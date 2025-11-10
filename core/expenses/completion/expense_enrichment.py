"""
Utilities to enrich manual expenses using the existing LLM classification pipeline.
Transforms an expense payload into a richer structure (descripcion_contable,
categoría, SAT code, proveedor, etc.) reusing TicketAnalyzer prompts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from core.ticket_analyzer import TicketAnalyzer, TicketAnalysis
from core.accounting.account_catalog import retrieve_relevant_accounts, get_context_snippets

logger = logging.getLogger(__name__)


def _prepare_company_context_payload(company_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize company context before sending to the LLM."""
    if not company_context:
        return {}

    safe_context: Dict[str, Any] = {}
    for key, value in company_context.items():
        if value is None:
            continue
        # Convert complex objects to JSON friendly structures
        if isinstance(value, (dict, list, tuple)):
            try:
                safe_context[key] = json.loads(json.dumps(value, ensure_ascii=False, default=str))
            except Exception:  # pragma: no cover - defensive
                safe_context[key] = str(value)
        else:
            safe_context[key] = value

    return safe_context


def _dataclass_to_clean_dict(analysis: TicketAnalysis) -> Dict[str, Any]:
    """Convert TicketAnalysis dataclass into a JSON-friendly dict."""
    data = asdict(analysis)

    # Ensure there's always a raw_analysis object we can append metadata to
    raw_analysis = data.get("raw_analysis") or {}
    if not isinstance(raw_analysis, dict):
        raw_analysis = {"value": raw_analysis}
    raw_analysis.setdefault("source", "manual_expense_enrichment")
    if analysis.model_used:
        raw_analysis.setdefault("model_used", analysis.model_used)
    data["raw_analysis"] = raw_analysis
    data.setdefault("analysis_origin", "manual_expense_enrichment")

    # Remove keys with None to keep metadata concise
    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        cleaned[key] = value

    return cleaned


async def enrich_expense_with_llm(
    expense_payload: Dict[str, Any],
    company_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Enrich a manual expense using the LLM pipeline (same as ticket OCR flow).

    Args:
        expense_payload: Dict with the fields captured manually.
        company_context: Optional contextual information about the tenant/company.

    Returns:
        Dict with enriched metadata (descripcion_contable, categorias, SAT code, etc.)
        or None when enrichment is not possible.
    """
    analyzer = TicketAnalyzer()

    if not (analyzer.claude_client or analyzer.openai_client):
        logger.debug("Skipping expense enrichment: no LLM clients configured")
        return None

    safe_company_context = _prepare_company_context_payload(company_context)

    suggestions = retrieve_relevant_accounts(expense_payload)
    if suggestions:
        codes = [item.get("code") for item in suggestions if item.get("code")]
        context_snippets = get_context_snippets(codes, limit=5)
        for suggestion in suggestions:
            code = suggestion.get("code")
            if code and code in context_snippets:
                snippet = context_snippets[code]
                # keep snippet concise for the prompt
                if len(snippet) > 320:
                    snippet = f"{snippet[:320].rstrip()}…"
                suggestion["context"] = snippet

    try:
        analysis: TicketAnalysis = await analyzer.analyze_manual_expense(
            expense_payload,
            company_context=safe_company_context,
            suggested_accounts=suggestions,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Manual expense enrichment failed: %s", exc)
        return None

    enrichment = _dataclass_to_clean_dict(analysis)
    if suggestions:
        enrichment.setdefault("candidate_accounts", suggestions)
    return enrichment
