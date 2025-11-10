"""
API para Category Learning System
Sistema de aprendizaje de categorización basado en feedback del usuario
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/category-learning", tags=["ml", "categorization"])


# ============================================================================
# MODELS
# ============================================================================

class CategoryFeedbackRequest(BaseModel):
    """Request para enviar feedback de categorización"""
    expense_id: int
    feedback_type: str  # 'accepted', 'corrected', 'rejected'
    actual_category: Optional[str] = None
    user_id: Optional[int] = None
    notes: Optional[str] = None


class CategoryPredictionRequest(BaseModel):
    """Request para predecir categoría"""
    description: str
    amount: float
    merchant_name: Optional[str] = None


class CategoryMetricsResponse(BaseModel):
    """Response con métricas de categorización"""
    category_name: str
    total_predictions: int
    correct_predictions: int
    accuracy_rate: float
    avg_confidence: float
    most_common_keywords: List[str]
    most_common_merchants: List[str]


class CategoryPredictionResponse(BaseModel):
    """Response con predicción de categoría"""
    predicted_category: str
    confidence: float
    reasoning: str
    alternatives: List[Dict[str, Any]]


# ============================================================================
# HELPERS
# ============================================================================

def get_tenant_id_from_header(x_tenant_id: Optional[str] = Header(None)) -> int:
    """Obtener tenant_id del header"""
    return int(x_tenant_id) if x_tenant_id else 1


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/feedback")
def submit_category_feedback(
    request: CategoryFeedbackRequest,
    tenant_id: int = Depends(get_tenant_id_from_header)
):
    """
    Enviar feedback sobre categorización para mejorar el sistema ML

    feedback_type:
    - 'accepted': Usuario aceptó la categoría sugerida
    - 'corrected': Usuario corrigió la categoría (debe incluir actual_category)
    - 'rejected': Usuario rechazó completamente la sugerencia
    """
    try:
        from core.ai_pipeline.classification.category_learning_system import CategoryLearningSystem

        learning_system = CategoryLearningSystem()

        feedback_data = {
            'feedback_type': request.feedback_type,
            'actual_category': request.actual_category,
            'user_id': request.user_id,
            'notes': request.notes
        }

        success = learning_system.process_feedback(
            expense_id=request.expense_id,
            feedback_data=feedback_data,
            tenant_id=tenant_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Expense not found")

        logger.info(f"✅ Feedback procesado: expense_id={request.expense_id}, type={request.feedback_type}, tenant_id={tenant_id}")

        return {
            "success": True,
            "message": "Feedback procesado exitosamente",
            "expense_id": request.expense_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=CategoryPredictionResponse)
def predict_category(
    request: CategoryPredictionRequest,
    tenant_id: int = Depends(get_tenant_id_from_header)
):
    """
    Predecir categoría para un gasto usando ML
    """
    try:
        from core.ai_pipeline.classification.enhanced_categorization_engine import EnhancedCategorizationEngine

        engine = EnhancedCategorizationEngine()

        expense_data = {
            'description': request.description,
            'amount': request.amount,
            'merchant_name': request.merchant_name or ""
        }

        prediction = engine.predict_category(
            expense_data=expense_data,
            tenant_id=tenant_id
        )

        return CategoryPredictionResponse(
            predicted_category=prediction.get('category', 'Sin categoría'),
            confidence=prediction.get('confidence', 0.0),
            reasoning=prediction.get('reasoning', ''),
            alternatives=prediction.get('alternatives', [])
        )

    except Exception as e:
        logger.error(f"Error prediciendo categoría: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=List[CategoryMetricsResponse])
def get_category_metrics(
    tenant_id: int = Depends(get_tenant_id_from_header),
    category: Optional[str] = None
):
    """
    Obtener métricas de categorización ML
    """
    try:
        import sqlite3

        conn = sqlite3.connect("unified_mcp_system.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT * FROM category_learning_metrics
                WHERE tenant_id = ? AND category_name = ?
            """, (tenant_id, category))
        else:
            cursor.execute("""
                SELECT * FROM category_learning_metrics
                WHERE tenant_id = ?
                ORDER BY total_predictions DESC
            """, (tenant_id,))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            import json
            results.append(CategoryMetricsResponse(
                category_name=row["category_name"],
                total_predictions=row["total_predictions"],
                correct_predictions=row["correct_predictions"],
                accuracy_rate=row["accuracy_rate"],
                avg_confidence=row["avg_confidence"],
                most_common_keywords=json.loads(row["most_common_keywords"]) if row["most_common_keywords"] else [],
                most_common_merchants=json.loads(row["most_common_merchants"]) if row["most_common_merchants"] else []
            ))

        return results

    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{expense_id}")
def get_prediction_history(
    expense_id: int,
    tenant_id: int = Depends(get_tenant_id_from_header)
):
    """
    Obtener historial de predicciones para un gasto
    """
    try:
        import sqlite3

        conn = sqlite3.connect("unified_mcp_system.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM category_prediction_history
            WHERE expense_id = ? AND tenant_id = ?
            ORDER BY created_at DESC
        """, (expense_id, tenant_id))

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            import json
            history.append({
                "id": row["id"],
                "predicted_category": row["predicted_category"],
                "confidence": row["confidence"],
                "reasoning": row["reasoning"],
                "alternatives": json.loads(row["alternatives"]) if row["alternatives"] else [],
                "prediction_method": row["prediction_method"],
                "ml_model_version": row["ml_model_version"],
                "user_feedback": row["user_feedback"],
                "corrected_category": row["corrected_category"],
                "feedback_date": row["feedback_date"],
                "created_at": row["created_at"]
            })

        return {
            "expense_id": expense_id,
            "history": history,
            "total_predictions": len(history)
        }

    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_learning_stats(tenant_id: int = Depends(get_tenant_id_from_header)):
    """
    Obtener estadísticas generales del sistema de aprendizaje
    """
    try:
        import sqlite3

        conn = sqlite3.connect("unified_mcp_system.db")
        cursor = conn.cursor()

        # Total predicciones
        cursor.execute("""
            SELECT COUNT(*) FROM category_prediction_history
            WHERE tenant_id = ?
        """, (tenant_id,))
        total_predictions = cursor.fetchone()[0]

        # Predicciones con feedback
        cursor.execute("""
            SELECT COUNT(*) FROM category_prediction_history
            WHERE tenant_id = ? AND user_feedback IS NOT NULL
        """, (tenant_id,))
        predictions_with_feedback = cursor.fetchone()[0]

        # Accuracy promedio
        cursor.execute("""
            SELECT AVG(accuracy_rate) FROM category_learning_metrics
            WHERE tenant_id = ?
        """, (tenant_id,))
        avg_accuracy = cursor.fetchone()[0] or 0.0

        # Categorías aprendidas
        cursor.execute("""
            SELECT COUNT(*) FROM category_learning_metrics
            WHERE tenant_id = ? AND total_predictions >= 5
        """, (tenant_id,))
        learned_categories = cursor.fetchone()[0]

        conn.close()

        return {
            "total_predictions": total_predictions,
            "predictions_with_feedback": predictions_with_feedback,
            "feedback_rate": predictions_with_feedback / total_predictions if total_predictions > 0 else 0.0,
            "avg_accuracy": avg_accuracy,
            "learned_categories": learned_categories,
            "tenant_id": tenant_id
        }

    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))
