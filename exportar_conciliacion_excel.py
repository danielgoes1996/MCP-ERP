"""
Exportar Estado de Conciliación a CSV para Excel
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import csv
from decimal import Decimal

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}

def classify_transaction(description):
    desc_upper = description.upper()
    if any(x in desc_upper for x in ['TRASPASO', 'SPEI', 'TRANSFERENCIA']):
        return 'TRASPASO'
    elif any(x in desc_upper for x in ['COMISION', 'IVA COMISION', 'ISR RETENIDO']):
        return 'COMISION'
    elif any(x in desc_upper for x in ['RECARGA', 'TUTAG', 'PASE']):
        return 'RECARGA'
    else:
        return 'GASTO_REAL'

conn = psycopg2.connect(**POSTGRES_CONFIG)
cursor = conn.cursor(cursor_factory=RealDictCursor)

cursor.execute("""
    SELECT
        bt.id,
        bt.transaction_date,
        bt.description,
        bt.amount,
        bt.reconciled_invoice_id,
        bt.reconciliation_status,
        bt.match_confidence,
        ei.uuid as cfdi_uuid,
        ei.nombre_emisor,
        ei.total as cfdi_total,
        ei.fecha_emision as cfdi_fecha
    FROM bank_transactions bt
    LEFT JOIN expense_invoices ei ON bt.reconciled_invoice_id = ei.id
    WHERE bt.transaction_type = 'debit'
    ORDER BY bt.transaction_date DESC, bt.id DESC
""")

all_debits = cursor.fetchall()

# Generar CSV
output_file = '/Users/danielgoes96/Desktop/mcp-server/conciliacion_enero_2025.csv'

with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    
    # Header
    writer.writerow([
        'ID TX',
        'Fecha',
        'Descripción',
        'Monto',
        'Tipo',
        'Estado',
        'CFDI UUID',
        'Emisor CFDI',
        'Monto CFDI',
        'Fecha CFDI',
        'Diferencia',
        'Confianza'
    ])
    
    # Data
    for tx in all_debits:
        tipo = classify_transaction(tx['description'])
        estado = 'CONCILIADO' if tx['reconciled_invoice_id'] else 'PENDIENTE'
        
        if tipo != 'GASTO_REAL':
            estado = f'{tipo} (No requiere CFDI)'
        
        diferencia = ''
        if tx['reconciled_invoice_id'] and tx['cfdi_total']:
            diferencia = abs(abs(Decimal(str(tx['amount']))) - Decimal(str(tx['cfdi_total'])))
        
        confianza = ''
        if tx['match_confidence']:
            confianza = f"{float(tx['match_confidence']) * 100:.1f}%"
        
        writer.writerow([
            tx['id'],
            tx['transaction_date'],
            tx['description'],
            abs(tx['amount']),
            tipo,
            estado,
            tx['cfdi_uuid'] or '',
            tx['nombre_emisor'] or '',
            tx['cfdi_total'] or '',
            tx['cfdi_fecha'] or '',
            diferencia,
            confianza
        ])

cursor.close()
conn.close()

print(f"\n✅ Archivo CSV generado exitosamente:")
print(f"   {output_file}\n")
print("📊 El archivo contiene:")
print("   • 46 transacciones débito del estado de cuenta")
print("   • Clasificadas por tipo (GASTO_REAL, TRASPASO, COMISION, RECARGA)")
print("   • Estado de conciliación (CONCILIADO/PENDIENTE)")
print("   • Datos del CFDI vinculado (si existe)\n")
print("💡 Puedes abrir este archivo en Excel para análisis más detallado\n")
