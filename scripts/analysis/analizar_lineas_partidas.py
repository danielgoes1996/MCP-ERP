#!/usr/bin/env python3
"""
Analizar por qué las transacciones se dividen en múltiples líneas
"""

import re

def analizar_transacciones_partidas():
    """Analiza las transacciones que se dividen en múltiples líneas"""

    print("🔍 ANALIZANDO TRANSACCIONES PARTIDAS")
    print("=" * 60)

    with open('chunk_1_llm_input.txt', 'r', encoding='utf-8') as f:
        contenido = f.read()

    lineas = contenido.split('\n')

    transacciones_partidas = []
    transacciones_completas = []

    i = 0
    while i < len(lineas):
        linea = lineas[i].strip()

        # Si encuentra una transacción que empieza con JUL. DD + referencia
        if re.match(r'^JUL\.\s+\d{1,2}\s+\d{8,}', linea):
            transaccion_completa = [linea]
            j = i + 1

            # Revisar las siguientes líneas para ver si son continuación
            while j < len(lineas) and j < i + 5:  # Máximo 5 líneas adelante
                siguiente = lineas[j].strip()

                # Si la siguiente línea no empieza con JUL. y no está vacía, puede ser continuación
                if siguiente and not siguiente.startswith('JUL.') and not siguiente.startswith('---'):
                    # Verificar si parece ser continuación de la transacción
                    if (re.match(r'^\d+\.?\d*$', siguiente) or  # Solo números
                        'USD' in siguiente or 'TC' in siguiente or  # Monedas
                        len(siguiente) < 50):  # Líneas cortas probables continuaciones
                        transaccion_completa.append(siguiente)
                        j += 1
                    else:
                        break
                else:
                    break

            if len(transaccion_completa) > 1:
                transacciones_partidas.append({
                    'linea_inicio': i + 1,
                    'lineas': transaccion_completa,
                    'total_lineas': len(transaccion_completa)
                })
            else:
                transacciones_completas.append({
                    'linea': i + 1,
                    'texto': linea
                })

            i = j
        else:
            i += 1

    print(f"📊 RESULTADOS:")
    print(f"   Transacciones COMPLETAS (1 línea): {len(transacciones_completas)}")
    print(f"   Transacciones PARTIDAS (múltiples líneas): {len(transacciones_partidas)}")

    print(f"\n🔍 EJEMPLOS DE TRANSACCIONES PARTIDAS:")
    for idx, txn in enumerate(transacciones_partidas[:10]):
        print(f"\n  {idx+1}. Línea {txn['linea_inicio']} ({txn['total_lineas']} líneas):")
        for linea in txn['lineas']:
            print(f"     '{linea}'")

        # Mostrar cómo debería verse unida
        linea_unida = ' '.join(txn['lineas'])
        print(f"     UNIDA: '{linea_unida}'")

    print(f"\n🔍 EJEMPLOS DE TRANSACCIONES COMPLETAS:")
    for idx, txn in enumerate(transacciones_completas[:5]):
        print(f"  {idx+1}. Línea {txn['linea']}: {txn['texto'][:80]}...")

    return transacciones_partidas, transacciones_completas

def identificar_patron_division():
    """Identifica el patrón de por qué se dividen las transacciones"""

    print(f"\n🔍 IDENTIFICANDO PATRÓN DE DIVISIÓN")
    print("=" * 50)

    transacciones_partidas, _ = analizar_transacciones_partidas()

    patrones_division = {
        'numeros_separados': 0,
        'usd_separado': 0,
        'tc_separado': 0,
        'saldo_separado': 0,
        'descripcion_larga': 0
    }

    for txn in transacciones_partidas:
        lineas = txn['lineas']

        for i, linea in enumerate(lineas[1:], 1):  # Saltar la primera línea
            if re.match(r'^\d+\.?\d*$', linea):
                patrones_division['numeros_separados'] += 1
            elif 'USD' in linea:
                patrones_division['usd_separado'] += 1
            elif 'TC' in linea:
                patrones_division['tc_separado'] += 1
            elif len(linea) > 30:
                patrones_division['descripcion_larga'] += 1
            else:
                patrones_division['saldo_separado'] += 1

    print(f"📊 PATRONES DE DIVISIÓN ENCONTRADOS:")
    for patron, count in patrones_division.items():
        print(f"   {patron}: {count} casos")

    print(f"\n🔧 CAUSA PROBABLE:")
    print(f"   • El PDF tiene texto en columnas/celdas")
    print(f"   • El parser PDF extrae celda por celda, no fila completa")
    print(f"   • Las transacciones se fragmentan en múltiples líneas")
    print(f"   • El LLM no puede reconstruir la transacción completa")

def proponer_solucion():
    """Propone una solución para unir las líneas fragmentadas"""

    print(f"\n💡 SOLUCIÓN PROPUESTA:")
    print("=" * 30)

    print(f"✅ IMPLEMENTAR FUNCIÓN DE RECONSTITUCIÓN:")
    print(f"   1. Detectar líneas que empiecen con 'JUL. DD + referencia'")
    print(f"   2. Capturar las siguientes 2-3 líneas como continuación")
    print(f"   3. Unir todas las líneas en una sola transacción")
    print(f"   4. Limpiar espacios y formatear correctamente")
    print(f"   5. Enviar al LLM transacciones completas y limpias")

    print(f"\n🎯 BENEFICIOS ESPERADOS:")
    print(f"   • Transacciones completas en una sola línea")
    print(f"   • LLM puede procesarlas correctamente")
    print(f"   • Se recuperan las 5+ transacciones faltantes")
    print(f"   • Mejor precisión en extracción")

if __name__ == "__main__":
    transacciones_partidas, transacciones_completas = analizar_transacciones_partidas()
    identificar_patron_division()
    proponer_solucion()

    print(f"\n🎯 RESUMEN FINAL:")
    print(f"   Transacciones partidas: {len(transacciones_partidas)}")
    print(f"   Transacciones completas: {len(transacciones_completas)}")
    print(f"   Problema: PDF parser divide transacciones en múltiples líneas")
    print(f"   Solución: Implementar reconstitución de líneas antes de enviar al LLM")