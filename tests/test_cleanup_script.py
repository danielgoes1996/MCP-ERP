"""
Test for cleanup_stale_placeholders.py script.

Verifies that the 4-tier cleanup policy works correctly.
"""
import sqlite3
import json
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.cleanup_stale_placeholders import (
    get_db_connection,
    create_archive_table_if_not_exists,
    get_stale_placeholders_by_tier,
    archive_placeholder,
    delete_placeholder
)


def setup_test_data():
    """Create test placeholders with various ages."""
    print("   Setting up test data...")

    conn = get_db_connection()
    create_archive_table_if_not_exists(conn)
    cursor = conn.cursor()

    # Clean up old test data
    cursor.execute("DELETE FROM expense_records WHERE description LIKE 'TEST_CLEANUP%'")
    cursor.execute("DELETE FROM archived_placeholders WHERE description LIKE 'TEST_CLEANUP%'")

    now = datetime.utcnow()

    test_data = [
        # Tier 1: 10 days old (warning)
        {
            "description": "TEST_CLEANUP Tier1 10d",
            "amount": 1000.0,
            "days_ago": 10
        },
        # Tier 2: 20 days old (urgent)
        {
            "description": "TEST_CLEANUP Tier2 20d",
            "amount": 2000.0,
            "days_ago": 20
        },
        # Tier 3: 45 days old (archive)
        {
            "description": "TEST_CLEANUP Tier3 45d",
            "amount": 3000.0,
            "days_ago": 45
        },
        # Tier 4: 70 days old (delete)
        {
            "description": "TEST_CLEANUP Tier4 70d",
            "amount": 4000.0,
            "days_ago": 70
        },
    ]

    for expense in test_data:
        created_at = (now - timedelta(days=expense['days_ago'])).isoformat()

        cursor.execute("""
        INSERT INTO expense_records (
            description, amount, moneda, workflow_status, invoice_status,
            bank_status, company_id, created_at, updated_at, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense['description'],
            expense['amount'],
            'MXN',
            'requiere_completar',
            'pendiente',
            'pendiente',
            'default',
            created_at,
            created_at,
            json.dumps({
                "missing_fields": ["category", "provider_rfc"],
                "auto_created": True
            })
        ))

    conn.commit()
    conn.close()

    print(f"   ✅ Created {len(test_data)} test placeholders")


def test_tier_classification():
    """Test that placeholders are correctly classified into tiers."""
    print("\n📝 Testing tier classification...")

    conn = get_db_connection()
    tiers = get_stale_placeholders_by_tier(conn, company_id='default')

    # Verify counts
    assert len(tiers['tier1_warning']) >= 1, "Should have Tier 1 (warning) placeholders"
    assert len(tiers['tier2_urgent']) >= 1, "Should have Tier 2 (urgent) placeholders"
    assert len(tiers['tier3_archive']) >= 1, "Should have Tier 3 (archive) placeholders"
    assert len(tiers['tier4_delete']) >= 1, "Should have Tier 4 (delete) placeholders"

    print(f"   ✅ Tier 1 (7-14d):  {len(tiers['tier1_warning'])} placeholders")
    print(f"   ✅ Tier 2 (14-30d): {len(tiers['tier2_urgent'])} placeholders")
    print(f"   ✅ Tier 3 (30-60d): {len(tiers['tier3_archive'])} placeholders")
    print(f"   ✅ Tier 4 (>60d):   {len(tiers['tier4_delete'])} placeholders")

    conn.close()
    return True


def test_archive_functionality():
    """Test archiving a placeholder."""
    print("\n📝 Testing archive functionality...")

    conn = get_db_connection()
    create_archive_table_if_not_exists(conn)

    # Get a Tier 3 placeholder
    tiers = get_stale_placeholders_by_tier(conn, company_id='default')

    if not tiers['tier3_archive']:
        print("   ⚠️  No Tier 3 placeholders to test archiving")
        conn.close()
        return True

    placeholder = tiers['tier3_archive'][0]
    original_id = placeholder['id']

    # Archive it
    success = archive_placeholder(conn, placeholder, dry_run=False)
    assert success, "Archive should succeed"

    # Verify it's in archived_placeholders
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) FROM archived_placeholders
    WHERE original_expense_id = ?
    """, (original_id,))

    archived_count = cursor.fetchone()[0]
    assert archived_count == 1, "Should have 1 archived record"

    # Verify it's removed from expense_records
    cursor.execute("""
    SELECT COUNT(*) FROM expense_records
    WHERE id = ?
    """, (original_id,))

    active_count = cursor.fetchone()[0]
    assert active_count == 0, "Should be removed from active records"

    print(f"   ✅ Successfully archived expense {original_id}")

    conn.close()
    return True


def test_delete_functionality():
    """Test deleting a very old placeholder."""
    print("\n📝 Testing delete functionality...")

    conn = get_db_connection()
    create_archive_table_if_not_exists(conn)

    # Get a Tier 4 placeholder
    tiers = get_stale_placeholders_by_tier(conn, company_id='default')

    if not tiers['tier4_delete']:
        print("   ⚠️  No Tier 4 placeholders to test deletion")
        conn.close()
        return True

    placeholder = tiers['tier4_delete'][0]
    original_id = placeholder['id']

    # Delete it
    success = delete_placeholder(conn, placeholder, dry_run=False)
    assert success, "Delete should succeed"

    # Verify it's in archived_placeholders (audit trail)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT archived_reason FROM archived_placeholders
    WHERE original_expense_id = ?
    """, (original_id,))

    row = cursor.fetchone()
    assert row is not None, "Should have audit trail in archived_placeholders"
    assert "deleted" in row[0].lower() or "expired" in row[0].lower(), "Should note it was deleted"

    # Verify it's removed from expense_records
    cursor.execute("""
    SELECT COUNT(*) FROM expense_records
    WHERE id = ?
    """, (original_id,))

    active_count = cursor.fetchone()[0]
    assert active_count == 0, "Should be removed from active records"

    print(f"   ✅ Successfully deleted expense {original_id}")

    conn.close()
    return True


def cleanup_test_data():
    """Remove test data."""
    print("\n📝 Cleaning up test data...")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM expense_records WHERE description LIKE 'TEST_CLEANUP%'")
    expense_deleted = cursor.rowcount

    cursor.execute("DELETE FROM archived_placeholders WHERE description LIKE 'TEST_CLEANUP%'")
    archived_deleted = cursor.rowcount

    conn.commit()
    conn.close()

    print(f"   ✅ Deleted {expense_deleted} active + {archived_deleted} archived test records")


if __name__ == '__main__':
    print("="*70)
    print("🚀 TESTING CLEANUP SCRIPT")
    print("="*70)

    try:
        # Setup
        setup_test_data()

        # Test 1: Tier classification
        test_tier_classification()

        # Test 2: Archive functionality
        test_archive_functionality()

        # Test 3: Delete functionality
        test_delete_functionality()

        # Cleanup
        cleanup_test_data()

        print("\n" + "="*70)
        print("✅ ALL CLEANUP SCRIPT TESTS PASSED!")
        print("="*70)
        print("\n🎉 Issue #6 COMPLETED - Cleanup Script Verified!\n")

        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        cleanup_test_data()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup_test_data()
        sys.exit(1)
