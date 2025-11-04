"""Fiscal classification helpers.

Integra reglas de proveedor, catálogo SAT y CFDI con trazabilidad.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:  # Optional dependency for configurable fallbacks
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore

from core.accounting_catalog import (
    ACCOUNTING_CATEGORY_CATALOG,
    AccountingCategory,
)
from core.account_catalog import get_context_snippets, retrieve_relevant_accounts
from config.config import config
from core.sat_catalog_seed import CATEGORY_SAT_MAPPING
from core.text_normalizer import normalize_expense_text
from core.expense_features import build_expense_feature_snapshot
from core.expense_llm_classifier import ClassificationResult, ExpenseLLMClassifier
from core.sat_utils import extract_family_code
from core.classification_trace import record_classification_trace
from core.tenant_policies import get_policies, verify_family_preference
try:
    from core.ai.ai_context_memory_service import fetch_company_context
except ImportError:  # pragma: no cover - optional dependency
    fetch_company_context = None  # type: ignore

logger = logging.getLogger(__name__)

PredictionWriter = Callable[[sqlite3.Connection, int, int, str, float, str], None]
LLMClassifier = Callable[[Dict[str, str]], Dict[str, str]]

ACCOUNTING_MAPPINGS_PATH = Path(__file__).resolve().parent / "accounting_mappings.yaml"
GENERIC_SAT_PREFIXES = ("601", "602", "603", "604")

_DEFAULT_EXPENSE_CLASSIFIER: Optional[ExpenseLLMClassifier] = None


@lru_cache(maxsize=1)
def _load_accounting_mappings() -> List[Dict[str, Any]]:
    if not ACCOUNTING_MAPPINGS_PATH.exists():
        return []
    if yaml is None:
        logger.warning("PyYAML not installed; skipping accounting mappings overrides.")
        return []
    try:
        with ACCOUNTING_MAPPINGS_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or []
        if isinstance(data, list):
            return data
        logger.warning("Accounting mappings file is not a list; ignoring overrides.")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to read accounting mappings: %s", exc)
    return []


def _should_apply_fallback(sat_code: Optional[str]) -> bool:
    if not sat_code:
        return True
    normalized = sat_code.strip()
    for prefix in GENERIC_SAT_PREFIXES:
        if normalized == prefix or normalized.startswith(f"{prefix}."):
            return True
    return False


def _resolve_fallback_sat_code(llm_result: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    candidates: List[str] = []
    for key in ("categoria_contable", "categoria_semantica", "category"):
        value = llm_result.get(key)
        if value:
            normalized = normalize_expense_text(str(value))
            if normalized:
                candidates.append(normalized)

    if not candidates:
        return None, None

    for rule in _load_accounting_mappings():
        match_section = rule.get("match", {})
        categories = match_section.get("categoria_contable", [])
        normalized_targets = {normalize_expense_text(str(item)) for item in categories if item}
        if not normalized_targets:
            continue
        if any(candidate in normalized_targets for candidate in candidates):
            forced_code = rule.get("force_sat_account")
            if forced_code:
                rule_name = rule.get("name") or forced_code
                return str(forced_code), str(rule_name)
    return None, None


def _get_default_expense_classifier() -> ExpenseLLMClassifier:
    global _DEFAULT_EXPENSE_CLASSIFIER
    if _DEFAULT_EXPENSE_CLASSIFIER is None:
        _DEFAULT_EXPENSE_CLASSIFIER = ExpenseLLMClassifier()
    return _DEFAULT_EXPENSE_CLASSIFIER


def _fetch_expense_record(conn: sqlite3.Connection, expense_id: int, tenant_id: int) -> Dict[str, Any]:
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT *
                  FROM expense_records
                 WHERE id = ? AND tenant_id = ?
            """,
            (expense_id, tenant_id),
        )
        row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unable to fetch expense %s for tenant %s: %s", expense_id, tenant_id, exc)
        return {}
    if row is None:
        return {}

    if hasattr(row, "keys"):
        record = {key: row[key] for key in row.keys()}
    else:
        columns = [desc[0] for desc in cursor.description]
        record = {col: row[idx] for idx, col in enumerate(columns)}

    metadata = record.get("metadata")
    if isinstance(metadata, str):
        try:
            record["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            record["metadata"] = {}
    elif metadata is None:
        record["metadata"] = {}
    return record


def _build_expense_payload(expense_record: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    metadata = expense_record.get("metadata") if isinstance(expense_record.get("metadata"), dict) else {}
    payload = {
        "descripcion": snapshot.get("descripcion_original")
        or expense_record.get("descripcion")
        or expense_record.get("description"),
        "categoria": snapshot.get("categoria_usuario") or expense_record.get("categoria"),
        "categoria_semantica": snapshot.get("categoria_slug") or expense_record.get("categoria_semantica"),
        "categoria_contable": snapshot.get("categoria_contable"),
        "notas": expense_record.get("notas"),
        "comentarios": expense_record.get("comentarios"),
        "metadata": metadata,
    }
    return payload


def _derive_family_candidates(snapshot: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[str]:
    families: List[str] = []

    existing = snapshot.get("existing_sat_account_code")
    if existing:
        fam = extract_family_code(existing)
        if fam and fam not in families:
            families.append(fam)

    metadata = snapshot.get("metadata") or {}
    if isinstance(metadata, dict):
        llm_meta = metadata.get("llm_analysis") or {}
        if isinstance(llm_meta, dict):
            prev_code = llm_meta.get("sat_account_code")
            fam = extract_family_code(prev_code)
            if fam and fam not in families:
                families.append(fam)

    mapping_slug = snapshot.get("categoria_slug")
    if mapping_slug and mapping_slug in CATEGORY_SAT_MAPPING:
        mapping = CATEGORY_SAT_MAPPING[mapping_slug]
        fam = extract_family_code(mapping.get("sat_account_code"))
        if fam and fam not in families:
            families.append(fam)

    for candidate in candidates:
        fam = candidate.get("family_hint") or extract_family_code(candidate.get("code"))
        if fam and fam not in families:
            families.append(fam)
        if len(families) >= 3:
            break

    return families


def _normalize_provider_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return " ".join(name.strip().lower().split())


def _clamp_confidence(value: Optional[float]) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _build_company_context(expense_record: Dict[str, Any], tenant_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve persisted company context (if available) for enrichment."""
    if not fetch_company_context:  # pragma: no cover - optional dependency missing
        return None

    company_id = expense_record.get("company_id") or expense_record.get("tenant_id") or tenant_id

    try:
        context = fetch_company_context(company_id)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug(
            "Unable to fetch company context for tenant %s company %s: %s",
            tenant_id,
            company_id,
            exc,
        )
        return None

    if not context:
        return None

    filtered: Dict[str, Any] = {
        "company_id": company_id,
        "tenant_id": tenant_id,
        "summary": context.get("summary"),
        "topics": context.get("topics") or [],
        "confidence_score": context.get("confidence_score"),
        "model_name": context.get("model_name"),
        "context_version": context.get("context_version"),
        "created_at": context.get("created_at"),
    }

    business_profile = context.get("business_profile")
    if business_profile:
        filtered["business_profile"] = business_profile

    return filtered


def _log_model_config(conn: sqlite3.Connection, model_version: Optional[str], prompt_version: Optional[str]) -> None:
    """Persist the model/prompt combo used for audit purposes."""
    if not model_version and not prompt_version:
        return

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS model_config_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_version TEXT,
                prompt_version TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO model_config_history (model_version, prompt_version)
            VALUES (?, ?)
            """,
            (model_version, prompt_version),
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Unable to log model configuration: %s", exc)


def _enqueue_manual_review(conn: sqlite3.Connection, expense_id: int, tenant_id: int, reason: Optional[str]) -> None:
    """Store expenses that need human review."""
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS manual_review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL UNIQUE,
                tenant_id INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO manual_review_queue (expense_id, tenant_id, reason)
            VALUES (?, ?, ?)
            ON CONFLICT(expense_id) DO UPDATE SET
                reason = excluded.reason,
                created_at = CURRENT_TIMESTAMP,
                resolved_at = NULL,
                resolved_by = NULL
            """,
            (expense_id, tenant_id, reason),
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Unable to enqueue manual review for expense %s: %s", expense_id, exc)


def _verify_account_choice(tenant_id: int, family_code: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Run semantic validation against tenant policies."""
    needs_review, reason = verify_family_preference(tenant_id, family_code)
    return needs_review, reason


def lookup_provider_rule(
    conn: sqlite3.Connection,
    tenant_id: int,
    provider_name: Optional[str],
) -> Optional[sqlite3.Row]:
    """Busca una regla de proveedor normalizando el nombre."""

    normalized = _normalize_provider_name(provider_name)
    if not normalized:
        return None

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
          FROM provider_rules
         WHERE tenant_id = ?
           AND provider_name_normalized = ?
         ORDER BY confidence DESC, last_confirmed_at DESC
         LIMIT 1
        """,
        (tenant_id, normalized),
    )
    rule = cursor.fetchone()
    if rule:
        logger.info("🔎 Regla de proveedor encontrada: %s", normalized)
    else:
        logger.info("ℹ️ Sin regla de proveedor para: %s", normalized)
    return rule


def _find_catalog_category(text: str) -> Optional[AccountingCategory]:
    text_normalized = text.lower()
    for category in ACCOUNTING_CATEGORY_CATALOG:
        for synonym in category.sinonimos:
            if synonym.lower() in text_normalized:
                return category
    return None


def _apply_classification_updates(
    conn: sqlite3.Connection,
    expense_id: int,
    tenant_id: int,
    slug: Optional[str],
    sat_account_code: Optional[str],
    sat_product_service_code: Optional[str],
    tax_source: str,
    classification_source: str,
    explanation_short: str,
    explanation_detail: str,
    confidence: float,
    needs_review: bool,
) -> None:
    """Actualiza expense_records y deja rastro en category_prediction_history."""

    category_name = None
    category_conf = confidence
    categoria_fuente = classification_source

    if slug:
        mapping = CATEGORY_SAT_MAPPING.get(slug, {})
        sat_account_code = sat_account_code or mapping.get("sat_account_code")
        sat_product_service_code = sat_product_service_code or mapping.get(
            "sat_product_service_code"
        )
        category_obj = next(
            (cat for cat in ACCOUNTING_CATEGORY_CATALOG if cat.slug == slug), None
        )
        if category_obj:
            category_name = category_obj.nombre

    conn.execute(
        """
        UPDATE expense_records
           SET categoria = COALESCE(?, categoria),
               categoria_slug = COALESCE(?, categoria_slug),
               categoria_confianza = ?,
               categoria_fuente = ?,
               sat_account_code = COALESCE(?, sat_account_code),
               sat_product_service_code = COALESCE(?, sat_product_service_code),
               tax_source = ?,
               catalog_version = COALESCE(catalog_version, 'v1'),
               classification_source = ?,
               explanation_short = ?,
               explanation_detail = ?,
               needs_reclassification = ?,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ? AND tenant_id = ?
        """,
        (
            category_name,
            slug,
            category_conf,
            categoria_fuente,
            sat_account_code,
            sat_product_service_code,
            tax_source,
            classification_source,
            explanation_short,
            explanation_detail,
            1 if needs_review else 0,
            expense_id,
            tenant_id,
        ),
    )

    conn.execute(
        """
        INSERT INTO category_prediction_history (
            expense_id,
            predicted_category,
            confidence,
            reasoning,
            prediction_method,
            ml_model_version,
            tenant_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            expense_id,
            slug or "unknown",
            confidence,
            explanation_detail,
            tax_source,
            "fiscal_pipeline_v1",
            tenant_id,
        ),
    )


def classify_expense_fiscal(
    conn: sqlite3.Connection,
    expense_id: int,
    tenant_id: int,
    descripcion: str,
    proveedor: Optional[str],
    monto: float,
    llm_classifier: Optional[Any] = None,
) -> Optional[Dict[str, object]]:
    """Clasifica fiscalmente un gasto siguiendo reglas → catálogo → LLM."""

    texto_base = " ".join(filter(None, [descripcion or "", proveedor or ""]))

    provider_rule = lookup_provider_rule(conn, tenant_id, proveedor)
    provider_rule_suggestion: Optional[Dict[str, Any]] = None
    if provider_rule:
        provider_rule_suggestion = {
            "sat_account_code": provider_rule["sat_account_code"],
            "category_slug": provider_rule["category_slug"],
            "name": provider_rule["category_slug"],
            "confidence": float(provider_rule.get("confidence") or 0.9),
            "explanation": f"Regla proveedor {provider_rule['provider_name_normalized']} → {provider_rule['category_slug']}",
            "source": "provider_rule",
        }

    catalog_category = _find_catalog_category(texto_base)
    catalog_suggestion: Optional[Dict[str, Any]] = None
    if catalog_category:
        catalog_suggestion = {
            "sat_account_code": catalog_category.sat_account_code,
            "category_slug": catalog_category.slug,
            "name": catalog_category.nombre,
            "confidence": 0.75,
            "explanation": f"Coincidencia catálogo {catalog_category.slug}",
            "source": "catalog_keyword",
        }

    expense_record = _fetch_expense_record(conn, expense_id, tenant_id)
    if not expense_record:
        expense_record = {
            "descripcion": descripcion,
            "monto_total": monto,
            "proveedor_nombre": proveedor,
            "tenant_id": tenant_id,
            "metadata": {},
        }

    snapshot = build_expense_feature_snapshot(expense_record)
    if provider_rule_suggestion:
        snapshot["provider_rule_suggestion"] = provider_rule_suggestion
    if catalog_suggestion:
        snapshot["catalog_suggestion"] = catalog_suggestion
    company_context = _build_company_context(expense_record, tenant_id)
    if company_context:
        snapshot["company_context"] = company_context
    policies = get_policies(tenant_id)
    if policies:
        snapshot.setdefault("company_context", {}).setdefault("policies", policies)
    if not snapshot.get("descripcion_original"):
        snapshot["descripcion_original"] = descripcion
        snapshot["descripcion_normalizada"] = normalize_expense_text(descripcion)

    expense_payload = _build_expense_payload(expense_record, snapshot)
    candidate_pool: List[Dict[str, Any]] = []

    def add_candidate(candidate: Dict[str, Any]) -> None:
        code = candidate.get("code")
        if not code:
            return
        for existing in candidate_pool:
            if existing.get("code") == code:
                return
        candidate_pool.append(candidate)

    if provider_rule_suggestion:
        add_candidate(
            {
                "code": provider_rule_suggestion["sat_account_code"],
                "name": provider_rule_suggestion.get("name") or provider_rule_suggestion["sat_account_code"],
                "description": provider_rule_suggestion.get("explanation"),
                "score": _clamp_confidence(provider_rule_suggestion.get("confidence")) or 1.0,
                "family_hint": extract_family_code(provider_rule_suggestion["sat_account_code"]) or "",
                "context": provider_rule_suggestion.get("explanation"),
            }
        )

    if catalog_suggestion:
        add_candidate(
            {
                "code": catalog_suggestion["sat_account_code"],
                "name": catalog_suggestion.get("name") or catalog_suggestion["sat_account_code"],
                "description": catalog_suggestion.get("explanation"),
                "score": _clamp_confidence(catalog_suggestion.get("confidence")) or 0.75,
                "family_hint": extract_family_code(catalog_suggestion["sat_account_code"]) or "",
                "context": catalog_suggestion.get("explanation"),
            }
        )

    initial_candidates = retrieve_relevant_accounts(expense_payload, top_k=12)
    for candidate in initial_candidates:
        add_candidate(candidate)

    family_candidates = _derive_family_candidates(snapshot, candidate_pool)
    refined = retrieve_relevant_accounts(
        expense_payload,
        top_k=6,
        family_filter=family_candidates or None,
    )
    for candidate in refined:
        add_candidate(candidate)

    if not candidate_pool:
        logger.info("Sin candidatos SAT para gasto %s", expense_id)
        if provider_rule_suggestion:
            candidate_pool.append(
                {
                    "code": provider_rule_suggestion["sat_account_code"],
                    "name": provider_rule_suggestion.get("name") or provider_rule_suggestion["sat_account_code"],
                    "description": provider_rule_suggestion.get("explanation"),
                    "score": _clamp_confidence(provider_rule_suggestion.get("confidence")) or 1.0,
                    "family_hint": extract_family_code(provider_rule_suggestion["sat_account_code"]) or "",
                }
            )
        elif catalog_suggestion:
            candidate_pool.append(
                {
                    "code": catalog_suggestion["sat_account_code"],
                    "name": catalog_suggestion.get("name") or catalog_suggestion["sat_account_code"],
                    "description": catalog_suggestion.get("explanation"),
                    "score": catalog_suggestion.get("confidence", 0.75),
                    "family_hint": extract_family_code(catalog_suggestion["sat_account_code"]) or "",
                }
            )
        else:
            return None

    candidate_pool = candidate_pool[:6]

    context_snippets = get_context_snippets([cand["code"] for cand in candidate_pool], limit=6)
    for candidate in candidate_pool:
        candidate["context"] = context_snippets.get(candidate["code"]) or candidate.get("context")

    classifier_obj = _get_default_expense_classifier()
    if llm_classifier and hasattr(llm_classifier, "classify"):
        classifier_obj = llm_classifier  # type: ignore[assignment]

    result: Optional[ClassificationResult] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    try:
        result = classifier_obj.classify(snapshot, candidate_pool)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Clasificación IA fallida para gasto %s: %s", expense_id, exc)
        result = None

    if result and result.sat_account_code:
        sat_code = result.sat_account_code
        family_code = result.family_code or extract_family_code(sat_code)
        explanation_short = result.explanation_short or "Clasificación automática IA"
        explanation_detail = result.explanation_detail or explanation_short
        confidence = _clamp_confidence(result.confidence_sat)
        classification_source = "llm_hybrid"
        model_version = result.model_version or getattr(classifier_obj, "model", None)
        prompt_version = result.prompt_version or getattr(classifier_obj, "prompt_version", None)
    else:
        fallback = None
        if provider_rule_suggestion:
            fallback = provider_rule_suggestion
        elif catalog_suggestion:
            fallback = catalog_suggestion
        elif candidate_pool:
            first = candidate_pool[0]
            fallback = {
                "sat_account_code": first.get("code"),
                "category_slug": None,
                "confidence": _clamp_confidence(first.get("score")) or 0.6,
                "explanation": first.get("context") or first.get("description") or "Selección heurística",
                "source": "heuristic",
            }

        if not fallback or not fallback.get("sat_account_code"):
            raise RuntimeError("No se pudo clasificar el gasto y no hay fallback disponible")

        sat_code = fallback["sat_account_code"]
        family_code = extract_family_code(sat_code)
        confidence = _clamp_confidence(fallback.get("confidence"))
        explanation_short = fallback.get("explanation") or "Clasificación heurística"
        explanation_detail = explanation_short
        classification_source = fallback.get("source") or "rule"
        if classification_source != "llm":
            model_version = getattr(classifier_obj, "model", None)
            prompt_version = getattr(classifier_obj, "prompt_version", None)

    tax_source = "llm" if classification_source.startswith("llm") else "rule"
    needs_review, review_reason = _verify_account_choice(tenant_id, family_code)

    _log_model_config(conn, model_version, prompt_version)

    llm_result_map = {
        "sat_account_code": sat_code,
        "category_slug": snapshot.get("categoria_slug"),
        "categoria_contable": snapshot.get("categoria_contable"),
    }

    fallback_rule_name = None
    if _should_apply_fallback(sat_code):
        forced_code, fallback_rule_name = _resolve_fallback_sat_code(llm_result_map)
        if forced_code and forced_code != sat_code:
            sat_code = forced_code
            explanation_detail = f"{explanation_detail} | Regla fallback: {fallback_rule_name} → {forced_code}"
        elif fallback_rule_name:
            explanation_detail = f"{explanation_detail} | Regla validada: {fallback_rule_name}"

    candidate_digest = [
        {
            "code": cand.get("code"),
            "name": cand.get("name"),
            "description": cand.get("description"),
            "score": cand.get("score"),
            "family_hint": cand.get("family_hint"),
            "version_tag": cand.get("version_tag"),
            "context": cand.get("context"),
        }
        for cand in candidate_pool
    ]
    snapshot_summary = {
        "categoria_slug": snapshot.get("categoria_slug"),
        "categoria_usuario": snapshot.get("categoria_usuario"),
        "categoria_contable": snapshot.get("categoria_contable"),
        "amount": snapshot.get("amount"),
        "amount_bucket": snapshot.get("amount_bucket"),
        "provider_name": snapshot.get("provider_name"),
        "provider_rfc": snapshot.get("provider_rfc"),
        "keywords": (snapshot.get("keywords") or [])[:15],
    }
    raw_trace_payload = {
        "llm_result": asdict(result) if result else None,
        "final_sat_account_code": sat_code,
        "fallback_rule": fallback_rule_name,
        "candidates": candidate_digest,
        "snapshot": snapshot_summary,
        "company_context": company_context,
        "provider_rule_suggestion": provider_rule_suggestion,
        "catalog_suggestion": catalog_suggestion,
        "prompt_version": prompt_version,
        "model_version": model_version,
        "verification": {
            "needs_review": needs_review,
            "reason": review_reason,
        },
    }
    embedding_version = None
    if candidate_digest:
        embedding_version = candidate_digest[0].get("version_tag")
    if not embedding_version:
        embedding_version = getattr(config, "SAT_EMBEDDING_VERSION", "") or None

    trace_id: Optional[int] = None
    try:
        trace_id = record_classification_trace(
            conn,
            expense_id=expense_id,
            tenant_id=tenant_id,
            sat_account_code=sat_code,
            family_code=family_code,
            confidence_sat=confidence,
            confidence_family=result.confidence_family if result else confidence,
            explanation_short=explanation_short,
            explanation_detail=explanation_detail,
            tokens=snapshot.get("keywords"),
            model_version=model_version,
            embedding_version=embedding_version,
            raw_payload=raw_trace_payload,
        )
    except Exception as trace_exc:  # pragma: no cover - defensive logging
        logger.debug(
            "Unable to persist classification trace for expense %s tenant %s: %s",
            expense_id,
            tenant_id,
            trace_exc,
        )

    _apply_classification_updates(
        conn,
        expense_id,
        tenant_id,
        snapshot.get("categoria_slug"),
        sat_code,
        None,
        tax_source=tax_source,
        classification_source=classification_source,
        explanation_short=explanation_short,
        explanation_detail=explanation_detail,
        confidence=confidence,
        needs_review=needs_review,
    )
    if needs_review:
        _enqueue_manual_review(conn, expense_id, tenant_id, review_reason)
    conn.commit()

    return {
        "tax_source": tax_source,
        "classification_source": classification_source,
        "confidence": confidence,
        "family_code": family_code,
        "classification_trace_id": trace_id,
    }


def on_cfdi_received(
    conn: sqlite3.Connection,
    tenant_id: int,
    cfdi_data: Dict[str, object],
) -> Optional[int]:
    """Revalida un gasto cuando se recibe CFDI y actualiza códigos SAT."""

    required_keys = {"total", "provider_name", "issue_date"}
    if not required_keys.issubset(cfdi_data):
        raise ValueError("cfdi_data incompleto para on_cfdi_received")

    provider_normalized = _normalize_provider_name(cfdi_data.get("provider_name"))
    issue_date = datetime.fromisoformat(str(cfdi_data["issue_date"]))
    date_from = (issue_date - timedelta(days=3)).isoformat()
    date_to = (issue_date + timedelta(days=3)).isoformat()

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
          FROM expense_records
         WHERE tenant_id = ?
           AND ABS(amount - ?) < 0.05
           AND date BETWEEN ? AND ?
           AND (
                lower(COALESCE(merchant_name, '')) = ?
             OR lower(COALESCE(description, '')) LIKE '%' || ? || '%'
           )
         ORDER BY ABS(amount - ?) ASC
         LIMIT 1
        """,
        (
            tenant_id,
            cfdi_data["total"],
            date_from,
            date_to,
            provider_normalized,
            provider_normalized or "",
            cfdi_data["total"],
        ),
    )
    row = cursor.fetchone()
    if not row:
        logger.info("⚠️ No se encontró gasto coincidente para CFDI %s", cfdi_data)
        return None

    expense_id = row["id"]
    tasa_iva = float(cfdi_data.get("tasa_iva", 0))
    iva_amount = float(cfdi_data.get("iva_amount", 0))
    iva_16 = iva_amount if abs(tasa_iva - 0.16) < 0.001 else 0
    iva_0 = iva_amount if abs(tasa_iva) < 0.001 else 0

    conn.execute(
        """
        UPDATE expense_records
           SET sat_product_service_code = COALESCE(?, sat_product_service_code),
               sat_account_code = COALESCE(?, sat_account_code),
               iva_16 = ?,
               iva_0 = ?,
               cfdi_status = 'confirmed',
               tax_source = 'cfdi',
               catalog_version = COALESCE(catalog_version, 'v1'),
               classification_source = 'cfdi_xml',
               explanation_short = 'Revalidado con CFDI XML',
               explanation_detail = ?,
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ? AND tenant_id = ?
        """,
        (
            cfdi_data.get("sat_product_service_code"),
            cfdi_data.get("sat_account_code"),
            iva_16,
            iva_0,
            f"ClaveProdServ={cfdi_data.get('sat_product_service_code')} | TasaIVA={tasa_iva}",
            expense_id,
            tenant_id,
        ),
    )

    conn.execute(
        """
        INSERT INTO category_prediction_history (
            expense_id,
            predicted_category,
            confidence,
            reasoning,
            prediction_method,
            ml_model_version,
            tenant_id
        ) VALUES (?, ?, ?, ?, 'cfdi', 'fiscal_pipeline_v1', ?)
        """,
        (
            expense_id,
            cfdi_data.get("category_slug", "cfdi"),
            1.0,
            f"CFDI XML {cfdi_data.get('uuid', 'N/A')}",
            tenant_id,
        ),
    )

    conn.commit()
    return expense_id
