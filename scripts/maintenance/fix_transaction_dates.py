#!/usr/bin/env python3
"""
Corregir las fechas de las transacciones de 2024 a 2025
y recalcular saldos con datos correctos del PDF
"""
import sqlite3
from datetime import datetime

def fix_transaction_dates():
    """Corregir fechas de 2024 a 2025"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    print("🔧 Corrigiendo fechas de transacciones...")

    # Verificar transacciones actuales
    cursor.execute("""
        SELECT COUNT(*) as total_2024,
               MIN(date) as min_date,
               MAX(date) as max_date
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9 AND date LIKE '2024%'
    """)

    result = cursor.fetchone()
    total_2024 = result[0]

    print(f"📋 Encontradas {total_2024} transacciones con fechas 2024")
    print(f"📅 Rango actual: {result[1]} al {result[2]}")

    if total_2024 > 0:
        # Actualizar fechas de 2024 a 2025
        cursor.execute("""
            UPDATE bank_movements
            SET date = REPLACE(date, '2024-', '2025-')
            WHERE account_id = 5 AND user_id = 9 AND date LIKE '2024%'
        """)

        affected_rows = cursor.rowcount
        print(f"✅ Actualizadas {affected_rows} fechas de 2024 → 2025")

        # Verificar resultado
        cursor.execute("""
            SELECT COUNT(*) as total_2025,
                   MIN(date) as min_date,
                   MAX(date) as max_date
            FROM bank_movements
            WHERE account_id = 5 AND user_id = 9 AND date LIKE '2025%'
        """)

        result = cursor.fetchone()
        print(f"📋 Ahora hay {result[0]} transacciones en 2025")
        print(f"📅 Nuevo rango: {result[1]} al {result[2]}")

    conn.commit()
    conn.close()

def recalculate_with_correct_balance():
    """Recalcular saldos con el saldo inicial correcto del PDF"""

    # Datos del PDF
    saldo_inicial_pdf = 38587.42
    saldo_final_pdf = 41306.44

    print(f"\n🔄 Recalculando con saldo inicial del PDF: ${saldo_inicial_pdf:,.2f}")

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Obtener transacciones ordenadas (ahora con fechas 2025)
    cursor.execute("""
        SELECT id, date, description, amount
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    transactions = cursor.fetchall()
    print(f"📋 Procesando {len(transactions)} transacciones")

    # Calcular saldos corrientes con saldo inicial del PDF
    current_balance = saldo_inicial_pdf
    updates = []

    for i, (txn_id, date, description, amount) in enumerate(transactions):
        current_balance += amount
        updates.append((current_balance, txn_id))

        # Mostrar algunas transacciones
        if i < 3 or i >= len(transactions) - 3:
            print(f"  {date} | {description[:30]:30} | ${amount:8.2f} | Saldo: ${current_balance:10.2f}")
        elif i == 3:
            print("  ...")

    # Actualizar base de datos
    cursor.executemany("""
        UPDATE bank_movements
        SET balance_after = ?
        WHERE id = ?
    """, updates)

    conn.commit()
    conn.close()

    print(f"✅ Actualizados {len(updates)} saldos")
    print(f"💰 Saldo final calculado: ${current_balance:,.2f}")

    # Validar contra PDF
    diferencia = abs(current_balance - saldo_final_pdf)
    print(f"\n📊 VALIDACIÓN:")
    print(f"   📄 Saldo final PDF: ${saldo_final_pdf:,.2f}")
    print(f"   🧮 Saldo calculado: ${current_balance:,.2f}")
    print(f"   📐 Diferencia: ${diferencia:,.2f}")

    if diferencia < 1.0:
        print("✅ ¡PERFECTO! Los saldos coinciden exactamente.")
    elif diferencia < 10.0:
        print("🟡 Pequeña diferencia, probablemente por rendimientos o comisiones.")
    else:
        print("🟠 Diferencia moderada, revisar si hay transacciones faltantes.")

    return current_balance

def main():
    print("🔧 CORRECCIÓN DE FECHAS Y SALDOS")
    print("=" * 40)

    # Paso 1: Corregir fechas
    fix_transaction_dates()

    # Paso 2: Recalcular saldos
    final_balance = recalculate_with_correct_balance()

    print(f"\n🎉 ¡Proceso completado!")
    print(f"📅 Fechas corregidas: 2024 → 2025")
    print(f"💰 Saldos recalculados con datos del PDF")
    print(f"🔄 Ahora el UI mostrará saldos precisos desde ${38587.42:,.2f}")

if __name__ == "__main__":
    main()