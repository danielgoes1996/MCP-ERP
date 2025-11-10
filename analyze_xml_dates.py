#!/usr/bin/env python3
"""
Analizar fechas directamente desde los XMLs en el directorio
"""

from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict

print("🔍 ANALIZANDO XMLs DIRECTAMENTE DESDE ARCHIVOS\n")

xml_dir = Path("test_invoices/facturas_reales")
xml_files = list(xml_dir.rglob("*.xml"))

print(f"📊 Encontrados: {len(xml_files)} archivos XML\n")

ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}

by_month = defaultdict(lambda: {'count': 0, 'files': [], 'total': 0.0})
errors = []

for xml_file in xml_files:
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Extraer fecha
        fecha_str = root.get('Fecha')
        total_str = root.get('Total')

        if fecha_str:
            fecha = datetime.fromisoformat(fecha_str)
            mes_key = fecha.strftime('%Y-%m')

            total = float(total_str) if total_str else 0.0

            by_month[mes_key]['count'] += 1
            by_month[mes_key]['files'].append(xml_file.name)
            by_month[mes_key]['total'] += total

    except Exception as e:
        errors.append(f"{xml_file.name}: {e}")

print("📅 FACTURAS POR MES (desde archivos XML):\n")

sorted_months = sorted(by_month.items(), reverse=True)

meses_es = {
    '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
    '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
    '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

total_archivos = 0
total_monto = 0.0

for mes_key, data in sorted_months:
    año, mes = mes_key.split('-')
    mes_nombre = meses_es.get(mes, mes)
    count = data['count']
    total = data['total']

    total_archivos += count
    total_monto += total

    promedio = total / count if count > 0 else 0

    print(f"{mes_nombre} {año}")
    print(f"   Archivos XML: {count}")
    print(f"   Total: ${total:,.2f} MXN")
    print(f"   Promedio: ${promedio:,.2f} MXN")
    print()

print(f"📊 RESUMEN TOTAL:")
print(f"   Total archivos analizados: {total_archivos}")
print(f"   Monto total: ${total_monto:,.2f} MXN")

if errors:
    print(f"\n⚠️  Errores encontrados: {len(errors)}")
    for error in errors[:5]:
        print(f"   {error}")

# Mostrar detalle de enero
print("\n" + "="*80)
print("📋 DETALLE ENERO 2025:")
print("="*80)

enero_data = by_month.get('2025-01', {})
if enero_data.get('files'):
    print(f"\nTotal archivos en enero: {enero_data['count']}")
    print(f"Primeros 10 archivos:")
    for i, filename in enumerate(enero_data['files'][:10], 1):
        print(f"   {i}. {filename}")
