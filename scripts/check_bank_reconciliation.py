"""Quick integrity audit for bank reconciliation pipeline.

This script queries the unified_mcp_system.db SQLite database and reports
potential inconsistencies across the banking → reconciliation → policy flow.

Usage:
    python scripts/check_bank_reconciliation.py

Outputs a summary table with counts for:
    - Movements with links but without generated policies
    - Policies created without matching bank movements or entries
    - Feedback entries missing links
    - Movements marked reconciled without feedback

Adjust queries as needed once more business rules are formalised.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "unified_mcp_system.db"

QUERIES = {
    "links_without_policies": {
        "sql": """
            SELECT COUNT(*)
              FROM bank_match_links l
             WHERE l.bank_movement_id IS NOT NULL
               AND NOT EXISTS (
                    SELECT 1
                      FROM polizas_contables p
                     WHERE p.bank_movement_id = l.bank_movement_id
               )
        """,
        "description": "Links sin póliza generada",
    },
    "policies_without_entries": {
        "sql": """
            SELECT COUNT(*)
              FROM polizas_contables p
             WHERE NOT EXISTS (
                   SELECT 1
                     FROM polizas_detalle d
                    WHERE d.poliza_id = p.id
               )
        """,
        "description": "Pólizas sin asientos detalle",
    },
    "feedback_without_links": {
        "sql": """
            SELECT COUNT(*)
              FROM bank_reconciliation_feedback f
             WHERE NOT EXISTS (
                   SELECT 1
                     FROM bank_match_links l
                    WHERE l.bank_movement_id = f.movement_id
               )
        """,
        "description": "Feedback sin link banco↔CFDI",
    },
    "movements_reconciled_without_feedback": {
        "sql": """
            SELECT COUNT(*)
              FROM bank_movements m
             WHERE (m.reconciliation_status IN ('accepted', 'processed')
                    OR m.auto_matched = 1)
               AND NOT EXISTS (
                   SELECT 1
                     FROM bank_reconciliation_feedback f
                    WHERE f.movement_id = m.id
               )
        """,
        "description": "Movimientos conciliados sin feedback",
    },
}


def run_query(cursor: sqlite3.Cursor, sql: str) -> int:
    """Execute query and return first column from first row as integer."""
    cursor.execute(sql)
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        print("Bank Reconciliation Integrity Audit\n")
        print(f"Database: {DB_PATH}\n")
        for key, data in QUERIES.items():
            count = run_query(cursor, data["sql"])
            print(f"- {data['description']}: {count}")

        print("\n✔️  Review any non-zero counts to ensure end-to-end closure.")


if __name__ == "__main__":
    main()
