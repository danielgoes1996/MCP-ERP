#!/usr/bin/env python3
"""
Validate SQLite to PostgreSQL migration
"""
import sqlite3
import psycopg2
import os
import sys

class MigrationValidator:
    """Validate data migration between SQLite and PostgreSQL"""

    def __init__(self, sqlite_db: str, postgres_dsn: str):
        self.sqlite_db = sqlite_db
        self.postgres_dsn = postgres_dsn
        self.errors = []
        self.warnings = []

    def validate(self):
        """Run all validation checks"""

        print("🔍 Validating migration...\n")

        sqlite_conn = sqlite3.connect(self.sqlite_db)
        pg_conn = psycopg2.connect(self.postgres_dsn)

        try:
            # Get list of tables
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in sqlite_cursor.fetchall()]

            print(f"📋 Validating {len(tables)} tables...\n")

            for table in tables:
                self.validate_table(table, sqlite_conn, pg_conn)

            # Print summary
            print("\n" + "="*50)
            if self.errors:
                print(f"❌ Validation FAILED with {len(self.errors)} errors")
                print("="*50)
                for error in self.errors:
                    print(f"  ❌ {error}")
                return False
            elif self.warnings:
                print(f"⚠️  Validation completed with {len(self.warnings)} warnings")
                print("="*50)
                for warning in self.warnings:
                    print(f"  ⚠️  {warning}")
                return True
            else:
                print("✅ Validation PASSED - All checks successful!")
                print("="*50)
                return True

        finally:
            sqlite_conn.close()
            pg_conn.close()

    def validate_table(self, table: str, sqlite_conn, pg_conn):
        """Validate a single table"""

        # Get row counts
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()

        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        sqlite_count = sqlite_cursor.fetchone()[0]

        pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        pg_count = pg_cursor.fetchone()[0]

        # Compare counts
        if sqlite_count == 0 and pg_count == 0:
            print(f"⏭️  {table:30s} - Empty table (skipped)")
            return

        if sqlite_count != pg_count:
            error = f"{table}: Row count mismatch (SQLite: {sqlite_count}, PostgreSQL: {pg_count})"
            print(f"❌ {error}")
            self.errors.append(error)
        else:
            print(f"✅ {table:30s} - {sqlite_count:6,} rows migrated")

def main():
    # Get database connections from environment
    sqlite_db = os.getenv('SQLITE_DB', 'unified_mcp_system.db')

    pg_host = os.getenv('POSTGRES_HOST', 'localhost')
    pg_port = os.getenv('POSTGRES_PORT', '5432')
    pg_db = os.getenv('POSTGRES_DB', 'mcp_system')
    pg_user = os.getenv('POSTGRES_USER', 'mcp_user')
    pg_password = os.getenv('POSTGRES_PASSWORD', 'changeme')

    postgres_dsn = f"host={pg_host} port={pg_port} dbname={pg_db} user={pg_user} password={pg_password}"

    # Run validation
    validator = MigrationValidator(sqlite_db, postgres_dsn)
    success = validator.validate()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
