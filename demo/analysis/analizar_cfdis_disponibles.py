"""
Análisis de CFDIs Disponibles
Mostrar cuáles ya están conciliados y cuáles están sin usar
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


def main():
    print("\n" + "="*140)
    print("📄 ANÁLISIS DE CFDIs (FACTURAS) DISPONIBLES")
    print("="*140 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Obtener TODOS los CFDIs de tipo "I" (Ingreso para el proveedor = gasto para nosotros)
        cursor.execute("""
            SELECT
                ei.id,
                ei.uuid,
                ei.fecha_emision::DATE as fecha,
                ei.nombre_emisor,
                ei.total,
                ei.rfc_emisor,
                ei.tipo_comprobante,
                (SELECT bt.id FROM bank_transactions bt WHERE bt.reconciled_invoice_id = ei.id LIMIT 1) as tx_id,
                (SELECT bt.description FROM bank_transactions bt WHERE bt.reconciled_invoice_id = ei.id LIMIT 1) as tx_description
            FROM expense_invoices ei
            WHERE ei.tipo_comprobante = 'I'
            ORDER BY ei.fecha_emision DESC
        """)

        all_cfdis = cursor.fetchall()

        print(f"📋 Total de CFDIs en el sistema: {len(all_cfdis)}\n")

        # Separar conciliados vs disponibles
        conciliados = [cfdi for cfdi in all_cfdis if cfdi['tx_id'] is not None]
        disponibles = [cfdi for cfdi in all_cfdis if cfdi['tx_id'] is None]

        total_monto = sum(float(cfdi['total']) for cfdi in all_cfdis)
        monto_conciliado = sum(float(cfdi['total']) for cfdi in conciliados)
        monto_disponible = sum(float(cfdi['total']) for cfdi in disponibles)

        # ==========================================
        # RESUMEN GENERAL
        # ==========================================
        print("="*140)
        print("📊 RESUMEN GENERAL")
        print("="*140 + "\n")

        print(f"{'Estado':<20} {'Cantidad':>10} {'Monto Total':>15} {'%':>8}")
        print("-"*140)
        print(f"{'✅ Conciliados':<20} {len(conciliados):>10} ${monto_conciliado:>13,.2f} {(len(conciliados)/len(all_cfdis)*100):>7.1f}%")
        print(f"{'❌ Disponibles':<20} {len(disponibles):>10} ${monto_disponible:>13,.2f} {(len(disponibles)/len(all_cfdis)*100):>7.1f}%")
        print("-"*140)
        print(f"{'TOTAL':<20} {len(all_cfdis):>10} ${total_monto:>13,.2f} {100.0:>7.1f}%")

        # ==========================================
        # CFDIs YA CONCILIADOS
        # ==========================================
        print("\n\n" + "="*140)
        print(f"✅ CFDIs YA CONCILIADOS ({len(conciliados)})")
        print("="*140 + "\n")

        if conciliados:
            print(f"{'CFDI ID':<8} {'Fecha':<12} {'Emisor':<40} {'Total':>12} {'TX ID':<8} {'Descripción TX'}")
            print("-"*140)

            for cfdi in sorted(conciliados, key=lambda x: x['fecha'], reverse=True):
                emisor = (cfdi['nombre_emisor'] or 'N/A')[:40]
                tx_desc = (cfdi['tx_description'] or 'N/A')[:50]
                print(f"{cfdi['id']:<8} {str(cfdi['fecha']):<12} {emisor:<40} ${float(cfdi['total']):>10,.2f} TX-{cfdi['tx_id']:<5} {tx_desc}")

            print("-"*140)
            print(f"{'TOTAL CONCILIADO':<62} ${monto_conciliado:>10,.2f}\n")
        else:
            print("   (No hay CFDIs conciliados)\n")

        # ==========================================
        # CFDIs DISPONIBLES (SIN CONCILIAR)
        # ==========================================
        print("\n" + "="*140)
        print(f"❌ CFDIs DISPONIBLES (Sin conciliar) - ({len(disponibles)})")
        print("="*140 + "\n")

        if disponibles:
            print(f"{'CFDI ID':<8} {'Fecha':<12} {'Emisor':<50} {'Total':>12} {'Razón probable'}")
            print("-"*140)

            for cfdi in sorted(disponibles, key=lambda x: float(x['total']), reverse=True):
                emisor = (cfdi['nombre_emisor'] or 'N/A')[:50]

                # Determinar razón probable
                emisor_upper = emisor.upper()
                total = float(cfdi['total'])

                if 'GASOLINERO' in emisor_upper or 'BERISA' in emisor_upper:
                    razon = 'Posible match con gasolinera (diferencia en monto)'
                elif 'PREZ' in emisor_upper or 'DISTRIB' in emisor_upper:
                    razon = 'Posible match con distribuidor'
                elif 'ODOO' in emisor_upper or 'FINKOK' in emisor_upper:
                    razon = 'Posible match con suscripción'
                elif 'TELMEX' in emisor_upper or 'TELCEL' in emisor_upper:
                    razon = 'Posible match con telecomunicaciones'
                elif total < 100:
                    razon = 'Monto bajo - revisar manualmente'
                else:
                    razon = 'Sin transacción bancaria equivalente'

                print(f"{cfdi['id']:<8} {str(cfdi['fecha']):<12} {emisor:<50} ${total:>10,.2f} {razon}")

            print("-"*140)
            print(f"{'TOTAL DISPONIBLE':<72} ${monto_disponible:>10,.2f}\n")
        else:
            print("   ¡Todos los CFDIs están conciliados! 🎉\n")

        # ==========================================
        # ANÁLISIS POR EMISOR
        # ==========================================
        print("\n" + "="*140)
        print("📊 ANÁLISIS POR EMISOR")
        print("="*140 + "\n")

        emisores = {}
        for cfdi in all_cfdis:
            emisor = cfdi['nombre_emisor'] or 'Sin nombre'
            if emisor not in emisores:
                emisores[emisor] = {
                    'total': 0,
                    'conciliados': 0,
                    'disponibles': 0,
                    'monto_total': 0,
                    'monto_conciliado': 0,
                    'monto_disponible': 0
                }

            emisores[emisor]['total'] += 1
            emisores[emisor]['monto_total'] += float(cfdi['total'])

            if cfdi['tx_id']:
                emisores[emisor]['conciliados'] += 1
                emisores[emisor]['monto_conciliado'] += float(cfdi['total'])
            else:
                emisores[emisor]['disponibles'] += 1
                emisores[emisor]['monto_disponible'] += float(cfdi['total'])

        print(f"{'Emisor':<45} {'Total':>6} {'✅ Conc':>6} {'❌ Disp':>6} {'Monto Total':>15} {'Tasa':>8}")
        print("-"*140)

        for emisor in sorted(emisores.keys(), key=lambda x: -emisores[x]['monto_total']):
            datos = emisores[emisor]
            tasa = (datos['conciliados'] / datos['total'] * 100) if datos['total'] > 0 else 0
            emoji = '✅' if tasa == 100 else '⚠️' if tasa >= 50 else '❌'

            print(f"{emisor[:45]:<45} {datos['total']:>6} {datos['conciliados']:>6} {datos['disponibles']:>6} "
                  f"${datos['monto_total']:>13,.2f} {emoji} {tasa:>5.0f}%")

        # ==========================================
        # ESTADÍSTICAS
        # ==========================================
        print("\n\n" + "="*140)
        print("📈 ESTADÍSTICAS")
        print("="*140 + "\n")

        print(f"🎯 TASA DE UTILIZACIÓN DE CFDIs:")
        print(f"   CFDIs conciliados:        {len(conciliados)}/{len(all_cfdis)} ({len(conciliados)/len(all_cfdis)*100:.1f}%)")
        print(f"   Monto conciliado:         ${monto_conciliado:,.2f} / ${total_monto:,.2f}\n")

        print(f"✅ CFDIs UTILIZADOS:")
        print(f"   Total de CFDIs:           {len(conciliados)}")
        print(f"   Monto total:              ${monto_conciliado:,.2f} MXN")
        print(f"   Promedio:                 ${monto_conciliado/len(conciliados):,.2f} MXN\n" if conciliados else "   N/A\n")

        print(f"❌ CFDIs SIN USAR:")
        print(f"   Total de CFDIs:           {len(disponibles)}")
        print(f"   Monto total:              ${monto_disponible:,.2f} MXN")
        print(f"   Promedio:                 ${monto_disponible/len(disponibles):,.2f} MXN\n" if disponibles else "   N/A\n")

        # ==========================================
        # ACCIONES SUGERIDAS
        # ==========================================
        if disponibles:
            print("="*140)
            print("🚀 ACCIONES SUGERIDAS PARA CFDIs DISPONIBLES")
            print("="*140 + "\n")

            print("1. VERIFICAR MATCHING MANUAL:")
            print("   Algunos CFDIs disponibles pueden tener una transacción bancaria con:")
            print("   • Diferencia de monto (descuentos, propinas, etc.)")
            print("   • Diferencia de fecha (±10 días)")
            print("   • Descripción diferente\n")

            print("2. EJECUTAR MATCHER DE EMBEDDINGS:")
            print("   python3 test_embedding_matching.py")
            print("   (Puede encontrar matches que el sistema estricto no detectó)\n")

            print("3. REVISAR SI SON GASTOS DUPLICADOS:")
            print("   • Verificar si ya se pagaron con otra forma de pago")
            print("   • Revisar si son de otro periodo\n")

            print("4. CFDIs DE MONTOS BAJOS (<$100):")
            cfdis_bajos = [cfdi for cfdi in disponibles if float(cfdi['total']) < 100]
            if cfdis_bajos:
                print(f"   Hay {len(cfdis_bajos)} CFDIs con monto < $100")
                print(f"   Pueden ser propinas, cargos adicionales, etc.")
                print(f"   Revisar manualmente\n")

        print("="*140 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
