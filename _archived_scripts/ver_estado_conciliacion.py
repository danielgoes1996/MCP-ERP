"""
Reporte Detallado de Estado de Conciliación
Muestra qué gastos ya están conciliados y cuáles faltan
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
    print("📊 ESTADO DE CONCILIACIÓN - DETALLE COMPLETO")
    print("="*120 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Obtener TODOS los débitos del estado de cuenta
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

        print(f"📋 Total de débitos en el estado de cuenta: {len(all_debits)}\n")

        # Clasificar por tipo
        gastos_reales = []
        traspasos = []
        recargas = []
        comisiones = []

        for tx in all_debits:
            tipo = classify_transaction(tx['description'])
            if tipo == 'GASTO_REAL':
                gastos_reales.append(tx)
            elif tipo == 'TRASPASO':
                traspasos.append(tx)
            elif tipo == 'RECARGA':
                recargas.append(tx)
            elif tipo == 'COMISION':
                comisiones.append(tx)

        # ==========================================
        # 1. RESUMEN GENERAL
        # ==========================================
        print("="*120)
        print("📊 RESUMEN GENERAL")
        print("="*120 + "\n")

        total_amount = sum(abs(tx['amount']) for tx in all_debits)

        print(f"{'Tipo':<20} {'Cantidad':>10} {'Monto Total':>15} {'% TXs':>8} {'% Monto':>10}")
        print("-"*120)

        for tipo, txs in [('GASTO_REAL', gastos_reales), ('TRASPASO', traspasos),
                          ('RECARGA', recargas), ('COMISION', comisiones)]:
            count = len(txs)
            monto = sum(abs(tx['amount']) for tx in txs)
            pct_txs = (count / len(all_debits)) * 100 if all_debits else 0
            pct_monto = (monto / total_amount) * 100 if total_amount else 0
            print(f"{tipo:<20} {count:>10} ${monto:>13,.2f} {pct_txs:>7.1f}% {pct_monto:>9.1f}%")

        print("-"*120)
        print(f"{'TOTAL':<20} {len(all_debits):>10} ${total_amount:>13,.2f} {100.0:>7.1f}% {100.0:>9.1f}%")

        # ==========================================
        # 2. GASTOS REALES - CONCILIADOS
        # ==========================================
        gastos_conciliados = [tx for tx in gastos_reales if tx['reconciled_invoice_id'] is not None]
        gastos_sin_conciliar = [tx for tx in gastos_reales if tx['reconciled_invoice_id'] is None]

        print("\n\n" + "="*120)
        print(f"✅ GASTOS REALES CONCILIADOS ({len(gastos_conciliados)}/{len(gastos_reales)})")
        print("="*120 + "\n")

        if gastos_conciliados:
            print(f"{'ID':<4} {'Fecha':<12} {'Descripción TX':<50} {'Monto':>12} {'Emisor CFDI':<30}")
            print("-"*120)

            for tx in sorted(gastos_conciliados, key=lambda x: x['transaction_date'], reverse=True):
                nombre_emisor = (tx['nombre_emisor'] or 'N/A')[:30]
                print(f"{tx['id']:<4} {str(tx['transaction_date']):<12} {tx['description'][:50]:<50} "
                      f"${abs(tx['amount']):>10,.2f} {nombre_emisor:<30}")

            monto_conciliado = sum(abs(tx['amount']) for tx in gastos_conciliados)
            print("-"*120)
            print(f"{'TOTAL CONCILIADO':<68} ${monto_conciliado:>10,.2f}\n")
        else:
            print("   (No hay gastos conciliados aún)\n")

        # ==========================================
        # 3. GASTOS REALES - SIN CONCILIAR
        # ==========================================
        print("\n" + "="*120)
        print(f"❌ GASTOS REALES SIN CONCILIAR ({len(gastos_sin_conciliar)}/{len(gastos_reales)})")
        print("="*120 + "\n")

        if gastos_sin_conciliar:
            print(f"{'ID':<4} {'Fecha':<12} {'Descripción':<65} {'Monto':>12} {'Razón'}")
            print("-"*120)

            for tx in sorted(gastos_sin_conciliar, key=lambda x: abs(x['amount']), reverse=True):
                # Determinar razón
                desc_upper = tx['description'].upper()
                if any(x in desc_upper for x in ['ADOBE', 'APPLE', 'GOOGLE', 'TELCEL', 'SPOTIFY']):
                    razon = "Proveedor corporativo"
                elif any(x in desc_upper for x in ['GASOLINERO', 'GASOL']):
                    razon = "Gasolinera"
                elif any(x in desc_upper for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO']):
                    razon = "Restaurante"
                elif 'DISTRIB' in desc_upper:
                    razon = "Distribuidor"
                else:
                    razon = "Otros"

                print(f"{tx['id']:<4} {str(tx['transaction_date']):<12} {tx['description'][:65]:<65} "
                      f"${abs(tx['amount']):>10,.2f} {razon}")

            monto_sin_conciliar = sum(abs(tx['amount']) for tx in gastos_sin_conciliar)
            print("-"*120)
            print(f"{'TOTAL SIN CONCILIAR':<82} ${monto_sin_conciliar:>10,.2f}\n")
        else:
            print("   ¡Todos los gastos están conciliados! 🎉\n")

        # ==========================================
        # 4. OTROS MOVIMIENTOS (INFORMATIVOS)
        # ==========================================
        print("\n" + "="*120)
        print("📌 OTROS MOVIMIENTOS (No requieren CFDI)")
        print("="*120 + "\n")

        for tipo, txs in [('TRASPASOS', traspasos), ('RECARGAS', recargas), ('COMISIONES', comisiones)]:
            if not txs:
                continue

            monto = sum(abs(tx['amount']) for tx in txs)
            print(f"\n{tipo} ({len(txs)} transacciones - ${monto:,.2f} MXN)")
            print("-"*100)

            for tx in sorted(txs, key=lambda x: abs(x['amount']), reverse=True)[:5]:
                print(f"   {str(tx['transaction_date']):<12} {tx['description'][:60]:<60} ${abs(tx['amount']):>10,.2f}")

            if len(txs) > 5:
                print(f"   ... y {len(txs)-5} más")

        # ==========================================
        # 5. ESTADÍSTICAS FINALES
        # ==========================================
        print("\n\n" + "="*120)
        print("📊 ESTADÍSTICAS DE CONCILIACIÓN")
        print("="*120 + "\n")

        tasa_conciliacion = (len(gastos_conciliados) / len(gastos_reales) * 100) if gastos_reales else 0
        monto_gastos = sum(abs(tx['amount']) for tx in gastos_reales)
        monto_conciliado = sum(abs(tx['amount']) for tx in gastos_conciliados)
        monto_pendiente = sum(abs(tx['amount']) for tx in gastos_sin_conciliar)

        print(f"🎯 TASA DE CONCILIACIÓN:")
        print(f"   Gastos conciliados:           {len(gastos_conciliados):>3}/{len(gastos_reales):<3} ({tasa_conciliacion:.1f}%)")
        print(f"   Monto conciliado:             ${monto_conciliado:>10,.2f} / ${monto_gastos:,.2f}")
        print()

        print(f"✅ CONCILIADOS:")
        print(f"   Total de transacciones:       {len(gastos_conciliados)}")
        print(f"   Monto total:                  ${monto_conciliado:,.2f} MXN")
        print(f"   Promedio por transacción:     ${monto_conciliado/len(gastos_conciliados):,.2f} MXN" if gastos_conciliados else "   N/A")
        print()

        print(f"❌ PENDIENTES:")
        print(f"   Total de transacciones:       {len(gastos_sin_conciliar)}")
        print(f"   Monto total:                  ${monto_pendiente:,.2f} MXN")
        print(f"   Promedio por transacción:     ${monto_pendiente/len(gastos_sin_conciliar):,.2f} MXN" if gastos_sin_conciliar else "   N/A")
        print()

        # Categorías de pendientes
        if gastos_sin_conciliar:
            categorias = {}
            for tx in gastos_sin_conciliar:
                desc_upper = tx['description'].upper()
                if any(x in desc_upper for x in ['ADOBE', 'APPLE', 'GOOGLE', 'TELCEL', 'SPOTIFY', 'GITHUB']):
                    cat = 'Suscripciones/Software'
                elif any(x in desc_upper for x in ['GASOLINERO', 'GASOL']):
                    cat = 'Gasolina'
                elif any(x in desc_upper for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO', 'CANCINO']):
                    cat = 'Alimentos/Restaurantes'
                elif 'DISTRIB' in desc_upper:
                    cat = 'Distribuidores'
                else:
                    cat = 'Otros'

                if cat not in categorias:
                    categorias[cat] = []
                categorias[cat].append(tx)

            print(f"📋 PENDIENTES POR CATEGORÍA:")
            for cat, txs in sorted(categorias.items(), key=lambda x: -sum(abs(t['amount']) for t in x[1])):
                monto_cat = sum(abs(tx['amount']) for tx in txs)
                print(f"   {cat:<30} {len(txs):>2} tx  ${monto_cat:>8,.2f}")

        # ==========================================
        # 6. PRÓXIMOS PASOS
        # ==========================================
        print("\n\n" + "="*120)
        print("🚀 PRÓXIMOS PASOS")
        print("="*120 + "\n")

        if gastos_sin_conciliar:
            print(f"1. Solicitar {len(gastos_sin_conciliar)} CFDIs faltantes (${monto_pendiente:,.2f} MXN)")
            print(f"   📧 Templates generados en: cfdi_requests/")
            print()
            print(f"2. Cuando recibas los CFDIs:")
            print(f"   • Subirlos al sistema")
            print(f"   • Ejecutar: python3 test_embedding_matching.py")
            print(f"   • Verificar: python3 ver_estado_conciliacion.py")
            print()
            print(f"3. Meta:")
            print(f"   Tasa actual:  {tasa_conciliacion:.1f}%")
            print(f"   Tasa objetivo: 100%")
            print(f"   Faltante:     {100 - tasa_conciliacion:.1f}%")
        else:
            print("✅ ¡Todos los gastos están conciliados!")
            print("   No se requiere ninguna acción adicional.")

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
