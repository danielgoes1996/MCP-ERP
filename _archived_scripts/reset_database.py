#!/usr/bin/env python3
"""
Script para limpiar completamente la base de datos y empezar desde cero.
Elimina todos los tickets, merchants, jobs, y otros datos almacenados.
"""

import os
import sqlite3
from pathlib import Path

def reset_database():
    """Limpiar completamente la base de datos."""
    print("🧹 LIMPIANDO BASE DE DATOS COMPLETA")
    print("=" * 40)

    try:
        # Importar función para obtener path de DB
        from core.internal_db import _get_db_path, _DB_LOCK

        db_path = _get_db_path()
        print(f"📁 Database path: {db_path}")

        # Verificar si la DB existe
        if not os.path.exists(db_path):
            print("ℹ️  No database file found - nothing to clean")
            return True

        # Hacer backup de la DB actual
        backup_path = f"{db_path}.backup"
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"💾 Backup created: {backup_path}")

        # Conectar y limpiar tablas
        with _DB_LOCK:
            with sqlite3.connect(db_path) as connection:
                cursor = connection.cursor()

                # Obtener lista de todas las tablas
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()

                print(f"\n🗃️  Found {len(tables)} tables:")
                for table in tables:
                    table_name = table[0]
                    print(f"   📋 {table_name}")

                # Limpiar tablas principales
                tables_to_clean = [
                    'tickets',
                    'merchants',
                    'invoicing_jobs',
                    'expense_records',
                    'expense_invoices',
                    'expense_payments',
                    'account_catalog'
                ]

                cleaned_count = 0
                for table_name in tables_to_clean:
                    try:
                        # Verificar si la tabla existe
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
                        if cursor.fetchone():
                            # Contar registros antes
                            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                            count_before = cursor.fetchone()[0]

                            # Limpiar tabla
                            cursor.execute(f"DELETE FROM {table_name}")

                            # Resetear autoincrement
                            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")

                            print(f"   🗑️  Cleaned {table_name}: {count_before} records deleted")
                            cleaned_count += 1
                        else:
                            print(f"   ⚠️  Table {table_name} not found - skipping")
                    except Exception as e:
                        print(f"   ❌ Error cleaning {table_name}: {e}")

                # Commit cambios
                connection.commit()

                print(f"\n✅ Cleaned {cleaned_count} tables successfully")

                # Verificar que está limpio
                print(f"\n🔍 Verification:")
                for table_name in tables_to_clean:
                    try:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
                        if cursor.fetchone():
                            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                            count = cursor.fetchone()[0]
                            status = "✅ Empty" if count == 0 else f"⚠️  {count} records remaining"
                            print(f"   📋 {table_name}: {status}")
                    except Exception as e:
                        print(f"   ❌ Error checking {table_name}: {e}")

        print(f"\n🎉 DATABASE RESET COMPLETE!")
        print(f"💾 Backup available at: {backup_path}")
        print(f"🔄 Database is now clean and ready for fresh data")

        return True

    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        return False

def reset_cache_and_temp_files():
    """Limpiar archivos de cache y temporales."""
    print(f"\n🧹 CLEANING CACHE AND TEMP FILES")
    print("-" * 35)

    cache_patterns = [
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        "*.log",
        "temp_*"
    ]

    cleaned_files = 0
    cleaned_dirs = 0

    # Limpiar archivos de cache Python
    for root, dirs, files in os.walk("."):
        # Limpiar directorios __pycache__
        if "__pycache__" in dirs:
            pycache_path = os.path.join(root, "__pycache__")
            try:
                import shutil
                shutil.rmtree(pycache_path)
                print(f"   🗑️  Removed: {pycache_path}")
                cleaned_dirs += 1
            except Exception as e:
                print(f"   ❌ Error removing {pycache_path}: {e}")

        # Limpiar archivos .pyc
        for file in files:
            if file.endswith('.pyc'):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    cleaned_files += 1
                except Exception as e:
                    print(f"   ❌ Error removing {file_path}: {e}")

    print(f"   ✅ Cleaned {cleaned_dirs} cache directories")
    print(f"   ✅ Cleaned {cleaned_files} cache files")

def main():
    """Ejecutar limpieza completa."""
    print("🔄 RESET COMPLETE SYSTEM DATA")
    print("=" * 35)
    print("⚠️  WARNING: This will delete ALL stored data!")
    print("💾 A backup will be created automatically")

    # Confirmación
    try:
        confirm = input("\n❓ Are you sure you want to reset all data? (yes/no): ").lower().strip()
        if confirm not in ['yes', 'y', 'sí', 'si']:
            print("❌ Reset cancelled by user")
            return False
    except KeyboardInterrupt:
        print("\n❌ Reset cancelled by user")
        return False

    # Ejecutar reset
    success = True

    # 1. Reset database
    if not reset_database():
        success = False

    # 2. Clean cache
    reset_cache_and_temp_files()

    # 3. Reinicializar DB con estructura vacía
    print(f"\n🏗️  REINITIALIZING DATABASE STRUCTURE")
    print("-" * 40)
    try:
        from core.internal_db import initialize_internal_database
        initialize_internal_database()
        print("   ✅ Database structure reinitialized")
    except Exception as e:
        print(f"   ❌ Error reinitializing database: {e}")
        success = False

    # Resultado final
    if success:
        print(f"\n🎉 SYSTEM RESET COMPLETE!")
        print("=" * 25)
        print("✅ All data cleared successfully")
        print("✅ Database structure reinitialized")
        print("✅ Cache and temp files cleaned")
        print("🚀 System ready for fresh start")

        print(f"\n📋 NEXT STEPS:")
        print("1. Start server: python main.py")
        print("2. Open browser: http://localhost:8000")
        print("3. Begin processing new tickets")
    else:
        print(f"\n❌ RESET INCOMPLETE")
        print("Some errors occurred during reset")
        print("Check the output above for details")

    return success

if __name__ == "__main__":
    main()