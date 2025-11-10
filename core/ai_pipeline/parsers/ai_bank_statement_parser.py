"""
AI-Driven Bank Statement Parser
Parser 100% basado en Gemini LLM para extraer transacciones
"""

import logging
import os
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from core.ai_pipeline.ocr.gemini_vision_ocr import GeminiVisionOCR, get_gemini_ocr
from core.reconciliation.bank.bank_statements_models import (
    BankTransaction,
    TransactionType,
    MovementKind
)

logger = logging.getLogger(__name__)


@dataclass
class BankStatementData:
    """Datos estructurados del estado de cuenta"""
    bank_name: str
    account_type: str  # credit_card, debit_card, checking, savings
    account_number: str
    period_start: date
    period_end: date
    opening_balance: float
    closing_balance: float
    total_credits: float
    total_debits: float
    transactions: List[Dict[str, Any]]
    confidence: float
    metadata: Dict[str, Any]


class AIBankStatementParser:
    """
    Parser de estados de cuenta 100% AI-driven
    Usa Gemini Vision OCR + Gemini LLM para extraer transacciones
    """

    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai no está instalado")

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no configurada")

        # Configurar Gemini
        genai.configure(api_key=self.api_key)

        # Modelo para procesamiento de texto
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # OCR service
        self.ocr = get_gemini_ocr()

        logger.info("✅ AI Bank Statement Parser initialized")

    def parse_pdf(
        self,
        pdf_path: str,
        account_id: Optional[int] = None,
        company_id: Optional[int] = None
    ) -> BankStatementData:
        """
        Parsea un estado de cuenta PDF usando AI

        Args:
            pdf_path: Ruta al archivo PDF
            account_id: ID de la cuenta (opcional, para context)
            company_id: ID de la empresa (opcional, para context)

        Returns:
            BankStatementData con todas las transacciones extraídas
        """
        start_time = time.time()
        logger.info(f"🤖 AI Parsing PDF: {pdf_path}")

        try:
            # PASO 1: Extraer texto con Gemini Vision OCR
            logger.info("📄 Step 1/3: Extracting text with Gemini Vision OCR...")
            ocr_result = self.ocr.extract_text_from_pdf(
                pdf_path,
                extract_structured=True  # Pedimos estructura directamente
            )

            # PASO 2: Si OCR ya extrajo estructura, usarla directamente
            if ocr_result.pages[0].structured_data:
                logger.info("✅ OCR returned structured data, using it directly")
                structured_data = ocr_result.pages[0].structured_data
            else:
                # PASO 2b: Si OCR no devolvió estructura, enviar texto a LLM
                logger.info("📊 Step 2/3: Parsing text with Gemini LLM...")
                structured_data = self._parse_text_with_llm(
                    ocr_result.full_text,
                    Path(pdf_path).name
                )

            # PASO 3: Validar y normalizar datos
            logger.info("🔍 Step 3/3: Validating and normalizing data...")
            statement_data = self._normalize_statement_data(
                structured_data,
                pdf_path
            )

            processing_time = time.time() - start_time
            logger.info(f"✅ AI Parsing completed in {processing_time:.2f}s - {len(statement_data.transactions)} transactions")

            return statement_data

        except Exception as e:
            logger.error(f"❌ Error in AI parsing: {e}")
            raise

    def _parse_text_with_llm(self, text: str, file_name: str) -> Dict[str, Any]:
        """Parsea texto extraído usando Gemini LLM"""

        prompt = f"""
Eres un experto en análisis de estados de cuenta bancarios mexicanos.

Analiza este estado de cuenta y extrae TODA la información en formato JSON estructurado.

INFORMACIÓN DEL DOCUMENTO:
- Nombre del archivo: {file_name}

TEXTO DEL ESTADO DE CUENTA:
{text[:15000]}  # Limitar a ~15K chars para no exceder límite

INSTRUCCIONES IMPORTANTES:

1. **Información del Banco**:
   - Detecta el banco (BBVA, Santander, Banamex, HSBC, Scotiabank, Inbursa, BanRegio, etc.)
   - Detecta el tipo de cuenta:
     * "credit_card" si es tarjeta de crédito
     * "debit_card" si es tarjeta de débito
     * "checking" si es cuenta de cheques
     * "savings" si es cuenta de ahorro
   - Extrae número de cuenta enmascarado (ej: ****1234)

2. **Período del Estado**:
   - Fecha de inicio del período
   - Fecha de fin del período
   - Formato: YYYY-MM-DD

3. **Resumen Financiero**:
   - Saldo inicial (al inicio del período)
   - Saldo final (al final del período)
   - Total de créditos/abonos (suma de todos los abonos)
   - Total de débitos/cargos (suma de todos los cargos)

4. **Transacciones** (MUY IMPORTANTE):
   - Extrae TODAS las transacciones del estado
   - Cada transacción debe incluir:
     * **date**: Fecha de la transacción (YYYY-MM-DD)
     * **description**: Descripción (máximo 100 caracteres, limpia, sin saltos de línea ni comillas)
     * **amount**: Monto como número decimal
       - NEGATIVO para cargos/débitos (ej: -1500.00)
       - POSITIVO para abonos/créditos (ej: +5000.00)
     * **type**: "debit" para cargos, "credit" para abonos
     * **balance**: Saldo después de la transacción (si está disponible, sino null)
     * **reference**: Número de referencia (si está disponible, sino null)

5. **Detección de MSI (Meses Sin Intereses)**:
   - Si detectas transacciones que parecen ser MSI (ej: "COMPRA 3 MSI", "PAGO 6/12", etc.):
     * Marca **is_msi_candidate**: true
     * Extrae **msi_months**: número de meses (3, 6, 9, 12, 18, 24)
     * Asigna **msi_confidence**: 0.0 a 1.0 (qué tan seguro estás)

FORMATO DE RESPUESTA (JSON puro, sin markdown):

{{
  "bank_info": {{
    "bank_name": "BBVA",
    "account_type": "credit_card",
    "account_number": "****1234",
    "period_start": "2024-01-01",
    "period_end": "2024-01-31"
  }},
  "summary": {{
    "opening_balance": 10000.00,
    "closing_balance": 8500.00,
    "total_credits": 5000.00,
    "total_debits": 6500.00
  }},
  "transactions": [
    {{
      "date": "2024-01-05",
      "description": "Amazon México",
      "amount": -1500.00,
      "type": "debit",
      "balance": 8500.00,
      "reference": "REF123456",
      "is_msi_candidate": true,
      "msi_months": 6,
      "msi_confidence": 0.85
    }},
    {{
      "date": "2024-01-10",
      "description": "Transferencia SPEI Recibida",
      "amount": 5000.00,
      "type": "credit",
      "balance": 13500.00,
      "reference": "SPEI987654",
      "is_msi_candidate": false,
      "msi_months": null,
      "msi_confidence": 0.0
    }}
  ],
  "metadata": {{
    "confidence": 0.95,
    "total_transactions": 2
  }}
}}

RESPONDE SOLO CON EL JSON, SIN EXPLICACIONES ADICIONALES.
"""

        try:
            # Enviar a Gemini
            response = self.model.generate_content(prompt)

            # Parsear respuesta
            result_text = response.text.strip()

            # Limpiar markdown si existe
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            elif "```" in result_text:
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()

            # Intentar parsear JSON con manejo de errores
            try:
                data = json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ JSON parse error: {e}")
                logger.warning(f"Intentando limpiar JSON...")

                # Intentar limpiar caracteres problemáticos
                import re
                # Escapar comillas no escapadas en valores
                cleaned = result_text.replace('\n', ' ')
                # Remover caracteres de control
                cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)

                try:
                    data = json.loads(cleaned)
                    logger.info("✅ JSON parseado después de limpieza")
                except:
                    # Si aún falla, usar prompt más simple
                    logger.error("❌ No se pudo parsear JSON. Re-intentando con prompt simplificado...")
                    raise

            logger.info(f"✅ LLM parsed {len(data.get('transactions', []))} transactions")

            return data

        except Exception as e:
            logger.error(f"❌ Error parsing with LLM: {e}")
            raise

    def _normalize_statement_data(
        self,
        raw_data: Dict[str, Any],
        pdf_path: str
    ) -> BankStatementData:
        """Normaliza y valida datos extraídos"""

        try:
            bank_info = raw_data.get("bank_info", {})
            summary = raw_data.get("summary", {})
            transactions = raw_data.get("transactions", [])
            metadata = raw_data.get("metadata", {})

            # Parsear fechas
            period_start = self._parse_date(bank_info.get("period_start"))
            period_end = self._parse_date(bank_info.get("period_end"))

            # Normalizar transacciones
            normalized_transactions = []
            for tx in transactions:
                try:
                    normalized_tx = {
                        "date": self._parse_date(tx.get("date")),
                        "description": str(tx.get("description", "")).strip(),
                        "amount": float(tx.get("amount", 0)),
                        "type": tx.get("type", "debit"),
                        "balance": float(tx.get("balance")) if tx.get("balance") is not None else None,
                        "reference": tx.get("reference"),
                        "is_msi_candidate": tx.get("is_msi_candidate", False),
                        "msi_months": tx.get("msi_months"),
                        "msi_confidence": float(tx.get("msi_confidence", 0.0))
                    }
                    normalized_transactions.append(normalized_tx)
                except Exception as e:
                    logger.warning(f"⚠️ Skipping invalid transaction: {e}")
                    continue

            # Crear BankStatementData
            statement_data = BankStatementData(
                bank_name=bank_info.get("bank_name", "Unknown"),
                account_type=bank_info.get("account_type", "checking"),
                account_number=bank_info.get("account_number", "****0000"),
                period_start=period_start or date.today(),
                period_end=period_end or date.today(),
                opening_balance=float(summary.get("opening_balance", 0)),
                closing_balance=float(summary.get("closing_balance", 0)),
                total_credits=float(summary.get("total_credits", 0)),
                total_debits=float(summary.get("total_debits", 0)),
                transactions=normalized_transactions,
                confidence=float(metadata.get("confidence", 0.9)),
                metadata={
                    "file_name": Path(pdf_path).name,
                    "parsing_method": "ai_driven",
                    "model": "gemini-2.0-flash-exp",
                    **metadata
                }
            )

            return statement_data

        except Exception as e:
            logger.error(f"❌ Error normalizing data: {e}")
            raise

    def _parse_date(self, date_str: Any) -> Optional[date]:
        """Parsea fecha en múltiples formatos"""
        if not date_str:
            return None

        if isinstance(date_str, date):
            return date_str

        if isinstance(date_str, datetime):
            return date_str.date()

        # Intentar parsear string
        date_str = str(date_str).strip()

        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                continue

        logger.warning(f"⚠️ Could not parse date: {date_str}")
        return None


# Singleton instance
_ai_parser_instance: Optional[AIBankStatementParser] = None


def get_ai_parser() -> AIBankStatementParser:
    """Obtiene instancia singleton del AI parser"""
    global _ai_parser_instance

    if _ai_parser_instance is None:
        _ai_parser_instance = AIBankStatementParser()

    return _ai_parser_instance
