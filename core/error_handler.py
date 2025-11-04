"""
Standardized Error Handling for MCP Server
Provides consistent error responses, structured logging, and error tracking
"""

import logging
import uuid
import json
from datetime import datetime
from typing import Optional, Any, Dict
from fastapi import HTTPException, Request
from dataclasses import dataclass, asdict

# Import database adapter for error storage
try:
    from core.unified_db_adapter import get_unified_adapter
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for error tracking"""
    error_id: str
    timestamp: datetime
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.timestamp:
            result["timestamp"] = self.timestamp.isoformat()
        return result


class MCPError(Exception):
    """Base exception class for MCP Server errors"""

    def __init__(self, message: str, status_code: int = 500, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class ValidationError(MCPError):
    """Raised when input validation fails"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, status_code=400, details=details)


class NotFoundError(MCPError):
    """Raised when a resource is not found"""

    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with ID {identifier} not found"
        super().__init__(message, status_code=404)


class ServiceError(MCPError):
    """Raised when an external service fails"""

    def __init__(self, service: str, message: str, details: Optional[Any] = None):
        super().__init__(f"{service} error: {message}", status_code=503, details=details)


class BusinessLogicError(MCPError):
    """Raised when business logic validation fails"""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, status_code=422, details=details)


def handle_error(error: Exception, context: str = "", default_message: str = "Internal server error") -> HTTPException:
    """
    Convert various exceptions to standardized HTTPException

    Args:
        error: The exception to handle
        context: Additional context for logging
        default_message: Default error message for unknown exceptions

    Returns:
        HTTPException with appropriate status code and message
    """
    if isinstance(error, MCPError):
        logger.error(f"{context}: {error.message}", extra={"details": error.details})
        return HTTPException(status_code=error.status_code, detail=error.message)

    elif isinstance(error, HTTPException):
        # Re-raise existing HTTPExceptions
        logger.error(f"{context}: HTTP {error.status_code} - {error.detail}")
        return error

    elif isinstance(error, ValueError):
        logger.warning(f"{context}: Validation error - {str(error)}")
        return HTTPException(status_code=400, detail=str(error))

    elif isinstance(error, FileNotFoundError):
        logger.warning(f"{context}: File not found - {str(error)}")
        return HTTPException(status_code=404, detail="Resource not found")

    elif isinstance(error, PermissionError):
        logger.warning(f"{context}: Permission denied - {str(error)}")
        return HTTPException(status_code=403, detail="Access denied")

    else:
        # Log unexpected errors with full traceback
        logger.exception(f"{context}: Unexpected error", exc_info=error)
        return HTTPException(status_code=500, detail=default_message)


def log_endpoint_entry(endpoint: str, **kwargs):
    """Standardized logging for endpoint entry"""
    logger.info(f"📥 {endpoint} called", extra=kwargs)


def log_endpoint_success(endpoint: str, duration: Optional[float] = None, **kwargs):
    """Standardized logging for successful endpoint completion"""
    extra = {"duration_ms": duration} if duration else {}
    extra.update(kwargs)
    logger.info(f"✅ {endpoint} completed", extra=extra)


def log_endpoint_error(endpoint: str, error: Exception, **kwargs):
    """Standardized logging for endpoint errors"""
    logger.error(f"❌ {endpoint} failed: {str(error)}", extra=kwargs, exc_info=error)


def create_error_context(
    request: Optional[Request] = None,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    endpoint: Optional[str] = None
) -> ErrorContext:
    """Create error context for tracking"""
    error_id = str(uuid.uuid4())
    timestamp = datetime.utcnow()

    method = None
    ip_address = None
    user_agent = None

    if request:
        method = request.method
        ip_address = getattr(request.client, 'host', None) if request.client else None
        user_agent = request.headers.get('user-agent')
        endpoint = endpoint or str(request.url.path)

    return ErrorContext(
        error_id=error_id,
        timestamp=timestamp,
        user_id=user_id,
        tenant_id=tenant_id,
        endpoint=endpoint,
        method=method,
        ip_address=ip_address,
        user_agent=user_agent
    )


def store_error_in_db(
    context: ErrorContext,
    error: Exception,
    severity: str = "medium",
    category: str = "unknown",
    user_message: str = "Ha ocurrido un error",
    metadata: Optional[Dict[str, Any]] = None
):
    """Store error in database for tracking and analysis"""
    if not DB_AVAILABLE:
        logger.warning("Database not available for error storage")
        return

    try:
        adapter = get_unified_adapter()
        with adapter.get_connection() as conn:
            cursor = conn.cursor()

            # Create error_logs table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_id TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    user_id INTEGER,
                    tenant_id INTEGER,
                    endpoint TEXT,
                    method TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    stack_trace TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    resolution_notes TEXT
                )
            """)

            # Get stack trace
            import traceback
            stack_trace = traceback.format_exc() if error else None

            # Insert error log
            cursor.execute("""
                INSERT INTO error_logs
                (error_id, category, severity, message, user_message,
                 user_id, tenant_id, endpoint, method, ip_address, user_agent,
                 stack_trace, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                context.error_id,
                category,
                severity,
                str(error),
                user_message,
                context.user_id,
                context.tenant_id,
                context.endpoint,
                context.method,
                context.ip_address,
                context.user_agent,
                stack_trace,
                json.dumps(metadata) if metadata else None
            ))

            conn.commit()
            logger.info(f"✅ Error {context.error_id} stored in database")

    except Exception as e:
        logger.error(f"Failed to store error in database: {e}")


def handle_error_with_context(
    error: Exception,
    context: ErrorContext,
    default_message: str = "Internal server error",
    user_message: Optional[str] = None,
    category: str = "unknown",
    severity: str = "medium"
) -> HTTPException:
    """Enhanced error handling with full context and tracking"""

    # Use provided user message or generate one
    final_user_message = user_message or _generate_user_friendly_message(error, category)

    # Store error in database
    store_error_in_db(
        context=context,
        error=error,
        severity=severity,
        category=category,
        user_message=final_user_message,
        metadata={"original_error": str(error)}
    )

    # Enhanced logging with context
    logger.error(
        f"🔴 Error {context.error_id} in {context.endpoint}: {str(error)}",
        extra={
            "error_id": context.error_id,
            "user_id": context.user_id,
            "tenant_id": context.tenant_id,
            "endpoint": context.endpoint,
            "category": category,
            "severity": severity
        },
        exc_info=error
    )

    # Handle different error types
    if isinstance(error, MCPError):
        return HTTPException(
            status_code=error.status_code,
            detail={
                "error": True,
                "error_id": context.error_id,
                "message": final_user_message,
                "category": category,
                "timestamp": context.timestamp.isoformat()
            }
        )
    elif isinstance(error, HTTPException):
        return error
    elif isinstance(error, ValueError):
        return HTTPException(
            status_code=400,
            detail={
                "error": True,
                "error_id": context.error_id,
                "message": final_user_message,
                "category": "validation",
                "timestamp": context.timestamp.isoformat()
            }
        )
    else:
        return HTTPException(
            status_code=500,
            detail={
                "error": True,
                "error_id": context.error_id,
                "message": final_user_message,
                "category": category,
                "timestamp": context.timestamp.isoformat()
            }
        )


def _generate_user_friendly_message(error: Exception, category: str) -> str:
    """Generate user-friendly error messages based on error type and category"""
    user_messages = {
        "authentication": "Credenciales inválidas. Por favor, verifica tu email y contraseña.",
        "authorization": "No tienes permisos para realizar esta acción.",
        "validation": "Los datos proporcionados no son válidos. Por favor, revisa e intenta nuevamente.",
        "database": "Error en el servidor. Por favor, intenta nuevamente en unos momentos.",
        "external_api": "Servicio externo no disponible. Por favor, intenta más tarde.",
        "business_logic": "No se pudo completar la operación. Verifica los datos e intenta nuevamente.",
        "system": "Error interno del sistema. Nuestro equipo ha sido notificado.",
        "unknown": "Ha ocurrido un error inesperado. Por favor, contacta al soporte si persiste."
    }
    return user_messages.get(category, user_messages["unknown"])


def get_error_stats(tenant_id: Optional[int] = None, days: int = 7) -> Dict[str, Any]:
    """Get error statistics for monitoring and alerting"""
    if not DB_AVAILABLE:
        return {"error": "Database not available"}

    try:
        adapter = get_unified_adapter()
        with adapter.get_connection() as conn:
            cursor = conn.cursor()

            # Base query
            where_clause = "WHERE created_at >= datetime('now', '-{} days')".format(days)
            if tenant_id:
                where_clause += f" AND tenant_id = {tenant_id}"

            # Total errors
            cursor.execute(f"SELECT COUNT(*) FROM error_logs {where_clause}")
            total_errors = cursor.fetchone()[0]

            # Errors by category
            cursor.execute(f"""
                SELECT category, COUNT(*) as count
                FROM error_logs {where_clause}
                GROUP BY category
                ORDER BY count DESC
            """)
            by_category = dict(cursor.fetchall())

            # Errors by severity
            cursor.execute(f"""
                SELECT severity, COUNT(*) as count
                FROM error_logs {where_clause}
                GROUP BY severity
                ORDER BY count DESC
            """)
            by_severity = dict(cursor.fetchall())

            # Top endpoints with errors
            cursor.execute(f"""
                SELECT endpoint, COUNT(*) as count
                FROM error_logs {where_clause}
                GROUP BY endpoint
                ORDER BY count DESC
                LIMIT 10
            """)
            top_endpoints = dict(cursor.fetchall())

            return {
                "period_days": days,
                "tenant_id": tenant_id,
                "total_errors": total_errors,
                "by_category": by_category,
                "by_severity": by_severity,
                "top_error_endpoints": top_endpoints,
                "generated_at": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"Failed to get error stats: {e}")
        return {"error": str(e)}