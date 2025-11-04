"""
Tenant-specific policies used by the IA pipeline.

Allows storing preferred SAT families or overrides per tenant so the
reasoning step can adapt to historical feedback.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Dict, Optional, Tuple

from config.config import config

logger = logging.getLogger(__name__)


def _get_connection() -> sqlite3.Connection:
    db_path = getattr(config, "UNIFIED_DB_PATH", "unified_mcp_system.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table() -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant_policies (
                tenant_id INTEGER PRIMARY KEY,
                family_preferences TEXT,
                overrides TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def get_policies(tenant_id: int) -> Dict[str, object]:
    ensure_table()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT family_preferences, overrides FROM tenant_policies WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()

    if not row:
        return {}

    policies: Dict[str, object] = {}
    for key in ("family_preferences", "overrides"):
        raw = row[key]
        if not raw:
            continue
        try:
            policies[key] = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Invalid JSON in tenant_policies.%s for tenant %s", key, tenant_id)
            policies[key] = raw
    return policies


def upsert_family_preferences(tenant_id: int, preferences: Dict[str, float]) -> None:
    ensure_table()
    payload = json.dumps(preferences, ensure_ascii=False)
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO tenant_policies (tenant_id, family_preferences, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tenant_id) DO UPDATE SET
                family_preferences = excluded.family_preferences,
                updated_at = CURRENT_TIMESTAMP
            """,
            (tenant_id, payload),
        )


def verify_family_preference(tenant_id: int, family_code: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not family_code:
        return False, None

    policies = get_policies(tenant_id)
    family_prefs = policies.get("family_preferences")
    if isinstance(family_prefs, dict) and family_prefs:
        if family_code not in family_prefs:
            reason = f"Familia {family_code} fuera de preferencias del tenant."
            return True, reason
    return False, None
