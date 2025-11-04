#!/usr/bin/env python3
"""Ensure contextual columns exist in bank_movements without duplicating older naming."""

import sqlite3
from typing import Dict, List

DB_PATH = "unified_mcp_system.db"

EQUIVALENTS: Dict[str, List[str]] = {
    "ai_model": ["model_name", "modelo_ai"],
    "context_used": ["context", "context_text"],
    "context_confidence": ["confidence_score", "ai_confidence"],
    "company_id": ["empresa_id", "organization_id"],
}

REQUIRED = [
    "context_used",
    "ai_model",
    "context_confidence",
    "context_version",
    "company_id",
]


def get_existing_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.execute(f"PRAGMA table_info({table});")
    return [row[1] for row in cur.fetchall()]


def run(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    existing = get_existing_columns(conn, "bank_movements")

    print(f"🔍 Columnas actuales: {existing}\n")
    to_add: List[str] = []
    remapped: Dict[str, str] = {}

    for col in REQUIRED:
        if col in existing:
            print(f"✅ {col} ya existe")
            continue

        found = next((alt for alt in EQUIVALENTS.get(col, []) if alt in existing), None)
        if found:
            print(f"🔁 {col} ya existe como {found} (mapear en código)")
            remapped[col] = found
        else:
            print(f"➕ Falta {col} → se agregará")
            to_add.append(col)

    if to_add:
        print("\n🚧 Agregando columnas faltantes...")
        for col in to_add:
            col_type = "TEXT"
            if col == "context_confidence":
                col_type = "REAL"
            elif col in {"context_version", "company_id"}:
                col_type = "INTEGER"
            conn.execute(f"ALTER TABLE bank_movements ADD COLUMN {col} {col_type};")
        conn.commit()

    if remapped:
        print("\n📘 Sugerencia de mapeo para código:")
        for new, old in remapped.items():
            print(f"    • Usa `{old}` en lugar de `{new}` o mapéalos ambos según convenga.")

    print("\n✅ Verificación final completa.")
    conn.close()


if __name__ == "__main__":
    run()
