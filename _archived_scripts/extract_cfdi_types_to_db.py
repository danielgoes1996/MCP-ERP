#!/usr/bin/env python3
"""
Extraer tipo de comprobante desde XMLs y actualizar BD
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import xml.etree.ElementTree as ET
from collections import defaultdict

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

print("📋 EXTRAYENDO TIPO DE COMPROBANTE DESDE XMLs\n")

conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
cursor = conn.cursor()

# Obtener facturas
cursor.execute("""
    SELECT id, filename, raw_xml, fecha_emision, total
    FROM expense_invoices
    WHERE raw_xml IS NOT NULL
    ORDER BY fecha_emision, id;
""")

invoices = cursor.fetchall()
total_invoices = len(invoices)

print(f"📊 Procesando {total_invoices} facturas...\n")

updated_count = 0
by_month_type = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'total': 0.0}))

tipos_cfdi = {
    'I': 'Ingreso',
    'P': 'Pago',
    'E': 'Egreso',
    'T': 'Traslado',
    'N': 'Nómina'
}

for idx, invoice in enumerate(invoices, 1):
    if idx % 50 == 0:
        print(f"   Procesando {idx}/{total_invoices}...")

    try:
        root = ET.fromstring(invoice['raw_xml'])

        # Extraer tipo de comprobante
        tipo = root.get('TipoDeComprobante', 'I')

        # Actualizar en BD
        cursor.execute("""
            UPDATE expense_invoices
            SET tipo_comprobante = %s
            WHERE id = %s;
        """, (tipo, invoice['id']))

        updated_count += 1

        # Acumular por mes/tipo
        if invoice['fecha_emision']:
            mes_key = invoice['fecha_emision'].strftime('%Y-%m')
            by_month_type[mes_key][tipo]['count'] += 1
            by_month_type[mes_key][tipo]['total'] += float(invoice['total'])

    except Exception as e:
        print(f"   ⚠️  Error procesando {invoice['filename']}: {e}")

conn.commit()

print(f"\n✅ ACTUALIZACIÓN COMPLETADA:")
print(f"   • Facturas actualizadas: {updated_count}\n")

# Mostrar reporte por mes
print("="*100)
print("📅 FACTURAS POR MES Y TIPO DE COMPROBANTE")
print("="*100 + "\n")

meses_es = {
    '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
    '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
    '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

for mes_key in sorted(by_month_type.keys(), reverse=True):
    año, mes = mes_key.split('-')
    mes_nombre = meses_es.get(mes, mes)

    print(f"{'='*100}")
    print(f"{mes_nombre.upper()} {año}")
    print(f"{'='*100}")

    tipos = by_month_type[mes_key]
    total_mes_count = sum(t['count'] for t in tipos.values())
    total_mes_monto = sum(t['total'] for t in tipos.values())

    for tipo in sorted(tipos.keys()):
        tipo_nombre = tipos_cfdi.get(tipo, f'Tipo {tipo}')
        data = tipos[tipo]
        count = data['count']
        total = data['total']
        promedio = total / count if count > 0 else 0

        print(f"\n   {tipo} - {tipo_nombre}:")
        print(f"      Cantidad: {count} facturas")
        print(f"      Total: ${total:,.2f} MXN")
        print(f"      Promedio: ${promedio:,.2f} MXN")

    print(f"\n   {'─'*96}")
    print(f"   TOTAL MES: {total_mes_count} facturas | ${total_mes_monto:,.2f} MXN")
    print()

# Resumen total
cursor.execute("""
    SELECT
        tipo_comprobante,
        COUNT(*) as cantidad,
        SUM(total) as total_monto
    FROM expense_invoices
    GROUP BY tipo_comprobante
    ORDER BY tipo_comprobante;
""")

totales = cursor.fetchall()

print("="*100)
print("📊 RESUMEN TOTAL POR TIPO")
print("="*100 + "\n")

for row in totales:
    tipo = row['tipo_comprobante'] or 'NULL'
    tipo_nombre = tipos_cfdi.get(tipo, f'Tipo {tipo}')
    cantidad = row['cantidad']
    total_monto = float(row['total_monto']) if row['total_monto'] else 0.0

    print(f"{tipo} - {tipo_nombre}:")
    print(f"   Cantidad: {cantidad} facturas")
    print(f"   Total: ${total_monto:,.2f} MXN")
    print()

conn.close()
print("🎉 Proceso completado!")
