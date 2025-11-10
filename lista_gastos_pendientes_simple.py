"""
Lista Simple de Gastos Pendientes para Revisar
Formato tabla compacto para decidir rápido
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

conn = psycopg2.connect(**POSTGRES_CONFIG)
cursor = conn.cursor(cursor_factory=RealDictCursor)

cursor.execute("""
    SELECT
        bt.id,
        bt.transaction_date,
        bt.description,
        bt.amount
    FROM bank_transactions bt
    WHERE bt.transaction_type = 'debit'
      AND bt.reconciled_invoice_id IS NULL
      AND NOT (
          bt.description ILIKE '%traspaso%' OR bt.description ILIKE '%spei%' OR bt.description ILIKE '%transferencia%' OR
          bt.description ILIKE '%comision%' OR bt.description ILIKE '%iva comision%' OR bt.description ILIKE '%isr retenido%' OR
          bt.description ILIKE '%recarga%' OR bt.description ILIKE '%tutag%' OR bt.description ILIKE '%pase%'
      )
    ORDER BY ABS(bt.amount) DESC
""")

gastos = cursor.fetchall()

print("\n" + "="*140)
print("🔍 LISTA DE GASTOS PENDIENTES - Revisar si hay factura disponible")
print("="*140 + "\n")

print(f"Total: {len(gastos)} gastos sin conciliar\n")

print(f"{'#':<3} {'ID':<5} {'Fecha':<12} {'Monto':>12} {'Descripción':<50} {'Tipo':<20} {'Probabilidad CFDI'}")
print("-"*140)

for idx, tx in enumerate(gastos, 1):
    desc = tx['description']
    desc_upper = desc.upper()
    
    # Clasificar
    if any(x in desc_upper for x in ['ADOBE', 'APPLE', 'GOOGLE', 'SPOTIFY', 'GITHUB', 'TELCEL']):
        tipo = '💻 Suscripción'
        prob = '🟢 Alta'
    elif any(x in desc_upper for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO', 'CANCINO', 'GUERRAS']):
        tipo = '🍽️ Restaurante'
        prob = '🔴 Baja (si no pidió)'
    elif any(x in desc_upper for x in ['STRIPE', 'PAYPAL', 'CONEKTA']):
        tipo = '💳 Procesador'
        prob = '🟡 Media'
    else:
        tipo = '❓ Otros'
        prob = '🟡 Variable'
    
    print(f"{idx:<3} TX-{tx['id']:<3} {str(tx['transaction_date']):<12} ${abs(tx['amount']):>10,.2f} {desc[:50]:<50} {tipo:<20} {prob}")

print("-"*140)
print(f"\nTotal: ${sum(abs(tx['amount']) for tx in gastos):,.2f} MXN\n")

print("="*140)
print("INSTRUCCIONES:")
print("="*140)
print("Para cada gasto arriba, marca:")
print("  ✅ = Hay factura (subirla al sistema)")
print("  ❓ = Solicitar al proveedor")
print("  ❌ = No se puede obtener (anotar razón)")
print("="*140 + "\n")

# Agrupar por probabilidad
alta = [tx for tx in gastos if any(x in tx['description'].upper() for x in ['ADOBE', 'APPLE', 'GOOGLE', 'SPOTIFY', 'TELCEL'])]
media = [tx for tx in gastos if any(x in tx['description'].upper() for x in ['STRIPE', 'PAYPAL', 'CONEKTA', 'SQSP', 'DTM', 'CEA', 'MERCADO'])]
baja = [tx for tx in gastos if any(x in tx['description'].upper() for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO', 'GUERRAS'])]

print("📊 RESUMEN POR PROBABILIDAD:\n")
print(f"🟢 ALTA probabilidad ({len(alta)} gastos - ${sum(abs(tx['amount']) for tx in alta):,.2f}):")
print(f"   Suscripciones/Software con portales de facturación")
for tx in alta:
    print(f"   • TX-{tx['id']}: ${abs(tx['amount']):,.2f} - {tx['description'][:60]}")

print(f"\n🟡 MEDIA probabilidad ({len(media)} gastos - ${sum(abs(tx['amount']) for tx in media):,.2f}):")
print(f"   Requieren investigación (procesadores, otros)")
for tx in media:
    print(f"   • TX-{tx['id']}: ${abs(tx['amount']):,.2f} - {tx['description'][:60]}")

print(f"\n🔴 BAJA probabilidad ({len(baja)} gastos - ${sum(abs(tx['amount']) for tx in baja):,.2f}):")
print(f"   Difícil obtener si no se solicitó en el momento")
for tx in baja:
    print(f"   • TX-{tx['id']}: ${abs(tx['amount']):,.2f} - {tx['description'][:60]}")

otros = [tx for tx in gastos if tx not in alta and tx not in media and tx not in baja]
if otros:
    print(f"\n❓ OTROS ({len(otros)} gastos - ${sum(abs(tx['amount']) for tx in otros):,.2f}):")
    for tx in otros:
        print(f"   • TX-{tx['id']}: ${abs(tx['amount']):,.2f} - {tx['description'][:60]}")

print("\n" + "="*140 + "\n")

cursor.close()
conn.close()
