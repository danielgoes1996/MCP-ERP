"""
Database Optimization Utilities for MCP Server
Implements critical indexes and performance optimizations
"""

import sqlite3
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Handles database performance optimizations"""

    @staticmethod
    def apply_sqlite_optimizations(connection: sqlite3.Connection) -> None:
        """Apply SQLite performance optimizations"""
        try:
            # Enable WAL mode for better concurrent access
            connection.execute("PRAGMA journal_mode = WAL")

            # Set synchronous to NORMAL for better performance
            connection.execute("PRAGMA synchronous = NORMAL")

            # Increase cache size (10MB)
            connection.execute("PRAGMA cache_size = 10000")

            # Enable memory-mapped I/O
            connection.execute("PRAGMA mmap_size = 268435456")  # 256MB

            # Optimize temporary storage
            connection.execute("PRAGMA temp_store = MEMORY")

            logger.info("✅ SQLite performance optimizations applied")

        except Exception as e:
            logger.error(f"❌ Failed to apply SQLite optimizations: {e}")

    @staticmethod
    def create_critical_indexes(connection: sqlite3.Connection) -> None:
        """Create critical database indexes for performance"""

        indexes = [
            # Expense records compound index for common queries
            (
                "idx_expense_records_compound",
                "expense_records",
                ["tenant_id", "status", "date"],
                "Expense filtering by tenant, status, and date"
            ),

            # Expense invoices foreign key index
            (
                "idx_expense_invoices_expense_id",
                "expense_invoices",
                ["expense_id"],
                "Expense-invoice relationship lookups"
            ),

            # Tickets processing status index
            (
                "idx_tickets_processing",
                "tickets",
                ["status", "tenant_id", "created_at"],
                "Ticket processing queries"
            ),

            # Bank movements reconciliation index
            (
                "idx_bank_movements_reconciliation",
                "bank_movements",
                ["tenant_id", "date", "amount"],
                "Bank reconciliation queries"
            ),

            # User accounts lookup index - Skip if table doesn't exist
            (
                "idx_user_accounts_identifier",
                "user_accounts",
                ["identifier", "identifier_type"],
                "User account lookups"
            ),

            # Expense records date range queries
            (
                "idx_expense_records_date_range",
                "expense_records",
                ["date", "tenant_id"],
                "Date range expense queries"
            ),

            # Provider lookups
            (
                "idx_expense_records_provider",
                "expense_records",
                ["rfc_proveedor", "merchant_name"],
                "Provider-based queries"
            )
        ]

        created_count = 0
        for index_name, table_name, columns, description in indexes:
            try:
                cursor = connection.cursor()

                # First check if table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )

                if not cursor.fetchone():
                    logger.debug(f"Table {table_name} does not exist, skipping index {index_name}")
                    continue

                # Check if all columns exist in the table
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = [row[1] for row in cursor.fetchall()]

                missing_columns = [col for col in columns if col not in existing_columns]
                if missing_columns:
                    logger.debug(f"Columns {missing_columns} don't exist in {table_name}, skipping index {index_name}")
                    continue

                # Check if index already exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,)
                )

                if cursor.fetchone():
                    logger.debug(f"Index {index_name} already exists, skipping")
                    continue

                # Create the index
                columns_str = ", ".join(columns)
                sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
                connection.execute(sql)

                logger.info(f"✅ Created index: {index_name} - {description}")
                created_count += 1

            except Exception as e:
                logger.debug(f"Could not create index {index_name}: {e}")

        if created_count > 0:
            connection.commit()
            logger.info(f"✅ Created {created_count} new database indexes")
        else:
            logger.info("✅ All indexes already exist")

    @staticmethod
    def analyze_table_statistics(connection: sqlite3.Connection) -> None:
        """Update SQLite table statistics for better query planning"""
        try:
            connection.execute("ANALYZE")
            logger.info("✅ Updated table statistics for query optimizer")
        except Exception as e:
            logger.error(f"❌ Failed to analyze table statistics: {e}")

    @staticmethod
    def optimize_database(connection: sqlite3.Connection) -> None:
        """Run complete database optimization"""
        logger.info("🔧 Starting database optimization...")

        # Apply SQLite optimizations
        DatabaseOptimizer.apply_sqlite_optimizations(connection)

        # Create critical indexes
        DatabaseOptimizer.create_critical_indexes(connection)

        # Update table statistics
        DatabaseOptimizer.analyze_table_statistics(connection)

        logger.info("✅ Database optimization completed")

    @staticmethod
    def get_database_info(connection: sqlite3.Connection) -> dict:
        """Get database performance information"""
        try:
            cursor = connection.cursor()

            # Get table sizes
            cursor.execute("""
                SELECT name,
                       (SELECT COUNT(*) FROM sqlite_master sm2 WHERE sm2.tbl_name = sm.name AND sm2.type = 'table') as table_count
                FROM sqlite_master sm
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = cursor.fetchall()

            # Get index information
            cursor.execute("""
                SELECT name, tbl_name
                FROM sqlite_master
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
                ORDER BY tbl_name, name
            """)
            indexes = cursor.fetchall()

            # Get pragma information
            pragma_info = {}
            pragmas = ['journal_mode', 'synchronous', 'cache_size', 'mmap_size', 'temp_store']
            for pragma in pragmas:
                cursor.execute(f"PRAGMA {pragma}")
                result = cursor.fetchone()
                pragma_info[pragma] = result[0] if result else None

            return {
                'tables': tables,
                'indexes': indexes,
                'pragma_settings': pragma_info,
                'total_indexes': len(indexes)
            }

        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {}


def optimize_database_connection(connection: sqlite3.Connection) -> None:
    """Convenient function to optimize a database connection"""
    DatabaseOptimizer.optimize_database(connection)


if __name__ == "__main__":
    # Test the optimizer
    import tempfile
    import os

    # Create a test database
    test_db = tempfile.mktemp(suffix='.db')
    try:
        conn = sqlite3.connect(test_db)

        # Create a sample table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expense_records (
                id INTEGER PRIMARY KEY,
                company_id TEXT,
                invoice_status TEXT,
                expense_date TEXT
            )
        """)

        # Test optimization
        DatabaseOptimizer.optimize_database(conn)

        # Show results
        info = DatabaseOptimizer.get_database_info(conn)
        print(f"✅ Test completed. Created {info['total_indexes']} indexes")

        conn.close()

    finally:
        if os.path.exists(test_db):
            os.unlink(test_db)