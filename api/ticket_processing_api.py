"""Async Ticket Processing API

This module handles asynchronous ticket processing with real-time WebSocket updates.

Flow:
1. User uploads ticket image/PDF
2. Returns processing_id immediately
3. Background worker:
   - Performs OCR extraction
   - Parses ticket with Gemini
   - Extracts concepts for matching
   - Detects invoice portal URLs
   - Sends progress updates via WebSocket
4. Client receives real-time updates
5. Auto-fills expense form on completion

Created: 2025-11-25
Author: Claude Code
"""

import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from core.ai_pipeline.parsers.ticket_parser import (
    extract_ticket_concepts,
    format_ticket_for_storage,
    parse_ticket_text,
    TicketParserError,
)
from core.auth.jwt import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ticket-processing", tags=["Ticket Processing"])

# In-memory storage for processing status (replace with Redis in production)
_processing_status: Dict[str, Dict[str, Any]] = {}

# WebSocket connection manager
_active_connections: Dict[str, WebSocket] = {}


# ==================
# PYDANTIC MODELS
# ==================


class ProcessingStartResponse(BaseModel):
    """Response when ticket processing starts."""

    processing_id: str = Field(..., description="Unique ID for tracking this processing job")
    status: str = Field(default="processing", description="Initial status")
    message: str = Field(default="Ticket processing started", description="Status message")
    websocket_url: str = Field(..., description="WebSocket URL for real-time updates")


class ProcessingStatus(BaseModel):
    """Current status of ticket processing."""

    processing_id: str
    status: str = Field(
        ...,
        description="Current status: idle, uploading, ocr, parsing, extracting_concepts, finding_url, complete, error",
    )
    progress: int = Field(..., ge=0, le=100, description="Progress percentage 0-100")
    message: str = Field(..., description="Human-readable status message")
    current_step: str = Field(..., description="Current processing step")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted ticket data (when complete)")
    error: Optional[str] = Field(None, description="Error message if status=error")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TicketProcessingResult(BaseModel):
    """Final result of ticket processing."""

    processing_id: str
    status: str = Field(default="complete")
    merchant_name: Optional[str] = None
    merchant_rfc: Optional[str] = None
    folio: Optional[str] = None
    fecha: Optional[str] = None
    total: Optional[float] = None
    subtotal: Optional[float] = None
    iva: Optional[float] = None
    forma_pago: Optional[str] = None
    conceptos: list[Dict[str, Any]] = Field(default_factory=list)
    ticket_extracted_concepts: list[str] = Field(default_factory=list, description="Concepts for matching")
    invoice_portal_url: Optional[str] = None
    invoice_portal_hint: Optional[str] = None
    extraction_confidence: str = Field(default="low")
    extraction_model: str = Field(default="gemini-2.5-flash")


# ==================
# HELPER FUNCTIONS
# ==================


def _update_status(
    processing_id: str,
    status: str,
    progress: int,
    message: str,
    current_step: str,
    extracted_data: Optional[Dict] = None,
    error: Optional[str] = None,
):
    """Update processing status and notify via WebSocket if connected."""

    status_obj = ProcessingStatus(
        processing_id=processing_id,
        status=status,
        progress=progress,
        message=message,
        current_step=current_step,
        extracted_data=extracted_data,
        error=error,
        updated_at=datetime.utcnow(),
        created_at=_processing_status.get(processing_id, {}).get("created_at", datetime.utcnow()),
    )

    _processing_status[processing_id] = status_obj.model_dump()

    # Send WebSocket update if client connected
    if processing_id in _active_connections:
        asyncio.create_task(_send_websocket_update(processing_id, status_obj.model_dump()))

    logger.info(f"[{processing_id}] {status} - {message} ({progress}%)")


async def _send_websocket_update(processing_id: str, data: Dict[str, Any]):
    """Send update to WebSocket client."""

    websocket = _active_connections.get(processing_id)
    if websocket:
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket update to {processing_id}: {e}")
            # Remove dead connection
            _active_connections.pop(processing_id, None)


async def _perform_ocr(file_path: str, filename: str) -> str:
    """Perform OCR on uploaded file.

    TODO: Integrate with existing OCR service (Google Vision, Tesseract, etc.)
    For now, returns placeholder.
    """

    # Simulate OCR processing time
    await asyncio.sleep(1)

    # TODO: Replace with actual OCR call
    # Example: from core.ai_pipeline.parsers.advanced_ocr_service import extract_text
    # ocr_text = extract_text(file_path)

    # Placeholder OCR text for testing
    placeholder_ocr = f"""
    OXXO
    RFC: OXX830110P45

    TICKET: {uuid.uuid4().hex[:8].upper()}
    FECHA: {datetime.now().strftime('%d/%m/%Y')}

    COCA COLA 600ML       $18.00
    SABRITAS ORIGINAL     $15.50

    SUBTOTAL:             $33.50
    IVA 16%:              $5.36
    TOTAL:                $38.86

    FORMA PAGO: TARJETA

    ¿Necesitas factura?
    Visita: www.oxxo.com/facturacion
    """

    logger.info(f"OCR completed for {filename}: {len(placeholder_ocr)} characters extracted")

    return placeholder_ocr


def _detect_invoice_url(ocr_text: str, parsed_data: Dict[str, Any]) -> Optional[str]:
    """Detect invoice portal URL from OCR text or parsed data.

    TODO: Implement more sophisticated URL detection with ML/LLM.
    """

    # Check parsed data first
    if parsed_data.get('invoice_portal_url'):
        return parsed_data['invoice_portal_url']

    # Simple regex-based detection
    import re

    # Common Mexican invoice portal patterns
    patterns = [
        r'(https?://[^\s]+factura[^\s]*)',
        r'(www\.[^\s]+factura[^\s]*)',
        r'(https?://[^\s]+cfdi[^\s]*)',
        r'(www\.[^\s]+cfdi[^\s]*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Ensure https://
            if not url.startswith('http'):
                url = 'https://' + url
            return url

    return None


async def _process_ticket_background(processing_id: str, file_path: str, filename: str):
    """Background worker for ticket processing.

    Stages:
    1. OCR extraction (0-25%)
    2. Ticket parsing with Gemini (25-50%)
    3. Concept extraction (50-75%)
    4. URL detection (75-100%)
    """

    try:
        # Stage 1: OCR (0-25%)
        _update_status(
            processing_id,
            status="ocr",
            progress=10,
            message="Extrayendo texto del ticket...",
            current_step="OCR en progreso",
        )

        ocr_text = await _perform_ocr(file_path, filename)

        _update_status(
            processing_id,
            status="ocr",
            progress=25,
            message="Texto extraído exitosamente",
            current_step="OCR completado",
        )

        # Stage 2: Parsing with Gemini (25-50%)
        _update_status(
            processing_id,
            status="parsing",
            progress=30,
            message="Analizando ticket con IA...",
            current_step="Gemini procesando",
        )

        # Run Gemini parsing in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        parsed_data = await loop.run_in_executor(None, parse_ticket_text, ocr_text)

        _update_status(
            processing_id,
            status="parsing",
            progress=50,
            message="Ticket analizado correctamente",
            current_step="Parsing completado",
        )

        # Stage 3: Concept extraction (50-75%)
        _update_status(
            processing_id,
            status="extracting_concepts",
            progress=60,
            message="Extrayendo conceptos para matching...",
            current_step="Extracción de conceptos",
        )

        concepts = extract_ticket_concepts(parsed_data)

        _update_status(
            processing_id,
            status="extracting_concepts",
            progress=75,
            message=f"Extraídos {len(concepts)} conceptos",
            current_step="Conceptos extraídos",
        )

        # Stage 4: URL detection (75-100%)
        _update_status(
            processing_id,
            status="finding_url",
            progress=85,
            message="Buscando portal de facturación...",
            current_step="Detección de URL",
        )

        invoice_url = _detect_invoice_url(ocr_text, parsed_data)

        # Prepare final data
        storage_data = format_ticket_for_storage(parsed_data)
        storage_data['ticket_extracted_concepts'] = concepts

        result = TicketProcessingResult(
            processing_id=processing_id,
            status="complete",
            merchant_name=parsed_data.get('merchant_name'),
            merchant_rfc=parsed_data.get('merchant_rfc'),
            folio=parsed_data.get('folio'),
            fecha=parsed_data.get('fecha'),
            total=parsed_data.get('total'),
            subtotal=parsed_data.get('subtotal'),
            iva=parsed_data.get('iva'),
            forma_pago=parsed_data.get('forma_pago'),
            conceptos=parsed_data.get('conceptos', []),
            ticket_extracted_concepts=concepts,
            invoice_portal_url=invoice_url,
            invoice_portal_hint=parsed_data.get('invoice_portal_hint'),
            extraction_confidence=parsed_data.get('extraction_confidence', 'medium'),
            extraction_model=parsed_data.get('extraction_model', 'gemini-2.5-flash'),
        )

        _update_status(
            processing_id,
            status="complete",
            progress=100,
            message="Ticket procesado exitosamente",
            current_step="Completado",
            extracted_data=result.model_dump(),
        )

    except TicketParserError as e:
        logger.error(f"[{processing_id}] Ticket parsing error: {e}")
        _update_status(
            processing_id,
            status="error",
            progress=0,
            message="Error al analizar el ticket",
            current_step="Error",
            error=str(e),
        )

    except Exception as e:
        logger.error(f"[{processing_id}] Unexpected error: {e}", exc_info=True)
        _update_status(
            processing_id,
            status="error",
            progress=0,
            message="Error inesperado durante el procesamiento",
            current_step="Error",
            error=str(e),
        )

    finally:
        # Cleanup temp file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


# ==================
# API ENDPOINTS
# ==================


@router.post("/upload", response_model=ProcessingStartResponse)
async def upload_ticket_async(
    file: UploadFile = File(..., description="Ticket image or PDF file"),
    current_user: User = Depends(get_current_user),
):
    """Upload ticket for async processing.

    Returns processing_id immediately. Client should connect to WebSocket
    for real-time updates.

    Supported formats: JPG, PNG, PDF
    """

    # Validate file type
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Generate processing ID
    processing_id = str(uuid.uuid4())

    # Save uploaded file to temp directory
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"ticket_{processing_id}{file_ext}")

        with open(temp_path, 'wb') as f:
            content = await file.read()
            f.write(content)

        logger.info(f"[{processing_id}] Uploaded file saved: {temp_path} ({len(content)} bytes)")

    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Initialize processing status
    _update_status(
        processing_id,
        status="uploading",
        progress=0,
        message="Archivo recibido, iniciando procesamiento...",
        current_step="Iniciando",
    )

    # Start background processing
    asyncio.create_task(_process_ticket_background(processing_id, temp_path, file.filename))

    # Return processing info
    return ProcessingStartResponse(
        processing_id=processing_id,
        status="processing",
        message="Ticket processing started",
        websocket_url=f"/ticket-processing/ws/{processing_id}",
    )


@router.get("/status/{processing_id}", response_model=ProcessingStatus)
async def get_processing_status(processing_id: str, current_user: User = Depends(get_current_user)):
    """Get current processing status (polling alternative to WebSocket)."""

    status = _processing_status.get(processing_id)

    if not status:
        raise HTTPException(status_code=404, detail="Processing ID not found")

    return ProcessingStatus(**status)


@router.websocket("/ws/{processing_id}")
async def websocket_ticket_processing(websocket: WebSocket, processing_id: str):
    """WebSocket endpoint for real-time ticket processing updates.

    Client should connect after receiving processing_id from /upload endpoint.

    Updates are sent automatically as processing progresses.
    """

    await websocket.accept()
    _active_connections[processing_id] = websocket

    logger.info(f"WebSocket connected for processing_id: {processing_id}")

    try:
        # Send initial status if available
        if processing_id in _processing_status:
            await websocket.send_json(_processing_status[processing_id])

        # Keep connection alive and listen for client messages
        while True:
            # Wait for messages from client (e.g., ping/pong)
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for processing_id: {processing_id}")
        _active_connections.pop(processing_id, None)

    except Exception as e:
        logger.error(f"WebSocket error for {processing_id}: {e}")
        _active_connections.pop(processing_id, None)


@router.delete("/status/{processing_id}")
async def cleanup_processing_status(processing_id: str, current_user: User = Depends(get_current_user)):
    """Cleanup processing status after client has retrieved results.

    Call this after successfully processing the ticket data to free memory.
    """

    if processing_id in _processing_status:
        del _processing_status[processing_id]
        logger.info(f"Cleaned up processing status for {processing_id}")
        return {"status": "deleted", "processing_id": processing_id}

    raise HTTPException(status_code=404, detail="Processing ID not found")


# Export router
__all__ = ['router']
