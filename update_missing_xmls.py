#!/usr/bin/env python3
"""
Actualizar raw_xml para facturas que no lo tienen
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

print("🔄 ACTUALIZACIÓN: Cargando XMLs faltantes para facturas existentes\n")

# Conectar a PostgreSQL
conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
cursor = conn.cursor()

# Obtener facturas sin XML
cursor.execute("""
    SELECT id, filename
    FROM expense_invoices
    WHERE raw_xml IS NULL OR raw_xml = ''
    ORDER BY id;
""")

invoices_without_xml = cursor.fetchall()
total_without_xml = len(invoices_without_xml)

print(f"📊 Encontradas {total_without_xml} facturas sin XML\n")

if total_without_xml == 0:
    print("✅ Todas las facturas ya tienen XML completo!")
    conn.close()
    exit(0)

# Buscar y actualizar XMLs
updated_count = 0
not_found_count = 0

for idx, invoice in enumerate(invoices_without_xml, 1):
    invoice_id = invoice['id']
    filename = invoice['filename']

    if idx % 10 == 0:
        print(f"   Procesando {idx}/{total_without_xml}...")

    try:
        # Buscar XML en test_invoices (recursivamente)
        xml_path = Path("test_invoices") / filename
        xml_content = None

        if xml_path.exists():
            xml_content = xml_path.read_text(encoding='utf-8')
        else:
            # Buscar recursivamente
            xml_files = list(Path("test_invoices").rglob(filename))
            if xml_files:
                xml_content = xml_files[0].read_text(encoding='utf-8')

        if xml_content:
            # Actualizar en base de datos
            cursor.execute("""
                UPDATE expense_invoices
                SET raw_xml = %s
                WHERE id = %s;
            """, (xml_content, invoice_id))

            updated_count += 1
        else:
            not_found_count += 1
            print(f"   ⚠️  XML no encontrado: {filename}")

    except Exception as e:
        print(f"   ❌ Error procesando {filename}: {e}")
        not_found_count += 1

# Commit cambios
conn.commit()

print(f"\n✅ ACTUALIZACIÓN COMPLETADA:")
print(f"   • Facturas actualizadas: {updated_count}")
print(f"   • XMLs no encontrados: {not_found_count}")

# Verificar resultados
cursor.execute("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN raw_xml IS NOT NULL AND raw_xml != '' THEN 1 ELSE 0 END) as with_xml,
        SUM(CASE WHEN raw_xml IS NULL OR raw_xml = '' THEN 1 ELSE 0 END) as without_xml
    FROM expense_invoices;
""")

stats = cursor.fetchone()

print(f"\n📊 ESTADÍSTICAS FINALES:")
print(f"   • Total facturas: {stats['total']}")
print(f"   • Con XML: {stats['with_xml']} ({stats['with_xml']/stats['total']*100:.1f}%)")
print(f"   • Sin XML: {stats['without_xml']}")

conn.close()
print("\n🎉 Proceso completado!")
