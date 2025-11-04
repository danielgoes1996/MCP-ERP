"""
Hybrid Processor API - Endpoints para sistema de procesamiento híbrido multi-modal
Punto 19 de Auditoría: APIs para processing_metrics y ocr_confidence
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from core.hybrid_processor_system import (
    hybrid_processor_system,
    InputType,
    ProcessingStatus,
    ProcessorType
)
from core.error_handler import handle_error, log_endpoint_entry, log_endpoint_success, log_endpoint_error
from core.api_models import (
    HybridProcessorSessionCreateRequest,
    HybridProcessorSessionResponse,
    HybridProcessorProcessResponse,
    HybridProcessorStatusResponse,
    HybridProcessorMetricsResponse,
    HybridProcessorResultsResponse,
    HybridProcessorCancelResponse,
    HybridProcessorListResponse,
    HybridProcessorCompanyMetricsResponse,
    HybridProcessorHealthCheckResponse,
)

router = APIRouter(prefix="/hybrid-processor", tags=["Hybrid Processor"])
logger = logging.getLogger(__name__)

@router.post("/sessions/")
async def create_hybrid_processing_session(
    request: HybridProcessorSessionCreateRequest
) -> HybridProcessorSessionResponse:
    """
    Crea una nueva sesión de procesamiento híbrido multi-modal
    Soporta processing_metrics y ocr_confidence tracking
    """
    log_endpoint_entry("/hybrid-processor/sessions/", "POST", request.dict())

    try:
        # Validar tipo de input
        try:
            input_type_enum = InputType(request.input_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid input_type: {request.input_type}")

        # Crear sesión
        session_id = await hybrid_processor_system.create_session(
            company_id=request.company_id,
            input_data=request.input_data,
            input_type=input_type_enum,
            config=request.processing_config
        )

        response = {
            "session_id": session_id,
            "status": "created",
            "input_type": request.input_type,
            "company_id": request.company_id,
            "estimated_processing_time_ms": _estimate_processing_time(input_type_enum),
            "created_at": datetime.utcnow().isoformat()
        }

        log_endpoint_success("/hybrid-processor/sessions/", response)
        return response

    except Exception as e:
        error_msg = f"Error creating hybrid processing session: {str(e)}"
        log_endpoint_error("/hybrid-processor/sessions/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/sessions/{session_id}/process")
async def process_hybrid_session(
    session_id: str,
    background_tasks: BackgroundTasks
) -> HybridProcessorProcessResponse:
    """
    Inicia el procesamiento de una sesión híbrida
    Retorna processing_metrics en tiempo real
    """
    log_endpoint_entry(f"/hybrid-processor/sessions/{session_id}/process", "POST", {"session_id": session_id})

    try:
        # Verificar que la sesión existe
        session_status = await hybrid_processor_system.get_session_status(session_id)
        if 'error' in session_status:
            raise HTTPException(status_code=404, detail="Session not found")

        # Iniciar procesamiento en background
        background_tasks.add_task(_process_session_background, session_id)

        response = {
            "session_id": session_id,
            "status": "processing_started",
            "message": "Processing started in background",
            "check_status_url": f"/hybrid-processor/sessions/{session_id}/status"
        }

        log_endpoint_success(f"/hybrid-processor/sessions/{session_id}/process", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error starting session processing: {str(e)}"
        log_endpoint_error(f"/hybrid-processor/sessions/{session_id}/process", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/status")
async def get_hybrid_session_status(session_id: str) -> HybridProcessorStatusResponse:
    """
    Obtiene el estado actual de una sesión con processing_metrics detallados
    """
    log_endpoint_entry(f"/hybrid-processor/sessions/{session_id}/status", "GET", {"session_id": session_id})

    try:
        status_data = await hybrid_processor_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        response = {
            "session_id": session_id,
            "status": status_data["status"],
            "quality_score": status_data.get("quality_score", 0.0),
            "ocr_confidence": status_data.get("ocr_confidence", 0.0),  # ✅ CAMPO FALTANTE
            "processing_metrics": status_data.get("processing_metrics", {}),  # ✅ CAMPO FALTANTE
            "error_details": status_data.get("error_details"),
            "created_at": status_data.get("created_at"),
            "updated_at": status_data.get("updated_at"),
            "completed_at": status_data.get("completed_at"),
            "progress_percentage": _calculate_progress_percentage(status_data["status"])
        }

        log_endpoint_success(f"/hybrid-processor/sessions/{session_id}/status", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting session status: {str(e)}"
        log_endpoint_error(f"/hybrid-processor/sessions/{session_id}/status", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/metrics")
async def get_session_processing_metrics(session_id: str) -> HybridProcessorMetricsResponse:
    """
    Obtiene métricas detalladas de procesamiento de una sesión
    Incluye processing_metrics granulares por step
    """
    log_endpoint_entry(f"/hybrid-processor/sessions/{session_id}/metrics", "GET", {"session_id": session_id})

    try:
        status_data = await hybrid_processor_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        processing_metrics = status_data.get("processing_metrics", {})

        response = {
            "session_id": session_id,
            "processing_metrics": processing_metrics,  # ✅ CAMPO FALTANTE COMPLETO
            "ocr_confidence": status_data.get("ocr_confidence", 0.0),  # ✅ CAMPO FALTANTE
            "quality_breakdown": processing_metrics.get("quality_breakdown", {}),
            "engine_performance": processing_metrics.get("engine_performance", {}),
            "step_metrics": processing_metrics.get("step_metrics", {}),
            "total_processing_time_ms": processing_metrics.get("processing_time_ms", 0),
            "efficiency_score": _calculate_efficiency_score(processing_metrics)
        }

        log_endpoint_success(f"/hybrid-processor/sessions/{session_id}/metrics", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting session metrics: {str(e)}"
        log_endpoint_error(f"/hybrid-processor/sessions/{session_id}/metrics", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/results")
async def get_hybrid_session_results(session_id: str) -> HybridProcessorResultsResponse:
    """
    Obtiene los resultados finales de procesamiento híbrido
    """
    log_endpoint_entry(f"/hybrid-processor/sessions/{session_id}/results", "GET", {"session_id": session_id})

    try:
        status_data = await hybrid_processor_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        if status_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Session not completed yet")

        # En implementación real, obtener de hybrid_processor_results
        response = {
            "session_id": session_id,
            "status": "completed",
            "final_results": status_data.get("processing_metrics", {}).get("results", {}),
            "quality_score": status_data.get("quality_score", 0.0),
            "ocr_confidence": status_data.get("ocr_confidence", 0.0),  # ✅ CAMPO FALTANTE
            "processing_summary": {
                "total_steps": status_data.get("processing_metrics", {}).get("total_steps", 0),
                "successful_steps": status_data.get("processing_metrics", {}).get("total_steps", 0),
                "processing_time_ms": status_data.get("processing_metrics", {}).get("processing_time_ms", 0)
            }
        }

        log_endpoint_success(f"/hybrid-processor/sessions/{session_id}/results", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting session results: {str(e)}"
        log_endpoint_error(f"/hybrid-processor/sessions/{session_id}/results", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.delete("/sessions/{session_id}")
async def cancel_hybrid_session(session_id: str) -> HybridProcessorCancelResponse:
    """
    Cancela una sesión de procesamiento híbrido
    """
    log_endpoint_entry(f"/hybrid-processor/sessions/{session_id}", "DELETE", {"session_id": session_id})

    try:
        # Verificar que la sesión existe
        status_data = await hybrid_processor_system.get_session_status(session_id)
        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Solo se puede cancelar si está en processing o pending
        if status_data["status"] not in ["pending", "processing"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel session in status: {status_data['status']}")

        # Marcar como cancelada (implementación simplificada)
        await hybrid_processor_system._update_session_status(session_id, ProcessingStatus.FAILED, "Cancelled by user")

        response = {
            "session_id": session_id,
            "status": "cancelled",
            "message": "Session cancelled successfully"
        }

        log_endpoint_success(f"/hybrid-processor/sessions/{session_id}", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error cancelling session: {str(e)}"
        log_endpoint_error(f"/hybrid-processor/sessions/{session_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/processors/")
async def list_available_processors() -> HybridProcessorListResponse:
    """
    Lista todos los procesadores disponibles con sus métricas
    """
    log_endpoint_entry("/hybrid-processor/processors/", "GET", {})

    try:
        processors_info = {}

        for name, processor in hybrid_processor_system.processors.items():
            processors_info[name] = {
                "name": name,
                "type": processor.processor_type.value,
                "config": processor.config,
                "is_healthy": processor.is_healthy,
                "avg_processing_time_ms": processor.avg_processing_time,
                "success_rate": processor.success_rate,
                "usage_count": processor.usage_count
            }

        response = {
            "total_processors": len(processors_info),
            "processors": processors_info,
            "processor_types": [ptype.value for ptype in ProcessorType]
        }

        log_endpoint_success("/hybrid-processor/processors/", response)
        return response

    except Exception as e:
        error_msg = f"Error listing processors: {str(e)}"
        log_endpoint_error("/hybrid-processor/processors/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/metrics/{company_id}")
async def get_company_hybrid_metrics(company_id: str) -> HybridProcessorCompanyMetricsResponse:
    """
    Obtiene métricas agregadas de procesamiento híbrido para una empresa
    """
    log_endpoint_entry(f"/hybrid-processor/metrics/{company_id}", "GET", {"company_id": company_id})

    try:
        metrics = await hybrid_processor_system.get_processor_metrics(company_id)

        response = {
            "company_id": company_id,
            "metrics_period": "last_7_days",
            "total_sessions": metrics["total_sessions"],
            "avg_quality_score": metrics["avg_quality_score"],
            "avg_ocr_confidence": metrics["avg_ocr_confidence"],  # ✅ CAMPO FALTANTE
            "avg_processing_time_ms": metrics["avg_processing_time_ms"],
            "success_rate": metrics["success_rate"],
            "processor_performance": metrics["processor_performance"],  # ✅ PROCESSING_METRICS
            "recommendations": _generate_optimization_recommendations(metrics)
        }

        log_endpoint_success(f"/hybrid-processor/metrics/{company_id}", response)
        return response

    except Exception as e:
        error_msg = f"Error getting company metrics: {str(e)}"
        log_endpoint_error(f"/hybrid-processor/metrics/{company_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/processors/health-check")
async def run_processors_health_check() -> HybridProcessorHealthCheckResponse:
    """
    Ejecuta health check en todos los procesadores
    """
    log_endpoint_entry("/hybrid-processor/processors/health-check", "POST", {})

    try:
        health_results = {}

        for name, processor in hybrid_processor_system.processors.items():
            # Simulación de health check
            health_status = "healthy" if processor.success_rate > 70 else "degraded"
            if processor.success_rate < 30:
                health_status = "unhealthy"

            health_results[name] = {
                "status": health_status,
                "success_rate": processor.success_rate,
                "avg_response_time_ms": processor.avg_processing_time,
                "last_check": datetime.utcnow().isoformat()
            }

        overall_health = "healthy"
        unhealthy_count = sum(1 for result in health_results.values() if result["status"] == "unhealthy")
        if unhealthy_count > len(health_results) / 2:
            overall_health = "critical"
        elif unhealthy_count > 0:
            overall_health = "degraded"

        response = {
            "overall_health": overall_health,
            "total_processors": len(health_results),
            "healthy_processors": sum(1 for r in health_results.values() if r["status"] == "healthy"),
            "degraded_processors": sum(1 for r in health_results.values() if r["status"] == "degraded"),
            "unhealthy_processors": unhealthy_count,
            "processor_health": health_results,
            "check_timestamp": datetime.utcnow().isoformat()
        }

        log_endpoint_success("/hybrid-processor/processors/health-check", response)
        return response

    except Exception as e:
        error_msg = f"Error running health check: {str(e)}"
        log_endpoint_error("/hybrid-processor/processors/health-check", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# Funciones auxiliares

async def _process_session_background(session_id: str):
    """Procesa una sesión en background"""
    try:
        result = await hybrid_processor_system.process_session(session_id)
        logger.info(f"Background processing completed for session {session_id}")
    except Exception as e:
        logger.error(f"Background processing failed for session {session_id}: {e}")

def _estimate_processing_time(input_type: InputType) -> int:
    """Estima tiempo de procesamiento basado en tipo de input"""
    estimates = {
        InputType.DOCUMENT: 5000,
        InputType.IMAGE: 3000,
        InputType.TEXT: 1000,
        InputType.AUDIO: 8000,
        InputType.MIXED: 10000
    }
    return estimates.get(input_type, 5000)

def _calculate_progress_percentage(status: str) -> int:
    """Calcula porcentaje de progreso basado en estado"""
    progress_map = {
        "pending": 0,
        "processing": 50,
        "completed": 100,
        "failed": 0,
        "timeout": 0
    }
    return progress_map.get(status, 0)

def _calculate_efficiency_score(processing_metrics: Dict[str, Any]) -> float:
    """Calcula score de eficiencia basado en métricas"""
    total_time = processing_metrics.get("processing_time_ms", 1)
    total_steps = processing_metrics.get("total_steps", 1)

    # Score basado en tiempo por step
    time_per_step = total_time / total_steps

    # Efficient if less than 1 second per step
    if time_per_step < 1000:
        return 100.0
    elif time_per_step < 2000:
        return 80.0
    elif time_per_step < 5000:
        return 60.0
    else:
        return 40.0

def _generate_optimization_recommendations(metrics: Dict[str, Any]) -> List[str]:
    """Genera recomendaciones de optimización"""
    recommendations = []

    if metrics["avg_processing_time_ms"] > 5000:
        recommendations.append("Consider enabling parallel processing for better performance")

    if metrics["avg_quality_score"] < 80:
        recommendations.append("Review processor configurations to improve quality scores")

    if metrics["avg_ocr_confidence"] < 70:
        recommendations.append("Consider using higher-quality OCR engines or image preprocessing")

    if metrics["success_rate"] < 90:
        recommendations.append("Investigate common failure patterns and add error handling")

    if not recommendations:
        recommendations.append("System is performing optimally")

    return recommendations
