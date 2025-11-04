#!/usr/bin/env python3
"""
Extraer texto del PDF real y validar contra BD
"""

import re
import sqlite3
from core.robust_pdf_parser import RobustPDFParser

def extraer_fechas_del_pdf_real():
    """Extrae fechas del PDF real subido"""

    # Usar el PDF más reciente
    pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    print(f"🔍 EXTRAYENDO TEXTO DEL PDF REAL")
    print(f"📄 Archivo: {pdf_path}")
    print("=" * 60)

    try:
        # Extraer texto usando el parser robusto
        parser = RobustPDFParser()
        texto_completo = parser.extract_text(pdf_path)

        print(f"✅ Texto extraído exitosamente")
        print(f"📏 Longitud del texto: {len(texto_completo)} caracteres")

        # Buscar todas las líneas que empiezan con fechas
        lineas = texto_completo.split('\n')
        fechas_encontradas = []

        # Patrones para fechas en primera columna (formato Inbursa)
        patrones = [
            r'^(JUL\.?\s+\d{1,2})',      # JUL. 01, JUL 01
            r'^(AGO\.?\s+\d{1,2})',      # AGO. 01, AGO 01
            r'^(SEP\.?\s+\d{1,2})',      # SEP. 01, SEP 01
            r'^(\d{1,2}\s+JUL\.?)',      # 01 JUL, 01 JUL.
            r'^(Balance\s+Inicial)',      # Balance Inicial
        ]

        print(f"\n📅 BUSCANDO FECHAS EN PRIMERA COLUMNA:")

        for num_linea, linea in enumerate(lineas, 1):
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue

            for patron in patrones:
                match = re.match(patron, linea_limpia, re.IGNORECASE)
                if match:
                    fecha_encontrada = match.group(1)
                    fechas_encontradas.append({
                        'linea': num_linea,
                        'fecha': fecha_encontrada,
                        'texto_completo': linea_limpia[:120]  # Primeros 120 caracteres
                    })
                    break

        print(f"📊 Total fechas encontradas: {len(fechas_encontradas)}")

        # Mostrar las primeras 10 fechas encontradas
        print(f"\n📋 PRIMERAS 10 FECHAS ENCONTRADAS:")
        for i, fecha_info in enumerate(fechas_encontradas[:10]):
            print(f"  {i+1:2d}. Línea {fecha_info['linea']:3d}: {fecha_info['fecha']:12} | {fecha_info['texto_completo']}")

        if len(fechas_encontradas) > 10:
            print(f"       ... y {len(fechas_encontradas) - 10} fechas más")

        # Mostrar las últimas 5 fechas
        print(f"\n📋 ÚLTIMAS 5 FECHAS ENCONTRADAS:")
        for i, fecha_info in enumerate(fechas_encontradas[-5:], len(fechas_encontradas)-4):
            print(f"  {i:2d}. Línea {fecha_info['linea']:3d}: {fecha_info['fecha']:12} | {fecha_info['texto_completo']}")

        return fechas_encontradas, texto_completo

    except Exception as e:
        print(f"❌ Error extrayendo PDF: {e}")
        return [], ""

def comparar_con_bd(fechas_pdf):
    """Compara las fechas del PDF con las transacciones en BD"""

    print(f"\n🔍 COMPARANDO CON BASE DE DATOS")
    print("=" * 40)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Obtener todas las transacciones de la cuenta
    cursor.execute("""
        SELECT id, date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    transacciones_bd = cursor.fetchall()

    print(f"📊 CONTEO FINAL:")
    print(f"   Fechas en PDF: {len(fechas_pdf)}")
    print(f"   Transacciones en BD: {len(transacciones_bd)}")
    print(f"   Diferencia: {abs(len(fechas_pdf) - len(transacciones_bd))}")

    if len(fechas_pdf) == len(transacciones_bd):
        print(f"   ✅ PERFECTO: Misma cantidad")
        print(f"   ✅ NO FALTAN TRANSACCIONES")
    elif len(fechas_pdf) > len(transacciones_bd):
        faltantes = len(fechas_pdf) - len(transacciones_bd)
        print(f"   ❌ FALTAN {faltantes} transacciones en BD")
        print(f"   🔧 Necesario agregar {faltantes} transacciones")
    else:
        extras = len(transacciones_bd) - len(fechas_pdf)
        print(f"   ⚠️ HAY {extras} transacciones extra en BD")
        print(f"   🔍 Revisar posibles duplicados")

    # Análisis por fecha
    print(f"\n📅 ANÁLISIS POR FECHAS:")

    # Contar fechas por día en PDF
    fechas_por_dia_pdf = {}
    for fecha_info in fechas_pdf:
        fecha = fecha_info['fecha']
        # Normalizar fecha
        if 'JUL' in fecha.upper():
            dia = re.search(r'\d{1,2}', fecha)
            if dia:
                dia_num = int(dia.group())
                fecha_normalizada = f"2025-07-{dia_num:02d}"
                fechas_por_dia_pdf[fecha_normalizada] = fechas_por_dia_pdf.get(fecha_normalizada, 0) + 1
        elif 'Balance Inicial' in fecha:
            fechas_por_dia_pdf['2025-07-01-balance'] = 1

    # Contar fechas por día en BD
    fechas_por_dia_bd = {}
    for txn in transacciones_bd:
        fecha = txn[1]  # date
        fechas_por_dia_bd[fecha] = fechas_por_dia_bd.get(fecha, 0) + 1

    # Comparar día por día
    print(f"   Días con discrepancias:")
    discrepancias = 0

    todas_las_fechas = set(list(fechas_por_dia_pdf.keys()) + list(fechas_por_dia_bd.keys()))
    for fecha in sorted(todas_las_fechas):
        if fecha == '2025-07-01-balance':
            continue  # Skip balance inicial

        count_pdf = fechas_por_dia_pdf.get(fecha, 0)
        count_bd = fechas_por_dia_bd.get(fecha, 0)

        if count_pdf != count_bd:
            discrepancias += 1
            print(f"     {fecha}: PDF={count_pdf}, BD={count_bd} (diff: {count_pdf - count_bd})")

    if discrepancias == 0:
        print(f"     ✅ No hay discrepancias por fecha")
    else:
        print(f"     ⚠️ {discrepancias} fechas con discrepancias")

    conn.close()

    return fechas_por_dia_pdf, fechas_por_dia_bd

def main():
    print("🎯 VALIDACIÓN DEFINITIVA: PDF REAL vs BASE DE DATOS")
    print("=" * 70)

    # Extraer fechas del PDF real
    fechas_pdf, texto_pdf = extraer_fechas_del_pdf_real()

    if not fechas_pdf:
        print("❌ No se pudieron extraer fechas del PDF")
        return

    # Comparar con BD
    fechas_pdf_dict, fechas_bd_dict = comparar_con_bd(fechas_pdf)

    print(f"\n🎯 CONCLUSIÓN FINAL:")

    total_pdf = len(fechas_pdf)

    # Contar transacciones en BD
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM bank_movements WHERE account_id = 5 AND user_id = 9")
    total_bd = cursor.fetchone()[0]
    conn.close()

    if total_pdf == total_bd:
        print(f"   ✅ SISTEMA COMPLETO")
        print(f"   ✅ {total_pdf} transacciones verificadas")
        print(f"   ✅ No se requiere acción")
    else:
        diferencia = abs(total_pdf - total_bd)
        print(f"   🚨 DISCREPANCIA CONFIRMADA")
        print(f"   📊 PDF: {total_pdf}, BD: {total_bd}")
        print(f"   🔧 Acción requerida: {'Agregar' if total_pdf > total_bd else 'Revisar'} {diferencia} transacciones")

if __name__ == "__main__":
    main()