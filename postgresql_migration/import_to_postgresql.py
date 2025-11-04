#!/usr/bin/env python3
"""
Importador PostgreSQL
Requiere: pip install psycopg2-binary
"""

import psycopg2
import csv
from pathlib import Path
import os

def import_csv_to_postgresql(csv_file, table_name, connection):
    """Importa CSV a PostgreSQL"""
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            cursor = connection.cursor()

            # Leer header
            reader = csv.DictReader(f)
            rows = list(reader)

            if not rows:
                print(f"⚠️  {csv_file} vacío")
                return

            # Construir INSERT
            columns = list(rows[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

            # Insertar datos
            for row in rows:
                values = [row[col] if row[col] != '' else None for col in columns]
                cursor.execute(sql, values)

            connection.commit()
            print(f"✅ {table_name}: {len(rows)} filas importadas")

    except Exception as e:
        print(f"❌ Error importando {table_name}: {e}")

def main():
    # Configuración PostgreSQL
    DB_CONFIG = {
        'host': os.getenv('PG_HOST', 'localhost'),
        'database': os.getenv('PG_DATABASE', 'mcp_production'),
        'user': os.getenv('PG_USER', 'mcp_user'),
        'password': os.getenv('PG_PASSWORD', 'your_password'),
        'port': os.getenv('PG_PORT', '5432')
    }

    data_dir = Path("postgresql_migration/data_export")

    if not data_dir.exists():
        print("❌ Directorio de datos no encontrado. Ejecuta export_data.py primero")
        return

    try:
        # Conectar a PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Conectado a PostgreSQL")

        # Orden de importación (respetando foreign keys)
        import_order = [
            'schema_versions',
            'tenants',
            'users',
            'expense_records',
            'bank_movements',
            'expense_invoices',
            'tickets',
            'automation_jobs',
            'automation_logs',
            'automation_screenshots',
            'gpt_usage_events'
        ]

        for table in import_order:
            csv_file = data_dir / f"{table}.csv"
            if csv_file.exists():
                import_csv_to_postgresql(csv_file, table, conn)
            else:
                print(f"⚠️  {csv_file} no encontrado")

        conn.close()
        print("🎉 Importación completada!")

    except Exception as e:
        print(f"❌ Error de conexión PostgreSQL: {e}")

if __name__ == "__main__":
    main()
