#!/usr/bin/env python3
"""
Script para reinicializar la base de datos con las nuevas columnas
"""

import os
import sys

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def reset_database():
    """Eliminar y recrear la base de datos"""

    db_path = os.path.join(os.path.dirname(__file__), "internal_erp.db")

    print(f"🗑️  Eliminando base de datos existente: {db_path}")

    if os.path.exists(db_path):
        os.remove(db_path)
        print("✅ Base de datos eliminada")
    else:
        print("⚠️  Base de datos no existía")

    # Inicializar nueva base de datos
    print("🔄 Inicializando nueva base de datos...")

    from core.internal_db import initialize_internal_database

    try:
        initialize_internal_database()
        print("✅ Base de datos inicializada con nuevas columnas")

        # Verificar tabla tickets
        import sqlite3
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()
            cursor.execute("PRAGMA table_info(tickets)")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"📋 Columnas de tickets: {columns}")

            # Verificar que las nuevas columnas existen
            required_columns = ['merchant_name', 'category', 'confidence']
            for col in required_columns:
                if col in columns:
                    print(f"✅ Columna '{col}' creada correctamente")
                else:
                    print(f"❌ Columna '{col}' NO encontrada")

    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reset_database()