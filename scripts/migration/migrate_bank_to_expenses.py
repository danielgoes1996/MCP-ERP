#!/usr/bin/env python3
"""
Migrate bank_movements to expense_records for UI display
"""
import sqlite3
from datetime import datetime

def migrate_bank_movements_to_expenses():
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    print("🔄 Migrando bank_movements a expense_records...")

    # Get bank movements for user 9, account 5
    cursor.execute("""
        SELECT
            date, description, amount, movement_kind,
            category, user_id, tenant_id, raw_data, reference
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date DESC
    """)

    movements = cursor.fetchall()
    print(f"📊 Encontrados {len(movements)} movimientos bancarios")

    # Clear existing expense records for this user to avoid duplicates
    cursor.execute("DELETE FROM expense_records WHERE user_id = 9 AND tenant_id = 3")
    print(f"🗑️ Limpiados registros anteriores")

    # Insert each movement as an expense record
    migrated_count = 0
    for movement in movements:
        date, description, amount, movement_kind, category, user_id, tenant_id, raw_data, reference = movement

        # Map movement_kind to appropriate status
        if movement_kind == 'Gasto':
            status = 'approved'
            amount = abs(amount) * -1  # Ensure negative for expenses
        elif movement_kind == 'Ingreso':
            status = 'approved'
            amount = abs(amount)  # Ensure positive for income
        else:  # Transferencia
            status = 'approved'
            # Keep original sign

        # Parse date (handle different formats)
        try:
            if isinstance(date, str):
                if 'T' in date:
                    parsed_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                else:
                    parsed_date = datetime.strptime(date, '%Y-%m-%d')
            else:
                parsed_date = date
        except:
            parsed_date = datetime.now()

        # Determine category
        expense_category = category or 'Sin categoría'

        # Create merchant name from description
        merchant_name = description[:100] if description else 'Movimiento bancario'

        # Insert into expense_records
        cursor.execute("""
            INSERT INTO expense_records (
                amount, currency, description, category, merchant_name,
                date, user_id, tenant_id, status, created_at,
                deducible, requiere_factura, moneda, invoice_status,
                bank_status, approval_status, completion_status,
                field_completeness, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            amount,                    # amount
            'MXN',                    # currency
            description or 'Movimiento bancario',  # description
            expense_category,         # category
            merchant_name,            # merchant_name
            parsed_date,             # date
            user_id,                 # user_id
            tenant_id,               # tenant_id
            status,                  # status
            datetime.now(),          # created_at
            True,                    # deducible
            amount < 0,              # requiere_factura (only for expenses)
            'MXN',                   # moneda
            'facturado' if amount < 0 else 'no_aplica',  # invoice_status
            'conciliado_banco',      # bank_status (already from bank)
            'aprobado',              # approval_status
            'completo',              # completion_status
            100.0,                   # field_completeness
            f'{{"bank_reference": "{reference}", "movement_kind": "{movement_kind}", "raw_data": "{raw_data or ""}"}}' # metadata
        ))
        migrated_count += 1

    conn.commit()
    print(f"✅ Migrados {migrated_count} movimientos a expense_records")

    # Verify migration
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_ingresos,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_gastos
        FROM expense_records
        WHERE user_id = 9 AND tenant_id = 3
    """)

    total, ingresos, gastos = cursor.fetchone()
    print(f"\n📈 Resumen de migración:")
    print(f"  Total registros: {total}")
    print(f"  Total ingresos: ${ingresos:,.2f}")
    print(f"  Total gastos: ${gastos:,.2f}")
    print(f"  Balance neto: ${(ingresos or 0) - (gastos or 0):,.2f}")

    conn.close()
    print("\n🎉 Migración completada! Los datos reales ahora están disponibles en la UI.")

if __name__ == "__main__":
    migrate_bank_movements_to_expenses()