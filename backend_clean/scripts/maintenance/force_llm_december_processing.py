#!/usr/bin/env python3
"""
Force December processing with LLM parser only (no fallback)
"""
import os
import sys
sys.path.append('.')

from core.llm_pdf_parser import parse_pdf_with_llm
import sqlite3

def force_llm_december_processing():
    print("🔍 Force processing December with LLM parser only...")

    pdf_path = "./uploads/statements/9_20250928_211924_Periodo_DIC 2024 (1).pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return

    try:
        # Force LLM parser processing (account 7, user 9, tenant 3)
        print("🤖 Processing with LLM parser only...")
        transactions, summary = parse_pdf_with_llm(pdf_path, 7, 9, 3)

        print(f"✅ LLM Processing completed!")
        print(f"📊 Total transactions: {len(transactions)}")
        print(f"📊 Summary: {summary}")

        # Save to database
        conn = sqlite3.connect("unified_mcp_system.db")
        cursor = conn.cursor()

        # Add bank statement record with proper columns
        file_name = os.path.basename(pdf_path)
        cursor.execute("""
            INSERT INTO bank_statements (
                account_id, user_id, tenant_id, file_name, file_path, file_type,
                period_start, period_end, transaction_count, total_credits, total_debits,
                parsing_status, parsed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            7, 9, 3, file_name, pdf_path, "pdf",
            summary.get('period_start'), summary.get('period_end'),
            len(transactions), summary.get('total_credits', 0),
            abs(summary.get('total_debits', 0)), 'completed'
        ))

        # Save transactions to database
        for txn in transactions:
            cursor.execute("""
                INSERT INTO bank_movements (
                    account_id, user_id, tenant_id, date, description, amount,
                    transaction_type, raw_data, movement_kind, reference, balance_after
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                txn.account_id, txn.user_id, txn.tenant_id, txn.date, txn.description,
                txn.amount, txn.transaction_type, txn.raw_data,
                txn.movement_kind if txn.movement_kind else None,
                txn.reference, txn.balance_after
            ))

        conn.commit()
        conn.close()

        print(f"✅ Saved {len(transactions)} transactions to database")
        print(f"📊 Summary:")
        print(f"  - Period: {summary.get('period_start')} to {summary.get('period_end')}")
        print(f"  - Credits: ${summary.get('total_credits', 0):,.2f}")
        print(f"  - Debits: ${abs(summary.get('total_debits', 0)):,.2f}")

        # Show first few transactions
        print(f"\n📋 Sample transactions:")
        for i, txn in enumerate(transactions[:5]):
            print(f"  {i+1}. {txn.date} - {txn.description[:40]} - ${txn.amount}")
            print(f"     Format: {txn.raw_data[:50]}...")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    force_llm_december_processing()