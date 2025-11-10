#!/usr/bin/env python3
"""
Script para sincronizar las conciliaciones entre bank_transactions y expense_invoices
Actualiza linked_expense_id en expense_invoices basándose en reconciled_invoice_id de bank_transactions
"""

import os
import psycopg2

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}

def main():
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    print("=" * 80)
    print("SINCRONIZACIÓN DE CONCILIACIONES")
    print("=" * 80)
    print()

    # Obtener todas las conciliaciones de bank_transactions
    cursor.execute("""
        SELECT
            id as bank_tx_id,
            reconciled_invoice_id as cfdi_id,
            description,
            amount,
            transaction_date,
            match_confidence,
            reconciliation_status
        FROM bank_transactions
        WHERE reconciled_invoice_id IS NOT NULL
        AND EXTRACT(YEAR FROM transaction_date) = 2025
        AND EXTRACT(MONTH FROM transaction_date) = 1
        ORDER BY transaction_date
    """)

    bank_matches = cursor.fetchall()

    print(f"Encontradas {len(bank_matches)} conciliaciones en bank_transactions")
    print()

    # Actualizar expense_invoices con el linked_expense_id
    updated_count = 0
    skipped_count = 0

    for match in bank_matches:
        bank_tx_id, cfdi_id, description, amount, tx_date, confidence, status = match

        # Verificar si el CFDI ya tiene linked_expense_id
        cursor.execute("""
            SELECT linked_expense_id, match_method
            FROM expense_invoices
            WHERE id = %s
        """, (cfdi_id,))

        cfdi_data = cursor.fetchone()

        if cfdi_data and cfdi_data[0] is not None:
            # Ya tiene linked_expense_id
            if cfdi_data[0] == bank_tx_id:
                # print(f"CFDI-{cfdi_id} ya vinculado correctamente con TX-{bank_tx_id}")
                skipped_count += 1
            else:
                print(f"⚠️  CFDI-{cfdi_id} ya vinculado con otro: {cfdi_data[0]} (método: {cfdi_data[1]})")
                print(f"    Nuevo match: TX-{bank_tx_id} - {description[:50]} - ${amount}")
                skipped_count += 1
        else:
            # Actualizar el CFDI
            cursor.execute("""
                UPDATE expense_invoices
                SET
                    linked_expense_id = %s,
                    match_confidence = %s,
                    match_method = %s,
                    match_date = NOW()
                WHERE id = %s
            """, (
                bank_tx_id,
                confidence or 0.95,
                f"Bank TX #{bank_tx_id}: {description[:70]}",
                cfdi_id
            ))

            if cursor.rowcount > 0:
                print(f"✓ CFDI-{cfdi_id} vinculado con TX-{bank_tx_id} - {description[:40]} - ${amount:,.2f}")
                updated_count += 1

    # Commit
    conn.commit()

    print()
    print("=" * 80)
    print("RESUMEN DE SINCRONIZACIÓN")
    print("=" * 80)
    print(f"Total conciliaciones en bank_transactions: {len(bank_matches)}")
    print(f"Registros actualizados en expense_invoices: {updated_count}")
    print(f"Registros omitidos (ya sincronizados): {skipped_count}")
    print()

    # Verificar estado final
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

    print("ESTADO FINAL - ENERO 2025:")
    print(f"CFDIs conciliados: {conciliados}/{total} ({conciliados/total*100:.1f}%)")
    print(f"Monto conciliado: ${monto_conciliado:,.2f} de ${monto_total:,.2f}")
    print(f"Monto pendiente: ${monto_total - monto_conciliado:,.2f}")
    print()

    # Desglose por tipo de pago
    cursor.execute("""
        SELECT
            CASE
                WHEN linked_expense_id = -1 THEN 'Tarjeta AMEX'
                WHEN linked_expense_id > 0 THEN 'Banco (SPEI/débito)'
                ELSE 'Pendiente'
            END as tipo_pago,
            COUNT(*) as cantidad,
            SUM(total) as monto
        FROM expense_invoices
        WHERE EXTRACT(YEAR FROM fecha_emision) = 2025
        AND EXTRACT(MONTH FROM fecha_emision) = 1
        AND tipo_comprobante = 'I'
        GROUP BY tipo_pago
        ORDER BY monto DESC
    """)

    print("DESGLOSE POR TIPO DE PAGO:")
    for row in cursor.fetchall():
        tipo, cantidad, monto = row
        print(f"  {tipo:.<30} {cantidad:>3} CFDIs - ${monto:>12,.2f}")

    cursor.close()
    conn.close()

    print()
    print("=" * 80)
    print("✓ Sincronización completada")
    print("=" * 80)

if __name__ == "__main__":
    main()
