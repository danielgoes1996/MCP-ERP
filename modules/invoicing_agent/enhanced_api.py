"""
Enhanced API Router - Integración robusta sin romper endpoints existentes.

Añade capacidades del motor robusto manteniendo compatibilidad completa.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from core.enhanced_api_models import (
    EnhancedTicketCreate, EnhancedTicketResponse, AutomationJobRequest,
    AutomationJobResponse, BulkAutomationRequest, BulkAutomationResponse,
    SystemHealth, AutomationMetrics, FeatureFlags, TenantConfig,
    AutomationStatus, JobPriority
)

# Importar motor unificado
try:
    from core.unified_automation_engine import create_unified_engine
    UNIFIED_ENGINE_AVAILABLE = True
except ImportError:
    UNIFIED_ENGINE_AVAILABLE = False

# Importar persistencia existente
from modules.invoicing_agent.automation_persistence import create_automation_persistence

logger = logging.getLogger(__name__)

# Router para endpoints mejorados
enhanced_router = APIRouter(prefix="/invoicing/v2", tags=["automation_enhanced"])

# ===================================================================
# ENHANCED TICKET ENDPOINTS
# ===================================================================

@enhanced_router.post("/tickets", response_model=EnhancedTicketResponse)
async def create_enhanced_ticket(
    ticket: EnhancedTicketCreate,
    background_tasks: BackgroundTasks
) -> EnhancedTicketResponse:
    """
    Create ticket with enhanced automation capabilities.

    Backward compatible but with new features:
    - Priority queue
    - Alternative URLs
    - Captcha solving
    - Real-time progress tracking
    """
    try:
        # Create ticket using existing function (backward compatibility)
        from modules.invoicing_agent.models import create_ticket

        ticket_id = create_ticket(
            raw_data=ticket.raw_data,
            tipo=ticket.tipo,
            user_id=ticket.user_id,
            company_id=ticket.company_id
        )

        # Create enhanced automation job if auto_process enabled
        automation_job_id = None
        if ticket.auto_process and UNIFIED_ENGINE_AVAILABLE:
            background_tasks.add_task(
                _process_enhanced_ticket,
                ticket_id,
                ticket.dict()
            )

            # Create automation job record
            automation_job_id = await _create_automation_job(
                ticket_id=ticket_id,
                priority=ticket.priority,
                config={
                    "alternative_urls": ticket.alternative_urls or [],
                    "max_retries": ticket.max_retries,
                    "timeout_seconds": ticket.timeout_seconds,
                    "enable_captcha_solving": ticket.enable_captcha_solving,
                    "notification_webhook": ticket.notification_webhook
                }
            )

        # Build enhanced response
        return EnhancedTicketResponse(
            id=ticket_id,
            user_id=ticket.user_id,
            raw_data=ticket.raw_data,
            tipo=ticket.tipo,
            estado="pendiente",
            company_id=ticket.company_id,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            automation_status=AutomationStatus.QUEUED if ticket.auto_process else AutomationStatus.PENDING,
            automation_job_id=automation_job_id,
            retry_count=0
        )

    except Exception as e:
        logger.error(f"Error creating enhanced ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_router.get("/tickets/{ticket_id}", response_model=EnhancedTicketResponse)
async def get_enhanced_ticket(ticket_id: int) -> EnhancedTicketResponse:
    """Get ticket with full automation details."""
    try:
        # Get basic ticket (existing function)
        from modules.invoicing_agent.models import get_ticket
        ticket_data = get_ticket(ticket_id)

        if not ticket_data:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Get automation data
        persistence = create_automation_persistence()
        automation_data = persistence.get_automation_data(ticket_id)

        # Build enhanced response
        response = EnhancedTicketResponse(
            id=ticket_data['id'],
            user_id=ticket_data.get('user_id'),
            raw_data=ticket_data['raw_data'],
            tipo=ticket_data['tipo'],
            estado=ticket_data['estado'],
            company_id=ticket_data.get('company_id', 'default'),
            created_at=ticket_data['created_at'],
            updated_at=ticket_data['updated_at'],
            automation_status=_map_automation_status(automation_data),
            automation_job_id=automation_data.get('job_data', {}).get('id')
        )

        # Add automation details if available
        if not automation_data.get('error'):
            response.automation_summary = _build_automation_summary(automation_data)
            response.automation_steps = _build_automation_steps(automation_data)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enhanced ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================================================================
# AUTOMATION JOB MANAGEMENT
# ===================================================================

@enhanced_router.post("/jobs", response_model=AutomationJobResponse)
async def create_automation_job(
    job_request: AutomationJobRequest,
    background_tasks: BackgroundTasks
) -> AutomationJobResponse:
    """Create standalone automation job."""
    try:
        job_id = await _create_automation_job(
            ticket_id=job_request.ticket_id,
            priority=job_request.priority,
            config=job_request.config,
            scheduled_at=job_request.scheduled_at
        )

        # Start processing if not scheduled
        if not job_request.scheduled_at:
            background_tasks.add_task(_process_automation_job, job_id)

        return await _get_automation_job(job_id)

    except Exception as e:
        logger.error(f"Error creating automation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_router.get("/jobs", response_model=List[AutomationJobResponse])
async def list_automation_jobs(
    status: Optional[AutomationStatus] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    company_id: str = Query("default")
) -> List[AutomationJobResponse]:
    """List automation jobs with filtering."""
    try:
        # Get jobs from database
        jobs = await _list_automation_jobs(
            status=status,
            limit=limit,
            offset=offset,
            company_id=company_id
        )
        return jobs

    except Exception as e:
        logger.error(f"Error listing automation jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_router.get("/jobs/{job_id}", response_model=AutomationJobResponse)
async def get_automation_job(job_id: int) -> AutomationJobResponse:
    """Get automation job details."""
    try:
        job = await _get_automation_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting automation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_router.post("/jobs/{job_id}/cancel")
async def cancel_automation_job(job_id: int) -> Dict[str, Any]:
    """Cancel running automation job."""
    try:
        # Implementation depends on your queue system
        # For now, mark as cancelled in database
        persistence = create_automation_persistence()
        persistence.update_automation_job_status(
            job_id,
            "cancelado",
            {"cancelled_at": datetime.utcnow().isoformat()}
        )

        return {"status": "cancelled", "job_id": job_id}

    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================================================================
# REAL-TIME PROGRESS STREAMING
# ===================================================================

@enhanced_router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: int):
    """Stream real-time job progress via SSE."""

    async def event_stream():
        """Generate SSE events for job progress."""
        try:
            last_update = None

            while True:
                # Get current job status
                job = await _get_automation_job(job_id)
                if not job:
                    yield {"event": "error", "data": json.dumps({"error": "Job not found"})}
                    break

                # Check if job is completed
                if job.status in [AutomationStatus.COMPLETED, AutomationStatus.FAILED, AutomationStatus.CANCELLED]:
                    yield {"event": "complete", "data": job.json()}
                    break

                # Send update if changed
                if job.updated_at != last_update:
                    yield {"event": "progress", "data": job.json()}
                    last_update = job.updated_at

                await asyncio.sleep(2)  # Poll every 2 seconds

        except Exception as e:
            logger.error(f"Error in job stream: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_stream())

# ===================================================================
# BULK OPERATIONS
# ===================================================================

@enhanced_router.post("/bulk", response_model=BulkAutomationResponse)
async def create_bulk_automation(
    bulk_request: BulkAutomationRequest,
    background_tasks: BackgroundTasks
) -> BulkAutomationResponse:
    """Process multiple tickets in batch."""
    try:
        import uuid
        batch_id = str(uuid.uuid4())

        # Create jobs for each ticket
        job_ids = []
        for ticket_id in bulk_request.ticket_ids:
            job_id = await _create_automation_job(
                ticket_id=ticket_id,
                priority=bulk_request.priority,
                config={"batch_id": batch_id}
            )
            job_ids.append(job_id)

        # Start batch processing with concurrency limit
        background_tasks.add_task(
            _process_bulk_automation,
            job_ids,
            bulk_request.max_concurrent,
            bulk_request.notification_webhook
        )

        # Estimate completion time
        estimated_time_per_job = 120  # seconds
        estimated_completion = datetime.utcnow() + timedelta(
            seconds=estimated_time_per_job * len(bulk_request.ticket_ids) // bulk_request.max_concurrent
        )

        return BulkAutomationResponse(
            batch_id=batch_id,
            total_tickets=len(bulk_request.ticket_ids),
            jobs_created=job_ids,
            estimated_completion=estimated_completion,
            status_url=f"/invoicing/v2/bulk/{batch_id}/status"
        )

    except Exception as e:
        logger.error(f"Error creating bulk automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================================================================
# SYSTEM MONITORING
# ===================================================================

@enhanced_router.get("/health", response_model=SystemHealth)
async def get_system_health() -> SystemHealth:
    """Get system health status."""
    try:
        from core.service_stack_config import get_service_stack

        service_stack = get_service_stack()
        service_status = service_stack.get_service_status()

        # Build health response
        services = []
        for service_key, info in service_status["services"].items():
            services.append({
                "name": info["name"],
                "status": "healthy" if info["available"] else "down",
                "response_time_ms": None,
                "error_rate": None,
                "last_check": datetime.utcnow()
            })

        # Get system metrics
        active_jobs = await _count_active_jobs()
        queue_size = await _get_queue_size()

        overall_status = "healthy" if service_status["readiness_score"] > 0.7 else "degraded"

        return SystemHealth(
            status=overall_status,
            services=services,
            active_jobs=active_jobs,
            queue_size=queue_size,
            average_processing_time_ms=120000,  # TODO: Calculate from DB
            success_rate_24h=0.85  # TODO: Calculate from DB
        )

    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_router.get("/metrics", response_model=AutomationMetrics)
async def get_automation_metrics() -> AutomationMetrics:
    """Get automation metrics."""
    try:
        # TODO: Implement metrics calculation from database
        return AutomationMetrics(
            total_jobs_today=0,
            successful_jobs_today=0,
            failed_jobs_today=0,
            average_processing_time_ms=120000,
            captchas_solved_today=0,
            cost_today=0.0,
            top_error_types=[]
        )

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

async def _process_enhanced_ticket(ticket_id: int, config: Dict[str, Any]):
    """Process ticket with enhanced automation."""
    try:
        if not UNIFIED_ENGINE_AVAILABLE:
            logger.warning("Unified engine not available for enhanced processing")
            return

        engine = create_unified_engine()

        # Get ticket data
        from modules.invoicing_agent.models import get_ticket
        ticket_data = get_ticket(ticket_id)

        if not ticket_data:
            logger.error(f"Ticket {ticket_id} not found for processing")
            return

        # Create merchant placeholder
        merchant = {
            "nombre": config.get("merchant_hint", "Unknown"),
            "portal_url": ""  # Will be determined by URL classification
        }

        # Process with unified engine
        result = await engine.process_invoice_automation(
            merchant=merchant,
            ticket_data=ticket_data,
            ticket_id=ticket_id,
            alternative_urls=config.get("alternative_urls", [])
        )

        logger.info(f"Enhanced processing completed for ticket {ticket_id}: {result.success}")

    except Exception as e:
        logger.error(f"Error in enhanced ticket processing: {e}")

async def _create_automation_job(
    ticket_id: int,
    priority: JobPriority = JobPriority.NORMAL,
    config: Dict[str, Any] = None,
    scheduled_at: Optional[datetime] = None
) -> int:
    """Create automation job record."""
    try:
        persistence = create_automation_persistence()

        job_data = {
            'config': config or {},
            'company_id': 'default',
            'priority': priority.value,
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None
        }

        job_id = persistence.create_automation_job(ticket_id, job_data)
        return job_id

    except Exception as e:
        logger.error(f"Error creating automation job: {e}")
        raise

async def _get_automation_job(job_id: int) -> Optional[AutomationJobResponse]:
    """Get automation job details."""
    # TODO: Implement proper job retrieval from database
    return None

async def _list_automation_jobs(
    status: Optional[AutomationStatus] = None,
    limit: int = 50,
    offset: int = 0,
    company_id: str = "default"
) -> List[AutomationJobResponse]:
    """List automation jobs."""
    # TODO: Implement proper job listing from database
    return []

async def _count_active_jobs() -> int:
    """Count active automation jobs."""
    # TODO: Implement from database
    return 0

async def _get_queue_size() -> int:
    """Get queue size."""
    # TODO: Implement queue size check
    return 0

def _map_automation_status(automation_data: Dict[str, Any]) -> AutomationStatus:
    """Map automation data to status enum."""
    if automation_data.get('error'):
        return AutomationStatus.FAILED

    job_data = automation_data.get('job_data', {})
    estado = job_data.get('estado', 'pendiente')

    status_mapping = {
        'en_progreso': AutomationStatus.PROCESSING,
        'completado': AutomationStatus.COMPLETED,
        'fallido': AutomationStatus.FAILED,
        'pausado': AutomationStatus.REQUIRES_INTERVENTION
    }

    return status_mapping.get(estado, AutomationStatus.PENDING)

def _build_automation_summary(automation_data: Dict[str, Any]):
    """Build automation summary from data."""
    # TODO: Implement based on automation_data structure
    return None

def _build_automation_steps(automation_data: Dict[str, Any]):
    """Build automation steps from data."""
    # TODO: Implement based on automation_data structure
    return []

async def _process_automation_job(job_id: int):
    """Process individual automation job."""
    # TODO: Implement job processing
    pass

async def _process_bulk_automation(
    job_ids: List[int],
    max_concurrent: int,
    notification_webhook: Optional[str]
):
    """Process multiple jobs with concurrency limit."""
    # TODO: Implement bulk processing with semaphore
    pass