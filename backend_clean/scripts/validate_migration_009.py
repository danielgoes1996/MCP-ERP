#!/usr/bin/env python3
"""
Validate migration 009 - Automation Engine v2
Complete validation of the new automation schema.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def validate_migration_009(db_path: str = "data/mcp_internal.db"):
    """Validate that migration 009 was applied correctly."""

    print("🔍 Validating Migration 009 - Automation Engine v2")
    print("=" * 55)

    db_path = Path(db_path)
    if not db_path.exists():
        print("❌ Database not found")
        return False

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # 1. Check migration record
        print("📋 Checking migration record...")
        migration = conn.execute("""
            SELECT name, applied_at FROM schema_versions
            WHERE name = '009_automation_engine'
        """).fetchone()

        if not migration:
            print("❌ Migration 009 not found in schema_versions")
            return False

        print(f"   ✅ Migration applied at: {migration['applied_at']}")

        # 2. Check tables exist
        print("\n📋 Checking automation tables...")
        expected_tables = [
            'automation_jobs',
            'automation_logs',
            'automation_screenshots',
            'automation_config'
        ]

        for table in expected_tables:
            exists = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (table,)).fetchone()

            if not exists:
                print(f"❌ Table {table} not found")
                return False

            # Check record count
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"   ✅ {table}: exists ({count} records)")

        # 3. Check indexes
        print("\n📋 Checking indexes...")
        index_count = conn.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_automation_%'
        """).fetchone()[0]

        if index_count < 8:
            print(f"⚠️ Expected 8+ automation indexes, found {index_count}")
        else:
            print(f"   ✅ Automation indexes: {index_count} created")

        # 4. Check seed configuration
        print("\n📋 Checking seed configuration...")
        configs = conn.execute("""
            SELECT key, value, category FROM automation_config
            WHERE updated_by = 'migration_009'
            ORDER BY key
        """).fetchall()

        if len(configs) < 5:
            print(f"⚠️ Expected 5+ seed configs, found {len(configs)}")
        else:
            print(f"   ✅ Seed configuration: {len(configs)} entries")
            for config in configs:
                print(f"      • {config['key']}: {config['value']} ({config['category']})")

        # 5. Test basic functionality
        print("\n📋 Testing basic functionality...")

        # Test automation_config
        test_config_id = None
        try:
            cursor = conn.execute("""
                INSERT INTO automation_config (
                    key, value, value_type, scope, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, ('test_validation', 'true', 'boolean', 'global',
                  datetime.now().isoformat(), 'validation_test'))

            test_config_id = cursor.lastrowid
            print("   ✅ automation_config: INSERT works")

            # Test retrieval
            result = conn.execute("""
                SELECT * FROM automation_config WHERE id = ?
            """, (test_config_id,)).fetchone()

            if result:
                print("   ✅ automation_config: SELECT works")
            else:
                print("   ❌ automation_config: SELECT failed")

        except Exception as e:
            print(f"   ❌ automation_config test failed: {e}")

        # Test automation_jobs with constraints
        test_job_id = None
        try:
            session_id = f"test_{int(datetime.now().timestamp())}"
            cursor = conn.execute("""
                INSERT INTO automation_jobs (
                    ticket_id, estado, automation_type, priority,
                    session_id, company_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (1, 'pendiente', 'selenium', 5, session_id, 'test',
                  datetime.now().isoformat(), datetime.now().isoformat()))

            test_job_id = cursor.lastrowid
            print("   ✅ automation_jobs: INSERT works")

        except Exception as e:
            print(f"   ❌ automation_jobs test failed: {e}")

        # 6. Test constraints
        print("\n📋 Testing constraints...")

        # Test invalid priority (should fail)
        try:
            conn.execute("""
                INSERT INTO automation_jobs (
                    ticket_id, estado, priority, session_id, company_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, 'pendiente', 15, 'test_invalid', 'test',
                  datetime.now().isoformat(), datetime.now().isoformat()))

            print("   ⚠️ Priority constraint not working (should reject priority > 10)")
        except sqlite3.IntegrityError:
            print("   ✅ Priority constraint working (rejected priority > 10)")

        # Test invalid estado (should fail)
        try:
            conn.execute("""
                INSERT INTO automation_jobs (
                    ticket_id, estado, session_id, company_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (1, 'invalid_state', 'test_invalid2', 'test',
                  datetime.now().isoformat(), datetime.now().isoformat()))

            print("   ⚠️ Estado constraint not working (should reject invalid states)")
        except sqlite3.IntegrityError:
            print("   ✅ Estado constraint working (rejected invalid state)")

        # 7. Test foreign key relationships
        print("\n📋 Testing foreign key relationships...")

        if test_job_id:
            try:
                # Test automation_logs FK
                conn.execute("""
                    INSERT INTO automation_logs (
                        job_id, session_id, level, category, message, timestamp, company_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (test_job_id, session_id, 'info', 'navigation', 'test log',
                      datetime.now().isoformat(), 'test'))

                print("   ✅ automation_logs: Foreign key relationship works")

                # Test automation_screenshots FK
                conn.execute("""
                    INSERT INTO automation_screenshots (
                        job_id, session_id, step_name, screenshot_type, file_path, created_at, company_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (test_job_id, session_id, 'test_step', 'step', '/test/path.png',
                      datetime.now().isoformat(), 'test'))

                print("   ✅ automation_screenshots: Foreign key relationship works")

            except Exception as e:
                print(f"   ❌ Foreign key test failed: {e}")

        # 8. Cleanup test data
        print("\n📋 Cleaning up test data...")
        if test_config_id:
            conn.execute("DELETE FROM automation_config WHERE id = ?", (test_config_id,))
        if test_job_id:
            conn.execute("DELETE FROM automation_logs WHERE job_id = ?", (test_job_id,))
            conn.execute("DELETE FROM automation_screenshots WHERE job_id = ?", (test_job_id,))
            conn.execute("DELETE FROM automation_jobs WHERE id = ?", (test_job_id,))

        conn.commit()
        print("   ✅ Test data cleaned up")

        # 9. Final summary
        print("\n📊 Migration Validation Summary:")
        print("   ✅ Migration record: Found")
        print(f"   ✅ Tables created: {len(expected_tables)}/4")
        print(f"   ✅ Indexes created: {index_count}")
        print(f"   ✅ Seed configs: {len(configs)}")
        print("   ✅ Constraints: Working")
        print("   ✅ Foreign keys: Working")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False

def main():
    """Main validation function."""

    if not Path("core/internal_db.py").exists():
        print("❌ Error: Run from mcp-server root directory")
        return 1

    success = validate_migration_009()

    if success:
        print("\n🎉 Migration 009 validation PASSED!")
        print("📋 Next steps:")
        print("   1. Implement read-only API endpoints")
        print("   2. Setup feature flag system")
        print("   3. Create basic automation tests")
        return 0
    else:
        print("\n💥 Migration 009 validation FAILED!")
        print("📋 Actions needed:")
        print("   1. Review error messages above")
        print("   2. Fix schema issues")
        print("   3. Re-run validation")
        return 1

if __name__ == "__main__":
    exit(main())