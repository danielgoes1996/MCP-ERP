"""
Reporte CORRECTO de conciliación
Separa: Gastos reales, Traspasos, Recargas, Comisiones
Solo calcula tasa sobre GASTOS REALES que necesitan CFDI
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
    """Clasifica una transacción por tipo"""
    desc_upper = description.upper()

    if any(x in desc_upper for x in ['TRASPASO', 'SPEI', 'TRANSFERENCIA']):
        return 'TRASPASO'
    elif any(x in desc_upper for x in ['COMISION', 'IVA COMISION', 'ISR RETENIDO']):
        return 'COMISION'
    elif any(x in desc_upper for x in ['RECARGA', 'TUTAG', 'PASE']):
        return 'RECARGA'
    else:
        return 'GASTO_REAL'


def main():
    print("\n" + "="*120)
    print("📊 REPORTE CORRECTO DE CONCILIACIÓN - ENERO 2025")
    print("="*120 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Obtener todas las transacciones débito
        cursor.execute("""
            WITH best_matches AS (
              SELECT
                vr.transaction_id,
                vr.invoice_id,
                vr.nombre_emisor,
                vr.amount_difference,
                vr.days_difference,
                vr.match_status,
                vr.match_score
              FROM vw_reconciliation_ready_improved vr
              WHERE vr.match_rank = 1
            )
            SELECT
              bt.id,
              bt.transaction_date,
              bt.description,
              bt.amount,
              bm.invoice_id,
              bm.nombre_emisor,
              bm.amount_difference,
              bm.days_difference,
              bm.match_status,
              bm.match_score
            FROM bank_transactions bt
            LEFT JOIN best_matches bm ON bt.id = bm.transaction_id
            WHERE bt.transaction_type = 'debit'
            ORDER BY bt.transaction_date DESC
        """)

        all_transactions = cursor.fetchall()

        # Clasificar por tipo
        by_type = {
            'GASTO_REAL': [],
            'TRASPASO': [],
            'RECARGA': [],
            'COMISION': []
        }

        for tx in all_transactions:
            tipo = classify_transaction(tx['description'])
            by_type[tipo].append(tx)

        # ==========================================
        # 1. RESUMEN POR TIPO
        # ==========================================
        print("📋 RESUMEN POR TIPO DE TRANSACCIÓN")
        print("="*120 + "\n")
        print(f"{'Tipo':<20} {'Cantidad':>10} {'Monto Total':>15} {'% TXs':>8} {'% Monto':>10} {'¿Necesita CFDI?'}")
        print("-"*120)

        total_txs = len(all_transactions)
        total_amount = sum(abs(tx['amount']) for tx in all_transactions)

        for tipo in ['GASTO_REAL', 'TRASPASO', 'RECARGA', 'COMISION']:
            txs = by_type[tipo]
            count = len(txs)
            monto = sum(abs(tx['amount']) for tx in txs)
            pct_txs = (count / total_txs) * 100
            pct_monto = (monto / total_amount) * 100
            necesita_cfdi = "✅ SÍ" if tipo == 'GASTO_REAL' else "❌ NO"

            print(f"{tipo:<20} {count:>10} ${monto:>13,.2f} {pct_txs:>7.1f}% {pct_monto:>9.1f}% {necesita_cfdi}")

        print("-"*120)
        print(f"{'TOTAL':<20} {total_txs:>10} ${total_amount:>13,.2f} {100.0:>7.1f}% {100.0:>9.1f}%")

        # ==========================================
        # 2. ANÁLISIS DE GASTOS REALES (los que SÍ necesitan CFDI)
        # ==========================================
        print("\n\n" + "="*120)
        print("💰 ANÁLISIS DE GASTOS REALES (necesitan CFDI)")
        print("="*120 + "\n")

        gastos_reales = by_type['GASTO_REAL']

        # Clasificar gastos reales
        gastos_con_match = [tx for tx in gastos_reales if tx['match_status'] and 'AUTO_MATCH' in tx['match_status']]
        gastos_sin_match = [tx for tx in gastos_reales if not (tx['match_status'] and 'AUTO_MATCH' in tx['match_status'])]

        print(f"Total gastos reales:          {len(gastos_reales)}")
        print(f"✅ Con match perfecto:        {len(gastos_con_match):>3} ({len(gastos_con_match)/len(gastos_reales)*100:>5.1f}%)")
        print(f"❌ Sin match:                 {len(gastos_sin_match):>3} ({len(gastos_sin_match)/len(gastos_reales)*100:>5.1f}%)")
        print()

        monto_gastos = sum(abs(tx['amount']) for tx in gastos_reales)
        monto_con_match = sum(abs(tx['amount']) for tx in gastos_con_match)
        monto_sin_match = sum(abs(tx['amount']) for tx in gastos_sin_match)

        print(f"💵 Por monto:")
        print(f"Total gastos:                 ${monto_gastos:>10,.2f}")
        print(f"✅ Con match:                 ${monto_con_match:>10,.2f} ({monto_con_match/monto_gastos*100:>5.1f}%)")
        print(f"❌ Sin match:                 ${monto_sin_match:>10,.2f} ({monto_sin_match/monto_gastos*100:>5.1f}%)")

        # ==========================================
        # 3. DETALLE DE GASTOS REALES CON MATCH
        # ==========================================
        if gastos_con_match:
            print("\n\n" + "="*120)
            print("✅ GASTOS REALES CON MATCH PERFECTO")
            print("="*120)
            print(f"{'ID':<4} {'Fecha':<12} {'Descripción':<45} {'Monto':>12} {'CFDI':<30}")
            print("-"*120)

            for tx in gastos_con_match:
                print(f"{tx['id']:<4} {str(tx['transaction_date']):<12} {tx['description'][:45]:<45} "
                      f"${abs(tx['amount']):>10,.2f} {(tx['nombre_emisor'] or '')[:30]}")

        # ==========================================
        # 4. DETALLE DE GASTOS REALES SIN MATCH
        # ==========================================
        if gastos_sin_match:
            print("\n\n" + "="*120)
            print("❌ GASTOS REALES SIN MATCH (Solicitar CFDIs)")
            print("="*120)
            print(f"{'ID':<4} {'Fecha':<12} {'Descripción':<60} {'Monto':>12}")
            print("-"*120)

            for tx in gastos_sin_match:
                print(f"{tx['id']:<4} {str(tx['transaction_date']):<12} {tx['description'][:60]:<60} ${abs(tx['amount']):>10,.2f}")

        # ==========================================
        # 5. DETALLE DE OTROS TIPOS (informativos)
        # ==========================================
        print("\n\n" + "="*120)
        print("📌 OTROS MOVIMIENTOS (NO requieren CFDI)")
        print("="*120 + "\n")

        for tipo in ['TRASPASO', 'RECARGA', 'COMISION']:
            txs = by_type[tipo]
            if not txs:
                continue

            monto = sum(abs(tx['amount']) for tx in txs)
            print(f"\n{tipo} ({len(txs)} transacciones - ${monto:,.2f})")
            print("-"*80)

            for tx in txs[:5]:  # Mostrar máximo 5
                print(f"  • {tx['description'][:60]:<60} ${abs(tx['amount']):>10,.2f}")

            if len(txs) > 5:
                print(f"  ... y {len(txs)-5} más")

        # ==========================================
        # 6. RESUMEN FINAL Y TASA DE CONCILIACIÓN
        # ==========================================
        print("\n\n" + "="*120)
        print("🎯 TASA DE CONCILIACIÓN (solo gastos reales)")
        print("="*120 + "\n")

        tasa_actual = (len(gastos_con_match) / len(gastos_reales)) * 100 if gastos_reales else 0

        print(f"Gastos reales que NECESITAN CFDI:     {len(gastos_reales)} transacciones (${monto_gastos:,.2f})")
        print(f"Gastos conciliados:                    {len(gastos_con_match)} transacciones (${monto_con_match:,.2f})")
        print()
        print(f"📊 TASA DE CONCILIACIÓN:               {tasa_actual:.1f}%")
        print()
        print(f"💡 Para llegar a 90%+:")
        print(f"   Necesitas {int(len(gastos_reales) * 0.9 - len(gastos_con_match))} CFDIs más")
        print(f"   Monto faltante: ${monto_sin_match:,.2f}")

        # ==========================================
        # 7. RECOMENDACIONES
        # ==========================================
        print("\n\n" + "="*120)
        print("💡 RECOMENDACIONES")
        print("="*120 + "\n")

        print(f"1. ✅ APLICAR AUTOMÁTICAMENTE")
        print(f"   {len(gastos_con_match)} gastos reales con match perfecto")
        print()

        print(f"2. 📋 SOLICITAR CFDIs FALTANTES")
        print(f"   {len(gastos_sin_match)} gastos sin factura (${monto_sin_match:,.2f})")

        # Categorizar gastos sin match
        categorias_sin_match = {}
        for tx in gastos_sin_match:
            desc = tx['description'].upper()
            if 'GASOLINERO' in desc or 'GASOL' in desc:
                cat = 'Gasolina'
            elif any(x in desc for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO', 'GUERRAS', 'CANCINO']):
                cat = 'Alimentos/Restaurantes'
            elif any(x in desc for x in ['APPLE', 'ADOBE', 'GOOGLE', 'SPOTIFY']):
                cat = 'Suscripciones'
            elif 'TELCEL' in desc or 'TELMEX' in desc:
                cat = 'Telecomunicaciones'
            else:
                cat = 'Otros'

            if cat not in categorias_sin_match:
                categorias_sin_match[cat] = []
            categorias_sin_match[cat].append(tx)

        print()
        for cat, txs in sorted(categorias_sin_match.items(), key=lambda x: -sum(abs(t['amount']) for t in x[1])):
            monto_cat = sum(abs(tx['amount']) for tx in txs)
            print(f"   • {cat:<25} {len(txs):>2} tx  ${monto_cat:>8,.2f}")

        print()
        print(f"3. ℹ️  INFORMATIVOS (no requieren acción)")
        print(f"   • Traspasos:        {len(by_type['TRASPASO'])} tx  (movimientos internos)")
        print(f"   • Recargas:         {len(by_type['RECARGA'])} tx  (no generan CFDI)")
        print(f"   • Comisiones:       {len(by_type['COMISION'])} tx  (no generan CFDI)")

        print("\n" + "="*120 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
