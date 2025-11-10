"""
Resumen Simple de Conciliación
Vista rápida de qué está conciliado y qué falta
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

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
        ei.nombre_emisor
    FROM bank_transactions bt
    LEFT JOIN expense_invoices ei ON bt.reconciled_invoice_id = ei.id
    WHERE bt.transaction_type = 'debit'
    ORDER BY bt.transaction_date DESC
""")

all_debits = cursor.fetchall()
gastos_reales = [tx for tx in all_debits if classify_transaction(tx['description']) == 'GASTO_REAL']
conciliados = [tx for tx in gastos_reales if tx['reconciled_invoice_id'] is not None]
pendientes = [tx for tx in gastos_reales if tx['reconciled_invoice_id'] is None]

monto_conciliado = sum(abs(tx['amount']) for tx in conciliados)
monto_pendiente = sum(abs(tx['amount']) for tx in pendientes)
tasa = (len(conciliados) / len(gastos_reales) * 100) if gastos_reales else 0

print("\n" + "="*120)
print("📊 RESUMEN DE CONCILIACIÓN - ENERO 2025")
print("="*120 + "\n")

print(f"🎯 TASA DE CONCILIACIÓN: {tasa:.1f}% ({len(conciliados)}/{len(gastos_reales)} gastos)")
print(f"💰 MONTO CONCILIADO:     ${monto_conciliado:,.2f} / ${monto_conciliado + monto_pendiente:,.2f} MXN\n")

print("="*120)
print(f"✅ CONCILIADOS ({len(conciliados)})                                   ❌ PENDIENTES ({len(pendientes)})")
print("="*120)

max_rows = max(len(conciliados), len(pendientes))

for i in range(max_rows):
    # Columna izquierda (conciliados)
    if i < len(conciliados):
        tx = conciliados[i]
        left = f"TX-{tx['id']:<3} ${abs(tx['amount']):>7,.2f} {tx['description'][:30]:<30}"
    else:
        left = " " * 55

    # Columna derecha (pendientes)
    if i < len(pendientes):
        tx = pendientes[i]
        right = f"TX-{tx['id']:<3} ${abs(tx['amount']):>7,.2f} {tx['description'][:35]:<35}"
    else:
        right = ""

    print(f"{left}     {right}")

print("="*120)
print(f"{'TOTAL:':<42} ${monto_conciliado:>7,.2f}     {'TOTAL:':<35} ${monto_pendiente:>7,.2f}")
print("="*120 + "\n")

print("💡 Para solicitar los CFDIs faltantes:")
print("   python3 generate_cfdi_request_emails.py\n")

cursor.close()
conn.close()
