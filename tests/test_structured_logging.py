"""
Test for structured logging system.

Verifies that logs are output in JSON format with proper context.
"""
import json
import sys
import os
from io import StringIO

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_structured_logging_format():
    """Test that structured logger outputs JSON format."""
    print("\n📝 Testing structured logging format...")

    from core.structured_logger import (
        setup_structured_logging,
        get_structured_logger,
        set_request_context,
        log_expense_action,
        log_validation_error
    )

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        # Setup logging to stdout
        setup_structured_logging(level="INFO", enable_console=True)

        # Get logger
        logger = get_structured_logger("test_module")

        # Set request context
        set_request_context(
            tenant_id="test_tenant",
            user_id="test_user",
            request_id="test_request_123"
        )

        # Log message
        logger.info("Test message", extra={'test_field': 'test_value'})

        # Get output
        sys.stdout = old_stdout
        output = captured_output.getvalue()

        # Parse JSON
        log_line = output.strip().split('\n')[0]
        log_data = json.loads(log_line)

        # Verify structure
        assert "timestamp" in log_data, "Log should have timestamp"
        assert "level" in log_data, "Log should have level"
        assert "logger" in log_data, "Log should have logger name"
        assert "message" in log_data, "Log should have message"
        assert "context" in log_data, "Log should have context"

        # Verify context
        context = log_data["context"]
        assert context["tenant_id"] == "test_tenant", "Context should have tenant_id"
        assert context["user_id"] == "test_user", "Context should have user_id"
        assert context["request_id"] == "test_request_123", "Context should have request_id"

        # Verify extra fields
        assert "extra" in log_data, "Log should have extra fields"
        assert log_data["extra"]["test_field"] == "test_value", "Extra field should be present"

        print("   ✅ JSON format verified")
        print("   ✅ Context fields present")
        print("   ✅ Extra fields included")

        return True

    except Exception as e:
        sys.stdout = old_stdout
        print(f"   ❌ Test failed: {e}")
        return False


def test_expense_action_logging():
    """Test expense action logging helper."""
    print("\n📝 Testing expense action logging...")

    from core.structured_logger import (
        setup_structured_logging,
        get_structured_logger,
        set_request_context,
        log_expense_action
    )

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        setup_structured_logging(level="INFO", enable_console=True)
        logger = get_structured_logger("test_module")

        set_request_context(tenant_id="tenant_1", expense_id=42)

        # Log expense action
        log_expense_action(
            logger,
            action="created",
            expense_id=42,
            level="INFO",
            workflow_status="requiere_completar"
        )

        sys.stdout = old_stdout
        output = captured_output.getvalue()

        log_line = output.strip().split('\n')[0]
        log_data = json.loads(log_line)

        # Verify
        assert log_data["message"] == "Expense created", "Message should be formatted correctly"
        assert log_data["extra"]["expense_id"] == 42, "expense_id should be in extra"
        assert log_data["extra"]["action"] == "created", "action should be in extra"
        assert log_data["extra"]["workflow_status"] == "requiere_completar", "workflow_status should be in extra"

        print("   ✅ Expense action logged correctly")
        print("   ✅ All fields present")

        return True

    except Exception as e:
        sys.stdout = old_stdout
        print(f"   ❌ Test failed: {e}")
        return False


def test_validation_error_logging():
    """Test validation error logging helper."""
    print("\n📝 Testing validation error logging...")

    from core.structured_logger import (
        setup_structured_logging,
        get_structured_logger,
        set_request_context,
        log_validation_error
    )

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        setup_structured_logging(level="WARNING", enable_console=True)
        logger = get_structured_logger("test_module")

        set_request_context(tenant_id="tenant_1")

        # Log validation error
        log_validation_error(
            logger,
            error_type="duplicate_rfc",
            details={
                "rfc": "TEST123",
                "existing_expense_id": 10,
                "attempted_expense_id": 20
            }
        )

        sys.stdout = old_stdout
        output = captured_output.getvalue()

        log_line = output.strip().split('\n')[0]
        log_data = json.loads(log_line)

        # Verify
        assert log_data["level"] == "WARNING", "Should be WARNING level"
        assert "duplicate_rfc" in log_data["message"], "Message should contain error type"
        assert log_data["extra"]["error_type"] == "duplicate_rfc", "error_type should be in extra"
        assert "details" in log_data["extra"], "details should be in extra"

        details = log_data["extra"]["details"]
        assert details["rfc"] == "TEST123", "RFC should be in details"
        assert details["existing_expense_id"] == 10, "existing_expense_id should be in details"

        print("   ✅ Validation error logged correctly")
        print("   ✅ Error details included")

        return True

    except Exception as e:
        sys.stdout = old_stdout
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("="*70)
    print("🚀 TESTING STRUCTURED LOGGING SYSTEM")
    print("="*70)

    all_passed = True

    # Test 1
    if not test_structured_logging_format():
        all_passed = False

    # Test 2
    if not test_expense_action_logging():
        all_passed = False

    # Test 3
    if not test_validation_error_logging():
        all_passed = False

    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL STRUCTURED LOGGING TESTS PASSED!")
        print("="*70)
        print("\n🎉 Issue #4 COMPLETED - Structured Logging Verified!\n")
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)

    sys.exit(0 if all_passed else 1)
