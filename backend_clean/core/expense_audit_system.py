"""
Sistema de Auditoría Completo para Acciones de Gastos
Funcionalidad #12: Acciones de Gastos - Audit Trail Implementation

Este módulo proporciona:
- Tracking completo de acciones en gastos
- Audit trail detallado
- Sistema de rollback
- Validación de seguridad
- Performance optimizado para operaciones batch
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Tipos de acciones disponibles en gastos"""
    MARK_INVOICED = "mark_invoiced"
    MARK_NO_INVOICE = "mark_no_invoice"
    UPDATE_CATEGORY = "update_category"
    BULK_UPDATE = "bulk_update"
    ARCHIVE = "archive"
    RESTORE = "restore"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"


class ActionStatus(Enum):
    """Estados de las acciones"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ActionContext:
    """Contexto de la acción para audit trail"""
    user_id: int
    company_id: str
    session_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    api_version: Optional[str] = None
    client_info: Optional[Dict[str, Any]] = None


@dataclass
class ExpenseSnapshot:
    """Snapshot del estado de un gasto antes de la acción"""
    expense_id: int
    previous_state: Dict[str, Any]
    timestamp: datetime


@dataclass
class ActionRecord:
    """Registro completo de una acción"""
    action_id: str
    action_type: ActionType
    status: ActionStatus
    context: ActionContext
    target_expense_ids: List[int]
    parameters: Dict[str, Any]
    snapshots: List[ExpenseSnapshot]
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_data: Optional[Dict[str, Any]] = None
    affected_records: int = 0
    execution_time_ms: Optional[int] = None


class ExpenseAuditSystem:
    """Sistema de auditoría para acciones de gastos"""

    def __init__(self, db_adapter):
        self.db = db_adapter
        self._active_actions: Dict[str, ActionRecord] = {}

    async def start_action(
        self,
        action_type: ActionType,
        context: ActionContext,
        target_expense_ids: List[int],
        parameters: Dict[str, Any]
    ) -> str:
        """Inicia una acción y crea el audit trail"""

        action_id = str(uuid.uuid4())

        # Crear snapshots del estado actual
        snapshots = await self._create_expense_snapshots(target_expense_ids)

        # Crear registro de acción
        action_record = ActionRecord(
            action_id=action_id,
            action_type=action_type,
            status=ActionStatus.PENDING,
            context=context,
            target_expense_ids=target_expense_ids,
            parameters=parameters,
            snapshots=snapshots,
            started_at=datetime.utcnow()
        )

        # Guardar en memoria y BD
        self._active_actions[action_id] = action_record
        await self._persist_action_record(action_record)

        logger.info(f"Action {action_id} started: {action_type.value} for {len(target_expense_ids)} expenses")

        return action_id

    async def update_action_status(
        self,
        action_id: str,
        status: ActionStatus,
        affected_records: int = 0,
        error_message: Optional[str] = None
    ):
        """Actualiza el estado de una acción"""

        if action_id not in self._active_actions:
            raise ValueError(f"Action {action_id} not found")

        action_record = self._active_actions[action_id]
        action_record.status = status
        action_record.affected_records = affected_records

        if error_message:
            action_record.error_message = error_message

        if status in [ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.ROLLED_BACK]:
            action_record.completed_at = datetime.utcnow()
            action_record.execution_time_ms = int(
                (action_record.completed_at - action_record.started_at).total_seconds() * 1000
            )

        await self._persist_action_record(action_record)

        logger.info(f"Action {action_id} updated to {status.value}")

    async def complete_action(self, action_id: str, affected_records: int) -> ActionRecord:
        """Completa una acción exitosamente"""

        await self.update_action_status(
            action_id,
            ActionStatus.COMPLETED,
            affected_records=affected_records
        )

        action_record = self._active_actions[action_id]

        # Limpiar de memoria
        del self._active_actions[action_id]

        return action_record

    async def fail_action(self, action_id: str, error_message: str) -> ActionRecord:
        """Marca una acción como fallida"""

        await self.update_action_status(
            action_id,
            ActionStatus.FAILED,
            error_message=error_message
        )

        action_record = self._active_actions[action_id]

        # Preparar datos para rollback si es necesario
        action_record.rollback_data = await self._prepare_rollback_data(action_record)
        await self._persist_action_record(action_record)

        # Limpiar de memoria
        del self._active_actions[action_id]

        return action_record

    async def rollback_action(self, action_id: str) -> bool:
        """Ejecuta rollback de una acción"""

        # Obtener el registro de la acción
        action_record = await self._get_action_record(action_id)
        if not action_record:
            raise ValueError(f"Action record {action_id} not found")

        if action_record.status == ActionStatus.ROLLED_BACK:
            logger.warning(f"Action {action_id} already rolled back")
            return True

        if not action_record.rollback_data:
            raise ValueError(f"No rollback data available for action {action_id}")

        try:
            # Ejecutar rollback
            await self._execute_rollback(action_record)

            # Actualizar estado
            action_record.status = ActionStatus.ROLLED_BACK
            action_record.completed_at = datetime.utcnow()
            await self._persist_action_record(action_record)

            logger.info(f"Action {action_id} rolled back successfully")
            return True

        except Exception as e:
            logger.error(f"Rollback failed for action {action_id}: {e}")
            return False

    async def get_audit_trail(
        self,
        expense_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Obtiene el audit trail completo de un gasto"""

        query = """
        SELECT
            action_id,
            action_type,
            status,
            user_id,
            company_id,
            parameters,
            started_at,
            completed_at,
            affected_records,
            execution_time_ms,
            error_message
        FROM expense_action_audit
        WHERE $1 = ANY(target_expense_ids)
        ORDER BY started_at DESC
        LIMIT $2
        """

        records = await self.db.fetch_all(query, expense_id, limit)

        return [dict(record) for record in records]

    async def get_bulk_action_stats(
        self,
        company_id: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Estadísticas de acciones bulk por empresa"""

        query = """
        SELECT
            action_type,
            status,
            COUNT(*) as count,
            AVG(affected_records) as avg_affected,
            AVG(execution_time_ms) as avg_execution_time_ms,
            MAX(execution_time_ms) as max_execution_time_ms
        FROM expense_action_audit
        WHERE company_id = $1
        AND started_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
        GROUP BY action_type, status
        ORDER BY action_type, status
        """

        stats = await self.db.fetch_all(query % days_back, company_id)

        # Organizar estadísticas
        result = {
            "summary": {
                "total_actions": 0,
                "successful_actions": 0,
                "failed_actions": 0,
                "total_expenses_affected": 0
            },
            "by_action_type": {},
            "performance_metrics": {
                "avg_execution_time_ms": 0,
                "max_execution_time_ms": 0
            }
        }

        for stat in stats:
            action_type = stat["action_type"]
            status = stat["status"]
            count = stat["count"]

            if action_type not in result["by_action_type"]:
                result["by_action_type"][action_type] = {
                    "completed": 0,
                    "failed": 0,
                    "avg_affected": 0,
                    "avg_time_ms": 0
                }

            result["by_action_type"][action_type][status] = count
            result["by_action_type"][action_type]["avg_affected"] = stat["avg_affected"]
            result["by_action_type"][action_type]["avg_time_ms"] = stat["avg_execution_time_ms"]

            result["summary"]["total_actions"] += count
            if status == "completed":
                result["summary"]["successful_actions"] += count
            elif status == "failed":
                result["summary"]["failed_actions"] += count

        return result

    # Métodos privados

    async def _create_expense_snapshots(self, expense_ids: List[int]) -> List[ExpenseSnapshot]:
        """Crea snapshots del estado actual de los gastos"""
        snapshots = []

        for expense_id in expense_ids:
            # Obtener estado actual del gasto
            expense_data = await self.db.fetch_one(
                "SELECT * FROM expenses WHERE id = $1",
                expense_id
            )

            if expense_data:
                snapshot = ExpenseSnapshot(
                    expense_id=expense_id,
                    previous_state=dict(expense_data),
                    timestamp=datetime.utcnow()
                )
                snapshots.append(snapshot)

        return snapshots

    async def _persist_action_record(self, action_record: ActionRecord):
        """Persiste el registro de acción en la base de datos"""

        query = """
        INSERT INTO expense_action_audit (
            action_id, action_type, status, user_id, company_id, session_id,
            target_expense_ids, parameters, snapshots, started_at, completed_at,
            affected_records, execution_time_ms, error_message, rollback_data,
            ip_address, user_agent, api_version, client_info
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
        )
        ON CONFLICT (action_id) DO UPDATE SET
            status = EXCLUDED.status,
            completed_at = EXCLUDED.completed_at,
            affected_records = EXCLUDED.affected_records,
            execution_time_ms = EXCLUDED.execution_time_ms,
            error_message = EXCLUDED.error_message,
            rollback_data = EXCLUDED.rollback_data
        """

        await self.db.execute(
            query,
            action_record.action_id,
            action_record.action_type.value,
            action_record.status.value,
            action_record.context.user_id,
            action_record.context.company_id,
            action_record.context.session_id,
            action_record.target_expense_ids,
            json.dumps(action_record.parameters),
            json.dumps([asdict(s) for s in action_record.snapshots]),
            action_record.started_at,
            action_record.completed_at,
            action_record.affected_records,
            action_record.execution_time_ms,
            action_record.error_message,
            json.dumps(action_record.rollback_data) if action_record.rollback_data else None,
            action_record.context.ip_address,
            action_record.context.user_agent,
            action_record.context.api_version,
            json.dumps(action_record.context.client_info) if action_record.context.client_info else None
        )

    async def _prepare_rollback_data(self, action_record: ActionRecord) -> Dict[str, Any]:
        """Prepara datos necesarios para rollback"""

        rollback_data = {
            "action_type": action_record.action_type.value,
            "original_snapshots": [asdict(s) for s in action_record.snapshots],
            "parameters": action_record.parameters,
            "rollback_strategy": self._determine_rollback_strategy(action_record.action_type)
        }

        return rollback_data

    def _determine_rollback_strategy(self, action_type: ActionType) -> str:
        """Determina la estrategia de rollback según el tipo de acción"""

        strategies = {
            ActionType.MARK_INVOICED: "restore_invoice_status",
            ActionType.MARK_NO_INVOICE: "restore_invoice_status",
            ActionType.UPDATE_CATEGORY: "restore_category",
            ActionType.BULK_UPDATE: "restore_fields",
            ActionType.ARCHIVE: "restore_active_status",
            ActionType.DELETE: "restore_record",
            ActionType.APPROVE: "restore_approval_status",
            ActionType.REJECT: "restore_approval_status"
        }

        return strategies.get(action_type, "manual_review_required")

    async def _execute_rollback(self, action_record: ActionRecord):
        """Ejecuta el rollback basado en la estrategia determinada"""

        strategy = action_record.rollback_data["rollback_strategy"]
        snapshots = action_record.rollback_data["original_snapshots"]

        if strategy == "restore_invoice_status":
            await self._rollback_invoice_status(snapshots)
        elif strategy == "restore_category":
            await self._rollback_category_changes(snapshots)
        elif strategy == "restore_fields":
            await self._rollback_field_changes(snapshots)
        elif strategy == "restore_active_status":
            await self._rollback_status_changes(snapshots)
        else:
            raise ValueError(f"Rollback strategy '{strategy}' not implemented")

    async def _rollback_invoice_status(self, snapshots: List[Dict[str, Any]]):
        """Rollback específico para cambios de estado de factura"""

        for snapshot in snapshots:
            expense_id = snapshot["expense_id"]
            original_state = snapshot["previous_state"]

            await self.db.execute("""
                UPDATE expenses
                SET invoice_status = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, original_state.get("invoice_status"), expense_id)

    async def _rollback_category_changes(self, snapshots: List[Dict[str, Any]]):
        """Rollback específico para cambios de categoría"""

        for snapshot in snapshots:
            expense_id = snapshot["expense_id"]
            original_state = snapshot["previous_state"]

            await self.db.execute("""
                UPDATE expenses
                SET categoria = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, original_state.get("categoria"), expense_id)

    async def _rollback_field_changes(self, snapshots: List[Dict[str, Any]]):
        """Rollback genérico para múltiples campos"""

        for snapshot in snapshots:
            expense_id = snapshot["expense_id"]
            original_state = snapshot["previous_state"]

            # Construir query dinámico para restaurar todos los campos
            update_fields = []
            values = []
            param_idx = 1

            # Campos que pueden ser restaurados
            restorable_fields = [
                "descripcion", "monto_total", "categoria", "proveedor",
                "deducible", "centro_costo", "proyecto", "invoice_status",
                "bank_status", "approval_status"
            ]

            for field in restorable_fields:
                if field in original_state:
                    update_fields.append(f"{field} = ${param_idx}")
                    values.append(original_state[field])
                    param_idx += 1

            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(expense_id)

                query = f"""
                    UPDATE expenses
                    SET {', '.join(update_fields)}
                    WHERE id = ${param_idx}
                """

                await self.db.execute(query, *values)

    async def _rollback_status_changes(self, snapshots: List[Dict[str, Any]]):
        """Rollback específico para cambios de estado (archivar/restaurar)"""

        for snapshot in snapshots:
            expense_id = snapshot["expense_id"]
            original_state = snapshot["previous_state"]

            await self.db.execute("""
                UPDATE expenses
                SET estado = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, original_state.get("estado", "pendiente"), expense_id)

    async def _get_action_record(self, action_id: str) -> Optional[ActionRecord]:
        """Obtiene un registro de acción de la base de datos"""

        query = """
        SELECT * FROM expense_action_audit WHERE action_id = $1
        """

        record = await self.db.fetch_one(query, action_id)
        if not record:
            return None

        # Reconstruir ActionRecord desde la base de datos
        # Implementación simplificada - en producción necesitaría deserialización completa
        return ActionRecord(
            action_id=record["action_id"],
            action_type=ActionType(record["action_type"]),
            status=ActionStatus(record["status"]),
            context=ActionContext(
                user_id=record["user_id"],
                company_id=record["company_id"],
                session_id=record["session_id"]
            ),
            target_expense_ids=record["target_expense_ids"],
            parameters=json.loads(record["parameters"]) if record["parameters"] else {},
            snapshots=[],  # Simplificado
            started_at=record["started_at"],
            completed_at=record["completed_at"],
            error_message=record["error_message"],
            rollback_data=json.loads(record["rollback_data"]) if record["rollback_data"] else None,
            affected_records=record["affected_records"],
            execution_time_ms=record["execution_time_ms"]
        )


# Singleton instance
audit_system = ExpenseAuditSystem(None)  # Se inicializa con el adaptador de BD


# Helper functions para uso fácil

async def track_expense_action(
    action_type: ActionType,
    user_id: int,
    company_id: str,
    expense_ids: List[int],
    parameters: Dict[str, Any],
    session_id: Optional[str] = None,
    ip_address: Optional[str] = None
) -> str:
    """Helper para iniciar tracking de una acción"""

    context = ActionContext(
        user_id=user_id,
        company_id=company_id,
        session_id=session_id or str(uuid.uuid4()),
        ip_address=ip_address
    )

    return await audit_system.start_action(action_type, context, expense_ids, parameters)


async def complete_expense_action(action_id: str, affected_records: int) -> ActionRecord:
    """Helper para completar una acción"""
    return await audit_system.complete_action(action_id, affected_records)


async def fail_expense_action(action_id: str, error_message: str) -> ActionRecord:
    """Helper para fallar una acción"""
    return await audit_system.fail_action(action_id, error_message)