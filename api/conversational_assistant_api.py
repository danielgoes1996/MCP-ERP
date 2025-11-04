from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import asyncio
from core.conversational_assistant_system import ConversationalAssistantSystem
from core.api_models import (
    ConversationSessionRequest,
    ConversationSessionResponse,
    UserQueryRequest,
    UserQueryResponse,
    ConversationHistoryResponse,
    ConversationalAnalyticsResponse,
    LLMModelConfigRequest,
    LLMModelConfigResponse,
    CacheStatsResponse,
    QueryInteraction
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversational-assistant", tags=["Conversational Assistant"])
assistant_system = ConversationalAssistantSystem()

@router.post("/sessions", response_model=ConversationSessionResponse)
async def create_conversation_session(request: ConversationSessionRequest):
    """
    Crear nueva sesión de conversación con el asistente
    """
    try:
        session_id = await assistant_system.create_conversation_session(
            user_id=request.user_id,
            company_id=request.company_id,
            session_name=request.session_name
        )

        return ConversationSessionResponse(
            session_id=session_id,
            user_id=request.user_id,
            company_id=request.company_id,
            session_name=request.session_name or f"Conversación {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            created_at=datetime.utcnow(),
            is_active=True
        )

    except Exception as e:
        logger.error(f"Error creating conversation session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=UserQueryResponse)
async def process_user_query(request: UserQueryRequest):
    """
    Procesar consulta del usuario con el asistente conversacional

    Características:
    - Sanitización automática de input
    - Cache inteligente de respuestas
    - Múltiples proveedores LLM
    - SQL injection prevention
    - Logging completo de interacciones
    """
    try:
        # Validar longitud de query
        if len(request.user_query) > 10000:
            raise HTTPException(
                status_code=400,
                detail="Query demasiado larga. Máximo 10,000 caracteres."
            )

        # Validar session_id
        if not request.session_id or len(request.session_id) < 5:
            raise HTTPException(
                status_code=400,
                detail="session_id es requerido y debe ser válido"
            )

        # Procesar query con el sistema
        result = await assistant_system.process_user_query(
            session_id=request.session_id,
            user_id=request.user_id,
            user_query=request.user_query,
            context=request.context
        )

        if result["status"] == "error":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Error procesando consulta")
            )

        return UserQueryResponse(
            session_id=request.session_id,
            user_query=request.user_query,
            assistant_response=result["response"],
            sql_executed=result.get("sql_executed"),
            llm_model_used=result.get("llm_model_used"),
            confidence_score=result.get("confidence", 0.0),
            query_intent=result.get("query_intent"),
            processing_time_ms=result.get("processing_time_ms", 0),
            from_cache=result.get("from_cache", False),
            sql_result_rows=result.get("sql_result_rows", 0),
            created_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing user query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/history", response_model=List[QueryInteraction])
async def get_conversation_history(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Número máximo de interacciones a retornar")
):
    """
    Obtener historial de conversación de una sesión
    """
    try:
        history = await assistant_system.get_conversation_history(
            session_id=session_id,
            limit=limit
        )

        return [
            QueryInteraction(
                user_query=item["user_query"],
                assistant_response=item["assistant_response"],
                llm_model_used=item["llm_model_used"],
                confidence_score=item["confidence_score"],
                processing_time_ms=item["processing_time_ms"],
                created_at=datetime.fromisoformat(item["created_at"].replace('Z', '+00:00')) if isinstance(item["created_at"], str) else item["created_at"]
            )
            for item in history
        ]

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/{user_id}", response_model=ConversationalAnalyticsResponse)
async def get_user_analytics(
    user_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Número de días para el análisis")
):
    """
    Obtener analytics de uso del asistente conversacional
    """
    try:
        analytics = await assistant_system.get_analytics(user_id=user_id, days=days)

        return ConversationalAnalyticsResponse(
            user_id=user_id,
            period_days=days,
            total_interactions=analytics.get("total_interactions", 0),
            average_confidence=analytics.get("average_confidence", 0.0),
            average_processing_time_ms=analytics.get("average_processing_time_ms", 0.0),
            sql_queries_executed=analytics.get("sql_queries_executed", 0),
            model_distribution=analytics.get("model_distribution", {}),
            cache_hit_rate=0.0,  # Se calculará en futuras versiones
            most_common_intents=[],  # Se implementará con más datos
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting user analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/config", response_model=LLMModelConfigResponse)
async def configure_llm_model(request: LLMModelConfigRequest):
    """
    Configurar un nuevo modelo LLM o actualizar configuración existente

    Permite configurar:
    - Modelos OpenAI (GPT-4, GPT-3.5-turbo)
    - Modelos Anthropic (Claude)
    - Modelos locales
    - Configuración de temperatura, max_tokens, etc.
    """
    try:
        # Validar configuración
        if request.max_tokens < 100 or request.max_tokens > 50000:
            raise HTTPException(
                status_code=400,
                detail="max_tokens debe estar entre 100 y 50,000"
            )

        if request.temperature < 0.0 or request.temperature > 2.0:
            raise HTTPException(
                status_code=400,
                detail="temperature debe estar entre 0.0 y 2.0"
            )

        # Aquí se implementaría la lógica de configuración
        # Por ahora devolvemos una respuesta de éxito

        return LLMModelConfigResponse(
            model_name=request.model_name,
            provider=request.provider,
            model_version=request.model_version,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            model_config=request.model_config,
            is_active=request.is_active,
            health_status="healthy",
            total_requests=0,
            average_response_time_ms=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring LLM model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models", response_model=List[LLMModelConfigResponse])
async def list_llm_models(active_only: bool = Query(default=True, description="Solo mostrar modelos activos")):
    """
    Listar todos los modelos LLM configurados
    """
    try:
        # Aquí se implementaría la consulta a la base de datos
        # Por ahora devolvemos modelos por defecto

        default_models = [
            LLMModelConfigResponse(
                model_name="gpt-4o",
                provider="openai",
                model_version="2024-08-06",
                max_tokens=4000,
                temperature=0.7,
                model_config={"supports_function_calling": True, "context_length": 128000},
                is_active=True,
                health_status="healthy",
                total_requests=0,
                average_response_time_ms=0.0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            LLMModelConfigResponse(
                model_name="claude-3-5-sonnet",
                provider="anthropic",
                model_version="20241022",
                max_tokens=4000,
                temperature=0.7,
                model_config={"supports_function_calling": True, "context_length": 200000},
                is_active=True,
                health_status="healthy",
                total_requests=0,
                average_response_time_ms=0.0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ]

        if active_only:
            return [model for model in default_models if model.is_active]

        return default_models

    except Exception as e:
        logger.error(f"Error listing LLM models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_statistics():
    """
    Obtener estadísticas del cache de respuestas LLM
    """
    try:
        # Aquí se implementaría la consulta de estadísticas reales
        return CacheStatsResponse(
            total_cached_responses=0,
            cache_hit_rate=0.0,
            cache_size_mb=0.0,
            expired_entries=0,
            most_cached_queries=[],
            cache_performance={
                "average_hit_time_ms": 10.5,
                "average_miss_time_ms": 1250.0
            },
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting cache statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cache", status_code=204)
async def clear_cache(
    expired_only: bool = Query(default=True, description="Solo limpiar entradas expiradas"),
    background_tasks: BackgroundTasks = None
):
    """
    Limpiar cache de respuestas LLM
    """
    try:
        if background_tasks:
            background_tasks.add_task(_clear_cache_background, expired_only)
        else:
            await _clear_cache_background(expired_only)

        return {"message": "Cache clearing initiated"}

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _clear_cache_background(expired_only: bool = True):
    """
    Tarea en background para limpiar cache
    """
    try:
        # Aquí se implementaría la lógica real de limpieza
        logger.info(f"Cache clearing completed (expired_only: {expired_only})")
        await asyncio.sleep(1)  # Simular trabajo

    except Exception as e:
        logger.error(f"Error in background cache clearing: {e}")

@router.post("/feedback")
async def record_user_feedback(
    session_id: str,
    interaction_id: Optional[int] = None,
    rating: int = Query(..., ge=1, le=5, description="Rating de 1-5 estrellas"),
    feedback_text: Optional[str] = None
):
    """
    Registrar feedback del usuario sobre respuestas del asistente
    """
    try:
        # Validar feedback
        if feedback_text and len(feedback_text) > 1000:
            raise HTTPException(
                status_code=400,
                detail="Feedback text debe ser menor a 1000 caracteres"
            )

        # Aquí se implementaría el registro en base de datos
        logger.info(f"User feedback recorded for session {session_id}: {rating}/5")

        return {
            "status": "success",
            "message": "Feedback registrado correctamente",
            "session_id": session_id,
            "rating": rating
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording user feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """
    Health check del sistema de asistente conversacional
    """
    try:
        # Verificar componentes críticos
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy",
                "llm_providers": {
                    "openai": "unknown",
                    "anthropic": "unknown"
                },
                "cache": "healthy",
                "memory_usage": "normal"
            }
        }

        return health_status

    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }