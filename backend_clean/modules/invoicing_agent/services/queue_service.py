"""
Queue Service - Sistema de colas robusto para procesamiento de tickets.

Arquitectura escalable usando Redis/Celery para procesar miles de tickets en paralelo.
Incluye reintentos automáticos, prioridades y monitoreo.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Estados de los jobs en la cola."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Prioridades de procesamiento."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20


@dataclass
class Job:
    """Definición de un job de procesamiento."""
    id: str
    task_name: str
    ticket_id: int
    company_id: str
    status: JobStatus
    priority: JobPriority
    created_at: datetime
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializar job a diccionario."""
        data = asdict(self)
        # Convertir enums y datetime a strings
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        data['created_at'] = self.created_at.isoformat()
        data['scheduled_at'] = self.scheduled_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Deserializar job desde diccionario."""
        data['status'] = JobStatus(data['status'])
        data['priority'] = JobPriority(data['priority'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['scheduled_at'] = datetime.fromisoformat(data['scheduled_at'])
        if data.get('started_at'):
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if data.get('completed_at'):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)


class QueueBackend:
    """Backend abstracto para sistemas de cola."""

    async def enqueue(self, job: Job) -> bool:
        """Encolar un job."""
        raise NotImplementedError

    async def dequeue(self, queue_name: str) -> Optional[Job]:
        """Obtener siguiente job de la cola."""
        raise NotImplementedError

    async def update_job(self, job: Job) -> bool:
        """Actualizar estado de un job."""
        raise NotImplementedError

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Obtener job por ID."""
        raise NotImplementedError

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de las colas."""
        raise NotImplementedError


class RedisQueueBackend(QueueBackend):
    """Backend usando Redis para persistencia y colas."""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None
        self.queue_prefix = "invoicing_queue"
        self.job_prefix = "invoicing_job"

    async def _get_redis(self):
        """Obtener cliente Redis con lazy loading."""
        if not self.redis_client:
            try:
                import aioredis
                self.redis_client = aioredis.from_url(self.redis_url)
                # Test connection
                await self.redis_client.ping()
                logger.info("Conexión a Redis establecida")
            except ImportError:
                logger.error("aioredis no instalado. Usar: pip install aioredis")
                raise
            except Exception as e:
                logger.error(f"Error conectando a Redis: {e}")
                raise
        return self.redis_client

    async def enqueue(self, job: Job) -> bool:
        """Encolar job en Redis con prioridad."""
        try:
            redis = await self._get_redis()

            # Guardar job data
            job_key = f"{self.job_prefix}:{job.id}"
            await redis.set(job_key, json.dumps(job.to_dict()), ex=86400 * 7)  # Expire en 7 días

            # Agregar a cola de prioridad
            queue_key = f"{self.queue_prefix}:{job.company_id}"
            score = job.priority.value * 1000000 + int(time.time())  # Prioridad + timestamp
            await redis.zadd(queue_key, {job.id: score})

            logger.info(f"Job {job.id} encolado con prioridad {job.priority.value}")
            return True

        except Exception as e:
            logger.error(f"Error encolando job {job.id}: {e}")
            return False

    async def dequeue(self, company_id: str = "default") -> Optional[Job]:
        """Obtener job de mayor prioridad."""
        try:
            redis = await self._get_redis()
            queue_key = f"{self.queue_prefix}:{company_id}"

            # Obtener job de mayor prioridad (score más alto)
            result = await redis.zpopmax(queue_key)
            if not result:
                return None

            job_id, score = result[0]
            job_key = f"{self.job_prefix}:{job_id}"

            # Obtener data del job
            job_data = await redis.get(job_key)
            if not job_data:
                logger.warning(f"Job data no encontrada para {job_id}")
                return None

            job = Job.from_dict(json.loads(job_data))
            logger.debug(f"Job {job_id} obtenido de cola {company_id}")
            return job

        except Exception as e:
            logger.error(f"Error obteniendo job de cola {company_id}: {e}")
            return None

    async def update_job(self, job: Job) -> bool:
        """Actualizar job en Redis."""
        try:
            redis = await self._get_redis()
            job_key = f"{self.job_prefix}:{job.id}"
            await redis.set(job_key, json.dumps(job.to_dict()), ex=86400 * 7)
            return True
        except Exception as e:
            logger.error(f"Error actualizando job {job.id}: {e}")
            return False

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Obtener job por ID."""
        try:
            redis = await self._get_redis()
            job_key = f"{self.job_prefix}:{job_id}"
            job_data = await redis.get(job_key)
            if job_data:
                return Job.from_dict(json.loads(job_data))
            return None
        except Exception as e:
            logger.error(f"Error obteniendo job {job_id}: {e}")
            return None

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de Redis."""
        try:
            redis = await self._get_redis()

            # Obtener todas las colas
            queue_pattern = f"{self.queue_prefix}:*"
            queue_keys = await redis.keys(queue_pattern)

            stats = {
                "total_queues": len(queue_keys),
                "queues": {},
                "total_pending_jobs": 0
            }

            for queue_key in queue_keys:
                company_id = queue_key.decode().split(":")[-1]
                queue_size = await redis.zcard(queue_key)
                stats["queues"][company_id] = queue_size
                stats["total_pending_jobs"] += queue_size

            return stats

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"error": str(e)}


class MemoryQueueBackend(QueueBackend):
    """Backend en memoria para desarrollo/testing."""

    def __init__(self):
        self.queues: Dict[str, List[Job]] = {}
        self.jobs: Dict[str, Job] = {}

    async def enqueue(self, job: Job) -> bool:
        """Encolar job en memoria."""
        try:
            # Guardar job
            self.jobs[job.id] = job

            # Agregar a cola con orden por prioridad
            queue_name = job.company_id
            if queue_name not in self.queues:
                self.queues[queue_name] = []

            # Insertar en posición correcta por prioridad
            inserted = False
            for i, existing_job in enumerate(self.queues[queue_name]):
                if job.priority.value > existing_job.priority.value:
                    self.queues[queue_name].insert(i, job)
                    inserted = True
                    break

            if not inserted:
                self.queues[queue_name].append(job)

            logger.info(f"Job {job.id} encolado en memoria")
            return True

        except Exception as e:
            logger.error(f"Error encolando job {job.id}: {e}")
            return False

    async def dequeue(self, company_id: str = "default") -> Optional[Job]:
        """Obtener job de mayor prioridad."""
        try:
            if company_id not in self.queues or not self.queues[company_id]:
                return None

            # Obtener job de mayor prioridad (primero en la lista)
            job = self.queues[company_id].pop(0)
            logger.debug(f"Job {job.id} obtenido de cola {company_id}")
            return job

        except Exception as e:
            logger.error(f"Error obteniendo job de cola {company_id}: {e}")
            return None

    async def update_job(self, job: Job) -> bool:
        """Actualizar job en memoria."""
        try:
            self.jobs[job.id] = job
            return True
        except Exception as e:
            logger.error(f"Error actualizando job {job.id}: {e}")
            return False

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Obtener job por ID."""
        return self.jobs.get(job_id)

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de memoria."""
        stats = {
            "total_queues": len(self.queues),
            "queues": {name: len(jobs) for name, jobs in self.queues.items()},
            "total_pending_jobs": sum(len(jobs) for jobs in self.queues.values()),
            "total_jobs": len(self.jobs)
        }
        return stats


class QueueService:
    """
    Servicio principal de colas con características empresariales.

    Características:
    - Múltiples backends (Redis, memoria)
    - Reintentos automáticos
    - Prioridades
    - Monitoreo y métricas
    - Balanceador de carga
    """

    def __init__(self, backend: Optional[QueueBackend] = None):
        self.backend = backend or self._create_default_backend()
        self.task_handlers: Dict[str, Callable] = {}
        self.metrics = {
            "jobs_enqueued": 0,
            "jobs_processed": 0,
            "jobs_failed": 0,
            "jobs_retried": 0,
            "average_processing_time": 0.0
        }

    def _create_default_backend(self) -> QueueBackend:
        """Crear backend por defecto basado en configuración."""
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                return RedisQueueBackend()
            except Exception as e:
                logger.warning(f"No se pudo inicializar Redis, usando memoria: {e}")

        return MemoryQueueBackend()

    async def enqueue_ticket_processing(
        self,
        ticket_id: int,
        company_id: str = "default",
        priority: JobPriority = JobPriority.NORMAL,
        delay_seconds: int = 0
    ) -> str:
        """
        Encolar procesamiento de ticket.

        Args:
            ticket_id: ID del ticket a procesar
            company_id: ID de la empresa
            priority: Prioridad del job
            delay_seconds: Retraso antes de procesar

        Returns:
            ID del job creado
        """
        job_id = str(uuid.uuid4())
        scheduled_at = datetime.utcnow() + timedelta(seconds=delay_seconds)

        job = Job(
            id=job_id,
            task_name="process_ticket",
            ticket_id=ticket_id,
            company_id=company_id,
            status=JobStatus.PENDING,
            priority=priority,
            created_at=datetime.utcnow(),
            scheduled_at=scheduled_at,
            metadata={"task_type": "ticket_processing"}
        )

        success = await self.backend.enqueue(job)
        if success:
            self.metrics["jobs_enqueued"] += 1
            logger.info(f"Ticket {ticket_id} encolado como job {job_id}")
        else:
            logger.error(f"Error encolando ticket {ticket_id}")

        return job_id

    async def process_jobs(
        self,
        company_id: str = "default",
        max_jobs: int = 10,
        timeout_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        Procesar jobs pendientes de una empresa.

        Args:
            company_id: ID de empresa a procesar
            max_jobs: Máximo número de jobs a procesar
            timeout_seconds: Timeout por job

        Returns:
            Estadísticas de procesamiento
        """
        results = {
            "processed": 0,
            "failed": 0,
            "skipped": 0,
            "results": []
        }

        for _ in range(max_jobs):
            job = await self.backend.dequeue(company_id)
            if not job:
                break

            # Verificar si es hora de procesar
            if job.scheduled_at > datetime.utcnow():
                # Re-encolar para más tarde
                await self.backend.enqueue(job)
                results["skipped"] += 1
                continue

            # Procesar job
            result = await self._process_single_job(job, timeout_seconds)
            results["results"].append(result)

            if result["success"]:
                results["processed"] += 1
                self.metrics["jobs_processed"] += 1
            else:
                results["failed"] += 1
                self.metrics["jobs_failed"] += 1

        return results

    async def _process_single_job(self, job: Job, timeout_seconds: int) -> Dict[str, Any]:
        """Procesar un job individual."""
        start_time = time.time()

        try:
            # Marcar como procesando
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()
            await self.backend.update_job(job)

            # Obtener handler para el task
            handler = self.task_handlers.get(job.task_name)
            if not handler:
                raise ValueError(f"No hay handler para task: {job.task_name}")

            # Ejecutar con timeout
            result = await asyncio.wait_for(
                handler(job),
                timeout=timeout_seconds
            )

            # Marcar como completado
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result = result
            await self.backend.update_job(job)

            processing_time = time.time() - start_time
            self._update_processing_time(processing_time)

            logger.info(f"Job {job.id} completado en {processing_time:.2f}s")
            return {
                "job_id": job.id,
                "success": True,
                "result": result,
                "processing_time": processing_time
            }

        except asyncio.TimeoutError:
            error_msg = f"Job {job.id} timeout después de {timeout_seconds}s"
            logger.error(error_msg)
            return await self._handle_job_failure(job, error_msg)

        except Exception as e:
            error_msg = f"Error procesando job {job.id}: {str(e)}"
            logger.error(error_msg)
            return await self._handle_job_failure(job, error_msg)

    async def _handle_job_failure(self, job: Job, error_message: str) -> Dict[str, Any]:
        """Manejar fallo de job con reintentos."""
        job.error_message = error_message
        job.retry_count += 1

        if job.retry_count <= job.max_retries:
            # Programar reintento con backoff exponencial
            delay = min(300, 60 * (2 ** (job.retry_count - 1)))  # Max 5 min
            job.status = JobStatus.RETRYING
            job.scheduled_at = datetime.utcnow() + timedelta(seconds=delay)

            await self.backend.enqueue(job)
            self.metrics["jobs_retried"] += 1

            logger.warning(f"Job {job.id} programado para reintento {job.retry_count} en {delay}s")
            return {
                "job_id": job.id,
                "success": False,
                "error": error_message,
                "retry_scheduled": True,
                "retry_count": job.retry_count
            }
        else:
            # Máximo de reintentos alcanzado
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            await self.backend.update_job(job)

            logger.error(f"Job {job.id} falló después de {job.max_retries} reintentos")
            return {
                "job_id": job.id,
                "success": False,
                "error": error_message,
                "retry_scheduled": False,
                "final_failure": True
            }

    def register_task_handler(self, task_name: str, handler: Callable):
        """Registrar handler para un tipo de task."""
        self.task_handlers[task_name] = handler
        logger.info(f"Handler registrado para task: {task_name}")

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Obtener estado de un job."""
        job = await self.backend.get_job(job_id)
        return job.to_dict() if job else None

    async def get_queue_metrics(self) -> Dict[str, Any]:
        """Obtener métricas completas del sistema."""
        backend_stats = await self.backend.get_queue_stats()
        return {
            **self.metrics,
            **backend_stats,
            "task_handlers": list(self.task_handlers.keys())
        }

    def _update_processing_time(self, processing_time: float):
        """Actualizar promedio de tiempo de procesamiento."""
        total = self.metrics["jobs_processed"]
        current_avg = self.metrics["average_processing_time"]
        self.metrics["average_processing_time"] = (
            (current_avg * (total - 1) + processing_time) / total
        )


# Instancia global
queue_service = QueueService()


# Worker daemon
async def run_queue_worker(
    company_id: str = "default",
    interval: int = 10,
    max_jobs_per_cycle: int = 5
):
    """
    Ejecutar worker daemon que procesa jobs continuamente.

    Args:
        company_id: ID de empresa a procesar
        interval: Intervalo entre ciclos en segundos
        max_jobs_per_cycle: Máximo jobs por ciclo
    """
    logger.info(f"Iniciando queue worker para {company_id}, interval: {interval}s")

    while True:
        try:
            result = await queue_service.process_jobs(
                company_id=company_id,
                max_jobs=max_jobs_per_cycle
            )

            if result["processed"] > 0 or result["failed"] > 0:
                logger.info(f"Ciclo completado: {result['processed']} procesados, {result['failed']} fallaron")

            await asyncio.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Worker detenido por usuario")
            break
        except Exception as e:
            logger.error(f"Error en worker: {e}")
            await asyncio.sleep(interval)


if __name__ == "__main__":
    # Test del sistema de colas
    async def test_queue_system():
        print("=== Test Queue System ===")

        # Función dummy para procesar tickets
        async def dummy_ticket_processor(job: Job) -> Dict[str, Any]:
            await asyncio.sleep(0.1)  # Simular procesamiento
            return {
                "ticket_id": job.ticket_id,
                "processed_at": datetime.utcnow().isoformat(),
                "success": True
            }

        # Registrar handler
        queue_service.register_task_handler("process_ticket", dummy_ticket_processor)

        # Encolar algunos jobs
        job_ids = []
        for i in range(5):
            priority = JobPriority.HIGH if i < 2 else JobPriority.NORMAL
            job_id = await queue_service.enqueue_ticket_processing(
                ticket_id=100 + i,
                priority=priority
            )
            job_ids.append(job_id)
            print(f"Encolado ticket {100 + i} como job {job_id}")

        # Procesar jobs
        print("\nProcesando jobs...")
        result = await queue_service.process_jobs(max_jobs=10)
        print(f"Resultado: {result}")

        # Mostrar métricas
        print("\n=== Métricas ===")
        metrics = await queue_service.get_queue_metrics()
        for key, value in metrics.items():
            print(f"{key}: {value}")

    asyncio.run(test_queue_system())