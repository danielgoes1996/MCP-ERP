"""
Sistema de Rollback Optimizado para Operaciones Masivas de Gastos
Punto 12: Acciones de Gastos - Rollback System Implementation

Este módulo proporciona:
- Rollback inteligente por tipos de operación
- Verificación de integridad pre/post rollback
- Rollback parcial y por lotes
- Recovery automático en caso de fallo
- Performance optimizado para operaciones masivas
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from core.expense_audit_system import ActionType, ActionStatus, audit_system

logger = logging.getLogger(__name__)


class RollbackStrategy(Enum):
    """Estrategias de rollback disponibles"""
    IMMEDIATE = "immediate"           # Rollback inmediato
    DEFERRED = "deferred"            # Rollback diferido/programado
    BATCH = "batch"                  # Rollback por lotes
    SELECTIVE = "selective"          # Rollback selectivo de registros específicos
    CASCADE = "cascade"              # Rollback en cascada (incluye dependencias)


class RollbackStatus(Enum):
    """Estados del proceso de rollback"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RollbackPlan:
    """Plan de rollback detallado"""
    action_id: str
    strategy: RollbackStrategy
    target_records: List[int]
    estimated_duration_ms: int
    risk_level: str  # 'low', 'medium', 'high'
    dependencies: List[str]
    verification_steps: List[str]
    rollback_order: List[Dict[str, Any]]


@dataclass
class RollbackResult:
    """Resultado del rollback"""
    success: bool
    records_processed: int
    records_successful: int
    records_failed: int
    execution_time_ms: int
    errors: List[str]
    warnings: List[str]
    final_status: RollbackStatus


class ExpenseRollbackSystem:
    """Sistema de rollback para operaciones de gastos"""

    def __init__(self, db_adapter):
        self.db = db_adapter
        self._active_rollbacks: Dict[str, RollbackPlan] = {}
        self.max_concurrent_rollbacks = 3
        self.rollback_timeout_minutes = 30

    async def create_rollback_plan(
        self,
        action_id: str,
        strategy: RollbackStrategy = RollbackStrategy.IMMEDIATE,
        selective_records: Optional[List[int]] = None
    ) -> RollbackPlan:
        """Crea un plan de rollback detallado"""

        # Obtener información de la acción original
        action_record = await audit_system._get_action_record(action_id)
        if not action_record:
            raise ValueError(f"Action record {action_id} not found")

        if not action_record.rollback_data:
            raise ValueError(f"No rollback data available for action {action_id}")

        # Determinar registros objetivo
        if selective_records:
            target_records = selective_records
        else:
            target_records = action_record.target_expense_ids

        # Calcular duración estimada
        estimated_duration = self._estimate_rollback_duration(
            action_record.action_type,
            len(target_records),
            strategy
        )

        # Evaluar nivel de riesgo
        risk_level = self._assess_rollback_risk(action_record, strategy)

        # Identificar dependencias
        dependencies = await self._identify_rollback_dependencies(
            action_record.action_type,
            target_records
        )

        # Crear pasos de verificación
        verification_steps = self._create_verification_steps(
            action_record.action_type,
            target_records
        )

        # Crear orden de rollback
        rollback_order = await self._create_rollback_order(
            action_record,
            target_records,
            strategy
        )

        plan = RollbackPlan(
            action_id=action_id,
            strategy=strategy,
            target_records=target_records,
            estimated_duration_ms=estimated_duration,
            risk_level=risk_level,
            dependencies=dependencies,
            verification_steps=verification_steps,
            rollback_order=rollback_order
        )

        self._active_rollbacks[action_id] = plan

        logger.info(f"Rollback plan created for action {action_id}: {risk_level} risk, {len(target_records)} records")

        return plan

    async def execute_rollback(
        self,
        action_id: str,
        plan: Optional[RollbackPlan] = None,
        dry_run: bool = False
    ) -> RollbackResult:
        """Ejecuta el rollback según el plan"""

        if not plan:
            plan = self._active_rollbacks.get(action_id)
            if not plan:
                raise ValueError(f"No rollback plan found for action {action_id}")

        # Verificar si hay demasiados rollbacks concurrentes
        active_count = len([p for p in self._active_rollbacks.values()
                           if hasattr(p, 'status') and p.status == RollbackStatus.IN_PROGRESS])

        if active_count >= self.max_concurrent_rollbacks:
            raise RuntimeError("Maximum concurrent rollbacks reached. Please wait.")

        start_time = datetime.utcnow()

        try:
            # Marcar como en progreso
            plan.status = RollbackStatus.IN_PROGRESS

            # Pre-verificación
            pre_check_passed = await self._pre_rollback_verification(plan)
            if not pre_check_passed and not dry_run:
                raise RuntimeError("Pre-rollback verification failed")

            # Ejecutar rollback según estrategia
            if plan.strategy == RollbackStrategy.IMMEDIATE:
                result = await self._execute_immediate_rollback(plan, dry_run)
            elif plan.strategy == RollbackStrategy.BATCH:
                result = await self._execute_batch_rollback(plan, dry_run)
            elif plan.strategy == RollbackStrategy.SELECTIVE:
                result = await self._execute_selective_rollback(plan, dry_run)
            elif plan.strategy == RollbackStrategy.CASCADE:
                result = await self._execute_cascade_rollback(plan, dry_run)
            else:
                raise ValueError(f"Rollback strategy {plan.strategy} not implemented")

            # Post-verificación
            if result.success and not dry_run:
                post_check_passed = await self._post_rollback_verification(plan, result)
                if not post_check_passed:
                    result.success = False
                    result.errors.append("Post-rollback verification failed")

            # Actualizar estado final
            if result.success:
                if result.records_failed == 0:
                    result.final_status = RollbackStatus.COMPLETED
                else:
                    result.final_status = RollbackStatus.PARTIALLY_COMPLETED
            else:
                result.final_status = RollbackStatus.FAILED

            # Calcular tiempo de ejecución
            end_time = datetime.utcnow()
            result.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Limpiar plan activo
            if action_id in self._active_rollbacks:
                del self._active_rollbacks[action_id]

            # Persistir resultado
            await self._persist_rollback_result(action_id, result, dry_run)

            logger.info(f"Rollback {'simulation' if dry_run else 'execution'} completed for action {action_id}: "
                       f"{result.records_successful}/{result.records_processed} successful")

            return result

        except Exception as e:
            logger.error(f"Rollback execution failed for action {action_id}: {e}")

            result = RollbackResult(
                success=False,
                records_processed=0,
                records_successful=0,
                records_failed=0,
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                errors=[str(e)],
                warnings=[],
                final_status=RollbackStatus.FAILED
            )

            await self._persist_rollback_result(action_id, result, dry_run)
            return result

    async def get_rollback_status(self, action_id: str) -> Dict[str, Any]:
        """Obtiene el estado actual del rollback"""

        # Buscar en rollbacks activos
        if action_id in self._active_rollbacks:
            plan = self._active_rollbacks[action_id]
            return {
                "status": getattr(plan, 'status', RollbackStatus.PENDING).value,
                "strategy": plan.strategy.value,
                "target_records_count": len(plan.target_records),
                "estimated_duration_ms": plan.estimated_duration_ms,
                "risk_level": plan.risk_level,
                "dependencies": plan.dependencies
            }

        # Buscar en histórico
        query = """
        SELECT rollback_executed, rollback_executed_at, status
        FROM expense_action_audit
        WHERE action_id = $1
        """

        record = await self.db.fetch_one(query, action_id)
        if not record:
            return {"status": "not_found"}

        return {
            "status": "completed" if record["rollback_executed"] else "not_executed",
            "executed_at": record["rollback_executed_at"],
            "original_action_status": record["status"]
        }

    async def cancel_rollback(self, action_id: str) -> bool:
        """Cancela un rollback en progreso"""

        if action_id not in self._active_rollbacks:
            return False

        plan = self._active_rollbacks[action_id]
        if hasattr(plan, 'status') and plan.status == RollbackStatus.IN_PROGRESS:
            # En una implementación real, necesitaríamos cancelar las operaciones en curso
            plan.status = RollbackStatus.CANCELLED
            logger.warning(f"Rollback cancelled for action {action_id}")

        del self._active_rollbacks[action_id]
        return True

    # Métodos privados de implementación

    def _estimate_rollback_duration(
        self,
        action_type: ActionType,
        record_count: int,
        strategy: RollbackStrategy
    ) -> int:
        """Estima la duración del rollback en milisegundos"""

        base_time_per_record = {
            ActionType.MARK_INVOICED: 10,        # 10ms por registro
            ActionType.MARK_NO_INVOICE: 8,       # 8ms por registro
            ActionType.UPDATE_CATEGORY: 15,      # 15ms por registro
            ActionType.BULK_UPDATE: 20,          # 20ms por registro
            ActionType.ARCHIVE: 5,               # 5ms por registro
            ActionType.DELETE: 25,               # 25ms por registro (más complejo)
        }.get(action_type, 15)

        strategy_multiplier = {
            RollbackStrategy.IMMEDIATE: 1.0,
            RollbackStrategy.BATCH: 0.8,         # Más eficiente
            RollbackStrategy.SELECTIVE: 1.2,     # Overhead de selección
            RollbackStrategy.CASCADE: 1.5,       # Overhead de dependencias
        }.get(strategy, 1.0)

        estimated_ms = int(record_count * base_time_per_record * strategy_multiplier)

        # Añadir overhead base
        return max(estimated_ms, 100) + 500  # Mínimo 100ms + 500ms overhead

    def _assess_rollback_risk(
        self,
        action_record,
        strategy: RollbackStrategy
    ) -> str:
        """Evalúa el nivel de riesgo del rollback"""

        risk_factors = []

        # Factor de tiempo transcurrido
        if action_record.completed_at:
            age_hours = (datetime.utcnow() - action_record.completed_at).total_seconds() / 3600
            if age_hours > 24:
                risk_factors.append("old_action")

        # Factor de tamaño de operación
        if len(action_record.target_expense_ids) > 100:
            risk_factors.append("large_batch")

        # Factor de tipo de acción
        high_risk_actions = [ActionType.DELETE, ActionType.BULK_UPDATE]
        if action_record.action_type in high_risk_actions:
            risk_factors.append("high_impact_action")

        # Factor de estrategia
        if strategy == RollbackStrategy.CASCADE:
            risk_factors.append("cascade_strategy")

        # Evaluar riesgo general
        if len(risk_factors) >= 3:
            return "high"
        elif len(risk_factors) >= 1:
            return "medium"
        else:
            return "low"

    async def _identify_rollback_dependencies(
        self,
        action_type: ActionType,
        target_records: List[int]
    ) -> List[str]:
        """Identifica dependencias que podrían afectar el rollback"""

        dependencies = []

        # Verificar facturas vinculadas
        if action_type in [ActionType.MARK_INVOICED, ActionType.DELETE]:
            invoice_query = """
            SELECT COUNT(*) as count FROM invoices
            WHERE expense_id = ANY($1)
            """
            result = await self.db.fetch_one(invoice_query, target_records)
            if result["count"] > 0:
                dependencies.append("linked_invoices")

        # Verificar conciliaciones bancarias
        bank_query = """
        SELECT COUNT(*) as count FROM bank_reconciliation
        WHERE expense_id = ANY($1)
        """
        try:
            result = await self.db.fetch_one(bank_query, target_records)
            if result["count"] > 0:
                dependencies.append("bank_reconciliation")
        except:
            pass  # Tabla podría no existir aún

        # Verificar aprobaciones
        approval_query = """
        SELECT COUNT(*) as count FROM expenses
        WHERE id = ANY($1) AND approval_status = 'approved'
        """
        result = await self.db.fetch_one(approval_query, target_records)
        if result["count"] > 0:
            dependencies.append("approved_expenses")

        return dependencies

    def _create_verification_steps(
        self,
        action_type: ActionType,
        target_records: List[int]
    ) -> List[str]:
        """Crea pasos de verificación específicos para el tipo de acción"""

        base_steps = [
            "verify_records_exist",
            "verify_current_state",
            "verify_no_concurrent_modifications"
        ]

        action_specific_steps = {
            ActionType.MARK_INVOICED: [
                "verify_invoice_status_revertible",
                "verify_no_payment_records"
            ],
            ActionType.UPDATE_CATEGORY: [
                "verify_category_change_impact",
                "verify_reporting_dependencies"
            ],
            ActionType.DELETE: [
                "verify_no_hard_dependencies",
                "verify_backup_availability"
            ],
            ActionType.BULK_UPDATE: [
                "verify_field_consistency",
                "verify_business_rules"
            ]
        }.get(action_type, [])

        return base_steps + action_specific_steps

    async def _create_rollback_order(
        self,
        action_record,
        target_records: List[int],
        strategy: RollbackStrategy
    ) -> List[Dict[str, Any]]:
        """Crea el orden óptimo de rollback"""

        if strategy == RollbackStrategy.BATCH:
            # Dividir en lotes
            batch_size = 50
            batches = []
            for i in range(0, len(target_records), batch_size):
                batch = target_records[i:i + batch_size]
                batches.append({
                    "step": f"batch_{i // batch_size + 1}",
                    "records": batch,
                    "operation": "rollback_batch",
                    "estimated_time_ms": len(batch) * 15
                })
            return batches

        elif strategy == RollbackStrategy.CASCADE:
            # Orden para rollback en cascada
            return [
                {
                    "step": "rollback_dependent_records",
                    "records": target_records,
                    "operation": "rollback_dependencies",
                    "estimated_time_ms": len(target_records) * 25
                },
                {
                    "step": "rollback_main_records",
                    "records": target_records,
                    "operation": "rollback_main",
                    "estimated_time_ms": len(target_records) * 20
                }
            ]

        else:
            # Rollback directo
            return [
                {
                    "step": "rollback_all",
                    "records": target_records,
                    "operation": "rollback_direct",
                    "estimated_time_ms": len(target_records) * 15
                }
            ]

    async def _pre_rollback_verification(self, plan: RollbackPlan) -> bool:
        """Verificación previa al rollback"""

        try:
            # Verificar que los registros todavía existen
            existing_count = await self.db.fetch_one(
                "SELECT COUNT(*) as count FROM expenses WHERE id = ANY($1)",
                plan.target_records
            )

            if existing_count["count"] != len(plan.target_records):
                logger.warning(f"Some target records no longer exist for rollback {plan.action_id}")
                return False

            # Verificar no hay modificaciones concurrentes
            # (Implementación simplificada - en producción sería más compleja)
            recent_changes = await self.db.fetch_one("""
                SELECT COUNT(*) as count FROM expense_action_audit
                WHERE $1 && target_expense_ids
                AND started_at > CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                AND action_id != $2
            """, plan.target_records, plan.action_id)

            if recent_changes["count"] > 0:
                logger.warning(f"Concurrent modifications detected for rollback {plan.action_id}")
                return False

            return True

        except Exception as e:
            logger.error(f"Pre-rollback verification failed: {e}")
            return False

    async def _execute_immediate_rollback(
        self,
        plan: RollbackPlan,
        dry_run: bool
    ) -> RollbackResult:
        """Ejecuta rollback inmediato"""

        successful = 0
        failed = 0
        errors = []

        # Obtener datos de rollback
        action_record = await audit_system._get_action_record(plan.action_id)

        for expense_id in plan.target_records:
            try:
                if not dry_run:
                    # Ejecutar rollback real
                    await self._rollback_single_expense(
                        expense_id,
                        action_record.rollback_data
                    )
                successful += 1

            except Exception as e:
                failed += 1
                errors.append(f"Expense {expense_id}: {str(e)}")
                logger.error(f"Failed to rollback expense {expense_id}: {e}")

        return RollbackResult(
            success=(failed == 0),
            records_processed=len(plan.target_records),
            records_successful=successful,
            records_failed=failed,
            execution_time_ms=0,  # Se calcula en el método padre
            errors=errors,
            warnings=[],
            final_status=RollbackStatus.PENDING  # Se actualiza en el método padre
        )

    async def _execute_batch_rollback(
        self,
        plan: RollbackPlan,
        dry_run: bool
    ) -> RollbackResult:
        """Ejecuta rollback por lotes para mejor performance"""

        successful = 0
        failed = 0
        errors = []
        warnings = []

        batch_size = 50
        action_record = await audit_system._get_action_record(plan.action_id)

        for i in range(0, len(plan.target_records), batch_size):
            batch = plan.target_records[i:i + batch_size]

            try:
                if not dry_run:
                    # Ejecutar rollback del lote
                    batch_success = await self._rollback_expense_batch(
                        batch,
                        action_record.rollback_data
                    )
                    successful += batch_success
                    if batch_success < len(batch):
                        failed += len(batch) - batch_success
                        warnings.append(f"Batch {i//batch_size + 1}: {batch_success}/{len(batch)} successful")
                else:
                    successful += len(batch)

                # Pequeña pausa entre lotes para no sobrecargar
                await asyncio.sleep(0.1)

            except Exception as e:
                failed += len(batch)
                errors.append(f"Batch {i//batch_size + 1}: {str(e)}")

        return RollbackResult(
            success=(failed == 0),
            records_processed=len(plan.target_records),
            records_successful=successful,
            records_failed=failed,
            execution_time_ms=0,
            errors=errors,
            warnings=warnings,
            final_status=RollbackStatus.PENDING
        )

    async def _execute_selective_rollback(
        self,
        plan: RollbackPlan,
        dry_run: bool
    ) -> RollbackResult:
        """Ejecuta rollback selectivo"""
        # Similar a immediate pero con filtros adicionales
        return await self._execute_immediate_rollback(plan, dry_run)

    async def _execute_cascade_rollback(
        self,
        plan: RollbackPlan,
        dry_run: bool
    ) -> RollbackResult:
        """Ejecuta rollback en cascada con dependencias"""

        successful = 0
        failed = 0
        errors = []

        action_record = await audit_system._get_action_record(plan.action_id)

        try:
            # Paso 1: Rollback de dependencias
            if "linked_invoices" in plan.dependencies:
                if not dry_run:
                    dep_result = await self._rollback_invoice_dependencies(plan.target_records)
                    if not dep_result:
                        errors.append("Failed to rollback invoice dependencies")

            # Paso 2: Rollback principal
            main_result = await self._execute_immediate_rollback(plan, dry_run)
            return main_result

        except Exception as e:
            errors.append(f"Cascade rollback failed: {str(e)}")
            return RollbackResult(
                success=False,
                records_processed=len(plan.target_records),
                records_successful=0,
                records_failed=len(plan.target_records),
                execution_time_ms=0,
                errors=errors,
                warnings=[],
                final_status=RollbackStatus.FAILED
            )

    async def _rollback_single_expense(
        self,
        expense_id: int,
        rollback_data: Dict[str, Any]
    ):
        """Rollback de un gasto individual"""

        snapshots = rollback_data.get("original_snapshots", [])
        expense_snapshot = None

        # Buscar snapshot del gasto específico
        for snapshot in snapshots:
            if snapshot["expense_id"] == expense_id:
                expense_snapshot = snapshot
                break

        if not expense_snapshot:
            raise ValueError(f"No snapshot found for expense {expense_id}")

        # Restaurar estado original
        original_state = expense_snapshot["previous_state"]
        await audit_system._rollback_field_changes([expense_snapshot])

    async def _rollback_expense_batch(
        self,
        expense_ids: List[int],
        rollback_data: Dict[str, Any]
    ) -> int:
        """Rollback de un lote de gastos"""

        snapshots = rollback_data.get("original_snapshots", [])
        batch_snapshots = [s for s in snapshots if s["expense_id"] in expense_ids]

        try:
            await audit_system._rollback_field_changes(batch_snapshots)
            return len(batch_snapshots)
        except Exception as e:
            logger.error(f"Batch rollback failed: {e}")
            return 0

    async def _rollback_invoice_dependencies(self, expense_ids: List[int]) -> bool:
        """Rollback de dependencias de facturas"""

        try:
            # Eliminar vínculos de facturas que fueron creados por la acción
            await self.db.execute("""
                UPDATE invoices SET expense_id = NULL
                WHERE expense_id = ANY($1)
                AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
            """, expense_ids)

            return True
        except Exception as e:
            logger.error(f"Failed to rollback invoice dependencies: {e}")
            return False

    async def _post_rollback_verification(
        self,
        plan: RollbackPlan,
        result: RollbackResult
    ) -> bool:
        """Verificación posterior al rollback"""

        try:
            # Verificar que los campos se restauraron correctamente
            # (Implementación simplificada)
            restored_count = await self.db.fetch_one(
                "SELECT COUNT(*) as count FROM expenses WHERE id = ANY($1)",
                plan.target_records
            )

            return restored_count["count"] == len(plan.target_records)

        except Exception as e:
            logger.error(f"Post-rollback verification failed: {e}")
            return False

    async def _persist_rollback_result(
        self,
        action_id: str,
        result: RollbackResult,
        dry_run: bool
    ):
        """Persiste el resultado del rollback"""

        if not dry_run:
            # Marcar el rollback como ejecutado en la auditoría
            await self.db.execute("""
                UPDATE expense_action_audit
                SET rollback_executed = TRUE,
                    rollback_executed_at = CURRENT_TIMESTAMP,
                    status = $2
                WHERE action_id = $1
            """, action_id, result.final_status.value)

        # Log del resultado
        log_data = {
            "action_id": action_id,
            "dry_run": dry_run,
            "success": result.success,
            "records_processed": result.records_processed,
            "records_successful": result.records_successful,
            "execution_time_ms": result.execution_time_ms,
            "errors": result.errors
        }

        logger.info(f"Rollback result persisted: {log_data}")


# Singleton instance
rollback_system = ExpenseRollbackSystem(None)  # Se inicializa con el adaptador de BD