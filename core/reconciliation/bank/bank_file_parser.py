"""
Parser para archivos de estados de cuenta bancarios
Soporta PDF y Excel con extracción inteligente de transacciones
"""

import re
import os
try:
    import pandas as pd
except ImportError:  # pragma: no cover - pandas no disponible en algunos entornos
    pd = None
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import PyPDF2
from io import BytesIO

from core.reconciliation.bank.bank_rules_loader import load_bank_rules, merge_unique
from core.reconciliation.bank.bank_detector import BankDetector
from core.reconciliation.bank.bank_statements_models import (
    BankTransaction,
    MovementKind,
    TransactionType,
    infer_movement_kind,
    should_skip_transaction,
    normalize_description,
)
# AI Bank Classifier (optional - falls back to rule-based if not available)
try:
    from core.reconciliation.bank.ai_bank_classifier import AIBankClassifier
    AI_CLASSIFIER_AVAILABLE = True
except ImportError:
    AI_CLASSIFIER_AVAILABLE = False
    logger.info("⚠️ AI Bank Classifier not available, using rule-based detection only")

logger = logging.getLogger(__name__)

# PostgreSQL configuration for MSI detection
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}


class BankFileParser:
    """Parser universal para estados de cuenta bancarios"""

    def __init__(self):
        # Patrones comunes para detectar transacciones en texto
        self.date_patterns = [
            r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\b',  # DD/MM/YYYY o DD-MM-YYYY
            r'\b(\d{2,4})[\/\-](\d{1,2})[\/\-](\d{1,2})\b',  # YYYY/MM/DD o YYYY-MM-DD
            r'\b(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s*\d{1,2}\b',
        ]

        # Patrones para detectar montos
        self.amount_patterns = [
            r'[\$]?\s*([+-]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56 o 1,234.56
            r'[\$]?\s*([+-]?\d+(?:\.\d{2})?)',  # $123.45 o 123.45
        ]

        # Palabras clave para identificar tipo de transacción
        self.credit_keywords = [
            'deposito', 'abono', 'transferencia recibida', 'interes', 'intereses', 'devolucion',
            'ingreso', 'credito', 'deposito electronico', 'spei recibido', 'ganado', 'ganados'
        ]

        self.debit_keywords = [
            'cargo', 'retiro', 'pago', 'compra', 'comision', 'domiciliacion',
            'transferencia enviada', 'spei enviado', 'debito', 'iva'
        ]

        self.reference_pattern = re.compile(r'\b[A-Z0-9]{6,}\b')

        # Preserve baselines so per-bank rules can extend them safely
        self.base_credit_keywords = list(self.credit_keywords)
        self.base_debit_keywords = list(self.debit_keywords)
        self.base_amount_patterns = list(self.amount_patterns)

        self.bank_detector = BankDetector()
        self.last_bank_rules_applied: Optional[str] = None

        # AI Bank Classifier (optional)
        self.ai_classifier = None
        if AI_CLASSIFIER_AVAILABLE:
            try:
                # Usar Gemini por defecto (más barato y rápido)
                use_gemini = os.getenv("GEMINI_API_KEY") is not None
                self.ai_classifier = AIBankClassifier(use_gemini=use_gemini)
                logger.info("✅ AI Bank Classifier initialized")
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize AI classifier: {e}")
                self.ai_classifier = None

        self.prefer_first_amount = False
        self.has_running_balance_column = False
        self.merge_multiline_concepts = False
        self.custom_line_regexes: List[re.Pattern] = []
        self.custom_skip_keywords: set[str] = set()
        self.current_year_hint: Optional[int] = None

        self._reset_dynamic_rules()

    def _reset_dynamic_rules(self) -> None:
        """Restore parser keywords/patterns to their base values."""
        self.credit_keywords = list(self.base_credit_keywords)
        self.debit_keywords = list(self.base_debit_keywords)
        self.amount_patterns = list(self.base_amount_patterns)
        self.last_bank_rules_applied = None
        self.prefer_first_amount = False
        self.has_running_balance_column = False
        self.merge_multiline_concepts = False
        self.custom_line_regexes = []
        self.custom_skip_keywords = set()
        self.current_year_hint = None

    def _apply_bank_rules(self, bank_name: Optional[str]) -> None:
        if not bank_name:
            return

        rules = load_bank_rules(bank_name)
        if not rules:
            return

        credit_additions = [kw.lower() for kw in rules.get('credit_keywords', [])]
        if credit_additions:
            merge_unique(self.credit_keywords, credit_additions)

        debit_additions = [kw.lower() for kw in rules.get('debit_keywords', [])]
        if debit_additions:
            merge_unique(self.debit_keywords, debit_additions)

        for pattern in rules.get('amount_patterns', []):
            pattern = pattern.strip()
            if pattern and pattern not in self.amount_patterns:
                self.amount_patterns.append(pattern)

        for skip in rules.get('skip_patterns', []):
            normalized = skip.strip().lower()
            if normalized:
                self.custom_skip_keywords.add(normalized)

        self.merge_multiline_concepts = bool(rules.get('merge_multiline_concepts', self.merge_multiline_concepts))
        self.prefer_first_amount = bool(rules.get('prefer_first_amount', self.prefer_first_amount))
        self.has_running_balance_column = bool(rules.get('has_running_balance_column', self.has_running_balance_column))

        for pattern in rules.get('transaction_line_patterns', []):
            pattern = pattern.strip()
            if not pattern:
                continue
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                logger.warning("Invalid custom transaction pattern for %s: %s", bank_name, exc)
                continue
            self.custom_line_regexes.append(compiled)

        self.last_bank_rules_applied = bank_name
        logger.info("Applied bank-specific rules for %s", bank_name)

    def _get_account_info(self, account_id: int, tenant_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene información de la cuenta desde payment_accounts

        Returns:
            Dict con: id, account_name, bank_name, account_type, company_id, tenant_id
            None si no se encuentra la cuenta
        """
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(**POSTGRES_CONFIG)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT id, account_name, bank_name, account_type, company_id, tenant_id, status
                FROM payment_accounts
                WHERE id = %s AND tenant_id = %s
            """, [account_id, tenant_id])

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if not result:
                logger.warning(f"Account {account_id} not found for tenant {tenant_id}")
                return None

            account_info = dict(result)
            logger.info(f"Account info retrieved: {account_info.get('account_name')} (type: {account_info.get('account_type')})")
            return account_info

        except Exception as e:
            logger.error(f"Error retrieving account info: {e}")
            return None

    def _classify_statement_with_ai(
        self,
        pdf_text: str,
        file_name: str,
        account_id: int,
        tenant_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Clasifica el estado de cuenta con AI y actualiza payment_accounts si necesario

        🤖 Usa LLM para detectar:
        - Banco (cualquier banco mexicano)
        - Tipo de cuenta (credit_card, debit_card, checking, savings)
        - Período del estado
        - Metadata adicional

        🔄 Si detecta que account_type es diferente al registrado, lo actualiza automáticamente

        Returns:
            Dict con clasificación o None si falla
        """
        if not self.ai_classifier:
            logger.info("⚠️ AI classifier not available, skipping AI classification")
            return None

        try:
            logger.info(f"🤖 Classifying statement with AI: {file_name}")
            classification = self.ai_classifier.classify_statement(
                pdf_text=pdf_text,
                file_name=file_name,
                use_cache=True
            )

            logger.info(
                f"✅ AI Classification: {classification['banco']} - "
                f"{classification['account_type']} (confidence: {classification['confidence']:.2%})"
            )

            # Verificar si necesitamos actualizar payment_accounts
            account_info = self._get_account_info(account_id, tenant_id)
            if not account_info:
                return classification

            current_account_type = account_info.get('account_type')
            current_bank = account_info.get('bank_name')
            detected_account_type = classification['account_type']
            detected_bank = classification['banco']

            # Actualizar si hay diferencias significativas y alta confianza (>80%)
            needs_update = False
            update_fields = {}

            if classification['confidence'] >= 0.80:
                if current_account_type != detected_account_type:
                    logger.info(
                        f"🔄 Account type mismatch: DB has '{current_account_type}', "
                        f"AI detected '{detected_account_type}' - Updating..."
                    )
                    update_fields['account_type'] = detected_account_type
                    needs_update = True

                # Actualizar banco si difiere (solo si confianza muy alta >90%)
                if classification['confidence'] >= 0.90 and current_bank != detected_bank:
                    logger.info(
                        f"🔄 Bank mismatch: DB has '{current_bank}', "
                        f"AI detected '{detected_bank}' - Updating..."
                    )
                    update_fields['bank_name'] = detected_bank
                    needs_update = True

            if needs_update:
                self._update_payment_account(account_id, tenant_id, update_fields, classification)

            return classification

        except Exception as e:
            logger.error(f"❌ AI classification failed: {e}", exc_info=True)
            return None

    def _update_payment_account(
        self,
        account_id: int,
        tenant_id: int,
        update_fields: Dict[str, str],
        classification: Dict[str, Any]
    ):
        """
        Actualiza payment_accounts con info detectada por AI

        Args:
            account_id: ID de la cuenta
            tenant_id: ID del tenant
            update_fields: Dict con campos a actualizar (account_type, bank_name, etc.)
            classification: Clasificación completa del AI
        """
        try:
            import psycopg2

            conn = psycopg2.connect(**POSTGRES_CONFIG)
            cursor = conn.cursor()

            # Construir query dinámico
            set_clause = ", ".join([f"{field} = %s" for field in update_fields.keys()])
            values = list(update_fields.values())
            values.extend([account_id, tenant_id])

            query = f"""
                UPDATE payment_accounts
                SET {set_clause},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND tenant_id = %s
            """

            cursor.execute(query, values)
            conn.commit()

            logger.info(
                f"✅ Updated payment_account {account_id}: {update_fields} "
                f"(AI confidence: {classification['confidence']:.2%})"
            )

            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"❌ Error updating payment_account: {e}", exc_info=True)

    def _extract_text_from_pdf_for_classification(self, file_path: str, max_pages: int = 3) -> str:
        """
        Extrae texto de las primeras páginas del PDF para clasificación AI

        Args:
            file_path: Ruta al PDF
            max_pages: Máximo de páginas a extraer (default: 3)

        Returns:
            Texto extraído (truncado a ~4000 caracteres)
        """
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                total_pages = len(pdf_reader.pages)
                pages_to_read = min(max_pages, total_pages)

                text_parts = []
                for page_num in range(pages_to_read):
                    try:
                        page = pdf_reader.pages[page_num]
                        text_parts.append(page.extract_text())
                    except Exception as e:
                        logger.warning(f"⚠️ Could not extract text from page {page_num}: {e}")
                        continue

                full_text = "\n".join(text_parts)

                # Truncar a ~4000 caracteres para no gastar muchos tokens
                if len(full_text) > 4000:
                    full_text = full_text[:4000]

                return full_text

        except Exception as e:
            logger.error(f"❌ Error extracting PDF text for classification: {e}")
            return ""

    def _detect_msi_candidates(
        self,
        transactions: List[BankTransaction],
        account_info: Dict[str, Any],
        period_start: Optional[date] = None,
        period_end: Optional[date] = None
    ) -> List[BankTransaction]:
        """
        Detecta candidatos MSI comparando transacciones con facturas

        Solo aplica si account_type == 'credit_card'

        Returns:
            Lista de transacciones enriquecidas con campos MSI
        """
        # Validar que sea tarjeta de crédito
        if account_info.get('account_type') != 'credit_card':
            logger.info(f"Account type '{account_info.get('account_type')}' is not MSI eligible, skipping MSI detection")
            return transactions

        if not transactions:
            logger.info("No transactions to analyze for MSI detection")
            return transactions

        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            # Determinar período de búsqueda de facturas
            if not period_start or not period_end:
                dates = [txn.transaction_date for txn in transactions if txn.transaction_date]
                if not dates:
                    logger.warning("No transaction dates found for MSI detection")
                    return transactions
                period_start = min(dates) - timedelta(days=30)  # Buffer de 30 días antes
                period_end = max(dates) + timedelta(days=7)     # Buffer de 7 días después

            company_id = account_info.get('company_id')
            tenant_id = account_info.get('tenant_id')

            logger.info(f"🔍 MSI Detection: Searching invoices for company {company_id} between {period_start} and {period_end}")

            # Buscar facturas con FormaPago '04' (tarjeta de crédito) en el período
            conn = psycopg2.connect(**POSTGRES_CONFIG)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    id, uuid, fecha_emision, forma_pago, total,
                    nombre_emisor, payment_account_id, es_msi, msi_meses
                FROM expense_invoices
                WHERE company_id = %s
                AND tenant_id = %s
                AND forma_pago = '04'
                AND fecha_emision BETWEEN %s AND %s
                AND status != 'cancelled'
                ORDER BY fecha_emision DESC
            """, [company_id, tenant_id, period_start, period_end])

            invoices = cursor.fetchall()
            cursor.close()
            conn.close()

            logger.info(f"✅ Found {len(invoices)} invoices with FormaPago '04' in period")

            if not invoices:
                logger.info("No invoices found for MSI matching")
                return transactions

            # Crear índice de facturas por monto (tolerancia de ±2%)
            invoice_by_amount: Dict[float, List[Dict]] = {}
            for inv in invoices:
                total = float(inv['total'])
                invoice_by_amount.setdefault(total, []).append(dict(inv))

            # Procesar cada transacción DEBIT (cargos en tarjeta de crédito)
            enriched_transactions = []
            msi_matches_count = 0

            for txn in transactions:
                # Solo procesar débitos (cargos) de tarjeta de crédito
                if txn.transaction_type != TransactionType.DEBIT:
                    enriched_transactions.append(txn)
                    continue

                txn_amount = abs(txn.amount)  # Usar valor absoluto para comparación

                # Buscar facturas con montos similares (tolerancia ±2%)
                tolerance = txn_amount * 0.02  # 2% de tolerancia
                matched_invoices = []

                for invoice_total, invs in invoice_by_amount.items():
                    if abs(invoice_total - txn_amount) <= tolerance:
                        matched_invoices.extend(invs)

                # Si hay exactamente 1 match, alta confianza
                # Si hay múltiples matches, confianza media-baja
                if len(matched_invoices) == 1:
                    inv = matched_invoices[0]
                    confidence = 0.95  # Alta confianza

                    # Validar que la factura no tenga ya MSI confirmado
                    if inv.get('es_msi') and inv.get('msi_meses'):
                        # Ya tiene MSI confirmado, no marcar como candidato
                        logger.debug(f"Invoice {inv['uuid'][:8]} already has MSI confirmed ({inv['msi_meses']} months)")
                        enriched_transactions.append(txn)
                        continue

                    # Calcular meses MSI probables basado en patrón de monto
                    msi_months = self._infer_msi_months(txn_amount, inv['total'])

                    txn.msi_candidate = True
                    txn.msi_invoice_id = inv['id']
                    txn.msi_months = msi_months
                    txn.msi_confidence = confidence
                    txn.ai_model = "bank_parser_v1"

                    msi_matches_count += 1
                    logger.info(
                        f"💳 MSI Match (conf={confidence:.0%}): Transaction ${txn_amount:.2f} → "
                        f"Invoice {inv['uuid'][:8]} ({inv['nombre_emisor'][:30]}) [{msi_months or '?'} months]"
                    )

                elif len(matched_invoices) > 1:
                    # Múltiples matches: menor confianza, no auto-asignar
                    confidence = 0.60 - (len(matched_invoices) * 0.05)  # Decrece con más matches
                    confidence = max(confidence, 0.30)  # Mínimo 30%

                    # Tomar el match más reciente como candidato principal
                    inv = max(matched_invoices, key=lambda x: x['fecha_emision'])

                    txn.msi_candidate = True
                    txn.msi_invoice_id = inv['id']
                    txn.msi_months = None  # Requiere confirmación manual
                    txn.msi_confidence = confidence
                    txn.ai_model = "bank_parser_v1"

                    msi_matches_count += 1
                    logger.info(
                        f"⚠️ MSI Multiple Matches (conf={confidence:.0%}): Transaction ${txn_amount:.2f} → "
                        f"{len(matched_invoices)} invoices (primary: {inv['uuid'][:8]})"
                    )

                enriched_transactions.append(txn)

            logger.info(f"🎯 MSI Detection Complete: {msi_matches_count}/{len(transactions)} transactions marked as MSI candidates")
            return enriched_transactions

        except Exception as e:
            logger.error(f"Error during MSI detection: {e}")
            # En caso de error, devolver transacciones sin modificar
            return transactions

    def _infer_msi_months(self, transaction_amount: float, invoice_total: float) -> Optional[int]:
        """
        Intenta inferir el número de meses MSI basado en la relación monto/total

        Si transaction_amount ≈ invoice_total → pago único (no MSI)
        Si transaction_amount ≈ invoice_total / N → N meses MSI

        Returns:
            Número de meses MSI detectados (3, 6, 9, 12, 18, 24) o None
        """
        valid_msi_months = [3, 6, 9, 12, 18, 24]

        # Tolerancia del 3% para cuentas con redondeo
        tolerance = 0.03

        for months in valid_msi_months:
            expected_payment = invoice_total / months
            ratio = abs(transaction_amount - expected_payment) / expected_payment

            if ratio <= tolerance:
                logger.debug(f"Inferred {months} MSI months: ${transaction_amount:.2f} ≈ ${invoice_total:.2f}/{months}")
                return months

        # Si no coincide con ningún patrón MSI, probablemente es pago único
        return None

    @staticmethod
    def _extract_detected_bank(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
        if not isinstance(metadata, dict):
            return None

        try:
            fallback_meta = metadata.get('intelligent_fallback')
            if isinstance(fallback_meta, dict):
                analysis = fallback_meta.get('bank_analysis')
                if isinstance(analysis, dict):
                    detected = analysis.get('detected_bank')
                    if detected:
                        return detected

            detected = metadata.get('detected_bank')
            if detected:
                return detected
        except Exception:  # pragma: no cover - defensive
            return None

        return None

    def _detect_bank_from_pdf(self, file_path: str) -> Optional[str]:
        """Attempt to detect bank by extracting text from the PDF."""
        try:
            text_chunks: List[str] = []
            with open(file_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                for page in reader.pages[:3]:  # first pages usually contain headers
                    try:
                        extracted = page.extract_text() or ""
                        text_chunks.append(extracted)
                    except Exception as exc:
                        logger.debug("Error extracting text while detecting bank: %s", exc)
            if not text_chunks:
                return None
            combined = "\n".join(text_chunks)
            return self.bank_detector.detect_bank_from_text(combined)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to detect bank from %s: %s", file_path, exc)
            return None

    def _apply_improved_classification(self, transactions):
        """Normalize classification and amount signs for parsed transactions."""
        normalized: List[BankTransaction] = []

        for txn in transactions:
            description_lower = (txn.description or '').lower()

            # Apply keyword-based classification consistent with legacy logic
            is_expense = self._is_expense_transaction(txn.description)
            if is_expense:
                txn.transaction_type = TransactionType.DEBIT
                txn.movement_kind = MovementKind.GASTO
            else:
                txn.transaction_type = TransactionType.CREDIT
                if 'traspaso' in description_lower or 'transferencia' in description_lower:
                    txn.movement_kind = MovementKind.TRANSFERENCIA
                else:
                    txn.movement_kind = MovementKind.INGRESO

            # Skip balance rows that occasionally leak as transactions
            if should_skip_transaction(txn.description):
                continue

            amount = float(getattr(txn, 'amount', 0) or 0)
            if txn.transaction_type == TransactionType.CREDIT and amount < 0:
                amount = abs(amount)
            elif txn.transaction_type == TransactionType.DEBIT and amount > 0:
                amount = -abs(amount)
            elif txn.transaction_type == TransactionType.DEBIT and amount == 0:
                # If we cannot determine the amount, skip the transaction to avoid noise
                continue

            txn.amount = round(amount, 2)

            normalized.append(txn)

        return normalized

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

    def parse_file(
        self,
        file_path: str,
        file_type: str,
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """
        Parsear archivo de estado de cuenta

        Returns:
            Tuple con (transacciones, resumen)
        """
        self._reset_dynamic_rules()
        detected_bank: Optional[str] = None

        # 🎯 Obtener información de la cuenta PRIMERO
        logger.info(f"📋 Retrieving account info for account_id={account_id}, tenant_id={tenant_id}")
        account_info = self._get_account_info(account_id, tenant_id)

        if account_info:
            logger.info(
                f"✅ Account: {account_info.get('account_name')} | "
                f"Type: {account_info.get('account_type')} | "
                f"Bank: {account_info.get('bank_name')}"
            )
        else:
            logger.warning(f"⚠️ Could not retrieve account info, MSI detection will be skipped")

        if file_type.lower() == 'pdf':
            # 🤖 AI Classification FIRST (detecta banco Y tipo de cuenta)
            ai_classification = None
            if self.ai_classifier:
                try:
                    # Extraer texto del PDF para clasificación AI
                    pdf_text = self._extract_text_from_pdf_for_classification(file_path)
                    if pdf_text:
                        ai_classification = self._classify_statement_with_ai(
                            pdf_text=pdf_text,
                            file_name=os.path.basename(file_path),
                            account_id=account_id,
                            tenant_id=tenant_id
                        )
                        if ai_classification and ai_classification.get('banco'):
                            detected_bank = ai_classification['banco']
                            logger.info(f"✅ Using AI-detected bank: {detected_bank}")
                except Exception as e:
                    logger.warning(f"⚠️ AI classification failed, falling back to rule-based: {e}")

            # 📋 Fallback a detección rule-based si AI no funcionó
            if not detected_bank:
                if 'inbursa' in file_path.lower():
                    detected_bank = 'inbursa'
                try:
                    detected_bank = detected_bank or self._detect_bank_from_pdf(file_path)
                except Exception as exc:
                    logger.debug("Bank detection hint failed: %s", exc)

            if detected_bank:
                try:
                    self._apply_bank_rules(detected_bank.lower())
                except Exception:
                    self._apply_bank_rules(detected_bank)

            if (detected_bank or '').lower() == 'inbursa':
                transactions, summary = self._parse_inbursa_pdf_with_layout(
                    file_path, account_id, user_id, tenant_id
                )
                summary = self._augment_summary(summary, transactions)

                # 💳 MSI Detection para tarjetas de crédito
                if account_info:
                    logger.info("🔍 Running MSI detection for Inbursa statement...")
                    transactions = self._detect_msi_candidates(
                        transactions, account_info,
                        summary.get('period_start'), summary.get('period_end')
                    )

                return transactions, summary

        try:
            if file_type.lower() in ['pdf']:
                # 🚀 PRODUCTION STRATEGY: Use robust multi-parser for maximum extraction
                # then apply LLM classification improvements
                try:
                    from core.intelligent_fallback_parser import intelligent_parser
                    logger.info("🎯 Using intelligent multi-parser for maximum extraction")
                    transactions, metadata = intelligent_parser.parse_with_intelligent_fallback(
                        file_path, account_id, user_id, tenant_id
                    )

                    detected_from_meta = self._extract_detected_bank(metadata)
                    if detected_from_meta:
                        detected_bank = detected_from_meta
                    elif not detected_bank:
                        detected_bank = self._detect_bank_from_pdf(file_path)
                    if detected_bank:
                        self._apply_bank_rules(detected_bank)

                    # Apply improved classification logic to all transactions
                    logger.info(f"🔧 Applying improved classification to {len(transactions)} transactions")

                    # Log before classification
                    if transactions:
                        sample_txn = transactions[0]
                        logger.info(f"Before classification: '{sample_txn.description}' -> {sample_txn.transaction_type}")

                    transactions = self._apply_improved_classification(transactions)

                    # Log after classification
                    if transactions:
                        sample_txn = transactions[0]
                        logger.info(f"After classification: '{sample_txn.description}' -> {sample_txn.transaction_type}")

                    # Create compatible summary
                    summary = {
                        'total_transactions': len(transactions),
                        'parser_used': 'intelligent_multi_parser_with_improved_classification',
                        'metadata': metadata
                    }
                    if detected_bank:
                        summary['detected_bank'] = detected_bank
                    summary = self._augment_summary(summary, transactions)
                    logger.info(f"✅ Multi-parser extracted {len(transactions)} transactions with improved classification")

                    # 💳 MSI Detection para tarjetas de crédito
                    if account_info:
                        logger.info("🔍 Running MSI detection for multi-parser transactions...")
                        transactions = self._detect_msi_candidates(
                            transactions, account_info,
                            summary.get('period_start'), summary.get('period_end')
                        )

                    return transactions, summary

                except Exception as e:
                    logger.warning(f"⚠️ Multi-parser failed, falling back to LLM parser: {e}")
                    # Fallback to LLM parser
                    try:
                        from core.llm_pdf_parser import LLMPDFParser
                        logger.info("🤖 Using LLM parser as fallback")
                        llm_parser = LLMPDFParser()
                        transactions, summary = llm_parser.parse_bank_statement_with_llm(
                            file_path, account_id, user_id, tenant_id
                        )
                        detected_bank = summary.get('metadata', {}).get('detected_bank') if isinstance(summary, dict) else None
                        if not detected_bank:
                            detected_bank = self._detect_bank_from_pdf(file_path)
                        self._apply_bank_rules(detected_bank)
                        transactions = self._apply_improved_classification(transactions)
                        summary = self._augment_summary(summary, transactions)
                        logger.info(f"✅ LLM parser extracted {len(transactions)} transactions")

                        # 💳 MSI Detection para tarjetas de crédito
                        if account_info:
                            logger.info("🔍 Running MSI detection for LLM parser transactions...")
                            transactions = self._detect_msi_candidates(
                                transactions, account_info,
                                summary.get('period_start'), summary.get('period_end')
                            )

                        return transactions, summary
                    except Exception as e2:
                        logger.warning(f"⚠️ LLM parser also failed, falling back to robust parser: {e2}")
                        try:
                            from core.ai_pipeline.parsers.robust_pdf_parser import parse_pdf_robust
                            logger.info("🔧 Using robust parser as final fallback")
                            transactions, summary = parse_pdf_robust(file_path, account_id, user_id, tenant_id)
                            summary = self._augment_summary(summary, transactions)
                            return transactions, summary
                        except Exception as e3:
                            logger.warning(f"⚠️ Robust parser also failed, using basic regex: {e3}")
                            return self._parse_pdf(file_path, account_id, user_id, tenant_id)
            elif file_type.lower() in ['xlsx', 'xls', 'excel']:
                transactions, summary = self._parse_excel(file_path, account_id, user_id, tenant_id)

                # 💳 MSI Detection para tarjetas de crédito
                if account_info:
                    logger.info("🔍 Running MSI detection for Excel transactions...")
                    transactions = self._detect_msi_candidates(
                        transactions, account_info,
                        summary.get('period_start'), summary.get('period_end')
                    )

                return transactions, summary

            elif file_type.lower() in ['csv']:
                transactions, summary = self._parse_csv(file_path, account_id, user_id, tenant_id)

                # 💳 MSI Detection para tarjetas de crédito
                if account_info:
                    logger.info("🔍 Running MSI detection for CSV transactions...")
                    transactions = self._detect_msi_candidates(
                        transactions, account_info,
                        summary.get('period_start'), summary.get('period_end')
                    )

                return transactions, summary
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            raise

    def _parse_pdf(
        self,
        file_path: str,
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """Parsear archivo PDF"""
        transactions = []
        summary = {
            'total_credits': 0.0,
            'total_debits': 0.0,
            'transaction_count': 0,
            'opening_balance': 0.0,
            'closing_balance': 0.0,
            'period_start': None,
            'period_end': None,
            'total_incomes': 0.0,
            'total_expenses': 0.0,
            'total_transfers': 0.0,
        }

        try:
            # Intentar primero con el parser robusto
            try:
                from core.ai_pipeline.parsers.robust_pdf_parser import parse_pdf_robust
                logger.info(f"🚀 Usando parser robusto para {file_path}")
                robust_transactions, robust_summary = parse_pdf_robust(file_path, account_id, user_id, tenant_id)

                if robust_transactions:
                    logger.info(f"✅ Parser robusto exitoso: {len(robust_transactions)} transacciones")
                    return robust_transactions, robust_summary

            except Exception as e:
                logger.warning(f"⚠️ Parser robusto falló: {e}, intentando método original")

            # Fallback al método original
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                full_text = ""

                for page in reader.pages:
                    try:
                        full_text += page.extract_text() + "\n"
                    except Exception as e:
                        logger.warning(f"Error extracting text from page: {e}")
                        continue

            detected_bank = self.bank_detector.detect_bank_from_text(full_text)
            self._apply_bank_rules(detected_bank)
            if detected_bank:
                summary['detected_bank'] = detected_bank

            # Extraer información del periodo y balances
            period_info = self._extract_period_info(full_text)
            summary.update(period_info)

            self.current_year_hint = None
            if period_info.get('period_end'):
                self.current_year_hint = period_info['period_end'].year
            elif period_info.get('period_start'):
                self.current_year_hint = period_info['period_start'].year

            # Extraer transacciones del texto
            parsed_transactions = self._extract_transactions_from_text(
                full_text, account_id, user_id, tenant_id
            )

            transactions.extend(parsed_transactions)

            # Calcular totales
            for txn in transactions:
                amount_abs = abs(txn.amount)
                if txn.transaction_type == TransactionType.CREDIT:
                    summary['total_credits'] += amount_abs
                else:
                    summary['total_debits'] += amount_abs

                if txn.movement_kind == MovementKind.INGRESO:
                    summary['total_incomes'] += amount_abs
                elif txn.movement_kind == MovementKind.GASTO:
                    summary['total_expenses'] += amount_abs
                elif txn.movement_kind == MovementKind.TRANSFERENCIA:
                    summary['total_transfers'] += amount_abs

            summary['transaction_count'] = len(transactions)

        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            raise

        summary = self._augment_summary(summary, transactions)
        return transactions, summary

    def _parse_excel(
        self,
        file_path: str,
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """Parsear archivo Excel"""
        transactions = []
        summary = {
            'total_credits': 0.0,
            'total_debits': 0.0,
            'transaction_count': 0,
            'opening_balance': 0.0,
            'closing_balance': 0.0,
            'period_start': None,
            'period_end': None,
            'total_incomes': 0.0,
            'total_expenses': 0.0,
            'total_transfers': 0.0,
        }

        try:
            if pd is None:
                raise ImportError("pandas es requerido para parsear archivos Excel")
            # Intentar leer diferentes formatos de Excel
            df = pd.read_excel(file_path, sheet_name=0)

            # Detectar columnas relevantes
            column_mapping = self._detect_excel_columns(df)

            if not column_mapping:
                raise ValueError("No se pudieron identificar las columnas del estado de cuenta")

            # Procesar cada fila
            for index, row in df.iterrows():
                try:
                    transaction = self._parse_excel_row(
                        row, column_mapping, account_id, user_id, tenant_id
                    )
                    if transaction:
                        transactions.append(transaction)
                except Exception as e:
                    logger.warning(f"Error parsing row {index}: {e}")
                    continue

            # Calcular totales y periodo
            if transactions:
                dates = [txn.transaction_date for txn in transactions if txn.transaction_date]
                if dates:
                    summary['period_start'] = min(dates)
                    summary['period_end'] = max(dates)

                for txn in transactions:
                    amount_abs = abs(txn.amount)
                    if txn.transaction_type == TransactionType.CREDIT:
                        summary['total_credits'] += amount_abs
                    else:
                        summary['total_debits'] += amount_abs

                    if txn.movement_kind == MovementKind.INGRESO:
                        summary['total_incomes'] += amount_abs
                    elif txn.movement_kind == MovementKind.GASTO:
                        summary['total_expenses'] += amount_abs
                    elif txn.movement_kind == MovementKind.TRANSFERENCIA:
                        summary['total_transfers'] += amount_abs

            summary['transaction_count'] = len(transactions)

        except Exception as e:
            logger.error(f"Error parsing Excel {file_path}: {e}")
            raise

        return transactions, summary

    def _parse_csv(
        self,
        file_path: str,
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """Parsear archivo CSV"""
        try:
            if pd is None:
                raise ImportError("pandas es requerido para parsear archivos CSV")
            # Intentar diferentes encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("No se pudo determinar la codificación del archivo CSV")

            # Use the DataFrame for CSV processing
            column_mapping = self._detect_excel_columns(df)
            if not column_mapping:
                raise ValueError("No se pudieron identificar las columnas del estado de cuenta CSV")

            transactions = []
            for index, row in df.iterrows():
                try:
                    transaction = self._parse_excel_row(row, column_mapping, account_id, user_id, tenant_id)
                    if transaction:
                        transactions.append(transaction)
                except Exception as e:
                    logger.warning(f"Error parsing CSV row {index}: {e}")
                    continue

            # Calculate summary
            summary = {
                'total_credits': 0.0, 'total_debits': 0.0, 'transaction_count': len(transactions),
                'opening_balance': 0.0, 'closing_balance': 0.0, 'period_start': None, 'period_end': None,
                'total_incomes': 0.0, 'total_expenses': 0.0, 'total_transfers': 0.0,
            }

            if transactions:
                dates = [txn.transaction_date for txn in transactions if txn.transaction_date]
                if dates:
                    summary['period_start'] = min(dates)
                    summary['period_end'] = max(dates)

                for txn in transactions:
                    amount_abs = abs(txn.amount)
                    if txn.transaction_type == TransactionType.CREDIT:
                        summary['total_credits'] += amount_abs
                    else:
                        summary['total_debits'] += amount_abs

                    if txn.movement_kind == MovementKind.INGRESO:
                        summary['total_incomes'] += amount_abs
                    elif txn.movement_kind == MovementKind.GASTO:
                        summary['total_expenses'] += amount_abs
                    elif txn.movement_kind == MovementKind.TRANSFERENCIA:
                        summary['total_transfers'] += amount_abs

            summary = self._augment_summary(summary, transactions)
            return transactions, summary

        except Exception as e:
            logger.error(f"Error parsing CSV {file_path}: {e}")
            raise

    def _detect_excel_columns(self, df: Any) -> Optional[Dict[str, str]]:
        """Detectar automáticamente las columnas relevantes en Excel"""
        column_mapping = {}

        # Normalizar nombres de columnas
        columns_lower = {col.lower(): col for col in df.columns}

        # Detectar columna de fecha
        date_keywords = ['fecha', 'date', 'dia', 'day']
        for keyword in date_keywords:
            matches = [col for col in columns_lower.keys() if keyword in col]
            if matches:
                column_mapping['date'] = columns_lower[matches[0]]
                break

        # Detectar columna de descripción
        desc_keywords = ['descripcion', 'description', 'concepto', 'detalle', 'desc']
        for keyword in desc_keywords:
            matches = [col for col in columns_lower.keys() if keyword in col]
            if matches:
                column_mapping['description'] = columns_lower[matches[0]]
                break

        # Detectar columnas de monto
        amount_keywords = ['monto', 'amount', 'importe', 'cantidad']
        cargo_keywords = ['cargo', 'debit', 'debito', 'salida']
        abono_keywords = ['abono', 'credit', 'credito', 'entrada', 'ingreso']

        # Buscar columnas de cargo y abono separadas
        for keyword in cargo_keywords:
            matches = [col for col in columns_lower.keys() if keyword in col]
            if matches:
                column_mapping['debit'] = columns_lower[matches[0]]
                break

        for keyword in abono_keywords:
            matches = [col for col in columns_lower.keys() if keyword in col]
            if matches:
                column_mapping['credit'] = columns_lower[matches[0]]
                break

        # Si no hay columnas separadas, buscar columna de monto general
        if 'debit' not in column_mapping and 'credit' not in column_mapping:
            for keyword in amount_keywords:
                matches = [col for col in columns_lower.keys() if keyword in col]
                if matches:
                    column_mapping['amount'] = columns_lower[matches[0]]
                    break

        # Detectar columna de saldo
        balance_keywords = ['saldo', 'balance', 'balance_after']
        for keyword in balance_keywords:
            matches = [col for col in columns_lower.keys() if keyword in col]
            if matches:
                column_mapping['balance'] = columns_lower[matches[0]]
                break

        # Verificar que tenemos las columnas mínimas
        if 'date' not in column_mapping:
            return None

        if ('amount' not in column_mapping and
            'debit' not in column_mapping and
            'credit' not in column_mapping):
            return None

        return column_mapping

    def _parse_excel_row(
        self,
        row,
        column_mapping: Dict[str, str],
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> Optional[BankTransaction]:
        """Parsear una fila de Excel/CSV"""
        try:
            # Extraer fecha
            date_col = column_mapping.get('date')
            if not date_col or (pd is not None and pd.isna(row[date_col])):
                return None

            txn_date = self._parse_date(row[date_col])
            if not txn_date:
                return None

            # Extraer descripción
            desc_col = column_mapping.get('description', '')
            description = str(row[desc_col]) if desc_col and not (pd is not None and pd.isna(row[desc_col])) else ''

            # Extraer monto y tipo
            amount = 0.0
            transaction_type = TransactionType.DEBIT

            if 'amount' in column_mapping:
                # Columna única de monto
                amount_val = row[column_mapping['amount']]
                if pd is not None and pd.isna(amount_val):
                    return None

                amount = float(str(amount_val).replace(',', '').replace('$', ''))
                transaction_type = TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT
                amount = abs(amount)

            elif 'debit' in column_mapping and 'credit' in column_mapping:
                # Columnas separadas de cargo y abono
                debit_val = row[column_mapping['debit']]
                credit_val = row[column_mapping['credit']]

                if pd is not None and not pd.isna(debit_val) and debit_val != 0:
                    amount = abs(float(str(debit_val).replace(',', '').replace('$', '')))
                    transaction_type = TransactionType.DEBIT
                elif pd is not None and not pd.isna(credit_val) and credit_val != 0:
                    amount = abs(float(str(credit_val).replace(',', '').replace('$', '')))
                    transaction_type = TransactionType.CREDIT
                else:
                    return None

            if amount == 0:
                return None

            # Refinar tipo basado en descripción
            transaction_type = self._classify_transaction_type(description, transaction_type)
            description = re.sub(r'\(\s*\)', '', description)
            if self._should_skip_description(description):
                return None

            movement_kind = infer_movement_kind(transaction_type, description)

            amount_signed = amount if transaction_type == TransactionType.CREDIT else -amount
            amount_signed = round(amount_signed, 2)

            if amount > 1_000_000:
                logger.debug(f"Skipping Excel row with unrealistic amount {amount}: {description[:60]}")
                return None

            # Extraer saldo si está disponible
            balance_after = None
            if 'balance' in column_mapping and not pd.isna(row[column_mapping['balance']]):
                try:
                    balance_after = float(str(row[column_mapping['balance']]).replace(',', '').replace('$', ''))
                except:
                    pass

            return BankTransaction(
                account_id=account_id,
                user_id=user_id,
                tenant_id=tenant_id,
                transaction_date=txn_date,
                description=description.strip(),
                amount=amount_signed,
                transaction_type=transaction_type,
                balance=balance_after,
                raw_data=row.to_json(),
                movement_kind=movement_kind
            )

        except Exception as e:
            logger.warning(f"Error parsing row: {e}")
            return None

    def _extract_period_info(self, text: str) -> Dict[str, Any]:
        """Extraer información de periodo y saldos del texto"""
        info = {
            'period_start': None,
            'period_end': None,
            'opening_balance': 0.0,
            'closing_balance': 0.0
        }

        # Buscar fechas de periodo
        period_patterns = [
            r'periodo\s+del?\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+al?\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'from\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+to\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        ]

        for pattern in period_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start_date = self._parse_date(match.group(1))
                end_date = self._parse_date(match.group(2))
                if start_date and end_date:
                    info['period_start'] = start_date
                    info['period_end'] = end_date
                    break

        # Buscar saldos
        balance_patterns = [
            r'saldo\s+inicial[:\s]+\$?\s*([+-]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'saldo\s+final[:\s]+\$?\s*([+-]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'balance\s+anterior[:\s]+\$?\s*([+-]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        ]

        for pattern in balance_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    if 'inicial' in pattern or 'anterior' in pattern:
                        info['opening_balance'] = float(matches[0].replace(',', ''))
                    elif 'final' in pattern:
                        info['closing_balance'] = float(matches[0].replace(',', ''))
                except:
                    pass

        return info

    def _extract_transactions_from_text(
        self,
        text: str,
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> List[BankTransaction]:
        """Extraer transacciones del texto PDF"""
        transactions_map = {}
        ordered_keys = []
        last_key = None

        def process_transaction(txn: BankTransaction):
            nonlocal last_key
            description_signature = normalize_description(txn.description)
            key = (
                txn.transaction_date.isoformat() if txn.transaction_date else '',
                description_signature,
                round(float(txn.amount or 0.0), 2),
            )

            if key in transactions_map:
                existing = transactions_map[key]
                existing.description = self._merge_descriptions(existing.description, txn.description)
                if getattr(txn, 'balance', None) is not None:
                    existing.balance = txn.balance
            else:
                transactions_map[key] = txn
                ordered_keys.append(key)

            last_key = key

        # Dividir en líneas y buscar patrones de transacciones
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Buscar líneas que parezcan transacciones
            transaction = None
            for regex in self.custom_line_regexes:
                match = regex.match(line)
                if match:
                    transaction = self._parse_custom_transaction_line(
                        match, line, account_id, user_id, tenant_id
                    )
                    break

            if not transaction and self._looks_like_transaction(line):
                transaction = self._parse_transaction_line(
                    line, account_id, user_id, tenant_id
                )

            if transaction:
                process_transaction(transaction)
                continue
            else:
                if self.merge_multiline_concepts and last_key and not self._should_skip_description(line):
                    extra_text = line.strip()
                    if extra_text:
                        existing = transactions_map.get(last_key)
                        if existing:
                            existing.description = self._merge_descriptions(existing.description, extra_text)
                    continue

        return [transactions_map[key] for key in ordered_keys]

    def _augment_summary(self, summary: Optional[Dict[str, Any]], transactions: List[BankTransaction]) -> Dict[str, Any]:
        """Fill in aggregate fields and validate balances for a summary dict."""
        summary = dict(summary or {})

        total_credits = sum(
            abs(float(txn.amount or 0))
            for txn in transactions
            if txn.transaction_type == TransactionType.CREDIT
        )
        total_debits = sum(
            abs(float(txn.amount or 0))
            for txn in transactions
            if txn.transaction_type == TransactionType.DEBIT
        )

        summary['total_credits'] = round(total_credits, 2)
        summary['total_debits'] = round(total_debits, 2)
        summary['transaction_count'] = summary.get('transaction_count') or len(transactions)

        balances = [txn.balance for txn in transactions if getattr(txn, 'balance', None) is not None]
        if balances:
            first_with_balance = next((txn for txn in transactions if getattr(txn, 'balance', None) is not None), None)
            if first_with_balance:
                opening = round(float(first_with_balance.balance) - float(first_with_balance.amount or 0), 2)
                summary.setdefault('opening_balance', opening)
            summary.setdefault('closing_balance', round(float(balances[-1]), 2))

        opening = summary.get('opening_balance')
        closing = summary.get('closing_balance')
        if opening is not None and closing is not None:
            balance_check = round(float(opening) + summary['total_credits'] - summary['total_debits'], 2)
            if abs(balance_check - float(closing)) > 0.5:
                logger.debug(
                    "Balance check mismatch: opening=%s credits=%s debits=%s closing=%s computed=%s",
                    opening,
                    summary['total_credits'],
                    summary['total_debits'],
                    closing,
                    balance_check,
                )

        return summary

    def _parse_inbursa_pdf_with_layout(
        self,
        file_path: str,
        account_id: int,
        user_id: int,
        tenant_id: int,
    ) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """Specialized extractor for Inbursa statements using pdfplumber layout data."""
        try:
            import pdfplumber  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive guard
            logger.warning("pdfplumber not available for Inbursa parsing: %s", exc)
            raise

        month_map = {
            'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12,
        }

        start_pattern = re.compile(r'^(?P<month>[A-Z]{3})\.\s*(?P<day>\d{2})\b')
        amount_regex = re.compile(r'-?\d[\d,]*\.\d{2}')
        ignore_prefixes = (
            'Página:', 'FECHA REFERENCIA', 'BANCO INBURSA', 'A partir', 'En caso',
            'Le recordamos', 'Rendimientos', 'Tasas expresadas', 'Tasa BRUTA',
            'TASA BRUTA', 'TASA NETA', 'Tipo de comprobante', 'Expedido en',
            'Receptor(', 'Regimen Fiscal', 'Método de Pago', 'Forma de pago',
            'Clave de unidad', 'Clave de Productos', 'Exportacion', 'R.F.C.',
            'Sello digital', 'Cadena original', 'Este documento', 'Totales',
            'CONSULTAS Y RECLAMACIONES', 'GLOSARIO', 'El producto descrito',
            'Incumplir sus obligaciones'
        )
        ignore_exact = {'n'}

        year_hint = self.current_year_hint
        if not year_hint:
            year_match = re.search(r'(20\d{2})', Path(file_path).stem)
            if year_match:
                year_hint = int(year_match.group(1))
            else:
                year_hint = datetime.utcnow().year
            self.current_year_hint = year_hint

        rows: List[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words(keep_blank_chars=False, use_text_flow=True)
                line_map: Dict[float, List[Dict[str, Any]]] = {}
                for word in words:
                    top = round(word['top'], 1)
                    line_map.setdefault(top, []).append(word)
                for top in sorted(line_map):
                    line_words = sorted(line_map[top], key=lambda item: item['x0'])
                    rows.append(' '.join(item['text'] for item in line_words).strip())

        raw_transactions: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for text in rows:
            if not text:
                continue
            match = start_pattern.match(text)
            if match:
                if current:
                    raw_transactions.append(current)
                month = month_map.get(match.group('month'), 0)
                if not month:
                    continue
                day = int(match.group('day'))
                rest = text[match.end():].strip()
                reference = None
                if rest:
                    parts = rest.split()
                    if parts and re.fullmatch(r'\d{5,}', parts[0]):
                        reference = parts[0]
                        rest = ' '.join(parts[1:])
                numbers = amount_regex.findall(rest)
                balance = amount = None
                if numbers:
                    balance = float(numbers[-1].replace(',', ''))
                    rest = rest.rsplit(numbers[-1], 1)[0].strip()
                    if len(numbers) >= 2:
                        amount = float(numbers[-2].replace(',', ''))
                        rest = rest.rsplit(numbers[-2], 1)[0].strip()
                current = {
                    'date': date(year_hint, month, day),
                    'description': rest.strip(),
                    'reference': reference,
                    'amount': amount,
                    'balance': balance,
                    'extras': [],
                    'raw_line': text.strip(),
                }
            elif current:
                current['extras'].append(text.strip())

        if current:
            raw_transactions.append(current)

        if not raw_transactions:
            return [], {}

        opening_balance = raw_transactions[0].get('balance')
        transactions: List[BankTransaction] = []
        prev_balance = opening_balance
        totals = {
            'total_credits': 0.0,
            'total_debits': 0.0,
            'total_incomes': 0.0,
            'total_expenses': 0.0,
            'total_transfers': 0.0,
        }

        # Skip balance inicial row if amount is None
        iterator = iter(raw_transactions)
        first = next(iterator)
        if first.get('amount') is None and should_skip_transaction(first.get('description')):
            prev_balance = first.get('balance')
        else:
            iterator = iter(raw_transactions)  # include first if not balance row

        for record in iterator:
            balance_after = record.get('balance')
            if balance_after is None:
                continue
            extras: List[str] = []
            for extra in record.get('extras', []):
                if extra in ignore_exact or any(extra.startswith(prefix) for prefix in ignore_prefixes):
                    break
                extras.append(extra)
            description = ' '.join(line for line in [record.get('description', '').strip()] + extras if line).strip()
            description = re.sub(r'\bTasa IVA 16\.0 ?%', '', description).strip()
            reference = record.get('reference')

            if prev_balance is None:
                prev_balance = balance_after - float(record.get('amount') or 0)

            amount = round(balance_after - prev_balance, 2)
            prev_balance = balance_after

            if abs(amount) < 0.01 and should_skip_transaction(description):
                continue

            txn_type = TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT
            movement_kind = infer_movement_kind(txn_type, description)

            if 'traspaso' in description.lower() or 'transferencia' in description.lower():
                totals['total_transfers'] += abs(amount)
            elif txn_type == TransactionType.CREDIT:
                totals['total_incomes'] += abs(amount)
            else:
                totals['total_expenses'] += abs(amount)

            if txn_type == TransactionType.CREDIT:
                totals['total_credits'] += abs(amount)
            else:
                totals['total_debits'] += abs(amount)

            transactions.append(
                BankTransaction(
                    account_id=account_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    transaction_date=record['date'],
                    description=description,
                    amount=round(amount, 2),
                    transaction_type=txn_type,
                    reference=reference,
                    balance=round(balance_after, 2),
                    raw_data=record.get('raw_line'),
                    movement_kind=movement_kind,
                )
            )

        summary = {
            'opening_balance': round(opening_balance or (prev_balance or 0.0), 2) if opening_balance is not None else None,
            'closing_balance': round(prev_balance, 2) if prev_balance is not None else None,
            'transaction_count': len(transactions),
            'total_credits': round(totals['total_credits'], 2),
            'total_debits': round(totals['total_debits'], 2),
            'total_incomes': round(totals['total_incomes'], 2),
            'total_expenses': round(totals['total_expenses'], 2),
            'total_transfers': round(totals['total_transfers'], 2),
            'detected_bank': 'inbursa',
        }

        return transactions, summary

    @staticmethod
    def _merge_descriptions(original: str, addition: str) -> str:
        if not addition:
            return original.strip()
        if not original:
            return addition.strip()
        return f"{original.strip()} {addition.strip()}".strip()

    def _should_skip_description(self, text: str) -> bool:
        if should_skip_transaction(text):
            return True
        lowered = (text or '').strip().lower()
        return bool(lowered and lowered in self.custom_skip_keywords)

    def _looks_like_transaction(self, line: str) -> bool:
        """Determinar si una línea parece una transacción"""
        # Debe tener una fecha y un monto
        has_date = any(re.search(pattern, line) for pattern in self.date_patterns)
        has_amount = any(re.search(pattern, line) for pattern in self.amount_patterns)
        has_reference = bool(self.reference_pattern.search(line.upper()))
        has_keywords = any(keyword in line.lower() for keyword in
                          self.credit_keywords + self.debit_keywords)

        return has_date and has_amount and has_reference and len(line.split()) >= 3

    def _parse_transaction_line(
        self,
        line: str,
        account_id: int,
        user_id: int,
        tenant_id: int
    ) -> Optional[BankTransaction]:
        """Parsear una línea de transacción del PDF"""
        try:
            # Extraer fecha
            txn_date = None
            for pattern in self.date_patterns:
                match = re.search(pattern, line)
                if match:
                    txn_date = self._parse_date(match.group(0))
                    if txn_date:
                        break

            if not txn_date:
                return None

            # Extraer monto
            raw_amounts = []
            for pattern in self.amount_patterns:
                matches = re.findall(pattern, line)
                if matches:
                    try:
                        # Handle negative signs properly
                        cleaned_matches = []
                        for m in matches:
                            cleaned = m.replace(',', '').replace('$', '').strip()
                            if cleaned.startswith('-'):
                                cleaned_matches.append(-float(cleaned[1:]))
                            elif cleaned.startswith('+'):
                                cleaned_matches.append(float(cleaned[1:]))
                            else:
                                cleaned_matches.append(float(cleaned))
                        extracted = [abs(val) for val in cleaned_matches]
                        raw_amounts.extend(extracted)
                    except Exception:
                        continue

            if not raw_amounts:
                return None

            balance_after = None
            if len(raw_amounts) > 1:
                balance_after = round(raw_amounts[-1], 2)
                candidate_amounts = raw_amounts[:-1]
            else:
                candidate_amounts = raw_amounts

            amount = max(candidate_amounts, default=0.0)

            if amount == 0:
                return None

            if amount > 1_000_000:
                logger.debug(f"Skipping transaction with unrealistic amount {amount} in line: {line[:80]}")
                return None

            # Determinar tipo de transacción
            transaction_type = self._classify_transaction_type(line)

            # Limpiar descripción
            description = line
            for pattern in self.date_patterns + self.amount_patterns:
                description = re.sub(pattern, '', description)
            description = ' '.join(description.split())

            reference = None
            reference_candidates = self.reference_pattern.findall(line.upper())
            if reference_candidates:
                reference = max(reference_candidates, key=len)
                description = re.sub(re.escape(reference), '', description, flags=re.IGNORECASE)

            description = re.sub(r'Ref:\s*\w+', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\(\s*\)', '', description)
            description = re.sub(r'^\d{6,}\s+', '', description)
            description = description.strip()

            if self._should_skip_description(description):
                return None

            if not description:
                return None

            amount_signed = amount if transaction_type == TransactionType.CREDIT else -amount
            amount_signed = round(amount_signed, 2)

            movement_kind = infer_movement_kind(transaction_type, description)

            return BankTransaction(
                account_id=account_id,
                user_id=user_id,
                tenant_id=tenant_id,
                transaction_date=txn_date,
                description=description,
                amount=amount_signed,
                transaction_type=transaction_type,
                raw_data=line,
                reference=reference,
                movement_kind=movement_kind,
                balance=balance_after
            )

        except Exception as e:
            logger.warning(f"Error parsing transaction line: {e}")
            return None

    def _classify_transaction_type(
        self,
        description: str,
        default: TransactionType = TransactionType.DEBIT
    ) -> TransactionType:
        """Clasificar tipo de transacción basado en descripción"""
        desc_lower = description.lower()

        # Revisar palabras clave de crédito
        if any(keyword in desc_lower for keyword in self.credit_keywords):
            return TransactionType.CREDIT

        # Revisar palabras clave de débito
        if any(keyword in desc_lower for keyword in self.debit_keywords):
            return TransactionType.DEBIT

        return default

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parsear fecha desde string"""
        if not date_str:
            return None

        # Limpiar string
        date_str = str(date_str).strip()

        # Formatos comunes
        formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
            '%Y/%m/%d', '%Y-%m-%d', '%y/%m/%d', '%y-%m-%d',
            '%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        # Month abbreviations (ESP)
        month_map = {
            'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12,
        }

        match = re.match(r'\b([A-Z]{3})\.?\s*(\d{1,2})\b', date_str.upper())
        if match:
            month_abbr, day_str = match.groups()
            month = month_map.get(month_abbr)
            if month:
                try:
                    day = int(day_str)
                except ValueError:
                    return None
                year = self.current_year_hint or datetime.utcnow().year
                try:
                    return date(year, month, day)
                except ValueError:
                    return None

        return None


# Instancia global del parser
bank_file_parser = BankFileParser()
