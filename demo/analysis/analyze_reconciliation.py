"""
Análisis Detallado de Conciliación

Muestra:
1. Estadísticas mejoradas
2. Desglose por nivel de confianza
3. Transacciones sin factura disponible
4. Categorización de gastos sin CFDI
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuración PostgreSQL
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}


def main():
    print("\n" + "="*90)
    print("📊 ANÁLISIS DETALLADO DE CONCILIACIÓN")
    print("="*90 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Estadísticas generales
        print("📈 ESTADÍSTICAS GENERALES (VISTAS MEJORADAS)")
        print("-" * 90)

        cursor.execute("SELECT * FROM vw_reconciliation_stats_improved")
        stats = cursor.fetchone()

        print(f"{'Total transacciones débito:':<40} {stats['total_transactions']}")
        print(f"{'Transacciones conciliadas:':<40} {stats['matched']}")
        print(f"{'Transacciones pendientes:':<40} {stats['pending']}")
        print(f"{'Tasa de conciliación actual:':<40} {stats['reconciliation_rate']:.2f}%")
        print()
        print(f"{'🤖 AUTO-MATCH DISPONIBLES:':<40}")
        print(f"{'  └─ Perfectos (diff=$0, days≤1):':<40} {stats['auto_match_perfect']} matches")
        print(f"{'  └─ Alta confianza (±$2, ±2d):':<40} {stats['auto_match_high']} matches")
        print(f"{'  └─ Media confianza (±$5, ±3d):':<40} {stats['auto_match_medium']} matches")
        print(f"{'  └─ Baja confianza (±$10, ±5d):':<40} {stats['auto_match_low']} matches")
        print()
        total_auto_matches = (stats['auto_match_perfect'] + stats['auto_match_high'] +
                              stats['auto_match_medium'] + stats['auto_match_low'])
        print(f"{'Total auto-matches disponibles:':<40} {total_auto_matches}")
        print(f"{'Tasa potencial (si se aplican todos):':<40} {stats['potential_reconciliation_rate']:.2f}%")
        print()
        print(f"{'❌ Sin factura disponible:':<40} {stats['no_invoice_found']} transacciones ({stats['no_invoice_found']/stats['total_transactions']*100:.1f}%)")

        # 2. Desglose por nivel de confianza
        print("\n" + "="*90)
        print("🎯 DESGLOSE DE AUTO-MATCHES POR NIVEL")
        print("="*90 + "\n")

        cursor.execute("""
            SELECT
                confidence_label,
                COUNT(*) as total,
                SUM(transaction_amount) as total_amount,
                AVG(amount_difference)::NUMERIC(10,2) as avg_diff,
                AVG(days_difference)::NUMERIC(10,2) as avg_days,
                AVG(match_score)::NUMERIC(10,2) as avg_score
            FROM vw_auto_match_suggestions_improved
            GROUP BY confidence_label
            ORDER BY
                CASE confidence_label
                    WHEN 'Perfecto (0% diff)' THEN 1
                    WHEN 'Alta confianza (±$2, ±2d)' THEN 2
                    WHEN 'Media confianza (±$5, ±3d)' THEN 3
                    WHEN 'Baja confianza (±$10, ±5d)' THEN 4
                END
        """)

        breakdown = cursor.fetchall()

        for row in breakdown:
            print(f"✓ {row['confidence_label']}")
            print(f"  Total: {row['total']} matches | ${row['total_amount']:,.2f}")
            print(f"  Promedio diff: ${row['avg_diff']:.2f} | {row['avg_days']:.1f} días | Score: {row['avg_score']:.0f}/100")
            print()

        # 3. Top 10 auto-matches
        print("="*90)
        print("🏆 TOP 10 AUTO-MATCHES RECOMENDADOS")
        print("="*90 + "\n")

        cursor.execute("""
            SELECT
                transaction_id,
                transaction_date,
                LEFT(transaction_description, 45) as description,
                transaction_amount,
                invoice_total,
                amount_difference,
                days_difference,
                match_score,
                confidence_label
            FROM vw_auto_match_suggestions_improved
            ORDER BY match_score DESC, amount_difference ASC
            LIMIT 10
        """)

        matches = cursor.fetchall()

        for i, m in enumerate(matches, 1):
            emoji = "🎯" if m['match_score'] == 100 else "✓"
            print(f"{emoji} #{i}  TX-{m['transaction_id']} | {m['transaction_date']}")
            print(f"      {m['description']}")
            print(f"      TX: ${m['transaction_amount']:>11,.2f}  |  Factura: ${m['invoice_total']:>11,.2f}  |  Diff: ${m['amount_difference']:.2f}")
            print(f"      Score: {m['match_score']}/100  |  Días: {m['days_difference']}  |  {m['confidence_label']}")
            print()

        # 4. Transacciones sin factura - Análisis por categoría
        print("="*90)
        print("❌ TRANSACCIONES SIN FACTURA DISPONIBLE")
        print("="*90 + "\n")

        cursor.execute("""
            SELECT
                transaction_id,
                transaction_date,
                description,
                amount,
                CASE
                    WHEN description ILIKE '%adobe%' OR description ILIKE '%apple%' OR description ILIKE '%google%'
                         OR description ILIKE '%spotify%' OR description ILIKE '%netflix%' THEN 'Suscripciones Tech'
                    WHEN description ILIKE '%gasolinero%' OR description ILIKE '%gasol%' THEN 'Gasolina'
                    WHEN description ILIKE '%comision%' THEN 'Comisiones Bancarias'
                    WHEN description ILIKE '%recarga%' OR description ILIKE '%tutag%' THEN 'Recargas/Peajes'
                    WHEN description ILIKE '%telcel%' OR description ILIKE '%telmex%' THEN 'Telecomunicaciones'
                    WHEN description ILIKE '%restaur%' OR description ILIKE '%sushi%' OR description ILIKE '%polanquito%'
                         OR description ILIKE '%guerras%' THEN 'Alimentos/Restaurantes'
                    WHEN description ILIKE '%traspaso%' OR description ILIKE '%spei%' THEN 'Traspasos'
                    WHEN description ILIKE '%domiciliacion%' THEN 'Domiciliación'
                    ELSE 'Otros'
                END as categoria
            FROM vw_transactions_without_invoice
            ORDER BY amount DESC
        """)

        no_invoice = cursor.fetchall()

        # Agrupar por categoría
        from collections import defaultdict
        por_categoria = defaultdict(list)
        for tx in no_invoice:
            por_categoria[tx['categoria']].append(tx)

        total_sin_factura = len(no_invoice)
        monto_total_sin_factura = sum(abs(tx['amount']) for tx in no_invoice)

        print(f"Total transacciones sin factura: {total_sin_factura} (${monto_total_sin_factura:,.2f})")
        print()

        for categoria, txs in sorted(por_categoria.items(), key=lambda x: -sum(abs(t['amount']) for t in x[1])):
            total_cat = len(txs)
            monto_cat = sum(abs(tx['amount']) for tx in txs)
            print(f"📁 {categoria}")
            print(f"   Total: {total_cat} transacciones | ${monto_cat:,.2f}")

            # Mostrar top 3 de esta categoría
            for tx in sorted(txs, key=lambda x: -abs(x['amount']))[:3]:
                print(f"   └─ TX-{tx['transaction_id']} | {tx['transaction_date']} | ${abs(tx['amount']):>8,.2f} | {tx['description'][:40]}")
            print()

        # 5. Recomendaciones
        print("="*90)
        print("💡 RECOMENDACIONES")
        print("="*90 + "\n")

        print(f"1. ✅ APLICAR AUTO-MATCHES ({total_auto_matches} matches)")
        print(f"   Esto subirá la tasa de: {stats['reconciliation_rate']:.1f}% → {stats['potential_reconciliation_rate']:.1f}%")
        print()

        print(f"2. 📋 SOLICITAR CFDIs FALTANTES")
        print(f"   {total_sin_factura} transacciones sin factura (${monto_total_sin_factura:,.2f})")
        print(f"   Categorías principales:")
        for categoria, txs in sorted(por_categoria.items(), key=lambda x: -sum(abs(t['amount']) for t in x[1]))[:5]:
            monto = sum(abs(tx['amount']) for tx in txs)
            print(f"   - {categoria}: ${monto:,.2f}")
        print()

        print(f"3. 🎯 TASA MÁXIMA ALCANZABLE")
        # Tasa máxima = (transacciones con factura disponible) / total
        transacciones_con_factura_disponible = stats['total_transactions'] - stats['no_invoice_found']
        tasa_maxima = (transacciones_con_factura_disponible / stats['total_transactions']) * 100
        print(f"   Con las facturas actuales: {tasa_maxima:.1f}%")
        print(f"   Para llegar a 90%+: Necesitas CFDIs para {stats['no_invoice_found']} transacciones más")
        print()

        print("="*90)
        print("🚀 SIGUIENTE PASO: Ejecuta 'python reconcile_auto_matches.py' para aplicar los matches")
        print("="*90 + "\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
