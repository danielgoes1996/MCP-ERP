#!/usr/bin/env python3
"""
Aggregate manual feedback to update tenant policies (preferred families).

Derives preferences from expense_records.metadata.classification_feedback.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import sqlite3

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tenant_policies import upsert_family_preferences, ensure_table  # noqa: E402
from config.config import config  # noqa: E402
from core.sat_utils import extract_family_code  # noqa: E402


def _connect() -> sqlite3.Connection:
    db_path = getattr(config, "UNIFIED_DB_PATH", "unified_mcp_system.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def collect_feedback() -> dict[int, Counter]:
    preferences: dict[int, Counter] = defaultdict(Counter)

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT tenant_id, metadata
              FROM expense_records
             WHERE metadata IS NOT NULL
            """
        ).fetchall()

    for row in rows:
        tenant_id = row["tenant_id"]
        metadata_raw = row["metadata"]
        if not metadata_raw:
            continue
        try:
            metadata = json.loads(metadata_raw)
        except json.JSONDecodeError:
            continue

        feedback_entries = metadata.get("classification_feedback")
        if not isinstance(feedback_entries, list):
            continue

        for entry in feedback_entries:
            if not isinstance(entry, dict):
                continue
            sat_code = entry.get("confirmed_sat_account_code") or entry.get("sat_account_code")
            if not sat_code:
                continue
            family = extract_family_code(sat_code)
            if not family:
                continue
            confidence = entry.get("confidence", 1.0)
            try:
                weight = float(confidence)
            except (TypeError, ValueError):
                weight = 1.0
            weight = max(0.1, min(5.0, weight))
            preferences[tenant_id][family] += weight

    return preferences


def main() -> None:
    ensure_table()
    prefs = collect_feedback()
    if not prefs:
        print("No feedback found to update tenant policies.")
        return

    for tenant_id, counter in prefs.items():
        ranked = {family: round(score, 2) for family, score in counter.most_common(10)}
        upsert_family_preferences(tenant_id, ranked)
        print(f"Updated tenant {tenant_id} policies: {ranked}")


if __name__ == "__main__":
    main()
