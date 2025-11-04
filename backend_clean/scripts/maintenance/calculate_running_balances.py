#!/usr/bin/env python3
"""
Calcular saldos corrientes para todas las transacciones
Esto permitirá mostrar cómo cada transacción afecta el saldo total
"""
import sqlite3
from typing import List, Tuple

def get_account_transactions(account_id: int, user_id: int) -> List[Tuple]:
    """Obtener todas las transacciones de una cuenta ordenadas por fecha"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = ? AND user_id = ?
        ORDER BY date ASC, id ASC
    """, (account_id, user_id))

    transactions = cursor.fetchall()
    conn.close()

    return transactions

def calculate_running_balances(account_id: int, user_id: int, initial_balance: float = 0.0):
    """Calcular saldos corrientes para todas las transacciones"""

    print(f"📊 Calculando saldos corrientes para cuenta {account_id} usuario {user_id}")

    # Obtener transacciones
    transactions = get_account_transactions(account_id, user_id)

    if not transactions:
        print("❌ No se encontraron transacciones")
        return

    print(f"📋 Encontradas {len(transactions)} transacciones")

    # Calcular saldos corrientes
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    current_balance = initial_balance
    updates = []

    print(f"💰 Saldo inicial: ${current_balance:,.2f}")
    print("\n📈 Calculando saldos:")

    for i, (txn_id, date, description, amount, current_balance_after) in enumerate(transactions):
        # Calcular nuevo saldo
        current_balance += amount

        # Preparar actualización
        updates.append((current_balance, txn_id))

        # Mostrar progreso para las primeras y últimas transacciones
        if i < 5 or i >= len(transactions) - 5:
            print(f"  {date} | {description[:40]:40} | ${amount:8.2f} | Saldo: ${current_balance:10.2f}")
        elif i == 5:
            print("  ...")

    # Ejecutar actualizaciones en batch
    print(f"\n💾 Actualizando {len(updates)} registros en la base de datos...")

    cursor.executemany("""
        UPDATE bank_movements
        SET balance_after = ?
        WHERE id = ?
    """, updates)

    conn.commit()

    # Verificar resultados
    cursor.execute("""
        SELECT COUNT(*) as total,
               MIN(balance_after) as min_balance,
               MAX(balance_after) as max_balance
        FROM bank_movements
        WHERE account_id = ? AND user_id = ? AND balance_after IS NOT NULL
    """, (account_id, user_id))

    total, min_balance, max_balance = cursor.fetchone()

    print(f"✅ Actualizados {total} registros")
    print(f"📊 Saldo mínimo: ${min_balance:,.2f}")
    print(f"📊 Saldo máximo: ${max_balance:,.2f}")
    print(f"💰 Saldo final: ${current_balance:,.2f}")

    conn.close()

    return current_balance

def detect_initial_balance_from_statement():
    """Detectar saldo inicial de los datos del estado de cuenta"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Buscar la primera transacción y intentar deducir el saldo inicial
    cursor.execute("""
        SELECT date, amount, description
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
        LIMIT 1
    """)

    first_txn = cursor.fetchone()

    if first_txn:
        print(f"🔍 Primera transacción: {first_txn[0]} | {first_txn[2]} | ${first_txn[1]}")

        # Para AMEX Gold, el saldo inicial típicamente se puede deducir del estado de cuenta
        # Por ahora usar 0 como base y ajustar según sea necesario
        initial_balance = 0.0

        print(f"💰 Usando saldo inicial estimado: ${initial_balance:,.2f}")
        return initial_balance

    conn.close()
    return 0.0

def show_balance_progression_sample(account_id: int, user_id: int, limit: int = 10):
    """Mostrar una muestra de cómo se ve la progresión de saldos"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = ? AND user_id = ? AND balance_after IS NOT NULL
        ORDER BY date ASC, id ASC
        LIMIT ?
    """, (account_id, user_id, limit))

    transactions = cursor.fetchall()

    print(f"\n📋 Muestra de progresión de saldos (primeras {limit} transacciones):")
    print("Fecha       | Descripción                           | Monto      | Saldo")
    print("-" * 80)

    for date, desc, amount, balance in transactions:
        amount_str = f"${amount:8.2f}"
        balance_str = f"${balance:10.2f}"
        print(f"{date} | {desc[:37]:37} | {amount_str} | {balance_str}")

    conn.close()

def main():
    print("🧮 CALCULADORA DE SALDOS CORRIENTES")
    print("=" * 50)

    # Parámetros de la cuenta AMEX Gold
    account_id = 5
    user_id = 9

    # Detectar o establecer saldo inicial
    initial_balance = detect_initial_balance_from_statement()

    # Calcular saldos corrientes
    final_balance = calculate_running_balances(account_id, user_id, initial_balance)

    # Mostrar muestra de resultados
    show_balance_progression_sample(account_id, user_id, 10)

    print(f"\n🎉 ¡Cálculo de saldos completado!")
    print(f"💰 Saldo final calculado: ${final_balance:,.2f}")
    print(f"\n💡 Ahora cada transacción mostrará:")
    print(f"   - Monto de la transacción")
    print(f"   - Saldo resultante después de la transacción")
    print(f"   - Progresión clara de cómo afecta cada movimiento")

if __name__ == "__main__":
    main()