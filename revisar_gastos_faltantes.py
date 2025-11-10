"""
Revisar TODOS los Gastos Faltantes
Mostrar cada uno para decidir si hay factura o no
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
    print("\n" + "="*130)
    print("🔍 REVISIÓN DETALLADA DE GASTOS FALTANTES - ¿HAY FACTURA O NO?")
    print("="*130 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Obtener gastos sin conciliar
        cursor.execute("""
            SELECT
                bt.id,
                bt.transaction_date,
                bt.description,
                bt.amount,
                bt.reference
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

        gastos_faltantes = cursor.fetchall()

        print(f"📋 Total de gastos sin conciliar: {len(gastos_faltantes)}\n")

        print("="*130)
        print("INSTRUCCIONES:")
        print("="*130)
        print("Para cada gasto, revisa si:")
        print("  1. ✅ SÍ HAY FACTURA - La solicitaron/recibieron pero no está en el sistema")
        print("  2. ❓ PENDIENTE - Hay que solicitarla al proveedor")
        print("  3. ❌ NO HAY FACTURA - No se puede obtener (ejemplo: gasolina sin ticket, compra personal, etc.)")
        print("="*130 + "\n\n")

        # Mostrar cada gasto en detalle
        for idx, tx in enumerate(gastos_faltantes, 1):
            # Clasificar tipo de proveedor
            desc_upper = tx['description'].upper()

            if any(x in desc_upper for x in ['ADOBE', 'APPLE', 'GOOGLE', 'SPOTIFY', 'GITHUB', 'TELCEL']):
                tipo = '💻 Suscripción/Software'
                nota = 'Tiene portal de facturación - Alta probabilidad de obtener CFDI'
            elif any(x in desc_upper for x in ['GASOLINERO', 'GASOL']):
                tipo = '⛽ Gasolina'
                nota = '¿Se solicitó factura en el momento? Si no, difícil de obtener'
            elif any(x in desc_upper for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO', 'CANCINO', 'GUERRAS']):
                tipo = '🍽️ Alimentos/Restaurante'
                nota = '¿Se solicitó factura en el momento? Contactar al restaurante'
            elif 'DISTRIB' in desc_upper or 'PREZ' in desc_upper:
                tipo = '📦 Distribuidor'
                nota = 'Proveedor recurrente - Alta probabilidad de obtener CFDI'
            elif any(x in desc_upper for x in ['STRIPE', 'PAYPAL', 'CONEKTA']):
                tipo = '💳 Procesador de pago'
                nota = 'Identificar comercio final, factura del comercio (no del procesador)'
            elif any(x in desc_upper for x in ['DOMICILIACION', 'TELMEX', 'CFE']):
                tipo = '📞 Servicios'
                nota = 'Tienen portal de facturación o envían por correo'
            else:
                tipo = '❓ Otros'
                nota = 'Revisar descripción para identificar proveedor'

            print(f"┌{'─'*128}┐")
            print(f"│ GASTO #{idx}/21                                                                                                                       │")
            print(f"├{'─'*128}┤")
            print(f"│ ID:              TX-{tx['id']:<3}                                                                                                           │")
            print(f"│ Fecha:           {str(tx['transaction_date'])}                                                                                             │")
            print(f"│ Monto:           ${abs(tx['amount']):>10,.2f} MXN                                                                                          │")
            print(f"│ Descripción:     {tx['description'][:90]:<90}│")
            if tx['reference']:
                print(f"│ Referencia:      {tx['reference'][:90]:<90}│")
            print(f"│                                                                                                                                │")
            print(f"│ Tipo:            {tipo:<90}│")
            print(f"│ Nota:            {nota[:90]:<90}│")
            print(f"├{'─'*128}┤")
            print(f"│ ¿HAY FACTURA DISPONIBLE?                                                                                                       │")
            print(f"│   [ ] ✅ SÍ - Hay factura (subirla al sistema)                                                                                 │")
            print(f"│   [ ] ❓ PENDIENTE - Solicitar al proveedor                                                                                    │")
            print(f"│   [ ] ❌ NO - No se puede obtener (razón: _______________________________)                                                      │")
            print(f"└{'─'*128}┘")
            print()

        # Resumen por tipo
        print("\n" + "="*130)
        print("📊 RESUMEN POR TIPO DE PROVEEDOR")
        print("="*130 + "\n")

        tipos = {}
        for tx in gastos_faltantes:
            desc_upper = tx['description'].upper()

            if any(x in desc_upper for x in ['ADOBE', 'APPLE', 'GOOGLE', 'SPOTIFY', 'GITHUB', 'TELCEL']):
                tipo = 'Suscripciones/Software'
            elif any(x in desc_upper for x in ['GASOLINERO', 'GASOL']):
                tipo = 'Gasolina'
            elif any(x in desc_upper for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO', 'CANCINO', 'GUERRAS']):
                tipo = 'Alimentos/Restaurantes'
            elif 'DISTRIB' in desc_upper:
                tipo = 'Distribuidores'
            elif any(x in desc_upper for x in ['STRIPE', 'PAYPAL', 'CONEKTA']):
                tipo = 'Procesadores de pago'
            elif any(x in desc_upper for x in ['DOMICILIACION', 'TELMEX', 'CFE']):
                tipo = 'Servicios'
            else:
                tipo = 'Otros'

            if tipo not in tipos:
                tipos[tipo] = []
            tipos[tipo].append(tx)

        print(f"{'Tipo':<30} {'Cantidad':>10} {'Monto Total':>15} {'Probabilidad de obtener CFDI'}")
        print("-"*130)

        probabilidades = {
            'Suscripciones/Software': '🟢 Alta (tienen portales)',
            'Distribuidores': '🟢 Alta (proveedores recurrentes)',
            'Servicios': '🟢 Alta (envían por correo)',
            'Procesadores de pago': '🟡 Media (depende del comercio)',
            'Gasolina': '🔴 Baja (si no se pidió en el momento)',
            'Alimentos/Restaurantes': '🔴 Baja (si no se pidió en el momento)',
            'Otros': '🟡 Variable'
        }

        for tipo in sorted(tipos.keys(), key=lambda x: -sum(abs(t['amount']) for t in tipos[x])):
            txs = tipos[tipo]
            count = len(txs)
            monto = sum(abs(tx['amount']) for tx in txs)
            prob = probabilidades.get(tipo, '🟡 Variable')
            print(f"{tipo:<30} {count:>10} ${monto:>13,.2f}   {prob}")

        print("-"*130)
        total_monto = sum(abs(tx['amount']) for tx in gastos_faltantes)
        print(f"{'TOTAL':<30} {len(gastos_faltantes):>10} ${total_monto:>13,.2f}")

        print("\n\n" + "="*130)
        print("💡 RECOMENDACIONES")
        print("="*130 + "\n")

        print("1. ALTA PRIORIDAD (alta probabilidad de obtener):")
        print("   • Suscripciones/Software: Usar portales de facturación")
        print("   • Servicios: Buscar en correo o portal del proveedor")
        print("   • Distribuidores: Contactar directamente\n")

        print("2. MEDIA PRIORIDAD (requieren investigación):")
        print("   • Procesadores de pago: Identificar comercio final")
        print("   • Otros: Revisar emails de confirmación de compra\n")

        print("3. BAJA PRIORIDAD (posiblemente no se puedan obtener):")
        print("   • Gasolina: Solo si se guardó el ticket y se solicitó factura")
        print("   • Restaurantes: Solo si se solicitó en el momento\n")

        print("="*130 + "\n")

        print("📝 SIGUIENTE PASO:")
        print("   Revisa cada gasto arriba y marca si:")
        print("   ✅ Hay factura disponible → Subirla al sistema")
        print("   ❓ Se puede solicitar → Usar templates en cfdi_requests/")
        print("   ❌ No se puede obtener → Documentar razón para auditoría\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
