#!/usr/bin/env python3
"""
Analizar las tablas duplicadas que causan confusión al LLM
"""

import re

def analizar_patron_paginas():
    """Analiza el patrón de páginas y tablas duplicadas"""

    print("🔍 ANALIZANDO TABLAS DUPLICADAS EN CHUNKS")
    print("=" * 60)

    # Leer el chunk 1
    with open('chunk_1_llm_input.txt', 'r', encoding='utf-8') as f:
        contenido = f.read()

    lineas = contenido.split('\n')

    # Buscar patrones de páginas
    paginas_encontradas = []
    tablas_duplicadas = []
    transacciones_reales = []

    for i, linea in enumerate(lineas):
        linea_clean = linea.strip()

        # Detectar inicio de página
        if '--- PÁGINA' in linea_clean:
            paginas_encontradas.append((i+1, linea_clean))

        # Detectar transacciones reales (con número de referencia)
        if re.match(r'^JUL\.\s+\d{1,2}\s+\d{8,}', linea_clean):
            transacciones_reales.append((i+1, linea_clean))

        # Detectar líneas solo con fechas (probables duplicados)
        if re.match(r'^JUL\.\s+\d{1,2}\s*$', linea_clean):
            tablas_duplicadas.append((i+1, linea_clean))

    print(f"📊 RESULTADOS DEL ANÁLISIS:")
    print(f"   Páginas detectadas: {len(paginas_encontradas)}")
    print(f"   Transacciones reales: {len(transacciones_reales)}")
    print(f"   Líneas JUL. sin datos: {len(tablas_duplicadas)}")

    print(f"\n📄 PÁGINAS ENCONTRADAS:")
    for line_num, texto in paginas_encontradas:
        print(f"   Línea {line_num:4d}: {texto}")

    print(f"\n🔍 PRIMERAS 10 TRANSACCIONES REALES:")
    for line_num, texto in transacciones_reales[:10]:
        print(f"   Línea {line_num:4d}: {texto[:80]}...")

    print(f"\n⚠️ LÍNEAS PROBLEMÁTICAS (solo fecha):")
    for line_num, texto in tablas_duplicadas[:15]:
        print(f"   Línea {line_num:4d}: '{texto}'")

    # Analizar contexto de las líneas problemáticas
    print(f"\n🔍 CONTEXTO DE LÍNEAS PROBLEMÁTICAS:")
    for line_num, texto in tablas_duplicadas[:5]:
        print(f"\n--- CONTEXTO LÍNEA {line_num} ---")
        start = max(0, line_num - 6)
        end = min(len(lineas), line_num + 3)

        for j in range(start, end):
            marker = ">>>" if j == line_num - 1 else "   "
            print(f"{marker} {j+1:4d}: {lineas[j]}")

    return len(transacciones_reales), len(tablas_duplicadas)

def analizar_patron_repeticion():
    """Analiza si hay patrones de repetición en las tablas"""

    print(f"\n🔍 ANALIZANDO PATRONES DE REPETICIÓN")
    print("=" * 50)

    with open('chunk_1_llm_input.txt', 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Buscar secciones repetidas
    lineas = contenido.split('\n')

    # Buscar bloques que empiecen con fechas similares
    bloques_fecha = {}

    for i, linea in enumerate(lineas):
        linea_clean = linea.strip()

        # Si encuentra una fecha al inicio de línea
        match = re.match(r'^(JUL\.\s+\d{1,2})', linea_clean)
        if match:
            fecha = match.group(1)

            if fecha not in bloques_fecha:
                bloques_fecha[fecha] = []

            bloques_fecha[fecha].append((i+1, linea_clean))

    print(f"📊 FECHAS DUPLICADAS:")
    for fecha, ocurrencias in bloques_fecha.items():
        if len(ocurrencias) > 1:
            print(f"\n🔄 Fecha '{fecha}' aparece {len(ocurrencias)} veces:")
            for line_num, texto in ocurrencias:
                tipo = "REAL" if re.search(r'\d{8,}', texto) else "VACIA"
                print(f"   Línea {line_num:4d} [{tipo:5}]: {texto[:60]}...")

def identificar_problema_llm():
    """Identifica el problema específico para el LLM"""

    print(f"\n🎯 IDENTIFICANDO PROBLEMA PARA EL LLM")
    print("=" * 50)

    transacciones_reales, lineas_vacias = analizar_patron_paginas()

    print(f"\n📊 PROBLEMA IDENTIFICADO:")
    print(f"   ✅ Transacciones completas: {transacciones_reales}")
    print(f"   ❌ Líneas solo con fecha: {lineas_vacias}")
    print(f"   🔍 Total líneas JUL.: {transacciones_reales + lineas_vacias}")

    print(f"\n🔧 CAUSA DEL PROBLEMA:")
    print(f"   • El PDF contiene tablas de encabezado repetidas en cada página")
    print(f"   • Estas tablas tienen solo fechas sin datos de transacción")
    print(f"   • El LLM ve {lineas_vacias} líneas 'JUL.' inválidas")
    print(f"   • Esto confunde al LLM y puede descartar transacciones válidas")

    print(f"\n💡 SOLUCIÓN PROPUESTA:")
    print(f"   1. Filtrar líneas que solo contengan 'JUL. DD' sin datos")
    print(f"   2. Limpiar el texto antes de enviarlo al LLM")
    print(f"   3. Conservar solo transacciones con número de referencia")

    return transacciones_reales, lineas_vacias

if __name__ == "__main__":
    transacciones_reales, lineas_vacias = identificar_problema_llm()

    print(f"\n🎯 RESUMEN FINAL:")
    print(f"   Transacciones válidas en chunk 1: {transacciones_reales}")
    print(f"   Líneas problemáticas: {lineas_vacias}")
    print(f"   Diferencia explicada: {lineas_vacias} líneas confunden al LLM")