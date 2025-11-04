#!/usr/bin/env python3
"""
Corregir orden y saldos empezando desde el Balance Inicial
"""
import sqlite3

def fix_initial_balance_order():
    """Recalcular saldos empezando desde el balance inicial como primera transacción"""

    print("🔄 CORRECCIÓN DE BALANCE INICIAL")
    print("=" * 40)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Verificar que tenemos el balance inicial
    cursor.execute("""
        SELECT id, date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
        LIMIT 3
    """)

    first_transactions = cursor.fetchall()
    print("📋 Primeras transacciones actuales:")
    for txn in first_transactions:
        print(f"  ID:{txn[0]} | {txn[1]} | {txn[2][:40]} | ${txn[3]} | Balance: ${txn[4]}")

    # Saldo inicial del PDF
    saldo_inicial_pdf = 38587.42

    # Obtener todas las transacciones en orden cronológico
    cursor.execute("""
        SELECT id, date, description, amount
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    transactions = cursor.fetchall()
    print(f"\n🔄 Recalculando {len(transactions)} transacciones...")

    # Calcular saldos progresivos
    current_balance = saldo_inicial_pdf
    updates = []

    for i, (txn_id, date, description, amount) in enumerate(transactions):
        if 'Balance Inicial' in description:
            # Para el balance inicial, el saldo después es el mismo saldo inicial
            balance_after = saldo_inicial_pdf
        else:
            # Para transacciones normales, agregar el monto
            current_balance += amount
            balance_after = current_balance

        updates.append((balance_after, txn_id))

        # Mostrar progreso
        if i < 5:
            print(f"  {date} | {description[:40]:40} | ${amount:8.2f} | Saldo: ${balance_after:10.2f}")

    # Actualizar todos los saldos
    cursor.executemany("""
        UPDATE bank_movements
        SET balance_after = ?
        WHERE id = ?
    """, updates)

    conn.commit()

    # Verificar resultado final
    cursor.execute("""
        SELECT date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
        LIMIT 5
    """)

    corrected_transactions = cursor.fetchall()
    print(f"\n✅ RESULTADO CORREGIDO - Primeras 5 transacciones:")
    for date, desc, amount, balance in corrected_transactions:
        print(f"  {date} | {desc[:40]:40} | ${amount:8.2f} | ${balance:10.2f}")

    conn.close()

    print(f"\n🎉 ¡Balance inicial corregido!")
    print(f"📋 Ahora la primera línea es el Balance Inicial: ${saldo_inicial_pdf:,.2f}")

if __name__ == "__main__":
    fix_initial_balance_order()