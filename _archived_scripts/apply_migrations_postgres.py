#!/usr/bin/env python3
"""
Apply all SQLite migrations to PostgreSQL
Converts SQLite syntax to PostgreSQL on the fly
"""

import psycopg2
import os
import re
from pathlib import Path

# PostgreSQL connection
POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

def convert_sqlite_to_postgres(sql):
    """Convert SQLite syntax to PostgreSQL"""

    # Replace AUTOINCREMENT with SERIAL
    sql = re.sub(r'\bINTEGER PRIMARY KEY AUTOINCREMENT\b', 'SERIAL PRIMARY KEY', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bINTEGER AUTOINCREMENT\b', 'SERIAL', sql, flags=re.IGNORECASE)

    # Replace INTEGER with INT
    sql = re.sub(r'\bINTEGER\b', 'INT', sql)

    # Replace REAL with DOUBLE PRECISION
    sql = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', sql)

    # Replace TEXT with VARCHAR or TEXT (keep TEXT)
    # No change needed - PostgreSQL supports TEXT

    # Replace DATETIME with TIMESTAMP
    sql = re.sub(r'\bDATETIME\b', 'TIMESTAMP', sql, flags=re.IGNORECASE)

    # Remove IF NOT EXISTS from indexes (not supported in old PostgreSQL)
    # Actually, modern PostgreSQL supports it, so keep it

    # Replace last_insert_rowid() with RETURNING id
    sql = re.sub(r'SELECT last_insert_rowid\(\)', 'RETURNING id', sql, flags=re.IGNORECASE)

    # Replace BLOB with BYTEA
    sql = re.sub(r'\bBLOB\b', 'BYTEA', sql, flags=re.IGNORECASE)

    # Fix boolean defaults
    sql = re.sub(r"DEFAULT '0'", 'DEFAULT FALSE', sql)
    sql = re.sub(r"DEFAULT '1'", 'DEFAULT TRUE', sql)
    sql = re.sub(r'DEFAULT 0([^\.0-9])', r'DEFAULT FALSE\1', sql)
    sql = re.sub(r'DEFAULT 1([^\.0-9])', r'DEFAULT TRUE\1', sql)

    return sql

def apply_migration(conn, migration_file):
    """Apply a single migration file"""
    print(f"\n📄 Applying: {migration_file.name}")

    # Read migration SQL
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Convert to PostgreSQL syntax
    sql = convert_sqlite_to_postgres(sql)

    # Split by semicolon and execute each statement
    statements = [s.strip() for s in sql.split(';') if s.strip()]

    cursor = conn.cursor()

    for i, statement in enumerate(statements, 1):
        try:
            cursor.execute(statement)
            print(f"   ✅ Statement {i}/{len(statements)}")
        except psycopg2.Error as e:
            # Check if error is "already exists" - in that case, continue
            if "already exists" in str(e).lower():
                print(f"   ⚠️  Statement {i}/{len(statements)} - Already exists, skipping")
                conn.rollback()
            else:
                print(f"   ❌ Error in statement {i}: {e}")
                print(f"   Statement: {statement[:200]}...")
                conn.rollback()
                raise

    conn.commit()
    cursor.close()
    print(f"✅ {migration_file.name} applied successfully")

def main():
    print("=" * 70)
    print("  🚀 APPLYING MIGRATIONS TO POSTGRESQL")
    print("=" * 70)

    # Connect to PostgreSQL
    print("\n🔌 Connecting to PostgreSQL...")
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    print("✅ Connected!")

    # Get all migration files in order
    migrations_dir = Path("migrations")
    migration_files = sorted(migrations_dir.glob("*.sql"))

    # Filter out duplicate numbered migrations (keep the longer filename)
    seen_numbers = {}
    for mf in migration_files:
        match = re.match(r'(\d+)', mf.name)
        if match:
            num = match.group(1)
            if num not in seen_numbers or len(mf.name) > len(seen_numbers[num].name):
                seen_numbers[num] = mf

    migration_files = sorted(seen_numbers.values(), key=lambda x: x.name)

    print(f"\n📊 Found {len(migration_files)} migration files")

    # Apply each migration
    for migration_file in migration_files:
        try:
            apply_migration(conn, migration_file)
        except Exception as e:
            print(f"\n❌ Failed to apply {migration_file.name}: {e}")
            print("Continuing with next migration...")
            continue

    # Close connection
    conn.close()

    print("\n" + "=" * 70)
    print("  ✅ MIGRATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
