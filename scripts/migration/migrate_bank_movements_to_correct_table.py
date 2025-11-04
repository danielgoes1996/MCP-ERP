#!/usr/bin/env python3
"""
Script para migrar movimientos bancarios de expense_records a bank_movements.

Los movimientos bancarios fueron guardados incorrectamente en expense_records.
Este script los identifica por su metadata y los migra a bank_movements.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "unified_mcp_system.db"


def migrate_bank_movements():
    """Migrar movimientos bancarios a la tabla correcta."""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Identificar gastos que son movimientos bancarios
        print("🔍 Identificando movimientos bancarios en expense_records...")

        cursor.execute("""
            SELECT * FROM expense_records
            WHERE metadata LIKE '%bank_reference%'
               OR metadata LIKE '%raw_data%'
               OR metadata LIKE '%movement_kind%'
        """)

        bank_expenses = cursor.fetchall()
        print(f"   Encontrados: {len(bank_expenses)} registros")

        if not bank_expenses:
            print("✅ No hay movimientos bancarios que migrar")
            return

        # 2. Migrar cada registro
        migrated = 0
        errors = []

        for expense in bank_expenses:
            try:
                # Parsear metadata
                metadata = {}
                if expense['metadata']:
                    try:
                        metadata = json.loads(expense['metadata'])
                    except:
                        metadata = {}

                # Determinar tipo de movimiento
                movement_kind = metadata.get('movement_kind', 'Gasto')
                bank_reference = metadata.get('bank_reference', '')
                raw_data = metadata.get('raw_data', '')

                # Determinar cargo/abono
                amount = abs(expense['amount']) if expense['amount'] else 0
                cargo_amount = amount if expense['amount'] < 0 else 0
                abono_amount = amount if expense['amount'] > 0 else 0

                # Insertar en bank_movements
                cursor.execute("""
                    INSERT INTO bank_movements (
                        amount, description, date, tenant_id, user_id,
                        movement_id, movement_kind, cargo_amount, abono_amount,
                        description_raw, raw_data, category,
                        processing_status, created_at,
                        transaction_type, reference
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    expense['amount'],
                    expense['description'],
                    expense['date'],
                    expense['tenant_id'],
                    expense['user_id'],
                    bank_reference,
                    movement_kind,
                    cargo_amount,
                    abono_amount,
                    raw_data,
                    raw_data,
                    expense['category'],
                    'migrated',
                    expense['created_at'],
                    'bank_statement',
                    bank_reference
                ))

                # Marcar el expense original como migrado (agregando metadata)
                updated_metadata = metadata.copy()
                updated_metadata['migrated_to_bank_movements'] = True
                updated_metadata['migrated_at'] = datetime.utcnow().isoformat()
                updated_metadata['original_expense_id'] = expense['id']

                cursor.execute("""
                    UPDATE expense_records
                    SET metadata = ?
                    WHERE id = ?
                """, (json.dumps(updated_metadata), expense['id']))

                migrated += 1

            except Exception as e:
                errors.append(f"Error migrando expense {expense['id']}: {str(e)}")
                continue

        # 3. Commit
        conn.commit()

        print(f"✅ Migrados: {migrated} movimientos bancarios a bank_movements")

        if errors:
            print(f"\n⚠️  Errores encontrados:")
            for error in errors:
                print(f"   - {error}")

        # 4. Ahora eliminar los registros migrados de expense_records
        print("\n🗑️  Eliminando registros migrados de expense_records...")
        cursor.execute("""
            DELETE FROM expense_records
            WHERE metadata LIKE '%migrated_to_bank_movements%'
        """)
        deleted = cursor.rowcount
        conn.commit()

        print(f"   Eliminados: {deleted} registros")

        # 5. Verificar
        cursor.execute("SELECT COUNT(*) FROM expense_records WHERE tenant_id = 3")
        remaining_expenses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM bank_movements WHERE tenant_id = 3")
        total_movements = cursor.fetchone()[0]

        print(f"\n📊 Resultado final:")
        print(f"   expense_records: {remaining_expenses} gastos")
        print(f"   bank_movements: {total_movements} movimientos bancarios")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante la migración: {str(e)}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 70)
    print("MIGRACIÓN DE MOVIMIENTOS BANCARIOS")
    print("=" * 70)
    print(f"Base de datos: {DB_PATH}\n")

    migrate_bank_movements()

    print("\n✅ Migración completada")
    print("=" * 70)
