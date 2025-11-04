"""
Idempotent Workers - Mitigación de riesgos de procesamiento duplicado

Sistema de workers que garantiza que cada ticket se procesa exactamente una vez.
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import sqlite3
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Estados de job con semántica clara."""
    PENDING = "pendiente"
    CLAIMED = "reclamado"  # Worker lo tomó pero no empezó
    PROCESSING = "procesando"
    COMPLETED = "completado"
    FAILED = "fallido"
    TIMEOUT = "timeout"
    CANCELLED = "cancelado"

@dataclass
class IdempotencyKey:
    """Clave de idempotencia para jobs."""
    ticket_id: int
    operation_type: str  # "automation", "ocr", "notification"
    config_hash: str  # Hash de configuración para detectar cambios
    retry_count: int = 0

    def to_string(self) -> str:
        """Convertir a string único."""
        return f"{self.ticket_id}:{self.operation_type}:{self.config_hash}:{self.retry_count}"

class IdempotentJobManager:
    """Gestor de jobs con garantías de idempotencia."""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path
        self.local_locks = {}  # Worker-local locks
        self.lock = threading.Lock()

    def generate_idempotency_key(
        self,
        ticket_id: int,
        operation_type: str,
        config: Dict[str, Any],
        retry_count: int = 0
    ) -> IdempotencyKey:
        """Generar clave de idempotencia."""
        # Hash configuration for change detection
        config_str = json.dumps(config, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]

        return IdempotencyKey(
            ticket_id=ticket_id,
            operation_type=operation_type,
            config_hash=config_hash,
            retry_count=retry_count
        )

    @contextmanager
    def claim_job(self, idempotency_key: IdempotencyKey, worker_id: str, timeout_seconds: int = 300):
        """Context manager para reclamar job de forma atómica."""
        job_id = None

        try:
            # 1. Try to claim job atomically
            job_id = self._atomic_claim_job(idempotency_key, worker_id, timeout_seconds)

            if job_id:
                logger.info(f"Worker {worker_id} claimed job {job_id} with key {idempotency_key.to_string()}")

                # 2. Update status to processing
                self._update_job_status(job_id, JobStatus.PROCESSING, worker_id)

                yield job_id

                # 3. Mark as completed if no exception
                self._update_job_status(job_id, JobStatus.COMPLETED, worker_id)

            else:
                # Job already exists and processed/processing
                logger.info(f"Job with key {idempotency_key.to_string()} already processed or processing")
                yield None

        except Exception as e:
            if job_id:
                # Mark as failed
                self._update_job_status(job_id, JobStatus.FAILED, worker_id, error_message=str(e))
            logger.error(f"Job {job_id} failed: {e}")
            raise

        finally:
            # Release local lock
            key_str = idempotency_key.to_string()
            with self.lock:
                if key_str in self.local_locks:
                    del self.local_locks[key_str]

    def _atomic_claim_job(
        self,
        idempotency_key: IdempotencyKey,
        worker_id: str,
        timeout_seconds: int
    ) -> Optional[int]:
        """Atomically claim a job or determine it's already processed."""

        key_str = idempotency_key.to_string()

        # Local lock to prevent same worker from double-processing
        with self.lock:
            if key_str in self.local_locks:
                logger.debug(f"Job {key_str} already being processed by this worker")
                return None
            self.local_locks[key_str] = True

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE;")  # Exclusive lock

                # Check if job already exists
                cursor = conn.execute("""
                    SELECT id, estado, claimed_by, claimed_at, completed_at
                    FROM automation_jobs
                    WHERE idempotency_key = ?
                """, [key_str])

                existing = cursor.fetchone()

                if existing:
                    job_id, estado, claimed_by, claimed_at, completed_at = existing

                    # If completed or failed, don't reprocess
                    if estado in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                        logger.info(f"Job {job_id} already {estado}, skipping")
                        return None

                    # Check for stale claims (timeout)
                    if claimed_at and estado == JobStatus.CLAIMED.value:
                        claimed_time = datetime.fromisoformat(claimed_at)
                        if datetime.now() - claimed_time > timedelta(seconds=timeout_seconds):
                            logger.warning(f"Job {job_id} claim by {claimed_by} timed out, reclaiming")
                            # Continue to reclaim
                        else:
                            logger.info(f"Job {job_id} still claimed by {claimed_by}")
                            return None

                    # If currently processing by another worker, don't interfere
                    if estado == JobStatus.PROCESSING.value and claimed_by != worker_id:
                        logger.info(f"Job {job_id} being processed by {claimed_by}")
                        return None

                    # Reclaim stale job
                    conn.execute("""
                        UPDATE automation_jobs
                        SET estado = ?, claimed_by = ?, claimed_at = ?, updated_at = ?
                        WHERE id = ?
                    """, [
                        JobStatus.CLAIMED.value,
                        worker_id,
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                        job_id
                    ])

                    conn.commit()
                    return job_id

                else:
                    # Create new job
                    now = datetime.now().isoformat()
                    cursor = conn.execute("""
                        INSERT INTO automation_jobs (
                            ticket_id, estado, claimed_by, claimed_at,
                            idempotency_key, config, session_id,
                            created_at, updated_at, company_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        idempotency_key.ticket_id,
                        JobStatus.CLAIMED.value,
                        worker_id,
                        now,
                        key_str,
                        json.dumps({}),  # Will be updated later
                        f"session_{idempotency_key.ticket_id}_{int(time.time())}",
                        now,
                        now,
                        "default"
                    ])

                    job_id = cursor.lastrowid
                    conn.commit()
                    logger.info(f"Created new job {job_id} for key {key_str}")
                    return job_id

        except Exception as e:
            logger.error(f"Error claiming job: {e}")
            # Release local lock on error
            with self.lock:
                if key_str in self.local_locks:
                    del self.local_locks[key_str]
            raise

    def _update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        worker_id: str,
        error_message: Optional[str] = None
    ):
        """Update job status atomically."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                update_fields = [
                    "estado = ?",
                    "updated_at = ?"
                ]
                update_values = [status.value, datetime.now().isoformat()]

                if status == JobStatus.COMPLETED:
                    update_fields.append("completed_at = ?")
                    update_values.append(datetime.now().isoformat())

                if error_message:
                    update_fields.append("error_message = ?")
                    update_values.append(error_message)

                update_values.append(job_id)

                conn.execute(f"""
                    UPDATE automation_jobs
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, update_values)

                conn.commit()

        except Exception as e:
            logger.error(f"Error updating job status: {e}")

    def get_job_result(self, idempotency_key: IdempotencyKey) -> Optional[Dict[str, Any]]:
        """Get result of job if already processed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, estado, result, error_message, completed_at
                    FROM automation_jobs
                    WHERE idempotency_key = ?
                """, [idempotency_key.to_string()])

                row = cursor.fetchone()
                if row:
                    job_id, estado, result, error_message, completed_at = row

                    if estado == JobStatus.COMPLETED.value:
                        return {
                            "success": True,
                            "job_id": job_id,
                            "result": json.loads(result) if result else {},
                            "completed_at": completed_at,
                            "from_cache": True
                        }
                    elif estado == JobStatus.FAILED.value:
                        return {
                            "success": False,
                            "job_id": job_id,
                            "error": error_message,
                            "completed_at": completed_at,
                            "from_cache": True
                        }

                return None

        except Exception as e:
            logger.error(f"Error getting job result: {e}")
            return None

    def cleanup_stale_jobs(self, stale_timeout_hours: int = 24):
        """Cleanup jobs that have been stuck for too long."""
        try:
            cutoff_time = (datetime.now() - timedelta(hours=stale_timeout_hours)).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                # Mark stale processing jobs as timeout
                cursor = conn.execute("""
                    UPDATE automation_jobs
                    SET estado = ?, error_message = ?, updated_at = ?
                    WHERE estado = ? AND claimed_at < ?
                """, [
                    JobStatus.TIMEOUT.value,
                    f"Job timed out after {stale_timeout_hours} hours",
                    datetime.now().isoformat(),
                    JobStatus.PROCESSING.value,
                    cutoff_time
                ])

                timeout_count = cursor.rowcount

                # Mark stale claimed jobs as timeout
                cursor = conn.execute("""
                    UPDATE automation_jobs
                    SET estado = ?, error_message = ?, updated_at = ?
                    WHERE estado = ? AND claimed_at < ?
                """, [
                    JobStatus.TIMEOUT.value,
                    f"Job claim timed out after {stale_timeout_hours} hours",
                    datetime.now().isoformat(),
                    JobStatus.CLAIMED.value,
                    cutoff_time
                ])

                claim_timeout_count = cursor.rowcount

                conn.commit()

                if timeout_count > 0 or claim_timeout_count > 0:
                    logger.warning(f"Cleaned up {timeout_count + claim_timeout_count} stale jobs")

        except Exception as e:
            logger.error(f"Error cleaning up stale jobs: {e}")

class IdempotentWorker:
    """Worker base class with idempotency guarantees."""

    def __init__(self, worker_id: str, job_manager: IdempotentJobManager):
        self.worker_id = worker_id
        self.job_manager = job_manager

    async def process_ticket_idempotent(
        self,
        ticket_id: int,
        operation_type: str,
        config: Dict[str, Any],
        processor_func: Callable
    ) -> Dict[str, Any]:
        """Process ticket with idempotency guarantees."""

        # Generate idempotency key
        idempotency_key = self.job_manager.generate_idempotency_key(
            ticket_id, operation_type, config
        )

        # Check if already processed
        existing_result = self.job_manager.get_job_result(idempotency_key)
        if existing_result:
            logger.info(f"Returning cached result for {idempotency_key.to_string()}")
            return existing_result

        # Process with idempotency guarantees
        with self.job_manager.claim_job(idempotency_key, self.worker_id) as job_id:
            if job_id is None:
                # Job is being processed by another worker or already done
                # Wait a bit and check result
                await asyncio.sleep(1)
                result = self.job_manager.get_job_result(idempotency_key)
                if result:
                    return result
                else:
                    return {
                        "success": False,
                        "error": "Job claimed by another worker but no result found",
                        "retry_needed": True
                    }

            # Process the job
            logger.info(f"Processing job {job_id} for ticket {ticket_id}")

            try:
                result = await processor_func(ticket_id, config, job_id)

                # Store result in database
                self._store_job_result(job_id, result)

                return {
                    "success": True,
                    "job_id": job_id,
                    "result": result,
                    "from_cache": False
                }

            except Exception as e:
                logger.error(f"Error processing job {job_id}: {e}")
                raise

    def _store_job_result(self, job_id: int, result: Dict[str, Any]):
        """Store job result in database."""
        try:
            with sqlite3.connect(self.job_manager.db_path) as conn:
                conn.execute("""
                    UPDATE automation_jobs
                    SET result = ?, updated_at = ?
                    WHERE id = ?
                """, [
                    json.dumps(result),
                    datetime.now().isoformat(),
                    job_id
                ])
                conn.commit()

        except Exception as e:
            logger.error(f"Error storing job result: {e}")

# Add idempotency_key column to automation_jobs if not exists
def ensure_idempotency_schema():
    """Ensure database has idempotency support."""
    try:
        from core.internal_db import _get_db_path, _DB_LOCK

        with _DB_LOCK:
            with sqlite3.connect(_get_db_path()) as conn:
                # Add idempotency_key column if not exists
                try:
                    conn.execute("ALTER TABLE automation_jobs ADD COLUMN idempotency_key TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists

                # Add claimed_by and claimed_at columns
                try:
                    conn.execute("ALTER TABLE automation_jobs ADD COLUMN claimed_by TEXT")
                    conn.execute("ALTER TABLE automation_jobs ADD COLUMN claimed_at TEXT")
                except sqlite3.OperationalError:
                    pass  # Columns already exist

                # Create index for idempotency
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_automation_jobs_idempotency
                    ON automation_jobs(idempotency_key)
                """)

                # Create index for worker queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_automation_jobs_worker
                    ON automation_jobs(estado, claimed_by, claimed_at)
                """)

                conn.commit()

    except Exception as e:
        logger.error(f"Error ensuring idempotency schema: {e}")

# Initialize on import
ensure_idempotency_schema()