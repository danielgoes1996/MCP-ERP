"""
Worker System - Sistema completo de workers con cola de tareas
Punto 22 de Auditoría: Implementa worker system con task queue y job scheduling
Resuelve campos faltantes: progress, worker_metadata, retry_policy
"""

import asyncio
import hashlib
import json
import logging
import time
import threading
import signal
import os
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from enum import Enum
from dataclasses import dataclass
import sqlite3
from datetime import datetime, timedelta
import uuid
import psutil
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import queue

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"

@dataclass
class RetryPolicy:
    """Política de reintentos para tareas"""
    max_attempts: int = 3
    initial_delay_seconds: int = 5
    max_delay_seconds: int = 300
    backoff_multiplier: float = 2.0
    retry_on_timeout: bool = True
    retry_on_error: bool = True
    retry_error_patterns: List[str] = None

    def __post_init__(self):
        if self.retry_error_patterns is None:
            self.retry_error_patterns = [
                "connection.*timeout",
                "network.*error",
                "temporary.*failure",
                "503.*service.*unavailable"
            ]

@dataclass
class WorkerMetadata:
    """Metadatos del worker"""
    worker_id: str
    worker_name: str
    worker_type: str
    capabilities: List[str]
    max_concurrent_tasks: int
    memory_limit_mb: int
    cpu_cores: int
    version: str
    heartbeat_interval: int = 30
    task_timeout_seconds: int = 3600
    registration_time: datetime = None
    last_heartbeat: datetime = None

@dataclass
class TaskProgress:
    """Progreso de ejecución de tarea"""
    percentage: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    estimated_remaining_seconds: int = 0
    details: Dict[str, Any] = None
    last_updated: datetime = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()

@dataclass
class Task:
    """Definición de tarea"""
    task_id: str
    task_type: str
    task_data: Dict[str, Any]
    priority: TaskPriority
    retry_policy: RetryPolicy
    timeout_seconds: int
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    depends_on: List[str] = None
    tags: List[str] = None
    progress: TaskProgress = None
    worker_metadata: WorkerMetadata = None

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []
        if self.tags is None:
            self.tags = []
        if self.progress is None:
            self.progress = TaskProgress()

class TaskQueue:
    """Cola de tareas con prioridad"""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.queue = queue.PriorityQueue(maxsize=max_size)
        self.pending_tasks = {}  # task_id -> task
        self.lock = threading.RLock()

    def enqueue(self, task: Task) -> bool:
        """Encola una tarea"""
        try:
            with self.lock:
                if len(self.pending_tasks) >= self.max_size:
                    return False

                # Priority queue usa tuplas (priority, item)
                # Menor número = mayor prioridad
                priority_value = -task.priority.value  # Invertir para mayor prioridad primero
                timestamp = task.created_at.timestamp()

                self.queue.put((priority_value, timestamp, task.task_id))
                self.pending_tasks[task.task_id] = task

                logger.debug(f"Enqueued task {task.task_id} with priority {task.priority.name}")
                return True

        except Exception as e:
            logger.error(f"Error enqueuing task {task.task_id}: {e}")
            return False

    def dequeue(self, timeout: float = 1.0) -> Optional[Task]:
        """Desencola la tarea de mayor prioridad"""
        try:
            # Obtener el task_id de la cola
            priority_value, timestamp, task_id = self.queue.get(timeout=timeout)

            with self.lock:
                task = self.pending_tasks.pop(task_id, None)
                if task:
                    logger.debug(f"Dequeued task {task_id}")
                    return task
                else:
                    logger.warning(f"Task {task_id} not found in pending tasks")
                    return None

        except queue.Empty:
            return None
        except Exception as e:
            logger.error(f"Error dequeuing task: {e}")
            return None

    def get_size(self) -> int:
        """Obtiene el tamaño actual de la cola"""
        with self.lock:
            return len(self.pending_tasks)

    def peek_next(self) -> Optional[Task]:
        """Ve la siguiente tarea sin removerla"""
        try:
            with self.lock:
                if self.queue.empty():
                    return None

                # Obtener elemento sin remover (hack usando queue interno)
                priority_value, timestamp, task_id = self.queue.queue[0]
                return self.pending_tasks.get(task_id)

        except Exception as e:
            logger.error(f"Error peeking next task: {e}")
            return None

class Worker:
    """Worker individual para procesar tareas"""

    def __init__(self, worker_metadata: WorkerMetadata, task_handlers: Dict[str, Callable]):
        self.metadata = worker_metadata
        self.task_handlers = task_handlers
        self.status = WorkerStatus.OFFLINE
        self.current_tasks = {}  # task_id -> task
        self.running = False
        self.shutdown_event = threading.Event()
        self.heartbeat_thread = None
        self.processing_thread = None
        self.task_queue = TaskQueue()

        # Performance tracking
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.total_processing_time = 0.0
        self.last_activity = datetime.utcnow()

    async def start(self):
        """Inicia el worker"""
        try:
            self.running = True
            self.status = WorkerStatus.IDLE
            self.metadata.registration_time = datetime.utcnow()
            self.metadata.last_heartbeat = datetime.utcnow()

            # Iniciar heartbeat
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()

            # Iniciar loop de procesamiento
            self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
            self.processing_thread.start()

            logger.info(f"Worker {self.metadata.worker_id} started")

        except Exception as e:
            logger.error(f"Error starting worker {self.metadata.worker_id}: {e}")
            self.status = WorkerStatus.ERROR
            raise

    async def stop(self):
        """Detiene el worker gracefully"""
        try:
            logger.info(f"Stopping worker {self.metadata.worker_id}")
            self.running = False
            self.shutdown_event.set()

            # Esperar a que terminen las tareas actuales
            timeout = 30  # 30 segundos de gracia
            start_time = time.time()

            while self.current_tasks and (time.time() - start_time) < timeout:
                await asyncio.sleep(1)

            # Cancelar tareas restantes
            for task_id in list(self.current_tasks.keys()):
                await self._cancel_task(task_id)

            self.status = WorkerStatus.OFFLINE
            logger.info(f"Worker {self.metadata.worker_id} stopped")

        except Exception as e:
            logger.error(f"Error stopping worker {self.metadata.worker_id}: {e}")

    def submit_task(self, task: Task) -> bool:
        """Envía una tarea al worker"""
        try:
            if len(self.current_tasks) >= self.metadata.max_concurrent_tasks:
                return self.task_queue.enqueue(task)

            # Procesar inmediatamente si hay capacidad
            return self._assign_task(task)

        except Exception as e:
            logger.error(f"Error submitting task {task.task_id}: {e}")
            return False

    def _assign_task(self, task: Task) -> bool:
        """Asigna una tarea para procesamiento inmediato"""
        try:
            if len(self.current_tasks) >= self.metadata.max_concurrent_tasks:
                return False

            # Verificar si el worker puede manejar este tipo de tarea
            if task.task_type not in self.task_handlers:
                logger.warning(f"Worker {self.metadata.worker_id} cannot handle task type {task.task_type}")
                return False

            # Asignar tarea
            task.worker_metadata = self.metadata
            self.current_tasks[task.task_id] = task
            self.status = WorkerStatus.BUSY

            # Procesar en background
            threading.Thread(
                target=self._process_task_sync,
                args=(task,),
                daemon=True
            ).start()

            logger.info(f"Assigned task {task.task_id} to worker {self.metadata.worker_id}")
            return True

        except Exception as e:
            logger.error(f"Error assigning task {task.task_id}: {e}")
            return False

    def _processing_loop(self):
        """Loop principal de procesamiento"""
        while self.running and not self.shutdown_event.is_set():
            try:
                # Verificar si hay capacidad para más tareas
                if len(self.current_tasks) < self.metadata.max_concurrent_tasks:
                    # Intentar tomar tarea de la cola
                    task = self.task_queue.dequeue(timeout=1.0)
                    if task:
                        self._assign_task(task)

                # Actualizar estado
                if not self.current_tasks:
                    self.status = WorkerStatus.IDLE
                else:
                    self.status = WorkerStatus.BUSY

                time.sleep(0.1)  # Pequeña pausa para evitar CPU spinning

            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                time.sleep(1)

    def _process_task_sync(self, task: Task):
        """Procesa una tarea de manera síncrona (wrapper para async)"""
        try:
            # Crear nuevo event loop para este thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(self._process_task(task))
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error in sync task processing: {e}")
            self._handle_task_error(task, e)

    async def _process_task(self, task: Task):
        """Procesa una tarea individual"""
        start_time = time.time()

        try:
            logger.info(f"Processing task {task.task_id} of type {task.task_type}")

            # Actualizar progreso inicial
            task.progress.current_step = "Initializing"
            task.progress.percentage = 0.0
            task.progress.last_updated = datetime.utcnow()

            # Obtener handler para el tipo de tarea
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler for task type {task.task_type}")

            # Configurar timeout
            try:
                result = await asyncio.wait_for(
                    handler(task, self._update_progress),
                    timeout=task.timeout_seconds
                )

                # Tarea completada exitosamente
                task.progress.percentage = 100.0
                task.progress.current_step = "Completed"
                task.progress.completed_steps = task.progress.total_steps
                task.progress.last_updated = datetime.utcnow()

                # Actualizar estadísticas
                processing_time = time.time() - start_time
                self.tasks_completed += 1
                self.total_processing_time += processing_time
                self.last_activity = datetime.utcnow()

                logger.info(f"Task {task.task_id} completed in {processing_time:.2f}s")

                # Notificar al sistema de resultados
                await self._notify_task_completion(task, result)

            except asyncio.TimeoutError:
                logger.warning(f"Task {task.task_id} timed out after {task.timeout_seconds}s")
                await self._handle_task_timeout(task)

        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {e}")
            self._handle_task_error(task, e)

        finally:
            # Remover tarea de las actuales
            self.current_tasks.pop(task.task_id, None)

    async def _update_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """Actualiza el progreso de una tarea"""
        try:
            task = self.current_tasks.get(task_id)
            if not task:
                return

            # Actualizar campos de progreso
            if 'percentage' in progress_data:
                task.progress.percentage = min(100.0, max(0.0, progress_data['percentage']))

            if 'current_step' in progress_data:
                task.progress.current_step = progress_data['current_step']

            if 'total_steps' in progress_data:
                task.progress.total_steps = progress_data['total_steps']

            if 'completed_steps' in progress_data:
                task.progress.completed_steps = progress_data['completed_steps']

            if 'estimated_remaining_seconds' in progress_data:
                task.progress.estimated_remaining_seconds = progress_data['estimated_remaining_seconds']

            if 'details' in progress_data:
                task.progress.details.update(progress_data['details'])

            task.progress.last_updated = datetime.utcnow()

            logger.debug(f"Task {task_id} progress: {task.progress.percentage:.1f}% - {task.progress.current_step}")

        except Exception as e:
            logger.error(f"Error updating progress for task {task_id}: {e}")

    def _handle_task_error(self, task: Task, error: Exception):
        """Maneja errores de tarea"""
        try:
            self.tasks_failed += 1
            task.progress.current_step = f"Failed: {str(error)}"
            task.progress.last_updated = datetime.utcnow()

            logger.error(f"Task {task.task_id} failed: {error}")

            # Aquí se podría implementar lógica de retry según retry_policy

        except Exception as e:
            logger.error(f"Error handling task error: {e}")

    async def _handle_task_timeout(self, task: Task):
        """Maneja timeout de tarea"""
        try:
            task.progress.current_step = "Timed out"
            task.progress.last_updated = datetime.utcnow()

            logger.warning(f"Task {task.task_id} timed out")

        except Exception as e:
            logger.error(f"Error handling task timeout: {e}")

    async def _cancel_task(self, task_id: str):
        """Cancela una tarea"""
        try:
            task = self.current_tasks.get(task_id)
            if task:
                task.progress.current_step = "Cancelled"
                task.progress.last_updated = datetime.utcnow()
                logger.info(f"Task {task_id} cancelled")

        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")

    async def _notify_task_completion(self, task: Task, result: Dict[str, Any]):
        """Notifica la finalización de una tarea"""
        try:
            # Aquí se podría integrar con el sistema de notificaciones
            logger.info(f"Task {task.task_id} completed with result keys: {list(result.keys())}")

        except Exception as e:
            logger.error(f"Error notifying task completion: {e}")

    def _heartbeat_loop(self):
        """Loop de heartbeat para mantener el worker vivo"""
        while self.running and not self.shutdown_event.is_set():
            try:
                self.metadata.last_heartbeat = datetime.utcnow()

                # Aquí se podría registrar el heartbeat en la base de datos
                logger.debug(f"Worker {self.metadata.worker_id} heartbeat")

                # Esperar hasta el próximo heartbeat
                self.shutdown_event.wait(self.metadata.heartbeat_interval)

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                time.sleep(self.metadata.heartbeat_interval)

    def get_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del worker"""
        return {
            'worker_id': self.metadata.worker_id,
            'worker_name': self.metadata.worker_name,
            'worker_type': self.metadata.worker_type,
            'status': self.status.value,
            'current_tasks': len(self.current_tasks),
            'max_concurrent_tasks': self.metadata.max_concurrent_tasks,
            'queue_size': self.task_queue.get_size(),
            'tasks_completed': self.tasks_completed,
            'tasks_failed': self.tasks_failed,
            'success_rate': (self.tasks_completed / max(1, self.tasks_completed + self.tasks_failed)) * 100,
            'average_processing_time': self.total_processing_time / max(1, self.tasks_completed),
            'last_activity': self.last_activity.isoformat(),
            'last_heartbeat': self.metadata.last_heartbeat.isoformat() if self.metadata.last_heartbeat else None,
            'capabilities': self.metadata.capabilities,
            'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'cpu_percent': psutil.Process().cpu_percent()
        }

class WorkerPool:
    """Pool de workers para procesamiento distribuido"""

    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path
        self.workers = {}  # worker_id -> worker
        self.task_queue = TaskQueue(max_size=50000)
        self.scheduler_running = False
        self.scheduler_thread = None
        self.shutdown_event = threading.Event()

        # Load balancer
        self.round_robin_index = 0

    async def register_worker(self, worker: Worker) -> bool:
        """Registra un worker en el pool"""
        try:
            if worker.metadata.worker_id in self.workers:
                logger.warning(f"Worker {worker.metadata.worker_id} already registered")
                return False

            self.workers[worker.metadata.worker_id] = worker
            await worker.start()

            # Guardar en BD
            await self._save_worker_registration(worker.metadata)

            logger.info(f"Registered worker {worker.metadata.worker_id}")
            return True

        except Exception as e:
            logger.error(f"Error registering worker {worker.metadata.worker_id}: {e}")
            return False

    async def unregister_worker(self, worker_id: str) -> bool:
        """Desregistra un worker del pool"""
        try:
            worker = self.workers.get(worker_id)
            if not worker:
                return False

            await worker.stop()
            del self.workers[worker_id]

            # Actualizar BD
            await self._update_worker_status(worker_id, WorkerStatus.OFFLINE)

            logger.info(f"Unregistered worker {worker_id}")
            return True

        except Exception as e:
            logger.error(f"Error unregistering worker {worker_id}: {e}")
            return False

    async def submit_task(self, task: Task) -> bool:
        """Envía una tarea al pool para procesamiento"""
        try:
            # Guardar tarea en BD
            await self._save_task(task)

            # Buscar worker disponible para el tipo de tarea
            suitable_worker = self._find_suitable_worker(task)

            if suitable_worker:
                # Enviar directamente al worker
                if suitable_worker.submit_task(task):
                    await self._update_task_status(task.task_id, TaskStatus.ASSIGNED, suitable_worker.metadata.worker_id)
                    return True

            # Si no hay worker disponible, encolar
            if self.task_queue.enqueue(task):
                await self._update_task_status(task.task_id, TaskStatus.QUEUED)
                return True

            return False

        except Exception as e:
            logger.error(f"Error submitting task {task.task_id}: {e}")
            return False

    def _find_suitable_worker(self, task: Task) -> Optional[Worker]:
        """Encuentra el worker más adecuado para una tarea"""
        try:
            suitable_workers = []

            for worker in self.workers.values():
                # Verificar capacidades
                if task.task_type not in worker.task_handlers:
                    continue

                # Verificar estado
                if worker.status not in [WorkerStatus.IDLE, WorkerStatus.BUSY]:
                    continue

                # Verificar capacidad
                if len(worker.current_tasks) >= worker.metadata.max_concurrent_tasks:
                    continue

                suitable_workers.append(worker)

            if not suitable_workers:
                return None

            # Estrategia de load balancing: round robin entre workers disponibles
            if len(suitable_workers) == 1:
                return suitable_workers[0]

            # Round robin
            self.round_robin_index = (self.round_robin_index + 1) % len(suitable_workers)
            return suitable_workers[self.round_robin_index]

        except Exception as e:
            logger.error(f"Error finding suitable worker: {e}")
            return None

    async def start_scheduler(self):
        """Inicia el scheduler de tareas"""
        try:
            if self.scheduler_running:
                return

            self.scheduler_running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()

            logger.info("Task scheduler started")

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

    async def stop_scheduler(self):
        """Detiene el scheduler de tareas"""
        try:
            self.scheduler_running = False
            self.shutdown_event.set()

            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=10)

            logger.info("Task scheduler stopped")

        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")

    def _scheduler_loop(self):
        """Loop principal del scheduler"""
        while self.scheduler_running and not self.shutdown_event.is_set():
            try:
                # Intentar asignar tareas de la cola
                task = self.task_queue.dequeue(timeout=1.0)
                if task:
                    worker = self._find_suitable_worker(task)
                    if worker:
                        if worker.submit_task(task):
                            asyncio.run(self._update_task_status(task.task_id, TaskStatus.ASSIGNED, worker.metadata.worker_id))
                        else:
                            # Re-encolar si no se pudo asignar
                            self.task_queue.enqueue(task)

                # Limpiar workers inactivos
                self._cleanup_inactive_workers()

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(1)

    def _cleanup_inactive_workers(self):
        """Limpia workers inactivos"""
        try:
            current_time = datetime.utcnow()
            inactive_workers = []

            for worker_id, worker in self.workers.items():
                if worker.metadata.last_heartbeat:
                    time_since_heartbeat = current_time - worker.metadata.last_heartbeat
                    if time_since_heartbeat > timedelta(seconds=worker.metadata.heartbeat_interval * 3):
                        inactive_workers.append(worker_id)

            # Remover workers inactivos
            for worker_id in inactive_workers:
                logger.warning(f"Removing inactive worker {worker_id}")
                asyncio.run(self.unregister_worker(worker_id))

        except Exception as e:
            logger.error(f"Error cleaning up inactive workers: {e}")

    async def get_pool_status(self) -> Dict[str, Any]:
        """Obtiene el estado del pool"""
        try:
            total_workers = len(self.workers)
            active_workers = sum(1 for w in self.workers.values() if w.status in [WorkerStatus.IDLE, WorkerStatus.BUSY])
            busy_workers = sum(1 for w in self.workers.values() if w.status == WorkerStatus.BUSY)

            total_tasks = sum(len(w.current_tasks) for w in self.workers.values())
            total_capacity = sum(w.metadata.max_concurrent_tasks for w in self.workers.values())

            return {
                'total_workers': total_workers,
                'active_workers': active_workers,
                'busy_workers': busy_workers,
                'idle_workers': active_workers - busy_workers,
                'total_current_tasks': total_tasks,
                'total_capacity': total_capacity,
                'utilization_percentage': (total_tasks / max(1, total_capacity)) * 100,
                'queue_size': self.task_queue.get_size(),
                'scheduler_running': self.scheduler_running,
                'workers': [w.get_status() for w in self.workers.values()]
            }

        except Exception as e:
            logger.error(f"Error getting pool status: {e}")
            return {'error': str(e)}

    # Database operations
    async def _save_worker_registration(self, metadata: WorkerMetadata):
        """Guarda registro de worker en BD"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO worker_registry (
                        worker_id, worker_name, worker_type, capabilities, max_concurrent_tasks,
                        memory_limit_mb, cpu_cores, version, heartbeat_interval, task_timeout_seconds,
                        status, registration_time, last_heartbeat, worker_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metadata.worker_id, metadata.worker_name, metadata.worker_type,
                    json.dumps(metadata.capabilities), metadata.max_concurrent_tasks,
                    metadata.memory_limit_mb, metadata.cpu_cores, metadata.version,
                    metadata.heartbeat_interval, metadata.task_timeout_seconds,
                    WorkerStatus.IDLE.value, metadata.registration_time,
                    metadata.last_heartbeat, json.dumps({  # ✅ CAMPO FALTANTE
                        'capabilities': metadata.capabilities,
                        'max_concurrent_tasks': metadata.max_concurrent_tasks,
                        'memory_limit_mb': metadata.memory_limit_mb,
                        'cpu_cores': metadata.cpu_cores,
                        'version': metadata.version,
                        'heartbeat_interval': metadata.heartbeat_interval,
                        'task_timeout_seconds': metadata.task_timeout_seconds
                    })
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error saving worker registration: {e}")

    async def _save_task(self, task: Task):
        """Guarda tarea en BD"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO worker_tasks (
                        task_id, task_type, task_data, priority, retry_policy,
                        timeout_seconds, status, progress, created_at, scheduled_for,
                        depends_on, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.task_id, task.task_type, json.dumps(task.task_data),
                    task.priority.value, json.dumps({  # ✅ CAMPO FALTANTE
                        'max_attempts': task.retry_policy.max_attempts,
                        'initial_delay_seconds': task.retry_policy.initial_delay_seconds,
                        'max_delay_seconds': task.retry_policy.max_delay_seconds,
                        'backoff_multiplier': task.retry_policy.backoff_multiplier,
                        'retry_on_timeout': task.retry_policy.retry_on_timeout,
                        'retry_on_error': task.retry_policy.retry_on_error,
                        'retry_error_patterns': task.retry_policy.retry_error_patterns
                    }),
                    task.timeout_seconds, TaskStatus.PENDING.value,
                    json.dumps({  # ✅ CAMPO FALTANTE
                        'percentage': task.progress.percentage,
                        'current_step': task.progress.current_step,
                        'total_steps': task.progress.total_steps,
                        'completed_steps': task.progress.completed_steps,
                        'estimated_remaining_seconds': task.progress.estimated_remaining_seconds,
                        'details': task.progress.details,
                        'last_updated': task.progress.last_updated.isoformat()
                    }),
                    task.created_at, task.scheduled_for,
                    json.dumps(task.depends_on), json.dumps(task.tags)
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error saving task: {e}")

    async def _update_task_status(self, task_id: str, status: TaskStatus, worker_id: str = None):
        """Actualiza estado de tarea"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                if worker_id:
                    cursor.execute("""
                        UPDATE worker_tasks
                        SET status = ?, assigned_worker_id = ?, updated_at = ?
                        WHERE task_id = ?
                    """, (status.value, worker_id, datetime.utcnow(), task_id))
                else:
                    cursor.execute("""
                        UPDATE worker_tasks
                        SET status = ?, updated_at = ?
                        WHERE task_id = ?
                    """, (status.value, datetime.utcnow(), task_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating task status: {e}")

    async def _update_worker_status(self, worker_id: str, status: WorkerStatus):
        """Actualiza estado de worker"""
        try:
            async with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE worker_registry
                    SET status = ?, last_heartbeat = ?
                    WHERE worker_id = ?
                """, (status.value, datetime.utcnow(), worker_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating worker status: {e}")

    @asynccontextmanager
    async def _get_db_connection(self):
        """Context manager para conexión a base de datos"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

class WorkerSystem:
    """Sistema principal de workers"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'initialized'):
            return

        self.worker_pool = WorkerPool()
        self.task_types = {}  # task_type -> handler_class
        self.initialized = True

    async def start(self):
        """Inicia el sistema de workers"""
        try:
            await self.worker_pool.start_scheduler()
            logger.info("Worker system started")

        except Exception as e:
            logger.error(f"Error starting worker system: {e}")
            raise

    async def stop(self):
        """Detiene el sistema de workers"""
        try:
            # Detener todos los workers
            for worker_id in list(self.worker_pool.workers.keys()):
                await self.worker_pool.unregister_worker(worker_id)

            # Detener scheduler
            await self.worker_pool.stop_scheduler()

            logger.info("Worker system stopped")

        except Exception as e:
            logger.error(f"Error stopping worker system: {e}")

    def register_task_type(self, task_type: str, handler: Callable):
        """Registra un tipo de tarea y su handler"""
        self.task_types[task_type] = handler
        logger.info(f"Registered task type: {task_type}")

    async def create_worker(self, worker_config: Dict[str, Any]) -> str:
        """Crea un nuevo worker"""
        try:
            worker_id = worker_config.get('worker_id', str(uuid.uuid4()))

            metadata = WorkerMetadata(
                worker_id=worker_id,
                worker_name=worker_config.get('worker_name', f'Worker-{worker_id[:8]}'),
                worker_type=worker_config.get('worker_type', 'general'),
                capabilities=worker_config.get('capabilities', list(self.task_types.keys())),
                max_concurrent_tasks=worker_config.get('max_concurrent_tasks', 5),
                memory_limit_mb=worker_config.get('memory_limit_mb', 1024),
                cpu_cores=worker_config.get('cpu_cores', 2),
                version=worker_config.get('version', '1.0.0'),
                heartbeat_interval=worker_config.get('heartbeat_interval', 30),
                task_timeout_seconds=worker_config.get('task_timeout_seconds', 3600)
            )

            # Crear handlers para los tipos de tarea soportados
            task_handlers = {}
            for capability in metadata.capabilities:
                if capability in self.task_types:
                    task_handlers[capability] = self.task_types[capability]

            worker = Worker(metadata, task_handlers)
            await self.worker_pool.register_worker(worker)

            return worker_id

        except Exception as e:
            logger.error(f"Error creating worker: {e}")
            raise

    async def submit_task(self, task_type: str, task_data: Dict[str, Any],
                         priority: TaskPriority = TaskPriority.NORMAL,
                         timeout_seconds: int = 3600,
                         retry_policy: Optional[RetryPolicy] = None) -> str:
        """Envía una tarea para procesamiento"""
        try:
            task_id = str(uuid.uuid4())

            if retry_policy is None:
                retry_policy = RetryPolicy()

            task = Task(
                task_id=task_id,
                task_type=task_type,
                task_data=task_data,
                priority=priority,
                retry_policy=retry_policy,
                timeout_seconds=timeout_seconds,
                created_at=datetime.utcnow()
            )

            success = await self.worker_pool.submit_task(task)
            if success:
                return task_id
            else:
                raise Exception("Failed to submit task")

        except Exception as e:
            logger.error(f"Error submitting task: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Obtiene el estado de una tarea"""
        try:
            async with self.worker_pool._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT task_id, task_type, status, progress, retry_policy,
                           assigned_worker_id, created_at, updated_at
                    FROM worker_tasks
                    WHERE task_id = ?
                """, (task_id,))

                row = cursor.fetchone()
                if not row:
                    return {'error': 'Task not found'}

                return {
                    'task_id': row[0],
                    'task_type': row[1],
                    'status': row[2],
                    'progress': json.loads(row[3] or '{}'),  # ✅ CAMPO FALTANTE
                    'retry_policy': json.loads(row[4] or '{}'),  # ✅ CAMPO FALTANTE
                    'assigned_worker_id': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                }

        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            return {'error': str(e)}

    async def get_system_status(self) -> Dict[str, Any]:
        """Obtiene el estado del sistema completo"""
        try:
            pool_status = await self.worker_pool.get_pool_status()

            return {
                'system_status': 'running' if self.worker_pool.scheduler_running else 'stopped',
                'registered_task_types': list(self.task_types.keys()),
                'pool_status': pool_status,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}

# Instancia singleton
worker_system = WorkerSystem()