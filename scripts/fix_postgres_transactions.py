#!/usr/bin/env python3
"""
Fix aborted PostgreSQL transactions by terminating all idle connections
and rolling back any aborted transactions.
"""

import psycopg2
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_transactions():
    """Terminate idle connections and aborted transactions."""

    try:
        # Connect as admin to terminate other connections
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
            port=int(os.getenv('POSTGRES_PORT', '5433')),
            database=os.getenv('POSTGRES_DB', 'mcp_system'),
            user=os.getenv('POSTGRES_USER', 'mcp_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'changeme')
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # 1. Find and terminate idle/aborted transactions
        logger.info("Finding idle and aborted transactions...")
        cursor.execute("""
            SELECT pid, state, query_start, state_change
            FROM pg_stat_activity
            WHERE datname = 'mcp_system'
              AND pid != pg_backend_pid()
              AND (state LIKE '%aborted%'
                   OR (state = 'idle in transaction' AND state_change < NOW() - INTERVAL '5 minutes'))
        """)

        aborted = cursor.fetchall()
        logger.info(f"Found {len(aborted)} aborted/idle transactions")

        for pid, state, query_start, state_change in aborted:
            logger.info(f"Terminating PID {pid} (state: {state})")
            try:
                cursor.execute("SELECT pg_terminate_backend(%s)", (pid,))
                logger.info(f"  ✓ Terminated PID {pid}")
            except Exception as e:
                logger.warning(f"  ✗ Could not terminate PID {pid}: {e}")

        # 2. Check for any remaining aborted transactions
        cursor.execute("""
            SELECT COUNT(*)
            FROM pg_stat_activity
            WHERE datname = 'mcp_system'
              AND state LIKE '%aborted%'
        """)
        remaining = cursor.fetchone()[0]

        if remaining > 0:
            logger.warning(f"Still have {remaining} aborted transactions")
        else:
            logger.info("✓ All aborted transactions cleared")

        cursor.close()
        conn.close()

        logger.info("✓ Transaction cleanup complete")
        return True

    except Exception as e:
        logger.error(f"Error fixing transactions: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = fix_transactions()
    exit(0 if success else 1)
