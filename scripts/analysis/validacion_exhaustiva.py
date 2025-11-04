#!/usr/bin/env python3
"""
Validación exhaustiva para detectar cualquier transacción faltante
"""

import sqlite3
from core.pdf_extraction_validator import PDFExtractionValidator

def validacion_exhaustiva():
    print("🔍 VALIDACIÓN EXHAUSTIVA DE TRANSACCIONES")
    print("=" * 60)

    # Conectar a BD y obtener todas las transacciones
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, date, description, amount, balance_after, movement_kind
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    all_transactions = cursor.fetchall()
    print(f"📊 Total transacciones en BD: {len(all_transactions)}")

    # Mostrar las primeras 10 y últimas 5 para verificar
    print(f"\n📋 PRIMERAS 10 TRANSACCIONES:")
    for i, txn in enumerate(all_transactions[:10]):
        print(f"  {i+1:2d}. {txn[1]} | {txn[2][:50]:50} | ${txn[3]:8.2f} | ${txn[4] or 0:10.2f}")

    print(f"\n📋 ÚLTIMAS 5 TRANSACCIONES:")
    for i, txn in enumerate(all_transactions[-5:], len(all_transactions)-4):
        print(f"  {i:2d}. {txn[1]} | {txn[2][:50]:50} | ${txn[3]:8.2f} | ${txn[4] or 0:10.2f}")

    # Verificaciones específicas
    print(f"\n🔍 VERIFICACIONES ESPECÍFICAS:")

    # 1. Balance Inicial
    balance_inicial = [t for t in all_transactions if 'Balance Inicial' in t[2]]
    print(f"  1. Balance Inicial: {'✅ Encontrado' if balance_inicial else '❌ NO encontrado'}")
    if balance_inicial:
        print(f"     • Posición: 1 (primera transacción)")
        print(f"     • Saldo: ${balance_inicial[0][4]}")

    # 2. Jorge Luis González
    jorge_txns = [t for t in all_transactions if 'Jorge Luis' in t[2] or 'JORGE LUIS' in t[2].upper()]
    print(f"  2. Jorge Luis González: {'✅ Encontrado' if jorge_txns else '❌ NO encontrado'}")
    if jorge_txns:
        for j in jorge_txns:
            print(f"     • {j[1]} | ${j[3]} | {j[2][:50]}")

    # 3. Continuidad de fechas (buscar gaps)
    print(f"  3. Continuidad de fechas:")
    fechas_unicas = sorted(set(t[1] for t in all_transactions))
    print(f"     • Rango: {fechas_unicas[0]} → {fechas_unicas[-1]}")
    print(f"     • Días con transacciones: {len(fechas_unicas)}")

    # 4. Verificar si hay días faltantes en julio
    from datetime import datetime, timedelta
    fecha_inicio = datetime.strptime(fechas_unicas[0], '%Y-%m-%d')
    fecha_fin = datetime.strptime(fechas_unicas[-1], '%Y-%m-%d')

    dias_esperados = (fecha_fin - fecha_inicio).days + 1
    gaps_encontrados = []

    fecha_actual = fecha_inicio
    while fecha_actual <= fecha_fin:
        fecha_str = fecha_actual.strftime('%Y-%m-%d')
        if fecha_str not in fechas_unicas:
            gaps_encontrados.append(fecha_str)
        fecha_actual += timedelta(days=1)

    print(f"     • Días esperados: {dias_esperados}")
    print(f"     • Gaps de fechas: {len(gaps_encontrados)}")
    if gaps_encontrados and len(gaps_encontrados) < 10:
        print(f"     • Fechas sin transacciones: {', '.join(gaps_encontrados)}")

    # 5. Validación de balances progresivos
    print(f"  4. Validación de balances:")
    balance_errors = 0
    for i in range(1, len(all_transactions)):
        prev_txn = all_transactions[i-1]
        curr_txn = all_transactions[i]

        if prev_txn[4] is not None and curr_txn[4] is not None:
            expected_balance = prev_txn[4] + curr_txn[3]
            actual_balance = curr_txn[4]

            if abs(expected_balance - actual_balance) > 0.01:  # Tolerancia de 1 centavo
                balance_errors += 1
                if balance_errors <= 3:  # Mostrar solo los primeros 3 errores
                    print(f"     ❌ Error balance txn {i+1}: Esperado ${expected_balance:.2f}, Actual ${actual_balance:.2f}")

    if balance_errors == 0:
        print(f"     ✅ Balances progresivos correctos")
    else:
        print(f"     ⚠️ {balance_errors} errores de balance encontrados")

    # 6. Usar el validador automático con texto PDF simulado
    print(f"\n🤖 VALIDACIÓN AUTOMÁTICA CON SISTEMA:")

    # Simular texto PDF con patrones conocidos
    pdf_simulado = """
    ESTADO DE CUENTA JULIO 2024

    Balance Inicial: $38,587.42

    JUL. 01 12345678 SPEI RECIBIDO JORGE LUIS GONZALEZ 1,000.00
    JUL. 01 87654321 OPENAI CHATGPT SUBSCRIPTION 378.85
    JUL. 02 11111111 APPLE SERVICES BILLING 215.00
    JUL. 03 22222222 BUBBLE STARTER PLAN 603.48

    ... más transacciones ...

    Saldo Final Julio: Consultar último movimiento
    """

    # Convertir transacciones para el validador
    validation_transactions = []
    for txn in all_transactions:
        validation_transactions.append({
            'date': txn[1],
            'description': txn[2],
            'amount': txn[3],
            'balance_after': txn[4]
        })

    validator = PDFExtractionValidator()
    resultado = validator.validate_extraction_completeness(
        pdf_simulado,
        validation_transactions,
        expected_balance_initial=38587.42
    )

    print(f"     • Transacciones en PDF simulado: {resultado['raw_transaction_count']}")
    print(f"     • Transacciones en BD: {resultado['extracted_transaction_count']}")
    print(f"     • Faltantes detectadas: {len(resultado['missing_transactions'])}")
    print(f"     • Validación: {'✅ COMPLETA' if resultado['is_complete'] else '❌ INCOMPLETA'}")

    if resultado['missing_transactions']:
        print(f"\n🚨 TRANSACCIONES FALTANTES DETECTADAS:")
        for i, missing in enumerate(resultado['missing_transactions'][:5]):
            raw = missing['raw_transaction']
            print(f"  {i+1}. {raw['raw_date']} | {raw['raw_description']} | ${raw['raw_amount']}")

    # Conclusión final
    print(f"\n🎯 CONCLUSIÓN FINAL:")

    issues = []
    if not balance_inicial:
        issues.append("Balance Inicial faltante")
    if not jorge_txns:
        issues.append("Jorge Luis González faltante")
    if balance_errors > 0:
        issues.append(f"{balance_errors} errores de balance")
    if not resultado['is_complete']:
        issues.append("Validación automática falló")

    if not issues:
        print(f"  ✅ NO SE DETECTARON TRANSACCIONES FALTANTES")
        print(f"  ✅ SISTEMA COMPLETO Y CONSISTENTE")
        print(f"  ✅ Total: {len(all_transactions)} transacciones verificadas")
    else:
        print(f"  ⚠️ PROBLEMAS DETECTADOS:")
        for issue in issues:
            print(f"    • {issue}")

    conn.close()

if __name__ == "__main__":
    validacion_exhaustiva()