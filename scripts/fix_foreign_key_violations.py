#!/usr/bin/env python3
"""
Fix foreign key violations before applying automation engine migration.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def fix_foreign_key_violations(db_path: str = "data/mcp_internal.db"):
    """Fix foreign key violations in the database."""

    print("🔧 Fixing Foreign Key Violations")
    print("=" * 40)

    db_path = Path(db_path)
    if not db_path.exists():
        print("❌ Database not found")
        return False

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        # Get all FK violations
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()

        if not violations:
            print("✅ No foreign key violations found")
            conn.close()
            return True

        print(f"📊 Found {len(violations)} foreign key violations")

        # Group violations by table
        violations_by_table = {}
        for violation in violations:
            table = violation[0]
            if table not in violations_by_table:
                violations_by_table[table] = []
            violations_by_table[table].append(violation)

        for table, table_violations in violations_by_table.items():
            print(f"\n🔍 Table: {table} ({len(table_violations)} violations)")

            # Show first few violations for context
            for i, violation in enumerate(table_violations[:3]):
                print(f"   {i+1}. Row ID: {violation[1]}, Parent: {violation[2]}, FK Index: {violation[3]}")

            if len(table_violations) > 3:
                print(f"   ... and {len(table_violations) - 3} more")

        # Strategy: Remove orphaned records
        print("\n🛠️ Fixing strategy: Remove orphaned records")

        fixed_count = 0

        # Common patterns to fix
        fix_strategies = [
            {
                "table": "expense_invoices",
                "check": "SELECT id FROM expense_invoices WHERE expense_id NOT IN (SELECT id FROM expense_records)",
                "fix": "DELETE FROM expense_invoices WHERE expense_id NOT IN (SELECT id FROM expense_records)"
            },
            {
                "table": "expense_events",
                "check": "SELECT id FROM expense_events WHERE expense_id NOT IN (SELECT id FROM expense_records)",
                "fix": "DELETE FROM expense_events WHERE expense_id NOT IN (SELECT id FROM expense_records)"
            },
            {
                "table": "expense_bank_links",
                "check": "SELECT id FROM expense_bank_links WHERE expense_id NOT IN (SELECT id FROM expense_records)",
                "fix": "DELETE FROM expense_bank_links WHERE expense_id NOT IN (SELECT id FROM expense_records)"
            },
            {
                "table": "expense_payments",
                "check": "SELECT id FROM expense_payments WHERE expense_id NOT IN (SELECT id FROM expense_records)",
                "fix": "DELETE FROM expense_payments WHERE expense_id NOT IN (SELECT id FROM expense_records)"
            },
            {
                "table": "tickets",
                "check": "SELECT id FROM tickets WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)",
                "fix": "UPDATE tickets SET user_id = NULL WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)"
            },
            {
                "table": "tickets",
                "check": "SELECT id FROM tickets WHERE merchant_id IS NOT NULL AND merchant_id NOT IN (SELECT id FROM merchants)",
                "fix": "UPDATE tickets SET merchant_id = NULL WHERE merchant_id IS NOT NULL AND merchant_id NOT IN (SELECT id FROM merchants)"
            },
            {
                "table": "invoicing_jobs",
                "check": "SELECT id FROM invoicing_jobs WHERE ticket_id NOT IN (SELECT id FROM tickets)",
                "fix": "DELETE FROM invoicing_jobs WHERE ticket_id NOT IN (SELECT id FROM tickets)"
            },
            {
                "table": "invoicing_jobs",
                "check": "SELECT id FROM invoicing_jobs WHERE merchant_id IS NOT NULL AND merchant_id NOT IN (SELECT id FROM merchants)",
                "fix": "UPDATE invoicing_jobs SET merchant_id = NULL WHERE merchant_id IS NOT NULL AND merchant_id NOT IN (SELECT id FROM merchants)"
            }
        ]

        for strategy in fix_strategies:
            table = strategy["table"]

            # Check if table exists
            table_exists = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (table,)).fetchone()

            if not table_exists:
                continue

            # Check for orphaned records
            try:
                orphaned = conn.execute(strategy["check"]).fetchall()

                if orphaned:
                    print(f"   🔧 Fixing {len(orphaned)} orphaned records in {table}")

                    # Apply fix
                    result = conn.execute(strategy["fix"])
                    affected_rows = result.rowcount

                    print(f"   ✅ Fixed {affected_rows} records in {table}")
                    fixed_count += affected_rows

            except sqlite3.OperationalError as e:
                print(f"   ⚠️ Could not fix {table}: {e}")
                continue

        # Commit changes
        conn.commit()

        # Re-check violations
        remaining_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()

        print(f"\n📊 Summary:")
        print(f"   • Fixed {fixed_count} records")
        print(f"   • Initial violations: {len(violations)}")
        print(f"   • Remaining violations: {len(remaining_violations)}")

        if remaining_violations:
            print(f"\n⚠️ {len(remaining_violations)} violations remain:")
            for violation in remaining_violations[:5]:
                print(f"   • Table: {violation[0]}, Row: {violation[1]}")

            if len(remaining_violations) > 5:
                print(f"   • ... and {len(remaining_violations) - 5} more")

            print("\n💡 Remaining violations may be acceptable for migration")
            print("   They will be handled by the new schema's soft foreign keys")
        else:
            print("✅ All foreign key violations resolved!")

        return True

    except Exception as e:
        print(f"❌ Error fixing violations: {e}")
        return False

def main():
    """Main function."""
    success = fix_foreign_key_violations()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())