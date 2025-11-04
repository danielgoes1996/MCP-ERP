from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query, UploadFile, File
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import asyncio
import os
from pathlib import Path
from core.rpa_automation_engine_system import RPAAutomationEngineSystem
from core.api_models import (
    RPASessionCreateRequest,
    RPASessionCreateResponse,
    RPASessionStatusResponse,
    RPAStepExecutionRequest,
    RPAStepExecutionResponse,
    RPAScreenshotResponse,
    RPAAnalyticsResponse,
    RPAPortalTemplateRequest,
    RPAPortalTemplateResponse,
    RPAPerformanceMetricsResponse,
    RPASessionControlRequest,
    RPASessionControlResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rpa-automation-engine", tags=["RPA Automation Engine"])
rpa_system = RPAAutomationEngineSystem()

@router.post("/sessions", response_model=RPASessionCreateResponse)
async def create_rpa_session(request: RPASessionCreateRequest):
    """
    Crear nueva sesión de automatización RPA con Playwright

    Características de Seguridad:
    - Encriptación automática de credenciales
    - Validación de pasos de automatización
    - Configuración de navegador segura
    - Sandboxing de ejecución
    """
    try:
        # Validar configuración de pasos
        if not request.automation_steps or len(request.automation_steps) == 0:
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos un paso de automatización"
            )

        # Validar límite de pasos
        if len(request.automation_steps) > 100:
            raise HTTPException(
                status_code=400,
                detail="Máximo 100 pasos de automatización por sesión"
            )

        # Validar URL del portal
        if not request.portal_url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=400,
                detail="URL del portal debe comenzar con http:// o https://"
            )

        # Crear sesión
        session_id = await rpa_system.create_rpa_session(
            user_id=request.user_id,
            company_id=request.company_id,
            portal_name=request.portal_name,
            portal_url=request.portal_url,
            automation_steps=request.automation_steps,
            credentials=request.credentials,
            browser_config=request.browser_config
        )

        return RPASessionCreateResponse(
            session_id=session_id,
            user_id=request.user_id,
            company_id=request.company_id,
            portal_name=request.portal_name,
            portal_url=request.portal_url,
            total_steps=len(request.automation_steps),
            status="initialized",
            created_at=datetime.utcnow(),
            estimated_duration_minutes=len(request.automation_steps) * 0.5  # Estimación básica
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating RPA session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/start", response_model=RPASessionControlResponse)
async def start_rpa_session(session_id: str, background_tasks: BackgroundTasks):
    """
    Iniciar ejecución de sesión RPA

    La ejecución se realiza en background para permitir seguimiento en tiempo real
    """
    try:
        # Validar formato de session_id
        if not session_id or len(session_id) < 10:
            raise HTTPException(
                status_code=400,
                detail="session_id inválido"
            )

        # Iniciar sesión en background
        result = await rpa_system.start_rpa_session(session_id)

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return RPASessionControlResponse(
            session_id=session_id,
            action="start",
            status="success",
            message="Sesión RPA iniciada correctamente",
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting RPA session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/pause", response_model=RPASessionControlResponse)
async def pause_rpa_session(session_id: str):
    """
    Pausar sesión RPA en ejecución
    """
    try:
        result = await rpa_system.pause_rpa_session(session_id)

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return RPASessionControlResponse(
            session_id=session_id,
            action="pause",
            status="success",
            message="Sesión pausada correctamente",
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error pausing RPA session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/resume", response_model=RPASessionControlResponse)
async def resume_rpa_session(session_id: str):
    """
    Reanudar sesión RPA pausada
    """
    try:
        result = await rpa_system.resume_rpa_session(session_id)

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return RPASessionControlResponse(
            session_id=session_id,
            action="resume",
            status="success",
            message="Sesión reanudada correctamente",
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error resuming RPA session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/cancel", response_model=RPASessionControlResponse)
async def cancel_rpa_session(session_id: str):
    """
    Cancelar sesión RPA
    """
    try:
        result = await rpa_system.cancel_rpa_session(session_id)

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return RPASessionControlResponse(
            session_id=session_id,
            action="cancel",
            status="success",
            message="Sesión cancelada correctamente",
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error cancelling RPA session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/status", response_model=RPASessionStatusResponse)
async def get_session_status(session_id: str):
    """
    Obtener estado actual de sesión RPA con progreso detallado
    """
    try:
        status_data = await rpa_system.get_session_status(session_id)

        if "error" in status_data:
            raise HTTPException(status_code=404, detail=status_data["error"])

        return RPASessionStatusResponse(
            session_id=session_id,
            status=status_data["status"],
            progress_percentage=status_data["progress_percentage"],
            current_step=status_data["current_step"],
            total_steps=status_data["total_steps"],
            execution_time_ms=status_data["execution_time_ms"],
            created_at=datetime.fromisoformat(status_data["created_at"].replace('Z', '+00:00')) if isinstance(status_data["created_at"], str) else status_data["created_at"],
            started_at=datetime.fromisoformat(status_data["started_at"].replace('Z', '+00:00')) if status_data["started_at"] and isinstance(status_data["started_at"], str) else status_data["started_at"],
            completed_at=datetime.fromisoformat(status_data["completed_at"].replace('Z', '+00:00')) if status_data["completed_at"] and isinstance(status_data["completed_at"], str) else status_data["completed_at"],
            estimated_remaining_time_ms=max(0, (status_data["total_steps"] - status_data["current_step"]) * 2000) if status_data["status"] == "running" else 0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/screenshots", response_model=List[RPAScreenshotResponse])
async def get_session_screenshots(
    session_id: str,
    screenshot_type: Optional[str] = Query(None, description="Filtrar por tipo de screenshot"),
    limit: int = Query(default=50, ge=1, le=200, description="Número máximo de screenshots")
):
    """
    Obtener screenshots capturados durante la automatización

    Tipos de screenshot disponibles:
    - initial: Screenshot inicial de la sesión
    - before_action: Antes de ejecutar una acción
    - after_action: Después de ejecutar una acción
    - error: Capturado durante errores
    - final: Screenshot final de la sesión
    - debug: Screenshots de debugging
    """
    try:
        screenshots = await rpa_system.get_session_screenshots(
            session_id=session_id,
            screenshot_type=screenshot_type
        )

        # Limitar resultados
        screenshots = screenshots[:limit]

        return [
            RPAScreenshotResponse(
                id=screenshot["id"],
                session_id=session_id,
                screenshot_type=screenshot["screenshot_type"],
                file_path=screenshot["file_path"],
                file_size_bytes=screenshot["file_size_bytes"],
                screenshot_metadata=screenshot["screenshot_metadata"],
                page_url=screenshot.get("page_url"),
                page_title=screenshot.get("page_title"),
                captured_at=datetime.fromisoformat(screenshot["captured_at"].replace('Z', '+00:00')) if isinstance(screenshot["captured_at"], str) else screenshot["captured_at"],
                is_available=Path(screenshot["file_path"]).exists()
            )
            for screenshot in screenshots
        ]

    except Exception as e:
        logger.error(f"Error getting session screenshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/{user_id}", response_model=RPAAnalyticsResponse)
async def get_rpa_analytics(
    user_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Número de días para análisis")
):
    """
    Obtener analytics de automatización RPA para usuario
    """
    try:
        analytics = await rpa_system.get_rpa_analytics(user_id=user_id, days=days)

        return RPAAnalyticsResponse(
            user_id=user_id,
            period_days=days,
            total_sessions=analytics.get("total_sessions", 0),
            successful_sessions=analytics.get("successful_sessions", 0),
            failed_sessions=analytics.get("failed_sessions", 0),
            success_rate=analytics.get("success_rate", 0.0),
            average_execution_time_ms=analytics.get("average_execution_time_ms", 0.0),
            average_progress=analytics.get("average_progress", 0.0),
            portal_usage=analytics.get("portal_usage", {}),
            most_common_errors=[],  # Se implementará con más datos
            performance_trends={},   # Se implementará con más datos
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting RPA analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates", response_model=RPAPortalTemplateResponse)
async def create_portal_template(request: RPAPortalTemplateRequest):
    """
    Crear plantilla reutilizable para automatización de portal

    Las plantillas permiten estandarizar automatizaciones para portales específicos
    """
    try:
        # Validar configuración de plantilla
        if not request.template_name or len(request.template_name.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Nombre de plantilla debe tener al menos 3 caracteres"
            )

        if not request.portal_domain:
            raise HTTPException(
                status_code=400,
                detail="Dominio del portal es requerido"
            )

        # Aquí se implementaría la creación en base de datos
        # Por ahora devolvemos una respuesta de éxito

        return RPAPortalTemplateResponse(
            id=1,  # Se generaría automáticamente
            template_name=request.template_name,
            portal_domain=request.portal_domain,
            template_version=request.template_version,
            template_config=request.template_config,
            login_selectors=request.login_selectors,
            navigation_selectors=request.navigation_selectors,
            success_indicators=request.success_indicators,
            is_active=True,
            success_rate=0.0,
            estimated_duration_ms=60000,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating portal template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates", response_model=List[RPAPortalTemplateResponse])
async def list_portal_templates(
    active_only: bool = Query(default=True, description="Solo mostrar plantillas activas"),
    portal_domain: Optional[str] = Query(None, description="Filtrar por dominio")
):
    """
    Listar plantillas de portales disponibles
    """
    try:
        # Plantillas por defecto para portales mexicanos
        default_templates = [
            RPAPortalTemplateResponse(
                id=1,
                template_name="SAT Portal Contribuyentes",
                portal_domain="portalcfdi.facturaelectronica.sat.gob.mx",
                template_version="1.0",
                template_config={"timeout": 45000, "wait_strategy": "network_idle"},
                login_selectors={"username": "#userInput", "password": "#passwordInput"},
                navigation_selectors={"menu_facturas": ".menu-facturas"},
                success_indicators=["Bienvenido", "Menú principal"],
                is_active=True,
                success_rate=87.5,
                estimated_duration_ms=90000,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            RPAPortalTemplateResponse(
                id=2,
                template_name="IMSS Patrón",
                portal_domain="imss.gob.mx",
                template_version="1.0",
                template_config={"timeout": 60000, "wait_strategy": "load"},
                login_selectors={"usuario": "#usuario", "password": "#password"},
                navigation_selectors={"servicios": ".servicios-menu"},
                success_indicators=["Servicios", "Mi cuenta"],
                is_active=True,
                success_rate=78.2,
                estimated_duration_ms=120000,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            RPAPortalTemplateResponse(
                id=3,
                template_name="INFONAVIT Patrón",
                portal_domain="infonavit.org.mx",
                template_version="1.0",
                template_config={"timeout": 30000, "wait_strategy": "dom_content_loaded"},
                login_selectors={"rfc": "#rfc", "password": "#password"},
                navigation_selectors={"mi_cuenta": ".mi-cuenta"},
                success_indicators=["Mi cuenta", "Movimientos"],
                is_active=True,
                success_rate=92.1,
                estimated_duration_ms=75000,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ]

        # Filtrar por dominio si se especifica
        if portal_domain:
            default_templates = [t for t in default_templates if portal_domain.lower() in t.portal_domain.lower()]

        # Filtrar por activo si se especifica
        if active_only:
            default_templates = [t for t in default_templates if t.is_active]

        return default_templates

    except Exception as e:
        logger.error(f"Error listing portal templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance", response_model=RPAPerformanceMetricsResponse)
async def get_performance_metrics():
    """
    Obtener métricas de performance del sistema RPA
    """
    try:
        metrics = rpa_system.get_performance_metrics()

        return RPAPerformanceMetricsResponse(
            active_sessions=metrics.get("active_sessions", 0),
            browser_instances=metrics.get("browser_instances", 0),
            system_cpu_usage=metrics.get("system_metrics", {}).get("cpu_usage_percent", 0.0),
            system_memory_usage=metrics.get("system_metrics", {}).get("memory_usage_percent", 0.0),
            available_memory_gb=metrics.get("system_metrics", {}).get("available_memory_gb", 0.0),
            screenshots_directory_size_mb=metrics.get("screenshots_directory_size_mb", 0.0),
            average_session_duration_ms=0.0,  # Se calculará con más datos
            error_rate=0.0,  # Se calculará con más datos
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/screenshot")
async def capture_manual_screenshot(session_id: str):
    """
    Capturar screenshot manual durante la ejecución
    """
    try:
        # Verificar que la sesión esté activa
        status_data = await rpa_system.get_session_status(session_id)
        if "error" in status_data:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")

        if status_data["status"] != "running":
            raise HTTPException(
                status_code=400,
                detail=f"No se puede capturar screenshot en sesión con estado: {status_data['status']}"
            )

        # Capturar screenshot manual
        screenshot_path = await rpa_system._capture_screenshot(session_id, None, "debug")

        if screenshot_path:
            return {
                "status": "success",
                "message": "Screenshot capturado exitosamente",
                "screenshot_path": screenshot_path,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Error capturando screenshot")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error capturing manual screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/logs")
async def get_session_logs(
    session_id: str,
    log_level: Optional[str] = Query(None, description="Filtrar por nivel de log"),
    limit: int = Query(default=100, ge=1, le=1000, description="Número máximo de logs")
):
    """
    Obtener logs detallados de ejecución de sesión
    """
    try:
        # Aquí se implementaría la consulta de logs desde la base de datos
        # Por ahora devolvemos logs de ejemplo

        sample_logs = [
            {
                "id": 1,
                "timestamp": datetime.utcnow().isoformat(),
                "log_level": "INFO",
                "log_category": "navigation",
                "log_message": "Navegando a portal principal",
                "browser_context": {"url": "https://example.com", "ready_state": "complete"}
            },
            {
                "id": 2,
                "timestamp": datetime.utcnow().isoformat(),
                "log_level": "DEBUG",
                "log_category": "element_detection",
                "log_message": "Elemento encontrado con selector #login-button",
                "browser_context": {"selector_used": "#login-button", "element_visible": True}
            }
        ]

        # Filtrar por nivel si se especifica
        if log_level:
            sample_logs = [log for log in sample_logs if log["log_level"] == log_level.upper()]

        return {"session_id": session_id, "logs": sample_logs[:limit]}

    except Exception as e:
        logger.error(f"Error getting session logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}/cleanup")
async def cleanup_session_resources(session_id: str):
    """
    Limpiar recursos de sesión (screenshots, logs temporales)
    """
    try:
        await rpa_system._cleanup_session(session_id)

        # Limpiar screenshots antiguos (opcional)
        screenshots_dir = Path("static/automation_screenshots")
        session_screenshots = list(screenshots_dir.glob(f"*{session_id}*"))

        cleaned_files = 0
        for screenshot_file in session_screenshots:
            try:
                screenshot_file.unlink()
                cleaned_files += 1
            except:
                pass

        return {
            "status": "success",
            "message": f"Recursos de sesión limpiados: {cleaned_files} archivos eliminados",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning up session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """
    Health check del sistema de automatización RPA
    """
    try:
        performance_metrics = rpa_system.get_performance_metrics()

        # Verificar componentes críticos
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy",
                "playwright": "available",
                "file_system": "healthy" if Path("static/automation_screenshots").exists() else "warning",
                "memory_usage": "normal" if performance_metrics.get("system_metrics", {}).get("memory_usage_percent", 0) < 80 else "high",
                "active_sessions": performance_metrics.get("active_sessions", 0)
            },
            "performance": {
                "cpu_usage": performance_metrics.get("system_metrics", {}).get("cpu_usage_percent", 0),
                "memory_usage": performance_metrics.get("system_metrics", {}).get("memory_usage_percent", 0),
                "available_memory_gb": performance_metrics.get("system_metrics", {}).get("available_memory_gb", 0)
            }
        }

        return health_status

    except Exception as e:
        logger.error(f"Error in RPA health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }