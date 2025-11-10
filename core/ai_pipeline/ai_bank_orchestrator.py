"""
AI Bank Statement Orchestrator
Orquesta todo el flujo AI-driven para procesamiento de estados de cuenta
"""

import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor

from core.ai_pipeline.ocr.gemini_vision_ocr import get_gemini_ocr
from core.ai_pipeline.parsers.ai_bank_statement_parser import (
    get_ai_parser,
    BankStatementData
)
from core.ai_pipeline.classification.ai_msi_detector import (
    get_ai_msi_detector,
    MSIMatch
)

logger = logging.getLogger(__name__)


# PostgreSQL configuration
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}


@dataclass
class ProcessingResult:
    """Resultado completo del procesamiento AI"""
    success: bool
    statement_id: Optional[int]
    statement_data: Optional[BankStatementData]
    transactions_created: int
    msi_matches: List[MSIMatch]
    processing_time_seconds: float
    metadata: Dict[str, Any]
    error: Optional[str] = None


class AIBankOrchestrator:
    """
    Orquestador del flujo completo AI-driven para estados de cuenta

    Flujo:
    1. Gemini Vision OCR → Extrae texto del PDF
    2. Gemini LLM → Parsea transacciones estructuradas
    3. Gemini Reasoning → Detecta MSI matches
    4. PostgreSQL → Guarda todo en BD
    """

    def __init__(self):
        # Servicios AI
        self.ocr = get_gemini_ocr()
        self.parser = get_ai_parser()
        self.msi_detector = get_ai_msi_detector()

        # Configuración
        self.enabled = os.getenv("AI_PARSER_ENABLED", "true").lower() == "true"
        self.fallback_to_traditional = os.getenv("AI_FALLBACK_ENABLED", "true").lower() == "true"

        logger.info(f"✅ AI Bank Orchestrator initialized (enabled={self.enabled}, fallback={self.fallback_to_traditional})")

    def process_bank_statement(
        self,
        pdf_path: str,
        account_id: int,
        company_id: int,
        user_id: int,
        tenant_id: str
    ) -> ProcessingResult:
        """
        Procesa un estado de cuenta completo usando AI

        Args:
            pdf_path: Ruta al archivo PDF
            account_id: ID de la cuenta bancaria
            company_id: ID de la empresa
            user_id: ID del usuario
            tenant_id: ID del tenant

        Returns:
            ProcessingResult con resultados del procesamiento
        """
        start_time = time.time()
        logger.info(f"🤖 AI Processing: {pdf_path} (account={account_id}, company={company_id})")

        try:
            # PASO 1: Parsear PDF con AI
            logger.info("📊 Step 1/4: Parsing PDF with AI...")
            statement_data = self.parser.parse_pdf(
                pdf_path,
                account_id=account_id,
                company_id=company_id
            )

            # PASO 2: Guardar en base de datos
            logger.info("💾 Step 2/4: Saving to database...")
            statement_id = self._save_to_database(
                statement_data,
                account_id,
                company_id,
                user_id,
                tenant_id,
                pdf_path
            )

            # PASO 3: Detectar MSI (solo si es tarjeta de crédito)
            msi_matches = []
            if statement_data.account_type == "credit_card":
                logger.info("💳 Step 3/4: Detecting MSI matches...")
                invoices = self._fetch_invoices_for_msi(company_id, tenant_id)
                msi_matches = self.msi_detector.detect_msi_matches(
                    statement_data.transactions,
                    invoices,
                    statement_data.account_type
                )

                # Guardar MSI matches en BD
                if msi_matches:
                    self._save_msi_matches(statement_id, msi_matches)

            # PASO 4: Actualizar payment_accounts si AI detectó diferencias
            logger.info("🔄 Step 4/4: Updating payment accounts...")
            self._update_payment_account_if_needed(
                account_id,
                statement_data,
                tenant_id
            )

            processing_time = time.time() - start_time

            result = ProcessingResult(
                success=True,
                statement_id=statement_id,
                statement_data=statement_data,
                transactions_created=len(statement_data.transactions),
                msi_matches=msi_matches,
                processing_time_seconds=processing_time,
                metadata={
                    "parsing_method": "ai_driven",
                    "model": "gemini-2.0-flash-exp",
                    "confidence": statement_data.confidence,
                    "msi_detected": len(msi_matches)
                }
            )

            logger.info(f"✅ AI Processing completed in {processing_time:.2f}s - {len(statement_data.transactions)} transactions, {len(msi_matches)} MSI matches")

            return result

        except Exception as e:
            logger.error(f"❌ Error in AI processing: {e}")

            # Si fallback está habilitado, intentar con parser tradicional
            if self.fallback_to_traditional:
                logger.warning("⚠️ Falling back to traditional parser...")
                return self._fallback_to_traditional_parser(
                    pdf_path,
                    account_id,
                    company_id,
                    user_id,
                    tenant_id,
                    original_error=str(e)
                )

            return ProcessingResult(
                success=False,
                statement_id=None,
                statement_data=None,
                transactions_created=0,
                msi_matches=[],
                processing_time_seconds=time.time() - start_time,
                metadata={},
                error=str(e)
            )

    def _save_to_database(
        self,
        statement_data: BankStatementData,
        account_id: int,
        company_id: int,
        user_id: int,
        tenant_id: str,
        file_path: str
    ) -> int:
        """Guarda statement y transacciones en PostgreSQL"""

        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Insertar bank_statement
            cursor.execute("""
                INSERT INTO bank_statements (
                    account_id, company_id, user_id, tenant_id,
                    file_name, file_path, file_type,
                    period_start, period_end,
                    opening_balance, closing_balance,
                    total_credits, total_debits,
                    transaction_count,
                    parsing_status, parsing_method,
                    ai_confidence,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s,
                    %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING id
            """, (
                account_id, company_id, user_id, tenant_id,
                Path(file_path).name, file_path, 'pdf',
                statement_data.period_start, statement_data.period_end,
                statement_data.opening_balance, statement_data.closing_balance,
                statement_data.total_credits, statement_data.total_debits,
                len(statement_data.transactions),
                'completed', 'ai_driven',
                statement_data.confidence
            ))

            statement_id = cursor.fetchone()['id']

            # Insertar transacciones
            for tx in statement_data.transactions:
                cursor.execute("""
                    INSERT INTO bank_transactions (
                        statement_id, company_id, tenant_id,
                        transaction_date, description, amount,
                        transaction_type, balance, reference,
                        msi_candidate, msi_months, msi_confidence,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """, (
                    statement_id, company_id, tenant_id,
                    tx["date"], tx["description"], tx["amount"],
                    tx["type"], tx["balance"], tx["reference"],
                    tx.get("is_msi_candidate", False),
                    tx.get("msi_months"),
                    tx.get("msi_confidence", 0.0)
                ))

            conn.commit()
            logger.info(f"✅ Saved statement {statement_id} with {len(statement_data.transactions)} transactions")

            return statement_id

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error saving to database: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _fetch_invoices_for_msi(
        self,
        company_id: int,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Obtiene facturas con FormaPago='04' para matching MSI"""

        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("""
                SELECT
                    id, fecha, rfc_emisor, descripcion_concepto,
                    total, forma_pago, uuid
                FROM expenses
                WHERE company_id = %s
                AND tenant_id = %s
                AND forma_pago = '04'
                AND fecha >= CURRENT_DATE - INTERVAL '180 days'
                ORDER BY fecha DESC
                LIMIT 100
            """, (company_id, tenant_id))

            invoices = [dict(row) for row in cursor.fetchall()]

            logger.info(f"📋 Found {len(invoices)} invoices with FormaPago='04' for MSI matching")

            return invoices

        except Exception as e:
            logger.error(f"❌ Error fetching invoices: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def _save_msi_matches(
        self,
        statement_id: int,
        msi_matches: List[MSIMatch]
    ):
        """Guarda MSI matches en bank_transactions"""

        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor()

        try:
            for match in msi_matches:
                cursor.execute("""
                    UPDATE bank_transactions
                    SET
                        msi_candidate = TRUE,
                        msi_invoice_id = %s,
                        msi_months = %s,
                        msi_confidence = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    match.invoice_id,
                    match.msi_months,
                    match.confidence,
                    match.transaction_id
                ))

            conn.commit()
            logger.info(f"✅ Saved {len(msi_matches)} MSI matches")

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error saving MSI matches: {e}")
        finally:
            cursor.close()
            conn.close()

    def _update_payment_account_if_needed(
        self,
        account_id: int,
        statement_data: BankStatementData,
        tenant_id: str
    ):
        """Actualiza payment_accounts si AI detectó datos incorrectos"""

        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Obtener configuración actual
            cursor.execute("""
                SELECT account_type, bank_name
                FROM payment_accounts
                WHERE id = %s AND tenant_id = %s
            """, (account_id, tenant_id))

            current = cursor.fetchone()

            if not current:
                return

            # Verificar si necesita actualización (confianza >= 90%)
            needs_update = False
            updates = {}

            if (statement_data.confidence >= 0.9 and
                current['account_type'] != statement_data.account_type):
                needs_update = True
                updates['account_type'] = statement_data.account_type
                logger.warning(f"⚠️ AI detected wrong account_type: {current['account_type']} → {statement_data.account_type}")

            if (statement_data.confidence >= 0.9 and
                current['bank_name'] != statement_data.bank_name):
                needs_update = True
                updates['bank_name'] = statement_data.bank_name
                logger.warning(f"⚠️ AI detected wrong bank_name: {current['bank_name']} → {statement_data.bank_name}")

            # Actualizar si es necesario
            if needs_update:
                set_clause = ', '.join([f"{k} = %s" for k in updates.keys()])
                values = list(updates.values()) + [account_id, tenant_id]

                cursor.execute(f"""
                    UPDATE payment_accounts
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND tenant_id = %s
                """, values)

                conn.commit()
                logger.info(f"✅ Updated payment_account {account_id}: {updates}")

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error updating payment_account: {e}")
        finally:
            cursor.close()
            conn.close()

    def _fallback_to_traditional_parser(
        self,
        pdf_path: str,
        account_id: int,
        company_id: int,
        user_id: int,
        tenant_id: str,
        original_error: str
    ) -> ProcessingResult:
        """Fallback al parser tradicional si AI falla"""

        logger.info("🔄 Using traditional parser as fallback...")

        try:
            from core.reconciliation.bank.bank_file_parser import bank_file_parser

            # Usar parser tradicional
            transactions, summary = bank_file_parser.parse(pdf_path, account_id)

            # TODO: Guardar en BD usando método tradicional

            return ProcessingResult(
                success=True,
                statement_id=None,
                statement_data=None,
                transactions_created=len(transactions),
                msi_matches=[],
                processing_time_seconds=0,
                metadata={
                    "parsing_method": "traditional_fallback",
                    "ai_error": original_error
                }
            )

        except Exception as e:
            logger.error(f"❌ Traditional parser also failed: {e}")

            return ProcessingResult(
                success=False,
                statement_id=None,
                statement_data=None,
                transactions_created=0,
                msi_matches=[],
                processing_time_seconds=0,
                metadata={},
                error=f"AI failed: {original_error}. Traditional also failed: {str(e)}"
            )


# Singleton instance
_orchestrator_instance: Optional[AIBankOrchestrator] = None


def get_ai_orchestrator() -> AIBankOrchestrator:
    """Obtiene instancia singleton del orchestrator"""
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = AIBankOrchestrator()

    return _orchestrator_instance
