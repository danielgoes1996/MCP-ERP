#!/usr/bin/env python3
"""
LLM-powered PDF parser for bank statements
Uses Claude (Anthropic) to intelligently extract and categorize transactions
"""
import requests
import json
import logging
import os
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple, Union
from core.bank_statements_models import (
    BankTransaction,
    MovementKind,
    TransactionType,
    infer_movement_kind,
    should_skip_transaction,
)
from core.robust_pdf_parser import RobustPDFParser
from core.bank_detector import BankDetector
from core.duplicate_prevention import DuplicateDetector
from core.pdf_extraction_validator import PDFExtractionValidator, validate_pdf_extraction
from core.extraction_audit_logger import log_extraction_start, log_extraction_complete, log_extraction_failed
from core.text_cleaner import PDFTextCleaner
from core.cost_analytics import cost_analytics

# Import LLM configuration
try:
    from config.llm_config import LLMConfig, ModelTier
except ImportError:
    # Fallback if config not available
    class LLMConfig:
        DEFAULT_MODEL = "claude-3-haiku-20240307"
        @classmethod
        def select_model_for_task(cls, *args, **kwargs):
            return cls.DEFAULT_MODEL

logger = logging.getLogger(__name__)


class LLMPDFParser:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-3-haiku-20240307"
        self.robust_parser = RobustPDFParser()
        self.duplicate_detector = DuplicateDetector()
        self.validator = PDFExtractionValidator()
        self.text_cleaner = PDFTextCleaner()
        self.bank_detector = BankDetector()
        self.company_context: Optional[Dict[str, Any]] = None
        self._context_payload_json: Optional[str] = None
        self._company_context_confidence: Optional[float] = None
        self._company_context_version: Optional[int] = None
        self._last_model_used: Optional[str] = self.model

        if not self.api_key:
            logger.warning("⚠️ Anthropic API key no configurada")

    def parse_bank_statement_with_llm(self, pdf_path: str, account_id: int, user_id: int, tenant_id: int, use_gemini_ocr: bool = True) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """Parse PDF using LLM for accuracy"""

        # Start audit logging
        pdf_filename = os.path.basename(pdf_path)
        pdf_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
        audit_id = log_extraction_start(tenant_id, user_id, account_id, pdf_filename, pdf_size, "llm")

        start_time = datetime.now()
        errors_encountered = []
        warnings_encountered = []
        api_calls_made = 0
        gemini_used = False

        try:
            # Check if we should use Gemini for OCR
            if use_gemini_ocr and os.getenv('USE_GEMINI_OCR', 'true').lower() == 'true':
                try:
                    from core.gemini_ocr_extractor import extract_pdf_with_gemini
                    logger.info(f"🌟 Using Gemini 2.0 Flash for OCR extraction")
                    raw_text = extract_pdf_with_gemini(pdf_path)
                    gemini_used = True
                    warnings_encountered.append("Used Gemini 2.0 Flash for OCR extraction")
                except Exception as e:
                    logger.warning(f"⚠️ Gemini OCR failed, falling back to traditional extraction: {e}")
                    errors_encountered.append(f"Gemini OCR failed: {str(e)[:100]}")
                    # Fall back to traditional extraction
                    raw_text = self.robust_parser.extract_text(pdf_path)
            else:
                # Traditional text extraction
                logger.info(f"🤖 Starting LLM-powered parsing for {pdf_path}")
                raw_text = self.robust_parser.extract_text(pdf_path)

            # NEW: Bank compatibility validation
            # TODO: Get actual account bank name from database
            # For now, we'll continue processing but log warnings
            bank_validation = self.bank_detector.validate_pdf_account_compatibility(raw_text, "Unknown")

            if bank_validation['detected_bank']:
                logger.info(f"🏦 Detected bank in PDF: {bank_validation['detected_bank']}")

            if bank_validation['warning_message']:
                logger.warning(f"⚠️ Bank compatibility issue: {bank_validation['warning_message']}")
                warnings_encountered.append(bank_validation['warning_message'])

            # PRODUCTION FIX: Skip text cleaning for non-JUL months to avoid losing transactions
            if 'DIC.' in raw_text or 'ENE.' in raw_text or 'FEB.' in raw_text or 'MAR.' in raw_text or 'ABR.' in raw_text or 'MAY.' in raw_text or 'AGO.' in raw_text or 'SEP.' in raw_text or 'OCT.' in raw_text or 'NOV.' in raw_text:
                logger.info(f"🎯 Skipping text cleaning for non-JUL month to preserve all transactions...")
                cleaned_text = raw_text
            else:
                # Clean and reconstruct text before processing
                logger.info(f"🧹 Cleaning and reconstructing PDF text...")
                cleaned_text = self.text_cleaner.clean_and_reconstruct(raw_text)

            # Get cleaning statistics
            cleaning_stats = self.text_cleaner.get_cleaning_stats(raw_text, cleaned_text)
            logger.info(f"📊 Cleaning stats: removed {cleaning_stats['lines_removed']} lines, " +
                       f"{cleaning_stats['jul_lines_removed']} JUL lines")

            # 🚀 PRODUCTION FIX: Force direct robust parsing for maximum extraction quality
            logger.info(f"🎯 Using direct robust parsing for maximum extraction quality...")
            chunks = []  # Initialize chunks for logging
            try:
                all_transactions, direct_summary = self.robust_parser.parse_transactions(
                    cleaned_text, account_id, user_id, tenant_id, pdf_path
                )
                logger.info(f"✅ Direct robust parsing extracted {len(all_transactions)} transactions")
                api_calls_made = 0  # No API calls made
                warnings_encountered.append("Used direct robust parsing for maximum reliability")
            except Exception as e:
                logger.error(f"❌ Direct robust parsing failed, falling back to chunked LLM: {e}")

                # Fallback to original chunked approach
                chunks = self._split_text_for_llm(cleaned_text)
                all_transactions = []
                llm_success_count = 0  # Track how many chunks succeeded with LLM

                for i, chunk in enumerate(chunks):
                    # Check if chunk contains transactions before processing
                    transaction_indicators = ['JUL.', 'AGO.', 'SEP.', 'OCT.', 'NOV.', 'DIC.',
                                            'ENE.', 'FEB.', 'MAR.', 'ABR.', 'MAY.', 'JUN.',
                                            'DEPOSITO', 'CARGO', 'ABONO', 'SPEI', 'TRANSFERENCIA']

                    has_transactions = any(indicator in chunk.upper() for indicator in transaction_indicators)
                    # Count any month abbreviation, not just JUL
                    transaction_count = sum(chunk.upper().count(month) for month in ['JUL.', 'AGO.', 'SEP.', 'OCT.', 'NOV.', 'DIC.', 'ENE.', 'FEB.', 'MAR.', 'ABR.', 'MAY.', 'JUN.'])

                    if not has_transactions or transaction_count == 0:
                        logger.info(f"📄 Skipping chunk {i+1}/{len(chunks)} (no transactions detected)")
                        continue

                    logger.info(f"📄 Processing chunk {i+1}/{len(chunks)} ({transaction_count} potential transactions)")

                    try:
                        transactions = self._parse_chunk_with_llm(chunk, account_id, user_id, tenant_id)
                        api_calls_made += 1  # Track API usage
                        llm_success_count += 1  # LLM succeeded
                        all_transactions.extend(transactions)
                        logger.info(f"✅ Extracted {len(transactions)} transactions from chunk {i+1}")
                    except Exception as e:
                        error_msg = f"LLM parsing failed for chunk {i+1}: {e}"
                        logger.warning(f"⚠️ {error_msg}")
                        errors_encountered.append(error_msg)
                        fallback_transactions = self._fallback_parse_chunk(chunk, account_id, user_id, tenant_id)
                        all_transactions.extend(fallback_transactions)
                        logger.info(f"🔄 Fallback extracted {len(fallback_transactions)} transactions from chunk {i+1}")

                # 🚀 NEW: If ALL chunks failed with LLM, use direct robust parsing on full text
                if llm_success_count == 0 and len(chunks) > 0:
                    logger.warning(f"⚠️ ALL {len(chunks)} chunks failed with LLM. Using direct robust parsing on full text...")
                    try:
                        direct_transactions, direct_summary = self.robust_parser.parse_transactions(
                            cleaned_text, account_id, user_id, tenant_id, pdf_path
                        )
                        logger.info(f"🎯 Direct robust parsing extracted {len(direct_transactions)} transactions")

                        # Replace chunked results with direct results (better quality)
                        all_transactions = direct_transactions
                        warnings_encountered.append(f"Used direct robust parsing due to complete LLM failure")
                    except Exception as e:
                        logger.error(f"❌ Direct robust parsing also failed: {e}")
                        errors_encountered.append(f"Direct robust parsing failed: {e}")

            # Remove duplicates and calculate summary
            unique_transactions = self._remove_duplicates(all_transactions)
            summary = self._calculate_summary(unique_transactions)

            # VALIDATE EXTRACTION COMPLETENESS
            logger.info("🔍 Validating extraction completeness...")

            # Convert transactions to dict format for validation
            validation_transactions = []
            for txn in unique_transactions:
                validation_transactions.append({
                    'date': txn.date.strftime('%Y-%m-%d'),
                    'description': txn.description,
                    'amount': txn.amount,
                    'balance_after': txn.balance_after
                })

            # Run validation with expected balances if available
            initial_balance = None
            final_balance = None

            # Try to extract balance information from summary or transactions
            if unique_transactions:
                # Look for balance inicial transaction
                for txn in unique_transactions:
                    if 'balance inicial' in txn.description.lower():
                        initial_balance = txn.balance_after
                        break

                # Use the last transaction's balance as final
                sorted_txns = sorted(unique_transactions, key=lambda x: x.date)
                if sorted_txns and sorted_txns[-1].balance_after:
                    final_balance = sorted_txns[-1].balance_after

            validation_result = self.validator.validate_extraction_completeness(
                cleaned_text,
                validation_transactions,
                initial_balance,
                final_balance
            )

            # Log validation report
            validation_report = self.validator.generate_validation_report(validation_result)
            logger.info(f"\n{validation_report}")

            # Add validation results to summary
            summary['validation'] = validation_result
            summary['validation_passed'] = validation_result['is_complete']

            # If validation failed, log as warning but don't fail
            if not validation_result['is_complete']:
                logger.warning("⚠️ VALIDATION WARNING - Some transactions may be missing")
                for issue in validation_result['issues']:
                    if issue['severity'] == 'critical':
                        logger.warning(f"⚠️ WARNING: {issue['message']}")

            logger.info(f"✅ LLM parsing completed: {len(unique_transactions)} unique transactions")
            logger.info(f"🔍 Validation status: {'✅ PASSED' if validation_result['is_complete'] else '❌ FAILED'}")

            # Complete audit logging
            extraction_time = (datetime.now() - start_time).total_seconds()
            log_extraction_complete(
                audit_id,
                raw_text_length=len(cleaned_text),
                chunks_processed=len(chunks),
                transactions_extracted=len(all_transactions),
                transactions_after_dedup=len(unique_transactions),
                validation_results=validation_result,
                extraction_time_seconds=extraction_time,
                initial_balance=initial_balance,
                final_balance=final_balance,
                errors=errors_encountered,
                warnings=warnings_encountered,
                api_calls_made=api_calls_made,
                api_cost_estimated=api_calls_made * 0.001  # Rough estimate
            )

            return unique_transactions, summary

        except Exception as e:
            # Log extraction failure
            error_msg = f"Critical error during PDF extraction: {e}"
            logger.error(f"❌ {error_msg}")
            log_extraction_failed(audit_id, error_msg)
            raise

    def _split_text_for_llm(self, text: str, max_chunk_size: int = 8000) -> List[str]:
        """Split text into manageable chunks for LLM processing without breaking transactions"""
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0

        # Pattern to identify transaction start (common across banks)
        transaction_patterns = [
            r'^[A-Z]{3}\.\s*\d{1,2}\s+\d{8,}',  # JUL. 01 12345678 (Inbursa)
            r'^\d{2}/\d{2}/\d{4}',              # 01/07/2024 (Other banks)
            r'^\d{4}-\d{2}-\d{2}',              # 2024-07-01 (ISO format)
            r'^[A-Z]{3}-\d{2}',                 # JUL-01 (Alternative format)
        ]

        for i, line in enumerate(lines):
            line_size = len(line)

            # Check if we're at max size and this might be a transaction start
            if current_size + line_size > max_chunk_size and current_chunk:
                # Check if current line starts a new transaction
                is_transaction_start = any(re.match(pattern, line.strip()) for pattern in transaction_patterns)

                if is_transaction_start:
                    # Safe to split here - complete previous chunk
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_size = line_size
                    logger.debug(f"🔀 Split chunk at transaction boundary: {line[:50]}...")
                else:
                    # Don't split mid-transaction, add to current chunk
                    current_chunk.append(line)
                    current_size += line_size

                    # If chunk gets too large, force split but with warning
                    if current_size > max_chunk_size * 2.0:  # Allow larger chunks
                        logger.warning(f"⚠️ Forced chunk split at line: {line[:50]}...")
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = []
                        current_size = 0
            else:
                current_chunk.append(line)
                current_size += line_size

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        logger.info(f"📊 Split into {len(chunks)} intelligent chunks (max size: {max_chunk_size})")
        return chunks

    def _parse_chunk_with_llm(self, text_chunk: str, account_id: int, user_id: int, tenant_id: int, retry_count: int = 0) -> List[BankTransaction]:
        """Envía un fragmento al LLM y devuelve las transacciones en formato estructurado."""

        prompt = self._build_prompt(text_chunk)

        # Intelligent model selection
        detected_bank = getattr(self, '_detected_bank', None)
        has_tables = '|' in text_chunk or '\t' in text_chunk  # Simple table detection
        selected_model = LLMConfig.select_model_for_task(
            text_length=len(text_chunk),
            retry_count=retry_count,
            has_tables=has_tables,
            bank_name=detected_bank
        )

        # Log model selection
        if selected_model != self.model:
            model_info = LLMConfig.get_model_info(selected_model)
            logger.info(f"🎯 Upgrading to {model_info['name']} for better accuracy (retry: {retry_count})")

        # Track GPT usage before calling
        confidence_before = 0.5  # Base confidence before LLM
        start_time = datetime.now()

        try:
            self._last_model_used = selected_model
            response_text = self._call_llm(prompt, model_override=selected_model)
            success = False
            transactions = []

            try:
                # Clean the response before JSON parsing
                cleaned_response = self._clean_llm_response(response_text)
                data = json.loads(cleaned_response)
                transactions = self._convert_llm_response_to_transactions(
                    data,
                    account_id,
                    user_id,
                    tenant_id,
                )
                success = len(transactions) > 0
                confidence_after = 0.95 if success else 0.6

                # Track successful GPT usage
                cost_analytics.track_gpt_usage(
                    field_name="bank_statement_parsing",
                    reason=f"LLM parsing for chunk with {len(text_chunk)} chars",
                    confidence_before=confidence_before,
                    confidence_after=confidence_after,
                    success=success,
                    merchant_type="bank_statement",
                    ticket_id=f"stmt_{account_id}_{int(start_time.timestamp())}"
                )

                return transactions

            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ LLM response was not valid JSON: {e}")
                logger.warning(f"Raw response (first 500 chars): {response_text[:500]}")

                # Track JSON parsing failure
                cost_analytics.track_gpt_usage(
                    field_name="bank_statement_parsing",
                    reason="LLM response JSON decode failed",
                    confidence_before=confidence_before,
                    confidence_after=0.7,  # Partial success
                    success=False,
                    merchant_type="bank_statement",
                    error_message=str(e)
                )

                # Try fallback parsing
                return self._try_fallback_json_parsing(response_text, account_id, user_id, tenant_id)

        except Exception as e:
            logger.error(f"❌ LLM API error: {e}")

            # Track API failure
            cost_analytics.track_gpt_usage(
                field_name="bank_statement_parsing",
                reason="LLM API call failed",
                confidence_before=confidence_before,
                confidence_after=0.0,
                success=False,
                merchant_type="bank_statement",
                error_message=str(e)
            )

            raise

    def _build_prompt(self, text_chunk: str) -> str:
        """Build prompt from template file for ContaFlow"""
        # Load prompt template
        prompt_file = "/Users/danielgoes96/Desktop/mcp-server/prompts/llm_bank_parser.txt"
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                template = f.read()
                context_block = self._format_company_context()
                if '{company_context}' in template:
                    template = template.replace('{company_context}', context_block)
                if '{bank_statement_text}' in template:
                    return template.replace('{bank_statement_text}', text_chunk)
                # Fallback inject context manually
                return f"{context_block}\n\n{template}\n\n{text_chunk}"
        except FileNotFoundError:
            logger.warning(f"⚠️ Prompt file not found at {prompt_file}, using fallback prompt")
            # Fallback to simplified ContaFlow prompt
            context_block = self._format_company_context()
            return (
                "You are a bank statement parser for ContaFlow. Extract ALL transactions and return as JSON array.\n\n"
                f"Company Context:\n{context_block}\n"
                "Required fields: date (YYYY-MM-DD), description, amount (positive/negative), transaction_type (credit/debit)\n"
                "Optional: reference, balance_after, category, movement_kind (Ingreso/Gasto/Transferencia)\n\n"
                "Return ONLY valid JSON array, no explanations.\n\n"
                f"Bank statement text:\n{text_chunk}\n\n"
                "JSON output:"
            )

    def _call_llm(self, prompt: str, model_override: str = None) -> str:
        if not self.api_key:
            raise RuntimeError("LLM API key not configured")

        # Use override model if provided, otherwise default
        model_to_use = model_override or self.model

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": model_to_use,
            "max_tokens": 4000,
            "temperature": 0,
            "system": "You are a bank statement parser for ContaFlow. Your task is to extract all transactions from bank statements and return them as structured JSON. Respond ONLY with valid JSON that matches the requested format exactly, with no additional text or explanations.",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code >= 400:
            error_detail = response.text
            logger.error(
                "❌ LLM API error %s: %s",
                response.status_code,
                error_detail[:500]
            )
            response.raise_for_status()

        data = response.json()
        content = data.get("content", [])
        if not content:
            raise ValueError("LLM response missing content")

        text_blocks = [block.get("text", "") for block in content if isinstance(block, dict)]
        response_text = "\n".join(filter(None, text_blocks)).strip()
        if not response_text:
            raise ValueError("LLM response empty")

        return response_text

    def _convert_llm_response_to_transactions(
        self,
        data: Any,
        account_id: int,
        user_id: int,
        tenant_id: int,
    ) -> List[BankTransaction]:
        """Convert LLM JSON response to BankTransaction objects"""
        transactions = []

        # Handle both array format (new ContaFlow) and object with transactions (legacy)
        if isinstance(data, list):
            transaction_list = data
        elif isinstance(data, dict) and 'transactions' in data:
            transaction_list = data['transactions']
        else:
            logger.warning("⚠️ Unexpected LLM response format")
            return []

        for txn_data in transaction_list:
            try:
                date_str = str(txn_data.get('date', '')).strip()
                txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()

                reference = str(txn_data.get('reference', '')).strip()
                if not reference:
                    reference = f"REF_{int(datetime.now().timestamp())}"

                amount = round(float(txn_data.get('amount', 0)), 2)
                description = str(txn_data.get('description', '')).strip()
                description = re.sub(r'\(\s*\)', '', description).strip()
                description_lower = description.lower()
                is_balance_entry = any(keyword in description_lower for keyword in (
                    'balance inicial',
                    'saldo inicial',
                ))

                # Get movement type from LLM response
                movement_type_llm = txn_data.get('movement_type', '').upper()

                if amount == 0 and not is_balance_entry:
                    continue

                # FIXED: Transaction type classification based on movement_type or description patterns
                if movement_type_llm == 'BALANCE' or is_balance_entry:
                    transaction_type = TransactionType.CREDIT  # Balance inicial is always credit
                elif movement_type_llm == 'CARGO':
                    transaction_type = TransactionType.DEBIT   # CARGO = gasto = debit
                elif movement_type_llm == 'ABONO':
                    transaction_type = TransactionType.CREDIT  # ABONO = ingreso = credit
                else:
                    # Fallback classification by description patterns
                    # Use description patterns to determine if it's an expense
                    is_expense = self._is_expense_transaction(description)
                    transaction_type = TransactionType.DEBIT if is_expense else TransactionType.CREDIT

                if should_skip_transaction(description) and not is_balance_entry:
                    continue

                category = txn_data.get('category', 'Sin categoría')
                confidence = 0.9

                balance_value = None
                balance_raw = txn_data.get('balance')
                if balance_raw not in (None, ""):
                    try:
                        # Format balance with exactly 2 decimal places like July
                        balance_value = float(f"{float(balance_raw):.2f}")
                    except (TypeError, ValueError):
                        balance_value = None

                # Classification based on CARGO/ABONO structure
                if movement_type_llm == 'BALANCE' or is_balance_entry:
                    movement_kind = MovementKind.TRANSFERENCIA
                elif movement_type_llm == 'CARGO':
                    movement_kind = MovementKind.GASTO  # CARGO = gasto
                elif movement_type_llm == 'ABONO':
                    movement_kind = MovementKind.INGRESO  # ABONO = ingreso
                else:
                    # Fallback: classify based on transaction_type
                    movement_kind = MovementKind.GASTO if transaction_type == TransactionType.DEBIT else MovementKind.INGRESO

                transaction = BankTransaction(
                    account_id=account_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    date=txn_date,
                    description=description[:500],
                    amount=amount,
                    transaction_type=transaction_type,
                    category=category,
                    confidence=confidence,
                    raw_data=f"PDF_LINE_{len(transactions)+1}: {date_str} {description[:50]}",
                    movement_kind=movement_kind,
                    reference=reference,
                    balance_after=balance_value
                )

                if self._context_payload_json:
                    transaction.context_used = self._context_payload_json
                    transaction.context_confidence = self._company_context_confidence
                    transaction.context_version = self._company_context_version
                if self._last_model_used:
                    transaction.ai_model = self._last_model_used

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"⚠️ Error converting LLM transaction: {e}")
                continue

        return transactions

    def _fallback_parse_chunk(self, chunk: str, account_id: int, user_id: int, tenant_id: int) -> List[BankTransaction]:
        """Fallback to robust parser if LLM fails"""
        logger.info("🔄 Using fallback robust parser")
        try:
            return self.robust_parser.parse_transactions(chunk, account_id, user_id, tenant_id)[0]
        except Exception as e:
            logger.warning(f"🔄 Robust parser fallback failed: {e}")
        return []

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    def set_company_context(self, context: Optional[Dict[str, Any]]) -> None:
        """Attach contextual memory used when composing prompts."""
        self.company_context = context or None
        self._context_payload_json = None
        self._company_context_confidence = None
        self._company_context_version = None

        if not context:
            return

        summary = context.get("summary") or "Contexto no disponible"
        profile = context.get("business_profile")
        if isinstance(profile, str):
            try:
                profile = json.loads(profile)
            except (TypeError, json.JSONDecodeError):
                pass

        self._company_context_confidence = context.get("confidence_score")
        self._company_context_version = context.get("context_version")

        payload = {
            "summary": summary,
            "business_profile": profile,
        }
        self._context_payload_json = json.dumps(payload, ensure_ascii=False)

    def _format_company_context(self) -> str:
        if not self.company_context:
            return "Contexto no disponible"

        summary = self.company_context.get("summary") or "Contexto no disponible"
        profile = self.company_context.get("business_profile")
        if isinstance(profile, str):
            try:
                profile = json.loads(profile)
            except (TypeError, json.JSONDecodeError):
                pass

        if isinstance(profile, (dict, list)):
            profile_text = json.dumps(profile, ensure_ascii=False, indent=2)
        elif profile:
            profile_text = str(profile)
        else:
            profile_text = "Perfil no disponible"

        confidence = self.company_context.get("confidence_score")
        version = self.company_context.get("context_version")
        extra_lines = []
        if confidence is not None:
            extra_lines.append(f"Confianza contexto: {confidence:.2f}")
        if version is not None:
            extra_lines.append(f"Versión contexto: {version}")

        extras_text = "\n".join(extra_lines)

        return (
            f"Resumen:\n{summary}\n\n"
            f"Perfil de negocio:\n{profile_text}\n"
            f"{extras_text}\n"
        ).strip()

    def get_last_model_used(self) -> Optional[str]:
        return self._last_model_used or self.model

    def _remove_duplicates(self, transactions: List[BankTransaction]) -> List[BankTransaction]:
        """Remove duplicate transactions - allow multiple legitimate transactions with same reference"""
        unique = []

        for txn in transactions:
            # Check if this is a true duplicate (exact same transaction)
            duplicate_found = False
            for existing_txn in unique:
                # Consider duplicate ONLY if ALL attributes match exactly
                if (txn.date == existing_txn.date and
                    abs(txn.amount - existing_txn.amount) < 0.01 and  # Same amount (within 1 cent)
                    txn.description.strip() == existing_txn.description.strip() and  # Exact description
                    getattr(txn, 'reference', None) == getattr(existing_txn, 'reference', None)):  # Same reference (or both None)

                    duplicate_found = True
                    break

            if not duplicate_found:
                unique.append(txn)

        return unique

    def _is_expense_transaction(self, description: str) -> bool:
        """Determine if a transaction is an expense based on description patterns"""
        desc_upper = description.upper()

        # First check for income patterns (these take precedence)
        income_patterns = [
            'DEPOSITO SPEI', 'DEPOSITO EFECTIVO', 'DEPOSITO TEF', 'DEPOSITO',
            'INTERES', 'INTERESES GANADOS', 'ABONO', 'TRANSFERENCIA RECIBIDA',
            'SPEI RECIBIDO', 'INGRESO', 'REEMBOLSO', 'DEVOLUCION'
        ]

        # If it matches income patterns, it's NOT an expense
        if any(pattern in desc_upper for pattern in income_patterns):
            return False

        # Common expense patterns
        expense_patterns = [
            'DOMICILIACION', 'TELMEX', 'APPLE', 'GOOGLE', 'STRIPE', 'PAYPAL',
            'RECARGA', 'COMISION', 'IVA', 'OPENAI', 'WSJ', 'NETFLIX', 'SPOTIFY',
            'AMAZON', 'UBER', 'RAPPI', 'MERCADO PAGO', 'OXXO', 'WALMART',
            'GASOLINERA', 'PEMEX', 'SHELL', 'CFE', 'CARGO', 'COMPRA',
            'PAGO', 'RETIRO', 'ATM', 'TARJETA', 'GPDC', 'HDM', 'NETPAY',
            'OFFICE MAX', 'GPO GASOLINERO', 'ATT CC COB'
        ]

        return any(pattern in desc_upper for pattern in expense_patterns)

    def _classify_movement_by_description(self, description: str, amount: float) -> MovementKind:
        """Classify movement based on description patterns"""
        desc_upper = description.upper()

        # Transfer patterns
        transfer_patterns = [
            'TRASPASO SPEI INBURED', 'TRASPASO ENTRE CUENTAS', 'DEQSA LAB',
            'TRASPASO SPEI', 'TRANSFERENCIA', 'TRANSFER'
        ]
        for pattern in transfer_patterns:
            if pattern in desc_upper:
                return MovementKind.TRANSFERENCIA

        # Income patterns
        income_patterns = [
            'DEPOSITO SPEI', 'DEPOSITO EFECTIVO', 'INTERESES GANADOS',
            'DEPOSITO', 'INTERES', 'REEMBOLSO'
        ]
        for pattern in income_patterns:
            if pattern in desc_upper:
                return MovementKind.INGRESO

        # Expense patterns
        expense_patterns = [
            'DOMICILIACION', 'TELMEX', 'APPLE', 'GOOGLE', 'STRIPE', 'PAYPAL',
            'RECARGA', 'COMISION', 'IVA', 'OPENAI', 'WSJ', 'NETFLIX', 'SPOTIFY',
            'AMAZON', 'UBER', 'RAPPI', 'MERCADO PAGO', 'OXXO'
        ]
        for pattern in expense_patterns:
            if pattern in desc_upper:
                return MovementKind.GASTO

        # Fallback to amount-based classification
        return MovementKind.INGRESO if amount > 0 else MovementKind.GASTO

    def _clean_llm_response(self, response_text: str) -> str:
        """Clean LLM response to extract valid JSON"""
        # Remove any text before the first {
        start_idx = response_text.find('{')
        if start_idx == -1:
            raise ValueError("No JSON found in response")

        # Remove any text after the last }
        end_idx = response_text.rfind('}')
        if end_idx == -1:
            raise ValueError("No complete JSON found in response")

        cleaned = response_text[start_idx:end_idx + 1]

        # Remove common markdown formatting
        cleaned = cleaned.replace('```json', '').replace('```', '')

        return cleaned.strip()

    def _try_fallback_json_parsing(self, response_text: str, account_id: int, user_id: int, tenant_id: int) -> List[BankTransaction]:
        """Try alternative methods to extract transactions from malformed JSON"""
        try:
            # Try to find individual transaction objects in the text
            transaction_pattern = r'\{[^{}]*"date"[^{}]*"amount"[^{}]*\}'
            matches = re.findall(transaction_pattern, response_text, re.DOTALL)

            transactions = []
            for match in matches:
                try:
                    txn_data = json.loads(match)
                    converted = self._convert_single_transaction(txn_data, account_id, user_id, tenant_id)
                    if converted:
                        transactions.append(converted)
                except:
                    continue

            logger.info(f"🔄 Fallback parsing recovered {len(transactions)} transactions")
            return transactions

        except Exception as e:
            logger.warning(f"🔄 Fallback parsing also failed: {e}")
            return []

    def _convert_single_transaction(self, txn_data: Dict, account_id: int, user_id: int, tenant_id: int) -> Optional[BankTransaction]:
        """Convert a single transaction dict to BankTransaction object"""
        try:
            date_str = str(txn_data.get('date', '')).strip()
            txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            reference = str(txn_data.get('reference', '')).strip()
            if not reference:
                reference = f"REF_{int(datetime.now().timestamp())}"

            amount = round(float(txn_data.get('amount', 0)), 2)

            description = str(txn_data.get('description', '')).strip()
            description = re.sub(r'\(\s*\)', '', description).strip()
            description_lower = description.lower()
            is_balance_entry = any(keyword in description_lower for keyword in (
                'balance inicial',
                'saldo inicial',
            ))

            # Get movement type from LLM response
            movement_type_llm = txn_data.get('movement_type', '').upper()

            if amount == 0 and not is_balance_entry:
                return None

            # Fix transaction type classification based on movement_type
            if movement_type_llm == 'BALANCE' or is_balance_entry:
                transaction_type = TransactionType.CREDIT  # Balance inicial is always credit
            elif movement_type_llm == 'CARGO':
                transaction_type = TransactionType.DEBIT   # CARGO = gasto = debit
            elif movement_type_llm == 'ABONO':
                transaction_type = TransactionType.CREDIT  # ABONO = ingreso = credit
            else:
                # Fallback classification by description patterns
                is_expense = self._is_expense_transaction(description)
                transaction_type = TransactionType.DEBIT if is_expense else TransactionType.CREDIT
            category = txn_data.get('category', 'Sin categoría')

            balance_value = None
            balance_raw = txn_data.get('balance')
            if balance_raw not in (None, ""):
                try:
                    balance_value = round(float(balance_raw), 2)
                except (TypeError, ValueError):
                    balance_value = None

            # Classification based on CARGO/ABONO structure
            if movement_type_llm == 'BALANCE' or is_balance_entry:
                movement_kind = MovementKind.TRANSFERENCIA
            elif movement_type_llm == 'CARGO':
                movement_kind = MovementKind.GASTO  # CARGO = gasto
            elif movement_type_llm == 'ABONO':
                movement_kind = MovementKind.INGRESO  # ABONO = ingreso
            else:
                # Fallback: classify based on transaction_type
                movement_kind = MovementKind.GASTO if transaction_type == TransactionType.DEBIT else MovementKind.INGRESO

            return BankTransaction(
                account_id=account_id,
                user_id=user_id,
                tenant_id=tenant_id,
                date=txn_date,
                description=description[:500],
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                confidence=0.85,
                raw_data=str(txn_data)[:1000],
                movement_kind=movement_kind,
                reference=reference,
                balance_after=balance_value
            )

        except Exception as e:
            logger.warning(f"⚠️ Error converting single transaction: {e}")
            return None

    def _calculate_summary(self, transactions: List[BankTransaction]) -> Dict[str, Any]:
        """Calculate summary statistics"""
        if not transactions:
            return {
                "total_transactions": 0,
                "total_credits": 0.0,
                "total_debits": 0.0,
                "period_start": None,
                "period_end": None,
                "opening_balance": 0.0,
                "closing_balance": 0.0,
                "total_incomes": 0.0,
                "total_expenses": 0.0,
                "total_transfers": 0.0,
            }

        credits_total = sum(t.amount for t in transactions if t.amount > 0)
        debits_total = sum(abs(t.amount) for t in transactions if t.amount < 0)
        incomes_total = sum(t.amount for t in transactions if t.movement_kind == MovementKind.INGRESO and t.amount > 0)
        expenses_total = sum(abs(t.amount) for t in transactions if t.movement_kind == MovementKind.GASTO and t.amount < 0)
        transfers_total = sum(abs(t.amount) for t in transactions if t.movement_kind == MovementKind.TRANSFERENCIA)

        dates = [t.date for t in transactions]

        return {
            "total_transactions": len(transactions),
            "total_credits": round(credits_total, 2),
            "total_debits": round(debits_total, 2),
            "period_start": min(dates) if dates else None,
            "period_end": max(dates) if dates else None,
            "opening_balance": 0.0,
            "closing_balance": 0.0,
            "total_incomes": round(incomes_total, 2),
            "total_expenses": round(expenses_total, 2),
            "total_transfers": round(transfers_total, 2),
        }


def parse_pdf_with_llm(file_path: str, account_id: int, user_id: int, tenant_id: int) -> Tuple[List[BankTransaction], Dict[str, Any]]:
    """Main function to parse PDF with LLM"""
    parser = LLMPDFParser()
    return parser.parse_bank_statement_with_llm(file_path, account_id, user_id, tenant_id)


if __name__ == "__main__":
    # Test the parser
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        transactions, summary = parse_pdf_with_llm(pdf_path, 1, 1, 1)
        print(f"✅ Extracted {len(transactions)} transactions")
        for txn in transactions[:5]:
            print(f"  {txn.date} | {txn.transaction_type} | ${txn.amount} | {txn.description}")
