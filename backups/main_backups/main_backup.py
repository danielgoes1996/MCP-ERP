"""
Main FastAPI application for MCP Server
This is the entry point for the MCP (Model Context Protocol) Server that acts as
a universal layer between AI agents and business systems.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal
import uvicorn
import logging
import tempfile
import os
from datetime import datetime, timedelta
import math
import re

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("Variables de entorno cargadas desde .env")
except ImportError:
    logging.warning("python-dotenv no instalado, usando variables del sistema")

# Import our core MCP handler and reconciliation helpers
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

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan to bootstrap the internal catalog."""

    try:
        initialize_internal_database()
        logger.info("Internal account catalog initialised")
        yield
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Error initialising internal database: %s", exc)
        raise


app = FastAPI(
    title="MCP Server",
    description="Universal layer between AI agents and business systems",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    lifespan=lifespan,
)

# Mount static files for web interface
app.mount("/static", StaticFiles(directory="static"), name="static")

# Import and mount invoicing agent router
try:
    from modules.invoicing_agent.api import router as invoicing_router
    app.include_router(invoicing_router)
    logger.info("Invoicing agent module loaded successfully")
except ImportError as e:
    logger.warning(f"Invoicing agent module not available: {e}")

# Import and mount authentication router
try:
    from api.auth_api import router as auth_router
    app.include_router(auth_router)
    logger.info("✅ Authentication system enabled")
except ImportError as e:
    logger.warning(f"Authentication module not available: {e}")

# Import and mount advanced invoicing API
try:
    from api.advanced_invoicing_api import router as advanced_invoicing_router
    app.include_router(advanced_invoicing_router)
    logger.info("Advanced invoicing API loaded successfully")
except ImportError as e:
    logger.warning(f"Advanced invoicing API not available: {e}")

# Import and mount client management API
try:
    from api.client_management_api import router as client_management_router
    app.include_router(client_management_router)
    logger.info("Client management API loaded successfully")
except ImportError as e:
    logger.warning(f"Client management API not available: {e}")

# Import all API models from centralized location
from core.api_models import *
logger.info("✅ API models loaded from core.api_models")

# Legacy model definitions below will be removed in next phase
# Keeping temporarily for compatibility

# All models are now imported from core.api_models
# The following class definitions will be removed in the next phase

# TODO: Remove all legacy model definitions below
# They are now imported from core.api_models
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BankSuggestionExpense(BaseModel):
    expense_id: str
    amount: float
    currency: str = "MXN"
    description: Optional[str] = None
    date: Optional[str] = None
    provider_name: Optional[str] = None
    paid_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    company_id: str = "default"


class BankSuggestionResponse(BaseModel):
    suggestions: List[Dict[str, Any]]


class BankReconciliationFeedback(BaseModel):
    expense_id: str
    movement_id: str
    confidence: float
    decision: str
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    company_id: str = "default"


class ExpenseCreate(BaseModel):
    # Campos básicos de gasto
    descripcion: str
    monto_total: float
    fecha_gasto: Optional[str] = None
    categoria: Optional[str] = None
    company_id: str = "default"

    # Información del proveedor
    proveedor: Optional[Dict[str, Any]] = None
    rfc: Optional[str] = None

    # Información fiscal
    tax_info: Optional[Dict[str, Any]] = None
    asientos_contables: Optional[List[Dict[str, Any]]] = None

    # Estados del workflow
    workflow_status: str = "draft"  # draft, pending_invoice, invoiced, closed
    estado_factura: str = "pendiente"  # pendiente, facturado, sin_factura
    estado_conciliacion: str = "pendiente"  # pendiente, conciliado, excluido

    # Información de pago
    forma_pago: Optional[str] = None
    paid_by: str = "company_account"
    will_have_cfdi: bool = True

    # Movimientos bancarios asociados
    movimientos_bancarios: Optional[List[Dict[str, Any]]] = None

    # Metadatos adicionales
    metadata: Optional[Dict[str, Any]] = None
    is_advance: bool = False
    is_ppd: bool = False
    asset_class: Optional[str] = None
    payment_terms: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: int
    descripcion: str
    monto_total: float
    fecha_gasto: Optional[str] = None
    categoria: Optional[str] = None
    company_id: str

    # Información del proveedor
    proveedor: Optional[Dict[str, Any]] = None
    rfc: Optional[str] = None

    # Información fiscal
    tax_info: Optional[Dict[str, Any]] = None
    asientos_contables: Optional[List[Dict[str, Any]]] = None
    accounting: Optional[Dict[str, Any]] = None

    # Estados del workflow
    workflow_status: str
    estado_factura: str
    estado_conciliacion: str

    # Información de pago
    forma_pago: Optional[str] = None
    paid_by: str
    will_have_cfdi: bool

    # Movimientos bancarios asociados
    movimientos_bancarios: Optional[List[Dict[str, Any]]] = None
    payments: Optional[List[Dict[str, Any]]] = None
    total_pagado: float = 0.0
    fecha_ultimo_pago: Optional[str] = None

    # Metadatos
    metadata: Optional[Dict[str, Any]] = None
    is_advance: bool
    is_ppd: bool
    asset_class: Optional[str] = None
    payment_terms: Optional[str] = None
    scenario: Optional[str] = None
    scenario_label: Optional[str] = None
    asiento_definitivo: Optional[bool] = None
    created_at: str
    updated_at: str


class ExpenseInvoicePayload(BaseModel):
    uuid: Optional[str] = None
    folio: Optional[str] = None
    url: Optional[str] = None
    issued_at: Optional[str] = None
    status: Optional[str] = None
    raw_xml: Optional[str] = None
    actor: Optional[str] = None


class ExpenseActionRequest(BaseModel):
    actor: Optional[str] = None


class OnboardingRequest(BaseModel):
    method: Literal["whatsapp", "email"]
    identifier: str
    full_name: Optional[str] = None


class DemoSnapshot(BaseModel):
    total_expenses: int
    total_amount: float
    invoice_breakdown: Dict[str, int] = Field(default_factory=dict)
    last_expense_date: Optional[str] = None


class OnboardingResponse(BaseModel):
    company_id: str
    user_id: int
    identifier: str
    identifier_type: str
    full_name: Optional[str] = None
    already_exists: bool
    demo_snapshot: DemoSnapshot
    demo_expenses: List[ExpenseResponse] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)


def _build_expense_response(record: Dict[str, Any]) -> ExpenseResponse:
    metadata = dict(record.get("metadata") or {})
    provider = metadata.get("proveedor")
    provider_name = record.get("provider_name")
    provider_rfc = record.get("provider_rfc")
    metadata_rfc = metadata.get("rfc")

    if not provider and provider_name:
        provider = {"nombre": provider_name}
        if provider_rfc:
            provider["rfc"] = provider_rfc

    tax_info = metadata.get("tax_info") or record.get("tax_metadata")
    asientos = metadata.get("asientos_contables")
    movimientos = metadata.get("movimientos_bancarios")

    for key in [
        "proveedor",
        "rfc",
        "tax_info",
        "asientos_contables",
        "movimientos_bancarios",
        "workflow_status",
        "estado_factura",
        "estado_conciliacion",
        "forma_pago",
        "paid_by",
        "will_have_cfdi",
        "categoria",
        "fecha_gasto",
        "company_id",
    ]:
        metadata.pop(key, None)

    return ExpenseResponse(
        id=record["id"],
        descripcion=record["description"],
        monto_total=record["amount"],
        fecha_gasto=record.get("expense_date"),
        categoria=record.get("category"),
        proveedor=provider,
        rfc=provider_rfc or metadata_rfc,
        tax_info=tax_info,
        asientos_contables=asientos,
        workflow_status=record.get("workflow_status", "draft"),
        estado_factura=record.get("invoice_status", "pendiente"),
        estado_conciliacion=record.get("bank_status", "pendiente"),
        forma_pago=record.get("payment_method"),
        paid_by=record.get("paid_by", "company_account"),
        will_have_cfdi=bool(record.get("will_have_cfdi", True)),
        movimientos_bancarios=movimientos,
        metadata=metadata or None,
        company_id=record.get("company_id", "default"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


def _parse_iso_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None


def _score_invoice_candidate(
    *,
    invoice_total: float,
    invoice_date: Optional[datetime],
    invoice_rfc: Optional[str],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    amount_diff = abs(candidate["amount"] - invoice_total)
    score = 0

    if math.isclose(candidate["amount"], invoice_total, rel_tol=0.0, abs_tol=0.01):
        score += 70
    elif amount_diff <= 1.0:
        score += 50
    else:
        # Too large difference, unlikely to match
        score -= 20

    days_diff: Optional[int] = None
    candidate_date = _parse_iso_date(candidate.get("expense_date"))
    if invoice_date and candidate_date:
        days_diff = abs((candidate_date.date() - invoice_date.date()).days)
        if days_diff == 0:
            score += 25
        elif days_diff <= 3:
            score += 15
        elif days_diff <= 7:
            score += 5
        else:
            score -= 5

    candidate_rfc = (candidate.get("provider_rfc") or "").strip().upper()
    invoice_rfc_normalized = (invoice_rfc or "").strip().upper()
    if invoice_rfc_normalized and candidate_rfc:
        if candidate_rfc == invoice_rfc_normalized:
            score += 20
        else:
            score -= 10

    return {
        "expense_id": candidate["id"],
        "descripcion": candidate["descripcion"],
        "monto_total": candidate["amount"],
        "fecha_gasto": candidate.get("expense_date"),
        "provider_name": candidate.get("provider_name"),
        "provider_rfc": candidate_rfc or None,
        "invoice_status": candidate.get("invoice_status"),
        "bank_status": candidate.get("bank_status"),
        "match_score": score,
        "amount_diff": amount_diff,
        "days_diff": days_diff,
    }


def _match_invoice_to_expense(
    *,
    company_id: str,
    invoice: "InvoiceMatchInput",
    global_auto_mark: bool,
) -> "InvoiceMatchResult":
    filename = invoice.filename
    if invoice.total is None:
        return InvoiceMatchResult(
            filename=filename,
            uuid=invoice.uuid,
            status="error",
            message="El CFDI no contiene un total válido",
        )

    candidates = fetch_candidate_expenses_for_invoice(company_id)
    invoice_date = _parse_iso_date(invoice.issued_at)
    scored_candidates = [
        _score_invoice_candidate(
            invoice_total=invoice.total,
            invoice_date=invoice_date,
            invoice_rfc=invoice.rfc_emisor,
            candidate=candidate,
        )
        for candidate in candidates
    ]

    scored_candidates = [c for c in scored_candidates if c["match_score"] > 0]
    scored_candidates.sort(key=lambda item: item["match_score"], reverse=True)
    logger.debug(
        "Invoice bulk-match: %s candidates -> %s",
        invoice.filename or invoice.uuid,
        scored_candidates,
    )

    result = InvoiceMatchResult(
        filename=filename,
        uuid=invoice.uuid,
        status="no_match",
        candidates=[InvoiceMatchCandidate(**candidate) for candidate in scored_candidates[:3]],
    )

    if not scored_candidates:
        result.message = "No se encontraron gastos con monto compatible"
        return result

    top_score = scored_candidates[0]["match_score"]
    runner_up = scored_candidates[1]["match_score"] if len(scored_candidates) > 1 else None

    high_confidence = top_score >= 80 and (runner_up is None or (top_score - runner_up) >= 15)
    moderate_confidence = top_score >= 65 and (runner_up is None or (top_score - runner_up) >= 10)

    if not (high_confidence or moderate_confidence):
        result.status = "needs_review"
        result.message = "Se encontraron candidatos pero requiere revisión manual"
        return result

    expense_id = scored_candidates[0]["expense_id"]
    try:
        record = register_expense_invoice(
            expense_id,
            uuid=invoice.uuid,
            folio=invoice.folio,
            url=invoice.url,
            issued_at=invoice.issued_at,
            status="registrada",
            raw_xml=invoice.raw_xml,
            actor="bulk_matcher",
        )
        if not record:
            raise ValueError("Gasto no encontrado al registrar la factura")

        if (invoice.auto_mark_invoiced and global_auto_mark) or high_confidence:
            record = db_mark_expense_invoiced(expense_id, actor="bulk_matcher") or record

        expense_response = _build_expense_response(record)
        result.status = "linked"
        result.expense = expense_response
        result.message = "Factura conciliada con el gasto"
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Error conciliando factura masiva: %s", exc)
        result.status = "error"
        result.message = f"Error registrando la factura: {exc}"

    return result
class InvoiceParseResponse(BaseModel):
    subtotal: float
    total: float
    currency: str = "MXN"
    taxes: List[Dict[str, Any]] = Field(default_factory=list)
    iva_amount: float = 0.0
    other_taxes: float = 0.0
    emitter: Optional[Dict[str, Any]] = None
    receiver: Optional[Dict[str, Any]] = None
    uuid: Optional[str] = None


class DuplicateCheckRequest(BaseModel):
    new_expense: ExpenseCreate
    check_existing: bool = True


class DuplicateCheckResponse(BaseModel):
    has_duplicates: bool
    total_found: int
    risk_level: str  # 'none', 'low', 'medium', 'high'
    recommendation: str  # 'proceed', 'warn', 'review', 'block'
    duplicates: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


class CategoryPredictionRequest(BaseModel):
    description: str
    amount: Optional[float] = None
    provider_name: Optional[str] = None
    include_history: bool = True
    company_id: str = "default"


class CategoryPredictionResponse(BaseModel):
    categoria_sugerida: str
    confianza: float
    razonamiento: str
    alternativas: List[Dict[str, Any]] = Field(default_factory=list)
    metodo_prediccion: str
    sugerencias_autocompletado: List[Dict[str, Any]] = Field(default_factory=list)


class InvoiceMatchInput(BaseModel):
    filename: Optional[str] = None
    uuid: Optional[str] = None
    total: float
    issued_at: Optional[str] = None
    rfc_emisor: Optional[str] = None
    folio: Optional[str] = None
    raw_xml: Optional[str] = None
    url: Optional[str] = None
    auto_mark_invoiced: bool = True


class InvoiceMatchCandidate(BaseModel):
    expense_id: int
    descripcion: str
    monto_total: float
    fecha_gasto: Optional[str]
    provider_name: Optional[str]
    provider_rfc: Optional[str] = None
    invoice_status: str
    bank_status: str
    match_score: int
    amount_diff: float
    days_diff: Optional[int] = None


class InvoiceMatchResult(BaseModel):
    filename: Optional[str] = None
    uuid: Optional[str] = None
    status: Literal["linked", "needs_review", "no_match", "error", "unsupported"]
    message: Optional[str] = None
    expense: Optional[ExpenseResponse] = None
    candidates: List[InvoiceMatchCandidate] = Field(default_factory=list)


class BulkInvoiceMatchRequest(BaseModel):
    company_id: str = "default"
    invoices: List[InvoiceMatchInput]
    auto_mark_invoiced: bool = True


class BulkInvoiceMatchResponse(BaseModel):
    company_id: str
    processed: int
    results: List[InvoiceMatchResult]


@app.get("/")
async def root():
    """
    Root endpoint - redirects to Advanced Ticket Dashboard.

    Returns:
        RedirectResponse: Redirect to the advanced ticket dashboard
    """
    logger.info("Root accessed - redirecting to Advanced Ticket Dashboard")
    return RedirectResponse(url="/advanced-ticket-dashboard.html", status_code=302)


@app.get("/onboarding")
async def onboarding_page() -> FileResponse:
    """Serve the onboarding experience."""

    logger.info("Onboarding interface accessed")
    return FileResponse("static/onboarding.html")


@app.get("/voice-expenses")
async def voice_expenses():
    """
    Voice expenses endpoint - serves the new React voice interface.

    Returns:
        HTMLResponse: The voice-enabled expense registration interface
    """
    logger.info("Voice expenses interface accessed")
    return FileResponse("static/voice-expenses.html")


@app.get("/advanced-ticket-dashboard.html")
async def advanced_ticket_dashboard():
    """
    Advanced ticket dashboard endpoint - serves the invoicing agent dashboard.

    Returns:
        HTMLResponse: The advanced ticket dashboard interface
    """
    logger.info("Advanced ticket dashboard interface accessed")
    return FileResponse("static/advanced-ticket-dashboard.html")


@app.get("/dashboard")
async def dashboard_redirect():
    """
    Legacy dashboard redirect - redirects to Advanced Ticket Dashboard.

    Returns:
        RedirectResponse: Redirect to the advanced ticket dashboard
    """
    logger.info("Legacy dashboard accessed - redirecting to Advanced Ticket Dashboard")
    return RedirectResponse(url="/advanced-ticket-dashboard.html", status_code=302)


@app.post("/simple_expense")
async def create_simple_expense(request: dict):
    """
    Endpoint simplificado para crear gastos desde la nueva interfaz de voz.
    Evita la complejidad de los modelos y usa mapeo directo.

    Args:
        request: Datos del gasto en formato simple

    Returns:
        JSONResponse: Resultado de la creación
    """
    try:
        logger.info("Creating simple expense from voice interface")

        # Usar el OdooFieldMapper directamente
        from core.odoo_field_mapper import OdooFieldMapper

        mapper = OdooFieldMapper()

        # Conectar a Odoo
        if not mapper.connect_to_odoo():
            raise Exception("No se pudo conectar a Odoo")

        # Mapear y crear el gasto
        result = mapper.create_expense_in_odoo(request)

        logger.info(f"Simple expense creation result: {result}")

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error creating simple expense: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error interno creando gasto: {str(e)}"
            }
        )


@app.get("/api/status")
async def api_status():
    """
    API status endpoint - health check for the MCP server.

    Returns:
        dict: Status message indicating server is running
    """
    logger.info("API status endpoint accessed")
    return {"status": "MCP Server running"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        dict: Detailed health status
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "server": "MCP Server",
        "uptime": "active"
    }


@app.post("/mcp", response_model=MCPResponse)
async def mcp_endpoint(request: MCPRequest):
    """
    Main MCP endpoint that receives method calls and routes them to handlers.

    Args:
        request (MCPRequest): The MCP request containing method and parameters

    Returns:
        MCPResponse: The response from the MCP handler

    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(f"MCP request received - Method: {request.method}, Params: {request.params}")

        # Call the core MCP handler
        result = handle_mcp_request(request.method, request.params)

        # Check if the result contains an error
        if "error" in result:
            logger.warning(f"MCP method error: {result['error']}")
            return MCPResponse(
                success=False,
                error=result["error"]
            )

        logger.info(f"MCP request processed successfully - Method: {request.method}")
        return MCPResponse(
            success=True,
            data=result
        )

    except Exception as e:
        logger.error(f"Unexpected error processing MCP request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/voice_mcp")
async def voice_mcp_endpoint(file: UploadFile = File(...)):
    """
    Voice-enabled MCP endpoint that processes audio input and returns both JSON and audio responses.

    Flow:
    1. Transcribe uploaded audio file to text using OpenAI Whisper
    2. Process the text through MCP handler
    3. Convert MCP response to speech using OpenAI TTS
    4. Return JSON response with transcript, MCP result, and audio file

    Args:
        file (UploadFile): Audio file (MP3, WAV, etc.)

    Returns:
        JSONResponse: {
            "success": bool,
            "transcript": str,
            "mcp_response": dict,
            "response_text": str,
            "audio_file_url": str,
            "error": str (if failed)
        }
    """
    if not VOICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Voice processing is disabled. Please configure OPENAI_API_KEY and install required dependencies."
        )

    try:
        logger.info(f"Voice MCP request received - File: {file.filename}, Content-Type: {file.content_type}")

        # Validate file type
        if not file.content_type or not file.content_type.startswith('audio/'):
            logger.warning(f"Invalid file type: {file.content_type}")
            # Allow anyway as some browsers may not set correct content type

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "audio.mp3")[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_audio_path = tmp_file.name

        logger.info(f"Audio file saved to: {tmp_audio_path}")

        # Process voice request through the pipeline
        def mcp_handler_wrapper(mcp_request):
            """Wrapper to handle MCP requests from voice processing"""
            method = mcp_request.get("method", "unknown")
            params = mcp_request.get("params", {})
            return handle_mcp_request(method, params)

        # Process through voice handler
        result = process_voice_request(tmp_audio_path, mcp_handler_wrapper)

        # Clean up temporary file
        try:
            os.unlink(tmp_audio_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")

        if not result["success"]:
            logger.error(f"Voice processing failed: {result.get('error')}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result.get("error", "Voice processing failed"),
                    "transcript": "",
                    "mcp_response": {},
                    "audio_file_url": ""
                }
            )

        # Prepare response
        response_data = {
            "success": True,
            "transcript": result.get("transcript", ""),
            "mcp_response": result.get("mcp_response", {}),
            "response_text": result.get("response_text", ""),
            "tts_success": result.get("tts_success", False),
            "audio_file_url": f"/audio/{os.path.basename(result.get('audio_file', ''))}" if result.get('audio_file') else ""
        }

        # Store audio file path for serving
        if result.get('audio_file'):
            # Store reference for serving the file
            app.state.audio_files = getattr(app.state, 'audio_files', {})
            audio_filename = os.path.basename(result['audio_file'])
            app.state.audio_files[audio_filename] = result['audio_file']

        logger.info(f"Voice MCP processed successfully - Transcript: {result.get('transcript', '')[:100]}...")
        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in voice MCP endpoint: {str(e)}")
        # Cleanup any temp files
        if 'tmp_audio_path' in locals():
            try:
                os.unlink(tmp_audio_path)
            except:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/audio/{filename}")
async def serve_audio_file(filename: str):
    """
    Serve generated audio files.

    Args:
        filename (str): Audio file name

    Returns:
        FileResponse: Audio file
    """
    if not VOICE_ENABLED:
        raise HTTPException(status_code=503, detail="Voice processing disabled")

    try:
        # Get stored audio file path
        audio_files = getattr(app.state, 'audio_files', {})
        if filename not in audio_files:
            raise HTTPException(status_code=404, detail="Audio file not found")

        file_path = audio_files[filename]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Audio file not found on disk")

        return FileResponse(
            path=file_path,
            media_type="audio/mpeg",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving audio file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error serving audio file")


@app.post("/voice_mcp_enhanced")
async def voice_mcp_enhanced_endpoint(file: UploadFile = File(...)):
    """
    Enhanced voice-enabled MCP endpoint with field validation and completion forms.

    Flow:
    1. Transcribe audio to text using OpenAI Whisper
    2. Enhance with LLM for better descriptions
    3. Validate completeness of fields
    4. Return completion form if fields are missing
    5. Allow user to complete and create expense

    Args:
        file (UploadFile): Audio file (MP3, WAV, etc.)

    Returns:
        JSONResponse: Enhanced response with validation and form
    """
    if not VOICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Voice processing is disabled. Please configure OPENAI_API_KEY and install required dependencies."
        )

    try:
        logger.info(f"Enhanced Voice MCP request received - File: {file.filename}")

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "audio.mp3")[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_audio_path = tmp_file.name

        # Step 1: Transcribe audio
        from core.voice_handler import get_voice_handler
        voice_handler = get_voice_handler()

        transcription_result = voice_handler.transcribe_audio(tmp_audio_path)

        # Clean up temp file
        try:
            os.unlink(tmp_audio_path)
        except:
            pass

        if not transcription_result["success"]:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": transcription_result.get("error", "Transcription failed"),
                    "stage": "transcription"
                }
            )

        transcript = transcription_result["transcript"]
        logger.info(f"Transcribed: {transcript}")

        # Step 2: Enhance with LLM
        try:
            from core.expense_enhancer import enhance_expense_from_voice
            # Extract amount from transcript for enhancement
            import re
            amount_match = re.search(r'(\d+(?:\.\d+)?)', transcript)
            amount = float(amount_match.group(1)) if amount_match else 100.0

            enhanced_data = enhance_expense_from_voice(transcript, amount)
        except Exception as e:
            logger.error(f"Error in LLM enhancement: {e}")
            enhanced_data = {
                'name': transcript,
                'total_amount': amount,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'payment_mode': 'own_account'
            }

        # Step 3: Validate completeness
        from core.expense_validator import expense_validator
        validation_result = expense_validator.validate_expense_data(enhanced_data)

        # Step 4: Generate completion form if needed
        completion_form = None
        if not validation_result['is_complete'] or validation_result['missing_critical']:
            completion_form = expense_validator.create_completion_form(enhanced_data, validation_result)

        response_data = {
            "success": True,
            "transcript": transcript,
            "enhanced_data": enhanced_data,
            "validation": validation_result,
            "completion_form": completion_form,
            "can_create_directly": validation_result['can_create'],
            "completeness_score": validation_result['completeness_score']
        }

        # If the expense is complete enough, offer direct creation
        if validation_result['can_create'] and validation_result['completeness_score'] >= 60:
            response_data['direct_creation_available'] = True

        logger.info(f"Enhanced voice processing completed - Score: {validation_result['completeness_score']}%")
        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Error in enhanced voice MCP endpoint: {str(e)}")
        if 'tmp_audio_path' in locals():
            try:
                os.unlink(tmp_audio_path)
            except:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


class CompleteExpenseRequest(BaseModel):
    """
    Pydantic model for complete expense request structure.
    """
    enhanced_data: Dict[str, Any]
    user_completions: Dict[str, Any]


@app.post("/complete_expense")
async def complete_expense_endpoint(request: CompleteExpenseRequest):
    """
    Complete and create expense with user-provided additional fields.

    Args:
        request: CompleteExpenseRequest with enhanced_data and user_completions

    Returns:
        JSONResponse: Result of expense creation in Odoo
    """
    try:
        logger.info("Completing expense with user data")

        # Merge enhanced data with user completions
        enhanced_data = request.enhanced_data
        user_completions = request.user_completions

        # Merge data
        final_expense_data = {**enhanced_data, **user_completions}

        # Create in Odoo using the mapper
        from core.odoo_field_mapper import get_odoo_mapper
        mapper = get_odoo_mapper()

        # Map to Odoo fields
        mapped_data, missing_fields = mapper.map_expense_data(final_expense_data)

        if missing_fields:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Critical fields still missing",
                    "missing_fields": missing_fields
                }
            )

        # Create in Odoo
        creation_result = mapper.create_expense_in_odoo(mapped_data)

        if creation_result['success']:
            # Generate TTS response
            if VOICE_ENABLED:
                try:
                    from core.voice_handler import text_to_speech
                    response_text = f"Gasto creado exitosamente con ID {creation_result['expense_id']}. Monto: ${final_expense_data.get('total_amount', 0)} pesos."
                    tts_result = text_to_speech(response_text)

                    if tts_result['success']:
                        # Store audio file for serving
                        app.state.audio_files = getattr(app.state, 'audio_files', {})
                        audio_filename = os.path.basename(tts_result['audio_file'])
                        app.state.audio_files[audio_filename] = tts_result['audio_file']
                        creation_result['audio_file_url'] = f"/audio/{audio_filename}"
                except Exception as e:
                    logger.warning(f"TTS generation failed: {e}")

        return JSONResponse(content=creation_result)

    except Exception as e:
        logger.error(f"Error completing expense: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating expense: {str(e)}"
        )


@app.post("/ocr/parse")
async def ocr_parse(file: UploadFile = File(...), lang: str = Form("spa+eng")):
    """
    OCR endpoint - Parse image/PDF and extract structured fields.

    Args:
        file: Image or PDF file
        lang: Tesseract language (default: spa+eng)

    Returns:
        JSONResponse: Extracted text and fields
    """
    try:
        logger.info(f"OCR parse request - File: {file.filename}, Size: {file.size}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        # Read file content
        content = await file.read()

        # Call Node.js OCR service
        import httpx

        files = {"file": (file.filename, content, file.content_type)}
        data = {"lang": lang}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:3001/ocr/parse",
                files=files,
                data=data,
                timeout=30.0
            )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"OCR parse successful - Confidence: {result.get('confidence', 0)}")
            return JSONResponse(content=result)
        else:
            error_msg = f"OCR service error: {response.status_code}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    except Exception as e:
        logger.error(f"Error in OCR parse: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


@app.post("/ocr/intake")
async def ocr_intake(
    file: UploadFile = File(...),
    paid_by: str = Form(...),
    will_have_cfdi: str = Form(...)
):
    """
    OCR intake endpoint - Create expense directly from OCR.

    Args:
        file: Image or PDF file
        paid_by: Payment method (company_account/own_account)
        will_have_cfdi: Whether CFDI is expected (true/false)

    Returns:
        JSONResponse: Created intake with route decision
    """
    try:
        logger.info(f"OCR intake request - File: {file.filename}, paid_by: {paid_by}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        # Read file content
        content = await file.read()

        # Use our Python OCR service directly
        import base64
        import time
        base64_image = base64.b64encode(content).decode('utf-8')

        # Use our Python OCR service
        from core.advanced_ocr_service import AdvancedOCRService
        ocr_service = AdvancedOCRService()

        ocr_result = await ocr_service.extract_text_intelligent(base64_image, "ticket")

        # Extract fields from OCR text
        if ocr_result.text:
            extracted_fields = ocr_service.extract_fields_from_lines(ocr_result.text.split('\n'))
        else:
            extracted_fields = {}

        # Create response in expected format
        intake_id = f"intake_{int(time.time())}"
        result = {
            "intake_id": intake_id,
            "message": "OCR procesado exitosamente",
            "route": "expense_creation",
            "confidence": ocr_result.confidence,
            "ocr_confidence": ocr_result.confidence,
            "fields": extracted_fields,
            "raw_text": ocr_result.text,
            "backend": ocr_result.backend.value,
            "processing_time_ms": ocr_result.processing_time_ms
        }

        logger.info(f"OCR intake successful - ID: {intake_id}, Fields: {list(extracted_fields.keys())}")
        return JSONResponse(content=result, status_code=201)

    except Exception as e:
        logger.error(f"Error in OCR intake: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR intake failed: {str(e)}")


@app.get("/ocr/stats")
async def ocr_stats():
    """
    OCR stats endpoint - Get OCR service statistics.

    Returns:
        JSONResponse: OCR service stats
    """
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:3001/ocr/stats", timeout=10.0)

        if response.status_code == 200:
            result = response.json()
            logger.info("OCR stats retrieved successfully")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=500, detail="OCR stats service error")

    except Exception as e:
        logger.error(f"Error getting OCR stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR stats failed: {str(e)}")


@app.get("/methods")
async def list_supported_methods():
    """
    List all supported MCP methods.

    Returns:
        dict: List of supported methods with descriptions
    """
    supported_methods = {
        "get_inventory": {
            "description": "Get inventory information for a product",
            "parameters": ["product_id", "location (optional)"]
        },
        "create_order": {
            "description": "Create a new order",
            "parameters": ["customer", "items"]
        },
        "create_expense": {
            "description": "Create a new expense record",
            "parameters": ["employee", "amount", "description"]
        },
        "ocr_parse": {
            "description": "Parse image/PDF with OCR and extract fields (POST /ocr/parse)",
            "parameters": ["file (multipart/form-data)", "lang (optional)"]
        },
        "ocr_intake": {
            "description": "Create expense directly from OCR (POST /ocr/intake)",
            "parameters": ["file (multipart/form-data)", "paid_by", "will_have_cfdi"]
        },
        "ocr_stats": {
            "description": "Get OCR service statistics (GET /ocr/stats)",
            "parameters": []
        },
        "bank_reconciliation_suggestions": {
            "description": "Sugerencias IA de conciliación bancaria (POST /bank_reconciliation/suggestions)",
            "parameters": ["expense_payload"]
        },
        "bank_reconciliation_feedback": {
            "description": "Registrar feedback de conciliación bancaria (POST /bank_reconciliation/feedback)",
            "parameters": ["expense_id", "movement_id", "confidence", "decision"]
        },
        "invoice_parse": {
            "description": "Analizar CFDI XML para extraer impuestos (POST /invoices/parse)",
            "parameters": ["file (multipart/form-data)"]
        },
        "invoicing_upload_ticket": {
            "description": "Subir ticket para facturación automática (POST /invoicing/tickets)",
            "parameters": ["file (optional)", "text_content (optional)", "user_id (optional)"]
        },
        "invoicing_ticket_status": {
            "description": "Ver estado de un ticket (GET /invoicing/tickets/{id})",
            "parameters": ["ticket_id"]
        },
        "invoicing_bulk_upload": {
            "description": "Carga masiva de tickets (POST /invoicing/bulk-match)",
            "parameters": ["tickets_list", "auto_process"]
        },
        "whatsapp_webhook": {
            "description": "Webhook para mensajes WhatsApp (POST /invoicing/webhooks/whatsapp)",
            "parameters": ["message_data"]
        },
        "invoicing_merchants": {
            "description": "Gestión de merchants para facturación (GET/POST /invoicing/merchants)",
            "parameters": ["merchant_data (for POST)"]
        },
        "invoicing_jobs": {
            "description": "Ver jobs de procesamiento (GET /invoicing/jobs)",
            "parameters": ["company_id"]
        }
    }

    # Add voice endpoints if enabled
    voice_endpoints = {}
    if VOICE_ENABLED:
        voice_endpoints = {
            "voice_mcp": {
                "description": "Basic voice-enabled MCP endpoint (POST /voice_mcp)",
                "parameters": ["audio_file (multipart/form-data)"],
                "returns": "JSON response + audio file"
            },
            "voice_mcp_enhanced": {
                "description": "Enhanced voice MCP with field validation (POST /voice_mcp_enhanced)",
                "parameters": ["audio_file (multipart/form-data)"],
                "returns": "JSON response + completion form + validation"
            },
            "complete_expense": {
                "description": "Complete expense creation with additional fields (POST /complete_expense)",
                "parameters": ["enhanced_data", "user_completions"],
                "returns": "Expense creation result"
            },
            "audio_file": {
                "description": "Serve generated audio files (GET /audio/{filename})",
                "parameters": ["filename"],
                "returns": "Audio file (MP3)"
            }
        }

    all_methods = {**supported_methods, **voice_endpoints}

    return {
        "supported_methods": all_methods,
        "total_methods": len(all_methods),
        "voice_enabled": VOICE_ENABLED
    }


@app.get("/bank_reconciliation/movements")
async def get_bank_movements(
    limit: int = 100,
    include_matched: bool = True,
    company_id: str = "default",
) -> Dict[str, Any]:
    """Return bank movements stored in the internal database."""

    movements = list_bank_movements(
        limit=limit,
        include_matched=include_matched,
        company_id=company_id,
    )
    return {"movements": movements, "count": len(movements)}


@app.post("/bank_reconciliation/suggestions", response_model=BankSuggestionResponse)
async def bank_reconciliation_suggestions(expense: BankSuggestionExpense) -> BankSuggestionResponse:
    """Return a ranked list of possible bank movements for an expense."""

    try:
        logger.debug("Generating bank reconciliation suggestions for %s", expense.expense_id)
        suggestions = suggest_bank_matches(
            expense.model_dump(),
            company_id=expense.company_id,
        )
        return BankSuggestionResponse(suggestions=suggestions)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Bank reconciliation suggestion error: %s", exc)
        raise HTTPException(status_code=500, detail="Error generando sugerencias de conciliación bancaria")


@app.post("/bank_reconciliation/feedback")
async def bank_reconciliation_feedback(feedback: BankReconciliationFeedback) -> Dict[str, Any]:
    """Store user feedback about a bank reconciliation suggestion."""

    decision = feedback.decision.lower()
    if decision not in {"accepted", "rejected", "manual"}:
        raise HTTPException(status_code=400, detail="Decisión inválida. Usa accepted, rejected o manual.")

    record_bank_match_feedback(
        expense_id=feedback.expense_id,
        movement_id=feedback.movement_id,
        confidence=feedback.confidence,
        decision=decision,
        notes=feedback.notes,
        metadata=feedback.metadata,
        company_id=feedback.company_id,
    )

    return {"success": True}


def _validate_onboarding_identifier(payload: OnboardingRequest) -> Dict[str, str]:
    identifier = payload.identifier.strip()
    if payload.method == "whatsapp":
        digits = re.sub(r"\D", "", identifier)
        if len(digits) < 10 or len(digits) > 15:
            raise HTTPException(status_code=400, detail="Número de WhatsApp inválido (usa 10 a 15 dígitos)")
        return {"normalized": digits, "identifier_type": "whatsapp"}

    email = identifier.lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Correo electrónico inválido")
    allowed_domains = {
        "gmail.com",
        "gmail.com.mx",
        "hotmail.com",
        "hotmail.es",
        "outlook.com",
        "outlook.es",
        "live.com",
        "live.com.mx",
    }
    domain = email.split("@")[-1]
    if domain not in allowed_domains:
        raise HTTPException(status_code=400, detail="Solo se permiten correos Gmail u Hotmail")
    return {"normalized": email, "identifier_type": "email"}


@app.post("/onboarding/register", response_model=OnboardingResponse)
async def onboarding_register(payload: OnboardingRequest) -> OnboardingResponse:
    """Register a new user via onboarding and seed demo data."""

    details = _validate_onboarding_identifier(payload)

    try:
        user_record = register_user_account(
            identifier=details["normalized"],
            identifier_type=details["identifier_type"],
            display_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error registrando usuario onboarding: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo registrar el usuario") from exc

    company_id = user_record["company_id"]
    already_exists = not user_record.get("created", False)

    records = fetch_expense_records(company_id=company_id, limit=10)
    demo_expenses = [_build_expense_response(record) for record in records]
    snapshot_raw = get_company_demo_snapshot(company_id)
    snapshot = DemoSnapshot(**snapshot_raw)

    next_steps = [
        "Revisa los gastos de ejemplo desde la vista de voz.",
        "Prueba la conciliación bancaria con los movimientos demo.",
        "Conecta tu empresa real cuando estés listo.",
    ]

    return OnboardingResponse(
        company_id=company_id,
        user_id=int(user_record["id"]),
        identifier=user_record["identifier"],
        identifier_type=user_record["identifier_type"],
        full_name=user_record.get("display_name") or payload.full_name,
        already_exists=already_exists,
        demo_snapshot=snapshot,
        demo_expenses=demo_expenses,
        next_steps=next_steps,
    )


@app.post("/invoices/parse", response_model=InvoiceParseResponse)
async def parse_invoice(file: UploadFile = File(...)) -> InvoiceParseResponse:
    """Parse CFDI XML uploads and return tax breakdown information."""

    filename = file.filename or ""
    if not filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CFDI XML")

    try:
        content = await file.read()
        parsed = parse_cfdi_xml(content)
        return InvoiceParseResponse(**parsed)
    except InvoiceParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Invoice parsing error: %s", exc)
        raise HTTPException(status_code=500, detail="Error interno al analizar la factura")


@app.post("/invoices/bulk-match", response_model=BulkInvoiceMatchResponse)
async def bulk_invoice_match(request: BulkInvoiceMatchRequest) -> BulkInvoiceMatchResponse:
    if not request.invoices:
        raise HTTPException(status_code=400, detail="No se recibieron facturas para conciliar")

    results: List[InvoiceMatchResult] = []

    for invoice in request.invoices:
        if invoice.total is None:
            results.append(
                InvoiceMatchResult(
                    filename=invoice.filename,
                    uuid=invoice.uuid,
                    status="error",
                    message="El CFDI no incluye un total numérico",
                )
            )
            continue

        if invoice.raw_xml is None and invoice.uuid is None:
            results.append(
                InvoiceMatchResult(
                    filename=invoice.filename,
                    status="unsupported",
                    message="Archivo sin datos de CFDI. Aporta XML o UUID para conciliar",
                )
            )
            continue

        match_result = _match_invoice_to_expense(
            company_id=request.company_id,
            invoice=invoice,
            global_auto_mark=request.auto_mark_invoiced,
        )
        results.append(match_result)

    return BulkInvoiceMatchResponse(
        company_id=request.company_id,
        processed=len(results),
        results=results,
    )


@app.post("/expenses", response_model=ExpenseResponse)
async def create_expense(expense: ExpenseCreate) -> ExpenseResponse:
    """Crear un nuevo gasto en la base de datos."""

    try:
        provider_name = (expense.proveedor or {}).get("nombre") if expense.proveedor else None

        account_code = "6180"
        if expense.categoria:
            account_mapping = {
                'combustible': '6140',
                'combustibles': '6140',
                'viajes': '6150',
                'viaticos': '6150',
                'alimentos': '6150',
                'servicios': '6130',
                'oficina': '6180',
                'honorarios': '6110',
                'renta': '6120',
                'publicidad': '6160',
                'marketing': '6160'
            }
            account_code = account_mapping.get(expense.categoria.lower(), account_code)

        invoice_uuid = None
        if expense.tax_info and expense.tax_info.get('uuid'):
            invoice_uuid = expense.tax_info['uuid']

        metadata_extra: Dict[str, Any] = dict(expense.metadata or {})
        if expense.proveedor:
            metadata_extra.setdefault('proveedor', expense.proveedor)
        if expense.rfc:
            metadata_extra.setdefault('rfc', expense.rfc)
        if expense.tax_info:
            metadata_extra.setdefault('tax_info', expense.tax_info)
        if expense.asientos_contables:
            metadata_extra['asientos_contables'] = expense.asientos_contables
        if expense.movimientos_bancarios:
            metadata_extra['movimientos_bancarios'] = expense.movimientos_bancarios

        metadata_extra.pop('company_id', None)

        expense_id = record_internal_expense(
            description=expense.descripcion,
            amount=expense.monto_total,
            account_code=account_code,
            currency="MXN",
            expense_date=expense.fecha_gasto,
            category=expense.categoria,
            provider_name=provider_name,
            provider_rfc=expense.rfc,
            workflow_status=expense.workflow_status,
            invoice_status=expense.estado_factura,
            invoice_uuid=invoice_uuid,
            tax_total=expense.tax_info.get('total') if expense.tax_info else None,
            tax_metadata=expense.tax_info,
            payment_method=expense.forma_pago,
            paid_by=expense.paid_by,
            will_have_cfdi=expense.will_have_cfdi,
            bank_status=expense.estado_conciliacion,
            metadata=metadata_extra,
            company_id=expense.company_id,
        )

        record = fetch_expense_record(expense_id)
        if not record:
            raise HTTPException(status_code=500, detail="No se pudo recuperar el gasto creado")

        return _build_expense_response(record)

    except Exception as exc:
        logger.exception("Error creating expense: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error creando gasto: {str(exc)}")


@app.get("/expenses", response_model=List[ExpenseResponse])
async def list_expenses(
    limit: int = 100,
    mes: Optional[str] = None,
    categoria: Optional[str] = None,
    estatus: Optional[str] = None,
    company_id: str = "default",
) -> List[ExpenseResponse]:
    """Listar gastos desde la base de datos."""

    try:
        if mes:
            try:
                datetime.strptime(mes, "%Y-%m")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Formato de mes inválido. Usa YYYY-MM") from exc

        records = fetch_expense_records(
            limit=limit,
            month=mes,
            category=categoria,
            invoice_status=estatus,
            company_id=company_id,
        )
        return [_build_expense_response(record) for record in records]

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error listing expenses: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error obteniendo gastos: {str(exc)}")


@app.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: int, expense: ExpenseCreate) -> ExpenseResponse:
    """Actualizar un gasto existente en la base de datos."""

    try:
        provider_name = (expense.proveedor or {}).get("nombre") if expense.proveedor else None

        account_code = "6180"
        if expense.categoria:
            category_mapping = {
                'combustible': '6140',
                'combustibles': '6140',
                'viajes': '6150',
                'viaticos': '6150',
                'alimentos': '6150',
                'servicios': '6130',
                'oficina': '6180',
                'honorarios': '6110',
                'renta': '6120',
                'publicidad': '6160',
                'marketing': '6160'
            }
            account_code = category_mapping.get(expense.categoria.lower(), account_code)

        invoice_uuid = None
        if expense.tax_info and expense.tax_info.get('uuid'):
            invoice_uuid = expense.tax_info['uuid']

        metadata_extra: Dict[str, Any] = dict(expense.metadata or {})
        if expense.proveedor:
            metadata_extra.setdefault('proveedor', expense.proveedor)
        if expense.rfc:
            metadata_extra.setdefault('rfc', expense.rfc)
        if expense.tax_info:
            metadata_extra.setdefault('tax_info', expense.tax_info)
        if expense.asientos_contables:
            metadata_extra['asientos_contables'] = expense.asientos_contables
        if expense.movimientos_bancarios:
            metadata_extra['movimientos_bancarios'] = expense.movimientos_bancarios

        metadata_extra.pop('company_id', None)

        updates = {
            "description": expense.descripcion,
            "amount": expense.monto_total,
            "account_code": account_code,
            "expense_date": expense.fecha_gasto,
            "category": expense.categoria,
            "provider_name": provider_name,
            "provider_rfc": expense.rfc,
            "workflow_status": expense.workflow_status,
            "invoice_status": expense.estado_factura,
            "bank_status": expense.estado_conciliacion,
            "payment_method": expense.forma_pago,
            "paid_by": expense.paid_by,
            "will_have_cfdi": expense.will_have_cfdi,
            "invoice_uuid": invoice_uuid,
            "tax_total": expense.tax_info.get('total') if expense.tax_info else None,
            "tax_metadata": expense.tax_info,
            "metadata": metadata_extra,
            "company_id": expense.company_id,
        }

        record = db_update_expense_record(expense_id, updates)
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")

        return _build_expense_response(record)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error updating expense: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error actualizando gasto: {str(exc)}")


@app.post("/expenses/{expense_id}/invoice", response_model=ExpenseResponse)
async def register_expense_invoice_endpoint(
    expense_id: int,
    payload: ExpenseInvoicePayload,
) -> ExpenseResponse:
    try:
        record = register_expense_invoice(
            expense_id,
            uuid=payload.uuid,
            folio=payload.folio,
            url=payload.url,
            issued_at=payload.issued_at,
            status=payload.status or "registrada",
            raw_xml=payload.raw_xml,
            actor=payload.actor,
        )
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return _build_expense_response(record)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error registrando factura interna: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo registrar la factura")


@app.post("/expenses/{expense_id}/mark-invoiced", response_model=ExpenseResponse)
async def mark_expense_as_invoiced(expense_id: int, request: ExpenseActionRequest) -> ExpenseResponse:
    try:
        record = db_mark_expense_invoiced(expense_id, actor=request.actor)
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return _build_expense_response(record)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error marcando gasto como facturado: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado de factura")


@app.post("/expenses/{expense_id}/close-no-invoice", response_model=ExpenseResponse)
async def close_expense_without_invoice(expense_id: int, request: ExpenseActionRequest) -> ExpenseResponse:
    try:
        record = db_mark_expense_without_invoice(expense_id, actor=request.actor)
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return _build_expense_response(record)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error cerrando gasto sin factura: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo cerrar el gasto sin factura")


@app.post("/expenses/check-duplicates", response_model=DuplicateCheckResponse)
async def check_expense_duplicates(request: DuplicateCheckRequest) -> DuplicateCheckResponse:
    """
    Verifica si un gasto nuevo es posiblemente duplicado comparándolo con gastos existentes.
    Usa embeddings semánticos y heurísticas para detectar similitudes.
    """
    try:
        from core.duplicate_detector import detect_expense_duplicates

        # Obtener gastos existentes si se solicita
        existing_expenses = []
        company_scope = request.new_expense.company_id
        if request.check_existing:
            records = fetch_expense_records(limit=200, company_id=company_scope)
            for record in records:
                metadata = record.get("metadata") or {}
                proveedor = metadata.get("proveedor") or (
                    {"nombre": record.get("provider_name")} if record.get("provider_name") else None
                )
                existing_expenses.append(
                    {
                        'id': record['id'],
                        'descripcion': record['description'],
                        'monto_total': record['amount'],
                        'fecha_gasto': record.get('expense_date'),
                        'categoria': record.get('category'),
                        'proveedor': proveedor,
                        'rfc': record.get('provider_rfc') or metadata.get('rfc'),
                        'created_at': record.get('created_at'),
                    }
                )

        # Convertir ExpenseCreate a diccionario
        new_expense_dict = {
            'descripcion': request.new_expense.descripcion,
            'monto_total': request.new_expense.monto_total,
            'fecha_gasto': request.new_expense.fecha_gasto,
            'categoria': request.new_expense.categoria,
            'proveedor': request.new_expense.proveedor,
            'rfc': request.new_expense.rfc,
            'company_id': company_scope,
        }

        # Detectar duplicados
        detection_result = detect_expense_duplicates(new_expense_dict, existing_expenses)

        return DuplicateCheckResponse(
            has_duplicates=detection_result['summary']['has_duplicates'],
            total_found=detection_result['summary']['total_found'],
            risk_level=detection_result['summary']['risk_level'],
            recommendation=detection_result['summary']['recommendation'],
            duplicates=detection_result['duplicates'],
            summary=detection_result['summary']
        )

    except Exception as exc:
        logger.exception("Error checking for duplicate expenses: %s", exc)
        # En caso de error, permitir que continúe (fail-safe)
        return DuplicateCheckResponse(
            has_duplicates=False,
            total_found=0,
            risk_level='none',
            recommendation='proceed',
            duplicates=[],
            summary={'error': f'Error en detección: {str(exc)}'}
        )


@app.post("/expenses/predict-category", response_model=CategoryPredictionResponse)
async def predict_expense_category(request: CategoryPredictionRequest) -> CategoryPredictionResponse:
    """
    Predice la categoría de un gasto usando LLM contextual y historial del usuario.
    Incluye sugerencias de autocompletado para mejorar la UX.
    """
    try:
        from core.category_predictor import predict_expense_category, get_category_predictor

        # Obtener historial de gastos si se solicita
        expense_history = []
        if request.include_history:
            records = fetch_expense_records(limit=50, company_id=request.company_id)
            for record in records:
                metadata = record.get("metadata") or {}
                provider = metadata.get('proveedor')
                if not provider and record.get('provider_name'):
                    provider = {"nombre": record.get('provider_name')}

                expense_history.append(
                    {
                        'descripcion': record['description'],
                        'monto_total': record['amount'],
                        'categoria': record.get('category'),
                        'proveedor': provider,
                        'fecha_gasto': record.get('expense_date'),
                        'created_at': record.get('created_at'),
                    }
                )

        # Predecir categoría
        prediction_result = predict_expense_category(
            description=request.description,
            amount=request.amount,
            provider_name=request.provider_name,
            expense_history=expense_history
        )

        # Obtener sugerencias de autocompletado
        predictor = get_category_predictor()
        autocomplete_suggestions = predictor.get_category_suggestions(
            prediction_result['categoria_sugerida']
        )

        return CategoryPredictionResponse(
            categoria_sugerida=prediction_result['categoria_sugerida'],
            confianza=prediction_result['confianza'],
            razonamiento=prediction_result['razonamiento'],
            alternativas=prediction_result['alternativas'],
            metodo_prediccion=prediction_result['metodo_prediccion'],
            sugerencias_autocompletado=autocomplete_suggestions
        )

    except Exception as exc:
        logger.exception("Error predicting expense category: %s", exc)
        # En caso de error, devolver categoría por defecto
        return CategoryPredictionResponse(
            categoria_sugerida='oficina',
            confianza=0.3,
            razonamiento=f'Error en predicción: {str(exc)}. Usando categoría por defecto.',
            alternativas=[],
            metodo_prediccion='fallback',
            sugerencias_autocompletado=[]
        )


@app.get("/expenses/category-suggestions")
async def get_category_suggestions(partial: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """
    Obtiene sugerencias de categorías para autocompletado.
    """
    try:
        from core.category_predictor import get_category_predictor

        predictor = get_category_predictor()
        suggestions = predictor.get_category_suggestions(partial)

        return {"suggestions": suggestions}

    except Exception as exc:
        logger.exception("Error getting category suggestions: %s", exc)
        return {"suggestions": []}


# =====================================================
# CONVERSATIONAL ASSISTANT ENDPOINTS
# =====================================================

class QueryRequest(BaseModel):
    query: str = Field(..., description="Consulta en lenguaje natural")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="Respuesta del asistente")
    data: Optional[Dict[str, Any]] = Field(None, description="Datos relevantes")
    query_type: str = Field(..., description="Tipo de consulta detectada")
    confidence: float = Field(..., description="Confianza en la respuesta (0-1)")
    sql_executed: Optional[str] = Field(None, description="SQL ejecutado (si aplica)")
    has_llm: bool = Field(..., description="Si se usó LLM para procesar")

class NonReconciliationRequest(BaseModel):
    expense_id: str = Field(..., description="ID del gasto")
    reason_code: str = Field(..., description="Código del motivo")
    reason_text: str = Field(..., description="Descripción del motivo")
    notes: Optional[str] = Field(None, description="Notas adicionales")
    estimated_resolution_date: Optional[str] = Field(None, description="Fecha estimada de resolución")

class NonReconciliationResponse(BaseModel):
    success: bool = Field(..., description="Si la operación fue exitosa")
    message: str = Field(..., description="Mensaje de confirmación")
    expense_id: str = Field(..., description="ID del gasto actualizado")
    status: str = Field(..., description="Nuevo estado del gasto")


@app.post("/expenses/query")
async def process_natural_language_query(request: QueryRequest) -> QueryResponse:
    """
    Procesa consultas en lenguaje natural sobre gastos.

    Ejemplos de consultas:
    - "¿Cuánto gasté este mes?"
    - "Mostrar gastos de combustible"
    - "Breakdown por categorías"
    - "Gastos en Pemex"
    - "Resumen de gastos de la semana pasada"
    """
    try:
        from core.conversational_assistant import process_natural_language_query

        logger.info(f"Processing natural language query: {request.query}")

        result = process_natural_language_query(request.query)

        return QueryResponse(
            answer=result['answer'],
            data=result['data'],
            query_type=result['query_type'],
            confidence=result['confidence'],
            sql_executed=result['sql_executed'],
            has_llm=result['has_llm']
        )

    except Exception as exc:
        logger.exception("Error processing natural language query: %s", exc)
        return QueryResponse(
            answer=f"Ocurrió un error procesando tu consulta: {str(exc)}",
            data=None,
            query_type="error",
            confidence=0.1,
            sql_executed=None,
            has_llm=False
        )


@app.get("/expenses/query-help")
async def get_query_help() -> Dict[str, Any]:
    """
    Obtiene ayuda sobre los tipos de consultas que se pueden hacer.
    """
    return {
        "title": "Asistente Conversacional de Gastos",
        "description": "Puedes hacer consultas en lenguaje natural sobre tus gastos empresariales.",
        "examples": [
            {
                "query": "¿Cuánto gasté este mes?",
                "description": "Obtener resumen de gastos del mes actual"
            },
            {
                "query": "Mostrar gastos de combustible",
                "description": "Buscar gastos por categoría específica"
            },
            {
                "query": "Breakdown por categorías",
                "description": "Análisis detallado por todas las categorías"
            },
            {
                "query": "Gastos de la semana pasada",
                "description": "Análisis temporal de un período específico"
            },
            {
                "query": "Gastos en Pemex",
                "description": "Análisis por proveedor específico"
            },
            {
                "query": "Resumen general",
                "description": "Estadísticas generales de todos los gastos"
            }
        ],
        "query_types": [
            "expense_summary - Resúmenes y totales",
            "expense_search - Búsquedas específicas",
            "category_analysis - Análisis por categorías",
            "time_analysis - Análisis temporal",
            "provider_analysis - Análisis por proveedores"
        ]
    }


# =====================================================
# NON-RECONCILIATION MANAGEMENT ENDPOINTS
# =====================================================

@app.post("/expenses/{expense_id}/mark-non-reconcilable")
async def mark_expense_non_reconcilable(
    expense_id: str,
    request: NonReconciliationRequest
) -> NonReconciliationResponse:
    """
    Marca un gasto como no conciliable con motivo específico.

    Motivos comunes:
    - missing_invoice: Falta la factura CFDI
    - bank_account_missing: No aparece en estado de cuenta bancario
    - wrong_amount: Monto no coincide con la factura
    - duplicate_entry: Gasto duplicado
    - provider_issue: Problema con el proveedor
    - system_error: Error del sistema
    - pending_approval: Pendiente de aprobación
    - other: Otro motivo (especificar en notas)
    """
    try:
        logger.info(f"Marking expense {expense_id} as non-reconcilable: {request.reason_code}")

        # Motivos predefinidos con descripciones
        REASON_CODES = {
            "missing_invoice": "Falta la factura CFDI",
            "bank_account_missing": "No aparece en estado de cuenta bancario",
            "wrong_amount": "Monto no coincide con la factura",
            "duplicate_entry": "Gasto duplicado",
            "provider_issue": "Problema con el proveedor",
            "system_error": "Error del sistema",
            "pending_approval": "Pendiente de aprobación",
            "other": "Otro motivo"
        }

        if request.reason_code not in REASON_CODES:
            return NonReconciliationResponse(
                success=False,
                message=f"Código de motivo inválido: {request.reason_code}",
                expense_id=expense_id,
                status="error"
            )

        # Aquí normalmente actualizarías la base de datos
        # Por ahora simulamos la actualización
        non_reconciliation_data = {
            "expense_id": expense_id,
            "reason_code": request.reason_code,
            "reason_text": request.reason_text,
            "reason_description": REASON_CODES[request.reason_code],
            "notes": request.notes,
            "estimated_resolution_date": request.estimated_resolution_date,
            "marked_date": datetime.now().isoformat(),
            "status": "non_reconcilable"
        }

        logger.info(f"Expense {expense_id} marked as non-reconcilable: {non_reconciliation_data}")

        return NonReconciliationResponse(
            success=True,
            message=f"Gasto marcado como no conciliable: {REASON_CODES[request.reason_code]}",
            expense_id=expense_id,
            status="non_reconcilable"
        )

    except Exception as exc:
        logger.exception("Error marking expense as non-reconcilable: %s", exc)
        return NonReconciliationResponse(
            success=False,
            message=f"Error: {str(exc)}",
            expense_id=expense_id,
            status="error"
        )


@app.get("/expenses/non-reconciliation-reasons")
async def get_non_reconciliation_reasons() -> Dict[str, Any]:
    """
    Obtiene la lista de motivos predefinidos para no conciliación.
    """
    return {
        "reasons": [
            {
                "code": "missing_invoice",
                "title": "Falta factura CFDI",
                "description": "No se ha recibido o no se encuentra la factura correspondiente",
                "category": "documentation",
                "typical_resolution_days": 7
            },
            {
                "code": "bank_account_missing",
                "title": "No aparece en banco",
                "description": "El gasto no aparece en el estado de cuenta bancario",
                "category": "banking",
                "typical_resolution_days": 3
            },
            {
                "code": "wrong_amount",
                "title": "Monto no coincide",
                "description": "El monto registrado no coincide con la factura o estado de cuenta",
                "category": "amount_mismatch",
                "typical_resolution_days": 2
            },
            {
                "code": "duplicate_entry",
                "title": "Gasto duplicado",
                "description": "Este gasto ya fue registrado anteriormente",
                "category": "duplicate",
                "typical_resolution_days": 1
            },
            {
                "code": "provider_issue",
                "title": "Problema con proveedor",
                "description": "Hay un problema pendiente con el proveedor (datos incorrectos, etc.)",
                "category": "provider",
                "typical_resolution_days": 10
            },
            {
                "code": "system_error",
                "title": "Error del sistema",
                "description": "Error técnico que impide la conciliación automática",
                "category": "technical",
                "typical_resolution_days": 1
            },
            {
                "code": "pending_approval",
                "title": "Pendiente de aprobación",
                "description": "El gasto está pendiente de aprobación por parte de un superior",
                "category": "approval",
                "typical_resolution_days": 5
            },
            {
                "code": "other",
                "title": "Otro motivo",
                "description": "Motivo no contemplado en las opciones anteriores",
                "category": "other",
                "typical_resolution_days": 7
            }
        ],
        "categories": {
            "documentation": "Problemas de documentación",
            "banking": "Problemas bancarios",
            "amount_mismatch": "Discrepancias de montos",
            "duplicate": "Duplicados",
            "provider": "Problemas con proveedores",
            "technical": "Problemas técnicos",
            "approval": "Procesos de aprobación",
            "other": "Otros"
        }
    }


@app.get("/expenses/{expense_id}/non-reconciliation-status")
async def get_expense_non_reconciliation_status(expense_id: str) -> Dict[str, Any]:
    """
    Obtiene el estado de no conciliación de un gasto específico.
    """
    try:
        # Aquí normalmente consultarías la base de datos
        # Por ahora retornamos un ejemplo
        return {
            "expense_id": expense_id,
            "is_non_reconcilable": False,
            "reason": None,
            "notes": None,
            "marked_date": None,
            "estimated_resolution_date": None,
            "history": []
        }

    except Exception as exc:
        logger.exception("Error getting non-reconciliation status: %s", exc)
        return {
            "error": str(exc),
            "expense_id": expense_id
        }


# =====================================================
# DUMMY DATA GENERATION ENDPOINTS
# =====================================================

@app.post("/demo/generate-dummy-data")
async def generate_dummy_data() -> Dict[str, Any]:
    """
    Genera datos de prueba realistas para demostrar el sistema.

    Crea gastos de ejemplo con diferentes estados:
    - Gastos normales conciliados
    - Gastos pendientes de facturación
    - Gastos con problemas de conciliación
    - Gastos duplicados
    - Gastos con diferentes categorías y proveedores
    """
    try:
        from datetime import datetime, timedelta
        import random
        import uuid

        logger.info("Generating dummy data for demonstration")

        # Datos base realistas
        DUMMY_EXPENSES = [
            # Gastos de Combustible
            {
                "descripcion": "Gasolina Premium Pemex Insurgentes",
                "monto_total": 850.00,
                "categoria": "combustible",
                "proveedor": {"nombre": "Pemex", "rfc": "PEP970814HS9"},
                "fecha_gasto": (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "PEP970814HS9",
                "urgency_level": "medium"
            },
            {
                "descripcion": "Diesel Shell Periférico Sur",
                "monto_total": 1200.00,
                "categoria": "combustible",
                "proveedor": {"nombre": "Shell", "rfc": "SHE880315QR4"},
                "fecha_gasto": (datetime.now() - timedelta(days=18)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "SHE880315QR4",
                "urgency_level": "high"
            },

            # Gastos de Alimentos
            {
                "descripcion": "Almuerzo reunión con cliente Starbucks",
                "monto_total": 320.50,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Starbucks Coffee", "rfc": "STA950612LP8"},
                "fecha_gasto": (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                "estado_factura": "facturado",
                "workflow_status": "facturado",
                "factura_id": "A12345",
                "urgency_level": "low"
            },
            {
                "descripcion": "Cena corporativa Restaurante Pujol",
                "monto_total": 2400.00,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Restaurante Pujol", "rfc": "PUJ030920MN2"},
                "fecha_gasto": (datetime.now() - timedelta(days=12)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "PUJ030920MN2",
                "urgency_level": "medium"
            },

            # Gastos de Transporte
            {
                "descripcion": "Viaje Uber a oficina cliente",
                "monto_total": 145.00,
                "categoria": "transporte",
                "proveedor": {"nombre": "Uber Technologies", "rfc": "UBE140225ST7"},
                "fecha_gasto": (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "UBE140225ST7",
                "urgency_level": "low"
            },
            {
                "descripcion": "Vuelo VivaAerobus CDMX-GDL",
                "monto_total": 1850.00,
                "categoria": "transporte",
                "proveedor": {"nombre": "VivaAerobus", "rfc": "VIV061205KL9"},
                "fecha_gasto": (datetime.now() - timedelta(days=28)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "VIV061205KL9",
                "urgency_level": "critical"
            },

            # Gastos de Tecnología
            {
                "descripcion": "Licencia Microsoft Office 365 Business",
                "monto_total": 1890.00,
                "categoria": "tecnologia",
                "proveedor": {"nombre": "Microsoft Mexico", "rfc": "MIC920818QP3"},
                "fecha_gasto": (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "MIC920818QP3",
                "urgency_level": "high"
            },
            {
                "descripcion": "Suscripción Adobe Creative Cloud",
                "monto_total": 980.00,
                "categoria": "tecnologia",
                "proveedor": {"nombre": "Adobe Systems", "rfc": "ADO851201TP5"},
                "fecha_gasto": (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                "estado_factura": "facturado",
                "workflow_status": "facturado",
                "factura_id": "ADO98765",
                "urgency_level": "low"
            },

            # Gastos de Oficina
            {
                "descripcion": "Suministros de oficina Office Depot",
                "monto_total": 450.75,
                "categoria": "oficina",
                "proveedor": {"nombre": "Office Depot Mexico", "rfc": "OFD770403XY1"},
                "fecha_gasto": (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "OFD770403XY1",
                "urgency_level": "medium"
            },

            # Gastos de Hospedaje
            {
                "descripcion": "Hotel City Express Guadalajara",
                "monto_total": 1250.00,
                "categoria": "hospedaje",
                "proveedor": {"nombre": "Hoteles City Express", "rfc": "HCE990515AB8"},
                "fecha_gasto": (datetime.now() - timedelta(days=22)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "HCE990515AB8",
                "urgency_level": "high"
            },

            # Casos especiales para demo de no conciliación
            {
                "descripcion": "Comida duplicada - Posible error",
                "monto_total": 320.50,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Starbucks Coffee", "rfc": "STA950612LP8"},
                "fecha_gasto": (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "STA950612LP8",
                "urgency_level": "low",
                "is_potential_duplicate": True
            },
            {
                "descripcion": "Gasto sin factura - Pago en efectivo",
                "monto_total": 180.00,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Taquería Local", "rfc": ""},
                "fecha_gasto": (datetime.now() - timedelta(days=35)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "urgency_level": "critical",
                "missing_invoice_reason": "Establecimiento pequeño sin facturación"
            }
        ]

        # Generar IDs únicos y agregar metadata
        generated_expenses = []
        for i, expense in enumerate(DUMMY_EXPENSES):
            expense_id = f"DEMO-{str(uuid.uuid4())[:8].upper()}"

            complete_expense = {
                "id": expense_id,
                "timestamp": datetime.now().isoformat(),
                "input_method": "demo_data",
                **expense,
                "metadata": {
                    "generated_demo": True,
                    "generation_time": datetime.now().isoformat(),
                    "urgency_analysis": {
                        "level": expense.get("urgency_level", "low"),
                        "days_old": (datetime.now() - datetime.strptime(expense["fecha_gasto"], '%Y-%m-%d')).days
                    }
                },
                "asientos_contables": {
                    "numero_poliza": f"POL-{1000 + i}",
                    "tipo_poliza": "Diario",
                    "fecha_asiento": expense["fecha_gasto"],
                    "concepto": f"Registro de {expense['descripcion']}",
                    "balanceado": True,
                    "movimientos": [
                        {
                            "cuenta": "60101",
                            "nombre_cuenta": f"Gastos de {expense['categoria'].title()}",
                            "debe": expense["monto_total"],
                            "haber": 0,
                            "tipo": "debe"
                        },
                        {
                            "cuenta": "11301",
                            "nombre_cuenta": "Bancos - Cuenta Principal",
                            "debe": 0,
                            "haber": expense["monto_total"],
                            "tipo": "haber"
                        }
                    ]
                }
            }

            generated_expenses.append(complete_expense)

        # Agregar estadísticas de la generación
        stats = {
            "total_generated": len(generated_expenses),
            "by_category": {},
            "by_status": {},
            "by_urgency": {},
            "total_amount": sum(exp["monto_total"] for exp in generated_expenses),
            "date_range": {
                "from": min(exp["fecha_gasto"] for exp in generated_expenses),
                "to": max(exp["fecha_gasto"] for exp in generated_expenses)
            }
        }

        # Calcular estadísticas
        for expense in generated_expenses:
            category = expense["categoria"]
            status = expense["estado_factura"]
            urgency = expense.get("urgency_level", "low")

            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["by_urgency"][urgency] = stats["by_urgency"].get(urgency, 0) + 1

        logger.info(f"Generated {len(generated_expenses)} dummy expenses for demo")

        return {
            "success": True,
            "message": f"Se generaron {len(generated_expenses)} gastos de demostración",
            "manual_expenses": generated_expenses,
            "statistics": stats,
            "demo_scenarios": [
                "✅ Gastos normales en diferentes categorías",
                "⏳ Gastos pendientes con diferentes niveles de urgencia",
                "🔴 Gastos críticos (>25 días sin facturar)",
                "🟡 Gastos con alta prioridad (>15 días)",
                "🔄 Posibles duplicados para demostrar detección",
                "📄 Gastos sin facturas para demostrar no conciliación",
                "💰 Montos variados para análisis de insights",
                "🏢 Proveedores reales mexicanos con RFC",
                "📊 Asientos contables generados automáticamente"
            ]
        }

    except Exception as exc:
        logger.exception("Error generating dummy data: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "Error generando datos de demostración"
        }


if __name__ == "__main__":
    # Run the server when executed directly
    logger.info(f"Starting MCP Server on localhost:8002")
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8002,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )
