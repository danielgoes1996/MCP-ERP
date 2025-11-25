"""LLM-assisted SAT classification helper."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from core.shared.text_normalizer import normalize_expense_text
from core.sat_utils import extract_family_code
from core.shared.company_context import (
    get_company_classification_context,
    format_context_for_prompt,
    get_similar_corrections,
    format_corrections_for_prompt,
)
from core.ai_pipeline.classification.response_models import (
    SATClassificationResponse,
    ClassificationError,
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)

try:  # Optional dependency
    import anthropic
except ImportError:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore


@dataclass
class ClassificationResult:
    sat_account_code: Optional[str]
    family_code: Optional[str]
    confidence_sat: float
    confidence_family: float
    explanation_short: str
    explanation_detail: str
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    alternative_candidates: Optional[List[Dict[str, Any]]] = None  # Top 5 alternative SAT codes for UI dropdown
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata for debugging (e.g., llm_raw_response)


@lru_cache()
def _read_version_file(filename: str, default: str) -> str:
    path = Path(filename)
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            return content
    return default


MODEL_VERSION = _read_version_file("MODEL_VERSION", "claude-3-haiku-20240307")
PROMPT_VERSION = _read_version_file("PROMPT_VERSION", "prompt-v1")


class ExpenseLLMClassifier:
    """Wrapper around Anthropic Claude (or fallback heuristic) for SAT classification."""

    def __init__(self, model: Optional[str] = None) -> None:
        # Use provided model, or fallback to MODEL_VERSION, or default to Haiku
        self.model = model or MODEL_VERSION or "claude-3-5-haiku-20241022"
        self.prompt_version = PROMPT_VERSION
        self._client = None
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic and api_key:
            self._client = anthropic.Anthropic(api_key=api_key)

    def _build_alternative_candidates(self, candidates: List[Dict[str, Any]], chosen_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Build list of alternative candidates for UI dropdown.
        Returns top 4 alternatives (excluding the chosen one).
        """
        alternatives = []
        for candidate in candidates[:5]:
            # Skip if this is the chosen SAT code
            if chosen_code and candidate.get('code') == chosen_code:
                continue

            alternatives.append({
                'code': candidate.get('code'),
                'name': candidate.get('name'),
                'family_code': extract_family_code(candidate.get('code')),
                'score': float(candidate.get('score', 0)),
                'description': candidate.get('description', candidate.get('context', ''))
            })

        # Limit to top 4 alternatives
        return alternatives[:4]

    def classify(
        self,
        snapshot: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        hierarchical_family: Optional[str] = None,
        subfamily_reasoning: Optional[str] = None
    ) -> ClassificationResult:
        if not candidates:
            return ClassificationResult(
                sat_account_code=None,
                family_code=None,
                confidence_sat=0.0,
                confidence_family=0.0,
                explanation_short="Sin candidatos",
                explanation_detail="No se encontraron cuentas SAT relevantes en la búsqueda inicial.",
                alternative_candidates=[],
            )

        # === AUTO-APPLY LOGIC: Check correction memory BEFORE calling LLM ===
        company_id_int = self._resolve_company_id(snapshot.get("company_id"))
        if company_id_int:
            provider_rfc = snapshot.get("provider_rfc")
            clave_prod_serv = snapshot.get("clave_prod_serv")

            # Get similar corrections from memory
            corrections = get_similar_corrections(
                company_id_int,
                provider_rfc=provider_rfc,
                description=snapshot.get("descripcion_original"),
                limit=10
            )

            if corrections:
                # Count occurrences of each SAT code in corrections
                sat_code_counts = {}
                for correction in corrections:
                    sat_code = correction.get('sat_code')
                    if sat_code:
                        sat_code_counts[sat_code] = sat_code_counts.get(sat_code, 0) + 1

                # If we have ≥2 corrections pointing to the same SAT code, auto-apply
                if sat_code_counts:
                    most_common_sat = max(sat_code_counts, key=sat_code_counts.get)
                    count = sat_code_counts[most_common_sat]

                    if count >= 2:
                        family = extract_family_code(most_common_sat)
                        logger.info(
                            f"Auto-applying learned pattern: {most_common_sat} "
                            f"(company_id={company_id_int}, provider_rfc={provider_rfc}, "
                            f"corrections_count={count})"
                        )
                        return ClassificationResult(
                            sat_account_code=most_common_sat,
                            family_code=family,
                            confidence_sat=0.95,  # High confidence from learning
                            confidence_family=0.95,
                            explanation_short=f"Aplicado automáticamente (aprendido de {count} correcciones previas)",
                            explanation_detail=(
                                f"Este patrón ha sido corregido {count} veces por contadores. "
                                f"Se aplicó automáticamente sin consultar al LLM para mayor velocidad."
                            ),
                            model_version="auto-apply-v1",
                            prompt_version=self.prompt_version,
                            alternative_candidates=self._build_alternative_candidates(candidates, most_common_sat),
                        )

        if not self._client:
            # Fallback: choose top candidate (respecting hierarchical family if provided)
            best = candidates[0]

            # If hierarchical_family is set, try to find a candidate from that family
            if hierarchical_family:
                for candidate in candidates[:10]:  # Check top 10
                    candidate_family = extract_family_code(candidate.get("code"))
                    if candidate_family == hierarchical_family:
                        best = candidate
                        break

            family = extract_family_code(best.get("code"))
            return ClassificationResult(
                sat_account_code=best.get("code"),
                family_code=family,
                confidence_sat=float(best.get("score", 0.5)),
                confidence_family=float(best.get("score", 0.5)),
                explanation_short="Selección heurística",
                explanation_detail="Se eligió el candidato con mayor similitud ante la ausencia de LLM.",
                alternative_candidates=self._build_alternative_candidates(candidates, best.get("code")),
            )

        prompt = self._build_prompt(snapshot, candidates, hierarchical_family, subfamily_reasoning)

        # DEBUG: Log the complete prompt
        logger.debug("=" * 100)
        logger.debug("PROMPT COMPLETO ENVIADO AL LLM:")
        logger.debug("=" * 100)
        logger.debug(prompt)
        logger.debug("=" * 100)

        response = self._client.messages.create(
            model=self.model,
            max_tokens=400,
            temperature=0.0,  # Deterministic for consistency (Option B)
            system=(
                "Eres un contador experto en el catálogo SAT mexicano. "
                "Debes analizar los detalles del gasto y elegir la cuenta SAT que mejor aplique. "
                "Siempre responde en JSON válido usando claves: family_code, sat_account_code, confidence_family, "
                "confidence_sat, explanation_short, explanation_detail. "
                "confidence_* debe ser un número entre 0 y 1."
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        content = ""
        for block in response.content:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                content += block_text

        result = self._parse_response(content, candidates)

        # Store raw LLM response in metadata for debugging
        if not hasattr(result, 'metadata') or result.metadata is None:
            result.metadata = {}
        result.metadata['llm_raw_response'] = content

        return result

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

    def _build_prompt(
        self,
        snapshot: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        hierarchical_family: Optional[str] = None,
        subfamily_reasoning: Optional[str] = None
    ) -> str:
        features = {
            "descripcion": snapshot.get("descripcion_original"),
            "descripcion_normalizada": snapshot.get("descripcion_normalizada"),
            "keywords": snapshot.get("keywords"),
            "categoria_slug": snapshot.get("categoria_slug"),
            "categoria_usuario": snapshot.get("categoria_usuario"),
            "categoria_contable": snapshot.get("categoria_contable"),
            "provider_name": snapshot.get("provider_name"),
            "provider_rfc": snapshot.get("provider_rfc"),
            "amount": snapshot.get("amount"),
            "amount_bucket": snapshot.get("amount_bucket"),
            "payment_method": snapshot.get("payment_method"),
            "bank_status": snapshot.get("bank_status"),
            "invoice_status": snapshot.get("invoice_status"),
            "tenant_id": snapshot.get("tenant_id"),
            "company_id": snapshot.get("company_id"),
            "existing_sat_account_code": snapshot.get("existing_sat_account_code"),
            "uso_cfdi": snapshot.get("uso_cfdi"),  # NEW: UsoCFDI for validation
        }

        slim_snapshot = {k: v for k, v in features.items() if v not in (None, "", [], {})}

        # === NUEVO: Recuperar contexto de la empresa automáticamente ===
        company_block = ""
        corrections_block = ""

        company_id_int = self._resolve_company_id(snapshot.get("company_id"))

        if company_id_int:
            # Recuperar contexto de clasificación
            context = get_company_classification_context(company_id_int)
            if context:
                provider_rfc = snapshot.get("provider_rfc")
                formatted_context = format_context_for_prompt(context, provider_rfc)
                if formatted_context:
                    company_block = f"{formatted_context}\n\n"
                    logger.info(f"Injected company context for company_id={company_id_int}")

            # Recuperar correcciones previas similares
            provider_rfc = snapshot.get("provider_rfc")
            corrections = get_similar_corrections(company_id_int, provider_rfc=provider_rfc, limit=3)
            if corrections:
                formatted_corrections = format_corrections_for_prompt(corrections)
                if formatted_corrections:
                    corrections_block = f"{formatted_corrections}\n\n"
                    logger.info(f"Injected {len(corrections)} similar corrections for company_id={company_id_int}")

        # === Construir bloque de candidatos ===
        candidate_lines = []
        for idx, candidate in enumerate(candidates, start=1):
            candidate_lines.append(
                f"{idx}. {candidate.get('code')} — {candidate.get('name')} "
                f"(familia {candidate.get('family_hint')}, score {candidate.get('score'):.2f})"
            )
            context = candidate.get("context") or candidate.get("description") or ""
            if context:
                context_clean = normalize_expense_text(context)
                if context_clean:
                    candidate_lines.append(f"   contexto: {context_clean}")

        candidate_block = "\n".join(candidate_lines)

        # === Construir prompt final ===
        prompt = (
            "A continuación se presentan los datos de una FACTURA RECIBIDA (una compra/gasto/inversión que la empresa está pagando a un proveedor) "
            "y un conjunto de cuentas candidatas del catálogo SAT.\n\n"

            "IMPORTANTE: Esta factura representa algo que la empresa está COMPRANDO/PAGANDO. "
            "NUNCA uses cuentas de ingresos (400-499), ya que esas son solo para facturas que la empresa EMITE (ventas).\n\n"

            "Analiza el proveedor, concepto y naturaleza de la compra. La clasificación depende del tipo de compra:\n\n"

            "1. ACTIVOS FIJOS (151-158): Bienes de capital que se capitalizan y deprecian\n"
            "   - Laptops, computadoras, servidores → 156 (Equipo de cómputo)\n"
            "   - Vehículos, camionetas, camiones → 154 (Vehículos)\n"
            "   - Muebles, escritorios, sillas → 155 (Mobiliario)\n"
            "   - Maquinaria, equipo industrial → 153 (Maquinaria)\n"
            "   - Software, licencias perpetuas → 118 (Activos intangibles)\n\n"

            "2. INVENTARIOS (115): Mercancía para reventa o materia prima\n"
            "   - Productos para revender → 115 (Inventario)\n"
            "   - Materia prima para producción → 115.02\n\n"

            "3. COSTOS (501-505): Costos directos de producción/ventas\n"
            "   - Materia prima consumida → 501.03\n"
            "   - Compras para producción → 502\n\n"

            "4. GASTOS (601-614): Gastos operativos que se consumen (la mayoría de casos)\n"
            "   - Combustibles y lubricantes (gasolina, diesel) → 601.48, 602.48, 603.48, 604.48\n"
            "   - Servicios (internet, teléfono, consultoría) → 601.xx, 602.xx, 603.xx según tipo\n"
            "   - Transporte y fletes → 607.01\n"
            "   - Sueldos y prestaciones → 601.01, 601.02\n"
            "   - Rentas y arrendamientos → 608.01\n"
            "   - Suministros (papelería, limpieza) → 601.85\n"
            "   - ⚠️  612.xx = Gastos NO DEDUCIBLES (CUFIN) - usar solo para gastos no deducibles fiscalmente\n"
            "   - ⚠️  613.xx = DEPRECIACIÓN CONTABLE - NUNCA para facturas recibidas, solo cálculos internos\n\n"

            "INSTRUCCIONES CRÍTICAS:\n"
            "1. DEBES elegir EXCLUSIVAMENTE una de las cuentas SAT listadas en CANDIDATOS (abajo)\n"
            "2. NO inventes códigos SAT que no estén en la lista de candidatos\n"
            "3. 🚨 PROHIBIDO INVENTAR NOMBRES DE CUENTAS:\n"
            "   - Cuando elijas un código SAT (ej: 613.01), USA EL NOMBRE EXACTO que aparece en la lista de candidatos\n"
            "   - NUNCA inventes o modifiques el nombre de la cuenta SAT\n"
            "   - Ejemplo CORRECTO: Si el candidato dice '613.01 — Depreciación de edificios', tu explanation_short DEBE mencionar 'depreciación', NO inventar 'almacenamiento' u otra palabra\n"
            "   - Ejemplo INCORRECTO: Elegir 613.01 y luego decir 'Gasto por almacenamiento' cuando 613.01 es 'Depreciación de edificios'\n"
            "4. ⚠️  NIVEL DE DETALLE REQUERIDO:\n"
            "   - SIEMPRE selecciona códigos de NIVEL 2 (con punto decimal, ej: 115.02, 613.01, 601.84)\n"
            "   - NUNCA selecciones códigos de NIVEL 1 sin punto decimal (ej: NO uses '115', '613', '601')\n"
            "   - Si la lista de candidatos incluye '115', '115.01', '115.02', DEBES elegir una subcuenta específica (115.01 o 115.02), NO la genérica '115'\n"
            "   - Ejemplo: Para inventario de materiales, usa '115.02' (Materia prima y materiales), NO '115'\n"
            "5. Si ves descripciones técnicas (códigos, medidas, referencias), analiza el CONTEXTO COMPLETO:\n"
            "   - Tipo de proveedor (distribuidora → materiales, servicios → gastos admin)\n"
            "   - Clave producto SAT (24xxx → materiales, 43xxx → cómputo, 81xxx → servicios)\n"
            "   - Palabras clave enriquecidas (envases, materiales, suministros)\n"
            "6. Prioriza el candidato #1 si tiene sentido lógico con el contexto de la compra\n"
            "7. Si hay duda entre capitalizar (activos 15X) vs. gastos (6XX), considera:\n"
            "   - Monto alto + bien duradero → Activo fijo\n"
            "   - Monto bajo + consumible/servicio → Gasto\n\n"
        )

        # === HIERARCHICAL FAMILY CONSTRAINT (Critical Override) ===
        if hierarchical_family:
            prompt += (
                f"⚠️  RESTRICCIÓN JERÁRQUICA (OBLIGATORIA):\n"
                f"El clasificador jerárquico de Fase 1 ha determinado con alta confianza que esta factura "
                f"pertenece a la FAMILIA {hierarchical_family}.\n\n"
                f"DEBES elegir ÚNICAMENTE códigos SAT que pertenezcan a la familia {hierarchical_family}xx.\n"
                f"NO elijas códigos de otras familias, incluso si parecen relevantes.\n\n"
                f"Esta restricción tiene precedencia absoluta sobre cualquier otra consideración.\n"
                f"Si todos los candidatos son de familia {hierarchical_family}, elige el más apropiado.\n"
                f"Si hay candidatos de otras familias en la lista, IGNÓRALOS completamente.\n\n"
            )

        # === HIERARCHICAL REASONING (Phase 2A Context) ===
        if subfamily_reasoning:
            prompt += (
                f"📋 RAZONAMIENTO JERÁRQUICO (Fase 2A - Subfamilia):\n"
                f"{subfamily_reasoning}\n\n"
                f"Considera este análisis previo al seleccionar la cuenta SAT específica.\n\n"
            )

        prompt += (
            f"{company_block}"
            f"{corrections_block}"
        )

        # === NUEVO: UsoCFDI validation block ===
        uso_cfdi = snapshot.get("uso_cfdi")
        if uso_cfdi and company_block:
            # Only add UsoCFDI validation if we have company context to validate against
            prompt += (
                "VALIDACIÓN DE USOCFDI (CRÍTICO):\n"
                "El campo 'uso_cfdi' indica cómo el RECEPTOR declara usar la factura:\n"
                "  - G01 = Adquisición de mercancías (inventario, materias primas, insumos para producción)\n"
                "  - G03 = Gastos en general (servicios, suministros de oficina, gastos operativos)\n"
                "  - I01-I08 = Inversiones en activos fijos (equipo, vehículos, construcciones)\n\n"

                f"ESTA FACTURA TIENE: uso_cfdi='{uso_cfdi}'\n\n"

                "IMPORTANTE: Debes validar si el uso_cfdi es CORRECTO según el contexto de la empresa.\n\n"

                "EJEMPLO DE CONTRADICCIÓN (caso real):\n"
                "  - Empresa: producción de miel (empaca miel en frascos con etiquetas)\n"
                "  - Proveedor: GARIN ETIQUETAS (vende etiquetas adhesivas)\n"
                "  - Descripción: 'ETQ. DIGITAL BOPP TRANSPARENTE 60x195 MM COSECHA MULTIFLORAL 330 GR'\n"
                "  - Código SAT: 55121600 (Etiquetas autoadhesivas)\n"
                "  - uso_cfdi declarado: G03 (Gastos en general) ← INCORRECTO\n"
                "  - uso_cfdi correcto: G01 (Adquisición de mercancías) ← Las etiquetas son INSUMOS para empacar miel\n"
                "  - Clasificación correcta: 115 (Inventario) o 502 (Compras), NO 613.01 (Papelería)\n\n"

                "REGLAS DE VALIDACIÓN:\n"
                "1. Si la empresa es de producción/manufactura Y el proveedor vende insumos/materiales:\n"
                "   → uso_cfdi debería ser G01, NO G03\n"
                "   → Clasifica como 115 (Inventario) o 502 (Compras)\n\n"

                "2. Si uso_cfdi=G03 PERO el contexto indica que es material de producción:\n"
                "   → IGNORA el uso_cfdi incorrecto\n"
                "   → Usa el contexto de la empresa para clasificar correctamente\n"
                "   → Explica la contradicción en 'explanation_detail'\n\n"

                "3. Si uso_cfdi=G01 Y la empresa NO es de producción:\n"
                "   → Puede ser un error, revisa si realmente es inventario\n\n"

                "4. Si uso_cfdi=I01-I08 (inversiones):\n"
                "   → Debe ser activo fijo (151-158), NO gasto\n\n"

                "INSTRUCCIÓN FINAL:\n"
                "En tu respuesta JSON, incluye en 'explanation_detail' si detectaste contradicción entre "
                "uso_cfdi y el contexto real de la empresa, y por qué decidiste overridear la declaración.\n\n"
            )

        prompt += (
            f"DETALLES DE LA COMPRA:\n{json.dumps(slim_snapshot, ensure_ascii=False, indent=2)}\n\n"
            f"CANDIDATOS:\n{candidate_block}\n\n"
            "Devuelve exclusivamente un objeto JSON con las claves pedidas."
        )
        return prompt

    def _extract_json_from_markdown(self, content: str) -> Optional[str]:
        """
        Extract JSON from markdown code blocks.

        Handles formats like:
        ```json
        { ... }
        ```

        Or plain text with JSON embedded.

        Args:
            content: Raw LLM response

        Returns:
            Extracted JSON string or None if not found
        """
        import re

        # Try to extract from ```json ... ``` block
        json_pattern = r'```json\s*\n(.*?)\n```'
        match = re.search(json_pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to extract from ``` ... ``` block (no language specified)
        code_pattern = r'```\s*\n(.*?)\n```'
        match = re.search(code_pattern, content, re.DOTALL)
        if match:
            potential_json = match.group(1).strip()
            # Validate it looks like JSON
            if potential_json.startswith('{') and potential_json.endswith('}'):
                return potential_json

        # Try to find JSON object in plain text (look for { ... })
        json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        match = re.search(json_obj_pattern, content, re.DOTALL)
        if match:
            potential_json = match.group(0).strip()
            # Simple validation: must have at least one key-value pair
            if '"' in potential_json and ':' in potential_json:
                return potential_json

        return None

    def _parse_response(self, content: str, candidates: List[Dict[str, Any]]) -> ClassificationResult:
        # Try to parse JSON directly first
        try:
            data = json.loads(content.strip())
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_content = self._extract_json_from_markdown(content)

            if json_content:
                try:
                    data = json.loads(json_content)
                    logger.info("Successfully parsed JSON from markdown code block")
                except json.JSONDecodeError as e:
                    logger.warning(f"Extracted markdown JSON still invalid: {e}")
                    data = None
            else:
                data = None

            # If still no valid JSON, fall back to first candidate
            if data is None:
                logger.error(f"Failed to parse LLM response. Content preview: {content[:200]}")
                best = candidates[0]
                family = extract_family_code(best.get("code"))
                return ClassificationResult(
                    sat_account_code=best.get("code"),
                    family_code=family,
                    confidence_sat=float(best.get("score", 0.4)),
                    confidence_family=float(best.get("score", 0.4)),
                    explanation_short="Fallo al parsear JSON",
                    explanation_detail="El LLM devolvió un formato inválido; se eligió el candidato con mayor score.",
                    alternative_candidates=self._build_alternative_candidates(candidates, best.get("code")),
                )

        # Validate with Pydantic model
        try:
            validated_response = SATClassificationResponse(**data)
            logger.debug(f"Pydantic validation passed for SAT classification")
        except ValidationError as e:
            logger.error(f"Pydantic validation failed: {e}\nResponse data: {data}")
            # Fall back to first candidate on validation failure
            best = candidates[0]
            family = extract_family_code(best.get("code"))
            return ClassificationResult(
                sat_account_code=best.get("code"),
                family_code=family,
                confidence_sat=float(best.get("score", 0.4)),
                confidence_family=float(best.get("score", 0.4)),
                explanation_short="Validación fallida",
                explanation_detail=f"El LLM devolvió datos inválidos: {str(e)[:100]}. Se eligió el candidato con mayor score.",
                alternative_candidates=self._build_alternative_candidates(candidates, best.get("code")),
            )

        # Use validated data
        return ClassificationResult(
            sat_account_code=validated_response.sat_account_code,
            family_code=validated_response.family_code,
            confidence_sat=validated_response.confidence_sat,
            confidence_family=validated_response.confidence_family,
            explanation_short=validated_response.explanation_short,
            explanation_detail=validated_response.explanation_detail,
            model_version=self.model,
            prompt_version=self.prompt_version,
            alternative_candidates=self._build_alternative_candidates(candidates, validated_response.sat_account_code),
        )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)
