#!/usr/bin/env python3
"""
Extraer fechas de emisión desde los XMLs y actualizar la BD
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

print("📅 EXTRAYENDO FECHAS DE EMISIÓN DESDE XMLs\n")

conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
cursor = conn.cursor()

# Obtener facturas
cursor.execute("""
    SELECT id, filename, raw_xml, total
    FROM expense_invoices
    WHERE raw_xml IS NOT NULL
    ORDER BY id;
""")

invoices = cursor.fetchall()
total_invoices = len(invoices)

print(f"📊 Procesando {total_invoices} facturas...\n")

ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}

updated_count = 0
by_month = defaultdict(lambda: {'count': 0, 'total': 0.0})

for idx, invoice in enumerate(invoices, 1):
    if idx % 50 == 0:
        print(f"   Procesando {idx}/{total_invoices}...")

    try:
        root = ET.fromstring(invoice['raw_xml'])

        # Extraer fecha del atributo Fecha del Comprobante
        fecha_str = root.get('Fecha')

        if fecha_str:
            # Parsear fecha (formato: 2025-04-21T05:29:56)
            fecha = datetime.fromisoformat(fecha_str)

            # Actualizar en BD
            cursor.execute("""
                UPDATE expense_invoices
                SET fecha_emision = %s
                WHERE id = %s;
            """, (fecha, invoice['id']))

            updated_count += 1

            # Acumular por mes
            mes_key = fecha.strftime('%Y-%m')
            by_month[mes_key]['count'] += 1
            by_month[mes_key]['total'] += float(invoice['total'])

    except Exception as e:
        print(f"   ⚠️  Error procesando {invoice['filename']}: {e}")

conn.commit()

print(f"\n✅ ACTUALIZACIÓN COMPLETADA:")
print(f"   • Facturas actualizadas: {updated_count}\n")

# Mostrar por mes
print("📊 FACTURAS POR MES:\n")

sorted_months = sorted(by_month.items(), reverse=True)

meses_es = {
    '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
    '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
    '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

for mes_key, data in sorted_months:
    año, mes = mes_key.split('-')
    mes_nombre = meses_es.get(mes, mes)
    count = data['count']
    total = data['total']
    promedio = total / count if count > 0 else 0

    print(f"{mes_nombre} {año}")
    print(f"   Facturas: {count}")
    print(f"   Total: ${total:,.2f} MXN")
    print(f"   Promedio: ${promedio:,.2f} MXN")
    print()

conn.close()
print("🎉 Proceso completado!")
