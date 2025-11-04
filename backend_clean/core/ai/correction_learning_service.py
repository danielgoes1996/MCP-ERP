"""Local correction memory powered by lightweight embeddings.

This module stores human corrections to AI classifications so that future bank
statement parses can immediately benefit from prior feedback. It uses a
pgvector-compatible schema but gracefully degrades to JSON-stored embeddings
when running on SQLite during local development.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha512
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from config.config import config
from core.bank_statements_models import normalize_description

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses for strongly typed results
# ---------------------------------------------------------------------------


@dataclass
class CorrectionRecord:
    id: int
    company_id: int
    tenant_id: Optional[int]
    user_id: Optional[int]
    original_description: str
    normalized_description: str
    ai_category: Optional[str]
    corrected_category: str
    movement_kind: Optional[str]
    amount: Optional[float]
    model_used: Optional[str]
    notes: Optional[str]
    raw_transaction: Optional[Dict[str, Any]]
    embedding: List[float]
    similarity_hint: Optional[float]
    created_at: str


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _get_db_path() -> Path:
    """Return configured unified DB path."""
    return Path(config.UNIFIED_DB_PATH)


@contextmanager
def _get_connection() -> Iterable[sqlite3.Connection]:
    """Yield SQLite connection with safe defaults."""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_tables() -> None:
    """Create correction tables if they do not exist."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_correction_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                tenant_id INTEGER,
                user_id INTEGER,
                original_description TEXT NOT NULL,
                normalized_description TEXT NOT NULL,
                ai_category TEXT,
                corrected_category TEXT NOT NULL,
                movement_kind TEXT,
                amount REAL,
                model_used TEXT,
                notes TEXT,
                raw_transaction TEXT,
                embedding_json TEXT NOT NULL,
                embedding_dimensions INTEGER NOT NULL,
                similarity_hint REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_correction_company
            ON ai_correction_memory(company_id, created_at DESC)
            """
        )


_ensure_tables()


# ---------------------------------------------------------------------------
# Embedding helpers (hash-based, pgvector compatible)
# ---------------------------------------------------------------------------


def _compute_embedding(text: str, category: Optional[str] = None, dimensions: int = 32) -> List[float]:
    """Generate a deterministic embedding vector from text + category."""

    normalized = (text or "").strip().lower()
    augmented = f"{normalized}|{(category or '').strip().lower()}"
    digest = sha512(augmented.encode("utf-8")).digest()  # 64 bytes

    vector: List[float] = []
    bytes_per_dim = max(1, len(digest) // dimensions)
    for idx in range(dimensions):
        start = idx * bytes_per_dim
        chunk = digest[start : start + bytes_per_dim]
        if not chunk:
            chunk = digest[idx % len(digest) : (idx % len(digest)) + bytes_per_dim]
        integer = int.from_bytes(chunk, "big")
        max_int = (1 << (8 * len(chunk))) - 1 or 1
        value = (integer / max_int) * 2 - 1  # scale to [-1, 1]
        vector.append(round(value, 6))

    return vector


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Public API: store feedback and retrieve similarities
# ---------------------------------------------------------------------------


def store_correction_feedback(
    *,
    company_id: int,
    tenant_id: Optional[int],
    user_id: Optional[int],
    description: str,
    ai_category: Optional[str],
    corrected_category: str,
    movement_kind: Optional[str] = None,
    amount: Optional[float] = None,
    model_used: Optional[str] = None,
    notes: Optional[str] = None,
    raw_transaction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a correction example with its embedding."""

    if not description:
        raise ValueError("description is required for correction feedback")

    normalized = normalize_description(description) or description.strip().lower()
    embedding = _compute_embedding(normalized, corrected_category)
    embedding_json = json.dumps(embedding)

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ai_correction_memory (
                company_id, tenant_id, user_id,
                original_description, normalized_description,
                ai_category, corrected_category, movement_kind,
                amount, model_used, notes, raw_transaction,
                embedding_json, embedding_dimensions, similarity_hint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                tenant_id,
                user_id,
                description.strip(),
                normalized,
                ai_category,
                corrected_category,
                movement_kind,
                amount,
                model_used,
                notes,
                json.dumps(raw_transaction or {}, ensure_ascii=False),
                embedding_json,
                len(embedding),
                None,
            ),
        )
        record_id = cursor.lastrowid

    logger.info(
        "Stored correction feedback id=%s company=%s original='%s' -> category='%s'",
        record_id,
        company_id,
        normalized[:60],
        corrected_category,
    )

    return {
        "id": record_id,
        "embedding_dimensions": len(embedding),
        "normalized_description": normalized,
    }


def _fetch_corrections(company_id: int, limit: int = 250) -> List[CorrectionRecord]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM ai_correction_memory
            WHERE company_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (company_id, limit),
        )
        rows = cursor.fetchall()

    corrections: List[CorrectionRecord] = []
    for row in rows:
        embedding = json.loads(row["embedding_json"] or "[]")
        try:
            raw_txn = json.loads(row["raw_transaction"] or "{}")
        except json.JSONDecodeError:
            raw_txn = {}

        corrections.append(
            CorrectionRecord(
                id=row["id"],
                company_id=row["company_id"],
                tenant_id=row["tenant_id"],
                user_id=row["user_id"],
                original_description=row["original_description"],
                normalized_description=row["normalized_description"],
                ai_category=row["ai_category"],
                corrected_category=row["corrected_category"],
                movement_kind=row["movement_kind"],
                amount=row["amount"],
                model_used=row["model_used"],
                notes=row["notes"],
                raw_transaction=raw_txn,
                embedding=embedding,
                similarity_hint=row["similarity_hint"],
                created_at=row["created_at"],
            )
        )

    return corrections


def find_similar_corrections(
    *,
    company_id: int,
    description: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Return top-k similar corrections for the provided description."""

    if company_id is None or not description:
        return []

    normalized = normalize_description(description) or description.strip().lower()
    query_vector = _compute_embedding(normalized)
    corrections = _fetch_corrections(company_id)

    scored: List[Tuple[float, CorrectionRecord]] = []
    for record in corrections:
        similarity = _cosine_similarity(query_vector, record.embedding)
        scored.append((similarity, record))

    scored.sort(key=lambda item: item[0], reverse=True)

    results: List[Dict[str, Any]] = []
    for similarity, record in scored[:top_k]:
        results.append(
            {
                "id": record.id,
                "similarity": round(float(similarity), 4),
                "corrected_category": record.corrected_category,
                "original_description": record.original_description,
                "notes": record.notes,
                "movement_kind": record.movement_kind,
                "amount": record.amount,
                "created_at": record.created_at,
            }
        )

    return results


def apply_corrections_to_transactions(
    transactions: List[Any],
    company_id: Optional[int],
    *,
    similarity_threshold: float = 0.88,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Mutate transactions in place when a strong correction match exists."""

    if company_id is None or not transactions:
        return []

    corrections = _fetch_corrections(company_id)
    if not corrections:
        return []

    updates: List[Dict[str, Any]] = []

    for txn in transactions:
        description = getattr(txn, "description", None) or ""
        normalized = normalize_description(description) or description.strip().lower()
        if not normalized:
            continue

        query_vector = _compute_embedding(normalized)
        best_similarity = 0.0
        best_record: Optional[CorrectionRecord] = None

        for record in corrections:
            similarity = _cosine_similarity(query_vector, record.embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_record = record

        if not best_record or best_similarity < similarity_threshold:
            continue

        original_category = getattr(txn, "category", None)
        if original_category == best_record.corrected_category:
            continue

        txn.category = best_record.corrected_category
        if best_record.movement_kind:
            try:
                txn.movement_kind = best_record.movement_kind
            except AttributeError:
                pass
        txn.ai_model = f"{getattr(txn, 'ai_model', '')}+local-correction".strip("+")
        txn.confidence = max(0.9, getattr(txn, "confidence", 0.5) + 0.05)

        updates.append(
            {
                "transaction_description": description[:80],
                "original_category": original_category,
                "corrected_category": best_record.corrected_category,
                "similarity": round(float(best_similarity), 4),
                "correction_id": best_record.id,
            }
        )

    return updates


def aggregate_correction_stats(company_id: int) -> Dict[str, Any]:
    """Return simple statistics to expose via API responses."""

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total FROM ai_correction_memory WHERE company_id = ?",
            (company_id,),
        )
        total = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT corrected_category, COUNT(*) as count
            FROM ai_correction_memory
            WHERE company_id = ?
            GROUP BY corrected_category
            ORDER BY count DESC
            LIMIT 10
            """,
            (company_id,),
        )
        top_categories = [
            {"category": row["corrected_category"], "count": row["count"]}
            for row in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT id, original_description, corrected_category, created_at
            FROM ai_correction_memory
            WHERE company_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 5
            """,
            (company_id,),
        )
        recent = [
            {
                "id": row["id"],
                "description": row["original_description"],
                "category": row["corrected_category"],
                "created_at": row["created_at"],
            }
            for row in cursor.fetchall()
        ]

    return {
        "total_corrections": total,
        "top_categories": top_categories,
        "recent_examples": recent,
    }


__all__ = [
    "store_correction_feedback",
    "find_similar_corrections",
    "apply_corrections_to_transactions",
    "aggregate_correction_stats",
]

