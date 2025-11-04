"""
Enhanced Main FastAPI Application

Integra el motor robusto con la aplicación FastAPI existente
manteniendo 100% compatibilidad hacia atrás.

Para usar: renombrar main.py -> main_original.py y este archivo -> main.py
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal
import uvicorn

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("Variables de entorno cargadas desde .env")
except ImportError:
    logging.warning("python-dotenv no instalado, usando variables del sistema")

# Import original core functionality (mantener compatibilidad)
from core.mcp_handler import handle_mcp_request
from core.bank_reconciliation import suggest_bank_matches
from core.invoice_parser import parse_cfdi_xml, InvoiceParseError
from core.internal_db import (
    initialize_internal_database,
    list_bank_movements,
    record_bank_match_feedback,
    record_internal_expense,
    fetch_expense_records,
    fetch_expense_record,
    update_expense_record as db_update_expense_record,
    register_expense_invoice,
    mark_expense_invoiced as db_mark_expense_invoiced,
    mark_expense_without_invoice as db_mark_expense_without_invoice,
    register_user_account,
    get_company_demo_snapshot,
    fetch_candidate_expenses_for_invoice,
)
from config.config import config

# Import voice processing (optional - only if OpenAI is configured)
try:
    from core.voice_handler import process_voice_request, get_voice_handler
    VOICE_ENABLED = True
except ImportError as e:
    VOICE_ENABLED = False
    logging.getLogger(__name__).warning(f"Voice processing disabled: {e}")

# Enhanced automation imports
try:
    from modules.invoicing_agent.fastapi_integration import initialize_enhanced_api
    ENHANCED_AUTOMATION = True
except ImportError as e:
    ENHANCED_AUTOMATION = False
    logging.getLogger(__name__).warning(f"Enhanced automation disabled: {e}")

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enhanced lifespan with robust automation initialization
@asynccontextmanager
async def enhanced_lifespan(app: FastAPI):
    """Handle application lifespan with enhanced automation."""

    try:
        # Original initialization
        initialize_internal_database()
        logger.info("Internal account catalog initialised")

        # Enhanced automation initialization
        if ENHANCED_AUTOMATION:
            logger.info("🚀 Initializing enhanced automation system...")
            success = initialize_enhanced_api(app)
            if success:
                logger.info("✅ Enhanced automation system initialized")
            else:
                logger.warning("⚠️ Enhanced automation initialization failed - running in legacy mode")
        else:
            logger.info("🔄 Running in legacy mode (enhanced automation disabled)")

        yield

    except Exception as exc:
        logger.exception("Error initialising application: %s", exc)
        raise

# Initialize FastAPI app with enhanced capabilities
app = FastAPI(
    title="MCP Server - Enhanced Automation",
    description="Universal layer between AI agents and business systems with robust automation",
    version="1.1.0-enhanced",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=enhanced_lifespan,
)

# Mount static files for web interface
app.mount("/static", StaticFiles(directory="static"), name="static")

# Import and mount invoicing agent router (original)
try:
    from modules.invoicing_agent.api import router as invoicing_router
    app.include_router(invoicing_router)
    logger.info("Invoicing agent module loaded successfully")
except ImportError as e:
    logger.warning(f"Invoicing agent module not available: {e}")

# ALL ORIGINAL ENDPOINTS FROM main.py - MAINTAIN COMPATIBILITY
# ===================================================================

class MemoItem(BaseModel):
    content: str = Field(..., description="The content to remember")
    context: Optional[str] = Field(None, description="Additional context")

class InvoiceParseRequest(BaseModel):
    xml_content: str = Field(..., description="CFDI XML content to parse")

class ReconciliationRequest(BaseModel):
    expense_id: int = Field(..., description="Expense ID to reconcile")
    amount: float = Field(..., description="Transaction amount")
    transaction_date: str = Field(..., description="Transaction date")
    bank_description: str = Field(..., description="Bank transaction description")

class UserRegistration(BaseModel):
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User name")
    company_name: Optional[str] = Field(None, description="Company name")

class ExpenseCreate(BaseModel):
    amount: float = Field(..., description="Expense amount")
    concept: str = Field(..., description="Expense concept")
    category: Optional[str] = Field(None, description="Expense category")
    rfc: Optional[str] = Field(None, description="RFC for invoice matching")
    project_code: Optional[str] = Field(None, description="Project code")
    tags: List[str] = Field(default_factory=list, description="Expense tags")

class ExpenseUpdate(BaseModel):
    amount: Optional[float] = Field(None, description="Expense amount")
    concept: Optional[str] = Field(None, description="Expense concept")
    category: Optional[str] = Field(None, description="Expense category")
    rfc: Optional[str] = Field(None, description="RFC for invoice matching")
    project_code: Optional[str] = Field(None, description="Project code")
    tags: Optional[List[str]] = Field(None, description="Expense tags")

@app.get("/")
async def root():
    """Root endpoint - redirect to main interface."""
    return RedirectResponse(url="/static/index.html")

@app.post("/mcp")
async def mcp_endpoint(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Universal MCP (Model Context Protocol) endpoint.
    Handles various AI agent requests and routes them to appropriate handlers.
    """
    try:
        result = await handle_mcp_request(data)
        return result
    except Exception as e:
        logger.exception("Error in MCP request handling")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice")
async def voice_endpoint(
    audio: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    language: str = Form("es-MX")
) -> Dict[str, Any]:
    """
    Voice processing endpoint for expense recording.
    Accepts audio files and converts them to structured expense data.
    """
    if not VOICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Voice processing is not available. Please configure OpenAI API key."
        )

    try:
        result = await process_voice_request(audio, user_id, session_id, language)
        return result
    except Exception as e:
        logger.exception("Error in voice processing")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/parse-invoice")
async def parse_invoice_endpoint(request: InvoiceParseRequest) -> Dict[str, Any]:
    """Parse CFDI XML invoice and extract structured data."""
    try:
        result = parse_cfdi_xml(request.xml_content)
        return {"success": True, "data": result}
    except InvoiceParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error parsing invoice")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reconcile")
async def reconcile_expense(request: ReconciliationRequest) -> Dict[str, Any]:
    """Reconcile expense with bank transaction."""
    try:
        matches = suggest_bank_matches(
            request.expense_id,
            request.amount,
            request.transaction_date,
            request.bank_description
        )
        return {"success": True, "matches": matches}
    except Exception as e:
        logger.exception("Error in reconciliation")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bank-movements")
async def get_bank_movements(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """Get bank movements for reconciliation."""
    try:
        movements = list_bank_movements(start_date, end_date, limit)
        return {"success": True, "movements": movements}
    except Exception as e:
        logger.exception("Error fetching bank movements")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/register-user")
async def register_user_endpoint(user: UserRegistration) -> Dict[str, Any]:
    """Register a new user account."""
    try:
        user_id = register_user_account(user.email, user.name, user.company_name)
        return {"success": True, "user_id": user_id}
    except Exception as e:
        logger.exception("Error registering user")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/expenses")
async def create_expense_endpoint(expense: ExpenseCreate) -> Dict[str, Any]:
    """Create a new expense record."""
    try:
        expense_id = record_internal_expense(
            amount=expense.amount,
            concept=expense.concept,
            category=expense.category,
            rfc=expense.rfc,
            project_code=expense.project_code,
            tags=expense.tags
        )
        return {"success": True, "expense_id": expense_id}
    except Exception as e:
        logger.exception("Error creating expense")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/expenses")
async def get_expenses(
    limit: int = 100,
    offset: int = 0,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """Get expense records."""
    try:
        expenses = fetch_expense_records(limit, offset, category)
        return {"success": True, "expenses": expenses}
    except Exception as e:
        logger.exception("Error fetching expenses")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/expenses/{expense_id}")
async def get_expense(expense_id: int) -> Dict[str, Any]:
    """Get specific expense record."""
    try:
        expense = fetch_expense_record(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        return {"success": True, "expense": expense}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching expense")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/expenses/{expense_id}")
async def update_expense_endpoint(
    expense_id: int,
    expense: ExpenseUpdate
) -> Dict[str, Any]:
    """Update expense record."""
    try:
        # Filter out None values
        update_data = {k: v for k, v in expense.dict().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        success = db_update_expense_record(expense_id, **update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Expense not found")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating expense")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/company/{company_id}/demo-snapshot")
async def get_demo_snapshot(company_id: str) -> Dict[str, Any]:
    """Get demo snapshot for company."""
    try:
        snapshot = get_company_demo_snapshot(company_id)
        return {"success": True, "snapshot": snapshot}
    except Exception as e:
        logger.exception("Error getting demo snapshot")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "version": "1.1.0-enhanced",
        "features": {
            "voice_processing": VOICE_ENABLED,
            "enhanced_automation": ENHANCED_AUTOMATION
        }
    }

    # Add automation system health if available
    if ENHANCED_AUTOMATION:
        try:
            from modules.invoicing_agent.integration_layer import validate_automation_system
            automation_health = await validate_automation_system()
            health_status["automation_system"] = automation_health
        except Exception as e:
            health_status["automation_system"] = {"status": "error", "error": str(e)}

    return health_status

# Static file routes
@app.get("/static/advanced-ticket-dashboard.html", response_class=HTMLResponse)
async def advanced_ticket_dashboard():
    """Serve advanced ticket dashboard."""
    return FileResponse("static/advanced-ticket-dashboard.html")

@app.get("/static/automation-viewer.html", response_class=HTMLResponse)
async def automation_viewer():
    """Serve automation viewer."""
    return FileResponse("static/automation-viewer.html")

# Development server
if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")

    logger.info(f"🚀 Starting Enhanced MCP Server on {host}:{port}")
    logger.info(f"📊 Enhanced Automation: {ENHANCED_AUTOMATION}")
    logger.info(f"🎤 Voice Processing: {VOICE_ENABLED}")

    uvicorn.run(
        "main_enhanced:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )