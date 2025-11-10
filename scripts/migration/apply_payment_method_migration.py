#!/usr/bin/env python3
"""
Apply Payment Method Migration
Adds metodo_pago and forma_pago columns to expenses table
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.shared.unified_db_adapter import UnifiedDBAdapter

def main():
    print("=" * 80)
    print("APLICANDO MIGRACIÓN: Método y Forma de Pago")
    print("=" * 80)

    db = UnifiedDBAdapter()

    # Read migration SQL
    migration_path = "migrations/add_metodo_forma_pago.sql"
    print(f"\nLeyendo migración desde: {migration_path}")

    with open(migration_path, 'r') as f:
        migration_sql = f.read()

    try:
        print("\nEjecutando migración...")

        # Split by semicolons and execute each statement
        statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"  [{i}/{len(statements)}] Ejecutando statement...")
                db.execute(statement)

        print("\n✅ Migración aplicada exitosamente")

        # Verify columns exist
        print("\nVerificando columnas creadas...")
        result = db.query("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'expenses'
            AND column_name IN ('metodo_pago', 'forma_pago')
            ORDER BY column_name
        """)

        if result:
            print("\nColumnas creadas:")
            for row in result:
                col_name = row['column_name']
                data_type = row['data_type']
                max_length = row.get('character_maximum_length', '-')
                print(f"  ✓ {col_name}: {data_type}({max_length})")
        else:
            print("⚠️  No se pudieron verificar las columnas")

        # Check indexes
        print("\nVerificando índices creados...")
        indexes = db.query("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'expenses'
            AND indexname LIKE '%metodo%' OR indexname LIKE '%forma%'
        """)

        if indexes:
            for idx in indexes:
                print(f"  ✓ {idx['indexname']}")

        print("\n" + "=" * 80)
        print("✅ MIGRACIÓN COMPLETADA")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error aplicando migración: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
