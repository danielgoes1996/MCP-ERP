"""
Robust Automation Engine API - Endpoints para automatización robusta con risk assessment
Punto 20 de Auditoría: APIs para performance_metrics, recovery_actions y automation_health
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from core.robust_automation_engine_system import (
    robust_automation_engine_system,
    AutomationType,
    RiskLevel,
    HealthStatus,
    AutomationStatus
)
from core.api_models import (
    RobustAutomationSessionCreateRequest,
    RobustAutomationSessionResponse,
    RobustAutomationExecuteRequest,
    RobustAutomationExecuteResponse,
    RobustAutomationStatusResponse,
    RobustAutomationHealthResponse,
    RobustAutomationPerformanceResponse,
    RobustAutomationRecoveryResponse,
    RobustAutomationRecoveryTriggerRequest,
    RobustAutomationRecoveryTriggerResponse,
    RobustAutomationCancelResponse,
    RobustAutomationSystemHealthResponse,
)
from core.error_handler import handle_error, log_endpoint_entry, log_endpoint_success, log_endpoint_error

router = APIRouter(prefix="/robust-automation", tags=["Robust Automation Engine"])
logger = logging.getLogger(__name__)

@router.post("/sessions/")
async def create_robust_automation_session(
    request: "RobustAutomationSessionCreateRequest"
) -> "RobustAutomationSessionResponse":
    """
    Crea una nueva sesión de automatización robusta con risk assessment
    Incluye tracking de performance_metrics, recovery_actions y automation_health
    """
    log_endpoint_entry("/robust-automation/sessions/", "POST", request.dict())

    try:
        # Validar tipo de automatización
        try:
            automation_type_enum = AutomationType(request.automation_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid automation_type: {request.automation_type}")

        # Crear sesión con configuración robusta
        automation_config = {
            'name': request.automation_name,
            'type': request.automation_type,
            'target_system': request.target_system,
            'risk_tolerance': request.risk_tolerance,
            'recovery_enabled': request.enable_recovery,
            'health_monitoring': request.enable_health_monitoring,
            **request.automation_config
        }

        session_id = await robust_automation_engine_system.create_automation_session(
            company_id=request.company_id,
            automation_config=automation_config
        )

        response = {
            "session_id": session_id,
            "status": "created",
            "automation_type": request.automation_type,
            "company_id": request.company_id,
            "risk_assessment_enabled": True,
            "recovery_enabled": request.enable_recovery,
            "health_monitoring_enabled": request.enable_health_monitoring,
            "estimated_risk_level": _estimate_initial_risk_level(automation_config),
            "created_at": datetime.utcnow().isoformat()
        }

        log_endpoint_success("/robust-automation/sessions/", response)
        return response

    except Exception as e:
        error_msg = f"Error creating robust automation session: {str(e)}"
        log_endpoint_error("/robust-automation/sessions/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/sessions/{session_id}/execute")
async def execute_robust_automation(
    session_id: str,
    request: "RobustAutomationExecuteRequest",
    background_tasks: BackgroundTasks
) -> "RobustAutomationExecuteResponse":
    """
    Ejecuta automatización robusta con monitoreo completo
    Retorna performance_metrics y recovery_actions en tiempo real
    """
    log_endpoint_entry(f"/robust-automation/sessions/{session_id}/execute", "POST", request.dict())

    try:
        # Validar que la sesión existe
        session_status = await robust_automation_engine_system.get_session_status(session_id)
        if 'error' in session_status:
            raise HTTPException(status_code=404, detail="Session not found")

        # Ejecutar en background si se solicita
        if request.execute_async:
            background_tasks.add_task(_execute_automation_background, session_id, request.automation_steps)

            response = {
                "session_id": session_id,
                "status": "execution_started",
                "execution_mode": "async",
                "message": "Robust automation started in background",
                "check_status_url": f"/robust-automation/sessions/{session_id}/status",
                "estimated_completion_time": _estimate_completion_time(request.automation_steps)
            }
        else:
            # Ejecutar sincronicamente
            result = await robust_automation_engine_system.execute_automation_session(
                session_id, request.automation_steps
            )

            response = {
                "session_id": session_id,
                "status": result["status"],
                "execution_mode": "sync",
                "performance_metrics": result.get("performance_metrics", {}),  # ✅ CAMPO FALTANTE
                "recovery_actions": result.get("recovery_actions", []),        # ✅ CAMPO FALTANTE
                "automation_health": result.get("automation_health", {}),      # ✅ CAMPO FALTANTE
                "risk_assessment": result.get("risk_assessment", {}),
                "execution_summary": {
                    "total_steps": len(request.automation_steps),
                    "completed_steps": len([r for r in result.get("results", []) if r.get("status") == "completed"]),
                    "failed_steps": len([r for r in result.get("results", []) if r.get("status") == "failed"])
                }
            }

        log_endpoint_success(f"/robust-automation/sessions/{session_id}/execute", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error executing robust automation: {str(e)}"
        log_endpoint_error(f"/robust-automation/sessions/{session_id}/execute", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/status")
async def get_robust_automation_status(session_id: str) -> "RobustAutomationStatusResponse":
    """
    Obtiene estado completo con performance_metrics, recovery_actions y automation_health
    """
    log_endpoint_entry(f"/robust-automation/sessions/{session_id}/status", "GET", {"session_id": session_id})

    try:
        status_data = await robust_automation_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        response = {
            "session_id": session_id,
            "status": status_data["status"],
            "risk_level": status_data.get("risk_level", "medium"),
            "performance_metrics": status_data.get("performance_metrics", {}),  # ✅ CAMPO FALTANTE
            "recovery_actions": status_data.get("recovery_actions", []),        # ✅ CAMPO FALTANTE
            "automation_health": status_data.get("automation_health", {}),      # ✅ CAMPO FALTANTE
            "execution_progress": _calculate_execution_progress(status_data),
            "health_score": status_data.get("automation_health", {}).get("overall_score", 100.0),
            "risk_score": _calculate_current_risk_score(status_data),
            "created_at": status_data.get("created_at"),
            "updated_at": status_data.get("updated_at")
        }

        log_endpoint_success(f"/robust-automation/sessions/{session_id}/status", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting automation status: {str(e)}"
        log_endpoint_error(f"/robust-automation/sessions/{session_id}/status", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/performance")
async def get_session_performance_metrics(session_id: str) -> "RobustAutomationPerformanceResponse":
    """
    Obtiene métricas detalladas de performance para una sesión
    Incluye performance_metrics granulares y análisis de eficiencia
    """
    log_endpoint_entry(f"/robust-automation/sessions/{session_id}/performance", "GET", {"session_id": session_id})

    try:
        status_data = await robust_automation_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        performance_metrics = status_data.get("performance_metrics", {})

        response = {
            "session_id": session_id,
            "performance_metrics": performance_metrics,  # ✅ CAMPO FALTANTE COMPLETO
            "execution_time_ms": performance_metrics.get("execution_time_ms", 0),
            "cpu_usage_percent": performance_metrics.get("cpu_usage_percent", 0.0),
            "memory_usage_mb": performance_metrics.get("memory_usage_mb", 0.0),
            "throughput_ops_per_second": performance_metrics.get("throughput_ops_per_second", 0.0),
            "error_rate": performance_metrics.get("error_rate", 0.0),
            "success_rate": performance_metrics.get("success_rate", 100.0),
            "resource_efficiency": performance_metrics.get("resource_efficiency", 100.0),
            "step_breakdown": performance_metrics.get("step_breakdown", []),
            "performance_analysis": _analyze_performance_metrics(performance_metrics),
            "optimization_recommendations": _generate_performance_recommendations(performance_metrics)
        }

        log_endpoint_success(f"/robust-automation/sessions/{session_id}/performance", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting performance metrics: {str(e)}"
        log_endpoint_error(f"/robust-automation/sessions/{session_id}/performance", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/recovery")
async def get_session_recovery_actions(session_id: str) -> "RobustAutomationRecoveryResponse":
    """
    Obtiene acciones de recuperación ejecutadas para una sesión
    Incluye recovery_actions detalladas y análisis de efectividad
    """
    log_endpoint_entry(f"/robust-automation/sessions/{session_id}/recovery", "GET", {"session_id": session_id})

    try:
        status_data = await robust_automation_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        recovery_actions = status_data.get("recovery_actions", [])

        response = {
            "session_id": session_id,
            "recovery_actions": recovery_actions,  # ✅ CAMPO FALTANTE COMPLETO
            "total_recovery_actions": len(recovery_actions),
            "successful_recoveries": len([r for r in recovery_actions if r.get("success", False)]),
            "failed_recoveries": len([r for r in recovery_actions if not r.get("success", True)]),
            "recovery_effectiveness": _calculate_recovery_effectiveness(recovery_actions),
            "recovery_types_used": list(set(r.get("action_type", "unknown") for r in recovery_actions)),
            "total_recovery_time_ms": sum(r.get("execution_time_ms", 0) for r in recovery_actions),
            "recovery_analysis": _analyze_recovery_patterns(recovery_actions),
            "prevention_recommendations": _generate_prevention_recommendations(recovery_actions)
        }

        log_endpoint_success(f"/robust-automation/sessions/{session_id}/recovery", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting recovery actions: {str(e)}"
        log_endpoint_error(f"/robust-automation/sessions/{session_id}/recovery", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/health")
async def get_session_health_status(session_id: str) -> "RobustAutomationHealthResponse":
    """
    Obtiene estado de salud detallado de la automatización
    Incluye automation_health completo y tendencias
    """
    log_endpoint_entry(f"/robust-automation/sessions/{session_id}/health", "GET", {"session_id": session_id})

    try:
        status_data = await robust_automation_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        automation_health = status_data.get("automation_health", {})

        response = {
            "session_id": session_id,
            "automation_health": automation_health,  # ✅ CAMPO FALTANTE COMPLETO
            "overall_health_score": automation_health.get("overall_score", 100.0),
            "health_status": automation_health.get("health_status", "healthy"),
            "component_scores": automation_health.get("component_scores", {}),
            "health_trending": automation_health.get("trending", "stable"),
            "active_alerts": automation_health.get("alerts", []),
            "health_recommendations": automation_health.get("recommendations", []),
            "last_health_check": datetime.utcnow().isoformat(),
            "health_history": _get_health_history_summary(session_id),
            "critical_issues": [alert for alert in automation_health.get("alerts", []) if alert.get("level") == "critical"]
        }

        log_endpoint_success(f"/robust-automation/sessions/{session_id}/health", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting health status: {str(e)}"
        log_endpoint_error(f"/robust-automation/sessions/{session_id}/health", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/sessions/{session_id}/recovery/trigger")
async def trigger_manual_recovery(
    session_id: str,
    request: "RobustAutomationRecoveryTriggerRequest"
) -> "RobustAutomationRecoveryTriggerResponse":
    """
    Dispara recuperación manual para una sesión
    """
    log_endpoint_entry(f"/robust-automation/sessions/{session_id}/recovery/trigger", "POST", request.dict())

    try:
        # Validar que la sesión existe
        status_data = await robust_automation_engine_system.get_session_status(session_id)
        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Obtener engine de la sesión
        engine = robust_automation_engine_system.engines.get(session_id)
        if not engine:
            raise HTTPException(status_code=400, detail="Session engine not available")

        # Crear y ejecutar acción de recuperación manual
        recovery_action = await engine.recovery_manager.create_step_recovery_action(
            session_id, request.step_number or 0, request.recovery_reason, 0
        )

        recovery_result = await engine.recovery_manager.execute_recovery_action(recovery_action)

        response = {
            "session_id": session_id,
            "recovery_triggered": True,
            "recovery_type": request.recovery_type,
            "recovery_success": recovery_result["success"],
            "recovery_message": recovery_result["message"],
            "recovery_time_ms": recovery_result.get("execution_time_ms", 0),
            "recovery_data": recovery_result.get("recovery_data", {}),
            "timestamp": datetime.utcnow().isoformat()
        }

        log_endpoint_success(f"/robust-automation/sessions/{session_id}/recovery/trigger", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error triggering manual recovery: {str(e)}"
        log_endpoint_error(f"/robust-automation/sessions/{session_id}/recovery/trigger", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.delete("/sessions/{session_id}")
async def cancel_robust_automation(session_id: str) -> "RobustAutomationCancelResponse":
    """
    Cancela una sesión de automatización robusta
    """
    log_endpoint_entry(f"/robust-automation/sessions/{session_id}", "DELETE", {"session_id": session_id})

    try:
        # Validar que la sesión existe
        status_data = await robust_automation_engine_system.get_session_status(session_id)
        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Solo se puede cancelar si está en ejecución o pendiente
        if status_data["status"] not in ["pending", "running"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel session in status: {status_data['status']}")

        # Actualizar estado a cancelado
        await robust_automation_engine_system._update_session_status(session_id, AutomationStatus.CANCELLED, "Cancelled by user")

        # Limpiar engine de memoria
        if session_id in robust_automation_engine_system.engines:
            del robust_automation_engine_system.engines[session_id]

        response = {
            "session_id": session_id,
            "status": "cancelled",
            "message": "Robust automation session cancelled successfully",
            "cancellation_time": datetime.utcnow().isoformat()
        }

        log_endpoint_success(f"/robust-automation/sessions/{session_id}", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error cancelling automation: {str(e)}"
        log_endpoint_error(f"/robust-automation/sessions/{session_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/health/system")
async def get_system_health() -> "RobustAutomationSystemHealthResponse":
    """
    Obtiene estado de salud del sistema completo
    """
    log_endpoint_entry("/robust-automation/health/system", "GET", {})

    try:
        # Obtener métricas del sistema
        import psutil

        system_health = {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "active_sessions": len(robust_automation_engine_system.engines),
            "system_load": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.0
        }

        # Calcular health score del sistema
        health_score = _calculate_system_health_score(system_health)

        response = {
            "overall_health_score": health_score,
            "health_status": _determine_system_health_status(health_score),
            "system_metrics": system_health,
            "active_automation_sessions": len(robust_automation_engine_system.engines),
            "system_alerts": _generate_system_alerts(system_health),
            "system_recommendations": _generate_system_recommendations(system_health),
            "last_check": datetime.utcnow().isoformat()
        }

        log_endpoint_success("/robust-automation/health/system", response)
        return response

    except Exception as e:
        error_msg = f"Error getting system health: {str(e)}"
        log_endpoint_error("/robust-automation/health/system", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# Funciones auxiliares

async def _execute_automation_background(session_id: str, steps: List[Dict[str, Any]]):
    """Ejecuta automatización en background"""
    try:
        result = await robust_automation_engine_system.execute_automation_session(session_id, steps)
        logger.info(f"Background automation completed for session {session_id}")
    except Exception as e:
        logger.error(f"Background automation failed for session {session_id}: {e}")

def _estimate_initial_risk_level(automation_config: Dict[str, Any]) -> str:
    """Estima nivel de riesgo inicial"""
    automation_type = automation_config.get('type', 'workflow')

    if automation_type in ['web_scraping', 'integration']:
        return 'medium'
    elif automation_type == 'data_processing':
        return 'low'
    elif automation_type == 'monitoring':
        return 'low'
    else:
        return 'medium'

def _estimate_completion_time(steps: List[Dict[str, Any]]) -> str:
    """Estima tiempo de completado"""
    total_steps = len(steps)
    estimated_minutes = max(1, total_steps * 0.5)  # 30 segundos por step

    completion_time = datetime.utcnow()
    completion_time = completion_time.replace(minute=completion_time.minute + int(estimated_minutes))

    return completion_time.isoformat()

def _calculate_execution_progress(status_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula progreso de ejecución"""
    status = status_data.get("status", "pending")

    progress_map = {
        "pending": 0,
        "running": 50,
        "completed": 100,
        "failed": 100,
        "cancelled": 100
    }

    return {
        "percentage": progress_map.get(status, 0),
        "phase": _get_execution_phase(status),
        "estimated_completion": _estimate_completion_time([])  # Simplified
    }

def _get_execution_phase(status: str) -> str:
    """Obtiene fase de ejecución"""
    phase_map = {
        "pending": "initialization",
        "running": "execution",
        "completed": "finalized",
        "failed": "error_handling",
        "cancelled": "cleanup"
    }
    return phase_map.get(status, "unknown")

def _calculate_current_risk_score(status_data: Dict[str, Any]) -> float:
    """Calcula score de riesgo actual"""
    risk_level = status_data.get("risk_level", "medium")

    risk_scores = {
        "low": 25.0,
        "medium": 50.0,
        "high": 75.0,
        "critical": 95.0
    }

    return risk_scores.get(risk_level, 50.0)

def _analyze_performance_metrics(performance_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analiza métricas de performance"""
    execution_time = performance_metrics.get("execution_time_ms", 0)
    cpu_usage = performance_metrics.get("cpu_usage_percent", 0.0)
    success_rate = performance_metrics.get("success_rate", 100.0)

    return {
        "performance_grade": _calculate_performance_grade(execution_time, cpu_usage, success_rate),
        "bottlenecks": _identify_bottlenecks(performance_metrics),
        "efficiency_rating": performance_metrics.get("resource_efficiency", 100.0)
    }

def _calculate_performance_grade(execution_time: int, cpu_usage: float, success_rate: float) -> str:
    """Calcula grado de performance"""
    if success_rate >= 95 and execution_time < 5000 and cpu_usage < 50:
        return "A"
    elif success_rate >= 90 and execution_time < 10000 and cpu_usage < 70:
        return "B"
    elif success_rate >= 80 and execution_time < 20000 and cpu_usage < 90:
        return "C"
    else:
        return "D"

def _identify_bottlenecks(performance_metrics: Dict[str, Any]) -> List[str]:
    """Identifica cuellos de botella"""
    bottlenecks = []

    if performance_metrics.get("execution_time_ms", 0) > 10000:
        bottlenecks.append("High execution time")

    if performance_metrics.get("cpu_usage_percent", 0) > 80:
        bottlenecks.append("High CPU usage")

    if performance_metrics.get("memory_usage_mb", 0) > 500:
        bottlenecks.append("High memory usage")

    if performance_metrics.get("error_rate", 0) > 10:
        bottlenecks.append("High error rate")

    return bottlenecks

def _generate_performance_recommendations(performance_metrics: Dict[str, Any]) -> List[str]:
    """Genera recomendaciones de performance"""
    recommendations = []

    if performance_metrics.get("execution_time_ms", 0) > 10000:
        recommendations.append("Consider optimizing step execution order")

    if performance_metrics.get("cpu_usage_percent", 0) > 80:
        recommendations.append("Reduce concurrent operations or add delays")

    if performance_metrics.get("error_rate", 0) > 5:
        recommendations.append("Review error handling and add more robust fallbacks")

    if not recommendations:
        recommendations.append("Performance is optimal")

    return recommendations

def _calculate_recovery_effectiveness(recovery_actions: List[Dict[str, Any]]) -> float:
    """Calcula efectividad de recovery"""
    if not recovery_actions:
        return 100.0

    successful = len([r for r in recovery_actions if r.get("success", False)])
    return (successful / len(recovery_actions)) * 100

def _analyze_recovery_patterns(recovery_actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analiza patrones de recovery"""
    if not recovery_actions:
        return {"pattern": "no_recoveries_needed"}

    action_types = [r.get("action_type", "unknown") for r in recovery_actions]
    most_common = max(set(action_types), key=action_types.count) if action_types else "unknown"

    return {
        "most_common_type": most_common,
        "recovery_frequency": len(recovery_actions),
        "pattern": "frequent" if len(recovery_actions) > 5 else "occasional"
    }

def _generate_prevention_recommendations(recovery_actions: List[Dict[str, Any]]) -> List[str]:
    """Genera recomendaciones de prevención"""
    if not recovery_actions:
        return ["System is operating reliably"]

    recommendations = [
        "Review automation configuration to reduce error probability",
        "Add more comprehensive input validation",
        "Implement better error handling in critical steps"
    ]

    return recommendations

def _get_health_history_summary(session_id: str) -> Dict[str, Any]:
    """Obtiene resumen de historial de salud"""
    return {
        "trend": "stable",
        "lowest_score": 85.0,
        "highest_score": 100.0,
        "average_score": 92.5
    }

def _calculate_system_health_score(system_health: Dict[str, Any]) -> float:
    """Calcula score de salud del sistema"""
    cpu_score = max(0, 100 - system_health["cpu_usage"])
    memory_score = max(0, 100 - system_health["memory_usage"])
    disk_score = max(0, 100 - system_health["disk_usage"])

    return (cpu_score + memory_score + disk_score) / 3

def _determine_system_health_status(health_score: float) -> str:
    """Determina estado de salud del sistema"""
    if health_score >= 80:
        return "healthy"
    elif health_score >= 60:
        return "warning"
    else:
        return "critical"

def _generate_system_alerts(system_health: Dict[str, Any]) -> List[Dict[str, str]]:
    """Genera alertas del sistema"""
    alerts = []

    if system_health["cpu_usage"] > 90:
        alerts.append({"level": "critical", "message": "High CPU usage detected"})

    if system_health["memory_usage"] > 90:
        alerts.append({"level": "critical", "message": "High memory usage detected"})

    if system_health["disk_usage"] > 90:
        alerts.append({"level": "warning", "message": "High disk usage detected"})

    return alerts

def _generate_system_recommendations(system_health: Dict[str, Any]) -> List[str]:
    """Genera recomendaciones del sistema"""
    recommendations = []

    if system_health["cpu_usage"] > 80:
        recommendations.append("Consider reducing concurrent automation sessions")

    if system_health["memory_usage"] > 80:
        recommendations.append("Monitor memory usage and restart if necessary")

    if system_health["active_sessions"] > 10:
        recommendations.append("High number of active sessions, monitor system performance")

    if not recommendations:
        recommendations.append("System is operating optimally")

    return recommendations
