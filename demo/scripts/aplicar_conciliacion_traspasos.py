"""
Aplicar Conciliaciones de Traspasos SPEI
Concilia los traspasos con sus CFDIs correspondientes
"""

import os
import json
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
    print("\n" + "="*120)
    print("🚀 APLICAR CONCILIACIONES DE TRASPASOS SPEI")
    print("="*120 + "\n")

    # Cargar matches
    with open('/Users/danielgoes96/Desktop/mcp-server/matches_traspasos.json', 'r') as f:
        matches = json.load(f)

    print(f"📋 Total de matches a aplicar: {len(matches)}\n")

    # Mostrar resumen
    print("="*120)
    print("MATCHES A APLICAR:")
    print("="*120 + "\n")

    print(f"{'#':<3} {'TX':<8} {'CFDI':<8} {'Monto':>12} {'Emisor':<50}")
    print("-"*120)

    total_monto = 0
    for idx, m in enumerate(matches, 1):
        total_monto += abs(m['tx_amount'])
        print(f"{idx:<3} TX-{m['tx_id']:<5} CFDI-{m['cfdi_id']:<5} ${abs(m['tx_amount']):>10,.2f} {m['cfdi_emisor'][:50]}")

    print("-"*120)
    print(f"{'TOTAL':<20} ${total_monto:>10,.2f}\n")

    # Pedir confirmación
    print("="*120)
    respuesta = input("\n¿Confirmas aplicar estas conciliaciones? (sí/no): ").strip().lower()

    if respuesta not in ['sí', 'si', 's', 'yes', 'y']:
        print("\n❌ Operación cancelada\n")
        return

    # Aplicar conciliaciones
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        print("\n🔧 Aplicando conciliaciones...\n")

        # Deshabilitar trigger
        cursor.execute("ALTER TABLE bank_transactions DISABLE TRIGGER trg_generate_source_hash")

        aplicados = 0
        errores = 0

        for m in matches:
            try:
                # Verificar que no esté ya conciliado
                cursor.execute("""
                    SELECT reconciled_invoice_id
                    FROM bank_transactions
                    WHERE id = %s
                """, (m['tx_id'],))

                tx = cursor.fetchone()

                if tx and tx['reconciled_invoice_id']:
                    print(f"   ⚠️  TX-{m['tx_id']} ya está conciliado con CFDI-{tx['reconciled_invoice_id']}")
                    continue

                # Aplicar conciliación
                cursor.execute("""
                    UPDATE bank_transactions
                    SET
                        reconciled_invoice_id = %s,
                        match_confidence = 0.95,
                        reconciliation_status = 'auto',
                        reconciled_at = NOW()
                    WHERE id = %s
                """, (m['cfdi_id'], m['tx_id']))

                if cursor.rowcount > 0:
                    print(f"   ✓ TX-{m['tx_id']} → CFDI-{m['cfdi_id']} ({m['cfdi_emisor'][:50]})")
                    aplicados += 1
                else:
                    print(f"   ❌ Error al conciliar TX-{m['tx_id']}")
                    errores += 1

            except Exception as e:
                print(f"   ❌ Error en TX-{m['tx_id']}: {e}")
                errores += 1

        # Re-habilitar trigger
        cursor.execute("ALTER TABLE bank_transactions ENABLE TRIGGER trg_generate_source_hash")

        conn.commit()

        print("\n" + "="*120)
        print("✅ PROCESO COMPLETADO")
        print("="*120 + "\n")

        print(f"📊 RESULTADOS:")
        print(f"   Aplicados correctamente:   {aplicados}")
        print(f"   Errores:                   {errores}")
        print(f"   Total procesados:          {aplicados + errores}")
        print()

        # Verificar estado final
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM bank_transactions
            WHERE reconciled_invoice_id IS NOT NULL
              AND transaction_type = 'debit'
              AND transaction_date >= '2025-01-01'
              AND transaction_date < '2025-02-01'
        """)

        conciliados = cursor.fetchone()['total']

        cursor.execute("""
            SELECT COUNT(*) as total
            FROM bank_transactions
            WHERE transaction_type = 'debit'
              AND transaction_date >= '2025-01-01'
              AND transaction_date < '2025-02-01'
              AND NOT (
                  description ILIKE '%comision%' OR description ILIKE '%iva comision%' OR
                  description ILIKE '%isr retenido%' OR description ILIKE '%recarga%'
              )
        """)

        total_debitos = cursor.fetchone()['total']
        tasa = (conciliados / total_debitos * 100) if total_debitos > 0 else 0

        print(f"🎯 ESTADO FINAL:")
        print(f"   Débitos conciliados:       {conciliados}/{total_debitos}")
        print(f"   Tasa de conciliación:      {tasa:.1f}%")

        print("\n💡 PRÓXIMO PASO:")
        print("   Ver estado actualizado: python3 ver_estado_conciliacion.py")

        print("\n" + "="*120 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
