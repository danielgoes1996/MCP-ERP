"""
Sistema de colas para procesamiento escalable de miles de tickets diarios.

Estrategia:
- Redis/RQ para colas de trabajos
- Workers distribuidos
- Retry automático con backoff exponencial
- Monitoreo de rendimiento
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class JobMetrics:
    """Métricas de rendimiento de jobs."""
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    avg_processing_time: float = 0.0
    jobs_per_hour: float = 0.0
    error_rate: float = 0.0


class InvoicingQueueManager:
    """
    Gestor de colas optimizado para alta concurrencia.

    Características estratégicas:
    - Procesamiento batch para eficiencia
    - Rate limiting para APIs de merchants
    - Circuit breaker para fallos
    - Métricas en tiempo real
    """

    def __init__(self):
        self.use_redis = os.getenv("USE_REDIS", "false").lower() == "true"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.max_workers = int(os.getenv("MAX_WORKERS", "4"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "10"))

        # Rate limiting por merchant
        self.rate_limits = {
            "oxxo": {"calls_per_minute": 60, "last_reset": time.time(), "calls_made": 0},
            "walmart": {"calls_per_minute": 30, "last_reset": time.time(), "calls_made": 0},
            "costco": {"calls_per_minute": 120, "last_reset": time.time(), "calls_made": 0},
        }

        # Circuit breaker states
        self.circuit_breakers = {}

        # Métricas
        self.metrics = JobMetrics()
        self.processing_times: List[float] = []

    async def enqueue_job(self, ticket_id: int, merchant_id: Optional[int] = None, priority: int = 0) -> str:
        """
        Encolar job con prioridad estratégica.

        Prioridades:
        0 = Normal (WhatsApp automático)
        1 = Alta (UI web manual)
        2 = Crítica (reprocessing de errores)
        """
        job_data = {
            "ticket_id": ticket_id,
            "merchant_id": merchant_id,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }

        if self.use_redis:
            return await self._enqueue_redis(job_data)
        else:
            return await self._enqueue_memory(job_data)

    async def _enqueue_redis(self, job_data: Dict) -> str:
        """Encolar usando Redis/RQ para producción."""
        try:
            import redis
            import rq

            redis_conn = redis.from_url(self.redis_url)
            queue_name = f"invoicing_priority_{job_data['priority']}"

            job = rq.Queue(queue_name, connection=redis_conn).enqueue(
                'modules.invoicing_agent.worker.process_ticket_job',
                job_data,
                retry=rq.Retry(max=3, interval=[30, 60, 120])
            )

            logger.info(f"Job {job.id} enqueued to Redis queue {queue_name}")
            return job.id

        except ImportError:
            logger.warning("Redis/RQ not available, falling back to memory queue")
            return await self._enqueue_memory(job_data)

    async def _enqueue_memory(self, job_data: Dict) -> str:
        """Queue en memoria para desarrollo/testing."""
        from modules.invoicing_agent.models import create_invoicing_job

        job_id = create_invoicing_job(
            ticket_id=job_data["ticket_id"],
            merchant_id=job_data.get("merchant_id"),
            company_id="default"
        )

        logger.info(f"Job {job_id} enqueued to memory queue")
        return str(job_id)

    async def process_batch(self, company_id: str = "default") -> Dict[str, Any]:
        """
        Procesar lote de jobs para máxima eficiencia.

        Estrategia batch:
        - Agrupa jobs por merchant para rate limiting
        - Procesa en paralelo cuando es seguro
        - Optimiza llamadas a APIs
        """
        from modules.invoicing_agent.models import list_pending_jobs
        from modules.invoicing_agent.worker import InvoicingWorker

        start_time = time.time()

        # Obtener jobs pendientes
        pending_jobs = list_pending_jobs(company_id)

        if not pending_jobs:
            return {"processed": 0, "errors": 0, "processing_time": 0}

        # Agrupar por merchant para rate limiting
        jobs_by_merchant = {}
        for job in pending_jobs[:self.batch_size]:
            merchant_name = job.get("merchant_name", "unknown")
            if merchant_name not in jobs_by_merchant:
                jobs_by_merchant[merchant_name] = []
            jobs_by_merchant[merchant_name].append(job)

        results = {"processed": 0, "errors": 0, "jobs": []}
        worker = InvoicingWorker()

        # Procesar por merchant respetando rate limits
        for merchant_name, merchant_jobs in jobs_by_merchant.items():
            if not await self._check_rate_limit(merchant_name):
                logger.warning(f"Rate limit reached for {merchant_name}, skipping batch")
                continue

            # Procesar jobs del merchant
            for job in merchant_jobs:
                try:
                    result = await worker.process_job(job["id"])

                    if result["success"]:
                        results["processed"] += 1
                        await self._record_success(job["id"], time.time() - start_time)
                    else:
                        results["errors"] += 1
                        await self._record_error(job["id"], result.get("error"))

                    results["jobs"].append({
                        "job_id": job["id"],
                        "ticket_id": job["ticket_id"],
                        "success": result["success"]
                    })

                except Exception as e:
                    logger.error(f"Error processing job {job['id']}: {str(e)}")
                    results["errors"] += 1

        processing_time = time.time() - start_time
        results["processing_time"] = processing_time

        # Actualizar métricas
        await self._update_metrics(results)

        return results

    async def _check_rate_limit(self, merchant_name: str) -> bool:
        """Verificar y aplicar rate limiting por merchant."""
        if merchant_name not in self.rate_limits:
            return True

        limit_info = self.rate_limits[merchant_name]
        current_time = time.time()

        # Reset counter si ha pasado un minuto
        if current_time - limit_info["last_reset"] >= 60:
            limit_info["calls_made"] = 0
            limit_info["last_reset"] = current_time

        # Verificar límite
        if limit_info["calls_made"] >= limit_info["calls_per_minute"]:
            return False

        limit_info["calls_made"] += 1
        return True

    async def _record_success(self, job_id: int, processing_time: float):
        """Registrar job exitoso."""
        self.processing_times.append(processing_time)

        # Mantener solo las últimas 1000 mediciones
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]

    async def _record_error(self, job_id: int, error_message: str):
        """Registrar error y determinar si retry."""
        logger.error(f"Job {job_id} failed: {error_message}")

    async def _update_metrics(self, batch_results: Dict):
        """Actualizar métricas de rendimiento."""
        self.metrics.total_jobs += len(batch_results["jobs"])
        self.metrics.completed_jobs += batch_results["processed"]
        self.metrics.failed_jobs += batch_results["errors"]

        if self.processing_times:
            self.metrics.avg_processing_time = sum(self.processing_times) / len(self.processing_times)

        # Calcular jobs por hora
        if self.processing_times:
            avg_time = self.metrics.avg_processing_time
            self.metrics.jobs_per_hour = 3600 / avg_time if avg_time > 0 else 0

        # Error rate
        if self.metrics.total_jobs > 0:
            self.metrics.error_rate = self.metrics.failed_jobs / self.metrics.total_jobs

    def get_metrics(self) -> Dict[str, Any]:
        """Obtener métricas actuales para dashboard."""
        return {
            "total_jobs": self.metrics.total_jobs,
            "completed_jobs": self.metrics.completed_jobs,
            "failed_jobs": self.metrics.failed_jobs,
            "avg_processing_time": round(self.metrics.avg_processing_time, 2),
            "jobs_per_hour": round(self.metrics.jobs_per_hour, 1),
            "error_rate": round(self.metrics.error_rate * 100, 2),
            "current_rate_limits": {
                name: {
                    "calls_made": info["calls_made"],
                    "limit": info["calls_per_minute"],
                    "reset_in": max(0, 60 - (time.time() - info["last_reset"]))
                }
                for name, info in self.rate_limits.items()
            }
        }

    async def start_background_processor(self):
        """
        Iniciar procesador en background para alta concurrencia.

        Ideal para producción:
        - Procesa continuamente
        - Auto-scaling basado en carga
        - Manejo inteligente de errores
        """
        logger.info("Starting background queue processor")

        while True:
            try:
                result = await self.process_batch()

                if result["processed"] > 0:
                    logger.info(f"Batch processed: {result['processed']} success, {result['errors']} errors")

                # Ajustar delay basado en carga
                if result["processed"] == 0:
                    await asyncio.sleep(5)  # Sin trabajo, esperar más
                elif result["errors"] > result["processed"]:
                    await asyncio.sleep(10)  # Muchos errores, pausar
                else:
                    await asyncio.sleep(1)  # Procesando bien, continuar rápido

            except Exception as e:
                logger.error(f"Error in background processor: {str(e)}")
                await asyncio.sleep(30)  # Error, pausar y continuar


# Instancia global del queue manager
queue_manager = InvoicingQueueManager()


# ===================================================================
# CLI PARA EJECUTAR WORKERS
# ===================================================================

async def run_queue_worker():
    """Ejecutar worker de colas para producción."""
    logger.info("Starting invoicing queue worker")
    await queue_manager.start_background_processor()


if __name__ == "__main__":
    pass

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Ejecutar worker
    asyncio.run(run_queue_worker())