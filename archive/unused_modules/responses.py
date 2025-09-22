"""
Standardized API response formats
Provides consistent response structure across all endpoints
"""

from typing import Any, Optional, Dict, List, Union
from pydantic import BaseModel, Field
from datetime import datetime
from fastapi import status
from fastapi.responses import JSONResponse
import json


class StandardResponse(BaseModel):
    """Standard API response format"""
    success: bool = Field(description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Human-readable message")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status_code: int = Field(200, description="HTTP status code")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaginatedResponse(StandardResponse):
    """Response format for paginated data"""
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Items per page")
    total_items: int = Field(0, description="Total number of items")
    total_pages: int = Field(0, description="Total number of pages")
    has_next: bool = Field(False, description="Whether there is a next page")
    has_previous: bool = Field(False, description="Whether there is a previous page")


class ErrorDetail(BaseModel):
    """Error detail structure"""
    code: str = Field(description="Error code")
    message: str = Field(description="Error message")
    field: Optional[str] = Field(None, description="Field that caused the error")
    details: Optional[Any] = Field(None, description="Additional error details")


# Response builder functions
def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = status.HTTP_200_OK,
    **kwargs
) -> JSONResponse:
    """Create a successful response"""
    response = StandardResponse(
        success=True,
        message=message,
        data=data,
        status_code=status_code,
        **kwargs
    )

    return JSONResponse(
        status_code=status_code,
        content=response.dict(exclude_none=True)
    )


def error_response(
    message: str = "An error occurred",
    error_code: str = "UNKNOWN_ERROR",
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Any = None,
    **kwargs
) -> JSONResponse:
    """Create an error response"""
    response = StandardResponse(
        success=False,
        message=message,
        error={
            "code": error_code,
            "details": details
        },
        status_code=status_code,
        **kwargs
    )

    return JSONResponse(
        status_code=status_code,
        content=response.dict(exclude_none=True)
    )


def paginated_response(
    data: List[Any],
    page: int = 1,
    page_size: int = 20,
    total_items: int = 0,
    message: str = "Success",
    **kwargs
) -> JSONResponse:
    """Create a paginated response"""
    total_pages = (total_items + page_size - 1) // page_size if page_size > 0 else 0

    response = PaginatedResponse(
        success=True,
        message=message,
        data=data,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
        status_code=status.HTTP_200_OK,
        **kwargs
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response.dict(exclude_none=True)
    )


# Common error responses
def not_found_response(resource: str = "Resource") -> JSONResponse:
    """Create a not found response"""
    return error_response(
        message=f"{resource} not found",
        error_code="NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND
    )


def unauthorized_response(message: str = "Unauthorized") -> JSONResponse:
    """Create an unauthorized response"""
    return error_response(
        message=message,
        error_code="UNAUTHORIZED",
        status_code=status.HTTP_401_UNAUTHORIZED
    )


def forbidden_response(message: str = "Forbidden") -> JSONResponse:
    """Create a forbidden response"""
    return error_response(
        message=message,
        error_code="FORBIDDEN",
        status_code=status.HTTP_403_FORBIDDEN
    )


def validation_error_response(errors: List[Dict[str, Any]]) -> JSONResponse:
    """Create a validation error response"""
    return error_response(
        message="Validation failed",
        error_code="VALIDATION_ERROR",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=errors
    )


def server_error_response(message: str = "Internal server error") -> JSONResponse:
    """Create a server error response"""
    return error_response(
        message=message,
        error_code="INTERNAL_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


# Response wrapper for backwards compatibility
def create_response(
    success: bool = True,
    message: Optional[str] = None,
    data: Any = None,
    error: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a response dict (for backwards compatibility)"""
    response = {
        "success": success,
        "timestamp": datetime.utcnow().isoformat()
    }

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    if error:
        response["error"] = error

    response.update(kwargs)

    return response


# Middleware for automatic response formatting
class ResponseFormatter:
    """Middleware to automatically format responses"""

    async def __call__(self, request, call_next):
        response = await call_next(request)

        # Only format JSON responses
        if response.headers.get("content-type", "").startswith("application/json"):
            # Parse existing response
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            try:
                data = json.loads(body)

                # If not already formatted, wrap in standard format
                if not isinstance(data, dict) or "success" not in data:
                    formatted = StandardResponse(
                        success=response.status_code < 400,
                        data=data,
                        status_code=response.status_code
                    )
                    body = json.dumps(formatted.dict(exclude_none=True))

            except json.JSONDecodeError:
                pass

        return response


if __name__ == "__main__":
    # Test response creation
    print("Success response:")
    resp = success_response(data={"id": 1, "name": "Test"})
    print(resp.body)

    print("\nError response:")
    resp = error_response(message="Test error", error_code="TEST_ERROR")
    print(resp.body)

    print("\nPaginated response:")
    resp = paginated_response(
        data=[1, 2, 3],
        page=1,
        page_size=10,
        total_items=100
    )
    print(resp.body)