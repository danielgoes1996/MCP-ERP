#!/usr/bin/env python3
"""
Script para agregar las nuevas columnas a la tabla tickets
"""

import sqlite3
import os

def get_db_path():
    """Obtener ruta de la base de datos"""
    return os.path.join(os.path.dirname(__file__), "internal_erp.db")

def migrate_tickets_table():
    """Agregar columnas de merchant_name, category y confidence a tickets"""

    db_path = get_db_path()
    print(f"🔍 Conectando a base de datos: {db_path}")

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()

        # Verificar columnas existentes
        cursor.execute("PRAGMA table_info(tickets)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        print(f"📋 Columnas existentes: {existing_columns}")

        # Agregar columnas faltantes
        new_columns = [
            ("merchant_name", "TEXT"),
            ("category", "TEXT"),
            ("confidence", "REAL")
        ]

        for column_name, column_type in new_columns:
            if column_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE tickets ADD COLUMN {column_name} {column_type}"
                    print(f"➕ Agregando columna: {sql}")
                    cursor.execute(sql)
                    print(f"✅ Columna {column_name} agregada exitosamente")
                except sqlite3.Error as e:
                    print(f"❌ Error agregando columna {column_name}: {e}")
            else:
                print(f"⚠️  Columna {column_name} ya existe")

        connection.commit()

        # Verificar columnas finales
        cursor.execute("PRAGMA table_info(tickets)")
        final_columns = [col[1] for col in cursor.fetchall()]
        print(f"📋 Columnas finales: {final_columns}")

        print("✅ Migración completada")

if __name__ == "__main__":
    migrate_tickets_table()