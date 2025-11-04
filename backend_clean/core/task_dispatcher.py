"""Lightweight helpers to enqueue background tasks via the worker system."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from typing import Any, Dict, Optional

from config.config import config
from core.fiscal_pipeline import classify_expense_fiscal
from core.worker_system import TaskPriority, worker_system

logger = logging.getLogger(__name__)

# Internal coordination primitives created lazily to avoid binding to a loop at import time.
_startup_event: Optional[asyncio.Event] = None
_bootstrap_event: Optional[asyncio.Event] = None


async def _ensure_worker_system_started() -> None:
    """Start the worker scheduler if it is not already running."""
    global _startup_event

    if worker_system.worker_pool.scheduler_running:
        return

    if _startup_event is None or _startup_event.is_set():
        _startup_event = asyncio.Event()
        try:
            await worker_system.start()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unable to start worker system: %s", exc)
            raise
        finally:
            _startup_event.set()
    else:
        await _startup_event.wait()


async def _ensure_default_worker() -> None:
    """Make sure we have at least one worker registered with classification capability."""
    global _bootstrap_event

    if worker_system.worker_pool.workers:
        return

    if _bootstrap_event is None or _bootstrap_event.is_set():
        _bootstrap_event = asyncio.Event()
        try:
            await _ensure_worker_system_started()
            await worker_system.create_worker(
                {
                    "worker_name": "expense-classifier",
                    "worker_type": "expense",
                    "capabilities": ["expense.classify"],
                    "max_concurrent_tasks": 2,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unable to bootstrap default worker: %s", exc)
            raise
        finally:
            _bootstrap_event.set()
    else:
        await _bootstrap_event.wait()


async def _dispatch_task(
    task_type: str,
    payload: Dict[str, Any],
    *,
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout_seconds: int = 900,
) -> str:
    """Generic dispatcher that guarantees worker availability before submitting."""
    # Ensure handler is registered before boot (idempotent registration).
    _register_default_handlers()

    await _ensure_worker_system_started()
    await _ensure_default_worker()
    return await worker_system.submit_task(
        task_type,
        payload,
        priority=priority,
        timeout_seconds=timeout_seconds,
    )


async def enqueue_expense_classification(
    expense_id: int,
    tenant_id: int,
    *,
    descripcion: Optional[str] = None,
    proveedor: Optional[str] = None,
    monto: Optional[float] = None,
    priority: TaskPriority = TaskPriority.HIGH,
    timeout_seconds: int = 900,
) -> str:
    """
    Enqueue an expense classification job.

    Optional fields help the rules stage skip an extra DB lookup when already available.
    """
    payload = {
        "expense_id": expense_id,
        "tenant_id": tenant_id,
    }
    if descripcion is not None:
        payload["descripcion"] = descripcion
    if proveedor is not None:
        payload["proveedor"] = proveedor
    if monto is not None:
        payload["monto"] = monto

    return await _dispatch_task(
        "expense.classify",
        payload,
        priority=priority,
        timeout_seconds=timeout_seconds,
    )


def enqueue_expense_classification_sync(
    expense_id: int,
    tenant_id: int,
    *,
    descripcion: Optional[str] = None,
    proveedor: Optional[str] = None,
    monto: Optional[float] = None,
    priority: TaskPriority = TaskPriority.HIGH,
    timeout_seconds: int = 900,
) -> str:
    """Synchronous helper for scripts or CLI tooling."""

    async def _runner() -> str:
        return await enqueue_expense_classification(
            expense_id,
            tenant_id,
            descripcion=descripcion,
            proveedor=proveedor,
            monto=monto,
            priority=priority,
            timeout_seconds=timeout_seconds,
        )

    return asyncio.run(_runner())


def _run_expense_classification_impl(
    expense_id: int,
    tenant_id: int,
    *,
    descripcion: Optional[str],
    proveedor: Optional[str],
    monto: Optional[float],
) -> Dict[str, Any]:
    db_path = getattr(config, "UNIFIED_DB_PATH", None)
    if not db_path:
        raise RuntimeError("UNIFIED_DB_PATH is not configured")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if descripcion is None or proveedor is None or monto is None:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COALESCE(descripcion, description, '') AS descripcion,
                    COALESCE(proveedor_nombre, merchant_name, '') AS proveedor,
                    COALESCE(monto_total, amount, 0.0) AS monto
                FROM expense_records
                WHERE id = ? AND tenant_id = ?
                """,
                (expense_id, tenant_id),
            )
            row = cursor.fetchone()
            if row:
                descripcion = descripcion or row["descripcion"]
                proveedor = proveedor or row["proveedor"]
                monto = monto if monto is not None else float(row["monto"] or 0.0)
            else:
                raise ValueError(f"Gasto {expense_id} no encontrado para tenant {tenant_id}")

        result = classify_expense_fiscal(
            conn,
            expense_id=expense_id,
            tenant_id=tenant_id,
            descripcion=descripcion or "",
            proveedor=proveedor,
            monto=float(monto or 0.0),
        )

        return result or {"status": "no_classification"}
    finally:
        conn.close()


async def _handle_expense_classification(task, update_progress) -> Dict[str, Any]:
    """Worker handler that executes the fiscal pipeline for a single expense."""
    task_data = task.task_data or {}
    expense_id = task_data.get("expense_id")
    tenant_id = task_data.get("tenant_id")

    if expense_id is None or tenant_id is None:
        raise ValueError("Missing expense_id or tenant_id in task payload")

    descripcion = task_data.get("descripcion")
    proveedor = task_data.get("proveedor")
    monto = task_data.get("monto")

    await update_progress(
        task.task_id,
        {
            "current_step": "loading_expense",
            "percentage": 5.0,
            "details": {"expense_id": expense_id, "tenant_id": tenant_id},
        },
    )

    result = _run_expense_classification_impl(
        expense_id,
        tenant_id,
        descripcion=descripcion,
        proveedor=proveedor,
        monto=monto,
    )

    await update_progress(
        task.task_id,
        {"current_step": "pipeline_llm", "percentage": 85.0},
    )

    return result


def run_expense_classification_sync(
    expense_id: int,
    tenant_id: int,
    *,
    descripcion: Optional[str] = None,
    proveedor: Optional[str] = None,
    monto: Optional[float] = None,
) -> Dict[str, Any]:
    """Run the expense classification pipeline synchronously."""
    return _run_expense_classification_impl(
        expense_id,
        tenant_id,
        descripcion=descripcion,
        proveedor=proveedor,
        monto=monto,
    )


def _register_default_handlers() -> None:
    """Register core task handlers (idempotent)."""
    if "expense.classify" not in worker_system.task_types:
        worker_system.register_task_type("expense.classify", _handle_expense_classification)


__all__ = [
    "enqueue_expense_classification",
    "enqueue_expense_classification_sync",
]
