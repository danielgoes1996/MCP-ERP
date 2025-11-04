#!/usr/bin/env python3
"""
Recalcular todos los saldos después de agregar la transacción faltante
"""
import sqlite3

def recalculate_all_balances():
    """Recalcular todos los saldos en orden cronológico correcto"""

    print("🔄 RECALCULANDO TODOS LOS SALDOS DESPUÉS DE AGREGAR TRANSACCIÓN FALTANTE")
    print("=" * 75)

    # Saldo inicial del PDF
    saldo_inicial_pdf = 38587.42

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Obtener todas las transacciones en orden cronológico, incluyendo la nueva
    cursor.execute("""
        SELECT id, date, description, amount
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    transactions = cursor.fetchall()
    print(f"📋 Procesando {len(transactions)} transacciones")

    # Calcular saldos progresivos
    current_balance = saldo_inicial_pdf
    updates = []

    print(f"\n📊 RECÁLCULO DETALLADO:")
    for i, (txn_id, date, description, amount) in enumerate(transactions):
        if 'Balance Inicial' in description:
            # Para el balance inicial, mantener el saldo inicial
            balance_after = saldo_inicial_pdf
        else:
            # Para transacciones normales, agregar el monto
            current_balance += amount
            balance_after = current_balance

        updates.append((balance_after, txn_id))

        # Mostrar las primeras 5 transacciones para verificar
        if i < 5:
            print(f"  {i+1}. {date} | {description[:50]:50} | ${amount:8.2f} | Balance: ${balance_after:10.2f}")

    print(f"  ...")
    print(f"💰 Saldo final calculado: ${current_balance:,.2f}")

    # Actualizar todos los saldos
    cursor.executemany("""
        UPDATE bank_movements
        SET balance_after = ?
        WHERE id = ?
    """, updates)

    conn.commit()

    # Verificar las primeras transacciones después del update
    cursor.execute("""
        SELECT date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
        LIMIT 5
    """)

    verified_transactions = cursor.fetchall()
    print(f"\n✅ VERIFICACIÓN - Primeras 5 transacciones corregidas:")
    for i, (date, desc, amount, balance) in enumerate(verified_transactions):
        print(f"  {i+1}. {date} | {desc[:50]:50} | ${amount:8.2f} | ${balance:10.2f}")

    conn.close()

    print(f"\n🎉 ¡Saldos recalculados!")
    print(f"📋 Total transacciones: {len(transactions)}")
    print(f"💰 Saldo final: ${current_balance:,.2f}")

if __name__ == "__main__":
    recalculate_all_balances()