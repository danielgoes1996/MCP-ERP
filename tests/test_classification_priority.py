#!/usr/bin/env python3
"""
Test classification priority rules and merge logic.

Tests that merge_classification() properly respects the priority hierarchy:
  corrected > confirmed > pending > None

Created: 2025-01-13
Part of: POST_BACKFILL_ACTION_PLAN.md Phase 3
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.shared.classification_utils import merge_classification


def test_pending_cannot_override_confirmed():
    """Test that a new pending classification cannot override existing confirmed"""

    existing = {
        "status": "confirmed",
        "sat_account_code": "601.84",
        "sat_account_description": "Sueldos y salarios",
        "confidence_sat": 0.95,
        "reasoning": "User confirmed this classification"
    }

    new_classification = {
        "status": "pending",
        "sat_account_code": "601.01",
        "sat_account_description": "Different account",
        "confidence_sat": 0.80,
        "reasoning": "Automated classification"
    }

    result = merge_classification(existing, new_classification)

    # Should keep existing confirmed classification
    assert result["status"] == "confirmed", "Confirmed should not be overridden by pending"
    assert result["sat_account_code"] == "601.84", "SAT code should remain unchanged"
    print("✅ Test 1 passed: Pending cannot override confirmed")


def test_pending_cannot_override_corrected():
    """Test that a new pending classification cannot override existing corrected"""

    existing = {
        "status": "corrected",
        "sat_account_code": "601.01",
        "sat_account_description": "User corrected classification",
        "confidence_sat": 1.0,
        "reasoning": "User manually corrected"
    }

    new_classification = {
        "status": "pending",
        "sat_account_code": "601.84",
        "sat_account_description": "Automated suggestion",
        "confidence_sat": 0.90,
        "reasoning": "AI classification"
    }

    result = merge_classification(existing, new_classification)

    # Should keep existing corrected classification
    assert result["status"] == "corrected", "Corrected should not be overridden by pending"
    assert result["sat_account_code"] == "601.01", "SAT code should remain unchanged"
    print("✅ Test 2 passed: Pending cannot override corrected")


def test_confirmed_cannot_override_corrected():
    """Test that a confirmed classification cannot override existing corrected"""

    existing = {
        "status": "corrected",
        "sat_account_code": "601.01",
        "sat_account_description": "User corrected",
        "confidence_sat": 1.0,
        "reasoning": "Manual correction"
    }

    new_classification = {
        "status": "confirmed",
        "sat_account_code": "601.84",
        "sat_account_description": "User confirmed different code",
        "confidence_sat": 0.95,
        "reasoning": "User confirmation"
    }

    result = merge_classification(existing, new_classification)

    # Should keep existing corrected classification (highest priority)
    assert result["status"] == "corrected", "Corrected should not be overridden by confirmed"
    assert result["sat_account_code"] == "601.01", "SAT code should remain unchanged"
    print("✅ Test 3 passed: Confirmed cannot override corrected")


def test_pending_overrides_none():
    """Test that a pending classification can override missing classification"""

    existing = None

    new_classification = {
        "status": "pending",
        "sat_account_code": "601.84",
        "sat_account_description": "Sueldos y salarios",
        "confidence_sat": 0.85,
        "reasoning": "First classification"
    }

    result = merge_classification(existing, new_classification)

    # Should use new classification
    assert result["status"] == "pending", "Should accept new pending classification"
    assert result["sat_account_code"] == "601.84", "Should use new SAT code"
    print("✅ Test 4 passed: Pending overrides None")


def test_confirmed_overrides_pending():
    """Test that a confirmed classification overrides existing pending"""

    existing = {
        "status": "pending",
        "sat_account_code": "601.84",
        "sat_account_description": "AI suggestion",
        "confidence_sat": 0.85,
        "reasoning": "Automated"
    }

    new_classification = {
        "status": "confirmed",
        "sat_account_code": "601.01",
        "sat_account_description": "User confirmed different code",
        "confidence_sat": 0.95,
        "reasoning": "User confirmation"
    }

    result = merge_classification(existing, new_classification)

    # Should use new confirmed classification (higher priority)
    assert result["status"] == "confirmed", "Confirmed should override pending"
    assert result["sat_account_code"] == "601.01", "Should use new SAT code"
    print("✅ Test 5 passed: Confirmed overrides pending")


def test_corrected_overrides_confirmed():
    """Test that a corrected classification overrides existing confirmed"""

    existing = {
        "status": "confirmed",
        "sat_account_code": "601.84",
        "sat_account_description": "User confirmed",
        "confidence_sat": 0.95,
        "reasoning": "User confirmation"
    }

    new_classification = {
        "status": "corrected",
        "sat_account_code": "601.01",
        "sat_account_description": "User corrected after review",
        "confidence_sat": 1.0,
        "reasoning": "User correction"
    }

    result = merge_classification(existing, new_classification)

    # Should use new corrected classification (highest priority)
    assert result["status"] == "corrected", "Corrected should override confirmed"
    assert result["sat_account_code"] == "601.01", "Should use new SAT code"
    print("✅ Test 6 passed: Corrected overrides confirmed")


def test_same_priority_updates():
    """Test that same-priority classifications can update each other"""

    existing = {
        "status": "pending",
        "sat_account_code": "601.84",
        "sat_account_description": "Old classification",
        "confidence_sat": 0.75,
        "reasoning": "First attempt"
    }

    new_classification = {
        "status": "pending",
        "sat_account_code": "601.01",
        "sat_account_description": "Better classification",
        "confidence_sat": 0.90,
        "reasoning": "Improved classification"
    }

    result = merge_classification(existing, new_classification)

    # Should use new classification (same priority, so update allowed)
    assert result["status"] == "pending", "Status should remain pending"
    assert result["sat_account_code"] == "601.01", "Should use new SAT code"
    assert result["confidence_sat"] == 0.90, "Should use new confidence"
    print("✅ Test 7 passed: Same priority allows updates")


def test_merge_preserves_metadata():
    """Test that merge adds metadata about the merge operation"""

    existing = {
        "status": "pending",
        "sat_account_code": "601.84",
        "confidence_sat": 0.80
    }

    new_classification = {
        "status": "pending",
        "sat_account_code": "601.01",
        "confidence_sat": 0.85
    }

    result = merge_classification(existing, new_classification)

    # Should have merge metadata
    assert "merged_at" in result, "Should have merge timestamp"
    assert "previous_code" in result, "Should preserve previous SAT code"
    assert result["previous_code"] == "601.84", "Should have correct previous code"
    print("✅ Test 8 passed: Merge preserves metadata")


def test_none_existing_returns_new():
    """Test that when existing is None, new classification is returned as-is"""

    existing = None

    new_classification = {
        "status": "pending",
        "sat_account_code": "601.84",
        "confidence_sat": 0.85
    }

    result = merge_classification(existing, new_classification)

    # Should return new classification unchanged
    assert result == new_classification, "Should return new classification when existing is None"
    print("✅ Test 9 passed: None existing returns new classification")


def test_none_new_returns_existing():
    """Test that when new is None, existing classification is returned"""

    existing = {
        "status": "confirmed",
        "sat_account_code": "601.84",
        "confidence_sat": 0.95
    }

    new_classification = None

    result = merge_classification(existing, new_classification)

    # Should return existing classification unchanged
    assert result == existing, "Should return existing when new is None"
    print("✅ Test 10 passed: None new returns existing classification")


def run_all_tests():
    """Run all classification priority tests"""

    print("=" * 60)
    print("CLASSIFICATION PRIORITY RULES - TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        test_pending_cannot_override_confirmed,
        test_pending_cannot_override_corrected,
        test_confirmed_cannot_override_corrected,
        test_pending_overrides_none,
        test_confirmed_overrides_pending,
        test_corrected_overrides_confirmed,
        test_same_priority_updates,
        test_merge_preserves_metadata,
        test_none_existing_returns_new,
        test_none_new_returns_existing
    ]

    failed = 0
    for test_func in tests:
        try:
            test_func()
        except AssertionError as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} errored: {e}")
            failed += 1

    print()
    print("=" * 60)

    if failed == 0:
        print(f"✅ ALL {len(tests)} TESTS PASSED")
        print("=" * 60)
        print()
        print("Priority rules are working correctly:")
        print("  corrected > confirmed > pending > None")
        print()
        print("Safe to proceed with production deployment.")
        return 0
    else:
        print(f"❌ {failed}/{len(tests)} TESTS FAILED")
        print("=" * 60)
        print()
        print("⚠️  DO NOT DEPLOY - Fix priority rule issues first")
        return 1


if __name__ == '__main__':
    exit(run_all_tests())
