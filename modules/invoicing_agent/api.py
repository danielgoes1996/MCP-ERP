"""
API Router para el módulo de facturación automática de tickets.

Endpoints disponibles:
- POST /invoicing/tickets - Subir ticket
- GET /invoicing/tickets/{id} - Ver estado del ticket
- POST /invoicing/bulk-match - Carga masiva de tickets
- POST /webhooks/whatsapp - Webhook para mensajes de WhatsApp
- GET /invoicing/merchants - Listar merchants
- POST /invoicing/merchants - Crear merchant
- GET /invoicing/jobs - Ver jobs de facturación
"""

import base64
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from modules.invoicing_agent.models import (
    TicketCreate,
    TicketResponse,
    MerchantCreate,
    MerchantResponse,
    InvoicingJobResponse,
    WhatsAppMessage,
    BulkTicketUpload,
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket,
    create_merchant,
    get_merchant,
    list_merchants,
    find_merchant_by_name,
    create_invoicing_job,
    list_pending_jobs,
    create_expense_from_ticket,
)
from modules.invoicing_agent.worker import InvoicingWorker

# Nuevos servicios escalables
from modules.invoicing_agent.services import (
    orchestrator, process_ticket, process_multiple_tickets,
    get_system_health, initialize_services
)

logger = logging.getLogger(__name__)

# Crear el router y templates
router = APIRouter(prefix="/invoicing", tags=["invoicing_agent"])
try:
    templates = Jinja2Templates(directory="templates")
except Exception:
    templates = None  # Fallback si jinja2 no está disponible


# ===================================================================
# ENDPOINTS DE TICKETS
# ===================================================================

@router.post("/tickets", response_model=Dict[str, Any])
async def upload_ticket(
    file: Optional[UploadFile] = File(None),
    text_content: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    company_id: str = Form("default"),
) -> Dict[str, Any]:
    """
    Subir un ticket de compra para procesamiento automático.

    Puede subir:
    - Imagen/PDF del ticket
    - Texto del ticket
    - Nota de voz (pendiente implementación)
    """
    try:
        if not file and not text_content:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar un archivo o contenido de texto"
            )

        raw_data = ""
        tipo = "texto"

        if file:
            content = await file.read()

            # Determinar tipo según content type
            if file.content_type and file.content_type.startswith("image/"):
                tipo = "imagen"
                raw_data = base64.b64encode(content).decode('utf-8')
            elif file.content_type and file.content_type == "application/pdf":
                tipo = "pdf"
                raw_data = base64.b64encode(content).decode('utf-8')
            elif file.content_type and file.content_type.startswith("audio/"):
                tipo = "voz"
                raw_data = base64.b64encode(content).decode('utf-8')
            else:
                # Fallback a texto
                tipo = "texto"
                raw_data = content.decode('utf-8', errors='ignore')
        else:
            raw_data = text_content or ""

        # Crear el ticket
        ticket_id = create_ticket(
            raw_data=raw_data,
            tipo=tipo,
            user_id=user_id,
            company_id=company_id,
        )

        # Crear job de procesamiento
        job_id = create_invoicing_job(
            ticket_id=ticket_id,
            company_id=company_id,
        )

        # ANÁLISIS AUTOMÁTICO DEL TICKET
        analyzed_text = raw_data
        analysis_result = None

        # Si es imagen, primero extraer texto con OCR
        if tipo == "imagen":
            try:
                logger.info(f"Aplicando OCR automático a ticket {ticket_id}")

                from core.advanced_ocr_service import AdvancedOCRService
                ocr_service = AdvancedOCRService()

                ocr_result = await ocr_service.extract_text_intelligent(
                    raw_data,
                    context_hint="ticket"
                )

                if not ocr_result.error:
                    analyzed_text = ocr_result.text
                    logger.info(f"OCR exitoso para ticket {ticket_id}, texto extraído: {len(analyzed_text)} caracteres")
                else:
                    logger.warning(f"Error en OCR para ticket {ticket_id}: {ocr_result.error}")

            except Exception as e:
                logger.error(f"Error en OCR automático para ticket {ticket_id}: {e}")

        # Análisis con OpenAI del texto extraído
        if analyzed_text:
            try:
                logger.info(f"Analizando ticket {ticket_id} con OpenAI")

                from core.ticket_analyzer import analyze_ticket_content
                analysis = await analyze_ticket_content(analyzed_text)

                analysis_result = {
                    "merchant_name": analysis.merchant_name,
                    "category": analysis.category,
                    "confidence": analysis.confidence
                }

                logger.info(f"Análisis completado para ticket {ticket_id}: {analysis.merchant_name} - {analysis.category}")

                # Actualizar el ticket con los datos del análisis
                from modules.invoicing_agent.models import update_ticket
                update_ticket(
                    ticket_id,
                    merchant_name=analysis.merchant_name,
                    category=analysis.category,
                    confidence=analysis.confidence,
                    llm_analysis=analysis_result
                )

            except Exception as e:
                logger.warning(f"Error en análisis OpenAI para ticket {ticket_id}: {e}")
                analysis_result = {
                    "merchant_name": "Error de Análisis",
                    "category": "📦 Otros",
                    "confidence": 0.0
                }

        # Obtener datos del ticket creado
        ticket_data = get_ticket(ticket_id)

        logger.info(f"Ticket {ticket_id} creado, job {job_id} programado")

        # Preparar respuesta con análisis
        response = {
            "success": True,
            "ticket_id": ticket_id,
            "job_id": job_id,
            "status": "pendiente_procesamiento",
            "message": "Ticket recibido y programado para procesamiento",
            "ticket": ticket_data,
        }

        # Agregar análisis si está disponible
        if analysis_result:
            response["analysis"] = analysis_result
            response["analyzed_text"] = analyzed_text  # Texto completo sin truncar

        return response

    except Exception as e:
        logger.error(f"Error subiendo ticket: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando ticket: {str(e)}"
        )


@router.get("/tickets/{ticket_id}", response_model=Dict[str, Any])
async def get_ticket_status(ticket_id: int) -> Dict[str, Any]:
    """
    Obtener el estado y detalles de un ticket específico.
    """
    try:
        ticket = get_ticket(ticket_id)

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail=f"Ticket {ticket_id} no encontrado"
            )

        # Obtener jobs relacionados
        jobs = list_pending_jobs(ticket["company_id"])
        related_jobs = [job for job in jobs if job["ticket_id"] == ticket_id]

        return {
            "success": True,
            "ticket": ticket,
            "jobs": related_jobs,
            "processing_status": _determine_processing_status(ticket, related_jobs),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo ticket: {str(e)}"
        )


@router.get("/tickets", response_model=Dict[str, Any])
async def list_tickets_endpoint(
    company_id: str = "default",
    estado: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Listar tickets con filtros opcionales.
    """
    try:
        tickets = list_tickets(
            company_id=company_id,
            estado=estado,
            limit=limit
        )

        return {
            "success": True,
            "total": len(tickets),
            "tickets": tickets,
            "filters": {
                "company_id": company_id,
                "estado": estado,
                "limit": limit,
            }
        }

    except Exception as e:
        logger.error(f"Error listando tickets: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listando tickets: {str(e)}"
        )


# ===================================================================
# ENDPOINTS DE CARGA MASIVA
# ===================================================================

@router.post("/bulk-match", response_model=Dict[str, Any])
async def bulk_ticket_upload(request: BulkTicketUpload) -> Dict[str, Any]:
    """
    Carga masiva de tickets para procesamiento en lote.

    Útil para usuarios que tienen muchos tickets acumulados.
    """
    try:
        results = []
        total_processed = 0
        total_errors = 0

        for i, ticket_data in enumerate(request.tickets):
            try:
                # Validar datos mínimos
                if not ticket_data.get("raw_data"):
                    results.append({
                        "index": i,
                        "success": False,
                        "error": "raw_data es requerido",
                    })
                    total_errors += 1
                    continue

                # Crear ticket
                ticket_id = create_ticket(
                    raw_data=ticket_data["raw_data"],
                    tipo=ticket_data.get("tipo", "texto"),
                    user_id=ticket_data.get("user_id"),
                    company_id=request.company_id,
                )

                # Crear job si auto_process está habilitado
                job_id = None
                if request.auto_process:
                    job_id = create_invoicing_job(
                        ticket_id=ticket_id,
                        company_id=request.company_id,
                    )

                results.append({
                    "index": i,
                    "success": True,
                    "ticket_id": ticket_id,
                    "job_id": job_id,
                })
                total_processed += 1

            except Exception as e:
                results.append({
                    "index": i,
                    "success": False,
                    "error": str(e),
                })
                total_errors += 1

        logger.info(f"Carga masiva completada: {total_processed} exitosos, {total_errors} errores")

        return {
            "success": True,
            "total_tickets": len(request.tickets),
            "processed": total_processed,
            "errors": total_errors,
            "auto_process": request.auto_process,
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error en carga masiva: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en carga masiva: {str(e)}"
        )


# ===================================================================
# WEBHOOK DE WHATSAPP
# ===================================================================

@router.post("/webhooks/whatsapp", response_model=Dict[str, Any])
async def whatsapp_webhook(message: WhatsAppMessage) -> Dict[str, Any]:
    """
    Webhook para recibir mensajes entrantes de WhatsApp.

    Procesa automáticamente mensajes que contengan tickets de compra.
    """
    try:
        logger.info(f"Mensaje WhatsApp recibido: {message.message_id} de {message.from_number}")

        # Determinar company_id basado en número de teléfono (simplificado)
        company_id = _determine_company_from_phone(message.from_number)

        # Procesar según tipo de mensaje
        raw_data = message.content
        tipo = "texto"

        if message.message_type == "image" and message.media_url:
            tipo = "imagen"
            # En producción, descargar imagen desde media_url
            raw_data = f"imagen_url:{message.media_url}"
        elif message.message_type == "document" and message.media_url:
            tipo = "pdf"
            raw_data = f"documento_url:{message.media_url}"
        elif message.message_type == "audio" and message.media_url:
            tipo = "voz"
            raw_data = f"audio_url:{message.media_url}"

        # Crear ticket
        ticket_id = create_ticket(
            raw_data=raw_data,
            tipo=tipo,
            whatsapp_message_id=message.message_id,
            company_id=company_id,
        )

        # Crear job de procesamiento
        job_id = create_invoicing_job(
            ticket_id=ticket_id,
            company_id=company_id,
        )

        return {
            "success": True,
            "message": "Mensaje procesado exitosamente",
            "ticket_id": ticket_id,
            "job_id": job_id,
            "whatsapp_message_id": message.message_id,
        }

    except Exception as e:
        logger.error(f"Error procesando mensaje WhatsApp: {str(e)}")
        # No levantar HTTPException para webhooks
        return {
            "success": False,
            "error": str(e),
            "message": "Error procesando mensaje",
        }


# ===================================================================
# ENDPOINTS DE MERCHANTS
# ===================================================================

@router.get("/merchants", response_model=List[MerchantResponse])
async def list_merchants_endpoint() -> List[MerchantResponse]:
    """
    Listar merchants disponibles para facturación.
    """
    try:
        merchants = list_merchants(is_active=True)
        return [MerchantResponse(**merchant) for merchant in merchants]

    except Exception as e:
        logger.error(f"Error listando merchants: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listando merchants: {str(e)}"
        )


@router.post("/merchants", response_model=MerchantResponse)
async def create_merchant_endpoint(merchant: MerchantCreate) -> MerchantResponse:
    """
    Crear un nuevo merchant para facturación.
    """
    try:
        merchant_id = create_merchant(
            nombre=merchant.nombre,
            metodo_facturacion=merchant.metodo_facturacion,
            metadata=merchant.metadata,
        )

        merchant_data = get_merchant(merchant_id)
        if not merchant_data:
            raise HTTPException(
                status_code=500,
                detail="Error obteniendo merchant creado"
            )

        return MerchantResponse(**merchant_data)

    except Exception as e:
        logger.error(f"Error creando merchant: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creando merchant: {str(e)}"
        )


@router.get("/merchants/{merchant_id}", response_model=MerchantResponse)
async def get_merchant_endpoint(merchant_id: int) -> MerchantResponse:
    """
    Obtener detalles de un merchant específico.
    """
    try:
        merchant = get_merchant(merchant_id)

        if not merchant:
            raise HTTPException(
                status_code=404,
                detail=f"Merchant {merchant_id} no encontrado"
            )

        return MerchantResponse(**merchant)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo merchant {merchant_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo merchant: {str(e)}"
        )


# ===================================================================
# ENDPOINTS DE JOBS
# ===================================================================

@router.get("/jobs", response_model=Dict[str, Any])
async def list_jobs_endpoint(
    company_id: str = "default",
    limit: int = 50
) -> Dict[str, Any]:
    """
    Listar jobs de facturación pendientes y completados.
    """
    try:
        jobs = list_pending_jobs(company_id)

        return {
            "success": True,
            "total": len(jobs),
            "jobs": jobs,
            "company_id": company_id,
        }

    except Exception as e:
        logger.error(f"Error listando jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listando jobs: {str(e)}"
        )


@router.post("/jobs/{job_id}/process", response_model=Dict[str, Any])
async def process_job_manually(job_id: int) -> Dict[str, Any]:
    """
    Procesar un job específico manualmente.

    Útil para debug o reprocesamiento.
    """
    try:
        worker = InvoicingWorker()
        result = await worker.process_job(job_id)

        return {
            "success": True,
            "job_id": job_id,
            "result": result,
            "message": "Job procesado manualmente",
        }

    except Exception as e:
        logger.error(f"Error procesando job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando job: {str(e)}"
        )


# ===================================================================
# ENDPOINTS DE PROCESAMIENTO
# ===================================================================

@router.post("/tickets/{ticket_id}/create-expense", response_model=Dict[str, Any])
async def create_expense_from_ticket_endpoint(ticket_id: int) -> Dict[str, Any]:
    """
    Crear un expense record a partir de un ticket procesado.
    """
    try:
        expense_id = create_expense_from_ticket(ticket_id)

        if not expense_id:
            raise HTTPException(
                status_code=400,
                detail="No se pudo crear el gasto. Verifica que el ticket esté procesado correctamente."
            )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "expense_id": expense_id,
            "message": "Gasto creado exitosamente desde el ticket",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando gasto desde ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creando gasto: {str(e)}"
        )


# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def _determine_processing_status(ticket: Dict[str, Any], jobs: List[Dict[str, Any]]) -> str:
    """Determinar el estado de procesamiento de un ticket."""
    if ticket["estado"] == "procesado":
        return "completado"
    elif ticket["estado"] == "error":
        return "error"
    elif jobs:
        job_states = [job["estado"] for job in jobs]
        if "procesando" in job_states:
            return "procesando"
        elif "error" in job_states:
            return "error"
        else:
            return "pendiente"
    else:
        return "sin_jobs"


def _determine_company_from_phone(phone_number: str) -> str:
    """
    Determinar company_id basado en número de teléfono.

    En producción esto sería más sofisticado, consultando una tabla
    de usuarios registrados por teléfono.
    """
    # Implementación simplificada
    return "default"


# ===================================================================
# SEED DATA ENDPOINTS (DESARROLLO)
# ===================================================================

@router.post("/dev/seed-merchants", response_model=Dict[str, Any])
async def seed_merchants() -> Dict[str, Any]:
    """
    Crear merchants de prueba para desarrollo.

    Solo para desarrollo - remover en producción.
    """
    try:
        sample_merchants = [
            {
                "nombre": "OXXO",
                "metodo_facturacion": "portal",
                "metadata": {
                    "url": "https://facturacion.oxxo.com",
                    "requires_login": True,
                    "account_type": "empresa",
                }
            },
            {
                "nombre": "Walmart",
                "metodo_facturacion": "email",
                "metadata": {
                    "email": "facturacion@walmart.com.mx",
                    "subject_format": "Solicitud factura - {rfc}",
                }
            },
            {
                "nombre": "Costco",
                "metodo_facturacion": "api",
                "metadata": {
                    "api_url": "https://api.costco.com.mx/invoicing",
                    "auth_type": "oauth2",
                }
            },
            {
                "nombre": "Home Depot",
                "metodo_facturacion": "portal",
                "metadata": {
                    "url": "https://www.homedepot.com.mx/facturacion",
                    "requires_receipt_code": True,
                }
            }
        ]

        created_merchants = []
        for merchant_data in sample_merchants:
            merchant_id = create_merchant(**merchant_data)
            merchant = get_merchant(merchant_id)
            created_merchants.append(merchant)

        return {
            "success": True,
            "message": f"Se crearon {len(created_merchants)} merchants de prueba",
            "merchants": created_merchants,
        }

    except Exception as e:
        logger.error(f"Error creando merchants de prueba: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creando merchants: {str(e)}"
        )


# ===================================================================
# ENDPOINTS WEB UI
# ===================================================================

@router.get("/dashboard")
async def invoicing_dashboard(request: Request):
    """
    Redirige al dashboard simple unificado.
    Mantiene compatibilidad con URLs existentes.
    """
    # Redirigir permanentemente al dashboard simple
    return RedirectResponse(url="/invoicing/simple", status_code=301)


@router.get("/simple", response_class=HTMLResponse)
async def simple_dashboard(request: Request):
    """
    Dashboard simple sin dependencias de Jinja2.
    """
    from pathlib import Path
    html_path = Path("templates/invoicing/simple-dashboard.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    else:
        return HTMLResponse(content="<h1>Dashboard simple no encontrado</h1>", status_code=200)


# ===================================================================
# ENDPOINTS ESCALABLES (Nueva Arquitectura)
# ===================================================================

@router.post("/v2/tickets/process", response_model=Dict[str, Any])
async def process_ticket_v2(
    ticket_id: int,
    company_id: str = "default",
    priority: str = "normal"
) -> Dict[str, Any]:
    """
    Procesar ticket usando la nueva arquitectura escalable.

    Utiliza OCR Service, Merchant Classifier y Queue Service para
    procesamiento robusto y escalable.
    """
    try:
        # Convertir prioridad
        from modules.invoicing_agent.services.queue_service import JobPriority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "high": JobPriority.HIGH,
            "urgent": JobPriority.URGENT
        }
        job_priority = priority_map.get(priority.lower(), JobPriority.NORMAL)

        # Procesar con orchestrator
        result = await process_ticket(ticket_id, company_id)

        return {
            "success": result.success,
            "ticket_id": result.ticket_id,
            "stage": result.stage.value,
            "processing_time": result.processing_time,
            "requires_human_review": result.requires_human_review,
            "error_message": result.error_message,
            "metadata": result.metadata,
            "details": result.to_dict()
        }

    except Exception as e:
        logger.error(f"Error procesando ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando ticket: {str(e)}"
        )


@router.post("/v2/tickets/batch-process", response_model=Dict[str, Any])
async def batch_process_tickets(
    ticket_ids: List[int],
    company_id: str = "default",
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """
    Procesar múltiples tickets en paralelo usando arquitectura escalable.
    """
    try:
        # Validar límites
        if len(ticket_ids) > 100:
            raise HTTPException(
                status_code=400,
                detail="Máximo 100 tickets por lote"
            )

        if max_concurrent > 10:
            max_concurrent = 10

        # Procesar en lote
        results = await process_multiple_tickets(
            ticket_ids,
            company_id=company_id
        )

        # Generar estadísticas
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        requires_review = sum(1 for r in results if r.requires_human_review)

        return {
            "success": True,
            "total_tickets": len(ticket_ids),
            "processed_successfully": successful,
            "failed": failed,
            "requires_human_review": requires_review,
            "results": [r.to_dict() for r in results],
            "summary": {
                "success_rate": successful / len(results) if results else 0,
                "review_rate": requires_review / len(results) if results else 0,
                "average_processing_time": sum(r.processing_time for r in results) / len(results) if results else 0
            }
        }

    except Exception as e:
        logger.error(f"Error en procesamiento en lote: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en procesamiento en lote: {str(e)}"
        )


@router.get("/v2/tickets/{ticket_id}/status", response_model=Dict[str, Any])
async def get_ticket_processing_status(ticket_id: int) -> Dict[str, Any]:
    """
    Obtener estado detallado del procesamiento de un ticket.

    Incluye información de todas las etapas: OCR, clasificación, cola, automatización.
    """
    try:
        status = await orchestrator.get_processing_status(ticket_id)
        return status

    except Exception as e:
        logger.error(f"Error obteniendo estado de ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo estado: {str(e)}"
        )


@router.get("/v2/system/health", response_model=Dict[str, Any])
async def get_system_health_v2() -> Dict[str, Any]:
    """
    Obtener estado de salud completo del sistema escalable.

    Incluye métricas de OCR Service, Merchant Classifier, Queue Service y Orchestrator.
    """
    try:
        health = await get_system_health()
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "health": health
        }

    except Exception as e:
        logger.error(f"Error obteniendo salud del sistema: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo salud del sistema: {str(e)}"
        )


@router.post("/v2/system/initialize", response_model=Dict[str, Any])
async def initialize_system_v2() -> Dict[str, Any]:
    """
    Inicializar servicios escalables.

    Debe llamarse al inicio de la aplicación para configurar todos los servicios.
    """
    try:
        services = await initialize_services()

        return {
            "success": True,
            "message": "Servicios escalables inicializados correctamente",
            "services": {
                "ocr_service": "disponible",
                "merchant_classifier": "disponible",
                "queue_service": "disponible",
                "orchestrator": "disponible"
            }
        }

    except Exception as e:
        logger.error(f"Error inicializando servicios: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error inicializando servicios: {str(e)}"
        )


@router.get("/v2/queue/metrics", response_model=Dict[str, Any])
async def get_queue_metrics() -> Dict[str, Any]:
    """
    Obtener métricas detalladas del sistema de colas.
    """
    try:
        from modules.invoicing_agent.services.queue_service import queue_service

        metrics = await queue_service.get_queue_metrics()

        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "queue_metrics": metrics
        }

    except Exception as e:
        logger.error(f"Error obteniendo métricas de cola: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo métricas: {str(e)}"
        )


@router.post("/v2/workers/start", response_model=Dict[str, Any])
async def start_workers(
    company_id: str = "default",
    num_workers: int = 2
) -> Dict[str, Any]:
    """
    Iniciar workers para procesamiento automático.

    NOTA: Esta función inicia workers en background. En producción
    se recomiendan procesos separados para workers.
    """
    try:
        if num_workers > 5:
            num_workers = 5  # Límite de seguridad

        # En una implementación real, esto debería iniciar procesos separados
        # Por ahora devolvemos información sobre cómo iniciar workers

        return {
            "success": True,
            "message": f"Para iniciar {num_workers} workers, ejecutar:",
            "commands": [
                f"python -m modules.invoicing_agent.services.queue_service {company_id}",
                "# O usar el orchestrator para gestión completa:",
                f"python -c \"import asyncio; from modules.invoicing_agent.services.orchestrator import orchestrator; asyncio.run(orchestrator.start_workers('{company_id}', {num_workers}))\""
            ],
            "note": "En producción, usar procesos separados o contenedores para workers"
        }

    except Exception as e:
        logger.error(f"Error configurando workers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error configurando workers: {str(e)}"
        )


# ===================================================================
# ENDPOINTS DE EXTRACCIÓN DE URLs (Paradigma LATAM)
# ===================================================================

from pydantic import BaseModel

class URLExtractionRequest(BaseModel):
    text: Optional[str] = None
    ticket_id: Optional[int] = None

@router.post("/extract-urls", response_model=Dict[str, Any])
async def extract_urls_from_text(request: URLExtractionRequest) -> Dict[str, Any]:
    """
    Extraer URLs de facturación de texto usando el paradigma URL-driven para LATAM.

    Funciona de dos maneras:
    1. Proporcionar text directamente
    2. Proporcionar ticket_id para extraer del ticket

    Args:
        text: Texto del ticket para analizar (opcional)
        ticket_id: ID del ticket para obtener el texto (opcional)

    Returns:
        Diccionario con URLs encontradas, confianza y metadatos
    """
    try:
        from modules.invoicing_agent.services.url_extractor import url_extractor

        # Obtener texto para analizar
        if request.ticket_id:
            # Obtener texto del ticket
            ticket = get_ticket(request.ticket_id)
            if not ticket:
                raise HTTPException(
                    status_code=404,
                    detail=f"Ticket {request.ticket_id} no encontrado"
                )
            text_to_analyze = ticket.get("raw_data", "") or ticket.get("extracted_text", "")
        elif request.text:
            text_to_analyze = request.text
        else:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar 'text' o 'ticket_id'"
            )

        if not text_to_analyze.strip():
            return {
                "success": True,
                "urls": [],
                "total_found": 0,
                "message": "No hay texto para analizar",
                "method": "no_text"
            }

        # Extraer URLs usando el URL extractor
        logger.info(f"Extrayendo URLs de {'ticket ' + str(request.ticket_id) if request.ticket_id else 'texto directo'}")

        extracted_urls = url_extractor.extract_urls(text_to_analyze)
        best_url = url_extractor.get_best_facturacion_url(text_to_analyze)

        # Convertir a formato para la UI
        urls_data = []
        for url_obj in extracted_urls:
            urls_data.append({
                "url": url_obj.url,
                "confidence": url_obj.confidence,
                "type": url_obj.url_type.value,
                "context": url_obj.context,
                "merchant_hint": url_obj.merchant_hint,
                "method": url_obj.extracted_method,
                "metadata": url_obj.metadata
            })

        # Estadísticas
        high_confidence_count = sum(1 for url in urls_data if url["confidence"] >= 0.9)
        medium_confidence_count = sum(1 for url in urls_data if 0.7 <= url["confidence"] < 0.9)

        result = {
            "success": True,
            "urls": urls_data,
            "total_found": len(urls_data),
            "best_url": {
                "url": best_url.url,
                "confidence": best_url.confidence,
                "merchant_hint": best_url.merchant_hint
            } if best_url else None,
            "statistics": {
                "high_confidence": high_confidence_count,
                "medium_confidence": medium_confidence_count,
                "low_confidence": len(urls_data) - high_confidence_count - medium_confidence_count
            },
            "method": "url_extractor_service",
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "text_length": len(text_to_analyze)
        }

        # Log resultado
        if best_url:
            logger.info(f"✅ URL de facturación encontrada: {best_url.url} (confianza: {best_url.confidence:.3f})")
        else:
            logger.warning("❌ No se encontraron URLs de facturación")

        return result

    except Exception as e:
        logger.error(f"Error extrayendo URLs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extrayendo URLs: {str(e)}"
        )


@router.post("/tickets/{ticket_id}/extract-urls", response_model=Dict[str, Any])
async def extract_urls_from_ticket(ticket_id: int) -> Dict[str, Any]:
    """
    Endpoint específico para extraer URLs de un ticket por ID.

    Para tickets de imagen, hace OCR primero.
    Para tickets de texto, usa el texto directamente.
    """
    try:
        # Obtener datos del ticket
        ticket = get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=404,
                detail=f"Ticket {ticket_id} no encontrado"
            )

        text_to_analyze = ""

        # Determinar si necesitamos OCR
        if ticket.get("tipo") == "imagen":
            # Es una imagen, necesitamos OCR
            logger.info(f"Ticket {ticket_id} es imagen, aplicando OCR...")

            from core.advanced_ocr_service import AdvancedOCRService
            ocr_service = AdvancedOCRService()

            # Aplicar OCR real para todas las imágenes
            try:
                # Crear archivo temporal con la imagen
                import tempfile
                import base64
                import os

                raw_data = ticket.get("raw_data", "")
                if raw_data.startswith("data:image"):
                    base64_data = raw_data.split(",")[1]
                else:
                    base64_data = raw_data

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
                    temp_file.write(base64.b64decode(base64_data))
                    temp_image_path = temp_file.name

                # Aplicar OCR usando Google Vision
                with open(temp_image_path, 'rb') as img_file:
                    img_base64 = base64.b64encode(img_file.read()).decode('utf-8')

                ocr_result = await ocr_service.extract_text_intelligent(
                    img_base64,
                    context_hint="ticket"
                )

                # Limpiar archivo temporal
                try:
                    os.unlink(temp_image_path)
                except:
                    pass

                if ocr_result.error:
                    raise Exception(f"Error en OCR: {ocr_result.error}")

                text_to_analyze = ocr_result.text

            except Exception as ocr_error:
                logger.warning(f"Error en OCR para ticket {ticket_id}: {ocr_error}")
                text_to_analyze = "Error en OCR: No se pudo extraer texto de la imagen"

        else:
            # Es texto, usar directamente
            text_to_analyze = ticket.get("raw_data", "") or ticket.get("extracted_text", "")

        # Ahora extraer URLs del texto
        request = URLExtractionRequest(text=text_to_analyze)
        result = await extract_urls_from_text(request)

        # Analizar el ticket con OpenAI para obtener merchant y categoría
        analysis_result = None
        try:
            from core.ticket_analyzer import analyze_ticket_content

            analysis = await analyze_ticket_content(text_to_analyze)

            analysis_result = {
                "merchant_name": analysis.merchant_name,
                "category": analysis.category,
                "confidence": analysis.confidence
            }

            logger.info(f"Ticket {ticket_id} analizado: {analysis.merchant_name} - {analysis.category}")

        except Exception as e:
            logger.warning(f"Error analizando ticket {ticket_id}: {e}")
            analysis_result = {
                "merchant_name": "Error de Análisis",
                "category": "📦 Otros",
                "confidence": 0.0
            }

        # Agregar metadatos específicos del ticket
        result["ticket_id"] = ticket_id
        result["source"] = "ticket_extraction_with_ocr" if ticket.get("tipo") == "imagen" else "ticket_extraction_text"
        result["extracted_text_preview"] = text_to_analyze  # Texto completo sin truncar

        # Agregar análisis del ticket
        result["analysis"] = analysis_result

        return result

    except HTTPException:
        # Re-levantar errores HTTP tal como están
        raise
    except Exception as e:
        logger.error(f"Error extrayendo URLs del ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extrayendo URLs del ticket: {str(e)}"
        )


@router.get("/url-extraction/health", response_model=Dict[str, Any])
async def get_url_extraction_health() -> Dict[str, Any]:
    """
    Verificar estado de salud del sistema de extracción de URLs.
    """
    try:
        from modules.invoicing_agent.services.url_extractor import url_extractor

        # Test básico de extracción
        test_text = """
        OXXO TIENDA #1234
        RFC: OXX970814HS9
        Total: $45.50
        Solicita tu factura en: https://factura.oxxo.com
        """

        test_urls = url_extractor.extract_urls(test_text)
        test_best = url_extractor.get_best_facturacion_url(test_text)

        return {
            "success": True,
            "status": "healthy",
            "extractor_available": True,
            "known_domains_count": len(url_extractor.known_domains),
            "test_extraction": {
                "urls_found": len(test_urls),
                "best_url_found": test_best.url if test_best else None,
                "test_passed": len(test_urls) > 0 and test_best is not None
            },
            "capabilities": {
                "context_patterns": len(url_extractor.context_patterns),
                "facturacion_patterns": len(url_extractor.facturacion_patterns),
                "supports_multiline": True,
                "supports_domain_reconstruction": True
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error verificando salud de extracción de URLs: {str(e)}")
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }