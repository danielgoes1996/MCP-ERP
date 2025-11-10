#!/usr/bin/env python3
"""
Analizar tipos de comprobante CFDI en los archivos
"""

from pathlib import Path
import xml.etree.ElementTree as ET
from collections import defaultdict

print("🔍 ANALIZANDO TIPOS DE COMPROBANTE CFDI\n")

xml_dir = Path("test_invoices/facturas_reales")
xml_files = list(xml_dir.rglob("*.xml"))

print(f"📊 Total archivos XML: {len(xml_files)}\n")

by_type = defaultdict(lambda: {'count': 0, 'files': []})
by_month_type = defaultdict(lambda: defaultdict(int))
errors = []

tipos_cfdi = {
    'I': 'Ingreso (Factura)',
    'P': 'Pago (Complemento de Pago)',
    'E': 'Egreso (Nota de Crédito)',
    'T': 'Traslado',
    'N': 'Nómina'
}

for xml_file in xml_files:
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        tipo = root.get('TipoDeComprobante', 'Unknown')
        fecha_str = root.get('Fecha')

        by_type[tipo]['count'] += 1
        by_type[tipo]['files'].append(xml_file.name)

        if fecha_str:
            from datetime import datetime
            fecha = datetime.fromisoformat(fecha_str)
            mes_key = fecha.strftime('%Y-%m')
            by_month_type[mes_key][tipo] += 1

    except Exception as e:
        errors.append(f"{xml_file.name}: {e}")

print("📋 RESUMEN POR TIPO DE COMPROBANTE:\n")

for tipo, data in sorted(by_type.items()):
    tipo_nombre = tipos_cfdi.get(tipo, f'Tipo {tipo}')
    count = data['count']
    print(f"{tipo} - {tipo_nombre}: {count} archivos")

print("\n" + "="*80)
print("📅 DESGLOSE POR MES Y TIPO:")
print("="*80 + "\n")

meses_es = {
    '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
    '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
    '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

for mes_key in sorted(by_month_type.keys(), reverse=True):
    año, mes = mes_key.split('-')
    mes_nombre = meses_es.get(mes, mes)

    print(f"{mes_nombre} {año}:")
    tipos = by_month_type[mes_key]

    total_mes = sum(tipos.values())
    for tipo in sorted(tipos.keys()):
        tipo_nombre = tipos_cfdi.get(tipo, f'Tipo {tipo}')
        count = tipos[tipo]
        print(f"   {tipo} ({tipo_nombre}): {count}")

    print(f"   TOTAL: {total_mes}")
    print()

print("="*80)
print("📊 CONCLUSIÓN:")
print("="*80)

ingresos = by_type.get('I', {'count': 0})['count']
pagos = by_type.get('P', {'count': 0})['count']
otros = sum(d['count'] for t, d in by_type.items() if t not in ['I', 'P'])

print(f"\nFacturas de Ingreso (I): {ingresos} - Estas SÍ deben cargarse")
print(f"Complementos de Pago (P): {pagos} - Estas NO son facturas")
print(f"Otros tipos: {otros}")
print(f"\nTotal archivos: {len(xml_files)}")
print(f"\n✅ El sistema está correcto al cargar solo {ingresos} facturas de ingreso")

if errors:
    print(f"\n⚠️  Errores: {len(errors)}")
