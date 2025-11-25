#!/usr/bin/env python3
"""
Delete all invoices for a specific company.
Used to clean up test data before starting fresh testing.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys

POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
    'port': int(os.getenv('POSTGRES_PORT', '5433')),
    'database': os.getenv('POSTGRES_DB', 'mcp_system'),
    'user': os.getenv('POSTGRES_USER', 'mcp_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'changeme')
}

def delete_invoices_for_company(company_id: int, dry_run: bool = True):
    """Delete all invoices for a company by ID."""

    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        # 1. Find company
        cursor.execute("""
            SELECT
                id as company_id,
                name as company_name
            FROM companies
            WHERE id = %s
        """, (company_id,))

        company_info = cursor.fetchone()

        if not company_info:
            print(f"❌ Company not found: {company_id}")
            return

        print(f"\n📋 Company Info:")
        print(f"   Name: {company_info['company_name']}")
        print(f"   ID: {company_info['company_id']}")

        # 2. Count invoices
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM expense_invoices
            WHERE company_id = %s
        """, (company_id,))

        invoice_count = cursor.fetchone()['count']
        print(f"\n📊 Found {invoice_count} invoices to delete")

        if invoice_count == 0:
            print("✅ No invoices to delete")
            return

        # 3. Show sample invoice IDs
        cursor.execute("""
            SELECT id
            FROM expense_invoices
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (company_id,))

        samples = cursor.fetchall()
        print(f"\n📄 Sample invoice IDs (showing {len(samples)} of {invoice_count}):")
        for inv in samples:
            print(f"   - ID: {inv['id']}")

        # 4. Count corrections
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM ai_correction_memory
            WHERE company_id = %s
        """, (company_id,))

        correction_count = cursor.fetchone()['count']
        print(f"\n🔄 Found {correction_count} correction memory entries")

        if dry_run:
            print(f"\n⚠️  DRY RUN MODE - No data deleted")
            print(f"   Run with --delete flag to actually delete:")
            print(f"   - {invoice_count} invoices")
            print(f"   - {correction_count} correction memory entries")
            print(f"   - Related sessions")
            return

        # 5. Delete from related tables first
        print(f"\n🗑️  Deleting related data...")

        # Delete correction memory
        cursor.execute("""
            DELETE FROM ai_correction_memory
            WHERE company_id = %s
        """, (company_id,))
        corrections_deleted = cursor.rowcount
        print(f"   ✓ Deleted {corrections_deleted} correction memory entries")

        # Delete sessions (company_id is TEXT in this table)
        cursor.execute("""
            DELETE FROM sat_invoices
            WHERE company_id = %s
        """, (str(company_id),))
        sessions_deleted = cursor.rowcount
        print(f"   ✓ Deleted {sessions_deleted} invoice sessions")

        # Delete invoices
        cursor.execute("""
            DELETE FROM expense_invoices
            WHERE company_id = %s
        """, (company_id,))
        invoices_deleted = cursor.rowcount
        print(f"   ✓ Deleted {invoices_deleted} expense invoices")

        # Commit
        conn.commit()

        print(f"\n✅ Successfully deleted all data for company {company_info['company_name']}")
        print(f"   Total items deleted: {corrections_deleted + sessions_deleted + invoices_deleted}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Delete all invoices for a company")
    parser.add_argument("company_id", type=int, help="Company ID")
    parser.add_argument("--delete", action="store_true", help="Actually delete (default is dry run)")

    args = parser.parse_args()

    delete_invoices_for_company(args.company_id, dry_run=not args.delete)
