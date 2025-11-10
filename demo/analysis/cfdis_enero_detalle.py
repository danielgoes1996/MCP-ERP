"""
CFDIs de ENERO 2025 - Detalle
Mostrar solo los de enero: conciliados vs disponibles
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

# CFDIs de ENERO 2025
cursor.execute("""
    SELECT
        ei.id,
        ei.uuid,
        ei.fecha_emision::DATE as fecha,
        ei.nombre_emisor,
        ei.total,
        (SELECT bt.id FROM bank_transactions bt WHERE bt.reconciled_invoice_id = ei.id LIMIT 1) as tx_id,
        (SELECT bt.description FROM bank_transactions bt WHERE bt.reconciled_invoice_id = ei.id LIMIT 1) as tx_description
    FROM expense_invoices ei
    WHERE ei.tipo_comprobante = 'I'
      AND ei.fecha_emision >= '2025-01-01'
      AND ei.fecha_emision < '2025-02-01'
    ORDER BY ei.fecha_emision DESC
""")

cfdis_enero = cursor.fetchall()

conciliados = [c for c in cfdis_enero if c['tx_id'] is not None]
disponibles = [c for c in cfdis_enero if c['tx_id'] is None]

print("\n" + "="*120)
print("📄 CFDIs DE ENERO 2025 - DETALLE COMPLETO")
print("="*120 + "\n")

print(f"Total CFDIs de ENERO: {len(cfdis_enero)}")
print(f"✅ Conciliados:       {len(conciliados)} ({len(conciliados)/len(cfdis_enero)*100:.1f}%)")
print(f"❌ Disponibles:       {len(disponibles)} ({len(disponibles)/len(cfdis_enero)*100:.1f}%)")
print()

# CONCILIADOS
print("="*120)
print(f"✅ CFDIs DE ENERO YA CONCILIADOS ({len(conciliados)})")
print("="*120 + "\n")

if conciliados:
    print(f"{'CFDI':<6} {'Fecha':<12} {'Emisor':<45} {'Total':>12} {'TX':<6} {'Descripción TX'}")
    print("-"*120)
    
    for c in sorted(conciliados, key=lambda x: x['fecha'], reverse=True):
        print(f"{c['id']:<6} {str(c['fecha']):<12} {c['nombre_emisor'][:45]:<45} "
              f"${float(c['total']):>10,.2f} TX-{c['tx_id']:<4} {(c['tx_description'] or '')[:40]}")
    
    total_conc = sum(float(c['total']) for c in conciliados)
    print("-"*120)
    print(f"{'TOTAL':<65} ${total_conc:>10,.2f}\n")

# DISPONIBLES
print("="*120)
print(f"❌ CFDIs DE ENERO SIN CONCILIAR ({len(disponibles)})")
print("="*120 + "\n")

if disponibles:
    print(f"{'CFDI':<6} {'Fecha':<12} {'Emisor':<50} {'Total':>12} {'Estado'}")
    print("-"*120)
    
    for c in sorted(disponibles, key=lambda x: float(x['total']), reverse=True):
        emisor = c['nombre_emisor'][:50]
        total = float(c['total'])
        
        # Buscar posible match en banco
        cursor.execute("""
            SELECT id, description, amount, transaction_date
            FROM bank_transactions
            WHERE transaction_type = 'debit'
              AND reconciled_invoice_id IS NULL
              AND ABS(ABS(amount) - %s) <= 100
              AND transaction_date BETWEEN %s::DATE - INTERVAL '5 days' 
                                      AND %s::DATE + INTERVAL '5 days'
            ORDER BY ABS(ABS(amount) - %s) ASC
            LIMIT 1
        """, (total, c['fecha'], c['fecha'], total))
        
        posible = cursor.fetchone()
        
        if posible:
            diff = abs(abs(posible['amount']) - total)
            estado = f"Posible TX-{posible['id']} (diff ${diff:.2f})"
        else:
            estado = "Sin TX en banco"
        
        print(f"{c['id']:<6} {str(c['fecha']):<12} {emisor:<50} ${total:>10,.2f} {estado}")
    
    total_disp = sum(float(c['total']) for c in disponibles)
    print("-"*120)
    print(f"{'TOTAL':<70} ${total_disp:>10,.2f}\n")

# ANÁLISIS
print("="*120)
print("📊 ANÁLISIS")
print("="*120 + "\n")

print("¿Por qué estos CFDIs de ENERO no están conciliados?\n")

print("1. CRITERIOS ESTRICTOS:")
print("   • Diferencia de monto > $10")
print("   • Diferencia de fecha > 5 días")
print("   • Descripción muy diferente\n")

print("2. POSIBLES SOLUCIONES:")
print("   a) Ejecutar matcher de embeddings (más flexible):")
print("      python3 test_embedding_matching.py\n")

print("   b) Conciliación manual para casos especiales:")
print("      • Gastos con propina/descuento")
print("      • Facturas con fecha diferente\n")

print("3. VERIFICAR SI SON GASTOS REALES:")
# Contar gastos reales sin CFDI
cursor.execute("""
    SELECT COUNT(*) as total
    FROM bank_transactions bt
    WHERE bt.transaction_type = 'debit'
      AND bt.transaction_date >= '2025-01-01'
      AND bt.transaction_date < '2025-02-01'
      AND bt.reconciled_invoice_id IS NULL
      AND NOT (
          bt.description ILIKE '%traspaso%' OR bt.description ILIKE '%spei%' OR 
          bt.description ILIKE '%comision%' OR bt.description ILIKE '%recarga%'
      )
""")

gastos_sin_cfdi = cursor.fetchone()['total']

print(f"   • Gastos bancarios sin CFDI: {gastos_sin_cfdi}")
print(f"   • CFDIs sin usar:            {len(disponibles)}")
print()

if gastos_sin_cfdi > len(disponibles):
    print(f"   ⚠️  Faltan {gastos_sin_cfdi - len(disponibles)} CFDIs por solicitar")
elif gastos_sin_cfdi < len(disponibles):
    print(f"   ⚠️  Hay {len(disponibles) - gastos_sin_cfdi} CFDIs de más")
    print(f"      (Pueden ser de otro mes o duplicados)")
else:
    print(f"   ✅ Números cuadran: {gastos_sin_cfdi} gastos = {len(disponibles)} CFDIs")

print("\n" + "="*120 + "\n")

cursor.close()
conn.close()
