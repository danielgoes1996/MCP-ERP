"""
Structured Logging System for MCP Server.

Provides JSON-formatted logging with context (tenant_id, user_id, request_id)
for better observability and debugging.
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variables for request-scoped data
request_context: ContextVar[Dict[str, Any]] = ContextVar('request_context', default={})


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs logs in JSON format with consistent fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level (INFO, ERROR, etc.)
    - logger: Logger name (usually module name)
    - message: Log message
    - context: Request context (tenant_id, user_id, request_id)
    - extra: Additional fields passed to logger
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""

        # Base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context (tenant_id, user_id, request_id)
        ctx = request_context.get()
        if ctx:
            log_data["context"] = ctx

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # Add extra fields (expense_id, action, etc.)
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                'message', 'getMessage'
            ]:
                extra_fields[key] = value

        if extra_fields:
            log_data["extra"] = extra_fields

        return json.dumps(log_data)


def setup_structured_logging(
    level: str = "INFO",
    output_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        output_file: Optional file path for log output
        enable_console: Whether to log to console (stdout)
    """

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = StructuredFormatter()

    # Add console handler if enabled
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Add file handler if specified
    if output_file:
        file_handler = logging.FileHandler(output_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set up specific loggers
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = True


def set_request_context(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    **kwargs
) -> None:
    """
    Set context for the current request.

    This context will be included in all logs within the same async context.
    """
    ctx = {}

    if tenant_id:
        ctx["tenant_id"] = tenant_id
    if user_id:
        ctx["user_id"] = user_id
    if request_id:
        ctx["request_id"] = request_id

    # Add any additional context
    ctx.update(kwargs)

    request_context.set(ctx)


def clear_request_context() -> None:
    """Clear the current request context."""
    request_context.set({})


def get_structured_logger(name: str) -> logging.Logger:
    """
    Get a logger configured for structured logging.

    Usage:
        logger = get_structured_logger(__name__)
        logger.info("User action completed", action="create_expense", expense_id=123)
    """
    return logging.getLogger(name)


# Convenience functions for common logging patterns
def log_expense_action(
    logger: logging.Logger,
    action: str,
    expense_id: int,
    level: str = "INFO",
    **kwargs
) -> None:
    """
    Log an expense-related action with structured data.

    Args:
        logger: Logger instance
        action: Action being performed (e.g., "created", "updated", "deleted")
        expense_id: ID of the expense
        level: Log level
        **kwargs: Additional context fields
    """
    log_method = getattr(logger, level.lower())
    extra_data = {
        'expense_id': expense_id,
        'action': action,
        **kwargs
    }
    log_method(
        f"Expense {action}",
        extra=extra_data
    )


def log_validation_error(
    logger: logging.Logger,
    error_type: str,
    details: Dict[str, Any],
    **kwargs
) -> None:
    """
    Log a validation error with structured data.

    Args:
        logger: Logger instance
        error_type: Type of validation error (e.g., "duplicate_rfc", "missing_fields")
        details: Error details
        **kwargs: Additional context
    """
    extra_data = {
        'error_type': error_type,
        'details': details,
        **kwargs
    }
    logger.warning(
        f"Validation error: {error_type}",
        extra=extra_data
    )


def log_api_request(
    logger: logging.Logger,
    method: str,
    endpoint: str,
    status_code: int,
    duration_ms: float,
    **kwargs
) -> None:
    """
    Log an API request with timing and status.

    Args:
        logger: Logger instance
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        **kwargs: Additional context
    """
    extra_data = {
        'method': method,
        'endpoint': endpoint,
        'status_code': status_code,
        'duration_ms': duration_ms,
        **kwargs
    }
    logger.info(
        f"{method} {endpoint} - {status_code}",
        extra=extra_data
    )


# Example usage and testing
if __name__ == '__main__':
    # Setup logging
    setup_structured_logging(level="INFO", enable_console=True)

    # Get logger
    logger = get_structured_logger(__name__)

    # Set request context
    set_request_context(
        tenant_id="tenant_123",
        user_id="user_456",
        request_id="req_789"
    )

    # Log messages
    logger.info("Application started")
    logger.info("Processing expense", extra={'expense_id': 42, 'action': 'create'})

    # Log with different levels
    logger.warning("Validation warning", extra={'missing_fields': ["category", "rfc"]})

    # Log error with exception
    try:
        raise ValueError("Test error")
    except Exception:
        logger.exception("Error occurred during processing")

    # Clear context
    clear_request_context()

    logger.info("Request completed")
