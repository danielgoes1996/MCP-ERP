#!/usr/bin/env python3
"""
Parse PDF with LLM for exact CARGOS/ABONOS extraction
"""
import os
import sqlite3
from core.llm_pdf_parser import parse_pdf_with_llm

# Configure API key
os.environ['ANTHROPIC_API_KEY'] = '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'

def main():
    pdf_path = '/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf'

    print("🤖 Procesando PDF con parser LLM (Claude)...")

    try:
        transactions, summary = parse_pdf_with_llm(pdf_path, 5, 9, 3)
        print(f"✅ Extraídas {len(transactions)} transacciones con LLM")

        # Guardar en base de datos
        conn = sqlite3.connect('unified_mcp_system.db')
        cursor = conn.cursor()

        saved_count = 0
        for txn in transactions:
            try:
                cursor.execute("""
                    INSERT INTO bank_movements
                    (account_id, user_id, tenant_id, date, description, amount, transaction_type,
                     category, confidence, raw_data, movement_kind, reference, balance_after)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    txn.account_id, txn.user_id, txn.tenant_id, str(txn.date),
                    txn.description, txn.amount,
                    txn.transaction_type.value if hasattr(txn.transaction_type, 'value') else str(txn.transaction_type),
                    txn.category, txn.confidence, txn.raw_data,
                    txn.movement_kind.value if hasattr(txn.movement_kind, 'value') else str(txn.movement_kind),
                    txn.reference, txn.balance_after
                ))
                saved_count += 1
            except Exception as e:
                print(f"Error guardando transacción: {e}")

        conn.commit()
        print(f"✅ Guardadas {saved_count} transacciones válidas")

        # Mostrar estadísticas finales
        cursor.execute("""
            SELECT
                movement_kind,
                COUNT(*) as count,
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_positive,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_negative
            FROM bank_movements
            WHERE account_id = 5 AND user_id = 9
            GROUP BY movement_kind
        """)

        results = cursor.fetchall()
        print("\n📈 Estadísticas finales con LLM:")
        total_transactions = 0
        for row in results:
            kind, count, positive, negative = row
            total = positive + negative
            print(f"  {kind}: {count} transacciones, ${total:,.2f}")
            total_transactions += count

        print(f"\n🎯 Total final: {total_transactions} transacciones en AMEX Gold")

        # Comparar con objetivos (mapear a terminología CARGO/ABONO)
        print(f"\n🎯 Comparación con objetivos:")
        for row in results:
            kind, count, positive, negative = row
            if kind.upper() == 'GASTO':  # GASTO representa CARGOS
                print(f"  CARGOS: ${negative:,.2f} (objetivo: $49,753.10)")
            elif kind.upper() == 'INGRESO':  # INGRESO representa ABONOS
                print(f"  ABONOS: ${positive:,.2f} (objetivo: $52,472.12)")

        # Mostrar algunas transacciones de ejemplo
        cursor.execute("""
            SELECT date, description, amount, movement_kind
            FROM bank_movements
            WHERE account_id = 5 AND user_id = 9
            ORDER BY date DESC
            LIMIT 10
        """)

        examples = cursor.fetchall()
        print("\n📝 Ejemplos de transacciones extraídas por LLM:")
        for i, (date, desc, amount, kind) in enumerate(examples):
            print(f"  {i+1}. {date} | {kind} | ${amount:8.2f} | {desc[:50]}...")

        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()