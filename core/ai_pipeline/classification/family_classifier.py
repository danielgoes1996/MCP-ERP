"""
Family-level classifier for hierarchical invoice classification.

This is PHASE 1 of the 3-phase hierarchical classification system:
- Phase 1: Classify to family level (100-800) with >95% confidence ← THIS FILE
- Phase 2: Refine to subfamily (e.g., 600 → 613) with >90% confidence
- Phase 3: Select detailed account (e.g., 613 → 613.01) with >85% confidence
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.ai_pipeline.classification.prompts.family_classifier_prompt_optimized import (
    build_family_classification_prompt_optimized as build_family_classification_prompt,
)
from core.shared.company_context import get_company_classification_context
from core.ai_pipeline.classification.response_models import (
    FamilyClassificationResponse,
    ClassificationError,
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore


@dataclass
class FamilyClassificationResult:
    """Result from family-level classification."""

    familia_codigo: str  # "100", "200", "300", "400", "500", "600", "700", "800"
    familia_nombre: str  # "ACTIVO", "PASIVO", etc.
    confianza: float  # 0.0 - 1.0
    razonamiento_principal: str  # 1-2 sentence explanation
    factores_decision: List[str]  # List of decision factors
    uso_cfdi_analisis: str  # Analysis of UsoCFDI field
    override_uso_cfdi: bool  # True if classification contradicts UsoCFDI
    override_razon: Optional[str]  # Reason for override
    familias_alternativas: List[Dict[str, Any]]  # Alternative families with probabilities
    requiere_revision_humana: bool  # True if confidence < 0.95
    siguiente_fase: str  # "subfamily" to continue classification
    comentarios_adicionales: str  # Additional observations

    # Raw response for debugging
    raw_response: Optional[str] = None


class FamilyClassifier:
    """
    Phase 1 classifier: Categorizes invoices into family level (100-800).

    This classifier uses semantic analysis of invoice description + company context
    as PRIMARY signals, with UsoCFDI as SECONDARY validation only.

    Key Philosophy:
    - Trust invoice concept + business context over formal UsoCFDI declaration
    - Provider reliability varies (they often select UsoCFDI incorrectly)
    - Economic reality > Formal declaration
    """

    def __init__(self, model: str = "claude-3-5-haiku-20241022"):
        """
        Initialize family classifier.

        Args:
            model: Claude model to use for classification
                  Default is Haiku since family classification is a simple task (8 options)
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
        company_id: str,
        tenant_id: Optional[int] = None,
    ) -> FamilyClassificationResult:
        """
        Classify invoice to family level (100-800).

        Args:
            invoice_data: Dict with invoice fields:
                - descripcion: Invoice description/concept
                - proveedor: Provider name
                - rfc_proveedor: Provider RFC
                - clave_prod_serv: SAT product/service code
                - monto: Invoice amount
                - uso_cfdi: UsoCFDI code (optional, used as validation only)
            company_id: Company identifier
            tenant_id: Tenant identifier (optional)

        Returns:
            FamilyClassificationResult with family code and detailed reasoning

        Raises:
            ValueError: If invoice_data is missing required fields
            Exception: If LLM call fails or response cannot be parsed
        """

        # Validate required fields
        required_fields = ['descripcion', 'proveedor', 'monto']
        missing_fields = [f for f in required_fields if not invoice_data.get(f)]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        # Load company context
        company_context = None
        company_id_int = None
        try:
            # Resolve company_id to integer
            company_id_int = self._resolve_company_id(company_id)
            if company_id_int:
                company_context = get_company_classification_context(company_id_int)
                if company_context:
                    industry_desc = company_context.get('industry_description') or company_context.get('industry', 'N/A')
                    logger.info(f"Loaded company context for {company_id}: {industry_desc}")
                else:
                    logger.warning(f"No classification context found for company_id={company_id_int}")
            else:
                logger.warning(f"Could not resolve company_id '{company_id}' to integer")
        except Exception as e:
            logger.warning(f"Could not load company context for {company_id}: {e}")

        # Build prompt (initially without few-shot examples)
        prompt = build_family_classification_prompt(
            invoice_data=invoice_data,
            company_context=company_context,
            few_shot_examples=None,  # First attempt without examples
        )

        logger.info(
            f"Classifying invoice at FAMILY level: {invoice_data.get('descripcion', '')[:100]}... "
            f"(provider: {invoice_data.get('proveedor', 'N/A')})"
        )

        # Call LLM
        try:
            if not self._client:
                raise ValueError("Anthropic client not initialized - check ANTHROPIC_API_KEY env var")

            response = self._client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.0,  # Deterministic classification
                system=(
                    "Eres un contador experto mexicano especializado en clasificación de gastos "
                    "bajo el Código Agrupador del SAT. Tu tarea es clasificar facturas a nivel de familia "
                    "(100-800) basándote principalmente en el concepto de la factura y el contexto empresarial. "
                    "IMPORTANTE: Responde ÚNICAMENTE con el objeto JSON solicitado, sin texto explicativo adicional. "
                    "NO incluyas introducciones, explicaciones o comentarios antes o después del JSON."
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

            # Parse JSON response
            result = self._parse_response(content)
            result.raw_response = content

            # Log classification result
            logger.info(
                f"Family classification: {result.familia_codigo} ({result.familia_nombre}) "
                f"- Confidence: {result.confianza:.2%} "
                f"- Override UsoCFDI: {result.override_uso_cfdi}"
            )

            if result.override_uso_cfdi:
                logger.warning(
                    f"UsoCFDI override detected: {invoice_data.get('uso_cfdi')} → {result.familia_codigo} "
                    f"Reason: {result.override_razon}"
                )

            # Conditional few-shot learning: If confidence < 80%, retry with examples
            if result.confianza < 0.80 and company_id_int:
                logger.info(
                    f"Confidence {result.confianza:.2%} < 80% threshold - "
                    f"Retrying classification with few-shot examples..."
                )

                # Fetch few-shot examples
                from core.shared.company_context import get_family_classification_examples
                few_shot_examples = get_family_classification_examples(
                    company_id=company_id_int,
                    description=invoice_data.get('descripcion'),
                    limit=5
                )

                if few_shot_examples:
                    logger.info(f"Found {len(few_shot_examples)} few-shot examples for learning")

                    # Rebuild prompt with few-shot examples
                    prompt_with_examples = build_family_classification_prompt(
                        invoice_data=invoice_data,
                        company_context=company_context,
                        few_shot_examples=few_shot_examples,
                    )

                    # Re-classify with examples
                    response_with_examples = self._client.messages.create(
                        model=self.model,
                        max_tokens=2000,
                        temperature=0.0,
                        system=(
                            "Eres un contador experto mexicano especializado en clasificación de gastos "
                            "bajo el Código Agrupador del SAT. Tu tarea es clasificar facturas a nivel de familia "
                            "(100-800) basándote principalmente en el concepto de la factura y el contexto empresarial. "
                            "IMPORTANTE: Responde ÚNICAMENTE con el objeto JSON solicitado, sin texto explicativo adicional. "
                            "NO incluyas introducciones, explicaciones o comentarios antes o después del JSON."
                        ),
                        messages=[{"role": "user", "content": prompt_with_examples}],
                    )

                    # Extract and parse response
                    content_with_examples = ""
                    for block in response_with_examples.content:
                        block_text = getattr(block, "text", None)
                        if isinstance(block_text, str):
                            content_with_examples += block_text

                    result_with_examples = self._parse_response(content_with_examples)
                    result_with_examples.raw_response = content_with_examples

                    logger.info(
                        f"Few-shot classification: {result_with_examples.familia_codigo} ({result_with_examples.familia_nombre}) "
                        f"- New confidence: {result_with_examples.confianza:.2%} "
                        f"(was {result.confianza:.2%})"
                    )

                    # Use the new result
                    result = result_with_examples
                else:
                    logger.info("No few-shot examples found - keeping original classification")

            return result

        except Exception as e:
            logger.error(f"Family classification failed: {e}", exc_info=True)
            raise

    def _parse_response(self, response: str) -> FamilyClassificationResult:
        """
        Parse LLM JSON response into FamilyClassificationResult with Pydantic validation.

        Args:
            response: Raw LLM response (should be JSON)

        Returns:
            FamilyClassificationResult

        Raises:
            ValueError: If response is not valid JSON or missing required fields
        """

        # Extract JSON from response (handle markdown code blocks and narrative text)
        cleaned_response = response.strip()

        # Handle markdown code blocks
        if "```json" in cleaned_response:
            cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_response:
            cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()

        # Handle narrative text before JSON - look for the first '{'
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

        # Validate with Pydantic model first
        try:
            validated_response = FamilyClassificationResponse(**data)
            logger.debug(f"Pydantic validation passed for family classification")
        except ValidationError as e:
            logger.error(f"Pydantic validation failed: {e}\nResponse data: {data}")
            raise ValueError(f"LLM response failed validation: {e}")

        # Validate other required fields not in Pydantic model
        required_fields = [
            'factores_decision',
            'uso_cfdi_analisis', 'override_uso_cfdi',
            'requiere_revision_humana', 'siguiente_fase'
        ]

        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            raise ValueError(f"LLM response missing required fields: {missing_fields}")

        # Build result using validated Pydantic data + extra fields
        return FamilyClassificationResult(
            familia_codigo=validated_response.familia_codigo,
            familia_nombre=validated_response.familia_nombre,
            confianza=validated_response.confianza,
            razonamiento_principal=validated_response.razonamiento,
            factores_decision=data['factores_decision'],
            uso_cfdi_analisis=str(data['uso_cfdi_analisis']),
            override_uso_cfdi=bool(data['override_uso_cfdi']),
            override_razon=data.get('override_razon'),
            familias_alternativas=data.get('familias_alternativas', []),
            requiere_revision_humana=bool(data['requiere_revision_humana']),
            siguiente_fase=str(data['siguiente_fase']),
            comentarios_adicionales=str(data.get('comentarios_adicionales', '')),
        )

    def _resolve_company_id(self, company_id_raw: Any) -> Optional[int]:
        """
        Resolve company_id to integer.
        Handles int, numeric string, and string slug formats.
        """
        if not company_id_raw:
            return None

        if isinstance(company_id_raw, int):
            return company_id_raw
        elif isinstance(company_id_raw, str) and company_id_raw.isdigit():
            return int(company_id_raw)
        else:
            # Try lookup via tenant_utils
            try:
                from core.shared.tenant_utils import get_tenant_and_company
                _, company_id_int = get_tenant_and_company(company_id_raw)
                return company_id_int
            except (ImportError, ValueError, Exception) as e:
                logger.warning(f"Could not resolve company_id '{company_id_raw}' to integer: {e}")
                return None

    def classify_batch(
        self,
        invoices: List[Dict[str, Any]],
        company_id: str,
        tenant_id: Optional[int] = None,
    ) -> List[FamilyClassificationResult]:
        """
        Classify multiple invoices to family level.

        Args:
            invoices: List of invoice_data dicts
            company_id: Company identifier
            tenant_id: Tenant identifier (optional)

        Returns:
            List of FamilyClassificationResult (same order as input)
        """

        results = []
        for i, invoice_data in enumerate(invoices):
            try:
                logger.info(f"Classifying invoice {i+1}/{len(invoices)}")
                result = self.classify(invoice_data, company_id, tenant_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to classify invoice {i+1}: {e}")
                # Return a default "needs review" result on failure
                results.append(
                    FamilyClassificationResult(
                        familia_codigo="600",  # Default to operating expenses
                        familia_nombre="GASTOS DE OPERACIÓN",
                        confianza=0.0,
                        razonamiento_principal=f"Error en clasificación: {str(e)[:100]}",
                        factores_decision=[],
                        uso_cfdi_analisis="Error durante clasificación",
                        override_uso_cfdi=False,
                        override_razon=None,
                        familias_alternativas=[],
                        requiere_revision_humana=True,
                        siguiente_fase="manual_review",
                        comentarios_adicionales=f"Error: {str(e)}",
                        raw_response=None,
                    )
                )

        return results


def get_family_classifier(model: str = "claude-3-5-haiku-20241022") -> FamilyClassifier:
    """
    Factory function to get a FamilyClassifier instance.

    Args:
        model: Claude model to use (default: Haiku for cost optimization)

    Returns:
        FamilyClassifier instance
    """
    return FamilyClassifier(model=model)


__all__ = [
    'FamilyClassifier',
    'FamilyClassificationResult',
    'get_family_classifier',
]
