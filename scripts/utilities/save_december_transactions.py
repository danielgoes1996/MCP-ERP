#!/usr/bin/env python3
"""
Save December transactions to database for user to see in interface
"""
import os
import sys
sys.path.append('.')

from core.reconciliation.bank.bank_file_parser import BankFileParser
import sqlite3

def save_december_transactions():
    print("🔍 Processing and saving December transactions...")

    pdf_path = "./uploads/statements/9_20250928_211924_Periodo_DIC 2024 (1).pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return

    try:
        # Clear existing data first
        conn = sqlite3.connect("unified_mcp_system.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements WHERE account_id = 7")
        cursor.execute("DELETE FROM bank_statements WHERE account_id = 7")
        conn.commit()
        print("🗑️ Cleared existing December data")

        # Use bank file parser (which has fallback logic working now)
        parser = BankFileParser()
        transactions, summary = parser.parse_file(pdf_path, "pdf", 7, 1, 1)

        print(f"✅ Processing completed!")
        print(f"📊 Total transactions: {len(transactions)}")

        # Add bank statement record with proper columns
        file_name = os.path.basename(pdf_path)
        cursor.execute("""
            INSERT INTO bank_statements (
                account_id, user_id, tenant_id, file_name, file_path, file_type,
                period_start, period_end, transaction_count, total_credits, total_debits,
                parsing_status, parsed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            7, 1, 1, file_name, pdf_path, "pdf",
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
        for i, txn in enumerate(transactions[:3]):
            print(f"  {i+1}. {txn.date} - {txn.description[:40]} - ${txn.amount}")
            print(f"     Format: {txn.raw_data[:30]}...")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    save_december_transactions()