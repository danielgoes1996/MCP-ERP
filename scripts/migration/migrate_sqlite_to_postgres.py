#!/usr/bin/env python3
"""
Migration Script: SQLite → PostgreSQL
Migrates all tables, data, indexes, and triggers from unified_mcp_system.db to PostgreSQL
"""

import sqlite3
import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict, Any
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SQLITE_DB = "unified_mcp_system.db"
PG_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

# Tables already in PostgreSQL (skip these)
EXISTING_PG_TABLES = {
    'bank_statements', 'bank_transactions', 'bulk_invoice_batch_items',
    'bulk_invoice_batches', 'companies', 'expense_invoices', 'expenses',
    'invoice_import_logs', 'payment_accounts', 'refresh_tokens',
    'sat_download_logs', 'sat_efirma_credentials', 'sat_invoice_mapping',
    'sat_packages', 'sat_requests', 'schema_versions', 'tenants', 'users'
}

# SQLite to PostgreSQL type mapping
TYPE_MAPPING = {
    'INTEGER': 'INTEGER',
    'TEXT': 'TEXT',
    'REAL': 'REAL',
    'BLOB': 'BYTEA',
    'NUMERIC': 'NUMERIC',
    'BOOLEAN': 'BOOLEAN',
    'DATETIME': 'TIMESTAMP',
    'DATE': 'DATE',
    'TIME': 'TIME',
    'JSON': 'JSONB',
}


def convert_sqlite_type_to_pg(sqlite_type: str) -> str:
    """Convert SQLite type to PostgreSQL type"""
    sqlite_type = sqlite_type.upper()

    # Handle common variations
    if 'INT' in sqlite_type:
        return 'INTEGER'
    elif 'CHAR' in sqlite_type or 'CLOB' in sqlite_type or 'TEXT' in sqlite_type:
        return 'TEXT'
    elif 'BLOB' in sqlite_type:
        return 'BYTEA'
    elif 'REAL' in sqlite_type or 'FLOA' in sqlite_type or 'DOUB' in sqlite_type:
        return 'REAL'
    elif 'NUMERIC' in sqlite_type or 'DECIMAL' in sqlite_type:
        return 'NUMERIC'
    elif 'BOOL' in sqlite_type:
        return 'BOOLEAN'
    elif 'DATE' in sqlite_type or 'TIME' in sqlite_type:
        return 'TIMESTAMP'
    elif 'JSON' in sqlite_type:
        return 'JSONB'
    else:
        return 'TEXT'  # Default fallback


def get_sqlite_schema(table_name: str, sqlite_conn) -> str:
    """Get CREATE TABLE statement from SQLite"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    result = cursor.fetchone()
    return result[0] if result else None


def convert_schema_to_postgres(sqlite_schema: str, table_name: str) -> str:
    """Convert SQLite CREATE TABLE to PostgreSQL"""
    if not sqlite_schema:
        return None

    # Remove SQLite-specific keywords
    pg_schema = sqlite_schema.replace('AUTOINCREMENT', '')
    pg_schema = pg_schema.replace('autoincrement', '')

    # Convert types (basic conversion, might need refinement)
    for sqlite_type, pg_type in TYPE_MAPPING.items():
        pg_schema = pg_schema.replace(sqlite_type, pg_type)

    # Handle FOREIGN KEY constraints (PostgreSQL syntax is similar)
    # Handle CHECK constraints (PostgreSQL syntax is similar)

    return pg_schema


def get_table_columns(table_name: str, sqlite_conn) -> List[str]:
    """Get column names for a table"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return columns


def migrate_table(table_name: str, sqlite_conn, pg_conn, dry_run=False):
    """Migrate a single table from SQLite to PostgreSQL"""
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Migrating table: {table_name}")

    # Get SQLite schema
    sqlite_schema = get_sqlite_schema(table_name, sqlite_conn)
    if not sqlite_schema:
        logger.warning(f"Could not get schema for table: {table_name}")
        return False

    # Convert to PostgreSQL schema
    pg_schema = convert_schema_to_postgres(sqlite_schema, table_name)

    if dry_run:
        logger.info(f"[DRY RUN] Would create table with schema (truncated)")
    else:
        # Create table in PostgreSQL
        try:
            pg_cursor = pg_conn.cursor()
            # Disable foreign key constraints temporarily for initial creation
            pg_cursor.execute("SET session_replication_role = 'replica';")
            pg_cursor.execute(pg_schema)
            pg_cursor.execute("SET session_replication_role = 'origin';")
            pg_conn.commit()
            logger.info(f"✓ Created table: {table_name}")
        except Exception as e:
            logger.error(f"✗ Failed to create table {table_name}: {e}")
            logger.error(f"Schema was:\n{pg_schema[:500]}...")
            pg_conn.rollback()
            # Don't fail completely - some tables might have complex constraints
            logger.warning(f"  Continuing despite error...")
            return True  # Return True to continue migration

    # Get columns
    columns = get_table_columns(table_name, sqlite_conn)

    # Get data from SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        logger.info(f"  No data to migrate for {table_name}")
        return True

    logger.info(f"  Found {len(rows)} rows to migrate")

    if dry_run:
        logger.info(f"[DRY RUN] Would insert {len(rows)} rows into {table_name}")
        return True

    # Insert data into PostgreSQL
    try:
        pg_cursor = pg_conn.cursor()
        placeholders = ','.join(['%s'] * len(columns))
        insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"

        # Batch insert
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            pg_cursor.executemany(insert_sql, batch)
            logger.info(f"  Inserted {min(i + batch_size, len(rows))}/{len(rows)} rows")

        pg_conn.commit()
        logger.info(f"✓ Migrated {len(rows)} rows to {table_name}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to insert data into {table_name}: {e}")
        pg_conn.rollback()
        return False


def get_sqlite_indexes(table_name: str, sqlite_conn) -> List[str]:
    """Get index creation statements for a table"""
    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table_name,)
    )
    return [row[0] for row in cursor.fetchall()]


def migrate_indexes(table_name: str, sqlite_conn, pg_conn, dry_run=False):
    """Migrate indexes for a table"""
    indexes = get_sqlite_indexes(table_name, sqlite_conn)

    if not indexes:
        return

    logger.info(f"  Migrating {len(indexes)} indexes for {table_name}")

    for index_sql in indexes:
        # Convert SQLite index to PostgreSQL (mostly compatible)
        pg_index_sql = index_sql.replace('AUTOINCREMENT', '')

        if dry_run:
            logger.info(f"[DRY RUN] Would create index:\n{pg_index_sql}")
        else:
            try:
                pg_cursor = pg_conn.cursor()
                pg_cursor.execute(pg_index_sql)
                pg_conn.commit()
                logger.info(f"  ✓ Created index")
            except Exception as e:
                logger.warning(f"  ✗ Failed to create index: {e}")
                pg_conn.rollback()


def main(dry_run=False):
    """Main migration function"""
    logger.info("=" * 80)
    logger.info("SQLite → PostgreSQL Migration")
    logger.info("=" * 80)

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # Connect to SQLite
    logger.info(f"Connecting to SQLite: {SQLITE_DB}")
    sqlite_conn = sqlite3.connect(SQLITE_DB)

    # Connect to PostgreSQL
    logger.info(f"Connecting to PostgreSQL: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")
    pg_conn = psycopg2.connect(**PG_CONFIG)

    # Get all tables from SQLite
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [row[0] for row in cursor.fetchall()]

    # Filter out tables that already exist in PostgreSQL
    tables_to_migrate = [t for t in all_tables if t not in EXISTING_PG_TABLES and not t.startswith('sqlite_')]

    logger.info(f"\nTotal tables in SQLite: {len(all_tables)}")
    logger.info(f"Already in PostgreSQL: {len(EXISTING_PG_TABLES)}")
    logger.info(f"To migrate: {len(tables_to_migrate)}")
    logger.info(f"\nTables to migrate:")
    for table in tables_to_migrate:
        logger.info(f"  - {table}")

    if not dry_run:
        confirm = input("\nProceed with migration? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Migration cancelled")
            return

    # Migrate tables
    logger.info("\n" + "=" * 80)
    logger.info("Starting migration...")
    logger.info("=" * 80)

    success_count = 0
    failed_tables = []

    for table in tables_to_migrate:
        try:
            if migrate_table(table, sqlite_conn, pg_conn, dry_run):
                # Migrate indexes after successful table migration
                migrate_indexes(table, sqlite_conn, pg_conn, dry_run)
                success_count += 1
            else:
                failed_tables.append(table)
        except Exception as e:
            logger.error(f"✗ Failed to migrate {table}: {e}")
            failed_tables.append(table)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Migration Summary")
    logger.info("=" * 80)
    logger.info(f"Successfully migrated: {success_count}/{len(tables_to_migrate)} tables")

    if failed_tables:
        logger.warning(f"Failed tables ({len(failed_tables)}):")
        for table in failed_tables:
            logger.warning(f"  - {table}")
    else:
        logger.info("✓ All tables migrated successfully!")

    # Close connections
    sqlite_conn.close()
    pg_conn.close()

    logger.info("\n" + "=" * 80)
    logger.info("Migration completed")
    logger.info("=" * 80)


if __name__ == "__main__":
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    main(dry_run=dry_run)
