#!/usr/bin/env python3
"""
Extraer información de proveedores desde los XMLs almacenados
y actualizar la base de datos
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

print("🔍 EXTRAYENDO INFORMACIÓN DE PROVEEDORES DESDE XMLs\n")

# Conectar a PostgreSQL
conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
cursor = conn.cursor()

# Obtener facturas con XML
cursor.execute("""
    SELECT id, filename, raw_xml, total
    FROM expense_invoices
    WHERE raw_xml IS NOT NULL
    ORDER BY id;
""")

invoices = cursor.fetchall()
total_invoices = len(invoices)

print(f"📊 Procesando {total_invoices} facturas...\n")

# Namespace CFDI 4.0
ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}

updated_count = 0
providers = defaultdict(lambda: {'count': 0, 'total': 0.0, 'facturas': []})

for idx, invoice in enumerate(invoices, 1):
    if idx % 50 == 0:
        print(f"   Procesando {idx}/{total_invoices}...")

    try:
        # Parse XML
        root = ET.fromstring(invoice['raw_xml'])

        # Extraer información del emisor
        emisor = root.find('cfdi:Emisor', ns)

        if emisor is not None:
            rfc_emisor = emisor.get('Rfc')
            nombre_emisor = emisor.get('Nombre')
            regimen_fiscal = emisor.get('RegimenFiscal')

            # Actualizar en base de datos
            cursor.execute("""
                UPDATE expense_invoices
                SET
                    rfc_emisor = %s,
                    nombre_emisor = %s,
                    regimen_fiscal = %s
                WHERE id = %s;
            """, (rfc_emisor, nombre_emisor, regimen_fiscal, invoice['id']))

            updated_count += 1

            # Acumular estadísticas
            if nombre_emisor:
                providers[nombre_emisor]['count'] += 1
                providers[nombre_emisor]['total'] += float(invoice['total'])
                providers[nombre_emisor]['rfc'] = rfc_emisor
                providers[nombre_emisor]['facturas'].append({
                    'filename': invoice['filename'],
                    'total': float(invoice['total'])
                })

    except Exception as e:
        print(f"   ⚠️  Error procesando {invoice['filename']}: {e}")

# Commit cambios
conn.commit()

print(f"\n✅ ACTUALIZACIÓN COMPLETADA:")
print(f"   • Facturas actualizadas: {updated_count}")
print(f"   • Proveedores únicos: {len(providers)}")

# Mostrar top 15 proveedores por gasto
print(f"\n📊 TOP 15 PROVEEDORES POR GASTO:\n")

sorted_providers = sorted(
    providers.items(),
    key=lambda x: x[1]['total'],
    reverse=True
)

for idx, (nombre, data) in enumerate(sorted_providers[:15], 1):
    rfc = data.get('rfc', 'N/A')
    count = data['count']
    total = data['total']
    promedio = total / count if count > 0 else 0

    print(f"{idx:2d}. {nombre[:50]}")
    print(f"    RFC: {rfc}")
    print(f"    Facturas: {count}")
    print(f"    Total gastado: ${total:,.2f} MXN")
    print(f"    Promedio/factura: ${promedio:,.2f} MXN")
    print()

# Verificar en base de datos
cursor.execute("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN rfc_emisor IS NOT NULL THEN 1 ELSE 0 END) as with_rfc,
        SUM(CASE WHEN nombre_emisor IS NOT NULL THEN 1 ELSE 0 END) as with_nombre
    FROM expense_invoices;
""")

stats = cursor.fetchone()

print(f"📊 ESTADÍSTICAS FINALES:")
print(f"   • Total facturas: {stats['total']}")
print(f"   • Con RFC emisor: {stats['with_rfc']} ({stats['with_rfc']/stats['total']*100:.1f}%)")
print(f"   • Con nombre emisor: {stats['with_nombre']} ({stats['with_nombre']/stats['total']*100:.1f}%)")

conn.close()
print("\n🎉 Proceso completado!")
