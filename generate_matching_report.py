"""
Genera reporte completo de matching en formato tabla
Incluye: Matches perfectos, matches IA, y sin match
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

# Matches de IA (del test anterior)
AI_MATCHES = {
    4: {"invoice_name": "BANCO INBURSA", "similarity": 80, "diff": 10988.82, "confidence": "MEDIUM"},
    36: {"invoice_name": "GRUPO GASOLINERO BERISA", "similarity": 80, "diff": 11.56, "confidence": "MEDIUM"},
    42: {"invoice_name": "TELEFONOS DE MEXICO", "similarity": 75, "diff": 351.24, "confidence": "MEDIUM"},
    33: {"invoice_name": "TELEFONOS DE MEXICO", "similarity": 75, "diff": 0.01, "confidence": "MEDIUM"},
    44: {"invoice_name": "ODOO TECHNOLOGIES", "similarity": 75, "diff": 336.92, "confidence": "MEDIUM"},
    46: {"invoice_name": "GRUPO GASOLINERO BERISA", "similarity": 85, "diff": 420.41, "confidence": "LOW"},
    48: {"invoice_name": "FINKOK", "similarity": 70, "diff": 14.78, "confidence": "LOW"},
    26: {"invoice_name": "DISTRIBUIDORA PREZ", "similarity": 70, "diff": 3.70, "confidence": "LOW"},
    27: {"invoice_name": "DISTRIBUIDORA PREZ", "similarity": 70, "diff": 2.30, "confidence": "LOW"},
}


def main():
    print("\n" + "="*120)
    print("📊 REPORTE COMPLETO DE MATCHING - ENERO 2025")
    print("="*120 + "\n")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Obtener todas las transacciones con su mejor match
        cursor.execute("""
            WITH best_matches AS (
              SELECT
                vr.transaction_id,
                vr.invoice_id,
                vr.nombre_emisor,
                vr.amount_difference,
                vr.days_difference,
                vr.match_status,
                vr.match_score
              FROM vw_reconciliation_ready_improved vr
              WHERE vr.match_rank = 1
            )
            SELECT
              bt.id,
              bt.transaction_date,
              bt.description,
              bt.amount,
              bm.invoice_id,
              bm.nombre_emisor,
              bm.amount_difference,
              bm.days_difference,
              bm.match_status,
              bm.match_score
            FROM bank_transactions bt
            LEFT JOIN best_matches bm ON bt.id = bm.transaction_id
            WHERE bt.transaction_type = 'debit'
            ORDER BY bt.transaction_date DESC
        """)

        transactions = cursor.fetchall()

        # Clasificar transacciones
        perfect_matches = []
        ai_matches = []
        no_matches = []

        for tx in transactions:
            if tx['match_status'] and 'AUTO_MATCH' in tx['match_status']:
                perfect_matches.append(tx)
            elif tx['id'] in AI_MATCHES:
                ai_matches.append(tx)
            else:
                no_matches.append(tx)

        # Mostrar tabla de matches perfectos
        if perfect_matches:
            print("✅ MATCHES PERFECTOS (Aplicar automáticamente)")
            print("-" * 120)
            print(f"{'ID':<4} {'Fecha':<12} {'Descripción TX':<35} {'Monto':>12} {'CFDI Candidato':<30} {'Diff $':>10} {'Score':>6}")
            print("-" * 120)

            for tx in perfect_matches:
                print(f"{tx['id']:<4} {str(tx['transaction_date']):<12} {tx['description'][:35]:<35} "
                      f"${abs(tx['amount']):>10,.2f} {(tx['nombre_emisor'] or '')[:30]:<30} "
                      f"${tx['amount_difference']:>9,.2f} {tx['match_score']:>6}")

            print(f"\nTotal: {len(perfect_matches)} matches perfectos\n")

        # Mostrar tabla de matches IA
        if ai_matches:
            print("\n🤖 MATCHES DETECTADOS POR IA (Revisar antes de aplicar)")
            print("-" * 120)
            print(f"{'ID':<4} {'Fecha':<12} {'Descripción TX':<35} {'Monto':>12} {'CFDI Candidato (IA)':<30} {'Diff $':>10} {'Conf':>8}")
            print("-" * 120)

            for tx in ai_matches:
                ai_info = AI_MATCHES[tx['id']]
                conf_emoji = "🎯" if ai_info['confidence'] == "HIGH" else "✓" if ai_info['confidence'] == "MEDIUM" else "⚠️"
                print(f"{tx['id']:<4} {str(tx['transaction_date']):<12} {tx['description'][:35]:<35} "
                      f"${abs(tx['amount']):>10,.2f} {ai_info['invoice_name'][:30]:<30} "
                      f"${ai_info['diff']:>9,.2f} {conf_emoji} {ai_info['similarity']:>3}%")

            print(f"\nTotal: {len(ai_matches)} matches detectados por IA\n")

        # Mostrar tabla sin matches
        if no_matches:
            print("\n❌ SIN MATCH DISPONIBLE (Solicitar CFDIs)")
            print("-" * 120)
            print(f"{'ID':<4} {'Fecha':<12} {'Descripción':<50} {'Monto':>12} {'Categoría':<30}")
            print("-" * 120)

            for tx in no_matches:
                desc = tx['description']
                # Categorizar
                if 'APPLE' in desc or 'ADOBE' in desc or 'GOOGLE' in desc:
                    categoria = "Suscripciones Tech"
                elif 'GASOLINERO' in desc or 'GASOL' in desc:
                    categoria = "Gasolina sin factura"
                elif 'COMISION' in desc or 'IVA' in desc or 'ISR' in desc:
                    categoria = "Comisiones/Impuestos"
                elif 'RECARGA' in desc or 'TUTAG' in desc:
                    categoria = "Recargas/Peajes"
                elif 'TELCEL' in desc or 'TELMEX' in desc:
                    categoria = "Telecomunicaciones"
                elif 'TRASPASO' in desc or 'SPEI' in desc:
                    categoria = "Traspasos internos"
                elif 'SUSHI' in desc or 'TAQUERIA' in desc or 'STARBUCKS' in desc or 'POLANQUITO' in desc or 'GUERRAS' in desc:
                    categoria = "Alimentos/Restaurantes"
                else:
                    categoria = "Otros"

                print(f"{tx['id']:<4} {str(tx['transaction_date']):<12} {desc[:50]:<50} ${abs(tx['amount']):>10,.2f} {categoria:<30}")

            print(f"\nTotal: {len(no_matches)} sin match\n")

        # Resumen
        print("\n" + "="*120)
        print("📈 RESUMEN GENERAL")
        print("="*120 + "\n")

        total = len(transactions)
        print(f"Total transacciones débito:           {total}")
        print(f"✅ Matches perfectos (auto):          {len(perfect_matches):>3} ({len(perfect_matches)/total*100:>5.1f}%)")
        print(f"🤖 Matches IA (revisar):              {len(ai_matches):>3} ({len(ai_matches)/total*100:>5.1f}%)")
        print(f"❌ Sin match:                         {len(no_matches):>3} ({len(no_matches)/total*100:>5.1f}%)")
        print()

        # Calcular monto por categoría
        monto_perfect = sum(abs(tx['amount']) for tx in perfect_matches)
        monto_ai = sum(abs(tx['amount']) for tx in ai_matches)
        monto_no_match = sum(abs(tx['amount']) for tx in no_matches)
        monto_total = monto_perfect + monto_ai + monto_no_match

        print(f"💰 MONTOS:")
        print(f"✅ Matches perfectos:                 ${monto_perfect:>10,.2f} ({monto_perfect/monto_total*100:>5.1f}%)")
        print(f"🤖 Matches IA:                        ${monto_ai:>10,.2f} ({monto_ai/monto_total*100:>5.1f}%)")
        print(f"❌ Sin match:                         ${monto_no_match:>10,.2f} ({monto_no_match/monto_total*100:>5.1f}%)")
        print(f"   {'─'*40}")
        print(f"   TOTAL:                             ${monto_total:>10,.2f}")

        # Tasa de conciliación
        print()
        print(f"📊 TASAS DE CONCILIACIÓN:")
        print(f"   Actual (sin aplicar):               0.0%")
        print(f"   Con matches perfectos:              {len(perfect_matches)/total*100:.1f}%")
        print(f"   Con matches perfectos + IA:         {(len(perfect_matches) + len(ai_matches))/total*100:.1f}%")
        print(f"   Máxima alcanzable (100%):           {(len(perfect_matches) + len(ai_matches))/total*100:.1f}%")

        print("\n" + "="*120)
        print("💡 RECOMENDACIONES")
        print("="*120 + "\n")

        print(f"1. ✅ APLICAR AUTOMÁTICAMENTE los {len(perfect_matches)} matches perfectos")
        print(f"   → Esto subirá la tasa de 0% a {len(perfect_matches)/total*100:.1f}%")
        print()

        print(f"2. 🤖 REVISAR MANUALMENTE los {len(ai_matches)} matches de IA")
        print(f"   Recomendados para aplicar:")
        high_conf = [tx for tx in ai_matches if AI_MATCHES[tx['id']]['confidence'] in ['HIGH', 'MEDIUM'] and AI_MATCHES[tx['id']]['diff'] < 50]
        print(f"   • Confianza MEDIUM con diff < $50:  {len(high_conf)} matches")
        print(f"   → Esto subiría la tasa adicional en {len(high_conf)/total*100:.1f}%")
        print()

        print(f"3. 📋 SOLICITAR CFDIs FALTANTES para {len(no_matches)} transacciones")
        print(f"   Priorizar:")
        print(f"   • Gasolineras:        ${sum(abs(tx['amount']) for tx in no_matches if 'GASOL' in tx['description']):,.2f}")
        print(f"   • Restaurantes:       ${sum(abs(tx['amount']) for tx in no_matches if any(x in tx['description'] for x in ['SUSHI', 'TAQUERIA', 'STARBUCKS', 'POLANQUITO', 'GUERRAS'])):,.2f}")
        print(f"   • Telecomunicaciones: ${sum(abs(tx['amount']) for tx in no_matches if 'TELCEL' in tx['description']):,.2f}")

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
