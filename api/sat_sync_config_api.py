"""
SAT Sync Configuration API
==========================
API para configurar y gestionar sincronización automática con SAT
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import asyncio
import logging

from core.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.sat.sat_auto_sync_job import run_sync_for_company
from core.sat.sat_sync_scheduler import get_scheduler

router = APIRouter(prefix="/sat/sync-config", tags=["SAT Auto Sync"])
logger = logging.getLogger(__name__)


# ============================================================================
# Models
# ============================================================================

class SATSyncConfigCreate(BaseModel):
    """Modelo para crear/actualizar configuración"""
    company_id: int
    enabled: bool = True
    frequency: str = Field("weekly", description="daily, weekly, biweekly, monthly")
    day_of_week: Optional[int] = Field(None, description="0=Lunes, 1=Martes, etc")
    time: str = Field("02:00", description="Hora del día (HH:MM)")
    lookback_days: int = Field(10, description="Días hacia atrás para descargar")
    auto_classify: bool = True
    notify_email: bool = True
    notify_threshold: int = Field(5, description="Mínimo de facturas para notificar")


class SATSyncConfigResponse(BaseModel):
    """Respuesta con configuración"""
    id: int
    company_id: int
    enabled: bool
    frequency: str
    day_of_week: Optional[int]
    time: str
    lookback_days: int
    auto_classify: bool
    notify_email: bool
    notify_threshold: int
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_count: int
    last_sync_error: Optional[str]
    created_at: datetime
    updated_at: datetime


class ManualSyncRequest(BaseModel):
    """Solicitud de sync manual"""
    company_id: int


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/config/{company_id}", response_model=SATSyncConfigResponse)
async def get_config(company_id: int, db: Session = Depends(get_db)):
    """Obtiene configuración de sync para una compañía"""
    try:
        cursor = db.execute(text("""
            SELECT id, company_id, enabled, frequency, day_of_week, time,
                   lookback_days, auto_classify, notify_email, notify_threshold,
                   last_sync_at, last_sync_status, last_sync_count, last_sync_error,
                   created_at, updated_at
            FROM sat_sync_config
            WHERE company_id = :company_id
        """), {"company_id": company_id})

        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Configuración no encontrada")

        return {
            'id': row[0],
            'company_id': row[1],
            'enabled': bool(row[2]),
            'frequency': row[3],
            'day_of_week': row[4],
            'time': row[5],
            'lookback_days': row[6],
            'auto_classify': bool(row[7]),
            'notify_email': bool(row[8]),
            'notify_threshold': row[9],
            'last_sync_at': row[10],
            'last_sync_status': row[11],
            'last_sync_count': row[12] or 0,
            'last_sync_error': row[13],
            'created_at': row[14],
            'updated_at': row[15]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo configuración: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config", response_model=SATSyncConfigResponse)
async def create_or_update_config(
    config: SATSyncConfigCreate,
    db: Session = Depends(get_db)
):
    """Crea o actualiza configuración de sync"""
    try:
        # Verificar si ya existe
        cursor = db.execute(text("""
            SELECT id FROM sat_sync_config WHERE company_id = :company_id
        """), {"company_id": config.company_id})

        existing = cursor.fetchone()

        if existing:
            # Actualizar
            db.execute(text("""
                UPDATE sat_sync_config
                SET enabled = :enabled,
                    frequency = :frequency,
                    day_of_week = :day_of_week,
                    time = :time,
                    lookback_days = :lookback_days,
                    auto_classify = :auto_classify,
                    notify_email = :notify_email,
                    notify_threshold = :notify_threshold,
                    updated_at = :updated_at
                WHERE company_id = :company_id
            """), {
                "enabled": config.enabled,
                "frequency": config.frequency,
                "day_of_week": config.day_of_week,
                "time": config.time,
                "lookback_days": config.lookback_days,
                "auto_classify": config.auto_classify,
                "notify_email": config.notify_email,
                "notify_threshold": config.notify_threshold,
                "updated_at": datetime.utcnow(),
                "company_id": config.company_id
            })

        else:
            # Crear
            db.execute(text("""
                INSERT INTO sat_sync_config (
                    company_id, enabled, frequency, day_of_week, time,
                    lookback_days, auto_classify, notify_email, notify_threshold,
                    created_at, updated_at
                ) VALUES (:company_id, :enabled, :frequency, :day_of_week, :time,
                         :lookback_days, :auto_classify, :notify_email, :notify_threshold,
                         :created_at, :updated_at)
            """), {
                "company_id": config.company_id,
                "enabled": config.enabled,
                "frequency": config.frequency,
                "day_of_week": config.day_of_week,
                "time": config.time,
                "lookback_days": config.lookback_days,
                "auto_classify": config.auto_classify,
                "notify_email": config.notify_email,
                "notify_threshold": config.notify_threshold,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })

        db.commit()

        # Reload scheduler to apply changes
        try:
            scheduler = get_scheduler()
            await scheduler.reload_jobs()
            logger.info(f"Scheduler reloaded after config update for company_id={config.company_id}")
        except Exception as scheduler_exc:
            logger.warning(f"Failed to reload scheduler: {scheduler_exc}")

        # Retornar configuración actualizada
        return await get_config(config.company_id, db)

    except Exception as e:
        logger.error(f"Error guardando configuración: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-sync")
async def trigger_manual_sync(request: ManualSyncRequest):
    """
    Ejecuta sincronización manual para una compañía

    Este endpoint permite al usuario ejecutar la sincronización inmediatamente
    sin esperar al cron job programado.
    """
    try:
        logger.info(f"[MANUAL_SYNC] Iniciando sync manual para company_id={request.company_id}")

        # Ejecutar sync en background
        asyncio.create_task(run_sync_for_company(request.company_id))

        return {
            "success": True,
            "message": f"Sincronización iniciada para company_id={request.company_id}",
            "company_id": request.company_id
        }

    except Exception as e:
        logger.error(f"Error en sync manual: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync-history/{company_id}")
async def get_sync_history(company_id: int, db: Session = Depends(get_db)):
    """Obtiene historial de sincronizaciones"""
    try:
        # Por ahora solo retornamos el último sync de la config
        # En el futuro, podemos crear una tabla sync_history separada
        cursor = db.execute(text("""
            SELECT last_sync_at, last_sync_status, last_sync_count, last_sync_error
            FROM sat_sync_config
            WHERE company_id = :company_id
        """), {"company_id": company_id})

        row = cursor.fetchone()

        if not row:
            return {
                "company_id": company_id,
                "history": []
            }

        return {
            "company_id": company_id,
            "history": [
                {
                    "sync_at": row[0],
                    "status": row[1],
                    "count": row[2] or 0,
                    "error": row[3]
                }
            ] if row[0] else []
        }

    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-count/{company_id}")
async def get_pending_count(company_id: int, db: Session = Depends(get_db)):
    """
    Obtiene cantidad de facturas pendientes de clasificación del SAT

    Útil para mostrar badge en el frontend
    """
    try:
        cursor = db.execute(text("""
            SELECT COUNT(*)
            FROM sat_invoices
            WHERE company_id = :company_id
              AND source = 'sat_auto_sync'
              AND status = 'pending'
        """), {"company_id": str(company_id)})

        count = cursor.fetchone()[0]

        return {
            "company_id": company_id,
            "pending_count": count
        }

    except Exception as e:
        logger.error(f"Error obteniendo count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-jobs")
async def get_scheduled_jobs():
    """
    Obtiene lista de jobs programados en el scheduler

    Útil para debugging y monitoreo
    """
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_scheduled_jobs()

        return {
            "success": True,
            "scheduler_running": scheduler.running,
            "jobs": jobs
        }

    except Exception as e:
        logger.error(f"Error obteniendo jobs programados: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload-scheduler")
async def reload_scheduler():
    """
    Recarga el scheduler manualmente desde la DB

    Útil después de cambios manuales en la configuración
    """
    try:
        scheduler = get_scheduler()
        await scheduler.reload_jobs()

        return {
            "success": True,
            "message": "Scheduler recargado exitosamente"
        }

    except Exception as e:
        logger.error(f"Error recargando scheduler: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
