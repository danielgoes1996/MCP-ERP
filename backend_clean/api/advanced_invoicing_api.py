"""
API Avanzada para Facturación Automática de Tickets
Endpoints de clase mundial para el sistema de facturación automática.
Integra OCR, IA, RPA y automatización completa.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import base64

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

# Imports de nuestros módulos
from core.advanced_ocr_service import extract_text_intelligent, OCRResult
from core.ai_rpa_planner import create_rpa_plan, RPAPlan
from core.playwright_executor import execute_rpa_plan, ExecutionResult
from modules.invoicing_agent.ticket_processor import process_ticket_with_intelligence

logger = logging.getLogger(__name__)

# ===============================================================
# MODELOS PYDANTIC PARA LA API
# ===============================================================

class TicketUploadRequest(BaseModel):
    """Request para subir ticket"""
    source_type: str = Field(..., description="Tipo de fuente: 'image', 'pdf', 'voice', 'email'")
    content: str = Field(..., description="Contenido en base64 o texto")
    company_id: str = Field(..., description="ID de la empresa")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")


class TicketProcessResponse(BaseModel):
    """Respuesta del procesamiento de ticket"""
    ticket_id: str
    processing_status: str
    extracted_data: Dict[str, Any]
    merchant_info: Optional[Dict[str, Any]]
    confidence_score: float
    next_actions: List[str]


class InvoiceAutomationRequest(BaseModel):
    """Request para automatización de facturación"""
    ticket_id: str = Field(..., description="ID del ticket")
    fiscal_data: Dict[str, str] = Field(..., description="Datos fiscales del receptor")
    automation_config: Dict[str, Any] = Field(default_factory=dict, description="Configuración de automatización")
    force_execution: bool = Field(default=False, description="Forzar ejecución sin validaciones")


class InvoiceAutomationResponse(BaseModel):
    """Respuesta de automatización de facturación"""
    job_id: str
    status: str
    estimated_duration_seconds: int
    plan_summary: Dict[str, Any]
    execution_url: str


class JobStatusResponse(BaseModel):
    """Respuesta del estado de job"""
    job_id: str
    status: str
    progress_percentage: float
    current_step: Optional[str]
    steps_completed: int
    total_steps: int
    error_message: Optional[str]
    result_data: Optional[Dict[str, Any]]


class CompanyStatsResponse(BaseModel):
    """Respuesta de estadísticas de empresa"""
    company_id: str
    period: str
    total_tickets: int
    auto_invoiced: int
    manual_review: int
    success_rate: float
    avg_processing_time_ms: int
    top_merchants: List[Dict[str, Any]]


# ===============================================================
# ROUTER PRINCIPAL
# ===============================================================

router = APIRouter(prefix="/api/v1/invoicing", tags=["Advanced Invoicing"])


# ===============================================================
# ENDPOINTS DE CARGA Y PROCESAMIENTO DE TICKETS
# ===============================================================

@router.post("/tickets/upload", response_model=TicketProcessResponse)
async def upload_and_process_ticket(
    request: TicketUploadRequest,
    background_tasks: BackgroundTasks
) -> TicketProcessResponse:
    """
    Subir y procesar ticket para facturación automática.

    Flujo completo:
    1. Validar datos de entrada
    2. Extraer texto con OCR inteligente
    3. Procesar con IA para identificar merchant y datos
    4. Guardar en base de datos
    5. Devolver resultado con próximas acciones
    """

    logger.info(f"Procesando ticket para empresa {request.company_id}")

    try:
        # 1. Generar ID único para el ticket
        ticket_id = str(uuid.uuid4())

        # 2. Procesar según tipo de fuente
        extracted_text = ""
        ocr_result = None

        if request.source_type == "image":
            # Usar OCR inteligente
            ocr_result = await extract_text_intelligent(
                image_data=request.content,
                context_hint="ticket"
            )
            extracted_text = ocr_result.text

        elif request.source_type == "pdf":
            # Procesar PDF (implementar extracción de PDF)
            extracted_text = await _extract_text_from_pdf(request.content)

        elif request.source_type == "voice":
            # Procesar audio (usar speech-to-text)
            extracted_text = await _transcribe_audio(request.content)

        elif request.source_type == "email":
            # Procesar email (extraer contenido relevante)
            extracted_text = await _extract_text_from_email(request.content)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de fuente no soportado: {request.source_type}"
            )

        if not extracted_text:
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer texto del contenido"
            )

        # 3. Procesar con inteligencia artificial
        processed_data = await process_ticket_with_intelligence(extracted_text)

        # 4. Determinar próximas acciones
        next_actions = _determine_next_actions(processed_data)

        # 5. Guardar en base de datos (background task)
        background_tasks.add_task(
            _save_ticket_to_database,
            ticket_id=ticket_id,
            company_id=request.company_id,
            source_type=request.source_type,
            source_content=request.content,
            extracted_text=extracted_text,
            processed_data=processed_data,
            ocr_result=ocr_result,
            metadata=request.metadata
        )

        # 6. Construir respuesta
        response = TicketProcessResponse(
            ticket_id=ticket_id,
            processing_status="processed",
            extracted_data=processed_data.get("extracted_data", {}),
            merchant_info=processed_data.get("merchant"),
            confidence_score=processed_data.get("confidence", 0.0),
            next_actions=next_actions
        )

        logger.info(f"Ticket {ticket_id} procesado exitosamente")
        return response

    except Exception as e:
        logger.error(f"Error procesando ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tickets/{ticket_id}/automate", response_model=InvoiceAutomationResponse)
async def start_invoice_automation(
    ticket_id: str,
    request: InvoiceAutomationRequest,
    background_tasks: BackgroundTasks
) -> InvoiceAutomationResponse:
    """
    Iniciar automatización de facturación para un ticket.

    Flujo:
    1. Validar que el ticket existe y está listo
    2. Obtener credenciales del merchant
    3. Crear plan de automatización con IA
    4. Iniciar ejecución en background
    5. Devolver información del job
    """

    logger.info(f"Iniciando automatización para ticket {ticket_id}")

    try:
        # 1. Obtener información del ticket
        ticket_data = await _get_ticket_from_database(ticket_id)
        if not ticket_data:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        if ticket_data["processing_status"] != "processed":
            raise HTTPException(
                status_code=400,
                detail="Ticket no está listo para automatización"
            )

        # 2. Validar que el merchant es automatizable
        merchant_info = ticket_data.get("merchant_info")
        if not merchant_info or not merchant_info.get("portal"):
            raise HTTPException(
                status_code=400,
                detail="Merchant no tiene portal de automatización configurado"
            )

        # 3. Obtener credenciales del merchant
        credentials = await _get_merchant_credentials(
            company_id=ticket_data["company_id"],
            merchant_id=merchant_info["id"]
        )

        # 4. Preparar datos para automatización
        automation_data = {
            **ticket_data["extracted_data"],
            **request.fiscal_data
        }

        # 5. Crear plan de automatización con IA
        rpa_plan = await create_rpa_plan(
            merchant_name=merchant_info["name"],
            portal_url=merchant_info["portal"],
            ticket_data=automation_data,
            credentials=credentials,
            context="Facturación automática de ticket"
        )

        # 6. Crear job de automatización
        job_id = str(uuid.uuid4())

        # 7. Iniciar ejecución en background
        background_tasks.add_task(
            _execute_automation_job,
            job_id=job_id,
            ticket_id=ticket_id,
            rpa_plan=rpa_plan,
            automation_data=automation_data,
            config=request.automation_config
        )

        # 8. Guardar job en base de datos
        await _create_automation_job(
            job_id=job_id,
            ticket_id=ticket_id,
            company_id=ticket_data["company_id"],
            merchant_id=merchant_info["id"],
            plan=rpa_plan,
            config=request.automation_config
        )

        # 9. Construir respuesta
        response = InvoiceAutomationResponse(
            job_id=job_id,
            status="queued",
            estimated_duration_seconds=rpa_plan.estimated_duration_seconds,
            plan_summary={
                "total_steps": len(rpa_plan.actions),
                "merchant": rpa_plan.merchant_name,
                "portal": rpa_plan.portal_url,
                "confidence": rpa_plan.confidence_score
            },
            execution_url=f"/api/v1/invoicing/jobs/{job_id}/status"
        )

        logger.info(f"Job de automatización {job_id} creado para ticket {ticket_id}")
        return response

    except Exception as e:
        logger.error(f"Error iniciando automatización: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===============================================================
# ENDPOINTS DE MONITOREO DE JOBS
# ===============================================================

@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Obtener estado de un job de automatización"""

    try:
        job_data = await _get_job_from_database(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job no encontrado")

        # Calcular progreso
        progress_percentage = _calculate_job_progress(job_data)

        response = JobStatusResponse(
            job_id=job_id,
            status=job_data["status"],
            progress_percentage=progress_percentage,
            current_step=job_data.get("current_step"),
            steps_completed=job_data.get("steps_completed", 0),
            total_steps=job_data.get("total_steps", 0),
            error_message=job_data.get("error_message"),
            result_data=job_data.get("result_data")
        )

        return response

    except Exception as e:
        logger.error(f"Error obteniendo estado del job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str, limit: int = 100):
    """Obtener logs detallados de un job"""

    try:
        logs = await _get_job_logs_from_database(job_id, limit)
        return {"job_id": job_id, "logs": logs}

    except Exception as e:
        logger.error(f"Error obteniendo logs del job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/screenshots")
async def get_job_screenshots(job_id: str):
    """Obtener capturas de pantalla de un job"""

    try:
        screenshots = await _get_job_screenshots_from_database(job_id)
        return {"job_id": job_id, "screenshots": screenshots}

    except Exception as e:
        logger.error(f"Error obteniendo screenshots del job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/download/{file_name}")
async def download_job_file(job_id: str, file_name: str):
    """Descargar archivo generado por un job (CFDI, PDF, etc.)"""

    try:
        file_path = await _get_job_file_path(job_id, file_name)
        if not file_path or not Path(file_path).exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/octet-stream"
        )

    except Exception as e:
        logger.error(f"Error descargando archivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===============================================================
# ENDPOINTS DE ESTADÍSTICAS Y DASHBOARD
# ===============================================================

@router.get("/companies/{company_id}/stats", response_model=CompanyStatsResponse)
async def get_company_stats(
    company_id: str,
    period: str = "last_30_days"
) -> CompanyStatsResponse:
    """Obtener estadísticas de facturación de una empresa"""

    try:
        stats = await _calculate_company_stats(company_id, period)

        response = CompanyStatsResponse(
            company_id=company_id,
            period=period,
            total_tickets=stats["total_tickets"],
            auto_invoiced=stats["auto_invoiced"],
            manual_review=stats["manual_review"],
            success_rate=stats["success_rate"],
            avg_processing_time_ms=stats["avg_processing_time_ms"],
            top_merchants=stats["top_merchants"]
        )

        return response

    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/merchants/{merchant_id}/analytics")
async def get_merchant_analytics(merchant_id: str):
    """Obtener analíticas de un merchant específico"""

    try:
        analytics = await _get_merchant_analytics(merchant_id)
        return analytics

    except Exception as e:
        logger.error(f"Error obteniendo analíticas del merchant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===============================================================
# ENDPOINTS DE CONFIGURACIÓN
# ===============================================================

@router.post("/merchants/{merchant_id}/credentials")
async def update_merchant_credentials(
    merchant_id: str,
    company_id: str,
    credentials: Dict[str, str]
):
    """Actualizar credenciales de un merchant"""

    try:
        await _save_merchant_credentials(company_id, merchant_id, credentials)
        return {"message": "Credenciales actualizadas exitosamente"}

    except Exception as e:
        logger.error(f"Error actualizando credenciales: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/merchants/{merchant_id}/test-portal")
async def test_merchant_portal(merchant_id: str):
    """Probar conectividad con el portal de un merchant"""

    try:
        test_result = await _test_merchant_portal_connectivity(merchant_id)
        return test_result

    except Exception as e:
        logger.error(f"Error probando portal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===============================================================
# FUNCIONES DE UTILIDAD
# ===============================================================

async def _extract_text_from_pdf(base64_pdf: str) -> str:
    """Extraer texto de PDF"""
    # Implementación de extracción de PDF
    # Por ahora, simulación
    return "Contenido simulado de PDF"


async def _transcribe_audio(base64_audio: str) -> str:
    """Transcribir audio a texto"""
    # Implementación de speech-to-text
    # Por ahora, simulación
    return "Transcripción simulada de audio"


async def _extract_text_from_email(email_content: str) -> str:
    """Extraer texto relevante de email"""
    # Implementación de parsing de email
    # Por ahora, retornar contenido directo
    return email_content


def _determine_next_actions(processed_data: Dict[str, Any]) -> List[str]:
    """Determinar próximas acciones basadas en datos procesados"""

    actions = []
    call_to_action = processed_data.get("call_to_action", {})

    if call_to_action.get("can_auto_process"):
        actions.append("auto_invoice")
    else:
        actions.append("manual_review")

    if processed_data.get("confidence", 0) < 0.8:
        actions.append("verify_data")

    return actions


async def _save_ticket_to_database(
    ticket_id: str,
    company_id: str,
    source_type: str,
    source_content: str,
    extracted_text: str,
    processed_data: Dict[str, Any],
    ocr_result: Optional[OCRResult],
    metadata: Dict[str, Any]
):
    """Guardar ticket en base de datos"""

    # Implementar guardado en base de datos
    logger.info(f"Guardando ticket {ticket_id} en base de datos")

    # Por ahora, solo log
    ticket_data = {
        "id": ticket_id,
        "company_id": company_id,
        "source_type": source_type,
        "extracted_text": extracted_text,
        "processed_data": processed_data,
        "created_at": datetime.utcnow().isoformat()
    }

    logger.info(f"Ticket guardado: {json.dumps(ticket_data, indent=2)}")


async def _get_ticket_from_database(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Obtener ticket de base de datos"""

    # Implementar obtención de base de datos
    # Por ahora, simulación
    return {
        "id": ticket_id,
        "company_id": "test_company",
        "processing_status": "processed",
        "extracted_data": {
            "folio": "123456",
            "total": 100.0,
            "fecha": "2025-01-19"
        },
        "merchant_info": {
            "id": "merchant_001",
            "name": "Test Merchant",
            "portal": "https://test-portal.com"
        }
    }


async def _get_merchant_credentials(company_id: str, merchant_id: str) -> Dict[str, str]:
    """Obtener credenciales de merchant"""

    # Implementar obtención de credenciales seguras
    # Por ahora, simulación
    return {
        "username": "test_user",
        "password": "test_password"
    }


async def _execute_automation_job(
    job_id: str,
    ticket_id: str,
    rpa_plan: RPAPlan,
    automation_data: Dict[str, Any],
    config: Dict[str, Any]
):
    """Ejecutar job de automatización en background"""

    logger.info(f"Ejecutando job {job_id} para ticket {ticket_id}")

    try:
        # Actualizar estado del job
        await _update_job_status(job_id, "running")

        # Ejecutar plan RPA
        execution_result = await execute_rpa_plan(
            plan=rpa_plan,
            input_data=automation_data,
            config=config
        )

        # Procesar resultado
        if execution_result.status.value == "completed":
            await _update_job_status(job_id, "completed", execution_result)
            await _process_automation_success(ticket_id, execution_result)
        else:
            await _update_job_status(job_id, "failed", execution_result)

        logger.info(f"Job {job_id} completado con estado: {execution_result.status.value}")

    except Exception as e:
        logger.error(f"Error ejecutando job {job_id}: {e}")
        await _update_job_status(job_id, "error", error_message=str(e))


async def _create_automation_job(
    job_id: str,
    ticket_id: str,
    company_id: str,
    merchant_id: str,
    plan: RPAPlan,
    config: Dict[str, Any]
):
    """Crear job en base de datos"""

    # Implementar creación en base de datos
    logger.info(f"Creando job {job_id} en base de datos")


async def _get_job_from_database(job_id: str) -> Optional[Dict[str, Any]]:
    """Obtener job de base de datos"""

    # Implementar obtención de base de datos
    # Por ahora, simulación
    return {
        "id": job_id,
        "status": "running",
        "steps_completed": 3,
        "total_steps": 10,
        "current_step": "Llenando formulario de facturación"
    }


def _calculate_job_progress(job_data: Dict[str, Any]) -> float:
    """Calcular progreso del job"""

    total_steps = job_data.get("total_steps", 0)
    completed_steps = job_data.get("steps_completed", 0)

    if total_steps == 0:
        return 0.0

    return (completed_steps / total_steps) * 100.0


async def _get_job_logs_from_database(job_id: str, limit: int) -> List[Dict[str, Any]]:
    """Obtener logs del job"""

    # Implementar obtención de logs
    return [
        {"timestamp": "2025-01-19T10:00:00Z", "level": "INFO", "message": "Job iniciado"},
        {"timestamp": "2025-01-19T10:01:00Z", "level": "INFO", "message": "Navegando al portal"},
        {"timestamp": "2025-01-19T10:02:00Z", "level": "INFO", "message": "Llenando formulario"}
    ]


async def _get_job_screenshots_from_database(job_id: str) -> List[Dict[str, Any]]:
    """Obtener screenshots del job"""

    # Implementar obtención de screenshots
    return [
        {"step": 1, "description": "Página inicial", "url": f"/api/v1/invoicing/jobs/{job_id}/download/screenshot_1.png"},
        {"step": 5, "description": "Formulario llenado", "url": f"/api/v1/invoicing/jobs/{job_id}/download/screenshot_5.png"}
    ]


async def _get_job_file_path(job_id: str, file_name: str) -> Optional[str]:
    """Obtener path de archivo del job"""

    # Implementar obtención de path
    base_path = Path("automation_downloads") / job_id
    file_path = base_path / file_name

    if file_path.exists():
        return str(file_path)

    return None


async def _calculate_company_stats(company_id: str, period: str) -> Dict[str, Any]:
    """Calcular estadísticas de empresa"""

    # Implementar cálculo de estadísticas
    return {
        "total_tickets": 150,
        "auto_invoiced": 120,
        "manual_review": 30,
        "success_rate": 80.0,
        "avg_processing_time_ms": 45000,
        "top_merchants": [
            {"name": "OXXO", "tickets": 50, "success_rate": 95.0},
            {"name": "Walmart", "tickets": 30, "success_rate": 85.0}
        ]
    }


async def _get_merchant_analytics(merchant_id: str) -> Dict[str, Any]:
    """Obtener analíticas de merchant"""

    # Implementar obtención de analíticas
    return {
        "merchant_id": merchant_id,
        "total_automations": 100,
        "success_rate": 85.0,
        "avg_duration_seconds": 60,
        "common_errors": [
            {"error": "Timeout en formulario", "count": 5},
            {"error": "Campo RFC no encontrado", "count": 3}
        ]
    }


async def _save_merchant_credentials(
    company_id: str,
    merchant_id: str,
    credentials: Dict[str, str]
):
    """Guardar credenciales de merchant"""

    # Implementar guardado seguro de credenciales
    logger.info(f"Guardando credenciales para merchant {merchant_id}")


async def _test_merchant_portal_connectivity(merchant_id: str) -> Dict[str, Any]:
    """Probar conectividad con portal de merchant"""

    # Implementar prueba de conectividad
    return {
        "merchant_id": merchant_id,
        "status": "online",
        "response_time_ms": 250,
        "last_check": datetime.utcnow().isoformat()
    }


async def _update_job_status(
    job_id: str,
    status: str,
    execution_result: Optional[ExecutionResult] = None,
    error_message: Optional[str] = None
):
    """Actualizar estado del job"""

    # Implementar actualización en base de datos
    logger.info(f"Actualizando job {job_id} a estado: {status}")


async def _process_automation_success(
    ticket_id: str,
    execution_result: ExecutionResult
):
    """Procesar resultado exitoso de automatización"""

    # Implementar procesamiento de éxito
    logger.info(f"Procesando éxito de automatización para ticket {ticket_id}")


# ===============================================================
# CONFIGURACIÓN DEL ROUTER
# ===============================================================

# El router se puede incluir en main.py con:
# app.include_router(router)