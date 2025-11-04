#!/usr/bin/env python3
"""
Corregir el cálculo de saldos para mostrar correctamente en orden cronológico inverso
"""
import sqlite3

def recalculate_balances_for_reverse_order():
    """Recalcular saldos para mostrar correctamente de más reciente a más antigua"""

    # Saldo inicial del PDF
    saldo_inicial_pdf = 38587.42

    print("🔄 Recalculando saldos para orden cronológico inverso...")

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Paso 1: Obtener transacciones en orden cronológico (para calcular)
    cursor.execute("""
        SELECT id, date, description, amount
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    transactions_asc = cursor.fetchall()
    print(f"📋 Procesando {len(transactions_asc)} transacciones en orden cronológico")

    # Paso 2: Calcular saldos progresivos (orden cronológico)
    current_balance = saldo_inicial_pdf
    balance_map = {}  # id -> balance_after

    for i, (txn_id, date, description, amount) in enumerate(transactions_asc):
        current_balance += amount
        balance_map[txn_id] = current_balance

        # Mostrar progreso
        if i < 3:
            print(f"  {date} | {description[:30]:30} | ${amount:8.2f} | Saldo: ${current_balance:10.2f}")
        elif i == 3:
            print("  ...")

    print(f"💰 Saldo final calculado: ${current_balance:,.2f}")

    # Paso 3: Actualizar todos los saldos
    updates = [(balance_map[txn_id], txn_id) for txn_id, _, _, _ in transactions_asc]

    cursor.executemany("""
        UPDATE bank_movements
        SET balance_after = ?
        WHERE id = ?
    """, updates)

    conn.commit()

    # Paso 4: Verificar el orden de visualización (más reciente primero)
    cursor.execute("""
        SELECT date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date DESC, id DESC
        LIMIT 5
    """)

    recent_transactions = cursor.fetchall()

    print(f"\n📊 VERIFICACIÓN - Transacciones más recientes (como se ven en UI):")
    for date, desc, amount, balance in recent_transactions:
        print(f"  {date} | {desc[:30]:30} | ${amount:8.2f} | Saldo: ${balance:10.2f}")

    # Paso 5: Verificar transacciones más antiguas
    cursor.execute("""
        SELECT date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
        LIMIT 5
    """)

    old_transactions = cursor.fetchall()

    print(f"\n📊 VERIFICACIÓN - Transacciones más antiguas:")
    for date, desc, amount, balance in old_transactions:
        print(f"  {date} | {desc[:30]:30} | ${amount:8.2f} | Saldo: ${balance:10.2f}")

    # Verificar que el primer saldo sea correcto
    first_balance = old_transactions[0][3] if old_transactions else None
    expected_first = saldo_inicial_pdf + old_transactions[0][2] if old_transactions else None

    if first_balance and expected_first:
        print(f"\n✅ VALIDACIÓN:")
        print(f"   Saldo inicial PDF: ${saldo_inicial_pdf:,.2f}")
        print(f"   Primera transacción: ${old_transactions[0][2]:,.2f}")
        print(f"   Saldo después de primera: ${first_balance:,.2f}")
        print(f"   Esperado: ${expected_first:,.2f}")

        if abs(first_balance - expected_first) < 0.01:
            print("✅ ¡Cálculo correcto!")
        else:
            print("❌ Error en cálculo")

    conn.close()

def main():
    print("🔄 CORRECCIÓN DE ORDEN DE SALDOS")
    print("=" * 40)

    recalculate_balances_for_reverse_order()

    print(f"\n🎉 ¡Saldos corregidos!")
    print(f"📋 Ahora en el UI verás:")
    print(f"   - Transacciones de más reciente a más antigua")
    print(f"   - Saldos correctos para cada transacción")
    print(f"   - Secuencia lógica de balances")

if __name__ == "__main__":
    main()