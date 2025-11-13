#!/usr/bin/env python3
"""
PostgreSQL Migration Script
Applies schema migrations from migrations/ directory to PostgreSQL
"""

import psycopg2
import psycopg2.extras
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# PostgreSQL configuration
PG_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}


def get_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(**PG_CONFIG)


def check_schema_versions_table(conn):
    """Check if schema_versions table exists"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'schema_versions'
        );
    """)
    return cursor.fetchone()[0]


def get_applied_migrations(conn):
    """Get list of already applied migrations"""
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_versions ORDER BY version")
    return [row[0] for row in cursor.fetchall()]


def apply_migration_file(filepath: Path, conn):
    """Apply a single migration file"""
    logger.info(f"Applying migration: {filepath.name}")

    with open(filepath, 'r') as f:
        sql = f.read()

    try:
        cursor = conn.cursor()
        # Execute SQL (might contain multiple statements)
        cursor.execute(sql)

        # Record migration
        version = filepath.stem.split('_')[0]  # e.g., "001" from "001_create_tables.sql"
        cursor.execute(
            "INSERT INTO schema_versions (version, applied_at) VALUES (%s, CURRENT_TIMESTAMP)",
            (version,)
        )

        conn.commit()
        logger.info(f"✓ Applied migration: {filepath.name}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to apply migration {filepath.name}: {e}")
        conn.rollback()
        return False


def main():
    """Main migration function"""
    logger.info("=" * 80)
    logger.info("PostgreSQL Schema Migration")
    logger.info("=" * 80)

    # Connect to PostgreSQL
    logger.info(f"Connecting to PostgreSQL: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")
    conn = get_connection()

    # Check if schema_versions table exists
    if not check_schema_versions_table(conn):
        logger.warning("schema_versions table exists - skipping migration")
        logger.info("PostgreSQL is already initialized")
        return

    # Get applied migrations
    applied = get_applied_migrations(conn)
    logger.info(f"Already applied migrations: {len(applied)}")

    # Get migration files
    migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))
    logger.info(f"Found {len(migration_files)} migration files")

    # Apply pending migrations
    pending = [f for f in migration_files if f.stem.split('_')[0] not in applied]

    if not pending:
        logger.info("✓ No pending migrations")
        return

    logger.info(f"Pending migrations: {len(pending)}")
    for f in pending:
        logger.info(f"  - {f.name}")

    # Apply migrations
    logger.info("\n" + "=" * 80)
    logger.info("Applying pending migrations...")
    logger.info("=" * 80)

    success_count = 0
    for migration_file in pending:
        if apply_migration_file(migration_file, conn):
            success_count += 1
        else:
            logger.error("Migration failed - stopping")
            break

    logger.info("\n" + "=" * 80)
    logger.info(f"Applied {success_count}/{len(pending)} migrations")
    logger.info("=" * 80)

    conn.close()


if __name__ == "__main__":
    main()
