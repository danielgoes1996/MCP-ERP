"""
SAT Sync Dashboard API
======================
API para visualizar métricas e historial de sincronizaciones SAT
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from core.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text

router = APIRouter(prefix="/sat/sync-dashboard", tags=["SAT Sync Dashboard"])
logger = logging.getLogger(__name__)


# ============================================================================
# Models
# ============================================================================

class SyncHistoryItem(BaseModel):
    """Item de historial de sincronización"""
    id: int
    company_id: int
    sync_started_at: datetime
    sync_completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    status: str
    invoices_downloaded: int
    invoices_classified: int
    invoices_failed: int
    error_message: Optional[str]


class SyncStatsResponse(BaseModel):
    """Estadísticas de sincronización"""
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    total_invoices: int
    avg_duration_seconds: int
    last_7_days: int
    success_rate: float


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/history/{company_id}")
async def get_sync_history(
    company_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Obtiene historial de sincronizaciones para una compañía

    Args:
        company_id: ID de la compañía
        limit: Número máximo de registros a retornar
        offset: Offset para paginación
    """
    try:
        cursor = db.execute(text("""
            SELECT
                id,
                company_id,
                sync_started_at,
                sync_completed_at,
                duration_seconds,
                status,
                invoices_downloaded,
                invoices_classified,
                invoices_failed,
                error_message
            FROM sat_sync_history
            WHERE company_id = :company_id
            ORDER BY sync_started_at DESC
            LIMIT :limit OFFSET :offset
        """), {
            "company_id": company_id,
            "limit": limit,
            "offset": offset
        })

        history = []
        for row in cursor.fetchall():
            history.append({
                'id': row[0],
                'company_id': row[1],
                'sync_started_at': row[2].isoformat() if row[2] else None,
                'sync_completed_at': row[3].isoformat() if row[3] else None,
                'duration_seconds': row[4],
                'status': row[5],
                'invoices_downloaded': row[6] or 0,
                'invoices_classified': row[7] or 0,
                'invoices_failed': row[8] or 0,
                'error_message': row[9]
            })

        # Obtener total count
        cursor_count = db.execute(text("""
            SELECT COUNT(*) FROM sat_sync_history WHERE company_id = :company_id
        """), {"company_id": company_id})

        total = cursor_count.fetchone()[0]

        return {
            "company_id": company_id,
            "history": history,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{company_id}", response_model=SyncStatsResponse)
async def get_sync_stats(company_id: int, db: Session = Depends(get_db)):
    """
    Obtiene estadísticas agregadas de sincronización para una compañía

    Args:
        company_id: ID de la compañía
    """
    try:
        # Calcular fecha de hace 7 días
        seven_days_ago = datetime.now() - timedelta(days=7)

        # Query agregada
        cursor = db.execute(text("""
            SELECT
                COUNT(*) as total_syncs,
                COUNT(*) FILTER (WHERE status = 'success') as successful_syncs,
                COUNT(*) FILTER (WHERE status = 'error') as failed_syncs,
                COALESCE(SUM(invoices_downloaded), 0) as total_invoices,
                COALESCE(AVG(duration_seconds)::INTEGER, 0) as avg_duration_seconds,
                COUNT(*) FILTER (WHERE sync_started_at >= :seven_days_ago) as last_7_days
            FROM sat_sync_history
            WHERE company_id = :company_id
        """), {
            "company_id": company_id,
            "seven_days_ago": seven_days_ago
        })

        row = cursor.fetchone()

        if not row or row[0] == 0:
            # No hay datos, retornar stats vacías
            return {
                "total_syncs": 0,
                "successful_syncs": 0,
                "failed_syncs": 0,
                "total_invoices": 0,
                "avg_duration_seconds": 0,
                "last_7_days": 0,
                "success_rate": 0.0
            }

        total_syncs = row[0]
        successful_syncs = row[1] or 0
        failed_syncs = row[2] or 0
        total_invoices = row[3] or 0
        avg_duration_seconds = row[4] or 0
        last_7_days = row[5] or 0

        # Calcular success rate
        success_rate = (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0.0

        return {
            "total_syncs": total_syncs,
            "successful_syncs": successful_syncs,
            "failed_syncs": failed_syncs,
            "total_invoices": total_invoices,
            "avg_duration_seconds": avg_duration_seconds,
            "last_7_days": last_7_days,
            "success_rate": success_rate
        }

    except Exception as e:
        logger.error(f"Error obteniendo stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/{company_id}")
async def get_sync_config(company_id: int, db: Session = Depends(get_db)):
    """
    Obtiene la configuración actual de sincronización y último estado

    Args:
        company_id: ID de la compañía
    """
    try:
        cursor = db.execute(text("""
            SELECT
                enabled,
                frequency,
                day_of_week,
                time,
                lookback_days,
                auto_classify,
                last_sync_at,
                last_sync_status,
                last_sync_count,
                last_sync_error,
                created_at,
                updated_at
            FROM sat_sync_config
            WHERE company_id = :company_id
        """), {"company_id": company_id})

        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        return {
            "company_id": company_id,
            "enabled": bool(row[0]),
            "frequency": row[1],
            "day_of_week": row[2],
            "time": row[3],
            "lookback_days": row[4],
            "auto_classify": bool(row[5]),
            "last_sync_at": row[6].isoformat() if row[6] else None,
            "last_sync_status": row[7],
            "last_sync_count": row[8] or 0,
            "last_sync_error": row[9],
            "created_at": row[10].isoformat() if row[10] else None,
            "updated_at": row[11].isoformat() if row[11] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo configuración: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-errors/{company_id}")
async def get_recent_errors(
    company_id: int,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """
    Obtiene los errores más recientes de sincronización

    Útil para debugging y monitoreo
    """
    try:
        cursor = db.execute(text("""
            SELECT
                id,
                sync_started_at,
                error_message,
                error_details,
                invoices_downloaded,
                invoices_failed
            FROM sat_sync_history
            WHERE company_id = :company_id
              AND status = 'error'
            ORDER BY sync_started_at DESC
            LIMIT :limit
        """), {
            "company_id": company_id,
            "limit": limit
        })

        errors = []
        for row in cursor.fetchall():
            errors.append({
                'id': row[0],
                'sync_started_at': row[1].isoformat() if row[1] else None,
                'error_message': row[2],
                'error_details': row[3],
                'invoices_downloaded': row[4] or 0,
                'invoices_failed': row[5] or 0
            })

        return {
            "company_id": company_id,
            "recent_errors": errors
        }

    except Exception as e:
        logger.error(f"Error obteniendo errores recientes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
