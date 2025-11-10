#!/usr/bin/env python3
"""
Parse PDF using robust parser with corrected 2024 dates
"""
from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser
from core.shared.unified_db_adapter import UnifiedDBAdapter

def main():
    pdf_path = '/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf'

    print(f"🤖 Parsing PDF with robust parser: {pdf_path}")

    parser = RobustPDFParser()
    try:
        transactions, summary = parser.parse_transactions(pdf_path, 5, 9, 3)
        print(f"✅ Processed {len(transactions)} transactions")

        # Show first few transactions to verify dates
        for i, txn in enumerate(transactions[:10]):
            print(f"{i+1:2d}. {txn.date} | {txn.movement_kind:12s} | ${txn.amount:8.2f} | {txn.description[:50]}...")

        # Save to database
        print("\n💾 Saving to database...")
        db_adapter = UnifiedDBAdapter('unified_mcp_system.db')

        for txn in transactions:
            try:
                # Insert the transaction
                db_adapter.execute_query(
                    "INSERT INTO bank_movements (account_id, user_id, tenant_id, date, description, amount, transaction_type, category, confidence, raw_data, movement_kind, reference, balance_after) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (txn.account_id, txn.user_id, txn.tenant_id, str(txn.date), txn.description, txn.amount, txn.transaction_type.value, txn.category, txn.confidence, txn.raw_data, txn.movement_kind.value, txn.reference, txn.balance_after)
                )
            except Exception as e:
                if "UNIQUE constraint failed" not in str(e):
                    print(f"⚠️ Error saving transaction: {e}")
                continue

        print(f"✅ Saved {len(transactions)} transactions to database")

        # Verify dates in database
        result = db_adapter.fetch_all("SELECT DISTINCT substr(date, 1, 7) as year_month, COUNT(*) FROM bank_movements WHERE account_id = 5 AND user_id = 9 GROUP BY year_month ORDER BY year_month")
        print(f"📊 Date distribution: {result}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()