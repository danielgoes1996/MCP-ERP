#!/usr/bin/env python3
"""
Apply Migration 035: Enhance expense_invoices with Fiscal Fields

Usage:
    python migrations/apply_035_migration.py

Requirements:
    - SQLite database at: unified_mcp_system.db
    - Backup will be created automatically
"""

import sqlite3
import os
import sys
from datetime import datetime
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = "unified_mcp_system.db"
MIGRATION_FILE = "migrations/035_enhance_expense_invoices_fiscal_fields.sql"
BACKUP_DIR = "backups"


def create_backup():
    """Create a backup of the database before migration"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        sys.exit(1)

    # Create backups directory
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/unified_mcp_system_before_035_{timestamp}.db"

    print(f"📦 Creating backup at: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup created successfully")

    return backup_path


def check_prerequisites(conn):
    """Check if prerequisites are met before running migration"""
    cursor = conn.cursor()

    # Check if migration already applied
    cursor.execute("""
        SELECT COUNT(*) FROM schema_migrations
        WHERE version = '035'
    """)
    if cursor.fetchone()[0] > 0:
        print("⚠️  Migration 035 already applied!")
        response = input("Do you want to re-apply it? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Migration cancelled")
            sys.exit(0)

    # Check table exists
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='table' AND name='expense_invoices'
    """)
    if cursor.fetchone()[0] == 0:
        print("❌ Table expense_invoices does not exist!")
        sys.exit(1)

    # Count existing records
    cursor.execute("SELECT COUNT(*) FROM expense_invoices")
    count = cursor.fetchone()[0]
    print(f"ℹ️  Found {count} existing invoice records")

    # Check for NULL values in columns that will become NOT NULL
    cursor.execute("""
        SELECT
            SUM(CASE WHEN expense_id IS NULL THEN 1 ELSE 0 END) as null_expense_id,
            SUM(CASE WHEN tenant_id IS NULL THEN 1 ELSE 0 END) as null_tenant_id,
            SUM(CASE WHEN filename IS NULL THEN 1 ELSE 0 END) as null_filename,
            SUM(CASE WHEN content_type IS NULL THEN 1 ELSE 0 END) as null_content_type
        FROM expense_invoices
    """)
    null_counts = cursor.fetchone()

    if any(null_counts):
        print(f"⚠️  Found NULL values that need to be fixed:")
        print(f"   - expense_id: {null_counts[0]}")
        print(f"   - tenant_id: {null_counts[1]}")
        print(f"   - filename: {null_counts[2]}")
        print(f"   - content_type: {null_counts[3]}")
        print(f"\nThe migration will handle these automatically.")

    return True


def apply_migration(conn):
    """Apply the migration SQL"""
    print("\n🚀 Applying migration 035...")

    # Read migration file
    if not os.path.exists(MIGRATION_FILE):
        print(f"❌ Migration file not found: {MIGRATION_FILE}")
        sys.exit(1)

    with open(MIGRATION_FILE, 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    # Execute migration
    cursor = conn.cursor()

    try:
        # SQLite doesn't support multiple statements in executescript well with transactions
        # So we'll execute it and commit
        cursor.executescript(migration_sql)
        print("✅ Migration SQL executed successfully")

    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise


def verify_migration(conn):
    """Verify the migration was successful"""
    print("\n🔍 Verifying migration...")

    cursor = conn.cursor()

    # Check new columns exist
    cursor.execute("PRAGMA table_info(expense_invoices)")
    columns = [row[1] for row in cursor.fetchall()]

    required_columns = [
        'uuid', 'rfc_emisor', 'nombre_emisor', 'rfc_receptor',
        'fecha_emision', 'fecha_timbrado', 'cfdi_status', 'version_cfdi',
        'tasa', 'tipo_impuesto', 'tipo_factor',
        'isr_retenido', 'iva_retenido', 'ieps', 'otros_impuestos',
        'mes_fiscal', 'xml_path', 'origen_importacion', 'total'
    ]

    missing_columns = [col for col in required_columns if col not in columns]
    if missing_columns:
        print(f"❌ Missing columns: {missing_columns}")
        return False

    print(f"✅ All {len(required_columns)} new columns created")

    # Check indexes
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='expense_invoices'
        ORDER BY name
    """)
    indexes = [row[0] for row in cursor.fetchall()]
    print(f"✅ Created {len(indexes)} indexes on expense_invoices")

    # Check invoice_import_logs table
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='table' AND name='invoice_import_logs'
    """)
    if cursor.fetchone()[0] == 0:
        print("❌ Table invoice_import_logs not created!")
        return False

    print("✅ Table invoice_import_logs created")

    # Check triggers
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='trigger' AND tbl_name='expense_invoices'
    """)
    triggers = [row[0] for row in cursor.fetchall()]
    if len(triggers) < 2:
        print(f"⚠️  Expected 2 triggers, found {len(triggers)}")
    else:
        print(f"✅ Created {len(triggers)} triggers for auto-calculating total")

    # Check schema_migrations
    cursor.execute("""
        SELECT COUNT(*) FROM schema_migrations
        WHERE version = '035'
    """)
    if cursor.fetchone()[0] == 0:
        print("⚠️  Migration not recorded in schema_migrations")
        return False

    print("✅ Migration recorded in schema_migrations")

    return True


def show_summary(conn):
    """Show summary of changes"""
    print("\n📊 Migration Summary:")
    print("=" * 60)

    cursor = conn.cursor()

    # Column count
    cursor.execute("PRAGMA table_info(expense_invoices)")
    column_count = len(cursor.fetchall())
    print(f"expense_invoices columns: {column_count}")

    # Index count
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='index' AND tbl_name='expense_invoices'
    """)
    index_count = cursor.fetchone()[0]
    print(f"expense_invoices indexes: {index_count}")

    # Trigger count
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='trigger' AND tbl_name='expense_invoices'
    """)
    trigger_count = cursor.fetchone()[0]
    print(f"expense_invoices triggers: {trigger_count}")

    # invoice_import_logs
    cursor.execute("PRAGMA table_info(invoice_import_logs)")
    import_log_columns = len(cursor.fetchall())
    print(f"invoice_import_logs columns: {import_log_columns}")

    print("=" * 60)


def main():
    """Main migration execution"""
    print("=" * 60)
    print("🔧 Migration 035: Enhance expense_invoices")
    print("=" * 60)

    # Create backup
    backup_path = create_backup()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Check prerequisites
        check_prerequisites(conn)

        # Apply migration
        apply_migration(conn)

        # Verify migration
        if not verify_migration(conn):
            print("\n❌ Migration verification failed!")
            print(f"💾 Restore from backup: {backup_path}")
            sys.exit(1)

        # Commit changes
        conn.commit()

        # Show summary
        show_summary(conn)

        print("\n✅ Migration 035 completed successfully!")
        print(f"💾 Backup saved at: {backup_path}")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("Rolling back changes...")
        conn.rollback()
        print(f"💾 Restore from backup: {backup_path}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
