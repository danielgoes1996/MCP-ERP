#!/usr/bin/env python3
"""Utility script to verify required schema columns for contextual banking flow."""

import sqlite3
from pathlib import Path
from typing import Dict, List

EXPECTED_TABLES: Dict[str, List[str]] = {
    "ai_context_memory": [
        "company_id",
        "summary",
        "onboarding_snapshot",  # business_profile data stored here
        "created_at",
    ],
    "bank_movements": [
        "id",
        "company_id",
        "date",
        "description",
        "amount",
        "balance_after",
        "transaction_type",
        "category",
        "context_used",
        "ai_model",
        "context_confidence",
        "context_version",
    ],
}


def verify_schema_diff(db_path: str = "unified_mcp_system.db") -> None:
    """Check that critical tables expose the columns required by the contextual pipeline."""
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"⚠️ Base de datos no encontrada en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🔍 Verificando estructura de base de datos...")
    for table_name, expected_cols in EXPECTED_TABLES.items():
        try:
            cursor.execute(f"PRAGMA table_info({table_name});")
            existing_cols = [row[1] for row in cursor.fetchall()]
        except sqlite3.OperationalError as exc:
            print(f"⚠️ Tabla {table_name} no encontrada ({exc})")
            continue

        missing: List[str] = []
        for col in expected_cols:
            if col == "company_id" and col not in existing_cols:
                # Historical schemas may omit company_id in bank_movements; shout out regardless
                missing.append(col)
                continue

            if col == "onboarding_snapshot" and "business_profile" in existing_cols:
                continue

            if col not in existing_cols:
                missing.append(col)
        if not missing:
            print(f"✅ {table_name}: OK")
        else:
            print(f"⚠️ {table_name}: faltan columnas -> {missing}")

    conn.close()


if __name__ == "__main__":
    verify_schema_diff()
