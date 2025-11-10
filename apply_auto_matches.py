"""
Aplicar Matches Automáticos

Este script:
1. Muestra todos los matches automáticos disponibles
2. Excluye false positives (TX-40: PAYPAL*GOOGLE → FINKOK)
3. Pide confirmación antes de aplicar
4. Actualiza bank_transactions con reconciled_invoice_id
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

# IDs de transacciones a EXCLUIR (false positives)
EXCLUDE_TXS = [40]  # TX-40: PAYPAL*GOOGLE → FINKOK


def main():
    print("\n" + "="*100)
    print("🚀 APLICAR MATCHES AUTOMÁTICOS")
    print("="*100 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Obtener matches automáticos
        cursor.execute("""
            SELECT
                vr.transaction_id,
                vr.transaction_date,
                vr.transaction_description,
                vr.transaction_amount,
                vr.invoice_id,
                vr.nombre_emisor,
                vr.invoice_total,
                vr.invoice_date,
                vr.amount_difference,
                vr.days_difference,
                vr.match_score,
                vr.match_status
            FROM vw_reconciliation_ready_improved vr
            WHERE vr.match_status LIKE 'AUTO_MATCH%'
              AND vr.match_rank = 1
            ORDER BY vr.match_score DESC, vr.amount_difference ASC
        """)

        all_matches = cursor.fetchall()

        # Filtrar false positives
        valid_matches = [m for m in all_matches if m['transaction_id'] not in EXCLUDE_TXS]
        excluded_matches = [m for m in all_matches if m['transaction_id'] in EXCLUDE_TXS]

        print(f"📊 RESUMEN:")
        print(f"   Total matches encontrados:     {len(all_matches)}")
        print(f"   Válidos para aplicar:          {len(valid_matches)}")
        print(f"   Excluidos (false positives):   {len(excluded_matches)}")
        print()

        # Mostrar excluidos
        if excluded_matches:
            print("❌ EXCLUIDOS (False Positives):")
            print("-" * 100)
            for m in excluded_matches:
                print(f"   TX-{m['transaction_id']}: {m['transaction_description']} → {m['nombre_emisor']}")
                print(f"      Razón: Descripción no coincide (diff ${m['amount_difference']:.2f})")
            print()

        # Mostrar válidos
        if not valid_matches:
            print("✅ No hay matches para aplicar")
            return

        print("✅ MATCHES VÁLIDOS PARA APLICAR:")
        print("-" * 100)
        print(f"{'ID':<4} {'Descripción TX':<45} {'Monto TX':>12} {'Emisor CFDI':<30} {'Diff':>8} {'Score':>6}")
        print("-" * 100)

        for m in valid_matches:
            emoji = "🎯" if m['match_score'] >= 95 else "✓"
            print(f"{emoji} {m['transaction_id']:<3} {m['transaction_description'][:45]:<45} "
                  f"${abs(m['transaction_amount']):>10,.2f} {(m['nombre_emisor'] or '')[:30]:<30} "
                  f"${m['amount_difference']:>7,.2f} {m['match_score']:>6}")

        print("-" * 100)

        # Calcular impacto
        cursor.execute("""
            WITH gastos_reales AS (
                SELECT COUNT(*) as total
                FROM bank_transactions bt
                WHERE bt.transaction_type = 'debit'
                  AND NOT (
                      description ILIKE '%traspaso%' OR description ILIKE '%spei%' OR description ILIKE '%transferencia%' OR
                      description ILIKE '%comision%' OR description ILIKE '%iva comision%' OR description ILIKE '%isr retenido%' OR
                      description ILIKE '%recarga%' OR description ILIKE '%tutag%' OR description ILIKE '%pase%'
                  )
            )
            SELECT total FROM gastos_reales
        """)

        total_gastos = cursor.fetchone()['total']
        tasa_antes = 0.0
        tasa_despues = (len(valid_matches) / total_gastos * 100) if total_gastos > 0 else 0

        print(f"\n📈 IMPACTO:")
        print(f"   Total gastos reales:           {total_gastos}")
        print(f"   Matches a aplicar:             {len(valid_matches)}")
        print(f"   Tasa ANTES:                    {tasa_antes:.1f}%")
        print(f"   Tasa DESPUÉS:                  {tasa_despues:.1f}%")
        print(f"   Mejora:                        +{tasa_despues - tasa_antes:.1f}%")
        print()

        # Pedir confirmación
        print("="*100)
        respuesta = input("\n¿Aplicar estos matches? (sí/no): ").strip().lower()

        if respuesta not in ['sí', 'si', 's', 'yes', 'y']:
            print("\n❌ Operación cancelada")
            return

        # Aplicar matches
        print("\n🔧 Aplicando matches...\n")

        aplicados = 0
        errores = 0

        for m in valid_matches:
            try:
                cursor.execute("""
                    UPDATE bank_transactions
                    SET
                        reconciled_invoice_id = %s,
                        match_confidence = %s,
                        reconciliation_status = 'auto',
                        reconciled_at = NOW()
                    WHERE id = %s
                      AND reconciled_invoice_id IS NULL  -- Solo si no está ya conciliado
                """, (m['invoice_id'], m['match_score'] / 100.0, m['transaction_id']))

                if cursor.rowcount > 0:
                    print(f"   ✓ TX-{m['transaction_id']} → CFDI-{m['invoice_id']} ({m['nombre_emisor'][:40]})")
                    aplicados += 1
                else:
                    print(f"   ⚠️  TX-{m['transaction_id']} ya estaba conciliado")

            except Exception as e:
                print(f"   ❌ Error en TX-{m['transaction_id']}: {e}")
                errores += 1

        conn.commit()

        print("\n" + "="*100)
        print("✅ PROCESO COMPLETADO")
        print("="*100 + "\n")

        print(f"📊 RESULTADOS:")
        print(f"   Aplicados correctamente:       {aplicados}")
        print(f"   Errores:                       {errores}")
        print(f"   Total procesados:              {aplicados + errores}")
        print()

        # Verificar estado final
        cursor.execute("""
            SELECT COUNT(*) as conciliados
            FROM bank_transactions
            WHERE reconciled_invoice_id IS NOT NULL
              AND transaction_type = 'debit'
        """)

        conciliados = cursor.fetchone()['conciliados']
        tasa_final = (conciliados / total_gastos * 100) if total_gastos > 0 else 0

        print(f"🎯 ESTADO FINAL:")
        print(f"   Gastos conciliados:            {conciliados}/{total_gastos}")
        print(f"   Tasa de conciliación:          {tasa_final:.1f}%")

        print("\n" + "="*100 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
