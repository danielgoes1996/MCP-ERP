#!/usr/bin/env python3
"""
Gemini Native PDF Parser for ContaFlow
Uses Google's latest Gemini API with native PDF support
No need to convert PDFs to images - processes PDFs directly
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pathlib

# ContaFlow imports
from core.reconciliation.bank.bank_statements_models import (
    BankTransaction,
    TransactionType,
    MovementKind,
    infer_movement_kind,
)
from core.reports.cost_analytics import cost_analytics

# Google AI imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


logger = logging.getLogger(__name__)


class GeminiNativeParser:
    """
    Native PDF parser using Google's latest Gemini API
    Processes PDFs directly without conversion to images
    Supports files up to 50MB using File API
    """

    def __init__(self, api_key: str = None):
        """Initialize Gemini parser with API key"""
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY') or os.getenv('GEMINI_API_KEY')

        if not GEMINI_AVAILABLE:
            logger.error("❌ google-generativeai not installed. Run: pip install google-generativeai")
            raise ImportError("google-generativeai package required")

        if not self.api_key:
            logger.warning("⚠️ Google AI API key not configured")
            raise ValueError("Google AI API key required. Set GOOGLE_AI_API_KEY or GEMINI_API_KEY env variable")

        # Configure Gemini with API key
        genai.configure(api_key=self.api_key)

        # Model configuration
        self.model_name = "gemini-2.5-flash"  # Best price-performance model for PDF processing

        # Timeout (seconds) so we fail fast when the API is unreachable
        try:
            self.request_timeout = int(os.getenv('GEMINI_REQUEST_TIMEOUT', '180'))
        except ValueError:
            self.request_timeout = 180

        # Generation config
        self.generation_config = genai.GenerationConfig(
            temperature=0.1,
            max_output_tokens=65536,
            response_mime_type="application/json",
            response_schema=self._define_output_schema(),
        )

        logger.info("✅ Gemini Native PDF parser initialized")

    def parse_bank_statement(
        self,
        pdf_path: str,
        account_id: int,
        user_id: int,
        tenant_id: int,
        use_file_api: bool = None
    ) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """
        Parse bank statement PDF using native Gemini PDF support

        Args:
            pdf_path: Path to PDF file
            account_id: Account ID for the transactions
            user_id: User ID
            tenant_id: Tenant ID
            use_file_api: Force use of File API (auto-detect if None)

        Returns:
            Tuple of (transactions list, summary dict)
        """
        start_time = time.time()
        confidence_before = 0.3  # Base confidence

        try:
            logger.info(f"🚀 Starting Gemini native PDF parsing for {pdf_path}")

            # Check file size to determine method
            file_size = os.path.getsize(pdf_path)
            file_size_mb = file_size / (1024 * 1024)

            # Auto-detect: Use File API for files > 20MB
            if use_file_api is None:
                use_file_api = file_size_mb > 20

            if use_file_api or file_size_mb > 20:
                logger.info(f"📤 Using File API for large PDF ({file_size_mb:.1f}MB)")
                response = self._process_with_file_api(pdf_path)
            else:
                logger.info(f"📄 Processing PDF directly ({file_size_mb:.1f}MB)")
                try:
                    response = self._process_direct(pdf_path)
                except RuntimeError as direct_exc:
                    message = str(direct_exc).lower()
                    if 'timeout' in message or '504' in message:
                        logger.warning("⏱️ Gemini direct call timed out, retrying via File API")
                        response = self._process_with_file_api(pdf_path)
                        use_file_api = True  # Reflect final method used
                    else:
                        raise

            # Parse response
            extracted_data = self._parse_response(response)

            # Convert to BankTransaction objects
            year_hint = self._infer_year_hint(pdf_path, extracted_data)
            if year_hint:
                extracted_data.setdefault('raw_metadata', {})['year_hint'] = year_hint

            transactions = self._convert_to_transactions(
                extracted_data,
                account_id,
                user_id,
                tenant_id,
                year_hint=year_hint,
            )

            # Calculate summary
            summary = self._calculate_summary(transactions, extracted_data)

            # Add processing metadata
            processing_time = round(time.time() - start_time, 2)
            summary['metadata'] = {
                'parser': 'gemini-native-pdf',
                'model': self.model_name,
                'file_size_mb': round(file_size_mb, 2),
                'method': 'file_api' if use_file_api else 'direct',
                'processing_time': processing_time,
                'timestamp': datetime.utcnow().isoformat()
            }

            # Track usage
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                tokens_used = getattr(usage, 'total_token_count', 0)

                summary['metadata']['tokens'] = {
                    'prompt': getattr(usage, 'prompt_token_count', 0),
                    'output': getattr(usage, 'candidates_token_count', 0),
                    'total': tokens_used
                }

                # Track in cost analytics
                confidence_after = 0.95 if transactions else 0.5
                cost_analytics.track_gpt_usage(
                    field_name="bank_statement_gemini_native",
                    reason=f"Native PDF parsing with Gemini ({file_size_mb:.1f}MB)",
                    confidence_before=confidence_before,
                    confidence_after=confidence_after,
                    success=bool(transactions),
                    merchant_type="bank_statement",
                    ticket_id=f"gemini_native_{account_id}_{int(start_time)}"
                )

                logger.info(f"📊 Tokens used: {tokens_used}")

            logger.info(f"✅ Gemini extracted {len(transactions)} transactions in {processing_time}s")

            return transactions, summary

        except Exception as e:
            logger.error(f"❌ Gemini native parsing failed: {e}")

            # Track failure
            cost_analytics.track_gpt_usage(
                field_name="bank_statement_gemini_native",
                reason="Gemini native parsing failed",
                confidence_before=confidence_before,
                confidence_after=0.0,
                success=False,
                merchant_type="bank_statement",
                error_message=str(e)
            )

            raise

    def _process_direct(self, pdf_path: str) -> Any:
        """Process PDF directly (for files < 20MB)"""

        # Read PDF bytes
        filepath = pathlib.Path(pdf_path)
        pdf_bytes = filepath.read_bytes()

        # Build prompt
        prompt = self._build_extraction_prompt()

        # Create model
        model = genai.GenerativeModel(self.model_name)

        # Generate content with native PDF support
        try:
            response = model.generate_content(
                [
                    {
                        "mime_type": "application/pdf",
                        "data": pdf_bytes
                    },
                    prompt
                ],
                generation_config=self.generation_config,
                request_options={"timeout": self.request_timeout},
            )
            return response
        except Exception as exc:
            logger.warning(f"⚠️ Gemini direct call failed: {exc}")
            raise RuntimeError(f"Gemini direct processing failed: {exc}")

    def _process_with_file_api(self, pdf_path: str) -> Any:
        """Process PDF using File API (for large files or better performance)"""

        # Upload file using File API
        logger.info("📤 Uploading PDF to File API...")

        with open(pdf_path, 'rb') as pdf_file:
            uploaded_file = genai.upload_file(
                pdf_file,
                mime_type='application/pdf'
            )

        logger.info(f"✅ File uploaded: {uploaded_file.name}")

        # Build prompt
        prompt = self._build_extraction_prompt()

        # Create model
        model = genai.GenerativeModel(self.model_name)

        # Generate content using uploaded file
        try:
            response = model.generate_content(
                [uploaded_file, prompt],
                generation_config=self.generation_config,
                request_options={"timeout": self.request_timeout},
            )
            return response
        except Exception as exc:
            logger.warning(f"⚠️ Gemini File API call failed: {exc}")
            raise RuntimeError(f"Gemini File API processing failed: {exc}")
        finally:
            try:
                genai.delete_file(uploaded_file.name)
                logger.info(f"🧹 Deleted uploaded file {uploaded_file.name}")
            except Exception as cleanup_exc:
                logger.debug(f"⚠️ Unable to delete uploaded file {uploaded_file.name}: {cleanup_exc}")

    def _build_extraction_prompt(self) -> str:
        """Prompt que instruye a Gemini a devolver únicamente los campos necesarios."""
        return (
            "Eres un analista experto en estados de cuenta bancarios. "
            "Analiza el PDF adjunto y extrae únicamente los movimientos del periodo. "
            "Para cada movimiento captura: fecha, concepto, referencia (si existe), "
            "cargo_mxn, abono_mxn y saldo_mxn. Los montos deben ser numéricos; usa 0.0 cuando no aplique. "
            "Devuelve exclusivamente un arreglo JSON de objetos con esos campos, sin texto adicional ni comentarios." 
        )

    def _define_output_schema(self):
        """Schema JSON restringido usando Pydantic."""
        return {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string"},
                    "concepto": {"type": "string"},
                    "referencia": {"type": "string", "nullable": True},
                    "cargo_mxn": {"type": "number"},
                    "abono_mxn": {"type": "number"},
                    "saldo_mxn": {"type": "number"},
                },
                "required": [
                    "fecha",
                    "concepto",
                    "cargo_mxn",
                    "abono_mxn",
                    "saldo_mxn",
                ],
            },
        }

    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse and validate Gemini's response"""
        try:
            logger.info(f"📦 Gemini raw response object: {response}")
            logger.info(f"📦 Gemini text response: {getattr(response, 'text', None)}")
            logger.info(f"📦 Gemini parsed response: {getattr(response, 'parsed', None)}")
            response_text = ""
            structured = getattr(response, 'parsed', None)
            if structured is not None:
                if isinstance(structured, list):
                    data = []
                    for item in structured:
                        if hasattr(item, 'model_dump'):
                            data.append(item.model_dump())
                        else:
                            data.append(dict(item))
                else:
                    data = structured
            else:
                # Get text from response
                if hasattr(response, 'text'):
                    response_text = response.text
                else:
                    response_text = str(response)

                # Clean markdown if present
                response_text = response_text.strip()
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.startswith('```'):
                    response_text = response_text[3:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]

                # Parse JSON
                data = json.loads(response_text.strip())

            # If the model returned the new structured array, wrap it into the
            # legacy structure expected downstream.
            if isinstance(data, list):
                raw_transactions: List[Dict[str, Any]] = []
                def _safe_float(value: Any) -> float:
                    if value in (None, "", []):
                        return 0.0
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        try:
                            return float(str(value).replace(',', '').strip())
                        except Exception:
                            return 0.0

                for item in data:
                    fecha = item.get('fecha', '')
                    concepto = item.get('concepto', '')
                    referencia = item.get('referencia')
                    cargo = _safe_float(item.get('cargo_mxn'))
                    abono = _safe_float(item.get('abono_mxn'))
                    saldo_val = item.get('saldo_mxn')
                    saldo = _safe_float(saldo_val) if saldo_val is not None else None

                    amount_value = abono - cargo
                    type_raw = 'ABONO' if amount_value >= 0 else 'CARGO'

                    raw_transactions.append({
                        'date_raw': fecha,
                        'description_raw': concepto,
                        'amount_raw': str(amount_value),
                        'type_raw': type_raw,
                        'reference_raw': referencia if referencia is not None else '',
                        'balance_raw': '' if saldo is None else str(saldo),
                        'source_item': item,
                    })

                data = {
                    'raw_transactions': raw_transactions,
                    'transactions': raw_transactions,
                    'bank_info': {},
                    'balances': {},
                    'raw_metadata': {
                        'original_count': len(raw_transactions),
                        'structured_output': True,
                    },
                }

            # Normalize structure for backward compatibility
            if not isinstance(data.get('raw_transactions'), list):
                if isinstance(data.get('transactions'), list):
                    data['raw_transactions'] = data['transactions']
                else:
                    data['raw_transactions'] = []

            if not isinstance(data.get('transactions'), list):
                data['transactions'] = data['raw_transactions']

            if not isinstance(data.get('bank_info'), dict):
                data['bank_info'] = {}

            if not isinstance(data.get('balances'), dict):
                data['balances'] = {}

            if not isinstance(data.get('raw_metadata'), dict):
                data['raw_metadata'] = {}

            raw_count = len(data.get('raw_transactions', []))
            logger.info(f"✅ Parsed {raw_count} raw transactions from response")

            return data

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Gemini JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")

            # Return empty structure
            return {
                'transactions': [],
                'raw_transactions': [],
                'bank_info': {},
                'balances': {},
                'raw_metadata': {},
                'error': str(e),
                'raw_response': response_text[:1000]
            }

    def _infer_year_hint(self, pdf_path: str, extracted_data: Dict[str, Any]) -> Optional[int]:
        """Attempts to infer statement year from extracted metadata or filename."""
        import os
        import re

        candidates: List[int] = []
        year_pattern = re.compile(r"(20\d{2})")

        def collect(text: Optional[str]):
            if not text:
                return
            for match in year_pattern.findall(text):
                try:
                    candidates.append(int(match))
                except ValueError:
                    continue

        # Bank info or metadata might contain the period text with year
        bank_info = extracted_data.get('bank_info', {})
        if isinstance(bank_info, dict):
            for value in bank_info.values():
                if isinstance(value, str):
                    collect(value)

        raw_metadata = extracted_data.get('raw_metadata', {})
        if isinstance(raw_metadata, dict):
            collect(raw_metadata.get('period_text'))
            collect(raw_metadata.get('statement_period'))

        # Inspect raw transactions for explicit year
        raw_transactions = extracted_data.get('raw_transactions', []);
        for item in raw_transactions:
            if isinstance(item, dict):
                collect(item.get('fecha'))
                collect(item.get('date'))

        # Fallback to filename
        collect(os.path.basename(pdf_path))

        if candidates:
            # Choose the most recent year detected
            return sorted(set(candidates))[-1]

        return None

    def _convert_to_transactions(
        self,
        data: Dict[str, Any],
        account_id: int,
        user_id: int,
        tenant_id: int,
        year_hint: Optional[int] = None,
    ) -> List[BankTransaction]:
        """Convert raw extracted data to BankTransaction objects - MINIMAL PROCESSING"""
        transactions = []
        current_year = year_hint or datetime.now().year

        # Handle both old format (transactions) and new format (raw_transactions)
        raw_transactions = data.get('raw_transactions', data.get('transactions', []))

        for txn_data in raw_transactions:
            try:
                # Store the complete raw data for Claude processing later
                raw_json = json.dumps(txn_data, ensure_ascii=False)

                # Get raw date and try basic parsing
                date_raw = txn_data.get('date_raw', txn_data.get('date', ''))
                description_raw = txn_data.get('description_raw', txn_data.get('description', ''))
                amount_raw = txn_data.get('amount_raw', txn_data.get('amount', '0'))
                type_raw = txn_data.get('type_raw', txn_data.get('transaction_type', '')).upper()
                reference_raw = txn_data.get('reference_raw', txn_data.get('reference', ''))
                balance_raw = txn_data.get('balance_raw', txn_data.get('balance_after', ''))

                if not date_raw or not description_raw:
                    logger.debug(f"Skipping transaction with missing date or description: {txn_data}")
                    continue

                # Parse date - handle common Mexican formats
                txn_date = self._parse_mexican_date(date_raw, current_year)
                if not txn_date:
                    logger.warning(f"Could not parse date: {date_raw}")
                    continue

                # Parse amount - just remove $ and commas
                amount = self._parse_amount(amount_raw)

                # Determine transaction type from raw text
                if 'CARGO' in type_raw or 'DEBIT' in type_raw:
                    transaction_type = TransactionType.DEBIT
                    if amount > 0:
                        amount = -amount
                elif 'ABONO' in type_raw or 'CREDIT' in type_raw:
                    transaction_type = TransactionType.CREDIT
                    if amount < 0:
                        amount = abs(amount)
                else:
                    # Fallback: infer from amount sign
                    if amount >= 0:
                        transaction_type = TransactionType.CREDIT
                    else:
                        transaction_type = TransactionType.DEBIT

                # Basic movement kind inference (will be refined by Claude)
                movement_kind = infer_movement_kind(transaction_type, description_raw)

                # Parse balance if available
                balance_after = None
                if balance_raw:
                    balance_after = self._parse_amount(balance_raw)

                # Create transaction with raw data preserved
                transaction = BankTransaction(
                    account_id=account_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    date=txn_date,
                    description=description_raw[:500],  # Keep original description
                    amount=round(amount, 2),
                    transaction_type=transaction_type,
                    category=None,  # Let Claude categorize with context
                    reference=reference_raw[:100] if reference_raw else None,
                    balance_after=balance_after,
                    movement_kind=movement_kind,
                    confidence=0.5,  # Low confidence until Claude processes
                    raw_data=raw_json[:1000],
                    ai_model="gemini-2.5-flash-raw-extraction",
                    context_used=json.dumps({"extraction_only": True, "needs_processing": True})
                )

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"⚠️ Error converting raw transaction: {e}")
                logger.debug(f"Problem transaction: {txn_data}")
                continue

        return transactions

    def _parse_mexican_date(self, date_str: str, year: int) -> Optional[datetime.date]:
        """Parse common Mexican date formats"""
        import re
        from datetime import datetime

        date_str = date_str.strip().upper()

        # Month mapping for Spanish
        months_es = {
            'ENE': 1, 'ENERO': 1,
            'FEB': 2, 'FEBRERO': 2,
            'MAR': 3, 'MARZO': 3,
            'ABR': 4, 'ABRIL': 4,
            'MAY': 5, 'MAYO': 5,
            'JUN': 6, 'JUNIO': 6,
            'JUL': 7, 'JULIO': 7,
            'AGO': 8, 'AGOSTO': 8,
            'SEP': 9, 'SEPT': 9, 'SEPTIEMBRE': 9,
            'OCT': 10, 'OCTUBRE': 10,
            'NOV': 11, 'NOVIEMBRE': 11,
            'DIC': 12, 'DICIEMBRE': 12
        }

        try:
            # Try ISO format first
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return datetime.strptime(date_str, '%Y-%m-%d').date()

            # Try DD/MM/YYYY or DD-MM-YYYY
            if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', date_str):
                for fmt in ['%d/%m/%Y', '%d-%m-%Y']:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except:
                        pass

            # Try "15 JUL" or "JUL. 15" format
            for month_str, month_num in months_es.items():
                if month_str in date_str:
                    # Extract day number
                    day_match = re.search(r'\d{1,2}', date_str)
                    if day_match:
                        day = int(day_match.group())
                        return datetime(year, month_num, day).date()

            logger.debug(f"Could not parse date: {date_str}")
            return None

        except Exception as e:
            logger.debug(f"Date parsing error for '{date_str}': {e}")
            return None

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount from various formats"""
        if isinstance(amount_str, (int, float)):
            return float(amount_str)

        # Remove currency symbols and spaces
        amount_str = str(amount_str).replace('$', '').replace(',', '').replace(' ', '')

        try:
            return float(amount_str)
        except:
            logger.debug(f"Could not parse amount: {amount_str}")
            return 0.0

    def _calculate_summary(
        self,
        transactions: List[BankTransaction],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate summary statistics from raw extracted data"""

        # Extract bank info from new format
        bank_info = extracted_data.get('bank_info', {})
        balances = extracted_data.get('balances', {})

        # Parse opening and closing balances
        opening_balance = self._parse_amount(balances.get('opening_amount', 0))
        closing_balance = self._parse_amount(balances.get('closing_amount', 0))

        # Calculate totals from transactions
        total_credits = sum(abs(t.amount) for t in transactions if t.amount > 0)
        total_debits = sum(abs(t.amount) for t in transactions if t.amount < 0)

        # Get period from transactions
        dates = [t.transaction_date for t in transactions]
        period_start = min(dates).isoformat() if dates else None
        period_end = max(dates).isoformat() if dates else None

        summary = {
            # Bank information
            'bank_name': bank_info.get('bank_name'),
            'account_number': bank_info.get('account_number'),
            'client_name': bank_info.get('client_name'),
            'period_text': bank_info.get('period_text'),

            # Calculated periods
            'period_start': period_start,
            'period_end': period_end,

            # Balances
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
            'opening_balance_text': balances.get('opening_text'),
            'closing_balance_text': balances.get('closing_text'),

            # Transaction totals
            'total_credits': round(total_credits, 2),
            'total_debits': round(total_debits, 2),
            'transaction_count': len(transactions),

            # Parser info
            'parser_used': 'gemini-native-raw-extraction',
            'needs_claude_processing': True,
            'needs_enrichment_processing': True,

            # Raw data for the enrichment stage
            'raw_extraction': {
                'bank_info': bank_info,
                'balances': balances,
                'metadata': extracted_data.get('raw_metadata', {}),
                'transaction_count_raw': len(extracted_data.get('raw_transactions', [])),
                'raw_transactions': extracted_data.get('raw_transactions', [])[:400]
            }
        }

        # Add movement type totals (basic, will be refined by the enrichment stage)
        summary['total_incomes'] = sum(
            abs(t.amount) for t in transactions
            if t.movement_kind == MovementKind.INGRESO
        )
        summary['total_expenses'] = sum(
            abs(t.amount) for t in transactions
            if t.movement_kind == MovementKind.GASTO
        )
        summary['total_transfers'] = sum(
            abs(t.amount) for t in transactions
            if t.movement_kind == MovementKind.TRANSFERENCIA
        )

        return summary

    def parse_multiple_statements(
        self,
        pdf_paths: List[str],
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """
        Parse multiple bank statements in one request
        Maximum 1000 pages total across all PDFs

        Args:
            pdf_paths: List of paths to PDF files
            account_id: Account ID
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            Tuple of (all transactions, combined summary)
        """
        logger.info(f"🚀 Processing {len(pdf_paths)} bank statements")

        # Upload all files
        uploaded_files = []
        total_size = 0

        for pdf_path in pdf_paths:
            file_size = os.path.getsize(pdf_path)
            total_size += file_size

            logger.info(f"📤 Uploading {os.path.basename(pdf_path)}")
            with open(pdf_path, 'rb') as pdf_file:
                uploaded_file = genai.upload_file(
                    pdf_file,
                    mime_type='application/pdf'
                )
            uploaded_files.append(uploaded_file)

        logger.info(f"✅ Uploaded {len(uploaded_files)} files, total size: {total_size/(1024*1024):.1f}MB")

        # Build prompt for multiple files
        prompt = """
Analiza TODOS estos estados de cuenta bancarios y extrae TODAS las transacciones de cada uno.
Combina los resultados en una sola estructura JSON con todas las transacciones ordenadas por fecha.
""" + self._build_extraction_prompt()

        # Create model
        model = genai.GenerativeModel(self.model_name)

        # Process all files together
        response = model.generate_content(
            uploaded_files + [prompt],
            generation_config=self.generation_config
        )

        # Parse and convert
        extracted_data = self._parse_response(response)
        year_hint = self._infer_year_hint(pdf_path, extracted_data)
        if year_hint:
            extracted_data.setdefault('raw_metadata', {})['year_hint'] = year_hint

        transactions = self._convert_to_transactions(
            extracted_data,
            account_id,
            user_id,
            tenant_id,
            year_hint=year_hint,
        )

        summary = self._calculate_summary(transactions, extracted_data)
        summary.setdefault('metadata', {})
        summary['metadata'].update({
            'parser': summary.get('parser_used', 'gemini-native-raw-extraction'),
            'files_processed': len(pdf_paths)
        })

        return transactions, summary


# Standalone functions for easy integration
def parse_with_gemini_native(
    pdf_path: str,
    account_id: int,
    user_id: int,
    tenant_id: int,
    api_key: str = None
) -> Tuple[List[BankTransaction], Dict[str, Any]]:
    """
    Parse bank statement with native Gemini PDF support

    Args:
        pdf_path: Path to PDF file
        account_id: Account ID
        user_id: User ID
        tenant_id: Tenant ID
        api_key: Optional Google AI API key

    Returns:
        Tuple of (transactions, summary)
    """
    parser = GeminiNativeParser(api_key)
    return parser.parse_bank_statement(pdf_path, account_id, user_id, tenant_id)


def parse_multiple_with_gemini(
    pdf_paths: List[str],
    account_id: int,
    user_id: int,
    tenant_id: int,
    api_key: str = None
) -> Tuple[List[BankTransaction], Dict[str, Any]]:
    """
    Parse multiple bank statements with Gemini

    Args:
        pdf_paths: List of PDF file paths
        account_id: Account ID
        user_id: User ID
        tenant_id: Tenant ID
        api_key: Optional Google AI API key

    Returns:
        Tuple of (all transactions, combined summary)
    """
    parser = GeminiNativeParser(api_key)
    return parser.parse_multiple_statements(pdf_paths, account_id, user_id, tenant_id)
