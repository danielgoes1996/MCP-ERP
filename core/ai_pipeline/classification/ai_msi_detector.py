"""
AI-Driven MSI (Meses Sin Intereses) Detection
Usa Gemini LLM para detectar y asociar transacciones MSI con facturas
"""

import logging
import os
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, timedelta
from dataclasses import dataclass

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MSIMatch:
    """Resultado de matching MSI"""
    transaction_id: int
    invoice_id: int
    msi_months: int
    monthly_amount: float
    total_amount: float
    confidence: float
    reasoning: str
    metadata: Dict[str, Any]


class AIMSIDetector:
    """
    Detector de MSI usando AI
    Analiza transacciones y facturas para encontrar coincidencias MSI
    """

    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai no está instalado")

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no configurada")

        # Configurar Gemini
        genai.configure(api_key=self.api_key)

        # Modelo para razonamiento
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        logger.info("✅ AI MSI Detector initialized")

    def detect_msi_matches(
        self,
        transactions: List[Dict[str, Any]],
        invoices: List[Dict[str, Any]],
        account_type: str = "credit_card"
    ) -> List[MSIMatch]:
        """
        Detecta matches de MSI entre transacciones y facturas usando AI

        Args:
            transactions: Lista de transacciones del estado de cuenta
            invoices: Lista de facturas con FormaPago='04' (tarjeta crédito)
            account_type: Tipo de cuenta

        Returns:
            Lista de MSIMatch con coincidencias encontradas
        """
        # Solo procesar si es tarjeta de crédito
        if account_type != "credit_card":
            logger.info("⏭️  Skipping MSI detection - not a credit card")
            return []

        if not transactions or not invoices:
            logger.info("⏭️  No transactions or invoices to analyze")
            return []

        logger.info(f"🤖 AI MSI Detection: {len(transactions)} transactions vs {len(invoices)} invoices")

        try:
            # Preparar datos para el LLM
            prompt = self._create_msi_detection_prompt(transactions, invoices)

            # Enviar a Gemini
            response = self.model.generate_content(prompt)

            # Parsear respuesta
            result_text = response.text.strip()

            # Limpiar markdown
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            elif "```" in result_text:
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()

            # Parsear JSON
            data = json.loads(result_text)

            # Crear MSIMatch objects
            matches = []
            for match_data in data.get("matches", []):
                try:
                    match = MSIMatch(
                        transaction_id=match_data["transaction_id"],
                        invoice_id=match_data["invoice_id"],
                        msi_months=match_data["msi_months"],
                        monthly_amount=float(match_data["monthly_amount"]),
                        total_amount=float(match_data["total_amount"]),
                        confidence=float(match_data["confidence"]),
                        reasoning=match_data.get("reasoning", ""),
                        metadata=match_data.get("metadata", {})
                    )
                    matches.append(match)
                except Exception as e:
                    logger.warning(f"⚠️ Skipping invalid match: {e}")
                    continue

            logger.info(f"✅ AI detected {len(matches)} MSI matches")

            return matches

        except Exception as e:
            logger.error(f"❌ Error in AI MSI detection: {e}")
            return []

    def _create_msi_detection_prompt(
        self,
        transactions: List[Dict[str, Any]],
        invoices: List[Dict[str, Any]]
    ) -> str:
        """Crea prompt para detección de MSI"""

        # Limitar a últimas 50 transacciones y 100 facturas para no exceder límite
        transactions_sample = transactions[-50:] if len(transactions) > 50 else transactions
        invoices_sample = invoices[-100:] if len(invoices) > 100 else invoices

        # Preparar datos
        transactions_json = json.dumps([
            {
                "id": i,
                "date": str(tx.get("date", "")),
                "description": tx.get("description", ""),
                "amount": abs(float(tx.get("amount", 0))),  # Usar valor absoluto
                "is_msi_candidate": tx.get("is_msi_candidate", False),
                "msi_months": tx.get("msi_months"),
                "msi_confidence": tx.get("msi_confidence", 0.0)
            }
            for i, tx in enumerate(transactions_sample)
            if float(tx.get("amount", 0)) < 0  # Solo cargos
        ], indent=2)

        invoices_json = json.dumps([
            {
                "id": inv.get("id"),
                "date": str(inv.get("fecha", "")),
                "rfc": inv.get("rfc_emisor", ""),
                "description": inv.get("descripcion_concepto", ""),
                "total": float(inv.get("total", 0)),
                "forma_pago": inv.get("forma_pago", ""),
                "uuid": inv.get("uuid", "")[:8]  # Solo primeros 8 chars
            }
            for inv in invoices_sample
            if inv.get("forma_pago") == "04"  # Solo tarjeta de crédito
        ], indent=2)

        prompt = f"""
Eres un experto contador mexicano especializado en análisis de MSI (Meses Sin Intereses).

Tu tarea es encontrar coincidencias entre transacciones de tarjeta de crédito y facturas pagadas con MSI.

**TRANSACCIONES DEL ESTADO DE CUENTA:**
{transactions_json}

**FACTURAS CON FORMA DE PAGO 04 (TARJETA DE CRÉDITO):**
{invoices_json}

**INSTRUCCIONES PARA DETECCIÓN DE MSI:**

1. **¿Qué es MSI?**
   - Compra a crédito dividida en pagos mensuales iguales (3, 6, 9, 12, 18, 24 meses)
   - Sin intereses (cada mes se paga la misma cantidad)
   - El total de la factura = pago mensual × número de meses

2. **Cómo detectar MSI:**
   - Busca transacciones cuyo monto sea divisible exactamente por un número común de MSI (3, 6, 9, 12, 18, 24)
   - Verifica si el resultado coincide con el total de alguna factura
   - La descripción puede contener pistas: "MSI", "MESES", "PARCIALIDAD", etc.
   - Considera margen de error de ±2% (por redondeos)

3. **Ejemplos de matching:**
   - Factura: $6,000 → Transacción: $500/mes → 12 MSI ✅
   - Factura: $1,800 → Transacción: $300/mes → 6 MSI ✅
   - Factura: $2,499 → Transacción: $833/mes → 3 MSI ✅

4. **Validaciones importantes:**
   - La fecha de la factura debe ser ANTES o cercana a la fecha de la transacción
   - El monto total calculado (monthly × months) debe coincidir con el total de la factura (±2%)
   - Si una transacción ya tiene `is_msi_candidate: true`, dale mayor peso
   - Si la descripción menciona MSI, da mayor confianza

5. **Niveles de confianza:**
   - 0.95-1.0: Coincidencia exacta + descripción menciona MSI
   - 0.80-0.94: Coincidencia exacta sin mención de MSI
   - 0.60-0.79: Coincidencia con margen de error ±2%
   - 0.30-0.59: Coincidencia posible pero incierta
   - <0.30: No reportar (muy incierto)

**FORMATO DE RESPUESTA (JSON puro):**

{{
  "matches": [
    {{
      "transaction_id": 0,
      "invoice_id": 123,
      "msi_months": 12,
      "monthly_amount": 500.00,
      "total_amount": 6000.00,
      "confidence": 0.95,
      "reasoning": "Monto mensual $500 × 12 meses = $6,000 (total factura). Coincidencia exacta. Descripción menciona 'MSI'.",
      "metadata": {{
        "invoice_total": 6000.00,
        "calculated_total": 6000.00,
        "variance_percent": 0.0,
        "date_difference_days": 5
      }}
    }}
  ],
  "summary": {{
    "total_matches": 1,
    "total_msi_amount": 6000.00,
    "average_confidence": 0.95
  }}
}}

**RESPONDE SOLO CON JSON. NO INCLUYAS MATCHES CON CONFIANZA < 0.30.**
"""

        return prompt


# Singleton instance
_ai_msi_detector_instance: Optional[AIMSIDetector] = None


def get_ai_msi_detector() -> AIMSIDetector:
    """Obtiene instancia singleton del AI MSI detector"""
    global _ai_msi_detector_instance

    if _ai_msi_detector_instance is None:
        _ai_msi_detector_instance = AIMSIDetector()

    return _ai_msi_detector_instance
