"""
FastAPI Integration - Parches adaptativos para integrar motor robusto sin romper nada.

Este módulo modifica el API existente para añadir capacidades robustas
manteniendo 100% compatibilidad hacia atrás.
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

# Imports existentes (mantener compatibilidad)
from modules.invoicing_agent.api import router as existing_router
from modules.invoicing_agent.models import TicketResponse, InvoicingJobResponse

# Imports robustos
from modules.invoicing_agent.integration_layer import (
    get_integration_layer,
    process_ticket_with_fallback,
    get_ticket_with_automation_data,
    validate_automation_system,
    is_enhanced_automation_available
)
from modules.invoicing_agent.enhanced_api import enhanced_router
from core.enhanced_api_models import EnhancedTicketResponse, AutomationStatus
from core.security_middleware import require_permission, rate_limit, Permission

logger = logging.getLogger(__name__)

# ===================================================================
# PATCH EXISTING ENDPOINTS (BACKWARD COMPATIBLE)
# ===================================================================

def patch_existing_api():
    """
    Parcha los endpoints existentes para añadir capacidades robustas
    sin romper compatibilidad.
    """

    # Patch 1: Enhance GET /invoicing/tickets/{id}
    @existing_router.get("/tickets/{ticket_id}/enhanced", response_model=EnhancedTicketResponse)
    async def get_enhanced_ticket_data(ticket_id: int) -> EnhancedTicketResponse:
        """Get ticket with enhanced automation data (new endpoint)."""
        try:
            layer = get_integration_layer()
            ticket_data = layer.get_enhanced_ticket_data(ticket_id)

            if not ticket_data:
                raise HTTPException(status_code=404, detail="Ticket not found")

            # Convert to enhanced response
            automation_data = ticket_data.get("automation_data", {})

            return EnhancedTicketResponse(
                id=ticket_data["id"],
                user_id=ticket_data.get("user_id"),
                raw_data=ticket_data["raw_data"],
                tipo=ticket_data["tipo"],
                estado=ticket_data["estado"],
                company_id=ticket_data.get("company_id", "default"),
                created_at=ticket_data["created_at"],
                updated_at=ticket_data["updated_at"],
                automation_status=_map_to_automation_status(automation_data),
                automation_job_id=automation_data.get("job_data", {}).get("id"),
                retry_count=0,
                processing_time_ms=automation_data.get("summary", {}).get("duration_ms")
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting enhanced ticket: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Patch 2: Add processing endpoint that uses robust engine
    @existing_router.post("/tickets/{ticket_id}/process-robust")
    @rate_limit("process_ticket", limit=50, window_seconds=3600)
    async def process_ticket_robust(
        ticket_id: int,
        background_tasks: BackgroundTasks,
        priority: str = "normal",
        alternative_urls: Optional[List[str]] = None,
        enable_captcha: bool = True,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Process ticket with robust automation engine."""
        try:
            config = {
                "priority": priority,
                "alternative_urls": alternative_urls or [],
                "enable_captcha_solving": enable_captcha,
                "max_retries": max_retries
            }

            # Process in background if enhanced mode available
            if is_enhanced_automation_available():
                background_tasks.add_task(_process_ticket_background, ticket_id, config)
                return {
                    "status": "queued",
                    "ticket_id": ticket_id,
                    "mode": "enhanced",
                    "message": "Ticket queued for robust processing"
                }
            else:
                # Process immediately with legacy
                result = await process_ticket_with_fallback(ticket_id, config)
                return {
                    "status": "completed" if result["success"] else "failed",
                    "ticket_id": ticket_id,
                    "mode": "legacy",
                    "result": result
                }

        except Exception as e:
            logger.error(f"Error processing ticket {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Patch 3: Add system status endpoint
    @existing_router.get("/system/status")
    async def get_system_status() -> Dict[str, Any]:
        """Get automation system status."""
        try:
            health = await validate_automation_system()
            layer = get_integration_layer()

            return {
                "system_health": health,
                "enhanced_mode": layer.is_enhanced_mode(),
                "capabilities": layer._get_available_capabilities(),
                "api_version": "1.1-enhanced"
            }

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Patch 4: Add automation data endpoint
    @existing_router.get("/automation/latest-data-enhanced")
    async def get_latest_automation_data_enhanced() -> Dict[str, Any]:
        """Enhanced version of automation data with more details."""
        try:
            from modules.invoicing_agent.automation_persistence import create_automation_persistence

            persistence = create_automation_persistence()

            # Get recent tickets with automation data
            recent_tickets = []
            for ticket_id in range(1, 11):  # Last 10 tickets
                try:
                    automation_data = persistence.get_automation_data(ticket_id)
                    if not automation_data.get("error"):
                        recent_tickets.append({
                            "ticket_id": ticket_id,
                            "automation_data": automation_data
                        })
                except:
                    continue

            return {
                "enhanced_mode": is_enhanced_automation_available(),
                "recent_automations": recent_tickets,
                "system_capabilities": get_integration_layer()._get_available_capabilities()
            }

        except Exception as e:
            logger.error(f"Error getting enhanced automation data: {e}")
            return {
                "enhanced_mode": False,
                "recent_automations": [],
                "error": str(e)
            }

    logger.info("✅ Existing API patched with enhanced capabilities")

# ===================================================================
# ENHANCED ROUTER MOUNTING
# ===================================================================

def mount_enhanced_router(app):
    """Mount enhanced router to existing FastAPI app."""
    try:
        # Mount v2 API
        app.include_router(enhanced_router)
        logger.info("✅ Enhanced API v2 mounted at /invoicing/v2")

        # Apply patches to existing router
        patch_existing_api()
        logger.info("✅ Existing API patched with enhanced features")

        return True

    except Exception as e:
        logger.error(f"Error mounting enhanced router: {e}")
        return False

# ===================================================================
# MIDDLEWARE INTEGRATION
# ===================================================================

def add_automation_middleware(app):
    """Add automation-specific middleware."""

    @app.middleware("http")
    async def automation_middleware(request, call_next):
        """Middleware for automation requests."""
        start_time = time.time()

        # Add automation context headers
        if request.url.path.startswith("/invoicing"):
            request.state.automation_mode = is_enhanced_automation_available()
            request.state.automation_capabilities = get_integration_layer()._get_available_capabilities()

        response = await call_next(request)

        # Add automation headers to response
        if hasattr(request.state, "automation_mode"):
            response.headers["X-Automation-Mode"] = "enhanced" if request.state.automation_mode else "legacy"
            response.headers["X-Processing-Time"] = str(int((time.time() - start_time) * 1000))

        return response

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

async def _process_ticket_background(ticket_id: int, config: Dict[str, Any]):
    """Background task for processing tickets."""
    try:
        result = await process_ticket_with_fallback(ticket_id, config)
        logger.info(f"Background processing completed for ticket {ticket_id}: {result['success']}")
    except Exception as e:
        logger.error(f"Background processing failed for ticket {ticket_id}: {e}")

def _map_to_automation_status(automation_data: Dict[str, Any]) -> AutomationStatus:
    """Map automation data to status enum."""
    if not automation_data:
        return AutomationStatus.PENDING

    job_data = automation_data.get("job_data", {})
    estado = job_data.get("estado", "pendiente")

    mapping = {
        "pendiente": AutomationStatus.PENDING,
        "en_progreso": AutomationStatus.PROCESSING,
        "completado": AutomationStatus.COMPLETED,
        "fallido": AutomationStatus.FAILED,
        "pausado": AutomationStatus.REQUIRES_INTERVENTION
    }

    return mapping.get(estado, AutomationStatus.PENDING)

# ===================================================================
# FEATURE FLAGS INTEGRATION
# ===================================================================

def check_feature_flag(company_id: str, feature_name: str) -> bool:
    """Check if feature is enabled for company."""
    try:
        from core.internal_db import _get_db_path, _DB_LOCK
        import sqlite3

        with _DB_LOCK:
            with sqlite3.connect(_get_db_path()) as conn:
                cursor = conn.execute(
                    "SELECT enabled FROM feature_flags WHERE company_id = ? AND feature_name = ?",
                    (company_id, feature_name)
                )
                result = cursor.fetchone()
                return result[0] if result else True  # Default to enabled

    except Exception as e:
        logger.error(f"Error checking feature flag: {e}")
        return True  # Default to enabled on error

def feature_flag_guard(feature_name: str):
    """Decorator to guard endpoints with feature flags."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            company_id = kwargs.get("company_id", "default")

            if not check_feature_flag(company_id, feature_name):
                raise HTTPException(
                    status_code=404,
                    detail=f"Feature '{feature_name}' not available"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

# ===================================================================
# INITIALIZATION
# ===================================================================

def initialize_enhanced_api(app):
    """Initialize enhanced API integration."""
    try:
        # 1. Mount enhanced router
        success = mount_enhanced_router(app)
        if not success:
            logger.warning("Failed to mount enhanced router")

        # 2. Add middleware
        add_automation_middleware(app)

        # 3. Initialize integration layer
        layer = get_integration_layer()
        logger.info(f"Integration layer initialized - Enhanced mode: {layer.is_enhanced_mode()}")

        # 4. Apply database migration if needed
        _apply_migration_if_needed()

        return True

    except Exception as e:
        logger.error(f"Error initializing enhanced API: {e}")
        return False

def _apply_migration_if_needed():
    """Apply database migration for enhanced features."""
    try:
        import os
        migration_file = "/Users/danielgoes96/Desktop/mcp-server/migrations/010_enhance_automation_20240922.sql"

        if os.path.exists(migration_file):
            # Check if migration already applied
            from core.internal_db import _get_db_path, _DB_LOCK
            import sqlite3

            with _DB_LOCK:
                with sqlite3.connect(_get_db_path()) as conn:
                    # Check if feature_flags table exists
                    cursor = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='feature_flags'"
                    )
                    if not cursor.fetchone():
                        logger.info("Applying enhanced automation migration...")
                        with open(migration_file, 'r') as f:
                            migration_sql = f.read()
                        conn.executescript(migration_sql)
                        logger.info("✅ Enhanced automation migration applied")

    except Exception as e:
        logger.error(f"Error applying migration: {e}")

import time