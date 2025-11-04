"""Utility helpers to analyse company context and persist semantic memory."""

from __future__ import annotations

import json
import logging
import argparse
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from config.config import config
from core.ai.claude_context_analyzer import (
    ClaudeContextAnalyzerError,
    analyze_context_with_claude,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    """Return the unified database path from configuration."""
    return Path(config.UNIFIED_DB_PATH)


@contextmanager
def _get_connection() -> Iterable[sqlite3.Connection]:
    """Yield a SQLite connection with sensible defaults."""
    db_path = _get_db_path()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------

def _hash_based_embedding(text: str, length: int = 8) -> List[float]:
    """Generate a deterministic pseudo embedding from text."""
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vector: List[float] = []
    for idx in range(length):
        start = (idx * 4) % len(digest)
        chunk = digest[start : start + 4]
        value = int.from_bytes(chunk, "big") / 0xFFFFFFFF
        vector.append(round(value, 6))
    return vector


def _basic_topics(text: str, max_topics: int = 5) -> List[str]:
    """Extract naive keyword list from the supplied context."""
    import re

    words = re.findall(r"[a-záéíóúñA-ZÁÉÍÓÚÑ0-9]+", text.lower())
    stopwords = {
        "para",
        "como",
        "sobre",
        "este",
        "esta",
        "con",
        "los",
        "las",
        "del",
        "sus",
        "que",
        "nos",
        "empresa",
        "negocio",
        "venta",
        "ventas",
        "produccion",
        "producción",
    }
    keywords: List[str] = []
    for word in words:
        if len(word) < 4:
            continue
        if word in stopwords:
            continue
        if word not in keywords:
            keywords.append(word)
        if len(keywords) == max_topics:
            break
    return keywords or ["contexto", "empresa"]


def _call_stub_model(context_text: str) -> Dict[str, Any]:
    """Fallback analyser when external providers are disabled."""
    summary = context_text.strip().split(".")[0]
    summary = summary[:280] if summary else "Contexto empresarial no disponible."
    topics = _basic_topics(context_text)
    embedding = _hash_based_embedding(context_text)
    business_profile = {
        "industry": "desconocido",
        "products_services": topics[:3],
        "clients": [],
        "suppliers": [],
        "channels": [],
        "operation_frequency": None,
        "company_size": None,
        "business_model": None,
    }
    confidence = round(min(0.95, 0.65 + len(context_text) / 1000.0), 3)
    return {
        "summary": summary,
        "topics": topics,
        "confidence": confidence,
        "embedding_vector": embedding,
        "business_profile": business_profile,
        "model_name": "stub-context-analyzer",
        "language_detected": "es",
    }


def _analyse_with_ai(context_text: str, preference: Optional[str] = None) -> Dict[str, Any]:
    """Analyse the context using Claude when available, otherwise fallback to stub."""
    provider = (preference or os.getenv("CONTEXT_AI_PROVIDER", "claude")).lower()

    if provider == "stub":
        return _call_stub_model(context_text)

    try:
        result = analyze_context_with_claude(context_text)
        result.setdefault("model_name", os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"))
        return result
    except (ClaudeContextAnalyzerError, ValueError) as exc:
        logger.warning("Claude context analysis unavailable: %s", exc)
    except Exception as exc:  # pragma: no cover - protective fallback
        logger.exception("Unexpected error during Claude analysis: %s", exc)

    logger.info("Falling back to stub analyser for company context.")
    return _call_stub_model(context_text)


# ---------------------------------------------------------------------------
# Public helpers for context retrieval
# ---------------------------------------------------------------------------


def get_company_id_for_tenant(tenant_id: int) -> Optional[int]:
    """Resolve the primary company id associated with a tenant."""
    if tenant_id is None:
        return None

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM companies
            WHERE tenant_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()

    return int(row["id"]) if row else None


def get_latest_context_for_company(company_id: int) -> Optional[Dict[str, Any]]:
    """Fetch the most recent contextual summary for the given company."""
    if company_id is None:
        return None

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                summary,
                onboarding_snapshot,
                topics,
                context_version,
                confidence_score,
                model_name,
                created_at
            FROM ai_context_memory
            WHERE company_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 1
            """,
            (company_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    business_profile_raw = row["onboarding_snapshot"]
    business_profile: Optional[Any]
    if business_profile_raw:
        try:
            business_profile = json.loads(business_profile_raw)
        except (TypeError, json.JSONDecodeError):
            business_profile = business_profile_raw
    else:
        business_profile = None

    try:
        topics_raw = row["topics"]
    except (KeyError, IndexError, TypeError):
        topics_raw = None
    parsed_topics: List[Any] = []
    if topics_raw:
        try:
            parsed_topics = json.loads(topics_raw)
            if not isinstance(parsed_topics, list):
                parsed_topics = [parsed_topics]
        except (TypeError, json.JSONDecodeError):
            parsed_topics = [topics_raw]

    return {
        "summary": row["summary"],
        "business_profile": business_profile,
        "topics": parsed_topics,
        "context_version": row["context_version"],
        "confidence_score": row["confidence_score"],
        "model_name": row["model_name"],
        "created_at": row["created_at"],
        "company_id": company_id,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_and_store_context(
    company_id: int,
    context_text: str,
    source: str = "onboarding",
    *,
    created_by: Optional[int] = None,
    context_version: int = 1,
    preference: Optional[str] = None,
    dedupe_today: bool = True,
) -> Dict[str, Any]:
    """Generate semantic context and persist it into ai_context_memory.

    Args:
        company_id: Target company identifier.
        context_text: Raw textual context gathered from onboarding.
        source: Origin descriptor (e.g. "voice", "text", "onboarding").
        created_by: Optional user ID responsible for the action.
        context_version: Version tracker for the onboarding context.
        preference: Force a specific provider ("gemini", "claude", "stub").
        dedupe_today: Remove same-day entries before inserting.

    Returns:
        Dictionary with the stored record fields.
    """

    if not context_text or not context_text.strip():
        raise ValueError("context_text must contain meaningful content")

    analysis = _analyse_with_ai(context_text.strip(), preference)

    topics = analysis.get("topics") or []
    if not isinstance(topics, list):
        topics = [str(topics)]

    embedding_vector = analysis.get("embedding_vector") or _hash_based_embedding(context_text)
    if not isinstance(embedding_vector, list):
        raise ValueError("embedding_vector must be a list of floats")

    summary = analysis.get("summary", "")
    business_profile = analysis.get("business_profile") or {}
    confidence = analysis.get("confidence") or analysis.get("confidence_score") or 0.0
    model_name = analysis.get("model_name", os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"))
    language = analysis.get("language_detected", "unknown")

    with _get_connection() as conn:
        cursor = conn.cursor()

        if dedupe_today:
            cursor.execute(
                "DELETE FROM ai_context_memory WHERE company_id = ? AND DATE(created_at) = DATE('now')",
                (company_id,),
            )

        cursor.execute(
            """
            INSERT INTO ai_context_memory (
                company_id,
                created_by,
                context,
                embedding_vector,
                model_name,
                source,
                language_detected,
                context_version,
                summary,
                topics,
                confidence_score,
                onboarding_snapshot,
                last_refresh,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                company_id,
                created_by,
                context_text,
                json.dumps(embedding_vector),
                model_name,
                source,
                language,
                context_version,
                summary,
                json.dumps(topics, ensure_ascii=False),
                confidence,
                json.dumps(business_profile, ensure_ascii=False) if business_profile else None,
            ),
        )
        record_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO audit_trail (entidad, entidad_id, accion, usuario_id, cambios)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "ai_context_memory",
                record_id,
                "insert",
                created_by,
                json.dumps({"company_id": company_id, "source": source, "model": model_name}),
            ),
        )

        cursor.execute(
            "SELECT * FROM ai_context_memory WHERE id = ?",
            (record_id,),
        )
        row = cursor.fetchone()

    result = dict(row) if row else {
        "id": record_id,
        "company_id": company_id,
        "summary": summary,
        "topics": json.dumps(topics, ensure_ascii=False),
        "confidence_score": confidence,
        "model_name": model_name,
        "language_detected": language,
    }
    result["topics"] = json.loads(result.get("topics") or "[]")
    result["embedding_vector"] = json.loads(result.get("embedding_vector") or "[]")
    result["confidence_score"] = float(result.get("confidence_score") or 0.0)
    if result.get("onboarding_snapshot"):
        try:
            result["business_profile"] = json.loads(result["onboarding_snapshot"])
        except json.JSONDecodeError:
            result["business_profile"] = None
    else:
        result["business_profile"] = business_profile or None

    logger.info(
        "Stored AI context memory for company %s (id=%s, model=%s)",
        company_id,
        result.get("id"),
        model_name,
    )
    return result


def _run_cli(args: List[str]) -> None:
    parser = argparse.ArgumentParser(description="Test Claude context analysis and storage")
    parser.add_argument("--test_claude", metavar="TEXT", help="Context text to analyse", required=False)
    parser.add_argument("--company_id", type=int, default=1, help="Company ID to use for storage")
    parser.add_argument("--source", default="cli", help="Source label for the stored context")
    parsed = parser.parse_args(args)

    if not parsed.test_claude:
        parser.print_help()
        return

    stored = analyze_and_store_context(
        parsed.company_id,
        parsed.test_claude,
        source=parsed.source,
        created_by=None,
        preference="claude",
    )
    print(json.dumps(stored, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _run_cli(os.sys.argv[1:])
