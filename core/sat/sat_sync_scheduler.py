"""
SAT Sync Scheduler
==================
Scheduler que ejecuta sincronizaciones automáticas del SAT según configuración de cada compañía.

Soporta frecuencias:
- daily: Diario a la hora especificada
- weekly: Semanal en día específico
- biweekly: Quincenal
- monthly: Mensual (día 1 de cada mes)
"""

import logging
import asyncio
from datetime import datetime, time
from typing import List, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from core.database import get_db_session
from core.sat.sat_auto_sync_job import run_sync_for_company

logger = logging.getLogger(__name__)


class SATSyncScheduler:
    """Scheduler para sincronizaciones automáticas del SAT"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.running = False

    async def start(self):
        """Inicia el scheduler y carga jobs desde DB"""
        if self.running:
            print("[SAT_SCHEDULER] Scheduler ya está corriendo")
            logger.warning("[SAT_SCHEDULER] Scheduler ya está corriendo")
            return

        print("[SAT_SCHEDULER] Iniciando scheduler...")
        logger.info("[SAT_SCHEDULER] Iniciando scheduler...")

        # Cargar configuraciones de DB y crear jobs
        await self._load_jobs_from_db()

        # Iniciar scheduler
        print("[SAT_SCHEDULER] Starting APScheduler...")
        self.scheduler.start()
        self.running = True

        print(f"[SAT_SCHEDULER] ✅ Scheduler iniciado correctamente con {len(self.scheduler.get_jobs())} jobs")
        logger.info("[SAT_SCHEDULER] ✅ Scheduler iniciado correctamente")

    async def stop(self):
        """Detiene el scheduler"""
        if not self.running:
            return

        logger.info("[SAT_SCHEDULER] Deteniendo scheduler...")
        self.scheduler.shutdown(wait=True)
        self.running = False
        logger.info("[SAT_SCHEDULER] ✅ Scheduler detenido")

    async def _load_jobs_from_db(self):
        """Carga configuraciones de sync desde DB y crea jobs en el scheduler"""
        try:
            print("[SAT_SCHEDULER] Loading jobs from database...")
            with get_db_session() as db:
                cursor = db.execute(text("""
                    SELECT company_id, frequency, day_of_week, time
                    FROM sat_sync_config
                    WHERE enabled = true
                """))

                configs = cursor.fetchall()

                print(f"[SAT_SCHEDULER] Found {len(configs)} active configurations")
                logger.info(f"[SAT_SCHEDULER] Cargando {len(configs)} configuraciones activas")

                for row in configs:
                    company_id = row[0]
                    frequency = row[1]
                    day_of_week = row[2]
                    time_str = row[3]  # Format: "HH:MM"

                    await self._add_job_for_company(
                        company_id=company_id,
                        frequency=frequency,
                        day_of_week=day_of_week,
                        time_str=time_str
                    )

        except Exception as e:
            logger.error(f"[SAT_SCHEDULER] Error cargando jobs: {e}", exc_info=True)

    async def _add_job_for_company(
        self,
        company_id: int,
        frequency: str,
        day_of_week: int = None,
        time_str: str = "02:00"
    ):
        """
        Agrega un job al scheduler para una compañía específica

        Args:
            company_id: ID de la compañía
            frequency: 'daily', 'weekly', 'biweekly', 'monthly'
            day_of_week: 0=Lunes, 1=Martes, ... (solo para weekly)
            time_str: Hora del día en formato "HH:MM"
        """
        try:
            # Parsear hora
            hour, minute = map(int, time_str.split(':'))

            # Construir trigger según frecuencia
            if frequency == 'daily':
                trigger = CronTrigger(hour=hour, minute=minute)
                desc = f"diario a las {time_str}"

            elif frequency == 'weekly':
                # day_of_week: 0=Mon, 6=Sun (APScheduler)
                trigger = CronTrigger(day_of_week=day_of_week or 0, hour=hour, minute=minute)
                days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                day_name = days[day_of_week] if day_of_week is not None else 'Lunes'
                desc = f"semanal {day_name} a las {time_str}"

            elif frequency == 'biweekly':
                # Ejecutar cada 2 semanas en el día especificado
                # APScheduler no tiene "every 2 weeks", usamos week con intervalo
                trigger = CronTrigger(day_of_week=day_of_week or 0, hour=hour, minute=minute, week='*/2')
                desc = f"quincenal a las {time_str}"

            elif frequency == 'monthly':
                # Día 1 de cada mes
                trigger = CronTrigger(day=1, hour=hour, minute=minute)
                desc = f"mensual (día 1) a las {time_str}"

            else:
                logger.warning(f"[SAT_SCHEDULER] Frecuencia no soportada: {frequency}")
                return

            # Agregar job al scheduler
            job_id = f"sat_sync_company_{company_id}"

            self.scheduler.add_job(
                func=self._execute_sync_job,
                trigger=trigger,
                args=[company_id],
                id=job_id,
                name=f"SAT Sync - Company {company_id}",
                replace_existing=True,
                misfire_grace_time=3600  # 1 hora de gracia si se pierde una ejecución
            )

            logger.info(f"[SAT_SCHEDULER] ✅ Job agregado: company_id={company_id}, {desc}")

        except Exception as e:
            logger.error(f"[SAT_SCHEDULER] Error agregando job para company_id={company_id}: {e}")

    async def _execute_sync_job(self, company_id: int):
        """
        Ejecuta el job de sincronización para una compañía

        Esta función se llama automáticamente por el scheduler
        """
        logger.info(f"[SAT_SCHEDULER] ⏰ Ejecutando sync programado para company_id={company_id}")

        try:
            success, count, error = await run_sync_for_company(company_id)

            if success:
                logger.info(f"[SAT_SCHEDULER] ✅ Sync completado: {count} facturas procesadas")
            else:
                logger.error(f"[SAT_SCHEDULER] ❌ Error en sync: {error}")

        except Exception as e:
            logger.error(f"[SAT_SCHEDULER] ❌ Excepción en sync job: {e}", exc_info=True)

    async def reload_jobs(self):
        """
        Recarga todos los jobs desde la DB

        Útil cuando se actualiza la configuración de una compañía
        """
        logger.info("[SAT_SCHEDULER] Recargando jobs desde DB...")

        # Limpiar jobs existentes
        self.scheduler.remove_all_jobs()

        # Recargar desde DB
        await self._load_jobs_from_db()

        logger.info("[SAT_SCHEDULER] ✅ Jobs recargados")

    def get_scheduled_jobs(self) -> List[Dict]:
        """
        Obtiene lista de jobs programados

        Returns:
            Lista de dicts con info de cada job
        """
        jobs = []

        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time

            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': next_run.isoformat() if next_run else None,
                'trigger': str(job.trigger)
            })

        return jobs


# Singleton global
_scheduler_instance: SATSyncScheduler = None


def get_scheduler() -> SATSyncScheduler:
    """Obtiene instancia singleton del scheduler"""
    global _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = SATSyncScheduler()

    return _scheduler_instance


async def start_scheduler():
    """Inicia el scheduler (llamar en startup de FastAPI)"""
    scheduler = get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """Detiene el scheduler (llamar en shutdown de FastAPI)"""
    scheduler = get_scheduler()
    await scheduler.stop()
