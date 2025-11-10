"""
AI Description Matcher

Usa Gemini para hacer matching inteligente entre descripciones de transacciones
bancarias y nombres de emisores de CFDIs.

Ejemplo:
    TX: "STRIPE *ODOO TECHNOLOG MX"
    CFDI: "ODOO TECHNOLOGIES SA DE CV"
    → Match con 95% confianza ✅

    TX: "APPLE.COM/BILL US"
    CFDI: "FINKOK SA DE CV"
    → No match (0% confianza) ❌
"""

import os
from typing import List, Dict, Optional
from dataclasses import dataclass
import google.generativeai as genai
import json


@dataclass
class DescriptionMatch:
    """Resultado de matching por descripción"""
    transaction_id: int
    invoice_id: int
    transaction_description: str
    invoice_name: str
    similarity_score: float  # 0.0 - 1.0
    confidence: str  # "high", "medium", "low", "no_match"
    reasoning: str
    amount_diff: float
    days_diff: int


class AIDescriptionMatcher:
    """
    Matcher inteligente usando Gemini para comparar descripciones
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el matcher con Gemini

        Args:
            api_key: API key de Gemini (opcional, usa variable de entorno)
        """
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY no configurada")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def match_batch(
        self,
        transactions: List[Dict],
        invoices: List[Dict],
        min_score: float = 0.7
    ) -> List[DescriptionMatch]:
        """
        Hace matching de un batch de transacciones vs facturas

        Args:
            transactions: Lista de {id, description, amount, date}
            invoices: Lista de {id, nombre_emisor, total, fecha}
            min_score: Score mínimo para considerar match (0.7 = 70%)

        Returns:
            Lista de DescriptionMatch con los matches encontrados
        """
        if not transactions or not invoices:
            return []

        # Preparar datos para el prompt
        tx_data = []
        for tx in transactions:
            tx_data.append({
                "id": tx["id"],
                "description": tx["description"],
                "amount": float(tx["amount"]),
                "date": str(tx["date"])
            })

        inv_data = []
        for inv in invoices:
            inv_data.append({
                "id": inv["id"],
                "name": inv["nombre_emisor"],
                "amount": float(inv["total"]),
                "date": str(inv["fecha"])
            })

        # Prompt para Gemini
        prompt = f"""
Eres un experto en conciliación bancaria. Tu tarea es encontrar matches entre transacciones bancarias y facturas (CFDIs) basándote en la SIMILITUD DE DESCRIPCIONES.

TRANSACCIONES BANCARIAS:
{json.dumps(tx_data, indent=2, ensure_ascii=False)}

FACTURAS (CFDIs) DISPONIBLES:
{json.dumps(inv_data, indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Para cada transacción, busca la factura con descripción MÁS SIMILAR
2. Considera:
   - Nombres de empresas (ej: "ODOO TECHNOLOG" vs "ODOO TECHNOLOGIES")
   - Abreviaciones (ej: "DISTRIB" vs "DISTRIBUIDORA")
   - Palabras clave comunes
   - Diferencia de monto (± $10 es aceptable)
   - Diferencia de fecha (± 5 días es aceptable)

3. NO hagas match si:
   - Las descripciones no tienen relación alguna
   - La diferencia de monto es > $50
   - La diferencia de fecha es > 10 días

4. Asigna un similarity_score (0.0 - 1.0):
   - 1.0 = Match perfecto (mismo nombre)
   - 0.9 = Alta similitud (abreviación obvia)
   - 0.8 = Buena similitud (palabras clave coinciden)
   - 0.7 = Posible match (alguna relación)
   - < 0.7 = No match

5. Asigna confidence:
   - "high": score >= 0.85 y diff_amount <= $5 y diff_days <= 2
   - "medium": score >= 0.75 y diff_amount <= $10 y diff_days <= 5
   - "low": score >= 0.70 y diff_amount <= $20 y diff_days <= 7
   - "no_match": score < 0.70

FORMATO DE RESPUESTA (JSON):
{{
  "matches": [
    {{
      "transaction_id": 123,
      "invoice_id": 456,
      "similarity_score": 0.95,
      "confidence": "high",
      "reasoning": "STRIPE ODOO coincide con ODOO TECHNOLOGIES, montos iguales"
    }}
  ]
}}

IMPORTANTE:
- Solo incluye matches con score >= {min_score}
- Si no hay match, no incluyas la transacción
- Responde SOLO con JSON válido, sin markdown
"""

        try:
            # Llamar a Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # Limpiar markdown si existe
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            # Parsear respuesta
            result = json.loads(response_text)
            matches = []

            for match_data in result.get("matches", []):
                # Buscar la transacción y factura original
                tx = next((t for t in transactions if t["id"] == match_data["transaction_id"]), None)
                inv = next((i for i in invoices if i["id"] == match_data["invoice_id"]), None)

                if not tx or not inv:
                    continue

                # Calcular diferencias
                amount_diff = abs(abs(float(tx["amount"])) - float(inv["total"]))

                from datetime import datetime
                tx_date = datetime.strptime(str(tx["date"]), "%Y-%m-%d").date()
                inv_date = datetime.strptime(str(inv["fecha"]), "%Y-%m-%d").date()
                days_diff = abs((tx_date - inv_date).days)

                # Crear DescriptionMatch
                matches.append(DescriptionMatch(
                    transaction_id=match_data["transaction_id"],
                    invoice_id=match_data["invoice_id"],
                    transaction_description=tx["description"],
                    invoice_name=inv["nombre_emisor"],
                    similarity_score=match_data["similarity_score"],
                    confidence=match_data["confidence"],
                    reasoning=match_data.get("reasoning", "AI match"),
                    amount_diff=amount_diff,
                    days_diff=days_diff
                ))

            return matches

        except json.JSONDecodeError as e:
            print(f"❌ Error parseando respuesta de Gemini: {e}")
            print(f"Respuesta: {response_text[:500]}")
            return []
        except Exception as e:
            print(f"❌ Error en matching: {e}")
            import traceback
            traceback.print_exc()
            return []

    def match_single(
        self,
        transaction: Dict,
        invoices: List[Dict]
    ) -> Optional[DescriptionMatch]:
        """
        Encuentra el mejor match para una sola transacción

        Args:
            transaction: {id, description, amount, date}
            invoices: Lista de facturas candidatas

        Returns:
            Mejor match o None
        """
        matches = self.match_batch([transaction], invoices, min_score=0.7)

        if not matches:
            return None

        # Retornar el match con mayor score
        return max(matches, key=lambda m: m.similarity_score)


def get_ai_matcher() -> AIDescriptionMatcher:
    """
    Factory function para obtener el matcher

    Returns:
        Instancia de AIDescriptionMatcher
    """
    return AIDescriptionMatcher()


# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo de prueba
    matcher = AIDescriptionMatcher()

    transactions = [
        {
            "id": 1,
            "description": "STRIPE *ODOO TECHNOLOG MX",
            "amount": -535.92,
            "date": "2025-01-11"
        },
        {
            "id": 2,
            "description": "DISTRIB CRISTAL PREZ MX",
            "amount": -8090.01,
            "date": "2025-01-08"
        },
        {
            "id": 3,
            "description": "APPLE.COM/BILL US",
            "amount": -375.00,
            "date": "2025-01-17"
        }
    ]

    invoices = [
        {
            "id": 101,
            "nombre_emisor": "ODOO TECHNOLOGIES SA DE CV",
            "total": 535.92,
            "fecha": "2025-01-10"
        },
        {
            "id": 102,
            "nombre_emisor": "DISTRIBUIDORA PREZ SA DE CV",
            "total": 8090.01,
            "fecha": "2025-01-07"
        },
        {
            "id": 103,
            "nombre_emisor": "FINKOK SA DE CV",
            "total": 185.22,
            "fecha": "2025-01-17"
        }
    ]

    print("\n" + "="*80)
    print("🤖 AI DESCRIPTION MATCHER - PRUEBA")
    print("="*80 + "\n")

    matches = matcher.match_batch(transactions, invoices, min_score=0.7)

    print(f"Se encontraron {len(matches)} matches:\n")

    for match in matches:
        print(f"✓ TX-{match.transaction_id}: {match.transaction_description}")
        print(f"  ↔ CFDI-{match.invoice_id}: {match.invoice_name}")
        print(f"  Score: {match.similarity_score:.2%} | Confianza: {match.confidence}")
        print(f"  Diff: ${match.amount_diff:.2f} ({match.days_diff} días)")
        print(f"  Razón: {match.reasoning}")
        print()
