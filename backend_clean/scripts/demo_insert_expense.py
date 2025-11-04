#!/usr/bin/env python3
"""
Insert a demo expense row into SQLite to verify the full schema.
Usage:
    python scripts/demo_insert_expense.py
"""

import sqlite3
from datetime import datetime

DB_PATH = "unified_mcp_system.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    now = datetime.utcnow().isoformat()
    payload = {
        "amount": 1234.56,
        "currency": "MXN",
        "description": "Hospedaje demo Hilton CDMX",
        "category": "viajes",
        "merchant_name": "Hilton CDMX",
        "merchant_category": "hoteles",
        "date": now,
        "user_id": 2,
        "tenant_id": 2,
        "status": "pending",
        "created_at": now,
        "metadata": '{"source":"demo_insert"}',
        "sat_account_code": "604.47",
        "workflow_status": "pendiente_factura",
    }
    columns = ", ".join(payload.keys())
    placeholders = ", ".join("?" for _ in payload)
    conn.execute(
        f"INSERT INTO expense_records ({columns}) VALUES ({placeholders})",
        tuple(payload.values()),
    )
    conn.commit()
    conn.close()
    print("Demo expense inserted.")


if __name__ == "__main__":
    main()
