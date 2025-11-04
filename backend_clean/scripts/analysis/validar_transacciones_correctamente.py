#!/usr/bin/env python3
"""
Validación correcta: 1 fecha + 1 referencia = 1 transacción
(no cada línea individual)
"""

import re
import sqlite3
from core.robust_pdf_parser import RobustPDFParser

def extraer_transacciones_unicas_pdf():
    """
    Extrae transacciones únicas del PDF basándose en fecha + referencia
    """

    pdf_path = "./uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    print(f"🔍 ANÁLISIS CORRECTO: FECHA + REFERENCIA = 1 TRANSACCIÓN")
    print("=" * 65)

    try:
        parser = RobustPDFParser()
        texto_completo = parser.extract_text(pdf_path)

        lineas = texto_completo.split('\n')
        transacciones_unicas = []

        # Patrón para líneas que empiezan con fecha y tienen referencia completa
        # Formato: JUL. 01 1234567890 DESCRIPCION MONTO BALANCE
        patron_transaccion = r'^(JUL\.?\s+\d{1,2})\s+(\d{8,})\s+(.+?)(\d+[,\.]\d{2})\s+(\d+[,\.]\d{2})$'

        # Patrón para Balance Inicial
        patron_balance = r'^(JUL\.?\s+\d{1,2})\s+(BALANCE\s+INICIAL)\s+(\d+[,\.]\d{2})$'

        print(f"📋 BUSCANDO TRANSACCIONES COMPLETAS (FECHA + REFERENCIA):")

        for num_linea, linea in enumerate(lineas, 1):
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue

            # Buscar Balance Inicial
            match_balance = re.match(patron_balance, linea_limpia, re.IGNORECASE)
            if match_balance:
                fecha, descripcion, saldo = match_balance.groups()
                transacciones_unicas.append({
                    'linea': num_linea,
                    'fecha': fecha.strip(),
                    'referencia': 'BALANCE_INICIAL',
                    'descripcion': descripcion.strip(),
                    'monto': '0.00',
                    'saldo': saldo.replace(',', ''),
                    'texto_completo': linea_limpia
                })
                continue

            # Buscar transacciones normales
            match_txn = re.match(patron_transaccion, linea_limpia, re.IGNORECASE)
            if match_txn:
                fecha, referencia, descripcion, monto, saldo = match_txn.groups()
                transacciones_unicas.append({
                    'linea': num_linea,
                    'fecha': fecha.strip(),
                    'referencia': referencia.strip(),
                    'descripcion': descripcion.strip(),
                    'monto': monto.replace(',', ''),
                    'saldo': saldo.replace(',', ''),
                    'texto_completo': linea_limpia
                })

        print(f"📊 Total transacciones únicas encontradas: {len(transacciones_unicas)}")

        # Mostrar las primeras 10
        print(f"\n📋 PRIMERAS 10 TRANSACCIONES:")
        for i, txn in enumerate(transacciones_unicas[:10]):
            print(f"  {i+1:2d}. {txn['fecha']:8} | Ref: {txn['referencia'][:12]:12} | {txn['descripcion'][:40]:40} | ${txn['monto']:>8}")

        if len(transacciones_unicas) > 10:
            print(f"       ... y {len(transacciones_unicas) - 10} transacciones más")

        # Mostrar las últimas 5
        print(f"\n📋 ÚLTIMAS 5 TRANSACCIONES:")
        for i, txn in enumerate(transacciones_unicas[-5:], len(transacciones_unicas)-4):
            print(f"  {i:2d}. {txn['fecha']:8} | Ref: {txn['referencia'][:12]:12} | {txn['descripcion'][:40]:40} | ${txn['monto']:>8}")

        # Análisis por fecha
        fechas_count = {}
        for txn in transacciones_unicas:
            fecha_clean = txn['fecha'].replace('.', '').strip()
            dia = re.search(r'\d{1,2}', fecha_clean)
            if dia:
                dia_num = int(dia.group())
                fecha_key = f"JUL {dia_num:02d}"
                fechas_count[fecha_key] = fechas_count.get(fecha_key, 0) + 1

        print(f"\n📅 DISTRIBUCIÓN POR FECHA (PDF):")
        for fecha in sorted(fechas_count.keys()):
            print(f"   {fecha}: {fechas_count[fecha]} transacción(es)")

        return transacciones_unicas, fechas_count

    except Exception as e:
        print(f"❌ Error: {e}")
        return [], {}

def comparar_con_bd_correctamente(transacciones_pdf, fechas_pdf_count):
    """Compara las transacciones únicas del PDF con la BD"""

    print(f"\n🔍 COMPARACIÓN CORRECTA CON BASE DE DATOS")
    print("=" * 50)

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Obtener transacciones de BD
    cursor.execute("""
        SELECT date, description, amount, balance_after
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        ORDER BY date ASC, id ASC
    """)

    transacciones_bd = cursor.fetchall()

    # Agrupar BD por fecha
    fechas_bd_count = {}
    for txn in transacciones_bd:
        fecha_str = txn[0]  # 2025-07-01
        if fecha_str.startswith('2025-07-'):
            dia = fecha_str.split('-')[2]
            fecha_key = f"JUL {dia}"
            fechas_bd_count[fecha_key] = fechas_bd_count.get(fecha_key, 0) + 1

    print(f"📊 CONTEO CORRECTO:")
    print(f"   Transacciones únicas en PDF: {len(transacciones_pdf)}")
    print(f"   Transacciones en BD: {len(transacciones_bd)}")
    print(f"   Diferencia: {abs(len(transacciones_pdf) - len(transacciones_bd))}")

    # Comparación día por día
    print(f"\n📅 COMPARACIÓN POR FECHA:")
    todas_fechas = sorted(set(list(fechas_pdf_count.keys()) + list(fechas_bd_count.keys())))

    discrepancias = 0
    total_diferencia = 0

    for fecha in todas_fechas:
        count_pdf = fechas_pdf_count.get(fecha, 0)
        count_bd = fechas_bd_count.get(fecha, 0)
        diferencia = count_pdf - count_bd

        if diferencia != 0:
            discrepancias += 1
            total_diferencia += abs(diferencia)
            status = "❌" if diferencia != 0 else "✅"
            print(f"   {status} {fecha}: PDF={count_pdf}, BD={count_bd} (diff: {diferencia:+d})")
        else:
            print(f"   ✅ {fecha}: PDF={count_pdf}, BD={count_bd}")

    print(f"\n📊 RESUMEN:")
    print(f"   Fechas con discrepancias: {discrepancias}")
    print(f"   Total diferencias: {total_diferencia}")

    conn.close()

    return discrepancias, total_diferencia

def main():
    print("🎯 VALIDACIÓN CORRECTA: PDF vs BASE DE DATOS")
    print("=" * 60)
    print("Método: 1 fecha + 1 referencia = 1 transacción")
    print()

    # Extraer transacciones únicas del PDF
    transacciones_pdf, fechas_pdf_count = extraer_transacciones_unicas_pdf()

    if not transacciones_pdf:
        print("❌ No se pudieron extraer transacciones del PDF")
        return

    # Comparar con BD
    discrepancias, total_diferencia = comparar_con_bd_correctamente(transacciones_pdf, fechas_pdf_count)

    print(f"\n🎯 CONCLUSIÓN FINAL:")

    if total_diferencia == 0:
        print(f"   ✅ PERFECTO: Todas las transacciones coinciden")
        print(f"   ✅ {len(transacciones_pdf)} transacciones verificadas")
        print(f"   ✅ No faltan transacciones")
    else:
        print(f"   ⚠️ DISCREPANCIAS ENCONTRADAS")
        print(f"   📊 {discrepancias} fechas con diferencias")
        print(f"   🔢 Total diferencias: {total_diferencia}")
        print(f"   🔧 Revisión requerida")

if __name__ == "__main__":
    main()