"""
MCP-Server API v1
Professional API versioning and routing
"""

from fastapi import APIRouter
from .invoicing import router as invoicing_router
from .debug import router as debug_router

# Create v1 API router
router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include sub-routers
router.include_router(invoicing_router, prefix="/invoicing")
router.include_router(debug_router, prefix="/debug")

__version__ = "1.0.0"