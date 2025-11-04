"""Audit trail helpers for expense classification decisions."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, List

logger = logging.getLogger(__name__)

TRACE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS classification_trace (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    sat_account_code TEXT,
    family_code TEXT,
    confidence_sat REAL,
    confidence_family REAL,
    explanation_short TEXT,
    explanation_detail TEXT,
    tokens TEXT,
    model_version TEXT,
    embedding_version TEXT,
    raw_payload TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

TRACE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_classification_trace_expense
    ON classification_trace (expense_id, tenant_id, created_at DESC);
"""


def ensure_trace_table(conn: sqlite3.Connection) -> None:
    """Create audit table/index when absent."""
    conn.execute(TRACE_TABLE_SQL)
    conn.execute(TRACE_INDEX_SQL)
    conn.commit()


def _serialize_json(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:  # pragma: no cover - defensive logging
        logger.debug("Unable to serialize value for classification_trace, storing as string.")
        return str(value)


def record_classification_trace(
    conn: sqlite3.Connection,
    *,
    expense_id: int,
    tenant_id: int,
    sat_account_code: Optional[str],
    family_code: Optional[str],
    confidence_sat: float,
    confidence_family: float,
    explanation_short: str,
    explanation_detail: str,
    tokens: Optional[Iterable[str]] = None,
    model_version: Optional[str] = None,
    embedding_version: Optional[str] = None,
    raw_payload: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Persist a structured audit trace for an expense classification event.

    Returns the inserted row id for linkage with feedback entries.
    """
    ensure_trace_table(conn)

    serialized_tokens = _serialize_json(list(tokens) if tokens is not None else None)
    serialized_payload = _serialize_json(raw_payload)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO classification_trace (
            expense_id,
            tenant_id,
            sat_account_code,
            family_code,
            confidence_sat,
            confidence_family,
            explanation_short,
            explanation_detail,
            tokens,
            model_version,
            embedding_version,
            raw_payload,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            expense_id,
            tenant_id,
            sat_account_code,
            family_code,
            confidence_sat,
            confidence_family,
            explanation_short,
            explanation_detail,
            serialized_tokens,
            model_version,
            embedding_version,
            serialized_payload,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_latest_trace_id(conn: sqlite3.Connection, expense_id: int, tenant_id: int) -> Optional[int]:
    """Return the most recent classification trace id for an expense."""
    ensure_trace_table(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id
          FROM classification_trace
         WHERE expense_id = ? AND tenant_id = ?
         ORDER BY created_at DESC
         LIMIT 1
        """,
        (expense_id, tenant_id),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else None


def fetch_recent_traces(
    conn: sqlite3.Connection,
    tenant_id: int,
    *,
    expense_id: Optional[int] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Return recent classification traces for a tenant (optionally filtered by expense)."""
    ensure_trace_table(conn)
    cursor = conn.cursor()
    params = [tenant_id]
    query = """
        SELECT
            id,
            expense_id,
            tenant_id,
            sat_account_code,
            family_code,
            confidence_sat,
            confidence_family,
            explanation_short,
            explanation_detail,
            tokens,
            model_version,
            embedding_version,
            raw_payload,
            created_at
        FROM classification_trace
        WHERE tenant_id = ?
    """
    if expense_id is not None:
        query += " AND expense_id = ?"
        params.append(expense_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    results: list[Dict[str, Any]] = []
    for row in rows:
        # Row may be tuple or sqlite Row; normalize.
        if isinstance(row, sqlite3.Row):
            row_data = dict(row)
        else:
            (
                row_id,
                row_expense_id,
                row_tenant_id,
                sat_code,
                family,
                conf_sat,
                conf_family,
                expl_short,
                expl_detail,
                tokens_raw,
                model_version,
                embedding_version,
                raw_payload_raw,
                created_at,
            ) = row
            row_data = {
                "id": row_id,
                "expense_id": row_expense_id,
                "tenant_id": row_tenant_id,
                "sat_account_code": sat_code,
                "family_code": family,
                "confidence_sat": conf_sat,
                "confidence_family": conf_family,
                "explanation_short": expl_short,
                "explanation_detail": expl_detail,
                "tokens": tokens_raw,
                "model_version": model_version,
                "embedding_version": embedding_version,
                "raw_payload": raw_payload_raw,
                "created_at": created_at,
            }

        tokens_value = row_data.get("tokens")
        if isinstance(tokens_value, str) and tokens_value:
            try:
                row_data["tokens"] = json.loads(tokens_value)
            except json.JSONDecodeError:
                row_data["tokens"] = []
        elif tokens_value is None:
            row_data["tokens"] = []

        raw_payload_value = row_data.get("raw_payload")
        if isinstance(raw_payload_value, str) and raw_payload_value:
            try:
                row_data["raw_payload"] = json.loads(raw_payload_value)
            except json.JSONDecodeError:
                row_data["raw_payload"] = None

        results.append(row_data)

    return results
