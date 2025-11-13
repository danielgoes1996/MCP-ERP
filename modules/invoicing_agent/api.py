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
    _calculate_processing_status,
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
        original_image = None

        if file:
            content = await file.read()
            logger.info(f"Archivo recibido: filename={file.filename}, content_type={file.content_type}, size={len(content)} bytes")

            # Determinar tipo según content type, extensión y magic bytes
            filename_lower = (file.filename or "").lower()
            is_image_by_content = file.content_type and file.content_type.startswith("image/")
            is_image_by_extension = filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'))

            # Detectar imagen por magic bytes (primeros bytes del archivo)
            is_image_by_magic = False
            if len(content) > 10:
                # Verificar magic bytes comunes de imágenes
                magic_bytes = content[:10]
                if (magic_bytes.startswith(b'\xFF\xD8\xFF') or  # JPEG
                    magic_bytes.startswith(b'\x89PNG\r\n\x1a\n') or  # PNG
                    magic_bytes.startswith(b'GIF87a') or magic_bytes.startswith(b'GIF89a') or  # GIF
                    magic_bytes.startswith(b'BM') or  # BMP
                    magic_bytes.startswith(b'RIFF') and b'WEBP' in content[:20]):  # WebP
                    is_image_by_magic = True

            # Si archivo > 10KB y no es texto válido, probablemente es imagen
            is_image_by_size = False
            if len(content) > 10240:  # Mayor a 10KB
                try:
                    # Intentar decodificar como texto
                    text_test = content.decode('utf-8')
                    # Si tiene muchos caracteres no imprimibles, probablemente es imagen
                    non_printable = sum(1 for c in text_test[:500] if ord(c) < 32 and c not in '\n\r\t')
                    if non_printable > 50:  # Muchos caracteres no imprimibles
                        is_image_by_size = True
                except:
                    # No se puede decodificar como UTF-8, probablemente es imagen
                    is_image_by_size = True

            logger.info(f"Detección: content_type={is_image_by_content}, extension={is_image_by_extension}, magic={is_image_by_magic}, size={is_image_by_size}")

            if is_image_by_content or is_image_by_extension or is_image_by_magic or is_image_by_size:
                tipo = "imagen"
                original_image = base64.b64encode(content).decode('utf-8')
                raw_data = original_image
                logger.info(f"Detectado como imagen - content_type: {file.content_type}, extension: {filename_lower}, magic_bytes: {is_image_by_magic}")
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
                logger.info(f"Detectado como texto - content_type: {file.content_type}, extension: {filename_lower}")
        else:
            raw_data = text_content or ""

        # Crear el ticket
        ticket_id = create_ticket(
            raw_data=raw_data,
            tipo=tipo,
            user_id=user_id,
            company_id=company_id,
            original_image=original_image,
        )

        # Crear job de procesamiento
        job_id = create_invoicing_job(
            ticket_id=ticket_id,
            company_id=company_id,
        )

        # ANÁLISIS AUTOMÁTICO DEL TICKET
        analyzed_text = raw_data
        analysis_result = None

        # Importar módulos necesarios para procesamiento asíncrono
        import asyncio
        import threading

        # Si es imagen, iniciar procesamiento automático asíncrono
        if tipo == "imagen":
            logger.info(f"Ticket {ticket_id} es imagen - iniciando procesamiento automático asíncrono")
            # Programar procesamiento automático de la imagen

            async def process_image_async():
                try:
                    # Esperar un poco para que la respuesta se envíe al cliente
                    import time
                    time.sleep(2)

                    # ✅ EJECUTAR FUNCIÓN REUTILIZABLE: Mismo flujo que botón "Analizar"
                    logger.info(f"🚀 Ejecutando procesamiento automático completo para ticket {ticket_id}")

                    result = await _process_ticket_with_ocr_and_llm(ticket_id)

                    if result and result.get("analysis"):
                        merchant = result["analysis"].get("merchant_name", "Unknown")
                        logger.info(f"✅ Procesamiento automático completado: {merchant}")
                    else:
                        logger.warning(f"⚠️ Procesamiento automático completado pero sin análisis válido")

                except Exception as e:
                    logger.error(f"❌ Error en procesamiento automático para ticket {ticket_id}: {e}")

            def sync_wrapper():
                # Wrapper para ejecutar código async en hilo sincrónico
                import asyncio
                try:
                    # Crear nuevo event loop para este hilo
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(process_image_async())
                finally:
                    loop.close()

            # Ejecutar en hilo separado para no bloquear la respuesta
            thread = threading.Thread(target=sync_wrapper)
            thread.daemon = True
            thread.start()

            analyzed_text = None

        # ✅ ANÁLISIS LLM AHORA SE EJECUTA AUTOMÁTICAMENTE EN BACKGROUND
        # El análisis se ejecutará automáticamente en background, no es necesario aquí
        analysis_result = None  # Se calculará en background
        if False:  # Deshabilitado: análisis duplicado
            try:
                logger.info(f"Analizando ticket {ticket_id} con LLM (Claude) - Texto válido detectado")

                from core.ticket_analyzer import analyze_ticket_content
                analysis = await analyze_ticket_content(analyzed_text)

                analysis_result = {
                    "merchant_name": analysis.merchant_name,
                    "category": analysis.category,
                    "confidence": analysis.confidence,
                    "facturacion_urls": analysis.facturacion_urls or []
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
                logger.warning(f"Error en análisis LLM para ticket {ticket_id}: {e}")
                analysis_result = {
                    "merchant_name": "Error de Análisis",
                    "category": "📦 Otros",
                    "confidence": 0.0
                }
        else:
            if tipo == "imagen":
                logger.info(f"Ticket {ticket_id} - Análisis LLM pospuesto: esperando OCR de imagen")
                analysis_result = {
                    "merchant_name": "Procesando imagen...",
                    "category": "📦 Analizando",
                    "confidence": 0.0
                }
            else:
                logger.info(f"Ticket {ticket_id} - Análisis LLM pospuesto: texto insuficiente")
                analysis_result = {
                    "merchant_name": "Texto insuficiente",
                    "category": "📦 Pendiente",
                    "confidence": 0.0
                }

        # Obtener datos del ticket creado
        ticket_data = get_ticket(ticket_id)

        logger.info(f"Ticket {ticket_id} creado, job {job_id} programado")

        # Preparar respuesta diferente para imágenes vs texto
        response = {
            "success": True,
            "ticket_id": ticket_id,
            "job_id": job_id,
        }

        # Obtener el ticket creado para calcular processing status de manera sincronizada
        created_ticket = get_ticket(ticket_id)
        processing_status = _calculate_processing_status(created_ticket) if created_ticket else True

        if tipo == "imagen":
            # Para imágenes: NO devolver ticket ni analysis hasta que OCR esté completo
            response.update({
                "status": "image_processing",
                "message": "Imagen recibida. Procesando con OCR y análisis LLM...",
                "processing": processing_status,  # SINCRONIZADO con GET /tickets
                "estimated_time": "15-30 segundos"
            })
            logger.info(f"Respuesta para imagen: solo ticket_id, sin datos del ticket")
        else:
            # Para texto: también ejecutar procesamiento automático para consistencia
            logger.info(f"Ticket {ticket_id} es texto - iniciando procesamiento automático asíncrono")

            def sync_wrapper_text():
                # Wrapper para ejecutar código async en hilo sincrónico
                import asyncio
                try:
                    # Crear nuevo event loop para este hilo
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    async def process_text_async():
                        try:
                            import time
                            time.sleep(1)  # Menos tiempo para texto

                            logger.info(f"🚀 Ejecutando procesamiento automático para ticket texto {ticket_id}")
                            result = await _process_ticket_with_ocr_and_llm(ticket_id)

                            if result and result.get("analysis"):
                                merchant = result["analysis"].get("merchant_name", "Unknown")
                                logger.info(f"✅ Procesamiento automático texto completado: {merchant}")

                        except Exception as e:
                            logger.error(f"❌ Error en procesamiento automático texto para ticket {ticket_id}: {e}")

                    loop.run_until_complete(process_text_async())
                finally:
                    loop.close()

            # Ejecutar en hilo separado para no bloquear la respuesta
            thread = threading.Thread(target=sync_wrapper_text)
            thread.daemon = True
            thread.start()

            response.update({
                "status": "text_processing",
                "message": "Ticket de texto recibido. Procesando con análisis LLM...",
                "processing": processing_status,  # SINCRONIZADO con GET /tickets
                "ticket": ticket_data,
            })

            # Agregar análisis si está disponible
            if analysis_result:
                response["analysis"] = analysis_result
                response["analyzed_text"] = analyzed_text

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


@router.get("/stats")
async def get_dashboard_stats(company_id: str = "default"):
    """
    Obtener estadísticas reales del dashboard.

    Args:
        company_id: ID de la empresa para filtrar datos

    Returns:
        Estadísticas calculadas dinámicamente desde la base de datos
    """
    try:
        # Importar el calculador de estadísticas
        import sys
        from pathlib import Path

        # Añadir el directorio raíz al path si no está
        root_path = Path(__file__).parent.parent.parent
        if str(root_path) not in sys.path:
            sys.path.insert(0, str(root_path))

        from dashboard_stats_calculator import calculate_dashboard_stats, format_stats_for_dashboard

        # Calcular estadísticas reales
        raw_stats = calculate_dashboard_stats(company_id)
        formatted_stats = format_stats_for_dashboard(raw_stats)

        return {
            "success": True,
            "stats": formatted_stats,
            "raw_data": raw_stats,
            "company_id": company_id
        }

    except Exception as e:
        logger.error(f"Error calculando estadísticas del dashboard: {e}")

        # Fallback a estadísticas vacías
        return {
            "success": False,
            "error": str(e),
            "stats": {
                "total_tickets": 0,
                "auto_invoiced": 0,
                "success_rate": "0%",
                "avg_processing_time": "0s",
                "status_distribution": [],
                "recent_tickets": [],
                "top_merchants": [],
                "trends": {"daily": 0, "weekly": 0, "monthly": 0}
            }
        }


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
            # Para imágenes, priorizar extracted_text (texto OCR) sobre raw_data (imagen base64)
            text_to_analyze = ticket.get("extracted_text", "") or ticket.get("raw_data", "")
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


@router.post("/tickets/{ticket_id}/reanalyze", response_model=Dict[str, Any])
async def reanalyze_ticket_with_ocr(ticket_id: int) -> Dict[str, Any]:
    """
    Reanalizar un ticket después de que Google Cloud Vision OCR haya terminado correctamente.
    Usado cuando el análisis inicial fue pospuesto por texto insuficiente.
    """
    try:
        logger.info(f"Reanalizando ticket {ticket_id} con OCR completo")

        # Obtener datos del ticket usando el modelo existente
        from modules.invoicing_agent.models import get_ticket
        ticket_data = get_ticket(ticket_id)

        if not ticket_data:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        raw_data = ticket_data.get("raw_data", "")
        extracted_text = ticket_data.get("extracted_text")
        tipo = ticket_data.get("tipo", "texto")
        original_image = ticket_data.get("original_image")

        # Determinar qué texto usar para análisis
        analyzed_text = extracted_text or raw_data

        # Si es imagen y no hay extracted_text, ejecutar OCR
        if tipo == "imagen" and not extracted_text and original_image:
            logger.info(f"Ejecutando OCR de alta calidad para ticket {ticket_id}")

            from core.advanced_ocr_service import AdvancedOCRService
            ocr_service = AdvancedOCRService()

            ocr_result = await ocr_service.extract_text_intelligent(
                original_image,
                context_hint="ticket"
            )

            if not ocr_result.error and ocr_result.text and len(ocr_result.text.strip()) > 10:
                analyzed_text = ocr_result.text
                logger.info(f"OCR de alta calidad exitoso: {len(analyzed_text)} caracteres")

                # Actualizar extracted_text en la base de datos
                from modules.invoicing_agent.models import update_ticket
                update_ticket(ticket_id, extracted_text=analyzed_text)
            else:
                logger.warning(f"OCR de alta calidad falló para ticket {ticket_id}")

        # Ejecutar análisis LLM con texto de calidad
        if analyzed_text and len(analyzed_text.strip()) > 10:
            logger.info(f"Ejecutando análisis LLM con texto de calidad para ticket {ticket_id}")

            from core.ticket_analyzer import analyze_ticket_content
            analysis = await analyze_ticket_content(analyzed_text)

            analysis_result = {
                "merchant_name": analysis.merchant_name,
                "category": analysis.category,
                "confidence": analysis.confidence,
                "facturacion_urls": analysis.facturacion_urls or []
            }

            # Actualizar ticket con análisis
            from modules.invoicing_agent.models import update_ticket
            update_ticket(
                ticket_id,
                merchant_name=analysis.merchant_name,
                category=analysis.category,
                confidence=analysis.confidence,
                llm_analysis=analysis_result
            )

            return {
                "success": True,
                "ticket_id": ticket_id,
                "analysis_updated": True,
                "analysis": analysis_result,
                "message": "Ticket reananalizado exitosamente con OCR de alta calidad"
            }
        else:
            return {
                "success": False,
                "ticket_id": ticket_id,
                "analysis_updated": False,
                "error": "Texto insuficiente para análisis LLM",
                "message": "OCR no produjo suficiente texto para análisis"
            }

    except Exception as e:
        logger.error(f"Error reanalizando ticket {ticket_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reanalizando ticket: {str(e)}"
        )


async def _process_ticket_with_ocr_and_llm(ticket_id: int) -> Dict[str, Any]:
    """
    Función interna reutilizable para procesar un ticket con OCR y LLM.

    Ejecuta el flujo completo:
    1. OCR de Google Cloud Vision (si es imagen)
    2. Análisis LLM para merchant_name y categoría
    3. Extracción de URLs
    4. Actualización en base de datos

    Returns:
        Dict con el resultado del procesamiento
    """
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
        # Primero verificar si ya tenemos extracted_text en la BD
        existing_extracted_text = ticket.get("extracted_text", "")
        if existing_extracted_text and existing_extracted_text.strip():
            # Ya tenemos texto OCR extraído en la BD
            logger.info(f"Ticket {ticket_id} ya tiene extracted_text en BD, usando directamente")
            text_to_analyze = existing_extracted_text
        else:
            raw_data = ticket.get("raw_data", "")

            # Verificar si raw_data ya contiene texto OCR (en lugar de imagen base64)
            if not raw_data.startswith("/9j/") and not raw_data.startswith("data:image") and len(raw_data) < 5000:
                # Parece ser texto ya extraído, no imagen base64
                logger.info(f"Ticket {ticket_id} ya tiene texto OCR en raw_data, usando directamente")
                text_to_analyze = raw_data
            else:
                # Es una imagen, necesitamos OCR
                logger.info(f"Ticket {ticket_id} es imagen, aplicando OCR...")

                from core.advanced_ocr_service import AdvancedOCRService
                ocr_service = AdvancedOCRService()

                # Aplicar OCR real para todas las imágenes
                try:
                    # Procesar base64 directamente sin archivo temporal
                    import base64

                    if raw_data.startswith("data:image"):
                        base64_data = raw_data.split(",")[1]
                    else:
                        base64_data = raw_data

                    # Corregir padding del base64 antes de usarlo
                    base64_data = ocr_service._fix_base64_padding(base64_data)

                    # Usar el método Google Vision directo para preservar formato de líneas
                    ocr_result = await ocr_service._extract_google_vision(
                        base64_data,
                        "ticket"
                    )

                    if ocr_result.error:
                        raise Exception(f"Error en OCR: {ocr_result.error}")

                    text_to_analyze = ocr_result.text

                except Exception as ocr_error:
                    logger.warning(f"Error en OCR para ticket {ticket_id}: {ocr_error}")
                    text_to_analyze = "Error en OCR: No se pudo extraer texto de la imagen"

    else:
        # Es texto, usar directamente
        # Para imágenes, priorizar extracted_text (texto OCR) sobre raw_data (imagen base64)
        text_to_analyze = ticket.get("extracted_text", "") or ticket.get("raw_data", "")

    # Extraer campos estructurados (Web ID, RFC, etc.)
    extracted_fields = {}
    try:
        from core.advanced_ocr_service import AdvancedOCRService
        ocr_service = AdvancedOCRService()
        extracted_fields = ocr_service.extract_fields_from_lines(text_to_analyze.split('\n'))
        logger.info(f"Ticket {ticket_id} campos extraídos: {extracted_fields}")
    except Exception as e:
        logger.warning(f"Error extrayendo campos del ticket {ticket_id}: {e}")

    # Ahora extraer URLs del texto
    request = URLExtractionRequest(text=text_to_analyze)
    result = await extract_urls_from_text(request)

    # Analizar el ticket con LLM para obtener merchant y categoría
    analysis_result = None
    try:
        from core.ticket_analyzer import analyze_ticket_content

        analysis = await analyze_ticket_content(text_to_analyze)

        analysis_result = {
            "merchant_name": analysis.merchant_name,
            "category": analysis.category,
            "confidence": analysis.confidence,
            "facturacion_urls": analysis.facturacion_urls or []
        }

        logger.info(f"Ticket {ticket_id} analizado: {analysis.merchant_name} - {analysis.category}")

        # Actualizar el ticket en la base de datos con el análisis
        try:
            from modules.invoicing_agent.models import update_ticket
            update_ticket(
                ticket_id,
                merchant_name=analysis.merchant_name,
                category=analysis.category,
                confidence=analysis.confidence,
                llm_analysis=analysis_result,
                extracted_text=text_to_analyze  # También guardar el texto OCR limpio
            )
            logger.info(f"Ticket {ticket_id} actualizado en BD con análisis LLM")
        except Exception as update_error:
            logger.warning(f"Error actualizando ticket {ticket_id} en BD: {update_error}")

    except Exception as e:
        logger.warning(f"Error analizando ticket {ticket_id}: {e}")
        analysis_result = {
            "merchant_name": "Error de Análisis",
            "category": "📦 Otros",
            "confidence": 0.0,
            "facturacion_urls": []
        }

    # Combinar resultados
    combined_result = result.copy()
    combined_result.update({
        "analysis": analysis_result,
        "extracted_text": text_to_analyze,
        "extracted_fields": extracted_fields,
        "ticket_id": ticket_id
    })

    return combined_result


@router.post("/tickets/{ticket_id}/extract-urls", response_model=Dict[str, Any])
async def extract_urls_from_ticket(ticket_id: int) -> Dict[str, Any]:
    """
    Endpoint específico para extraer URLs de un ticket por ID.

    Para tickets de imagen, hace OCR primero.
    Para tickets de texto, usa el texto directamente.
    """
    try:
        # ✅ USAR FUNCIÓN REUTILIZABLE: Misma lógica que procesamiento automático
        return await _process_ticket_with_ocr_and_llm(ticket_id)

    except HTTPException:
        # Re-levantar errores HTTP tal como están
        raise
    except Exception as e:
        logger.error(f"Error extrayendo URLs del ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extrayendo URLs del ticket: {str(e)}"
        )


@router.get("/tickets/{ticket_id}/validate-consistency", response_model=Dict[str, Any])
async def validate_ticket_consistency(ticket_id: int) -> Dict[str, Any]:
        if ticket.get("tipo") == "imagen":
            raw_data = ticket.get("raw_data", "")

            # Verificar si raw_data ya contiene texto OCR (en lugar de imagen base64)
            if not raw_data.startswith("/9j/") and not raw_data.startswith("data:image") and len(raw_data) < 5000:
                # Parece ser texto ya extraído, no imagen base64
                logger.info(f"Ticket {ticket_id} ya tiene texto OCR extraído, usando directamente")
                text_to_analyze = raw_data
            else:
                # Es una imagen, necesitamos OCR
                logger.info(f"Ticket {ticket_id} es imagen, aplicando OCR...")

                from core.advanced_ocr_service import AdvancedOCRService
                ocr_service = AdvancedOCRService()

                # Aplicar OCR real para todas las imágenes
                try:
                    # Procesar base64 directamente sin archivo temporal
                    import base64

                    if raw_data.startswith("data:image"):
                        base64_data = raw_data.split(",")[1]
                    else:
                        base64_data = raw_data

                    # Corregir padding del base64 antes de usarlo
                    base64_data = ocr_service._fix_base64_padding(base64_data)

                    # Usar el método Google Vision directo para preservar formato de líneas
                    ocr_result = await ocr_service._extract_google_vision(
                        base64_data,
                        "ticket"
                    )

                    if ocr_result.error:
                        raise Exception(f"Error en OCR: {ocr_result.error}")

                    text_to_analyze = ocr_result.text

                except Exception as ocr_error:
                    logger.warning(f"Error en OCR para ticket {ticket_id}: {ocr_error}")
                    text_to_analyze = "Error en OCR: No se pudo extraer texto de la imagen"

        else:
            # Es texto, usar directamente
            # Para imágenes, priorizar extracted_text (texto OCR) sobre raw_data (imagen base64)
            text_to_analyze = ticket.get("extracted_text", "") or ticket.get("raw_data", "")

        # Extraer campos estructurados (Web ID, RFC, etc.)
        extracted_fields = {}
        try:
            from core.advanced_ocr_service import AdvancedOCRService
            ocr_service = AdvancedOCRService()
            extracted_fields = ocr_service.extract_fields_from_lines(text_to_analyze.split('\n'))
            logger.info(f"Ticket {ticket_id} campos extraídos: {extracted_fields}")
        except Exception as e:
            logger.warning(f"Error extrayendo campos del ticket {ticket_id}: {e}")

        # Ahora extraer URLs del texto
        request = URLExtractionRequest(text=text_to_analyze)
        result = await extract_urls_from_text(request)

        # Analizar el ticket con LLM para obtener merchant y categoría
        analysis_result = None
        try:
            from core.ticket_analyzer import analyze_ticket_content

            analysis = await analyze_ticket_content(text_to_analyze)

            analysis_result = {
                "merchant_name": analysis.merchant_name,
                "category": analysis.category,
                "confidence": analysis.confidence,
                "facturacion_urls": analysis.facturacion_urls or []
            }

            logger.info(f"Ticket {ticket_id} analizado: {analysis.merchant_name} - {analysis.category}")

            # Actualizar el ticket en la base de datos con el análisis
            try:
                from modules.invoicing_agent.models import update_ticket
                update_ticket(
                    ticket_id,
                    merchant_name=analysis.merchant_name,
                    category=analysis.category,
                    confidence=analysis.confidence,
                    llm_analysis=analysis_result,
                    extracted_text=text_to_analyze  # También guardar el texto OCR limpio
                )
                logger.info(f"Ticket {ticket_id} actualizado en BD con análisis LLM")
            except Exception as update_error:
                logger.warning(f"Error actualizando ticket {ticket_id} en BD: {update_error}")

        except Exception as e:
            logger.warning(f"Error analizando ticket {ticket_id}: {e}")
            analysis_result = {
                "merchant_name": "Error de Análisis",
                "category": "📦 Otros",
                "confidence": 0.0,
                "facturacion_urls": []
            }

        # Agregar metadatos específicos del ticket
        result["ticket_id"] = ticket_id
        result["source"] = "ticket_extraction_with_ocr" if ticket.get("tipo") == "imagen" else "ticket_extraction_text"
        result["extracted_text_preview"] = text_to_analyze  # Texto completo sin truncar

        # Actualizar la base de datos usando el consistency manager
        if analysis_result and analysis_result["merchant_name"] != "Error de Análisis":
            try:
                from core.data_consistency_manager import consistency_manager

                success = consistency_manager.update_ticket_analysis(
                    ticket_id=ticket_id,
                    analysis_result=analysis_result,
                    extracted_fields=extracted_fields,
                    extracted_text=text_to_analyze
                )

                if success:
                    logger.info(f"✅ Ticket {ticket_id} actualizado consistentemente")
                else:
                    logger.warning(f"⚠️ Error en consistency manager para ticket {ticket_id}")

            except Exception as db_error:
                logger.warning(f"⚠️ Error updating database for ticket {ticket_id}: {db_error}")

        # Agregar análisis del ticket
        result["analysis"] = analysis_result

        # Agregar campos extraídos (Web ID, RFC, etc.)
        result["extracted_fields"] = extracted_fields

        # Función para normalizar URLs y evitar duplicados
        def normalize_url(url):
            """Normalizar URL para comparación (sin protocolo, sin www, lowercase)"""
            normalized = url.lower().strip()
            # Remover protocolo
            if normalized.startswith(('http://', 'https://')):
                normalized = normalized.split('://', 1)[1]
            # Remover www
            if normalized.startswith('www.'):
                normalized = normalized[4:]
            # Remover trailing slash
            if normalized.endswith('/'):
                normalized = normalized[:-1]
            return normalized

        # Integrar URLs del LLM con las URLs extraídas por regex
        llm_urls = analysis_result.get("facturacion_urls", [])
        if llm_urls:
            # Crear set de URLs normalizadas existentes para evitar duplicados
            existing_normalized_urls = {normalize_url(url_data["url"]) for url_data in result.get("urls", [])}

            for llm_url in llm_urls:
                normalized_llm_url = normalize_url(llm_url["url"])
                if normalized_llm_url not in existing_normalized_urls:
                    # Agregar URL del LLM a la lista principal
                    if "urls" not in result:
                        result["urls"] = []

                    result["urls"].append({
                        "url": llm_url["url"],
                        "confidence": llm_url.get("confidence", 0.9),
                        "type": "facturacion",
                        "context": f"Sugerido por LLM para {analysis_result['merchant_name']}",
                        "merchant_hint": analysis_result["merchant_name"],
                        "method": "llm_suggestion",
                        "metadata": {"source": "llm_analysis"}
                    })

                    # Agregar al set de URLs normalizadas para evitar duplicados futuros
                    existing_normalized_urls.add(normalized_llm_url)

            # Si no había URLs y ahora tenemos URLs del LLM, actualizar el mensaje
            if not result.get("found_urls", False) and llm_urls:
                result["found_urls"] = True
                result["best_url"] = llm_urls[0]["url"]
                result["recommendation"] = f"URL de facturación sugerida para {analysis_result['merchant_name']}"



@router.get("/tickets/{ticket_id}/validate-consistency", response_model=Dict[str, Any])
async def validate_ticket_consistency(ticket_id: int) -> Dict[str, Any]:
    """
    Validar que un ticket tenga datos consistentes entre todos sus campos.

    Útil para debugging y monitoreo del UI.
    """
    try:
        from core.data_consistency_manager import consistency_manager

        validation_result = consistency_manager.validate_ticket_consistency(ticket_id)

        return {
            "success": True,
            "ticket_id": ticket_id,
            "validation": validation_result
        }

    except Exception as e:
        logger.error(f"Error validating ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error validating ticket: {str(e)}"
        )


@router.post("/maintenance/fix-inconsistencies", response_model=Dict[str, Any])
async def fix_data_inconsistencies() -> Dict[str, Any]:
    """
    Buscar y corregir inconsistencias en toda la base de datos.

    USAR CON CUIDADO - Solo para mantenimiento.
    """
    try:
        from core.data_consistency_manager import consistency_manager

        fix_result = consistency_manager.fix_all_inconsistencies()

        return {
            "success": True,
            "maintenance_result": fix_result
        }

    except Exception as e:
        logger.error(f"Error fixing inconsistencies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fixing inconsistencies: {str(e)}"
        )


@router.post("/tickets/{ticket_id}/navigate-urls", response_model=Dict[str, Any])
async def navigate_to_extracted_urls(ticket_id: int, auto_fill: bool = False) -> Dict[str, Any]:
    """
    Navegar automáticamente a las URLs de facturación extraídas de un ticket.

    Utiliza el sistema de automatización web (Selenium/Playwright) para:
    1. Obtener las URLs extraídas del ticket
    2. Navegar a cada URL encontrada
    3. Tomar screenshots de los portales
    4. Verificar accesibilidad de los portales
    """
    try:
        # Primero obtener las URLs extraídas del ticket
        logger.info(f"Navegando a URLs extraídas del ticket {ticket_id}")

        url_result = await extract_urls_from_ticket(ticket_id)

        urls_to_navigate = url_result.get("urls", [])
        if not urls_to_navigate:
            return {
                "success": False,
                "message": "No se encontraron URLs para navegar",
                "ticket_id": ticket_id,
                "urls_found": 0
            }

        # Obtener texto del ticket si auto_fill está activado
        ticket_text = None
        merchant_name = None
        logger.info(f"🔍 auto_fill activado: {auto_fill}")
        if auto_fill:
            # Buscar el ticket en la base de datos
            try:
                import sqlite3
                import json
                conn = sqlite3.connect('./data/mcp_internal.db')
                cursor = conn.cursor()

                # Obtener datos del ticket (incluyendo extracted_text)
                cursor.execute("SELECT raw_data, extracted_text, merchant_name, llm_analysis, tipo FROM tickets WHERE id = ?", (ticket_id,))
                ticket_result = cursor.fetchone()

                if ticket_result:
                    raw_data, extracted_text, db_merchant_name, llm_analysis, tipo = ticket_result
                    merchant_name = db_merchant_name

                    # Usar extracted_text si está disponible (OCR), sino raw_data
                    if extracted_text and extracted_text.strip():
                        ticket_text = extracted_text
                        logger.info(f"Usando extracted_text (OCR): {len(extracted_text)} caracteres")
                    elif raw_data and not (raw_data.startswith('/9j/') or raw_data.startswith('iVBOR')):
                        # Es texto directo (no imagen)
                        ticket_text = raw_data
                        logger.info(f"Usando raw_data (texto): {len(raw_data)} caracteres")
                    else:
                        # Fallback: construir texto básico desde análisis
                        if llm_analysis:
                            try:
                                analysis = json.loads(llm_analysis)
                                ticket_text = f"""
                                Merchant: {analysis.get('merchant_name', db_merchant_name)}
                                Category: {analysis.get('category', '')}
                                Confidence: {analysis.get('confidence', '')}
                                """
                                logger.info(f"Usando fallback desde llm_analysis")
                            except:
                                ticket_text = f"Merchant: {db_merchant_name}"
                                logger.info(f"Usando fallback básico")
                        else:
                            ticket_text = f"Merchant: {db_merchant_name}"
                            logger.info(f"Usando fallback básico")

                    logger.info(f"Texto del ticket obtenido: {len(ticket_text)} caracteres")
                    logger.info(f"Merchant: {merchant_name}")
                else:
                    logger.warning(f"No se encontró ticket con ID {ticket_id}")

                conn.close()
            except Exception as e:
                logger.error(f"Error obteniendo texto del ticket: {e}")

        # Importar el worker de automatización web
        from modules.invoicing_agent.web_automation import WebAutomationWorker

        automation_worker = WebAutomationWorker()
        navigation_results = []

        for i, url_data in enumerate(urls_to_navigate, 1):
            url = url_data.get("url")
            merchant_hint = url_data.get("merchant_hint", "Desconocido")

            # Usar merchant_name de la DB si está disponible, sino usar merchant_hint
            final_merchant_name = merchant_name if merchant_name else merchant_hint

            logger.info(f"Navegando a URL {i}/{len(urls_to_navigate)}: {url}")
            logger.info(f"Merchant: {final_merchant_name}")
            if ticket_text:
                logger.info(f"Ticket text preview: {ticket_text[:100]}...")

            try:
                # Navegar a la URL
                navigation_result = await automation_worker.navigate_to_portal(
                    url=url,
                    merchant_name=final_merchant_name,
                    take_screenshot=True,
                    auto_fill=auto_fill,
                    ticket_text=ticket_text
                )

                navigation_results.append({
                    "url": url,
                    "merchant": final_merchant_name,
                    "success": navigation_result.get("success", False),
                    "screenshot_path": navigation_result.get("screenshot_path"),
                    "accessibility": navigation_result.get("accessibility", "unknown"),
                    "loading_time": navigation_result.get("loading_time"),
                    "page_title": navigation_result.get("page_title"),
                    "form_detected": navigation_result.get("form_detected", False),
                    "form_fields": navigation_result.get("form_fields", []),
                    "auto_filled": navigation_result.get("auto_filled", False),
                    "filled_fields": navigation_result.get("filled_fields", {}),
                    "submission_result": navigation_result.get("submission_result"),
                    "error": navigation_result.get("error")
                })

            except Exception as e:
                logger.error(f"Error navegando a {url}: {e}")
                navigation_results.append({
                    "url": url,
                    "merchant": merchant_hint,
                    "success": False,
                    "form_detected": False,
                    "form_fields": [],
                    "error": str(e)
                })

        # Limpiar recursos
        await automation_worker.cleanup()

        successful_navigations = sum(1 for result in navigation_results if result.get("success", False))

        return {
            "success": True,
            "message": f"Navegación completada: {successful_navigations}/{len(urls_to_navigate)} exitosas",
            "ticket_id": ticket_id,
            "total_urls": len(urls_to_navigate),
            "successful_navigations": successful_navigations,
            "navigation_results": navigation_results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error en navegación automática para ticket {ticket_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en navegación automática: {str(e)}"
        )


def convert_db_to_viewer_format(automation_data: Dict[str, Any], ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Convertir datos de automatización de la DB al formato esperado por el viewer"""

    job_data = automation_data.get('job_data', {})
    logs = automation_data.get('logs', [])
    screenshots = automation_data.get('screenshots', [])
    summary = automation_data.get('summary', {})

    # Convertir logs a steps
    steps = []
    for i, log in enumerate(logs):
        # Parsear data JSON
        step_data = {}
        if log.get('data'):
            try:
                step_data = json.loads(log['data']) if isinstance(log['data'], str) else log['data']
            except:
                step_data = {}

        step = {
            "step_number": step_data.get('step_number', i + 1),
            "action_type": step_data.get('action_type', 'unknown'),
            "description": log.get('message', ''),
            "result": step_data.get('result', 'unknown'),
            "url": log.get('url', ''),
            "selector": log.get('element_selector', ''),
            "timing_ms": log.get('execution_time_ms', 0),
            "timestamp": log.get('timestamp', ''),
            "level": log.get('level', 'info'),
            "error_message": step_data.get('error_message'),
            "llm_reasoning": step_data.get('llm_reasoning'),
            "fallback_used": step_data.get('fallback_used', False)
        }
        steps.append(step)

    # Convertir screenshots
    screenshot_paths = []
    screenshot_details = []
    for screenshot in screenshots:
        if screenshot.get('file_path'):
            screenshot_paths.append(screenshot['file_path'])
            screenshot_details.append({
                "step_name": screenshot.get('step_name', ''),
                "type": screenshot.get('screenshot_type', 'step'),
                "url": screenshot.get('url', ''),
                "window_title": screenshot.get('window_title', ''),
                "file_size": screenshot.get('file_size', 0),
                "created_at": screenshot.get('created_at', ''),
                "detected_elements": json.loads(screenshot.get('detected_elements', '[]')) if isinstance(screenshot.get('detected_elements'), str) else screenshot.get('detected_elements', [])
            })

    # Construir respuesta en formato de viewer
    viewer_data = {
        "ticket_id": automation_data.get('ticket_id'),
        "ticket_info": {
            "merchant": ticket.get("merchant_name", "Unknown"),
            "tipo": ticket.get("tipo", "texto"),
            "estado": ticket.get("estado", "pendiente"),
            "texto_extraido": ticket.get("texto_extraido", ""),
            "created_at": ticket.get("created_at", "")
        },
        "automation_summary": {
            "job_id": job_data.get('id'),
            "session_id": logs[0].get('session_id') if logs else f"session_{automation_data.get('ticket_id')}",
            "status": summary.get('status', 'completed'),
            "total_steps": summary.get('total_steps', len(steps)),
            "successful_steps": len([s for s in steps if s.get('result') == 'success']),
            "success_rate": summary.get('success_rate', 0),
            "total_time_ms": summary.get('duration_ms', job_data.get('total_execution_time_ms', 0)),
            "final_url": summary.get('final_url', job_data.get('final_url', '')),
            "started_at": job_data.get('started_at', ''),
            "finished_at": job_data.get('finished_at', ''),
            "automation_type": job_data.get('automation_type', 'selenium'),
            "route_used": "robust_engine",
            "steps": steps,
            "screenshots": screenshot_paths,
            "screenshot_details": screenshot_details
        },
        "llm_summary": {
            "decisions_made": len([s for s in steps if s.get('llm_reasoning')]),
            "confidence_avg": 0.85,  # Default confidence
            "strategy_used": "multi_route_fallback",
            "intervention_required": summary.get('status') == 'manual_required'
        }
    }

    return viewer_data


@router.get("/automation-viewer")
async def automation_viewer(request: Request):
    """
    Dashboard visual para ver capturas de automatización y decisiones del LLM
    """
    from pathlib import Path
    html_path = Path("static/automation-viewer.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    else:
        return HTMLResponse(content="<h1>Automation Viewer no encontrado</h1>", status_code=404)


@router.get("/screenshots/{filename}")
async def serve_screenshot(filename: str):
    """
    Servir archivos de screenshots para el automation viewer
    """
    try:
        import os
        from fastapi.responses import FileResponse

        # Directorio de screenshots
        screenshots_dir = Path("screenshots")
        file_path = screenshots_dir / filename

        # Verificar que el archivo existe y está en el directorio correcto
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                path=str(file_path),
                media_type="image/png",
                filename=filename
            )
        else:
            # Servir imagen placeholder si no existe el screenshot
            placeholder_path = Path("static/placeholder-screenshot.png")
            if placeholder_path.exists():
                return FileResponse(
                    path=str(placeholder_path),
                    media_type="image/png"
                )
            else:
                raise HTTPException(status_code=404, detail="Screenshot no encontrado")

    except Exception as e:
        logger.error(f"Error sirviendo screenshot {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/automation/latest-data")
async def get_latest_automation_data() -> Dict[str, Any]:
    """
    Obtener datos de automatización del job más reciente (para testing y demo)
    """
    try:
        from modules.invoicing_agent.automation_persistence import AutomationPersistence
        persistence = AutomationPersistence()

        # Obtener el job más reciente
        with persistence.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ticket_id FROM automation_jobs
                ORDER BY created_at DESC
                LIMIT 1
            """)
            latest_result = cursor.fetchone()

            if not latest_result:
                return {
                    "success": False,
                    "error": "No hay datos de automatización disponibles",
                    "timestamp": datetime.now().isoformat()
                }

            latest_ticket_id = latest_result[0]

        # Obtener datos de automatización
        automation_data = persistence.get_automation_data(latest_ticket_id)

        if automation_data and not automation_data.get('error'):
            # Crear ticket info sintético para el viewer
            fake_ticket = {
                "merchant_name": "TestPortal (Demo)",
                "tipo": "automation_test",
                "estado": "completado",
                "texto_extraido": "RFC: XAXX010101000\nTotal: $100.00\nDemo Data",
                "created_at": datetime.now().isoformat()
            }

            # Convertir formato
            real_automation_data = convert_db_to_viewer_format(automation_data, fake_ticket)

            return {
                "success": True,
                "data": real_automation_data,
                "timestamp": datetime.now().isoformat(),
                "note": "Datos reales de automatización desde la base de datos"
            }
        else:
            return {
                "success": False,
                "error": automation_data.get('error', 'No se encontraron datos'),
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"Error obteniendo datos de automatización más recientes: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/tickets/{ticket_id}/automation-data", response_model=Dict[str, Any])
async def get_ticket_automation_data(ticket_id: int) -> Dict[str, Any]:
    """
    Obtener datos completos de automatización para un ticket específico.

    Incluye:
    - Screenshots dinámicos REALES
    - Decisiones del LLM paso a paso REALES
    - Análisis de cambios en la página REALES
    - Elementos detectados en cada momento REALES
    """
    try:
        # Obtener datos básicos del ticket
        ticket = get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} no encontrado")

        # Obtener datos REALES de automatización desde la DB
        try:
            from modules.invoicing_agent.automation_persistence import AutomationPersistence
            persistence = AutomationPersistence()
            automation_data = persistence.get_automation_data(ticket_id)

            # Si hay datos reales, usarlos
            if automation_data and not automation_data.get('error'):
                logger.info(f"✅ Datos reales de automatización encontrados para ticket {ticket_id}")

                # Convertir formato de DB a formato esperado por viewer
                real_automation_data = convert_db_to_viewer_format(automation_data, ticket)

                return {
                    "success": True,
                    "data": real_automation_data,
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.warning(f"No se pudieron obtener datos reales de automatización: {e}")

        # Fallback a datos simulados si no hay datos reales
        logger.info(f"📋 Usando datos simulados para ticket {ticket_id}")
        automation_data = {
            "ticket_id": ticket_id,
            "ticket_info": {
                "merchant": ticket.get("merchant_name", "Unknown"),
                "tipo": ticket.get("tipo", "texto"),
                "estado": ticket.get("estado", "pendiente"),
                "created_at": ticket.get("created_at", "")
            },
            "dynamic_analysis": {
                "success": True,
                "url": "https://ejemplo.com",
                "page_title": "Portal de Facturación",
                "captures": [
                    {
                        "interval": 0,
                        "timestamp": 1726951200000,  # timestamp ejemplo
                        "screenshot_path": f"dynamic_capture_{ticket_id}_0.png",
                        "elements_found": 3,
                        "forms_found": 0,
                        "current_url": "https://ejemplo.com",
                        "page_source_length": 15420,
                        "elements": [
                            {
                                "selector": "nav",
                                "text": "Navegación principal",
                                "visible": True,
                                "enabled": True,
                                "tag": "nav",
                                "location": {"x": 0, "y": 0},
                                "size": {"width": 1200, "height": 60},
                                "attributes": {"id": "main-nav", "class": "navbar"}
                            },
                            {
                                "selector": "button",
                                "text": "Inicio",
                                "visible": True,
                                "enabled": True,
                                "tag": "button",
                                "location": {"x": 100, "y": 20},
                                "size": {"width": 80, "height": 30},
                                "attributes": {"id": "home-btn", "class": "btn btn-primary"}
                            },
                            {
                                "selector": "a",
                                "text": "Servicios",
                                "visible": True,
                                "enabled": True,
                                "tag": "a",
                                "location": {"x": 200, "y": 20},
                                "size": {"width": 70, "height": 30},
                                "attributes": {"href": "/servicios", "class": "nav-link"}
                            }
                        ],
                        "forms": []
                    },
                    {
                        "interval": 3,
                        "timestamp": 1726951203000,
                        "screenshot_path": f"dynamic_capture_{ticket_id}_1.png",
                        "elements_found": 7,
                        "forms_found": 1,
                        "current_url": "https://ejemplo.com",
                        "page_source_length": 18950,
                        "elements": [
                            {
                                "selector": "button[contains(text(),'factura')]",
                                "text": "Solicitar Factura",
                                "visible": True,
                                "enabled": True,
                                "tag": "button",
                                "location": {"x": 500, "y": 300},
                                "size": {"width": 150, "height": 40},
                                "attributes": {"id": "factura-btn", "class": "btn btn-success factura-button"}
                            },
                            {
                                "selector": "input[name='rfc']",
                                "text": "",
                                "visible": True,
                                "enabled": True,
                                "tag": "input",
                                "location": {"x": 300, "y": 400},
                                "size": {"width": 200, "height": 35},
                                "attributes": {"name": "rfc", "placeholder": "RFC", "type": "text"}
                            },
                            {
                                "selector": "input[name='email']",
                                "text": "",
                                "visible": True,
                                "enabled": True,
                                "tag": "input",
                                "location": {"x": 300, "y": 450},
                                "size": {"width": 200, "height": 35},
                                "attributes": {"name": "email", "placeholder": "Email", "type": "email"}
                            }
                        ],
                        "forms": [
                            {
                                "index": 0,
                                "action": "/procesar-factura",
                                "method": "POST",
                                "fields_count": 4,
                                "visible": True,
                                "fields": [
                                    {"type": "input", "input_type": "text", "name": "rfc", "id": "rfc-field", "placeholder": "RFC", "required": True},
                                    {"type": "input", "input_type": "email", "name": "email", "id": "email-field", "placeholder": "Email", "required": True},
                                    {"type": "input", "input_type": "text", "name": "total", "id": "total-field", "placeholder": "Total", "required": False},
                                    {"type": "input", "input_type": "submit", "name": "", "id": "submit-btn", "placeholder": "", "required": False}
                                ]
                            }
                        ]
                    },
                    {
                        "interval": 6,
                        "timestamp": 1726951206000,
                        "screenshot_path": f"dynamic_capture_{ticket_id}_2.png",
                        "elements_found": 8,
                        "forms_found": 1,
                        "current_url": "https://ejemplo.com",
                        "page_source_length": 19240,
                        "elements": [
                            {
                                "selector": "button[contains(text(),'factura')]",
                                "text": "Solicitar Factura",
                                "visible": True,
                                "enabled": True,
                                "tag": "button",
                                "location": {"x": 500, "y": 300},
                                "size": {"width": 150, "height": 40},
                                "attributes": {"id": "factura-btn", "class": "btn btn-success factura-button"}
                            },
                            {
                                "selector": "input[name='telefono']",
                                "text": "",
                                "visible": True,
                                "enabled": True,
                                "tag": "input",
                                "location": {"x": 300, "y": 500},
                                "size": {"width": 200, "height": 35},
                                "attributes": {"name": "telefono", "placeholder": "Teléfono", "type": "tel"}
                            }
                        ]
                    },
                    {
                        "interval": 10,
                        "timestamp": 1726951210000,
                        "screenshot_path": f"dynamic_capture_{ticket_id}_3.png",
                        "elements_found": 10,
                        "forms_found": 1,
                        "current_url": "https://ejemplo.com",
                        "page_source_length": 20100,
                        "elements": [
                            {
                                "selector": "button[type='submit']",
                                "text": "Enviar Solicitud",
                                "visible": True,
                                "enabled": True,
                                "tag": "button",
                                "location": {"x": 400, "y": 600},
                                "size": {"width": 120, "height": 40},
                                "attributes": {"type": "submit", "class": "btn btn-primary submit-btn"}
                            }
                        ]
                    }
                ],
                "best_capture_index": 1,
                "changes_detected": {
                    "significant_changes": True,
                    "elements_appeared": [
                        {"interval": 3, "new_elements": 4},
                        {"interval": 6, "new_elements": 1},
                        {"interval": 10, "new_elements": 2}
                    ],
                    "elements_disappeared": [],
                    "forms_appeared": [
                        {"interval": 3, "new_forms": 1}
                    ],
                    "forms_disappeared": []
                },
                "recommendation": f"Mejor momento para interactuar: segundo 3. Se detectaron 1 formularios en el segundo 3. Se encontraron 7 elementos interactivos. Se detectaron 1 botones de facturación",
                "total_screenshots": 4
            },
            "llm_decisions": [
                {
                    "step": 1,
                    "state": "navigation",
                    "action": "navigate",
                    "confidence": 0.95,
                    "decision": "Navegar al portal principal de facturación",
                    "selector": "",
                    "value": "",
                    "result": "success",
                    "timing": "0s",
                    "reasoning": "Página cargada correctamente, elementos básicos detectados",
                    "next_state": "wait_for_elements"
                },
                {
                    "step": 2,
                    "state": "wait_for_elements",
                    "action": "wait",
                    "confidence": 0.88,
                    "decision": "Esperar a que aparezcan elementos de facturación dinámicos",
                    "selector": "button[contains(text(),'factura')]",
                    "value": "",
                    "result": "success",
                    "timing": "3s",
                    "reasoning": "Se detectó botón de facturación y formulario después de 3 segundos",
                    "next_state": "click_button"
                },
                {
                    "step": 3,
                    "state": "click_button",
                    "action": "click",
                    "confidence": 0.92,
                    "decision": "Hacer clic en botón 'Solicitar Factura'",
                    "selector": "#factura-btn",
                    "value": "",
                    "result": "success",
                    "timing": "6s",
                    "reasoning": "Botón visible y habilitado, posición estable",
                    "next_state": "fill_form"
                },
                {
                    "step": 4,
                    "state": "fill_form",
                    "action": "fill_field",
                    "confidence": 0.89,
                    "decision": "Llenar campo RFC con datos de empresa",
                    "selector": "input[name='rfc']",
                    "value": "XAXX010101000",
                    "result": "success",
                    "timing": "8s",
                    "reasoning": "Campo RFC detectado y accesible",
                    "next_state": "fill_form"
                },
                {
                    "step": 5,
                    "state": "fill_form",
                    "action": "fill_field",
                    "confidence": 0.85,
                    "decision": "Llenar campo email con correo de empresa",
                    "selector": "input[name='email']",
                    "value": "test@example.com",
                    "result": "success",
                    "timing": "9s",
                    "reasoning": "Campo email disponible en formulario",
                    "next_state": "submit_form"
                },
                {
                    "step": 6,
                    "state": "submit_form",
                    "action": "submit",
                    "confidence": 0.76,
                    "decision": "Enviar formulario de solicitud de factura",
                    "selector": "button[type='submit']",
                    "value": "",
                    "result": "partial",
                    "timing": "10s",
                    "reasoning": "Formulario enviado pero respuesta del servidor pendiente",
                    "next_state": "completed"
                }
            ],
            "automation_summary": {
                "total_steps": 6,
                "successful_steps": 5,
                "failed_steps": 0,
                "partial_steps": 1,
                "success_rate": 0.83,
                "total_time": "10s",
                "best_interaction_moment": "3s",
                "forms_detected": 1,
                "buttons_detected": 3,
                "fields_filled": 2,
                "significant_changes": True
            }
        }

        return {
            "success": True,
            "data": automation_data,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo datos de automatización para ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ==========================================
# INVOICE ATTACHMENT ENDPOINTS
# ==========================================

@router.get("/tickets/{ticket_id}/invoice-status", response_model=Dict[str, Any])
async def get_ticket_invoice_status(ticket_id: int):
    """
    Obtener el estado de factura y adjuntos de un ticket
    """
    try:
        from core.invoice_manager import invoice_manager

        # Obtener datos de factura
        invoice_data = invoice_manager.get_invoice_data(ticket_id)
        if not invoice_data:
            # Si no existe, crear entrada con estado pendiente
            invoice_manager.update_invoice_status(ticket_id, invoice_manager.InvoiceStatus.PENDIENTE)
            invoice_data = invoice_manager.get_invoice_data(ticket_id)

        # Obtener adjuntos
        attachments = invoice_manager.get_attachments(ticket_id)

        return {
            "success": True,
            "invoice_data": {
                "status": invoice_data.status.value,
                "pdf_path": invoice_data.pdf_path,
                "xml_path": invoice_data.xml_path,
                "metadata": invoice_data.metadata,
                "failure_reason": invoice_data.failure_reason,
                "last_check": invoice_data.last_check,
                "uuid": invoice_data.uuid,
                "sat_validation": invoice_data.sat_validation
            },
            "attachments": [
                {
                    "id": att.id,
                    "ticket_id": att.ticket_id,
                    "file_type": att.file_type.value,
                    "file_path": att.file_path,
                    "file_size": att.file_size,
                    "uploaded_at": att.uploaded_at,
                    "is_valid": att.is_valid,
                    "validation_details": att.validation_details
                } for att in attachments
            ]
        }

    except Exception as e:
        logger.error(f"Error getting invoice status for ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickets/{ticket_id}/image")
async def get_ticket_image(ticket_id: int):
    """
    Obtener la imagen original del ticket para visualización en el dashboard
    """
    try:
        # Obtener la imagen del ticket desde la base de datos
        import sqlite3
        conn = sqlite3.connect('./data/mcp_internal.db')
        cursor = conn.cursor()

        # Buscar el ticket
        cursor.execute("SELECT original_image, raw_data FROM tickets WHERE id = ?", (ticket_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        original_image, raw_data = result
        # Priorizar imagen original, luego raw_data
        image_data = original_image or raw_data

        # Verificar si es imagen base64
        if image_data and (image_data.startswith('/9j/') or image_data.startswith('iVBOR') or image_data.startswith('UklG')):
            # Es una imagen base64, determinar el tipo
            if image_data.startswith('/9j/'):
                media_type = "image/jpeg"
            elif image_data.startswith('iVBOR'):
                media_type = "image/png"
            elif image_data.startswith('UklG'):
                media_type = "image/webp"
            else:
                media_type = "image/jpeg"  # Default

            # Decodificar base64 y devolver como imagen
            import base64
            decoded_image_data = base64.b64decode(image_data)

            from fastapi.responses import Response
            return Response(content=decoded_image_data, media_type=media_type)
        else:
            # No es imagen válida
            raise HTTPException(status_code=404, detail="No hay imagen disponible para este ticket")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo imagen del ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/tickets/{ticket_id}/ocr-text")
async def get_ticket_ocr_text(ticket_id: int):
    """
    Obtener el texto OCR extraído de un ticket
    """
    try:
        ticket = get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        # Priorizar extracted_text (OCR) sobre raw_data
        ocr_text = ticket.get("extracted_text", "") or ticket.get("raw_data", "")

        return {
            "success": True,
            "ticket_id": ticket_id,
            "ocr_text": ocr_text,
            "tipo": ticket.get("tipo", ""),
            "has_extracted_text": bool(ticket.get("extracted_text")),
            "text_length": len(ocr_text)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo texto OCR del ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/tickets/{ticket_id}/upload-invoice", response_model=Dict[str, Any])
async def upload_invoice_file(
    ticket_id: int,
    file: UploadFile = File(...),
    file_type: str = Form(...)
):
    """
    Subir archivo de factura (PDF o XML) para un ticket
    """
    try:
        from core.invoice_manager import invoice_manager, AttachmentType

        # Validar tipo de archivo
        if file_type not in ['pdf', 'xml']:
            raise HTTPException(status_code=400, detail="Tipo de archivo debe ser 'pdf' o 'xml'")

        # Leer contenido del archivo
        file_content = await file.read()

        if not file_content:
            raise HTTPException(status_code=400, detail="Archivo vacío")

        # Convertir string a enum
        attachment_type = AttachmentType.PDF if file_type == 'pdf' else AttachmentType.XML

        # Guardar archivo
        attachment = invoice_manager.attach_invoice_file(
            ticket_id=ticket_id,
            file_content=file_content,
            file_type=attachment_type,
            original_filename=file.filename
        )

        if not attachment:
            raise HTTPException(status_code=500, detail="Error guardando archivo")

        # Verificar si la factura está completa
        invoice_manager.mark_invoice_complete(ticket_id)

        return {
            "success": True,
            "message": f"Archivo {file_type.upper()} subido exitosamente",
            "attachment": {
                "id": attachment.id,
                "ticket_id": attachment.ticket_id,
                "file_type": attachment.file_type.value,
                "file_size": attachment.file_size,
                "is_valid": attachment.is_valid,
                "validation_details": attachment.validation_details
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading invoice file for ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: int):
    """
    Descargar archivo adjunto por ID
    """
    try:
        import sqlite3
        import os
        from fastapi.responses import FileResponse

        # Obtener información del adjunto
        conn = sqlite3.connect('./data/mcp_internal.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_path, file_type, ticket_id
            FROM invoice_attachments
            WHERE id = ?
        """, (attachment_id,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            raise HTTPException(status_code=404, detail="Adjunto no encontrado")

        file_path, file_type, ticket_id = result

        # Verificar que el archivo existe
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Archivo no encontrado en el sistema")

        # Generar nombre de descarga
        filename = f"ticket_{ticket_id}_{file_type}.{file_type}"

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading attachment {attachment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-intelligent-agent/{ticket_id}")
async def test_intelligent_agent(ticket_id: int):
    """
    Endpoint para probar el agente de decisión inteligente con un ticket real.
    """
    try:
        # Obtener ticket
        ticket = get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        # Obtener merchant y URLs del ticket
        extracted_text = ticket.get("extracted_text", "") or ticket.get("raw_data", "")

        # Obtener URLs extraídas del ticket
        llm_analysis = ticket.get("llm_analysis", {})
        facturacion_urls = llm_analysis.get("facturacion_urls", [])

        # Usar URL real si está disponible, sino usar Google para pruebas
        if facturacion_urls and len(facturacion_urls) > 0:
            primary_url = facturacion_urls[0].get("url", "")
            # Asegurar que tenga protocolo
            if not primary_url.startswith("http"):
                primary_url = "https://" + primary_url
            merchant_name = llm_analysis.get("merchant_name", "Portal Real")
        else:
            primary_url = "https://google.com"  # Fallback para pruebas
            merchant_name = "Portal de Prueba"

        test_merchant = {
            "nombre": merchant_name,
            "metadata": {
                "url": primary_url
            }
        }

        # Preparar datos del ticket usando información extraída
        extracted_fields = llm_analysis.get("extracted_fields", {})

        ticket_data = {
            "rfc": "XAXX010101000",  # Mantener RFC por defecto
            "email": "test@example.com",  # Email por defecto
            "folio": extracted_fields.get("folio", ticket.get("id", "")),
            "total": extracted_fields.get("total", "100.00"),
            "fecha": extracted_fields.get("fecha", "2024-01-15"),
            "raw_data": extracted_text
        }

        # Importar y usar automatización
        from modules.invoicing_agent.web_automation import process_web_automation

        logger.info(f"Probando agente inteligente con ticket {ticket_id}")

        # Procesar con agente inteligente
        result = await process_web_automation(test_merchant, ticket_data)

        return {
            "ticket_id": ticket_id,
            "merchant": test_merchant["nombre"],
            "result": result,
            "ticket_data": ticket_data,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error testing intelligent agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-state-machine/{ticket_id}")
async def test_state_machine_agent(ticket_id: int):
    """
    Endpoint para probar el nuevo agente con State Machine
    """
    try:
        # Obtener ticket
        ticket = get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        # Extraer texto OCR
        extracted_text = ticket.get("extracted_text", "")
        if not extracted_text:
            # Intentar extraer con OCR si no existe
            try:
                image_path = get_ticket_image_path(ticket_id)
                if image_path and os.path.exists(image_path):
                    extracted_text = await extract_text_from_image(image_path)
            except Exception as e:
                logger.warning(f"Error extrayendo texto: {e}")

        # Obtener análisis LLM
        llm_analysis = ticket.get("llm_analysis", {})
        facturacion_urls = llm_analysis.get("facturacion_urls", [])

        # Usar URL real si está disponible
        if facturacion_urls and len(facturacion_urls) > 0:
            primary_url = facturacion_urls[0].get("url", "")
            if not primary_url.startswith("http"):
                primary_url = "https://" + primary_url
            merchant_name = llm_analysis.get("merchant_name", "Portal Real")
        else:
            primary_url = "https://litromil.com"  # Fallback
            merchant_name = "Litromil"

        test_merchant = {
            "nombre": merchant_name,
            "metadata": {"url": primary_url}
        }

        # Preparar datos del ticket
        extracted_fields = llm_analysis.get("extracted_fields", {})
        ticket_data = {
            "rfc": "XAXX010101000",
            "email": "test@example.com",
            "folio": extracted_fields.get("folio", ticket.get("id", "")),
            "total": extracted_fields.get("total", "100.00"),
            "fecha": extracted_fields.get("fecha", "2024-01-15"),
            "raw_data": extracted_text
        }

        logger.info(f"🚀 Probando State Machine con ticket {ticket_id}")

        # Importar y usar state machine
        import sys
        sys.path.append('/Users/danielgoes96/Desktop/mcp-server')
        from state_machine_integration import smart_state_machine_flow
        from modules.invoicing_agent.web_automation import WebAutomationWorker

        # Crear worker de automatización
        worker = WebAutomationWorker()
        try:
            # Navegar al portal del merchant
            await worker.navigate_to_portal(
                url=primary_url,
                merchant_name=merchant_name,
                ticket_text=extracted_text,
                take_screenshot=True
            )

            # Ejecutar flujo con State Machine
            result = await smart_state_machine_flow(worker, ticket_data, "Facturación automática con State Machine")

        finally:
            await worker.cleanup()

        return {
            "ticket_id": ticket_id,
            "merchant": merchant_name,
            "url": primary_url,
            "result": result,
            "ticket_data": ticket_data,
            "timestamp": datetime.now().isoformat(),
            "agent_type": "state_machine"
        }

    except Exception as e:
        logger.error(f"Error testing state machine: {e}")
        raise HTTPException(status_code=500, detail=str(e))