#!/usr/bin/env python3
"""
Validador de fechas PDF - Cuenta fechas en primera columna vs transacciones en BD
Método más confiable para detectar transacciones faltantes
"""

import re
import sqlite3
from typing import List, Dict

def extraer_fechas_primera_columna(pdf_text: str) -> List[str]:
    """
    Extrae todas las fechas de la primera columna del PDF
    Patrones esperados: JUL. 01, JUL 01, 01 JUL, etc.
    """
    fechas_encontradas = []

    # Patrones para fechas en primera columna
    patrones_fecha = [
        # Formato Inbursa: JUL. 01, AGO. 15, etc.
        r'^((?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2})',

        # Formato alternativo: 01 JUL, 15 AGO, etc.
        r'^(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?)',

        # Formato numérico: 01/07/2024, 2024-07-01, etc.
        r'^(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        r'^(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
    ]

    lines = pdf_text.split('\n')

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        for patron in patrones_fecha:
            match = re.match(patron, line, re.IGNORECASE)
            if match:
                fecha_raw = match.group(1)
                fechas_encontradas.append({
                    'fecha_raw': fecha_raw,
                    'linea': line_num,
                    'texto_completo': line[:100]  # Primeros 100 caracteres
                })
                break  # Solo un patrón por línea

    return fechas_encontradas

def contar_transacciones_bd(account_id: int = 5, user_id: int = 9) -> Dict:
    """Cuenta transacciones en la base de datos"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Contar total
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM bank_movements
        WHERE account_id = ? AND user_id = ?
    """, (account_id, user_id))

    total_bd = cursor.fetchone()[0]

    # Contar por fecha
    cursor.execute("""
        SELECT date, COUNT(*) as count
        FROM bank_movements
        WHERE account_id = ? AND user_id = ?
        GROUP BY date
        ORDER BY date
    """, (account_id, user_id))

    fechas_bd = cursor.fetchall()

    # Excluir Balance Inicial del conteo (no aparece en PDF como transacción normal)
    cursor.execute("""
        SELECT COUNT(*) as balance_inicial_count
        FROM bank_movements
        WHERE account_id = ? AND user_id = ?
          AND description LIKE '%Balance Inicial%'
    """, (account_id, user_id))

    balance_inicial_count = cursor.fetchone()[0]

    conn.close()

    return {
        'total_bd': total_bd,
        'total_sin_balance_inicial': total_bd - balance_inicial_count,
        'fechas_bd': fechas_bd,
        'balance_inicial_count': balance_inicial_count
    }

def validar_fechas_vs_transacciones(pdf_text: str = None) -> Dict:
    """
    Validación principal: fechas en PDF vs transacciones en BD
    """

    print("🔍 VALIDACIÓN POR CONTEO DE FECHAS")
    print("=" * 50)

    # Si no hay PDF, usar texto simulado del período conocido
    if not pdf_text:
        print("📄 Usando texto PDF simulado (falta el PDF original):")

        # Simular líneas con fechas basadas en lo que sabemos
        pdf_text = """
        Movimientos del período:

        JUL. 01 12345678 OPENAI CHATGPT SUBSCRIPTION 378.85
        JUL. 01 87654321 SPEI RECIBIDO JORGE LUIS GONZALEZ 1,000.00
        JUL. 02 11111111 TRANSFERENCIA SPEI OPERACION 1,152.00
        JUL. 02 22222222 APPLE SERVICES BILLING 215.00
        JUL. 03 33333333 TRANSFERENCIA SPEI OPERACION 1,071.00
        JUL. 03 44444444 BUBBLE STARTER PLAN USD 603.48
        JUL. 04 55555555 STRIPE CARRETA VERDE 10.00
        JUL. 04 66666666 DOMICILIACION SERVICIOS 15,397.59
        JUL. 05 77777777 TRANSFERENCIA SPEI OPERACION 867.00
        ... (más transacciones hasta JUL. 31)
        """

    # Extraer fechas del PDF
    fechas_pdf = extraer_fechas_primera_columna(pdf_text)

    print(f"📅 FECHAS ENCONTRADAS EN PDF:")
    print(f"   Total fechas en primera columna: {len(fechas_pdf)}")

    if fechas_pdf:
        print(f"   Primeras 5 fechas encontradas:")
        for i, fecha in enumerate(fechas_pdf[:5]):
            print(f"     {i+1}. Línea {fecha['linea']}: {fecha['fecha_raw']} | {fecha['texto_completo']}")

        if len(fechas_pdf) > 5:
            print(f"     ... y {len(fechas_pdf) - 5} fechas más")

    # Contar transacciones en BD
    bd_info = contar_transacciones_bd()

    print(f"\n📊 TRANSACCIONES EN BASE DE DATOS:")
    print(f"   Total en BD: {bd_info['total_bd']}")
    print(f"   Balance Inicial: {bd_info['balance_inicial_count']} (no cuenta para PDF)")
    print(f"   Transacciones reales: {bd_info['total_sin_balance_inicial']}")
    print(f"   Fechas únicas en BD: {len(bd_info['fechas_bd'])}")

    # Comparación
    print(f"\n🔍 COMPARACIÓN:")
    fechas_pdf_count = len(fechas_pdf)
    transacciones_reales = bd_info['total_sin_balance_inicial']

    print(f"   Fechas en PDF: {fechas_pdf_count}")
    print(f"   Transacciones en BD: {transacciones_reales}")
    print(f"   Diferencia: {abs(fechas_pdf_count - transacciones_reales)}")

    # Análisis
    if fechas_pdf_count == transacciones_reales:
        print(f"   ✅ PERFECTO: Mismo número de fechas y transacciones")
        resultado = "completo"
    elif fechas_pdf_count > transacciones_reales:
        print(f"   ⚠️ FALTAN {fechas_pdf_count - transacciones_reales} transacciones en BD")
        resultado = "faltan_en_bd"
    else:
        print(f"   ⚠️ HAY {transacciones_reales - fechas_pdf_count} transacciones extra en BD")
        resultado = "extra_en_bd"

    # Mostrar distribución por fecha en BD
    print(f"\n📋 DISTRIBUCIÓN POR FECHA EN BD:")
    for fecha, count in bd_info['fechas_bd'][:10]:  # Primeras 10 fechas
        print(f"   {fecha}: {count} transacción(es)")

    if len(bd_info['fechas_bd']) > 10:
        print(f"   ... y {len(bd_info['fechas_bd']) - 10} fechas más")

    return {
        'fechas_pdf_count': fechas_pdf_count,
        'transacciones_bd_count': transacciones_reales,
        'total_bd_count': bd_info['total_bd'],
        'balance_inicial_count': bd_info['balance_inicial_count'],
        'diferencia': abs(fechas_pdf_count - transacciones_reales),
        'resultado': resultado,
        'fechas_pdf': fechas_pdf,
        'fechas_bd': bd_info['fechas_bd']
    }

def test_con_pdf_real():
    """
    Prueba con PDF real si está disponible
    """

    # Aquí podrías cargar el PDF real si lo tienes
    # pdf_path = "ruta_al_pdf_original.pdf"
    # if os.path.exists(pdf_path):
    #     with open(pdf_path, 'r') as f:
    #         pdf_content = f.read()
    #     return validar_fechas_vs_transacciones(pdf_content)

    return validar_fechas_vs_transacciones()

if __name__ == "__main__":
    print("🎯 VALIDADOR DE FECHAS PDF vs TRANSACCIONES BD")
    print("=" * 60)
    print("Método: Contar fechas en primera columna del PDF")
    print("Objetivo: Verificar que cada fecha = una transacción")
    print()

    resultado = test_con_pdf_real()

    print(f"\n🎯 CONCLUSIÓN FINAL:")
    if resultado['resultado'] == 'completo':
        print(f"   ✅ SISTEMA COMPLETO")
        print(f"   ✅ No faltan transacciones")
        print(f"   ✅ Conteo PDF = Conteo BD")
    else:
        print(f"   ⚠️ DISCREPANCIA DETECTADA")
        print(f"   📊 Revisar diferencia de {resultado['diferencia']} transacciones")
        print(f"   🔧 Acción: Verificar PDF original completo")