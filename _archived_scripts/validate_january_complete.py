#!/usr/bin/env python3
"""
Validación completa: Comparar XMLs de enero vs Base de Datos
Verificar que todos los documentos fueron procesados correctamente
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
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

print("=" * 100)
print("🔍 VALIDACIÓN COMPLETA: ENERO 2025")
print("=" * 100 + "\n")

# ========================================
# PASO 1: Analizar archivos XML físicos
# ========================================
print("📂 PASO 1: Analizando archivos XML en directorio...\n")

xml_dir = Path("test_invoices")
xml_files = list(xml_dir.rglob("*.xml"))

# Analizar cada XML
files_by_month_type = defaultdict(lambda: defaultdict(list))
errors = []

for xml_file in xml_files:
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        tipo = root.get('TipoDeComprobante', 'Unknown')
        fecha_str = root.get('Fecha')
        total_str = root.get('Total', '0')
        uuid_str = root.get('UUID')

        # Buscar UUID en complemento si no está en root
        if not uuid_str:
            ns = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
            complemento = root.find('.//tfd:TimbreFiscalDigital', ns)
            if complemento is not None:
                uuid_str = complemento.get('UUID')

        if fecha_str:
            fecha = datetime.fromisoformat(fecha_str)
            mes_key = fecha.strftime('%Y-%m')

            if mes_key == '2025-01':
                files_by_month_type[mes_key][tipo].append({
                    'filename': xml_file.name,
                    'uuid': uuid_str,
                    'total': float(total_str),
                    'fecha': fecha
                })

    except Exception as e:
        errors.append(f"{xml_file.name}: {e}")

# Reporte de archivos físicos
print("📊 ARCHIVOS XML FÍSICOS EN ENERO 2025:\n")

tipos_cfdi = {
    'I': 'Ingreso (Factura)',
    'P': 'Pago (Complemento)',
    'E': 'Egreso (Nota Crédito)',
    'T': 'Traslado',
    'N': 'Nómina'
}

enero_data = files_by_month_type.get('2025-01', {})
total_enero_files = sum(len(docs) for docs in enero_data.values())

print(f"Total documentos en enero: {total_enero_files}\n")

for tipo in sorted(enero_data.keys()):
    tipo_nombre = tipos_cfdi.get(tipo, f'Tipo {tipo}')
    docs = enero_data[tipo]
    total_tipo = sum(d['total'] for d in docs)

    print(f"   {tipo} - {tipo_nombre}:")
    print(f"      Cantidad: {len(docs)} documentos")
    print(f"      Total: ${total_tipo:,.2f} MXN")
    print()

# ========================================
# PASO 2: Verificar en Base de Datos
# ========================================
print("=" * 100)
print("💾 PASO 2: Verificando en Base de Datos PostgreSQL...\n")

conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
cursor = conn.cursor()

# Contar facturas de enero en BD
cursor.execute("""
    SELECT
        tipo_comprobante,
        COUNT(*) as cantidad,
        SUM(total) as total_monto,
        COUNT(CASE WHEN raw_xml IS NOT NULL THEN 1 END) as con_xml
    FROM expense_invoices
    WHERE fecha_emision >= '2025-01-01'
      AND fecha_emision < '2025-02-01'
    GROUP BY tipo_comprobante
    ORDER BY tipo_comprobante;
""")

db_results = cursor.fetchall()

print("📊 FACTURAS EN BASE DE DATOS (ENERO 2025):\n")

total_db_count = 0
for row in db_results:
    tipo = row['tipo_comprobante'] or 'NULL'
    tipo_nombre = tipos_cfdi.get(tipo, f'Tipo {tipo}')
    cantidad = row['cantidad']
    total_monto = float(row['total_monto']) if row['total_monto'] else 0.0
    con_xml = row['con_xml']

    total_db_count += cantidad

    print(f"   {tipo} - {tipo_nombre}:")
    print(f"      Cantidad: {cantidad} facturas")
    print(f"      Total: ${total_monto:,.2f} MXN")
    print(f"      Con XML: {con_xml} ({con_xml/cantidad*100:.0f}%)")
    print()

print(f"Total en BD: {total_db_count} facturas\n")

# ========================================
# PASO 3: Verificar logs de importación
# ========================================
print("=" * 100)
print("📋 PASO 3: Verificando logs de importación...\n")

cursor.execute("""
    SELECT
        status,
        COUNT(*) as cantidad
    FROM invoice_import_logs
    WHERE import_date >= '2025-01-01'
      AND import_date < '2025-02-01'
    GROUP BY status
    ORDER BY status;
""")

log_results = cursor.fetchall()

print("📊 LOGS DE IMPORTACIÓN (ENERO 2025):\n")

for row in log_results:
    status = row['status']
    cantidad = row['cantidad']
    print(f"   {status}: {cantidad} documentos")

print()

# ========================================
# PASO 4: Verificar items procesados
# ========================================
print("=" * 100)
print("⚙️  PASO 4: Verificando items procesados en batches...\n")

cursor.execute("""
    SELECT
        item_status,
        error_code,
        COUNT(*) as cantidad
    FROM bulk_invoice_batch_items
    WHERE created_at >= '2025-01-01'
      AND created_at < '2025-02-01'
    GROUP BY item_status, error_code
    ORDER BY item_status, error_code;
""")

batch_items = cursor.fetchall()

print("📊 ITEMS EN BATCHES (ENERO 2025):\n")

for row in batch_items:
    item_status = row['item_status']
    error_code = row['error_code'] or '-'
    cantidad = row['cantidad']
    print(f"   {item_status:12} | Error: {error_code:20} | {cantidad} items")

print()

# ========================================
# PASO 5: Reconciliación final
# ========================================
print("=" * 100)
print("🔎 PASO 5: RECONCILIACIÓN FINAL\n")
print("=" * 100 + "\n")

# Conteo por tipo en archivos
tipo_i_files = len(enero_data.get('I', []))
tipo_p_files = len(enero_data.get('P', []))
tipo_e_files = len(enero_data.get('E', []))

# Buscar cuántos tipo I están en BD
cursor.execute("""
    SELECT COUNT(*) as count
    FROM expense_invoices
    WHERE tipo_comprobante = 'I'
      AND fecha_emision >= '2025-01-01'
      AND fecha_emision < '2025-02-01';
""")
tipo_i_db = cursor.fetchone()['count']

# Buscar cuántos tipo P fueron rechazados
cursor.execute("""
    SELECT COUNT(*) as count
    FROM bulk_invoice_batch_items
    WHERE error_code = 'INVALID_AMOUNT'
      AND created_at >= '2025-01-01'
      AND created_at < '2025-02-01';
""")
tipo_p_rejected = cursor.fetchone()['count']

print(f"📄 ARCHIVOS XML:")
print(f"   Tipo I (Ingreso):          {tipo_i_files} archivos")
print(f"   Tipo P (Pago):             {tipo_p_files} archivos")
print(f"   Tipo E (Egreso):           {tipo_e_files} archivos")
print(f"   TOTAL:                     {total_enero_files} archivos")
print()

print(f"💾 BASE DE DATOS:")
print(f"   Tipo I insertados:         {tipo_i_db} facturas")
print(f"   TOTAL en BD:               {total_db_count} facturas")
print()

print(f"⚠️  RECHAZADOS:")
print(f"   Tipo P (total=0):          {tipo_p_rejected} documentos")
print()

# Verificación de consistencia
print("=" * 100)
print("✅ VERIFICACIÓN DE CONSISTENCIA:")
print("=" * 100 + "\n")

# Check 1: Todos los tipo I deberían estar en BD
if tipo_i_files == tipo_i_db:
    print(f"✅ CORRECTO: Los {tipo_i_files} documentos tipo I (Ingreso) están en la BD")
else:
    print(f"⚠️  DISCREPANCIA: {tipo_i_files} archivos tipo I vs {tipo_i_db} en BD")

# Check 2: Todos los tipo P deberían estar rechazados
if tipo_p_files == tipo_p_rejected:
    print(f"✅ CORRECTO: Los {tipo_p_files} complementos de pago fueron rechazados (total=0)")
else:
    print(f"⚠️  DISCREPANCIA: {tipo_p_files} archivos tipo P vs {tipo_p_rejected} rechazados")

# Check 3: Total procesado
total_processed = tipo_i_db + tipo_p_rejected
if total_processed == total_enero_files:
    print(f"✅ CORRECTO: Los {total_enero_files} documentos fueron procesados")
else:
    print(f"⚠️  DISCREPANCIA: {total_enero_files} archivos vs {total_processed} procesados")

print()

# ========================================
# PASO 6: Listar UUIDs para verificación
# ========================================
print("=" * 100)
print("🔍 PASO 6: VERIFICACIÓN POR UUID (muestra)\n")
print("=" * 100 + "\n")

print("📄 PRIMEROS 5 TIPO I (deben estar en BD):\n")
tipo_i_docs = enero_data.get('I', [])[:5]
for doc in tipo_i_docs:
    uuid = doc['uuid']

    # Buscar en BD
    cursor.execute("""
        SELECT id, filename, total, tipo_comprobante
        FROM expense_invoices
        WHERE uuid = %s;
    """, (uuid,))

    db_record = cursor.fetchone()

    status = "✅ EN BD" if db_record else "❌ FALTA"
    print(f"   {status} | {doc['filename'][:40]:40} | UUID: {uuid}")

print("\n📄 PRIMEROS 5 TIPO P (deben estar rechazados):\n")
tipo_p_docs = enero_data.get('P', [])[:5]
for doc in tipo_p_docs:
    uuid = doc['uuid'] if doc['uuid'] else doc['filename']

    # Buscar en batch items
    cursor.execute("""
        SELECT filename, item_status, error_code
        FROM bulk_invoice_batch_items
        WHERE filename = %s
        ORDER BY created_at DESC
        LIMIT 1;
    """, (doc['filename'],))

    batch_record = cursor.fetchone()

    if batch_record and batch_record['error_code'] == 'INVALID_AMOUNT':
        status = "✅ RECHAZADO"
    else:
        status = "❌ NO PROCESADO"

    print(f"   {status} | {doc['filename'][:40]:40} | Total: ${doc['total']:.2f}")

conn.close()

print("\n" + "=" * 100)
print("🎉 VALIDACIÓN COMPLETADA")
print("=" * 100)
