"""LLM-assisted SAT classification helper."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.text_normalizer import normalize_expense_text
from core.sat_utils import extract_family_code

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

    def __init__(self, model: str = "claude-3-haiku-20240307") -> None:
        self.model = MODEL_VERSION or model
        self.prompt_version = PROMPT_VERSION
        self._client = None
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic and api_key:
            self._client = anthropic.Anthropic(api_key=api_key)

    def classify(self, snapshot: Dict[str, Any], candidates: List[Dict[str, Any]]) -> ClassificationResult:
        if not candidates:
            return ClassificationResult(
                sat_account_code=None,
                family_code=None,
                confidence_sat=0.0,
                confidence_family=0.0,
                explanation_short="Sin candidatos",
                explanation_detail="No se encontraron cuentas SAT relevantes en la búsqueda inicial.",
            )

        if not self._client:
            # Fallback: choose top candidate
            best = candidates[0]
            family = extract_family_code(best.get("code"))
            return ClassificationResult(
                sat_account_code=best.get("code"),
                family_code=family,
                confidence_sat=float(best.get("score", 0.5)),
                confidence_family=float(best.get("score", 0.5)),
                explanation_short="Selección heurística",
                explanation_detail="Se eligió el candidato con mayor similitud ante la ausencia de LLM.",
            )

        prompt = self._build_prompt(snapshot, candidates)
        response = self._client.messages.create(
            model=self.model,
            max_tokens=400,
            temperature=0.2,
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

        return self._parse_response(content, candidates)

    def _build_prompt(self, snapshot: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
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
        }

        company_context = snapshot.get("company_context")
        if company_context:
            features["company_context"] = company_context

        slim_snapshot = {k: v for k, v in features.items() if v not in (None, "", [], {})}

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

        company_context = features.pop("company_context", None)
        company_block = ""
        if company_context:
            company_block = (
                "CONTEXTO EMPRESA:\n"
                f"{json.dumps(company_context, ensure_ascii=False, indent=2)}\n\n"
            )

        prompt = (
            "A continuación se presentan los datos de un gasto y un conjunto de cuentas candidatas del catálogo SAT.\n"
            "Analiza la intención del gasto y selecciona la cuenta SAT más adecuada. Si hay duda entre varias "
            "opciones, elige la que cumpla mejor con la normativa fiscal mexicana.\n\n"
            f"{company_block}"
            f"DETALLES DEL GASTO:\n{json.dumps(slim_snapshot, ensure_ascii=False, indent=2)}\n\n"
            f"CANDIDATOS:\n{candidate_block}\n\n"
            "Devuelve exclusivamente un objeto JSON con las claves pedidas."
        )
        return prompt

    def _parse_response(self, content: str, candidates: List[Dict[str, Any]]) -> ClassificationResult:
        try:
            data = json.loads(content.strip())
        except json.JSONDecodeError:
            best = candidates[0]
            family = extract_family_code(best.get("code"))
            return ClassificationResult(
                sat_account_code=best.get("code"),
                family_code=family,
                confidence_sat=float(best.get("score", 0.4)),
                confidence_family=float(best.get("score", 0.4)),
                explanation_short="Fallo al parsear JSON",
                explanation_detail="El LLM devolvió un formato inválido; se eligió el candidato con mayor score.",
            )

        sat_code = data.get("sat_account_code")
        family_code = data.get("family_code") or extract_family_code(sat_code)
        confidence_sat = _safe_float(data.get("confidence_sat"), default=0.7)
        confidence_family = _safe_float(data.get("confidence_family"), default=confidence_sat)
        explanation_short = _safe_str(data.get("explanation_short")) or "Clasificación automática"
        explanation_detail = _safe_str(data.get("explanation_detail")) or explanation_short

        return ClassificationResult(
            sat_account_code=sat_code,
            family_code=family_code,
            confidence_sat=confidence_sat,
            confidence_family=confidence_family,
            explanation_short=explanation_short,
            explanation_detail=explanation_detail,
            model_version=self.model,
            prompt_version=self.prompt_version,
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
