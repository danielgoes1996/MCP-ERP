#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL
"""
import sqlite3
import psycopg2
import psycopg2.extras
import json
import sys
import os
from datetime import datetime
from typing import List, Tuple, Dict

class DataMigrator:
    """Migrate data from SQLite to PostgreSQL"""

    def __init__(self, sqlite_db: str, postgres_dsn: str):
        self.sqlite_db = sqlite_db
        self.postgres_dsn = postgres_dsn
        self.stats = {
            'tables_migrated': 0,
            'rows_migrated': 0,
            'errors': [],
            'skipped_tables': []
        }

    def connect_sqlite(self) -> sqlite3.Connection:
        """Connect to SQLite database"""
        conn = sqlite3.connect(self.sqlite_db)
        conn.row_factory = sqlite3.Row
        return conn

    def connect_postgres(self) -> psycopg2.extensions.connection:
        """Connect to PostgreSQL database"""
        return psycopg2.connect(self.postgres_dsn)

    def get_table_columns(self, sqlite_conn: sqlite3.Connection, table_name: str) -> List[str]:
        """Get column names for a table"""
        cursor = sqlite_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return columns

    def migrate_table(self, table_name: str, sqlite_conn: sqlite3.Connection,
                     pg_conn: psycopg2.extensions.connection) -> int:
        """Migrate a single table"""

        print(f"\n📦 Migrating table: {table_name}")

        # Get columns
        columns = self.get_table_columns(sqlite_conn, table_name)
        print(f"   Columns: {len(columns)}")

        # Get row count
        cursor = sqlite_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_rows = cursor.fetchone()[0]

        if total_rows == 0:
            print(f"   ⏭️  Skipping (empty table)")
            self.stats['skipped_tables'].append(table_name)
            return 0

        print(f"   Rows: {total_rows}")

        # Fetch all data from SQLite
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        # Prepare PostgreSQL insert
        pg_cursor = pg_conn.cursor()

        # Build INSERT statement
        columns_str = ', '.join(f'"{col}"' for col in columns)
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})'

        # Disable triggers temporarily for faster insert
        pg_cursor.execute(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL")

        # Insert data in batches
        batch_size = 100
        migrated = 0

        try:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]

                # Convert rows to tuples
                batch_data = [tuple(row) for row in batch]

                # Execute batch insert
                psycopg2.extras.execute_batch(pg_cursor, insert_sql, batch_data)

                migrated += len(batch)

                if migrated % 100 == 0:
                    print(f"   ⏳ Progress: {migrated}/{total_rows} rows")

            # Re-enable triggers
            pg_cursor.execute(f"ALTER TABLE {table_name} ENABLE TRIGGER ALL")

            # Update sequences for SERIAL columns
            for col in columns:
                if col.lower() in ['id']:  # Common auto-increment column
                    try:
                        pg_cursor.execute(f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table_name}', '{col}'),
                                COALESCE((SELECT MAX({col}) FROM {table_name}), 1),
                                true
                            )
                        """)
                    except Exception as e:
                        # Not all tables have sequences
                        pass

            pg_conn.commit()
            print(f"   ✅ Migrated: {migrated} rows")
            return migrated

        except Exception as e:
            pg_conn.rollback()
            error_msg = f"Error migrating {table_name}: {str(e)}"
            print(f"   ❌ {error_msg}")
            self.stats['errors'].append(error_msg)
            return 0

    def migrate_all(self, table_order: List[str] = None):
        """Migrate all tables"""

        print("🚀 Starting data migration from SQLite to PostgreSQL\n")
        print(f"📖 SQLite DB: {self.sqlite_db}")
        print(f"🐘 PostgreSQL: {self.postgres_dsn.split('@')[1] if '@' in self.postgres_dsn else 'localhost'}")

        sqlite_conn = self.connect_sqlite()
        pg_conn = self.connect_postgres()

        try:
            # Get list of tables
            if not table_order:
                cursor = sqlite_conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """)
                table_order = [row[0] for row in cursor.fetchall()]

            print(f"\n📊 Found {len(table_order)} tables to migrate")

            # Disable foreign key checks temporarily
            pg_cursor = pg_conn.cursor()
            pg_cursor.execute("SET session_replication_role = 'replica'")
            pg_conn.commit()

            # Migrate each table
            for table_name in table_order:
                try:
                    rows_migrated = self.migrate_table(table_name, sqlite_conn, pg_conn)
                    if rows_migrated > 0:
                        self.stats['tables_migrated'] += 1
                        self.stats['rows_migrated'] += rows_migrated
                except Exception as e:
                    print(f"   ❌ Failed: {str(e)}")
                    self.stats['errors'].append(f"{table_name}: {str(e)}")

            # Re-enable foreign key checks
            pg_cursor.execute("SET session_replication_role = 'origin'")
            pg_conn.commit()

            print("\n" + "="*50)
            print("✅ Migration Complete!")
            print("="*50)
            print(f"📊 Statistics:")
            print(f"   Tables migrated: {self.stats['tables_migrated']}")
            print(f"   Rows migrated: {self.stats['rows_migrated']:,}")
            print(f"   Skipped (empty): {len(self.stats['skipped_tables'])}")
            print(f"   Errors: {len(self.stats['errors'])}")

            if self.stats['errors']:
                print(f"\n⚠️  Errors encountered:")
                for error in self.stats['errors']:
                    print(f"   - {error}")

        finally:
            sqlite_conn.close()
            pg_conn.close()

        return self.stats

def main():
    # Get database connections from environment or arguments
    sqlite_db = os.getenv('SQLITE_DB', 'unified_mcp_system.db')

    # PostgreSQL connection
    pg_host = os.getenv('POSTGRES_HOST', 'localhost')
    pg_port = os.getenv('POSTGRES_PORT', '5432')
    pg_db = os.getenv('POSTGRES_DB', 'mcp_system')
    pg_user = os.getenv('POSTGRES_USER', 'mcp_user')
    pg_password = os.getenv('POSTGRES_PASSWORD', 'changeme')

    postgres_dsn = f"host={pg_host} port={pg_port} dbname={pg_db} user={pg_user} password={pg_password}"

    # Allow overriding from command line
    if len(sys.argv) > 1:
        sqlite_db = sys.argv[1]
    if len(sys.argv) > 2:
        postgres_dsn = sys.argv[2]

    # Run migration
    migrator = DataMigrator(sqlite_db, postgres_dsn)
    stats = migrator.migrate_all()

    # Exit with error if there were errors
    if stats['errors']:
        sys.exit(1)

if __name__ == "__main__":
    main()
