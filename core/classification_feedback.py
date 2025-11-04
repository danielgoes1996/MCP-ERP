"""
Lightweight helpers to persist expense classification feedback that can be used to
continuously fine-tune alias dictionaries or fallback rules.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from core.text_normalizer import normalize_expense_text
from core.classification_trace import get_latest_trace_id

logger = logging.getLogger(__name__)

FEEDBACK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS expense_classification_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    expense_id INTEGER,
    descripcion_normalizada TEXT NOT NULL,
    suggested_sat_code TEXT,
    confirmed_sat_code TEXT NOT NULL,
    classification_trace_id INTEGER,
    notes TEXT,
    captured_at TIMESTAMP NOT NULL
);
"""


def ensure_feedback_table(conn: sqlite3.Connection) -> None:
    """Create the feedback table when absent."""
    conn.execute(FEEDBACK_TABLE_SQL)
    try:
        conn.execute("ALTER TABLE expense_classification_feedback ADD COLUMN classification_trace_id INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()


def record_feedback(
    conn: sqlite3.Connection,
    *,
    tenant_id: int,
    descripcion: str,
    confirmed_sat_code: str,
    suggested_sat_code: Optional[str] = None,
    expense_id: Optional[int] = None,
    classification_trace_id: Optional[int] = None,
    notes: Optional[str] = None,
    captured_at: Optional[datetime] = None,
) -> None:
    """
    Persist a corrected classification so future training jobs can consume it.
    """
    ensure_feedback_table(conn)
    trace_id = classification_trace_id
    if trace_id is None and expense_id is not None:
        try:
            trace_id = get_latest_trace_id(conn, expense_id, tenant_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug(
                "Unable to resolve classification trace for expense %s tenant %s: %s",
                expense_id,
                tenant_id,
                exc,
            )

    normalized_desc = normalize_expense_text(descripcion)
    conn.execute(
        """
        INSERT INTO expense_classification_feedback (
            tenant_id,
            expense_id,
            descripcion_normalizada,
            suggested_sat_code,
            confirmed_sat_code,
            classification_trace_id,
            notes,
            captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id,
            expense_id,
            normalized_desc,
            suggested_sat_code,
            confirmed_sat_code,
            trace_id,
            notes,
            (captured_at or datetime.utcnow()).isoformat(),
        ),
    )
    conn.commit()
