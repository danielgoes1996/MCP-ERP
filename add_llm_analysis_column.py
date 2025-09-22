#!/usr/bin/env python3
"""
Migración para agregar columna llm_analysis a la tabla tickets
"""

import sqlite3
import os
import sys

def add_llm_analysis_column():
    """Agregar columna llm_analysis a la tabla tickets"""

    # Encontrar la base de datos
    db_path = "tickets.db"
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos en {db_path}")
        return False

    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()

            # Verificar si la columna ya existe
            cursor.execute("PRAGMA table_info(tickets)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'llm_analysis' in columns:
                print("✅ La columna llm_analysis ya existe")
                return True

            # Agregar la columna
            cursor.execute("ALTER TABLE tickets ADD COLUMN llm_analysis TEXT")
            connection.commit()

            print("✅ Columna llm_analysis agregada exitosamente")
            return True

    except Exception as e:
        print(f"❌ Error agregando columna: {e}")
        return False

if __name__ == "__main__":
    print("🔧 MIGRACIÓN: Agregando columna llm_analysis")
    print("=" * 50)

    success = add_llm_analysis_column()

    if success:
        print("✅ Migración completada exitosamente")
    else:
        print("❌ Migración falló")
        sys.exit(1)