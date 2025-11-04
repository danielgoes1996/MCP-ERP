#!/usr/bin/env python3
"""
Apply migration 009 - Automation Engine v2
Safe migration application with validation and rollback capability.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def apply_migration_009(db_path: str = "data/mcp_internal.db"):
    """Apply migration 009 with safety checks."""

    print("🚀 Applying Migration 009 - Automation Engine v2")
    print("=" * 55)

    db_path = Path(db_path)
    migration_file = Path("migrations/009_automation_engine_20240921.sql")

    if not db_path.exists():
        print("❌ Database not found")
        return False

    if not migration_file.exists():
        print("❌ Migration file not found")
        return False

    try:
        # Read migration SQL
        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        # Check if migration already applied
        existing = conn.execute("""
            SELECT name FROM schema_versions
            WHERE name = '009_automation_engine'
        """).fetchone()

        if existing:
            print("⚠️ Migration 009 already applied")
            conn.close()
            return True

        print("📋 Starting migration application...")

        # Begin transaction
        conn.execute("BEGIN TRANSACTION")

        try:
            # Split SQL into individual statements
            statements = [
                stmt.strip()
                for stmt in migration_sql.split(';')
                if stmt.strip() and not stmt.strip().startswith('--')
            ]

            executed_statements = 0

            for i, statement in enumerate(statements):
                if not statement:
                    continue

                try:
                    # Skip comments and empty lines
                    if statement.startswith('--') or not statement.strip():
                        continue

                    print(f"   🔧 Executing statement {i+1}/{len(statements)}")
                    conn.execute(statement)
                    executed_statements += 1

                except sqlite3.OperationalError as e:
                    # Handle specific errors that might be acceptable
                    error_msg = str(e).lower()

                    if "table automation_config already exists" in error_msg:
                        print(f"   ⚠️ Table already exists, skipping: {e}")
                        continue
                    elif "duplicate column name" in error_msg:
                        print(f"   ⚠️ Column already exists, skipping: {e}")
                        continue
                    elif "index automation_" in error_msg and "already exists" in error_msg:
                        print(f"   ⚠️ Index already exists, skipping: {e}")
                        continue
                    else:
                        # This is a real error
                        print(f"   ❌ SQL Error: {e}")
                        raise

            print(f"   ✅ Executed {executed_statements} statements successfully")

            # Validate migration
            print("🔍 Validating migration...")

            # Check that automation tables exist
            automation_tables = [
                'automation_jobs',
                'automation_logs',
                'automation_screenshots',
                'automation_config'
            ]

            for table in automation_tables:
                result = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name=?
                """, (table,)).fetchone()

                if not result:
                    raise Exception(f"Validation failed: table {table} not created")

            print("   ✅ All automation tables created successfully")

            # Check seed data
            config_count = conn.execute("""
                SELECT COUNT(*) FROM automation_config
                WHERE updated_by = 'migration_009'
            """).fetchone()[0]

            if config_count < 5:
                raise Exception(f"Validation failed: expected 5+ config entries, got {config_count}")

            print(f"   ✅ Seed configuration inserted: {config_count} entries")

            # Check indexes
            index_count = conn.execute("""
                SELECT COUNT(*) FROM sqlite_master
                WHERE type='index' AND name LIKE 'idx_automation_%'
            """).fetchone()[0]

            print(f"   ✅ Indexes created: {index_count} automation indexes")

            # Commit transaction
            conn.commit()
            print("💾 Migration committed successfully")

            # Final validation
            final_check = conn.execute("""
                SELECT name, applied_at FROM schema_versions
                WHERE name = '009_automation_engine'
            """).fetchone()

            if final_check:
                print(f"✅ Migration 009 applied successfully at {final_check[1]}")
            else:
                raise Exception("Migration record not found after commit")

        except Exception as e:
            # Rollback on any error
            conn.rollback()
            print(f"❌ Migration failed, rolled back: {e}")
            conn.close()
            return False

        conn.close()

        # Post-migration validation
        print("\n🔍 Post-migration validation...")
        validate_automation_schema(db_path)

        return True

    except Exception as e:
        print(f"❌ Migration application failed: {e}")
        return False

def validate_automation_schema(db_path: Path):
    """Validate the automation schema after migration."""

    try:
        conn = sqlite3.connect(db_path)

        # Test basic functionality
        test_session_id = f"test_{int(datetime.now().timestamp())}"

        # Test config table
        conn.execute("""
            INSERT INTO automation_config (
                key, value, value_type, scope, updated_at, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ('test_key', 'test_value', 'string', 'global', datetime.now().isoformat(), 'validation'))

        config_id = conn.lastrowid

        # Clean up test data
        conn.execute("DELETE FROM automation_config WHERE id = ?", (config_id,))
        conn.commit()

        print("   ✅ Schema validation passed")

        # Get table statistics
        stats = {}
        for table in ['automation_jobs', 'automation_logs', 'automation_screenshots', 'automation_config']:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count

        print("   📊 Table statistics:")
        for table, count in stats.items():
            print(f"      • {table}: {count} records")

        conn.close()

    except Exception as e:
        print(f"   ⚠️ Schema validation warning: {e}")

def main():
    """Main function."""

    # Verify we're in the right location
    if not Path("core/internal_db.py").exists():
        print("❌ Error: Run from mcp-server root directory")
        return 1

    # Apply migration
    success = apply_migration_009()

    if success:
        print("\n🎉 Migration 009 completed successfully!")
        print("📋 Next steps:")
        print("   1. Test read-only API endpoints")
        print("   2. Validate feature flags system")
        print("   3. Deploy to staging environment")
        return 0
    else:
        print("\n💥 Migration 009 failed!")
        print("📋 Recovery steps:")
        print("   1. Check error messages above")
        print("   2. Restore from backup if needed")
        print("   3. Fix issues and retry")
        return 1

if __name__ == "__main__":
    exit(main())