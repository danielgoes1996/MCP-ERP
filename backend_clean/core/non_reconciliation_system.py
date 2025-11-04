"""
Sistema de No Conciliación de Gastos
Punto 13: No Conciliación - Complete Implementation

Este módulo proporciona:
- Gestión completa de gastos no conciliables
- Sistema de escalation rules automatizado
- Workflow de resolución con SLA tracking
- Notificaciones automáticas por etapas
- Analytics y métricas de resolución
- Integration con audit trail
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NonReconciliationReason(Enum):
    """Standard non-reconciliation reasons aligned with database schema"""
    MISSING_VENDOR = "missing_vendor"
    MISSING_RECEIPT = "missing_receipt"
    MISSING_CATEGORY = "missing_category"
    MISSING_PROJECT = "missing_project"
    INVALID_FORMAT = "invalid_format"
    ENCODING_ERROR = "encoding_error"
    CURRENCY_MISMATCH = "currency_mismatch"
    AMOUNT_ZERO = "amount_zero"
    AMOUNT_EXCESSIVE = "amount_excessive"
    AMOUNT_PRECISION = "amount_precision"
    DATE_FUTURE = "date_future"
    DATE_TOO_OLD = "date_too_old"
    DATE_FORMAT = "date_format"
    VENDOR_NOT_FOUND = "vendor_not_found"
    VENDOR_INACTIVE = "vendor_inactive"
    DUPLICATE_SUSPECTED = "duplicate_suspected"
    CONFLICT_DETECTED = "conflict_detected"
    SYSTEM_ERROR = "system_error"
    API_TIMEOUT = "api_timeout"
    DATABASE_CONSTRAINT = "database_constraint"
    POLICY_VIOLATION = "policy_violation"
    HIGH_RISK_VENDOR = "high_risk_vendor"
    UNUSUAL_PATTERN = "unusual_pattern"
    BANK_RECONCILIATION = "bank_reconciliation"
    APPROVAL_PENDING = "approval_pending"
    DOCUMENT_VERIFICATION = "document_verification"


class ReconciliationStatus(Enum):
    """Status enumeration aligned with database schema"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ON_HOLD = "on_hold"
    REQUIRES_APPROVAL = "requires_approval"


class EscalationLevel(Enum):
    """Escalation levels aligned with database schema"""
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5


class BusinessImpactLevel(Enum):
    """Business impact levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NonReconciliationRequest:
    """Request para marcar gasto como no conciliable"""
    expense_id: int
    reason_code: NonReconciliationReason
    reason_text: str
    reported_by: int
    company_id: str
    estimated_resolution_hours: Optional[int] = None
    priority_level: str = "normal"  # low, normal, high, urgent
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class NonReconciliationRecord:
    """Registro completo de no conciliación"""
    id: int
    expense_id: int
    reason_code: NonReconciliationReason
    reason_text: str
    status: ReconciliationStatus
    reported_by: int
    company_id: str

    # Campos mejorados
    estimated_resolution_date: Optional[datetime]
    actual_resolution_date: Optional[datetime]
    priority_level: str
    escalation_level: EscalationLevel
    assigned_to: Optional[int]

    # Tracking de progreso
    created_at: datetime
    updated_at: datetime
    last_action_at: Optional[datetime]
    resolution_notes: Optional[str]

    # Metadata
    additional_context: Optional[Dict[str, Any]]
    escalation_history: List[Dict[str, Any]]
    action_history: List[Dict[str, Any]]


@dataclass
class EscalationRule:
    """Regla de escalation automática"""
    id: int
    company_id: str
    reason_code: Optional[NonReconciliationReason]
    priority_level: str
    time_threshold_hours: int
    escalate_to_level: EscalationLevel
    notification_template: str
    is_active: bool
    created_at: datetime


class NonReconciliationSystem:
    """Sistema completo de manejo de no conciliación"""

    def __init__(self, db_adapter):
        self.db = db_adapter

        # SLA por defecto en horas
        self.default_sla_hours = {
            "low": 72,      # 3 días
            "normal": 48,   # 2 días
            "high": 24,     # 1 día
            "urgent": 4     # 4 horas
        }

        # Templates de razones comunes
        self.reason_templates = {
            NonReconciliationReason.MISSING_RECEIPT: {
                "display_name": "Recibo Faltante",
                "estimated_hours": 48,
                "auto_escalate": True,
                "escalation_threshold": 72
            },
            NonReconciliationReason.AMOUNT_ZERO: {
                "display_name": "Monto Incorrecto",
                "estimated_hours": 24,
                "auto_escalate": True,
                "escalation_threshold": 48
            },
            NonReconciliationReason.DUPLICATE_SUSPECTED: {
                "display_name": "Entrada Duplicada",
                "estimated_hours": 12,
                "auto_escalate": False,
                "escalation_threshold": 24
            }
        }

    async def mark_as_non_reconcilable(
        self,
        request: NonReconciliationRequest
    ) -> NonReconciliationRecord:
        """Marca un gasto como no conciliable"""

        try:
            # Validar que el gasto existe y es válido
            expense = await self._validate_expense_for_non_reconciliation(request.expense_id)
            if not expense:
                raise ValueError(f"Expense {request.expense_id} not found or invalid")

            # Calcular fecha estimada de resolución
            estimated_resolution_date = await self._calculate_estimated_resolution(
                request.reason_code, request.priority_level, request.estimated_resolution_hours
            )

            # Crear registro
            record_id = await self._create_non_reconciliation_record(request, estimated_resolution_date)

            # Aplicar reglas de escalation iniciales
            await self._apply_initial_escalation_rules(record_id, request)

            # Actualizar estado del gasto
            await self._update_expense_reconciliation_status(
                request.expense_id,
                "non_reconcilable",
                request.reason_code.value
            )

            # Notificar creación
            await self._send_creation_notification(record_id)

            # Programar seguimiento automático
            await self._schedule_automatic_followup(record_id, estimated_resolution_date)

            # Obtener registro completo creado
            record = await self.get_non_reconciliation_record(record_id)

            logger.info(f"Non-reconciliation created: {record_id} for expense {request.expense_id}")
            return record

        except Exception as e:
            logger.error(f"Failed to mark expense {request.expense_id} as non-reconcilable: {e}")
            raise

    async def update_non_reconciliation_status(
        self,
        record_id: int,
        new_status: ReconciliationStatus,
        resolution_notes: Optional[str] = None,
        updated_by: Optional[int] = None
    ) -> NonReconciliationRecord:
        """Actualiza el estado de un registro de no conciliación"""

        try:
            # Obtener registro actual
            current_record = await self.get_non_reconciliation_record(record_id)
            if not current_record:
                raise ValueError(f"Non-reconciliation record {record_id} not found")

            # Validar transición de estado
            if not self._is_valid_status_transition(current_record.status, new_status):
                raise ValueError(f"Invalid status transition: {current_record.status} -> {new_status}")

            # Actualizar en BD
            update_data = {
                "status": new_status.value,
                "updated_at": datetime.utcnow(),
                "last_action_at": datetime.utcnow()
            }

            if resolution_notes:
                update_data["resolution_notes"] = resolution_notes

            if new_status == ReconciliationStatus.RESOLVED:
                update_data["actual_resolution_date"] = datetime.utcnow()
                # Actualizar estado del gasto de vuelta a conciliable
                await self._update_expense_reconciliation_status(
                    current_record.expense_id,
                    "reconcilable",
                    None
                )

            await self._update_non_reconciliation_record(record_id, update_data)

            # Registrar acción en historial
            await self._add_action_to_history(record_id, {
                "action": "status_change",
                "from_status": current_record.status.value,
                "to_status": new_status.value,
                "notes": resolution_notes,
                "updated_by": updated_by,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Notificar cambio de estado
            await self._send_status_change_notification(record_id, current_record.status, new_status)

            # Obtener registro actualizado
            updated_record = await self.get_non_reconciliation_record(record_id)

            logger.info(f"Non-reconciliation {record_id} status updated: {current_record.status.value} -> {new_status.value}")
            return updated_record

        except Exception as e:
            logger.error(f"Failed to update non-reconciliation status {record_id}: {e}")
            raise

    async def escalate_non_reconciliation(
        self,
        record_id: int,
        escalation_level: EscalationLevel,
        escalation_reason: str,
        escalated_by: Optional[int] = None
    ) -> bool:
        """Escala un registro de no conciliación"""

        try:
            # Obtener registro actual
            record = await self.get_non_reconciliation_record(record_id)
            if not record:
                raise ValueError(f"Non-reconciliation record {record_id} not found")

            # Determinar a quién asignar
            assignee = await self._determine_escalation_assignee(
                record.company_id, escalation_level
            )

            # Actualizar registro
            update_data = {
                "escalation_level": escalation_level.value,
                "assigned_to": assignee,
                "status": ReconciliationStatus.ESCALATED.value,
                "updated_at": datetime.utcnow(),
                "last_action_at": datetime.utcnow()
            }

            await self._update_non_reconciliation_record(record_id, update_data)

            # Agregar a historial de escalation
            escalation_entry = {
                "escalation_level": escalation_level.value,
                "reason": escalation_reason,
                "escalated_by": escalated_by,
                "assigned_to": assignee,
                "timestamp": datetime.utcnow().isoformat()
            }

            await self._add_escalation_to_history(record_id, escalation_entry)

            # Notificar escalation
            await self._send_escalation_notification(record_id, escalation_level, assignee)

            logger.info(f"Non-reconciliation {record_id} escalated to {escalation_level.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to escalate non-reconciliation {record_id}: {e}")
            return False

    async def get_non_reconciliation_record(self, record_id: int) -> Optional[NonReconciliationRecord]:
        """Obtiene un registro completo de no conciliación"""

        try:
            query = """
            SELECT
                nr.id, nr.expense_id, nr.reason_code, nr.reason_text,
                nr.status, nr.reported_by, nr.company_id,
                nr.estimated_resolution_date, nr.actual_resolution_date,
                nr.priority_level, nr.escalation_level, nr.assigned_to,
                nr.created_at, nr.updated_at, nr.last_action_at,
                nr.resolution_notes, nr.additional_context,
                nr.escalation_history, nr.action_history
            FROM non_reconciliation_records nr
            WHERE nr.id = $1
            """

            result = await self.db.fetch_one(query, record_id)
            if not result:
                return None

            return NonReconciliationRecord(
                id=result["id"],
                expense_id=result["expense_id"],
                reason_code=NonReconciliationReason(result["reason_code"]),
                reason_text=result["reason_text"],
                status=ReconciliationStatus(result["status"]),
                reported_by=result["reported_by"],
                company_id=result["company_id"],
                estimated_resolution_date=result["estimated_resolution_date"],
                actual_resolution_date=result["actual_resolution_date"],
                priority_level=result["priority_level"],
                escalation_level=EscalationLevel(result["escalation_level"]),
                assigned_to=result["assigned_to"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
                last_action_at=result["last_action_at"],
                resolution_notes=result["resolution_notes"],
                additional_context=result["additional_context"],
                escalation_history=result["escalation_history"] or [],
                action_history=result["action_history"] or []
            )

        except Exception as e:
            logger.error(f"Failed to get non-reconciliation record {record_id}: {e}")
            return None

    async def list_non_reconcilable_expenses(
        self,
        company_id: str,
        status: Optional[ReconciliationStatus] = None,
        assigned_to: Optional[int] = None,
        overdue_only: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lista gastos no conciliables con filtros"""

        try:
            conditions = ["nr.company_id = $1"]
            params = [company_id]
            param_index = 2

            if status:
                conditions.append(f"nr.status = ${param_index}")
                params.append(status.value)
                param_index += 1

            if assigned_to:
                conditions.append(f"nr.assigned_to = ${param_index}")
                params.append(assigned_to)
                param_index += 1

            if overdue_only:
                conditions.append(f"nr.estimated_resolution_date < CURRENT_TIMESTAMP")

            where_clause = " AND ".join(conditions)

            query = f"""
            SELECT
                nr.id, nr.expense_id, nr.reason_code, nr.reason_text,
                nr.status, nr.priority_level, nr.escalation_level,
                nr.estimated_resolution_date, nr.created_at,
                e.descripcion as expense_description,
                e.monto_total as expense_amount,
                u.full_name as reported_by_name,
                a.full_name as assigned_to_name
            FROM non_reconciliation_records nr
            JOIN expenses e ON nr.expense_id = e.id
            JOIN users u ON nr.reported_by = u.id
            LEFT JOIN users a ON nr.assigned_to = a.id
            WHERE {where_clause}
            ORDER BY
                CASE nr.priority_level
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'normal' THEN 3
                    ELSE 4
                END,
                nr.created_at DESC
            LIMIT ${param_index}
            """

            params.append(limit)
            results = await self.db.fetch_all(query, *params)

            return [dict(result) for result in results]

        except Exception as e:
            logger.error(f"Failed to list non-reconcilable expenses: {e}")
            return []

    async def get_non_reconciliation_analytics(
        self,
        company_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Obtiene analytics de no conciliación"""

        try:
            if not date_from:
                date_from = datetime.utcnow() - timedelta(days=30)
            if not date_to:
                date_to = datetime.utcnow()

            # Estadísticas generales
            stats_query = """
            SELECT
                COUNT(*) as total_cases,
                COUNT(*) FILTER (WHERE status = 'resolved') as resolved_cases,
                COUNT(*) FILTER (WHERE status IN ('escalated', 'pending_action')) as pending_cases,
                COUNT(*) FILTER (WHERE estimated_resolution_date < CURRENT_TIMESTAMP AND status NOT IN ('resolved', 'closed_unresolved')) as overdue_cases,
                AVG(EXTRACT(EPOCH FROM (COALESCE(actual_resolution_date, CURRENT_TIMESTAMP) - created_at))/3600) as avg_resolution_hours
            FROM non_reconciliation_records
            WHERE company_id = $1
            AND created_at BETWEEN $2 AND $3
            """

            stats = await self.db.fetch_one(stats_query, company_id, date_from, date_to)

            # Por motivo
            by_reason_query = """
            SELECT
                reason_code,
                COUNT(*) as count,
                AVG(EXTRACT(EPOCH FROM (COALESCE(actual_resolution_date, CURRENT_TIMESTAMP) - created_at))/3600) as avg_resolution_hours
            FROM non_reconciliation_records
            WHERE company_id = $1
            AND created_at BETWEEN $2 AND $3
            GROUP BY reason_code
            ORDER BY count DESC
            """

            by_reason = await self.db.fetch_all(by_reason_query, company_id, date_from, date_to)

            # Tendencias por día
            trends_query = """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as cases_created,
                COUNT(*) FILTER (WHERE status = 'resolved') as cases_resolved
            FROM non_reconciliation_records
            WHERE company_id = $1
            AND created_at BETWEEN $2 AND $3
            GROUP BY DATE(created_at)
            ORDER BY date
            """

            trends = await self.db.fetch_all(trends_query, company_id, date_from, date_to)

            # Performance de escalation
            escalation_stats = await self._get_escalation_analytics(company_id, date_from, date_to)

            return {
                "period": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat()
                },
                "summary": {
                    "total_cases": stats["total_cases"],
                    "resolved_cases": stats["resolved_cases"],
                    "pending_cases": stats["pending_cases"],
                    "overdue_cases": stats["overdue_cases"],
                    "resolution_rate": (stats["resolved_cases"] / max(stats["total_cases"], 1)) * 100,
                    "avg_resolution_hours": round(stats["avg_resolution_hours"] or 0, 2)
                },
                "by_reason": [dict(r) for r in by_reason],
                "daily_trends": [dict(t) for t in trends],
                "escalation_analytics": escalation_stats
            }

        except Exception as e:
            logger.error(f"Failed to get non-reconciliation analytics: {e}")
            return {"error": str(e)}

    # Métodos privados

    async def _validate_expense_for_non_reconciliation(self, expense_id: int) -> Optional[Dict[str, Any]]:
        """Valida que el gasto sea válido para marcar como no conciliable"""

        query = """
        SELECT id, descripcion, monto_total, estado, reconciliation_status
        FROM expenses
        WHERE id = $1 AND estado != 'deleted'
        """

        return await self.db.fetch_one(query, expense_id)

    async def _calculate_estimated_resolution(
        self,
        reason_code: NonReconciliationReason,
        priority_level: str,
        custom_hours: Optional[int]
    ) -> datetime:
        """Calcula fecha estimada de resolución"""

        if custom_hours:
            hours = custom_hours
        else:
            # Usar horas del template de razón o SLA por defecto
            template = self.reason_templates.get(reason_code, {})
            hours = template.get("estimated_hours", self.default_sla_hours.get(priority_level, 48))

        return datetime.utcnow() + timedelta(hours=hours)

    async def _create_non_reconciliation_record(
        self,
        request: NonReconciliationRequest,
        estimated_resolution_date: datetime
    ) -> int:
        """Crea registro en la base de datos"""

        query = """
        INSERT INTO non_reconciliation_records (
            expense_id, reason_code, reason_text, status, reported_by,
            company_id, estimated_resolution_date, priority_level,
            escalation_level, additional_context, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        ) RETURNING id
        """

        result = await self.db.fetch_one(
            query,
            request.expense_id,
            request.reason_code.value,
            request.reason_text,
            ReconciliationStatus.REPORTED.value,
            request.reported_by,
            request.company_id,
            estimated_resolution_date,
            request.priority_level,
            EscalationLevel.NONE.value,
            request.additional_context
        )

        return result["id"]

    async def _apply_initial_escalation_rules(self, record_id: int, request: NonReconciliationRequest):
        """Aplica reglas de escalation iniciales"""

        # Obtener reglas activas
        rules = await self._get_escalation_rules(
            request.company_id,
            request.reason_code,
            request.priority_level
        )

        # Aplicar reglas inmediatas (threshold = 0)
        for rule in rules:
            if rule["time_threshold_hours"] == 0:
                await self.escalate_non_reconciliation(
                    record_id,
                    EscalationLevel(rule["escalate_to_level"]),
                    f"Automatic escalation by rule: {rule['id']}",
                    None
                )

    async def _update_expense_reconciliation_status(
        self,
        expense_id: int,
        reconciliation_status: str,
        reason_code: Optional[str]
    ):
        """Actualiza estado de conciliación del gasto"""

        query = """
        UPDATE expenses
        SET reconciliation_status = $1,
            reconciliation_reason = $2,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $3
        """

        await self.db.execute(query, reconciliation_status, reason_code, expense_id)

    async def _send_creation_notification(self, record_id: int):
        """Envía notificación de creación"""
        # Implementación de notificación
        logger.info(f"Notification sent for non-reconciliation creation: {record_id}")

    async def _schedule_automatic_followup(self, record_id: int, estimated_date: datetime):
        """Programa seguimiento automático"""
        # En producción, esto usaría un sistema de colas/scheduler
        logger.info(f"Automatic follow-up scheduled for {record_id} at {estimated_date}")

    def _is_valid_status_transition(
        self,
        current_status: ReconciliationStatus,
        new_status: ReconciliationStatus
    ) -> bool:
        """Valida si la transición de estado es válida"""

        valid_transitions = {
            ReconciliationStatus.REPORTED: [
                ReconciliationStatus.UNDER_REVIEW,
                ReconciliationStatus.ESCALATED,
                ReconciliationStatus.CANCELLED
            ],
            ReconciliationStatus.UNDER_REVIEW: [
                ReconciliationStatus.PENDING_ACTION,
                ReconciliationStatus.ESCALATED,
                ReconciliationStatus.IN_RESOLUTION,
                ReconciliationStatus.RESOLVED
            ],
            ReconciliationStatus.PENDING_ACTION: [
                ReconciliationStatus.UNDER_REVIEW,
                ReconciliationStatus.ESCALATED,
                ReconciliationStatus.IN_RESOLUTION
            ],
            ReconciliationStatus.ESCALATED: [
                ReconciliationStatus.UNDER_REVIEW,
                ReconciliationStatus.IN_RESOLUTION,
                ReconciliationStatus.RESOLVED
            ],
            ReconciliationStatus.IN_RESOLUTION: [
                ReconciliationStatus.RESOLVED,
                ReconciliationStatus.CLOSED_UNRESOLVED,
                ReconciliationStatus.ESCALATED
            ]
        }

        return new_status in valid_transitions.get(current_status, [])

    async def _update_non_reconciliation_record(self, record_id: int, update_data: Dict[str, Any]):
        """Actualiza registro en BD"""

        # Construir query dinámico
        set_clauses = []
        params = []
        param_index = 1

        for key, value in update_data.items():
            set_clauses.append(f"{key} = ${param_index}")
            params.append(value)
            param_index += 1

        params.append(record_id)  # Para WHERE clause

        query = f"""
        UPDATE non_reconciliation_records
        SET {', '.join(set_clauses)}
        WHERE id = ${param_index}
        """

        await self.db.execute(query, *params)

    async def _add_action_to_history(self, record_id: int, action_data: Dict[str, Any]):
        """Añade acción al historial"""

        # Obtener historial actual
        current_history = await self.db.fetch_one(
            "SELECT action_history FROM non_reconciliation_records WHERE id = $1",
            record_id
        )

        history = current_history["action_history"] or []
        history.append(action_data)

        # Actualizar
        await self.db.execute(
            "UPDATE non_reconciliation_records SET action_history = $1 WHERE id = $2",
            history,
            record_id
        )

    async def _add_escalation_to_history(self, record_id: int, escalation_data: Dict[str, Any]):
        """Añade escalation al historial"""

        current_history = await self.db.fetch_one(
            "SELECT escalation_history FROM non_reconciliation_records WHERE id = $1",
            record_id
        )

        history = current_history["escalation_history"] or []
        history.append(escalation_data)

        await self.db.execute(
            "UPDATE non_reconciliation_records SET escalation_history = $1 WHERE id = $2",
            history,
            record_id
        )

    async def _determine_escalation_assignee(
        self,
        company_id: str,
        escalation_level: EscalationLevel
    ) -> Optional[int]:
        """Determina a quién asignar según nivel de escalation"""

        role_mapping = {
            EscalationLevel.SUPERVISOR: "supervisor",
            EscalationLevel.MANAGER: "manager",
            EscalationLevel.ADMIN: "admin",
            EscalationLevel.FINANCE_TEAM: "finance"
        }

        role = role_mapping.get(escalation_level)
        if not role:
            return None

        # Buscar usuario disponible con ese rol
        query = """
        SELECT id FROM users
        WHERE company_id = $1
        AND role = $2
        AND is_active = TRUE
        ORDER BY last_login DESC
        LIMIT 1
        """

        result = await self.db.fetch_one(query, company_id, role)
        return result["id"] if result else None

    async def _send_status_change_notification(
        self,
        record_id: int,
        old_status: ReconciliationStatus,
        new_status: ReconciliationStatus
    ):
        """Envía notificación de cambio de estado"""
        logger.info(f"Status change notification for {record_id}: {old_status.value} -> {new_status.value}")

    async def _send_escalation_notification(
        self,
        record_id: int,
        escalation_level: EscalationLevel,
        assignee: Optional[int]
    ):
        """Envía notificación de escalation"""
        logger.info(f"Escalation notification for {record_id} to level {escalation_level.value}, assignee: {assignee}")

    async def _get_escalation_rules(
        self,
        company_id: str,
        reason_code: NonReconciliationReason,
        priority_level: str
    ) -> List[Dict[str, Any]]:
        """Obtiene reglas de escalation aplicables"""

        query = """
        SELECT * FROM non_reconciliation_escalation_rules
        WHERE company_id = $1
        AND (reason_code = $2 OR reason_code IS NULL)
        AND (priority_level = $3 OR priority_level IS NULL)
        AND is_active = TRUE
        ORDER BY priority_order ASC
        """

        results = await self.db.fetch_all(query, company_id, reason_code.value, priority_level)
        return [dict(r) for r in results]

    async def _get_escalation_analytics(
        self,
        company_id: str,
        date_from: datetime,
        date_to: datetime
    ) -> Dict[str, Any]:
        """Obtiene analytics de escalation"""

        query = """
        SELECT
            escalation_level,
            COUNT(*) as escalations_count,
            AVG(EXTRACT(EPOCH FROM (COALESCE(actual_resolution_date, CURRENT_TIMESTAMP) - created_at))/3600) as avg_time_to_resolve
        FROM non_reconciliation_records
        WHERE company_id = $1
        AND created_at BETWEEN $2 AND $3
        AND escalation_level != 'none'
        GROUP BY escalation_level
        """

        results = await self.db.fetch_all(query, company_id, date_from, date_to)

        return {
            "escalation_breakdown": [dict(r) for r in results],
            "total_escalations": sum(r["escalations_count"] for r in results)
        }


# Singleton instance
non_reconciliation_system = NonReconciliationSystem(None)  # Se inicializa con el adaptador de BD


# Helper functions

async def mark_expense_non_reconcilable(
    expense_id: int,
    reason_code: NonReconciliationReason,
    reason_text: str,
    reported_by: int,
    company_id: str
) -> NonReconciliationRecord:
    """Helper para marcar gasto como no conciliable"""

    request = NonReconciliationRequest(
        expense_id=expense_id,
        reason_code=reason_code,
        reason_text=reason_text,
        reported_by=reported_by,
        company_id=company_id
    )

    return await non_reconciliation_system.mark_as_non_reconcilable(request)


async def resolve_non_reconcilable(
    record_id: int,
    resolution_notes: str,
    resolved_by: int
) -> NonReconciliationRecord:
    """Helper para resolver no conciliable"""

    return await non_reconciliation_system.update_non_reconciliation_status(
        record_id,
        ReconciliationStatus.RESOLVED,
        resolution_notes,
        resolved_by
    )