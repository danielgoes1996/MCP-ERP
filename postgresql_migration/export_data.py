#!/usr/bin/env python3
"""
Exportador de datos SQLite -> PostgreSQL
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime

def export_table_to_csv(db_path, table_name, output_dir):
    """Exporta una tabla SQLite a CSV"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if not rows:
            print(f"⚠️  Tabla {table_name} vacía")
            return

        csv_file = output_dir / f"{table_name}.csv"

        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
            writer.writeheader()

            for row in rows:
                # Convertir Row a dict
                row_dict = dict(row)
                writer.writerow(row_dict)

        print(f"✅ {table_name}: {len(rows)} filas -> {csv_file}")

def main():
    sqlite_db = "unified_mcp_system.db"
    output_dir = Path("postgresql_migration/data_export")
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = [
        'tenants', 'users', 'expense_records', 'bank_movements',
        'expense_invoices', 'tickets', 'automation_jobs',
        'automation_logs', 'automation_screenshots', 'gpt_usage_events',
        'schema_versions'
    ]

    print(f"🔄 Exportando datos desde {sqlite_db}")

    for table in tables:
        try:
            export_table_to_csv(sqlite_db, table, output_dir)
        except Exception as e:
            print(f"❌ Error exportando {table}: {e}")

    print("🎉 Exportación completada!")

if __name__ == "__main__":
    main()
