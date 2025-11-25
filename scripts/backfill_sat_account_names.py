#!/usr/bin/env python3
"""
Backfill script to populate sat_account_name in all invoices.

This script:
1. Finds all invoices with accounting_classification but missing sat_account_name
2. Looks up the official SAT account name from sat_account_embeddings
3. Updates the JSONB field with the official name
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=os.getenv('PG_HOST', '127.0.0.1'),
        port=int(os.getenv('PG_PORT', 5433)),
        database=os.getenv('PG_DB', 'mcp_system'),
        user=os.getenv('PG_USER', 'mcp_user'),
        password=os.getenv('PG_PASSWORD', 'changeme')
    )


def lookup_sat_account_name(cursor, sat_code: str) -> Optional[str]:
    """
    Look up official SAT account name from catalog.

    Args:
        cursor: Database cursor
        sat_code: SAT account code (e.g., "613.01")

    Returns:
        Official account name or None if not found
    """
    cursor.execute("""
        SELECT name
        FROM sat_account_embeddings
        WHERE code = %s
        LIMIT 1
    """, (sat_code,))

    row = cursor.fetchone()
    if row:
        return row['name']

    return None


def backfill_sat_account_names(company_id: Optional[int] = None, limit: int = 1000, dry_run: bool = False):
    """
    Backfill sat_account_name for all invoices.

    Args:
        company_id: Optional company_id to filter by
        limit: Maximum number of invoices to process
        dry_run: If True, only show what would be updated without making changes
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Build query
        where_clauses = [
            "accounting_classification IS NOT NULL",
            "accounting_classification->>'sat_account_code' IS NOT NULL",
            "(accounting_classification->>'sat_account_name' IS NULL OR accounting_classification->>'sat_account_name' = '')"
        ]

        if company_id is not None:
            where_clauses.append(f"company_id = {company_id}")

        where_clause = " AND ".join(where_clauses)

        # Get invoices that need backfill
        query = f"""
            SELECT
                id,
                original_filename,
                accounting_classification->>'sat_account_code' as sat_code,
                accounting_classification->>'sat_account_name' as current_name
            FROM sat_invoices
            WHERE {where_clause}
            LIMIT %s
        """

        cursor.execute(query, (limit,))
        invoices = cursor.fetchall()

        logger.info(f"Found {len(invoices)} invoices to backfill")

        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")

        updated_count = 0
        skipped_count = 0
        error_count = 0

        for invoice in invoices:
            invoice_id = invoice['id']
            sat_code = invoice['sat_code']
            current_name = invoice['current_name']
            filename = invoice['original_filename'] or 'Unknown'

            # Look up official name from catalog
            sat_account_name = lookup_sat_account_name(cursor, sat_code)

            if not sat_account_name:
                logger.warning(
                    f"⚠️  Invoice {invoice_id} ({filename[:40]}): SAT code {sat_code} not found in catalog"
                )
                skipped_count += 1
                continue

            if dry_run:
                logger.info(
                    f"Would update Invoice {invoice_id} ({filename[:40]}): "
                    f"{sat_code} → {sat_account_name}"
                )
                updated_count += 1
                continue

            # Update the JSONB field
            try:
                cursor.execute("""
                    UPDATE sat_invoices
                    SET accounting_classification = jsonb_set(
                        accounting_classification,
                        '{sat_account_name}',
                        %s::jsonb
                    ),
                    updated_at = NOW()
                    WHERE id = %s
                """, (f'"{sat_account_name}"', invoice_id))

                logger.info(
                    f"✅ Updated Invoice {invoice_id} ({filename[:40]}): "
                    f"{sat_code} → {sat_account_name}"
                )
                updated_count += 1

            except Exception as e:
                logger.error(
                    f"❌ Error updating Invoice {invoice_id}: {e}"
                )
                error_count += 1

        if not dry_run:
            conn.commit()
            logger.info("Changes committed to database")

        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("BACKFILL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total invoices processed: {len(invoices)}")
        logger.info(f"✅ Successfully updated: {updated_count}")
        logger.info(f"⚠️  Skipped (not in catalog): {skipped_count}")
        logger.info(f"❌ Errors: {error_count}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Fatal error during backfill: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill sat_account_name for invoices")
    parser.add_argument("--company-id", type=int, help="Filter by company_id")
    parser.add_argument("--limit", type=int, default=1000, help="Max invoices to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")

    args = parser.parse_args()

    backfill_sat_account_names(
        company_id=args.company_id,
        limit=args.limit,
        dry_run=args.dry_run
    )
