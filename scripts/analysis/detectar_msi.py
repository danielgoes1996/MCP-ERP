#!/usr/bin/env python3
"""
Detector de Meses Sin Intereses (MSI)
======================================
Identifica facturas PUE pagadas con tarjeta que podrían ser MSI
comparando con movimientos bancarios reales.

Uso:
    python3 detectar_msi.py --company-id 2
    python3 detectar_msi.py --company-id 2 --mes 2025-08
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
from datetime import datetime
from decimal import Decimal

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

def detectar_msi_facturas(company_id, mes=None):
    """
    Detecta posibles facturas MSI comparando con movimientos bancarios
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    print("=" * 100)
    print("🔍 DETECTOR DE MESES SIN INTERESES (MSI)")
    print("=" * 100)
    print(f"\nCompañía: {company_id}")
    if mes:
        print(f"Mes: {mes}")
    print()

    # PASO 1: Obtener facturas sospechosas (PUE + Tarjeta + >$5000)
    fecha_filter = ""
    if mes:
        fecha_filter = f"AND DATE_TRUNC('month', fecha_emision) = '{mes}-01'::date"

    query = f"""
        SELECT
            id,
            uuid,
            fecha_emision,
            nombre_emisor,
            total,
            metodo_pago,
            forma_pago
        FROM expense_invoices
        WHERE company_id = %s
        AND sat_status = 'vigente'
        AND metodo_pago = 'PUE'
        AND forma_pago = '04'
        AND total > 100
        {fecha_filter}
        ORDER BY total DESC;
    """

    cursor.execute(query, [company_id])
    facturas_sospechosas = cursor.fetchall()

    print(f"📋 FACTURAS CANDIDATAS (PUE + Tarjeta Crédito + >$100): {len(facturas_sospechosas)}")
    print("    → Solo tarjeta de crédito (04)")
    print("    → Cualquier monto arriba de $100\n")
    print("=" * 100)

    if len(facturas_sospechosas) == 0:
        print("✅ No se encontraron facturas sospechosas de MSI")
        conn.close()
        return

    # TODO: En producción, aquí harías join con tabla de movimientos bancarios
    # Por ahora, mostramos análisis manual

    print(f"\n{'#':<4} {'Fecha':<12} {'Emisor':<30} {'Total':>15} {'¿MSI?':<15} {'Acción'}")
    print("-" * 100)

    detectados = []

    for i, factura in enumerate(facturas_sospechosas, 1):
        total = float(factura['total'])

        # Heurística: Montos comunes de MSI
        posibles_meses = [3, 6, 9, 12, 18, 24]
        mejor_match = None

        for meses in posibles_meses:
            pago_mensual = total / meses
            # Si el pago mensual termina en cifras "bonitas" (0.00, 0.49, 0.99)
            centavos = (pago_mensual * 100) % 100
            if centavos < 1 or abs(centavos - 49) < 1 or abs(centavos - 99) < 1:
                mejor_match = {
                    'meses': meses,
                    'pago_mensual': pago_mensual
                }
                break

        if mejor_match:
            status = f"⚠️ Posible {mejor_match['meses']} MSI"
            accion = f"Verificar cargo ${mejor_match['pago_mensual']:,.2f}"
            detectados.append({
                'factura': factura,
                'meses': mejor_match['meses'],
                'pago_mensual': mejor_match['pago_mensual']
            })
        else:
            status = "✓ Probablemente normal"
            accion = "Sin acción"

        print(f"{i:<4} {str(factura['fecha_emision'])[:10]:<12} "
              f"{factura['nombre_emisor'][:28]:<30} "
              f"${total:>13,.2f} {status:<15} {accion}")

    # Reporte detallado de detectados
    if detectados:
        print("\n" + "=" * 100)
        print("⚠️  FACTURAS QUE REQUIEREN VERIFICACIÓN MANUAL")
        print("=" * 100)

        for item in detectados:
            factura = item['factura']
            total = float(factura['total'])

            print(f"\n📄 {factura['nombre_emisor']}")
            print(f"   Fecha: {factura['fecha_emision']}")
            print(f"   Total: ${total:,.2f}")
            print(f"   UUID: {factura['uuid']}")
            print()
            print(f"   🔍 VERIFICAR EN ESTADO DE CUENTA:")
            print(f"   ─" * 40)
            print(f"   Si encuentras cargo de ${item['pago_mensual']:,.2f}")
            print(f"   → Es MSI a {item['meses']} meses")
            print(f"   → Crear cuenta 'Acreedores MSI' por ${total - item['pago_mensual']:,.2f}")
            print()
            print(f"   Si encuentras cargo de ${total:,.2f}")
            print(f"   → NO es MSI, pago completo")
            print(f"   → Sin acción adicional")

    print("\n" + "=" * 100)
    print("📊 RESUMEN")
    print("=" * 100)
    print(f"\nTotal facturas analizadas: {len(facturas_sospechosas)}")
    print(f"Posibles MSI detectados:   {len(detectados)}")
    print(f"Requieren verificación:    {len(detectados)}")

    if detectados:
        print("\n⚠️  SIGUIENTE PASO:")
        print("   1. Revisar estados de cuenta de tarjetas")
        print("   2. Buscar cargos que coincidan con las fechas")
        print("   3. Si es MSI: Crear asiento contable con 'Acreedores MSI'")
        print("   4. Marcar factura con campo 'es_msi' = true")

    print("\n" + "=" * 100)

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Detecta facturas con posible pago en MSI'
    )

    parser.add_argument('--company-id', type=int, required=True, help='ID de la compañía')
    parser.add_argument('--mes', type=str, help='Mes específico (YYYY-MM)')

    args = parser.parse_args()

    detectar_msi_facturas(args.company_id, args.mes)


if __name__ == "__main__":
    main()
