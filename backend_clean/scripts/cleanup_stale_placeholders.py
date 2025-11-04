#!/usr/bin/env python3
"""
Cleanup script for stale expense placeholders.

This script implements a 4-tier expiration policy:
- Tier 1 (7-14 days): Warning notification
- Tier 2 (14-30 days): Urgent notification
- Tier 3 (30-60 days): Auto-archive to separate table
- Tier 4 (>60 days): Permanent deletion

Usage:
    python scripts/cleanup_stale_placeholders.py [--dry-run] [--company-id <id>]

Options:
    --dry-run       Show what would be deleted/archived without actually doing it
    --company-id    Target specific company (default: all companies)
    --verbose       Show detailed logging
"""
import argparse
import sqlite3
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.structured_logger import (
    setup_structured_logging,
    get_structured_logger,
    set_request_context
)


logger = get_structured_logger(__name__)


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect('unified_mcp_system.db')


def create_archive_table_if_not_exists(conn: sqlite3.Connection):
    """Create archived_placeholders table if it doesn't exist."""
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS archived_placeholders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_expense_id INTEGER NOT NULL,
        description TEXT,
        amount REAL,
        company_id TEXT,
        workflow_status TEXT,
        missing_fields TEXT,
        created_at TEXT,
        archived_at TEXT,
        archived_reason TEXT,
        metadata TEXT
    )
    """)

    conn.commit()
    logger.info("Ensured archived_placeholders table exists")


def get_stale_placeholders_by_tier(
    conn: sqlite3.Connection,
    company_id: str = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get stale placeholders grouped by expiration tier.

    Returns:
        {
            'tier1_warning': [...],    # 7-14 days old
            'tier2_urgent': [...],     # 14-30 days old
            'tier3_archive': [...],    # 30-60 days old
            'tier4_delete': [...]      # >60 days old
        }
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    company_filter = f"AND company_id = '{company_id}'" if company_id else ""

    query = f"""
    SELECT
        id,
        description,
        amount,
        company_id,
        workflow_status,
        metadata,
        created_at,
        (julianday('now') - julianday(created_at)) as days_old
    FROM expense_records
    WHERE workflow_status = 'requiere_completar'
    {company_filter}
    AND (julianday('now') - julianday(created_at)) >= 7
    ORDER BY created_at ASC
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    tiers = {
        'tier1_warning': [],
        'tier2_urgent': [],
        'tier3_archive': [],
        'tier4_delete': []
    }

    for row in rows:
        expense_data = {
            'id': row['id'],
            'description': row['description'],
            'amount': row['amount'],
            'company_id': row['company_id'],
            'workflow_status': row['workflow_status'],
            'metadata': row['metadata'],
            'created_at': row['created_at'],
            'days_old': row['days_old']
        }

        # Parse missing fields from metadata
        if row['metadata']:
            try:
                metadata = json.loads(row['metadata'])
                expense_data['missing_fields'] = metadata.get('missing_fields', [])
            except:
                expense_data['missing_fields'] = []

        days_old = row['days_old']

        if days_old >= 60:
            tiers['tier4_delete'].append(expense_data)
        elif days_old >= 30:
            tiers['tier3_archive'].append(expense_data)
        elif days_old >= 14:
            tiers['tier2_urgent'].append(expense_data)
        elif days_old >= 7:
            tiers['tier1_warning'].append(expense_data)

    return tiers


def send_warning_notification(expense: Dict[str, Any], tier: str):
    """
    Send warning notification for stale placeholder.

    In production, this would send email/Slack/etc.
    For now, just log the warning.
    """
    logger.warning(
        f"{tier.upper()} notification",
        extra={
            'expense_id': expense['id'],
            'days_old': round(expense['days_old'], 1),
            'company_id': expense['company_id'],
            'missing_fields': expense.get('missing_fields', []),
            'tier': tier
        }
    )


def archive_placeholder(
    conn: sqlite3.Connection,
    expense: Dict[str, Any],
    dry_run: bool = False
) -> bool:
    """Archive a stale placeholder to archived_placeholders table."""
    if dry_run:
        logger.info(
            f"[DRY RUN] Would archive expense {expense['id']}",
            extra={'expense_id': expense['id'], 'days_old': round(expense['days_old'], 1)}
        )
        return True

    cursor = conn.cursor()

    try:
        # Insert into archive table
        cursor.execute("""
        INSERT INTO archived_placeholders (
            original_expense_id, description, amount, company_id,
            workflow_status, missing_fields, created_at, archived_at,
            archived_reason, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense['id'],
            expense['description'],
            expense['amount'],
            expense['company_id'],
            expense['workflow_status'],
            json.dumps(expense.get('missing_fields', [])),
            expense['created_at'],
            datetime.utcnow().isoformat(),
            f"Auto-archived after {int(expense['days_old'])} days",
            expense.get('metadata')
        ))

        # Delete from expense_records
        cursor.execute("DELETE FROM expense_records WHERE id = ?", (expense['id'],))

        conn.commit()

        logger.info(
            f"Archived expense {expense['id']}",
            extra={
                'expense_id': expense['id'],
                'days_old': round(expense['days_old'], 1),
                'company_id': expense['company_id']
            }
        )
        return True

    except Exception as e:
        conn.rollback()
        logger.error(
            f"Failed to archive expense {expense['id']}: {e}",
            extra={'expense_id': expense['id']}
        )
        return False


def delete_placeholder(
    conn: sqlite3.Connection,
    expense: Dict[str, Any],
    dry_run: bool = False
) -> bool:
    """Permanently delete a very old placeholder."""
    if dry_run:
        logger.info(
            f"[DRY RUN] Would delete expense {expense['id']}",
            extra={'expense_id': expense['id'], 'days_old': round(expense['days_old'], 1)}
        )
        return True

    cursor = conn.cursor()

    try:
        # Log deletion to audit trail (in metadata)
        cursor.execute("""
        INSERT INTO archived_placeholders (
            original_expense_id, description, amount, company_id,
            workflow_status, missing_fields, created_at, archived_at,
            archived_reason, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense['id'],
            expense['description'],
            expense['amount'],
            expense['company_id'],
            expense['workflow_status'],
            json.dumps(expense.get('missing_fields', [])),
            expense['created_at'],
            datetime.utcnow().isoformat(),
            f"Auto-deleted after {int(expense['days_old'])} days (expired)",
            expense.get('metadata')
        ))

        # Delete from expense_records
        cursor.execute("DELETE FROM expense_records WHERE id = ?", (expense['id'],))

        conn.commit()

        logger.warning(
            f"Deleted expired expense {expense['id']}",
            extra={
                'expense_id': expense['id'],
                'days_old': round(expense['days_old'], 1),
                'company_id': expense['company_id'],
                'action': 'permanent_delete'
            }
        )
        return True

    except Exception as e:
        conn.rollback()
        logger.error(
            f"Failed to delete expense {expense['id']}: {e}",
            extra={'expense_id': expense['id']}
        )
        return False


def run_cleanup(dry_run: bool = False, company_id: str = None, verbose: bool = False):
    """
    Run the cleanup process for stale placeholders.

    Args:
        dry_run: If True, only show what would be done without actually doing it
        company_id: Target specific company (None for all)
        verbose: Show detailed logging
    """
    # Setup logging
    setup_structured_logging(
        level="DEBUG" if verbose else "INFO",
        enable_console=True
    )

    set_request_context(
        tenant_id=company_id or "all",
        action="cleanup_stale_placeholders"
    )

    logger.info(
        f"Starting stale placeholder cleanup {'(DRY RUN)' if dry_run else ''}",
        extra={'company_id': company_id or 'all', 'dry_run': dry_run}
    )

    conn = get_db_connection()

    # Create archive table if needed
    create_archive_table_if_not_exists(conn)

    # Get stale placeholders grouped by tier
    tiers = get_stale_placeholders_by_tier(conn, company_id)

    stats = {
        'tier1_warning_count': len(tiers['tier1_warning']),
        'tier2_urgent_count': len(tiers['tier2_urgent']),
        'tier3_archived_count': 0,
        'tier4_deleted_count': 0,
        'errors': 0
    }

    # Tier 1: Warning notifications (7-14 days)
    print(f"\n📊 Tier 1 (7-14 days): {stats['tier1_warning_count']} placeholders")
    for expense in tiers['tier1_warning']:
        send_warning_notification(expense, 'tier1_warning')

    # Tier 2: Urgent notifications (14-30 days)
    print(f"📊 Tier 2 (14-30 days): {stats['tier2_urgent_count']} placeholders")
    for expense in tiers['tier2_urgent']:
        send_warning_notification(expense, 'tier2_urgent')

    # Tier 3: Archive (30-60 days)
    print(f"\n📦 Tier 3 (30-60 days): {len(tiers['tier3_archive'])} to archive")
    for expense in tiers['tier3_archive']:
        if archive_placeholder(conn, expense, dry_run):
            stats['tier3_archived_count'] += 1
        else:
            stats['errors'] += 1

    # Tier 4: Delete (>60 days)
    print(f"🗑️  Tier 4 (>60 days): {len(tiers['tier4_delete'])} to delete")
    for expense in tiers['tier4_delete']:
        if delete_placeholder(conn, expense, dry_run):
            stats['tier4_deleted_count'] += 1
        else:
            stats['errors'] += 1

    conn.close()

    # Summary
    print("\n" + "="*70)
    print("CLEANUP SUMMARY")
    print("="*70)
    print(f"Tier 1 (Warning):    {stats['tier1_warning_count']} notifications sent")
    print(f"Tier 2 (Urgent):     {stats['tier2_urgent_count']} notifications sent")
    print(f"Tier 3 (Archived):   {stats['tier3_archived_count']} placeholders archived")
    print(f"Tier 4 (Deleted):    {stats['tier4_deleted_count']} placeholders deleted")
    print(f"Errors:              {stats['errors']}")
    print("="*70)

    logger.info(
        "Cleanup completed",
        extra={
            **stats,
            'dry_run': dry_run
        }
    )

    return stats


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description='Cleanup stale expense placeholders'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    parser.add_argument(
        '--company-id',
        type=str,
        default=None,
        help='Target specific company (default: all companies)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed logging'
    )

    args = parser.parse_args()

    try:
        stats = run_cleanup(
            dry_run=args.dry_run,
            company_id=args.company_id,
            verbose=args.verbose
        )

        # Exit with error code if there were errors
        sys.exit(1 if stats['errors'] > 0 else 0)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
