#!/usr/bin/env python3
"""
Verificar que la base de datos esté completamente limpia.
"""

import sqlite3

def verify_clean_database():
    """Verificar el estado de la base de datos después del reset."""
    print("🔍 VERIFYING CLEAN DATABASE")
    print("=" * 30)

    try:
        from core.internal_db import _get_db_path

        db_path = _get_db_path()

        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()

            tables_to_check = [
                'tickets',
                'merchants',
                'invoicing_jobs',
                'expense_records',
                'expense_invoices',
                'expense_payments'
            ]

            print("📊 TABLE STATUS:")
            all_empty = True

            for table_name in tables_to_check:
                try:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
                    if cursor.fetchone():
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]

                        if count == 0:
                            print(f"   ✅ {table_name}: Empty (0 records)")
                        else:
                            print(f"   ⚠️  {table_name}: {count} records remaining")
                            all_empty = False
                    else:
                        print(f"   ❓ {table_name}: Table not found")
                except Exception as e:
                    print(f"   ❌ {table_name}: Error - {e}")
                    all_empty = False

            if all_empty:
                print(f"\n🎉 DATABASE IS COMPLETELY CLEAN!")
                print("✅ All tables are empty")
                print("🚀 Ready for fresh data")
            else:
                print(f"\n⚠️  DATABASE NOT COMPLETELY CLEAN")
                print("Some tables still contain data")

            return all_empty

    except Exception as e:
        print(f"❌ Error verifying database: {e}")
        return False

if __name__ == "__main__":
    verify_clean_database()