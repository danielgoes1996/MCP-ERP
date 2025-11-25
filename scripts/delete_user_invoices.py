#!/usr/bin/env python3
"""
Delete all invoices for a specific user email.
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

def delete_invoices_for_user(email: str, dry_run: bool = True):
    """Delete all invoices for a user by email."""

    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        # 1. Find user and company
        cursor.execute("""
            SELECT
                u.id as user_id,
                u.email,
                c.id as company_id,
                c.name as company_name
            FROM users u
            JOIN companies c ON u.company_id = c.id
            WHERE u.email = %s
        """, (email,))

        user_info = cursor.fetchone()

        if not user_info:
            print(f"❌ User not found: {email}")
            return

        print(f"\n📋 User Info:")
        print(f"   Email: {user_info['email']}")
        print(f"   User ID: {user_info['user_id']}")
        print(f"   Company: {user_info['company_name']} (ID: {user_info['company_id']})")

        company_id = user_info['company_id']

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

        # 3. Show sample invoices
        cursor.execute("""
            SELECT
                id,
                session_id,
                cfdi_uuid,
                (parsed_data->>'emisor'->>'nombre') as provider_name,
                (accounting_classification->>'sat_account_code') as sat_code,
                (accounting_classification->>'status') as status
            FROM expense_invoices
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (company_id,))

        samples = cursor.fetchall()
        print(f"\n📄 Sample invoices (showing {len(samples)} of {invoice_count}):")
        for inv in samples:
            print(f"   - ID: {inv['id']}, UUID: {inv['cfdi_uuid'][:20] if inv['cfdi_uuid'] else 'N/A'}..., Status: {inv['status'] or 'N/A'}")

        if dry_run:
            print(f"\n⚠️  DRY RUN MODE - No data deleted")
            print(f"   Run with --delete flag to actually delete {invoice_count} invoices")
            return

        # 4. Delete from related tables first (corrections, sessions)
        print(f"\n🗑️  Deleting related data...")

        # Delete correction memory
        cursor.execute("""
            DELETE FROM ai_correction_memory
            WHERE company_id = %s
        """, (company_id,))
        corrections_deleted = cursor.rowcount
        print(f"   ✓ Deleted {corrections_deleted} correction memory entries")

        # Delete sessions
        cursor.execute("""
            DELETE FROM sat_invoices
            WHERE company_id = %s
        """, (company_id,))
        sessions_deleted = cursor.rowcount
        print(f"   ✓ Deleted {sessions_deleted} invoice sessions")

        # 5. Delete invoices
        cursor.execute("""
            DELETE FROM expense_invoices
            WHERE company_id = %s
        """, (company_id,))
        invoices_deleted = cursor.rowcount
        print(f"   ✓ Deleted {invoices_deleted} expense invoices")

        # Commit
        conn.commit()

        print(f"\n✅ Successfully deleted all data for {email}")
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

    parser = argparse.ArgumentParser(description="Delete all invoices for a user")
    parser.add_argument("email", help="User email address")
    parser.add_argument("--delete", action="store_true", help="Actually delete (default is dry run)")

    args = parser.parse_args()

    delete_invoices_for_user(args.email, dry_run=not args.delete)
