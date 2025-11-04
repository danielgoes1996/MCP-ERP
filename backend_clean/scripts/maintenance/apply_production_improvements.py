#!/usr/bin/env python3
"""
Script para aplicar mejoras de producción a transacciones existentes
"""
import sqlite3
from core.enhanced_categorization_engine import EnhancedCategorizationEngine

def apply_improvements():
    print("🚀 APPLYING PRODUCTION IMPROVEMENTS")
    print("=" * 50)

    # Conectar a la base de datos
    conn = sqlite3.connect('unified_mcp_system.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Inicializar el motor de categorización
    engine = EnhancedCategorizationEngine()

    try:
        # Obtener todas las transacciones existentes
        cursor.execute("""
            SELECT id, description, amount, date, raw_data
            FROM bank_movements
            WHERE account_id IN (7, 11)
            ORDER BY date, id
        """)

        transactions = cursor.fetchall()
        print(f"📊 Processing {len(transactions)} transactions...")

        updates_count = 0
        previous_balance = 20239.85  # Balance inicial conocido del estado de cuenta

        for i, txn in enumerate(transactions):
            # Procesar transacción con el motor mejorado
            processed = engine.process_transaction(
                description=txn['description'] or '',
                amount=txn['amount'] or 0.0,
                date_str=txn['date'] or '',
                raw_description=txn['raw_data'] or txn['description']
            )

            # Calcular balance progresivo
            if processed['display_type'] == 'balance_inicial':
                current_balance = previous_balance
                balance_before = previous_balance
            else:
                balance_before = previous_balance
                if processed['transaction_type'] == 'credit':
                    current_balance = previous_balance + abs(processed['amount'])
                else:
                    current_balance = previous_balance - abs(processed['amount'])

            # Actualizar en base de datos
            cursor.execute("""
                UPDATE bank_movements SET
                    date = ?,
                    cleaned_description = ?,
                    description_raw = ?,
                    transaction_type = ?,
                    movement_kind = ?,
                    display_type = ?,
                    transaction_subtype = ?,
                    category_auto = ?,
                    category_confidence = ?,
                    cargo_amount = ?,
                    abono_amount = ?,
                    balance_before = ?,
                    running_balance = ?
                WHERE id = ?
            """, (
                processed['date'],
                processed['description'],
                processed['description_raw'],
                processed['transaction_type'],
                processed['movement_kind'],
                processed['display_type'],
                processed['transaction_subtype'],
                processed['category_auto'],
                processed['category_confidence'],
                processed['cargo_amount'],
                processed['abono_amount'],
                balance_before,
                current_balance,
                txn['id']
            ))

            updates_count += 1
            previous_balance = current_balance

            if i % 10 == 0:  # Progress update
                print(f"   ✅ Processed {i+1}/{len(transactions)} transactions...")

        # Commit cambios
        conn.commit()
        print(f"\n🎯 SUCCESS: Updated {updates_count} transactions")

        # Mostrar resumen
        cursor.execute("""
            SELECT
                display_type,
                transaction_type,
                movement_kind,
                category_auto,
                COUNT(*) as count,
                ROUND(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 2) as total_credits,
                ROUND(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 2) as total_debits
            FROM bank_movements
            WHERE account_id IN (7, 11)
            GROUP BY display_type, transaction_type, movement_kind, category_auto
            ORDER BY display_type, transaction_type
        """)

        results = cursor.fetchall()
        print("\n📈 TRANSACTION SUMMARY:")
        print("-" * 80)
        print(f"{'Type':<15} {'T.Type':<8} {'Movement':<12} {'Category':<20} {'Count':<5} {'Credits':<10} {'Debits':<10}")
        print("-" * 80)

        for row in results:
            print(f"{row['display_type']:<15} {row['transaction_type']:<8} {row['movement_kind']:<12} {row['category_auto']:<20} {row['count']:<5} ${row['total_credits']:<9} ${row['total_debits']:<9}")

        # Verificar balance final
        cursor.execute("""
            SELECT running_balance
            FROM bank_movements
            WHERE account_id IN (7, 11)
            ORDER BY date DESC, id DESC
            LIMIT 1
        """)
        final_balance = cursor.fetchone()
        if final_balance:
            print(f"\n💰 FINAL BALANCE: ${final_balance['running_balance']:,.2f}")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    apply_improvements()