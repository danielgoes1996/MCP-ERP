#!/usr/bin/env python3
"""
Script para limpiar automáticamente la base de datos sin confirmación.
"""

import os
import sqlite3

def reset_database_auto():
    """Limpiar automáticamente la base de datos."""
    print("🧹 AUTO-CLEANING DATABASE")
    print("=" * 30)

    try:
        from core.internal_db import _get_db_path, _DB_LOCK

        db_path = _get_db_path()
        print(f"📁 Database: {db_path}")

        if not os.path.exists(db_path):
            print("ℹ️  No database found - nothing to clean")
            return True

        # Backup
        backup_path = f"{db_path}.backup"
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"💾 Backup: {backup_path}")

        # Limpiar
        with _DB_LOCK:
            with sqlite3.connect(db_path) as connection:
                cursor = connection.cursor()

                tables_to_clean = [
                    'tickets',
                    'merchants',
                    'invoicing_jobs',
                    'expense_records',
                    'expense_invoices',
                    'expense_payments'
                ]

                total_deleted = 0
                for table_name in tables_to_clean:
                    try:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
                        if cursor.fetchone():
                            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                            count_before = cursor.fetchone()[0]

                            cursor.execute(f"DELETE FROM {table_name}")
                            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")

                            print(f"   🗑️  {table_name}: {count_before} records deleted")
                            total_deleted += count_before
                    except Exception as e:
                        print(f"   ⚠️  {table_name}: {e}")

                connection.commit()
                print(f"\n✅ Total deleted: {total_deleted} records")

        # Reinicializar estructura
        from core.internal_db import initialize_internal_database
        initialize_internal_database()
        print(f"🏗️  Database structure reinitialized")

        print(f"\n🎉 RESET COMPLETE!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    reset_database_auto()