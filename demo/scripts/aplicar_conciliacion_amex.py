#!/usr/bin/env python3
"""
Script para aplicar las conciliaciones encontradas en el estado de cuenta AMEX
Concilia 4 CFDIs con sus pagos correspondientes en tarjeta de crédito
"""

import os
import psycopg2
from datetime import datetime

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}

# Matches encontrados del estado de cuenta AMEX
matches_amex = [
    {
        'cfdi_id': 747,
        'cfdi_emisor': 'VENTUS SPORT',
        'cfdi_monto': 4325.00,
        'tx_fecha': '2025-01-23',
        'tx_descripcion': 'TODOLLANTAS SUC CONSTI (VENTUS SPORT)',
        'tx_monto': 4325.00,
        'diferencia': 0.00,
        'nota': 'Llantas Pirelli + balanceo + nitrógeno'
    },
    {
        'cfdi_id': 761,
        'cfdi_emisor': 'HAISO PLASTICOS',
        'cfdi_monto': 1653.00,
        'tx_fecha': '2025-01-27',
        'tx_descripcion': 'COPARMEX HAISO PLASTIC',
        'tx_monto': 1653.00,
        'diferencia': 0.00,
        'nota': '15 cubetas plásticas 19L con tapas'
    },
    {
        'cfdi_id': 767,
        'cfdi_emisor': 'CLIFTON PACKAGING',
        'cfdi_monto': 3992.67,
        'tx_fecha': '2025-01-28',
        'tx_descripcion': 'CLIFTON PACKAGING',
        'tx_monto': 3992.66,
        'diferencia': 0.01,
        'nota': '2,000 bolsas Stand Up con zipper (cargo $4,257.14 - crédito $264.48)'
    },
    {
        'cfdi_id': 780,
        'cfdi_emisor': 'CARLOS ADRIAN DEL CALLEJO NAVA',
        'cfdi_monto': 780.00,
        'tx_fecha': '2025-01-28',
        'tx_descripcion': 'MERCADOPAGO*COLORMACHIN',
        'tx_monto': 780.00,
        'diferencia': 0.00,
        'nota': 'Reparación impresora + tinta'
    }
]

def main():
    conn = psycopg2.connect(**POSTGRES_CONFIG)

    cursor = conn.cursor()

    print("=" * 80)
    print("APLICANDO CONCILIACIONES DE TARJETA AMEX")
    print("=" * 80)
    print()

    # Primero, verificar que los CFDIs existen y no están ya conciliados
    print("Verificando CFDIs...")
    for match in matches_amex:
        cursor.execute("""
            SELECT id, nombre_emisor, total, linked_expense_id, match_method
            FROM expense_invoices
            WHERE id = %s
        """, (match['cfdi_id'],))

        cfdi = cursor.fetchone()
        if cfdi:
            print(f"✓ CFDI-{cfdi[0]}: {cfdi[1]} - ${cfdi[2]:,.2f}")
            if cfdi[3]:
                print(f"  ⚠️  Ya está conciliado (linked_expense_id: {cfdi[3]}, método: {cfdi[4] or 'N/A'})")
        else:
            print(f"✗ CFDI-{match['cfdi_id']} NO encontrado")

    print()
    print("-" * 80)
    print("Aplicando conciliaciones...")
    print("-" * 80)
    print()

    total_conciliado = 0

    for i, match in enumerate(matches_amex, 1):
        print(f"{i}. CFDI-{match['cfdi_id']} - {match['cfdi_emisor']}")
        print(f"   Monto CFDI: ${match['cfdi_monto']:,.2f}")
        print(f"   Pago AMEX: ${match['tx_monto']:,.2f} ({match['tx_fecha']})")
        print(f"   Diferencia: ${match['diferencia']:.2f}")
        print(f"   Nota: {match['nota']}")

        # Actualizar el CFDI con información de la conciliación
        # Marcar con -1 en linked_expense_id para indicar pago con tarjeta (no está en bank_transactions)
        # Guardar detalles en match_method (máximo 100 caracteres)
        method_str = f"AMEX {match['tx_fecha']}: {match['tx_descripcion'][:50]}"
        cursor.execute("""
            UPDATE expense_invoices
            SET
                linked_expense_id = -1,
                match_confidence = 1.0,
                match_method = %s,
                match_date = NOW()
            WHERE id = %s
            AND linked_expense_id IS NULL
        """, (
            method_str[:100],
            match['cfdi_id']
        ))

        if cursor.rowcount > 0:
            print(f"   ✓ Conciliado exitosamente")
            total_conciliado += match['cfdi_monto']
        else:
            print(f"   ⚠️  No se pudo actualizar (puede estar ya conciliado)")

        print()

    # Commit de los cambios
    conn.commit()

    print("=" * 80)
    print("RESUMEN DE CONCILIACIÓN AMEX")
    print("=" * 80)
    print(f"CFDIs conciliados: {len(matches_amex)}")
    print(f"Monto total conciliado: ${total_conciliado:,.2f} MXN")
    print()

    # Verificar estado actualizado de conciliación
    cursor.execute("""
        SELECT
            COUNT(*) FILTER (WHERE linked_expense_id IS NOT NULL) as conciliados,
            COUNT(*) as total,
            SUM(total) FILTER (WHERE linked_expense_id IS NOT NULL) as monto_conciliado,
            SUM(total) as monto_total
        FROM expense_invoices
        WHERE EXTRACT(YEAR FROM fecha_emision) = 2025
        AND EXTRACT(MONTH FROM fecha_emision) = 1
        AND tipo_comprobante = 'I'
    """)

    result = cursor.fetchone()
    conciliados, total, monto_conciliado, monto_total = result

    print("ESTADO ACTUALIZADO - ENERO 2025:")
    print(f"CFDIs conciliados: {conciliados}/{total} ({conciliados/total*100:.1f}%)")
    print(f"Monto conciliado: ${monto_conciliado:,.2f} de ${monto_total:,.2f}")
    print()

    # Mostrar CFDIs pendientes más grandes
    print("CFDIs PENDIENTES MÁS GRANDES:")
    cursor.execute("""
        SELECT id, nombre_emisor, total, fecha_emision, metodo_pago
        FROM expense_invoices
        WHERE EXTRACT(YEAR FROM fecha_emision) = 2025
        AND EXTRACT(MONTH FROM fecha_emision) = 1
        AND tipo_comprobante = 'I'
        AND linked_expense_id IS NULL
        ORDER BY total DESC
        LIMIT 10
    """)

    pendientes = cursor.fetchall()
    for cfdi in pendientes:
        print(f"CFDI-{cfdi[0]}: {cfdi[1]} - ${cfdi[2]:,.2f} ({cfdi[3]}) - {cfdi[4] or 'N/A'}")

    cursor.close()
    conn.close()

    print()
    print("=" * 80)
    print("✓ Conciliación AMEX completada")
    print("=" * 80)

if __name__ == "__main__":
    main()
