"""
Script de Conciliación Automática

Este script usa las vistas creadas para conciliar automáticamente
las transacciones bancarias con facturas (CFDIs).

Proceso:
1. Consulta vw_auto_match_suggestions para encontrar matches automáticos
2. Actualiza bank_transactions marcando la conciliación
3. Muestra estadísticas de conciliación

Uso:
    python reconcile_auto_matches.py
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Configuración PostgreSQL
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}


def get_auto_match_suggestions(cursor):
    """
    Obtiene sugerencias de conciliación automática
    usando la vista vw_auto_match_suggestions
    """
    cursor.execute("""
        SELECT
            transaction_id,
            transaction_date,
            transaction_description,
            transaction_amount,
            invoice_id,
            invoice_uuid,
            invoice_total,
            invoice_date,
            amount_difference,
            days_difference,
            rfc_emisor
        FROM vw_auto_match_suggestions
        ORDER BY amount_difference ASC, days_difference ASC
    """)

    return cursor.fetchall()


def reconcile_transaction(cursor, transaction_id, invoice_id, confidence=1.0, user_id=None):
    """
    Marca una transacción como conciliada con una factura
    """
    cursor.execute("""
        UPDATE bank_transactions
        SET
            reconciled_invoice_id = %s,
            match_confidence = %s,
            reconciliation_status = 'matched',
            reconciled_by = %s,
            reconciled_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id
    """, (invoice_id, confidence, user_id, transaction_id))

    return cursor.fetchone()


def get_reconciliation_stats(cursor):
    """
    Obtiene estadísticas de conciliación
    usando la vista vw_reconciliation_stats
    """
    cursor.execute("SELECT * FROM vw_reconciliation_stats")
    return cursor.fetchone()


def main():
    print("\n" + "="*80)
    print("🔄 CONCILIACIÓN AUTOMÁTICA DE TRANSACCIONES")
    print("="*80 + "\n")

    # Conectar a PostgreSQL
    print("🔍 Conectando a PostgreSQL...")
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    print("✅ Conexión exitosa\n")

    try:
        # PASO 1: Obtener estadísticas iniciales
        print("📊 ESTADÍSTICAS INICIALES")
        print("-" * 80)

        stats = get_reconciliation_stats(cursor)

        print(f"Total transacciones:     {stats['total_transactions']}")
        print(f"Conciliadas:             {stats['matched']}")
        print(f"Conciliadas manualmente: {stats['manual_matched']}")
        print(f"Revisadas:               {stats['reviewed']}")
        print(f"Pendientes:              {stats['pending']}")
        print(f"Confianza promedio:      {stats['avg_confidence']:.2%}")
        print(f"Tasa de conciliación:    {stats['reconciliation_rate']:.2f}%")

        # PASO 2: Obtener sugerencias de auto-match
        print("\n" + "="*80)
        print("🤖 SUGERENCIAS DE CONCILIACIÓN AUTOMÁTICA")
        print("="*80 + "\n")

        suggestions = get_auto_match_suggestions(cursor)

        if not suggestions:
            print("ℹ️  No hay sugerencias de auto-match disponibles")
            return

        print(f"Se encontraron {len(suggestions)} matches automáticos:\n")

        for i, match in enumerate(suggestions[:10], 1):
            print(f"{i:2d}. TX #{match['transaction_id']}")
            print(f"    📅 Fecha: {match['transaction_date']}")
            print(f"    📝 Descripción: {match['transaction_description'][:60]}")
            print(f"    💰 Monto transacción: ${match['transaction_amount']:,.2f}")
            print(f"    🧾 Factura: {match['invoice_uuid']}")
            print(f"    💵 Total factura: ${match['invoice_total']:,.2f}")
            print(f"    📊 Diferencia: ${match['amount_difference']:.2f} ({match['days_difference']} días)")
            print(f"    🏢 RFC Emisor: {match['rfc_emisor']}")
            print()

        if len(suggestions) > 10:
            print(f"... y {len(suggestions) - 10} matches más\n")

        # PASO 3: Confirmar conciliación
        print("="*80)
        response = input(f"\n¿Deseas conciliar automáticamente estos {len(suggestions)} matches? (si/no): ").strip().lower()

        if response not in ['si', 'sí', 's', 'yes', 'y']:
            print("\n❌ Conciliación cancelada")
            return

        # PASO 4: Aplicar conciliaciones
        print("\n🔄 Aplicando conciliaciones...")

        reconciled_count = 0
        for match in suggestions:
            result = reconcile_transaction(
                cursor,
                transaction_id=match['transaction_id'],
                invoice_id=match['invoice_id'],
                confidence=1.0,  # Alta confianza (match perfecto)
                user_id=None  # Sistema automático
            )

            if result:
                reconciled_count += 1
                if reconciled_count % 5 == 0:
                    print(f"   ✓ {reconciled_count}/{len(suggestions)} conciliadas...")

        # Commit
        conn.commit()

        print(f"\n✅ {reconciled_count} transacciones conciliadas exitosamente")

        # PASO 5: Mostrar estadísticas finales
        print("\n" + "="*80)
        print("📊 ESTADÍSTICAS FINALES")
        print("="*80 + "\n")

        stats_final = get_reconciliation_stats(cursor)

        print(f"Total transacciones:     {stats_final['total_transactions']}")
        print(f"Conciliadas:             {stats_final['matched']} (+{stats_final['matched'] - stats['matched']})")
        print(f"Pendientes:              {stats_final['pending']} (-{stats['pending'] - stats_final['pending']})")
        print(f"Tasa de conciliación:    {stats_final['reconciliation_rate']:.2f}% (+{stats_final['reconciliation_rate'] - stats['reconciliation_rate']:.2f}%)")

        print("\n" + "="*80)
        print("✅ CONCILIACIÓN COMPLETADA")
        print("="*80 + "\n")

        # Queries útiles
        print("🔍 QUERIES ÚTILES PARA VERIFICAR:")
        print(f"   -- Ver todas las conciliaciones")
        print(f"   SELECT * FROM vw_reconciliation_ready WHERE reconciliation_status = 'matched';")
        print()
        print(f"   -- Ver transacciones pendientes")
        print(f"   SELECT * FROM vw_pending_reconciliation;")
        print()
        print(f"   -- Ver estadísticas")
        print(f"   SELECT * FROM vw_reconciliation_stats;")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

    print("\n")


if __name__ == "__main__":
    main()
