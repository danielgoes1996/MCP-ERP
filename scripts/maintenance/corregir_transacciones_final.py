#!/usr/bin/env python3
"""
Corrección final: 40 abonos + 45 cargos + 1 balance = 86 total
"""

import sqlite3
import re

def analizar_estado_actual():
    """Analiza el estado actual y identifica duplicados"""

    print("🔍 ANÁLISIS DEL ESTADO ACTUAL")
    print("=" * 40)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Obtener todas las transacciones
    cursor.execute("""
        SELECT id, date, description, amount, raw_data, created_at
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    todas_transacciones = cursor.fetchall()

    print(f"📊 Total transacciones: {len(todas_transacciones)}")

    # Identificar duplicados por referencia
    referencias = {}
    duplicados = []

    for txn in todas_transacciones:
        txn_id, fecha, desc, amount, raw_data, created_at = txn

        # Extraer referencia del raw_data
        referencia = None
        if raw_data:
            # Buscar número de referencia
            ref_match = re.search(r'\d{8,}', raw_data)
            if ref_match:
                referencia = ref_match.group()

        if not referencia:
            # Para transacciones sin referencia clara, usar descripción + fecha
            referencia = f"{desc[:30]}_{fecha}"

        if referencia in referencias:
            # Es un duplicado
            duplicados.append({
                'referencia': referencia,
                'original_id': referencias[referencia]['id'],
                'duplicado_id': txn_id,
                'original_created': referencias[referencia]['created_at'],
                'duplicado_created': created_at,
                'descripcion': desc,
                'amount': amount
            })
        else:
            referencias[referencia] = {
                'id': txn_id,
                'created_at': created_at,
                'descripcion': desc,
                'amount': amount
            }

    print(f"🔍 Duplicados encontrados: {len(duplicados)}")

    if duplicados:
        print(f"\n📋 DUPLICADOS IDENTIFICADOS:")
        for i, dup in enumerate(duplicados):
            print(f"  {i+1}. Ref: {dup['referencia'][:20]} | IDs: {dup['original_id']} vs {dup['duplicado_id']} | ${dup['amount']}")

    conn.close()
    return duplicados

def identificar_depositos_spei_incorrectos():
    """Identifica DEPOSITOS SPEI que están marcados como negativos"""

    print(f"\n🔍 VERIFICANDO DEPOSITOS SPEI INCORRECTOS")
    print("=" * 45)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Buscar DEPOSITOS SPEI que están negativos
    cursor.execute("""
        SELECT id, date, description, amount
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
          AND description LIKE '%DEPOSITO SPEI%'
          AND amount < 0
        ORDER BY date ASC
    """)

    depositos_incorrectos = cursor.fetchall()

    print(f"📊 DEPOSITOS SPEI negativos (incorrectos): {len(depositos_incorrectos)}")

    if depositos_incorrectos:
        print(f"\n📋 DEPOSITOS SPEI A CORREGIR:")
        for i, (txn_id, fecha, desc, amount) in enumerate(depositos_incorrectos):
            print(f"  {i+1}. ID {txn_id} | {fecha} | ${amount} → ${abs(amount)} | {desc[:50]}")

    conn.close()
    return depositos_incorrectos

def eliminar_duplicados(duplicados):
    """Elimina las transacciones duplicadas (mantiene la más antigua)"""

    if not duplicados:
        print("✅ No hay duplicados que eliminar")
        return

    print(f"\n🗑️ ELIMINANDO {len(duplicados)} DUPLICADOS")
    print("=" * 40)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    eliminados = 0

    for dup in duplicados:
        try:
            # Mantener el original (más antiguo), eliminar el duplicado (más nuevo)
            cursor.execute("""
                DELETE FROM bank_movements
                WHERE id = ?
            """, (dup['duplicado_id'],))

            print(f"  ✅ Eliminado duplicado ID {dup['duplicado_id']} (mantenido {dup['original_id']})")
            eliminados += 1

        except Exception as e:
            print(f"  ❌ Error eliminando ID {dup['duplicado_id']}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ {eliminados} duplicados eliminados")

def corregir_depositos_spei(depositos_incorrectos):
    """Corrige el signo de los DEPOSITOS SPEI que están negativos"""

    if not depositos_incorrectos:
        print("✅ No hay DEPOSITOS SPEI que corregir")
        return

    print(f"\n🔧 CORRIGIENDO {len(depositos_incorrectos)} DEPOSITOS SPEI")
    print("=" * 50)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    corregidos = 0

    for txn_id, fecha, desc, amount in depositos_incorrectos:
        try:
            # Cambiar a positivo y actualizar tipo de transacción
            nuevo_amount = abs(amount)

            cursor.execute("""
                UPDATE bank_movements
                SET amount = ?,
                    transaction_type = 'credit',
                    movement_kind = 'ingreso'
                WHERE id = ?
            """, (nuevo_amount, txn_id))

            print(f"  ✅ ID {txn_id}: ${amount} → ${nuevo_amount}")
            corregidos += 1

        except Exception as e:
            print(f"  ❌ Error corrigiendo ID {txn_id}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ {corregidos} DEPOSITOS SPEI corregidos")

def verificar_resultado_final():
    """Verifica que tengamos exactamente 40 abonos + 45 cargos + 1 balance"""

    print(f"\n🎯 VERIFICACIÓN FINAL")
    print("=" * 30)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Contar por tipo
    cursor.execute("""
        SELECT
            CASE
                WHEN amount > 0 THEN 'ABONOS'
                WHEN amount < 0 THEN 'CARGOS'
                ELSE 'BALANCE_INICIAL'
            END as tipo,
            COUNT(*) as cantidad
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        GROUP BY tipo
        ORDER BY tipo
    """)

    resultados = cursor.fetchall()

    abonos = 0
    cargos = 0
    balance = 0
    total = 0

    print("📊 RESULTADO FINAL:")
    for tipo, cantidad in resultados:
        print(f"   {tipo}: {cantidad}")
        total += cantidad
        if tipo == 'ABONOS':
            abonos = cantidad
        elif tipo == 'CARGOS':
            cargos = cantidad
        else:
            balance = cantidad

    print(f"   TOTAL: {total}")

    print(f"\n📋 COMPARACIÓN CON OBJETIVO:")
    print(f"   Abonos - Objetivo: 40, Actual: {abonos} {'✅' if abonos == 40 else '❌'}")
    print(f"   Cargos - Objetivo: 45, Actual: {cargos} {'✅' if cargos == 45 else '❌'}")
    print(f"   Balance - Objetivo: 1, Actual: {balance} {'✅' if balance == 1 else '❌'}")
    print(f"   TOTAL - Objetivo: 86, Actual: {total} {'✅' if total == 86 else '❌'}")

    # Estado final
    if total == 86 and abonos == 40 and cargos == 45 and balance == 1:
        print(f"\n🎉 ¡PERFECTO! Sistema completo y correcto")
        print(f"✅ 40 abonos + 45 cargos + 1 balance = 86 transacciones")
    else:
        print(f"\n⚠️ Aún requiere ajustes:")
        if abonos != 40:
            diff = 40 - abonos
            print(f"   • {'Agregar' if diff > 0 else 'Quitar'} {abs(diff)} abonos")
        if cargos != 45:
            diff = 45 - cargos
            print(f"   • {'Agregar' if diff > 0 else 'Quitar'} {abs(diff)} cargos")

    conn.close()

    return total == 86 and abonos == 40 and cargos == 45 and balance == 1

def main():
    print("🎯 CORRECCIÓN FINAL: 40 ABONOS + 45 CARGOS + 1 BALANCE = 86")
    print("=" * 70)

    # Paso 1: Analizar duplicados
    duplicados = analizar_estado_actual()

    # Paso 2: Identificar DEPOSITOS SPEI incorrectos
    depositos_incorrectos = identificar_depositos_spei_incorrectos()

    # Paso 3: Eliminar duplicados
    eliminar_duplicados(duplicados)

    # Paso 4: Corregir signos de DEPOSITOS SPEI
    corregir_depositos_spei(depositos_incorrectos)

    # Paso 5: Verificar resultado final
    resultado_perfecto = verificar_resultado_final()

    if resultado_perfecto:
        print(f"\n🎉 ¡MISIÓN COMPLETADA!")
        print(f"✅ Sistema de transacciones perfecto: 40+45+1=86")
    else:
        print(f"\n🔧 Requiere ajustes adicionales")

if __name__ == "__main__":
    main()