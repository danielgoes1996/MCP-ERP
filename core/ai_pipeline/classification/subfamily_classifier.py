"""
Subfamily-level classifier for hierarchical invoice classification.

This is PHASE 2A of the 4-phase hierarchical classification system:
- Phase 1: Classify to family level (100-800) with >95% confidence
- Phase 2A: Classify to subfamily level (601, 602, 603...) with >90% confidence ← THIS FILE
- Phase 2B: Filter to account candidates using embedding search
- Phase 3: Select detailed account (e.g., 603 → 603.5) with >85% confidence
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.shared.db_config import get_connection

logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore


@dataclass
class SubfamilyClassificationResult:
    """Result from subfamily-level classification."""

    subfamily_code: str  # "601", "602", "603", etc.
    subfamily_name: str  # "Gastos generales", "Gastos de venta", etc.
    confidence: float  # 0.0 - 1.0
    reasoning: str  # Explanation of why this subfamily
    alternative_subfamilies: List[Dict[str, Any]]  # Alternatives with probabilities
    requires_human_review: bool  # True if confidence < 0.90
    validation: Dict[str, Any]  # Hierarchical validation info

    # Metadata
    shortlist_size: int  # Number of subfamilies evaluated
    model_used: str  # LLM model used

    # Raw response for debugging
    raw_response: Optional[str] = None


class SubfamilyClassifier:
    """
    Phase 2A classifier: Categorizes invoices into subfamily level (601, 602, 603...).

    This classifier receives:
    - Family code from Phase 1 (e.g., "600")
    - Invoice snapshot (description, provider, etc.)

    It performs:
    1. Query database for all subfamilies under the family (e.g., "600" → 601, 602, 603...)
    2. Build LLM prompt with shortlist of subfamilies
    3. Let LLM select the most appropriate subfamily
    4. Validate hierarchically that subfamily belongs to family

    Key Benefits:
    - Dramatically reduces candidate space for Phase 2B embedding search
    - Provides better traceability (600 → 603 → 603.5)
    - Improves LLM precision with smaller shortlist
    """

    def __init__(self, model: str = "claude-3-5-haiku-20241022"):
        """
        Initialize subfamily classifier.

        Args:
            model: Claude model to use for classification
                  Default is Haiku since subfamily classification is a focused task
        """
        self.model = model

        # Initialize Anthropic client
        if anthropic:
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY")
            self._client = anthropic.Anthropic(api_key=api_key) if api_key else None
        else:
            self._client = None

    def classify(
        self,
        invoice_data: Dict[str, Any],
        family_code: str,
        family_name: str,
        family_confidence: float,
        family_reasoning: Optional[str] = None,
        company_context: Optional[Dict[str, Any]] = None,
    ) -> SubfamilyClassificationResult:
        """
        Classify invoice to subfamily level (601, 602, 603...).

        Args:
            invoice_data: Dict with invoice fields:
                - descripcion: Invoice description/concept
                - proveedor: Provider name
                - rfc_proveedor: Provider RFC
                - clave_prod_serv: SAT product/service code (optional)
                - monto: Invoice amount
                - uso_cfdi: UsoCFDI code (optional)
            family_code: Family code from Phase 1 (e.g., "600")
            family_name: Family name from Phase 1 (e.g., "GASTOS OPERACIÓN")
            family_confidence: Confidence from Phase 1 (e.g., 0.95)
            company_context: Optional company classification context with industry, business_model, etc.

        Returns:
            SubfamilyClassificationResult with subfamily code and detailed reasoning

        Raises:
            ValueError: If invoice_data is missing required fields or no subfamilies found
            Exception: If LLM call fails or response cannot be parsed
        """

        # Validate required fields
        required_fields = ['descripcion', 'proveedor', 'monto']
        missing_fields = [f for f in required_fields if not invoice_data.get(f)]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        # Step 1: Query database for subfamilies under this family
        subfamilies = self._get_subfamilies_for_family(family_code)

        if not subfamilies:
            raise ValueError(f"No subfamilies found for family {family_code}")

        logger.info(
            f"Classifying to SUBFAMILY level: Family {family_code} has {len(subfamilies)} subfamilies"
        )

        # Step 2: Build prompt with subfamily shortlist
        prompt = self._build_prompt(
            invoice_data=invoice_data,
            family_code=family_code,
            family_name=family_name,
            family_confidence=family_confidence,
            subfamilies=subfamilies,
            family_reasoning=family_reasoning,
            company_context=company_context,
        )

        # Step 3: Call LLM
        try:
            if not self._client:
                raise ValueError("Anthropic client not initialized - check ANTHROPIC_API_KEY env var")

            response = self._client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.0,  # Deterministic classification
                system=(
                    "Eres un contador experto mexicano especializado en el Código Agrupador SAT. "
                    "Tu tarea es clasificar una factura en UNA SUBFAMILIA específica del catálogo SAT. "
                    "IMPORTANTE: La subfamilia debe ser uno de los códigos de 3 dígitos proporcionados en el prompt. "
                    "Responde ÚNICAMENTE con el objeto JSON solicitado, sin texto explicativo adicional."
                ),
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text from response
            content = ""
            for block in response.content:
                block_text = getattr(block, "text", None)
                if isinstance(block_text, str):
                    content += block_text

            logger.debug(f"LLM response: {content[:500]}...")

            # Step 4: Parse JSON response
            result = self._parse_response(content, family_code, subfamilies)
            result.raw_response = content

            # Log classification result
            logger.info(
                f"Subfamily classification: {result.subfamily_code} ({result.subfamily_name}) "
                f"- Confidence: {result.confidence:.2%}"
            )

            if result.requires_human_review:
                logger.warning(
                    f"Subfamily classification has low confidence ({result.confidence:.2%}) - "
                    f"requires human review"
                )

            return result

        except Exception as e:
            logger.error(f"Subfamily classification failed: {e}", exc_info=True)
            raise

    def _get_subfamilies_for_family(self, family_code: str) -> List[Dict[str, str]]:
        """
        Query database for all subfamilies under the given family.

        Args:
            family_code: Family code (e.g., "600")

        Returns:
            List of dicts with subfamily info:
            [
                {"code": "601", "name": "Gastos generales", "description": "..."},
                {"code": "602", "name": "Gastos de venta", "description": "..."},
                ...
            ]
        """

        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Subfamilies are codes of 3 digits (e.g., 601, 602, 603)
            # that start with the family's first digit (e.g., 6XX for family 600)
            cursor.execute(
                """
                SELECT DISTINCT code, name, description
                FROM sat_account_embeddings
                WHERE code LIKE %s
                  AND LENGTH(code) = 3
                ORDER BY code
                """,
                (f"{family_code[0]}%",),  # First digit of family code (e.g., "6" from "600")
            )

            results = cursor.fetchall()

            subfamilies = []
            for code, name, description in results:
                subfamilies.append({
                    'code': code,
                    'name': name,
                    'description': description or name
                })

            logger.info(f"Found {len(subfamilies)} subfamilies for family {family_code}")
            return subfamilies

        finally:
            cursor.close()
            conn.close()

    def _build_prompt(
        self,
        invoice_data: Dict[str, Any],
        family_code: str,
        family_name: str,
        family_confidence: float,
        subfamilies: List[Dict[str, str]],
        family_reasoning: Optional[str] = None,
        company_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build prompt for subfamily classification."""

        # Format subfamilies for prompt
        subfamilies_formatted = "\n".join([
            f"{sf['code']}: {sf['name']}"
            for sf in subfamilies
        ])

        # Format payment method information
        metodo_pago = invoice_data.get('metodo_pago', 'N/A')
        forma_pago = invoice_data.get('forma_pago', 'N/A')

        # Build payment context explanation
        payment_context = ""
        if metodo_pago == 'PUE':
            payment_context = "⚠️ PUE = Pago en Una Exhibición (CONTADO) - NO es anticipo"
        elif metodo_pago == 'PPD':
            payment_context = "⚠️ PPD = Pago en Parcialidades o Diferido - PUEDE ser anticipo"

        # Build company context block (STATIC - max ~100 tokens)
        company_context_block = ""
        if company_context:
            industry_desc = company_context.get('industry_description') or company_context.get('industry', 'N/A')
            business_model_desc = company_context.get('business_model_description') or company_context.get('business_model', 'N/A')

            # Limit typical_expenses to 5 items max (prevent growth)
            typical_expenses = company_context.get('typical_expenses', [])
            if typical_expenses and len(typical_expenses) > 5:
                typical_expenses = typical_expenses[:5]
            typical_expenses_str = ', '.join(typical_expenses) if typical_expenses else 'N/A'

            company_context_block = f"""
CONTEXTO EMPRESA RECEPTORA:
- Industria/Giro: {industry_desc}
- Modelo de negocio: {business_model_desc}
- Gastos típicos: {typical_expenses_str}

⚠️ IMPORTANTE: El MISMO gasto puede ser 601, 602 o 603 según el USO que le da esta empresa.
   - Si el gasto es PARA VENDER productos/servicios → 602 (Gastos de venta)
   - Si el gasto es PARA OPERAR internamente → 601 (Gastos generales)
   - Si el gasto es FINANCIERO/HONORARIOS → 603 (Gastos de administración)
"""

        prompt = f"""Clasifica esta factura en UNA SUBFAMILIA específica del Código Agrupador SAT.

FACTURA:
- Descripción: {invoice_data['descripcion']}
- Proveedor: {invoice_data['proveedor']} (RFC: {invoice_data.get('rfc_proveedor', 'N/A')})
- Monto: ${invoice_data['monto']:,.2f} MXN
- Uso CFDI: {invoice_data.get('uso_cfdi', 'N/A')}
- Clave Producto/Servicio: {invoice_data.get('clave_prod_serv', 'N/A')}
- Método de Pago: {metodo_pago} {payment_context}
- Forma de Pago: {forma_pago}
{company_context_block}
CONTEXTO JERÁRQUICO (ya determinado en Fase 1):
- Familia: {family_code} - {family_name}
- Confianza familia: {family_confidence:.2%}
- Razonamiento Fase 1: {family_reasoning if family_reasoning else 'N/A'}

SUBFAMILIAS DISPONIBLES PARA FAMILIA {family_code}:
{subfamilies_formatted}

INSTRUCCIONES:
1. Analiza el tipo específico de gasto/servicio descrito en la factura
2. Considera la naturaleza del proveedor y su actividad económica
3. Selecciona LA SUBFAMILIA más apropiada de la lista arriba
4. La subfamilia DEBE estar en la lista proporcionada

⚠️ REGLAS CRÍTICAS PARA CLASIFICACIÓN DE ANTICIPOS:
- Si Método de Pago = "PUE" → NO clasificar como 120 (Anticipo a proveedores)
- PUE significa pago de CONTADO, no anticipo
- Materiales/etiquetas/envases para producción → 115 (Inventario), NO 120
- Solo usa 120 (Anticipo) si Método Pago = "PPD" Y la descripción indica pago anticipado

🎯 REGLAS IMPERATIVAS PARA SUBFAMILIAS DE GASTOS (600):

**IMPORTANTE: Analiza TODA la descripción completa (incluyendo conceptos adicionales) para determinar la subfamilia correcta.**

**PROCESO DE CLASIFICACIÓN (en orden de prioridad):**

**PASO 1: Busca KEYWORDS DE LOGÍSTICA/VENTA en TODA la descripción:**
Si encuentras CUALQUIERA de estas palabras → DEBE ser 602:
- "almacenamiento", "storage", "bodega", "warehouse"
- "logística", "logistics", "fulfillment", "FBA"
- "flete", "envío", "shipping", "delivery", "entrega", "paquetería"
- "distribución", "acarreo", "transportación de mercancías"
- "comisión venta", "comisión vendedor", "publicidad", "marketing"

⚠️ EXCEPCIONES que NO son 602 (son 601):
- "mantenimiento vehículo", "afinación", "reparación vehículo" → 601 (uso interno)
- "combustible", "gasolina", "diesel" (sin mención de reparto) → 601 (uso interno)

⚠️ IMPORTANTE: Si estas palabras aparecen en "Adicionales:", aún aplica 602
⚠️ EJEMPLO: "Suscripción (84%) | Adicionales: Tarifas de almacenamiento de Amazon" → 602 (porque dice "almacenamiento")

**PASO 2: Si NO hay keywords de logística, busca SERVICIOS FINANCIEROS/PROFESIONALES:**
- "comisión bancaria", "fee bancario", "cargo financiero"
- "honorarios", "asesoría", "consultoría", "gestoría"
- "intereses", "recargos financieros"
→ CLASIFICAR como 603

**PASO 3: Si NO es logística NI financiero:**
- Servicios/software para uso interno
- Mantenimiento, suministros de oficina
→ CLASIFICAR como 601

**EJEMPLOS CONCRETOS:**
- "Suscripción software interno" → 601
- "Suscripción | Adicionales: Almacenamiento Amazon" → 602 (¡por la palabra "almacenamiento"!)
- "Comisión servicio bancario" → 603
- "Flete nacional" → 602

Responde SOLO con JSON válido:
{{
  "subfamily_code": "603",
  "subfamily_name": "Gastos de administración",
  "confidence": 0.92,
  "reasoning": "Explicación breve de por qué esta subfamilia es la más apropiada...",
  "alternative_subfamilies": [
    {{"code": "601", "name": "Gastos generales", "probability": 0.05, "reason": "Por qué podría ser alternativa..."}}
  ],
  "requires_human_review": false
}}"""

        return prompt

    def _parse_response(
        self,
        response: str,
        family_code: str,
        subfamilies: List[Dict[str, str]],
    ) -> SubfamilyClassificationResult:
        """
        Parse LLM JSON response into SubfamilyClassificationResult.

        Args:
            response: Raw LLM response (should be JSON)
            family_code: Expected family code for validation
            subfamilies: List of valid subfamilies for validation

        Returns:
            SubfamilyClassificationResult

        Raises:
            ValueError: If response is not valid JSON or missing required fields
        """

        # Extract JSON from response (handle markdown code blocks)
        cleaned_response = response.strip()

        if "```json" in cleaned_response:
            cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_response:
            cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()

        # Handle narrative text before JSON
        if not cleaned_response.startswith('{'):
            json_start = cleaned_response.find('{')
            if json_start != -1:
                logger.debug(f"Removing {json_start} characters of narrative text before JSON")
                cleaned_response = cleaned_response[json_start:]
            else:
                logger.error(f"No JSON object found in response: {response[:200]}...")
                raise ValueError(f"No JSON object found in LLM response")

        try:
            data = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {cleaned_response[:500]}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

        # Validate required fields
        required_fields = [
            'subfamily_code', 'subfamily_name', 'confidence',
            'reasoning', 'requires_human_review'
        ]
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            raise ValueError(f"LLM response missing required fields: {missing_fields}")

        subfamily_code = str(data['subfamily_code'])
        subfamily_name = str(data['subfamily_name'])
        confidence = float(data['confidence'])

        # Validate hierarchically: subfamily must belong to family
        is_valid = subfamily_code.startswith(family_code[0])

        # Validate subfamily is in the shortlist
        valid_codes = {sf['code'] for sf in subfamilies}
        is_in_shortlist = subfamily_code in valid_codes

        if not is_valid:
            logger.error(
                f"Hierarchical validation failed: subfamily {subfamily_code} does not belong to family {family_code}"
            )

        if not is_in_shortlist:
            logger.warning(
                f"Subfamily {subfamily_code} not in original shortlist - LLM hallucination?"
            )

        # Build validation metadata
        validation = {
            'is_hierarchically_valid': is_valid,
            'is_in_shortlist': is_in_shortlist,
            'expected_family': family_code,
            'obtained_subfamily': subfamily_code,
        }

        return SubfamilyClassificationResult(
            subfamily_code=subfamily_code,
            subfamily_name=subfamily_name,
            confidence=confidence,
            reasoning=str(data['reasoning']),
            alternative_subfamilies=data.get('alternative_subfamilies', []),
            requires_human_review=bool(data['requires_human_review']) or confidence < 0.90 or not is_valid,
            validation=validation,
            shortlist_size=len(subfamilies),
            model_used=self.model,
        )


def get_subfamily_classifier(model: str = "claude-3-5-haiku-20241022") -> SubfamilyClassifier:
    """
    Factory function to get a SubfamilyClassifier instance.

    Args:
        model: Claude model to use (default: Haiku for cost optimization)

    Returns:
        SubfamilyClassifier instance
    """
    return SubfamilyClassifier(model=model)


__all__ = [
    'SubfamilyClassifier',
    'SubfamilyClassificationResult',
    'get_subfamily_classifier',
]
