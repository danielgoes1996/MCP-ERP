"""
MCP-Server API v1 - Invoicing Endpoints
Professional invoicing API with proper versioning
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invoicing-v1"])

# Response models
class TicketResponse(BaseModel):
    id: str
    status: str
    merchant_name: Optional[str] = None
    total: Optional[float] = None
    created_at: str
    processing_time: Optional[float] = None

class TicketListResponse(BaseModel):
    tickets: List[TicketResponse]
    total_count: int
    page: int
    page_size: int

class MerchantResponse(BaseModel):
    id: str
    name: str
    status: str
    supported_automation: bool

class ProcessingStatsResponse(BaseModel):
    total_tickets: int
    successful_automations: int
    manual_interventions: int
    success_rate: float
    avg_processing_time: float

# Request models
class TicketCreateRequest(BaseModel):
    merchant_name: Optional[str] = Field(None, description="Merchant name if known")
    auto_process: bool = Field(True, description="Enable automatic processing")
    priority: str = Field("normal", description="Processing priority: low, normal, high")

@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    merchant: Optional[str] = Query(None, description="Filter by merchant")
):
    """
    List tickets with pagination and filtering

    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)
    - **status**: Filter by ticket status
    - **merchant**: Filter by merchant name
    """
    try:
        # Import here to avoid circular imports
        from modules.invoicing_agent.api import get_tickets_list

        result = await get_tickets_list(
            page=page,
            page_size=page_size,
            status_filter=status,
            merchant_filter=merchant
        )

        return result
    except Exception as e:
        logger.error(f"Error listing tickets: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/tickets", response_model=TicketResponse)
async def create_ticket(
    file: UploadFile = File(..., description="Ticket image file"),
    request: TicketCreateRequest = Depends()
):
    """
    Create a new ticket from uploaded image

    - **file**: Image file (JPG, PNG, PDF supported)
    - **merchant_name**: Optional merchant name hint
    - **auto_process**: Enable automatic processing
    - **priority**: Processing priority level
    """
    try:
        # Import here to avoid circular imports
        from modules.invoicing_agent.api import process_ticket_upload

        result = await process_ticket_upload(
            file=file,
            merchant_name=request.merchant_name,
            auto_process=request.auto_process,
            priority=request.priority
        )

        return result
    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str):
    """
    Get ticket details by ID

    - **ticket_id**: Unique ticket identifier
    """
    try:
        from modules.invoicing_agent.api import get_ticket_by_id

        result = await get_ticket_by_id(ticket_id)
        if not result:
            raise HTTPException(status_code=404, detail="Ticket not found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/tickets/{ticket_id}/process")
async def process_ticket(ticket_id: str):
    """
    Manually trigger ticket processing

    - **ticket_id**: Unique ticket identifier
    """
    try:
        from modules.invoicing_agent.api import manual_process_ticket

        result = await manual_process_ticket(ticket_id)
        return result
    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/merchants", response_model=List[MerchantResponse])
async def list_merchants():
    """
    List all supported merchants
    """
    try:
        from modules.invoicing_agent.api import get_merchants_list

        result = await get_merchants_list()
        return result
    except Exception as e:
        logger.error(f"Error listing merchants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/stats", response_model=ProcessingStatsResponse)
async def get_processing_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """
    Get processing statistics

    - **days**: Number of days to include in analysis (max 365)
    """
    try:
        from modules.invoicing_agent.api import get_processing_statistics

        result = await get_processing_statistics(days)
        return result
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def health_check():
    """
    API health check endpoint
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "api": "invoicing-v1"
    }