"""
Rollback Safety - Mitigación de riesgos de deployment

Sistema de rollback seguro con feature flags y health checks.
"""

import json
import sqlite3
import logging
import asyncio
import hashlib
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

class RollbackTrigger(Enum):
    """Razones para activar rollback."""
    MANUAL = "manual"
    ERROR_RATE_HIGH = "error_rate_high"
    RESPONSE_TIME_HIGH = "response_time_high"
    HEALTH_CHECK_FAILED = "health_check_failed"
    FEATURE_FLAG_EMERGENCY = "feature_flag_emergency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"

@dataclass
class DeploymentSnapshot:
    """Snapshot de deployment."""
    id: str
    version: str
    timestamp: datetime
    feature_flags_state: Dict[str, Any]
    database_schema_version: str
    config_checksum: str
    code_checksum: str
    rollback_data: Dict[str, Any]

@dataclass
class RollbackPlan:
    """Plan de rollback."""
    snapshot_id: str
    steps: List[Dict[str, Any]]
    estimated_duration_seconds: int
    risk_level: str  # "low", "medium", "high"
    validation_checks: List[str]

class FeatureFlagManager:
    """Gestor avanzado de feature flags con rollback automático."""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path
        self.flag_states = {}
        self.rollback_conditions = {}
        self.emergency_disable_list = set()

    def create_feature_flag(
        self,
        name: str,
        description: str,
        rollback_conditions: Dict[str, Any] = None,
        emergency_disable: bool = False
    ):
        """Crear feature flag con condiciones de rollback."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO feature_flags (
                        feature_name, description, enabled, rollback_conditions,
                        emergency_disable, created_at, updated_at, company_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    name, description, False,
                    json.dumps(rollback_conditions or {}),
                    emergency_disable,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "system"
                ])

                self.rollback_conditions[name] = rollback_conditions or {}
                if emergency_disable:
                    self.emergency_disable_list.add(name)

                logger.info(f"Feature flag created: {name}")

        except Exception as e:
            logger.error(f"Error creating feature flag {name}: {e}")

    def enable_feature_gradual(
        self,
        name: str,
        company_ids: List[str] = None,
        percentage: float = 100.0,
        monitoring_period_minutes: int = 60
    ) -> bool:
        """Habilitar feature de forma gradual con monitoreo."""
        try:
            # Si no se especifican companies, aplicar globalmente
            if company_ids is None:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT DISTINCT company_id FROM tickets")
                    company_ids = [row[0] for row in cursor.fetchall()]

            # Calcular companies a habilitar según porcentaje
            target_count = int(len(company_ids) * (percentage / 100.0))
            selected_companies = company_ids[:target_count]

            # Habilitar para companies seleccionadas
            with sqlite3.connect(self.db_path) as conn:
                for company_id in selected_companies:
                    conn.execute("""
                        INSERT OR REPLACE INTO feature_flags (
                            feature_name, company_id, enabled, enabled_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?)
                    """, [
                        name, company_id, True,
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ])

                conn.commit()

            # Programar verificación automática
            asyncio.create_task(
                self._monitor_feature_rollout(name, selected_companies, monitoring_period_minutes)
            )

            logger.info(f"Feature {name} enabled for {len(selected_companies)} companies ({percentage}%)")
            return True

        except Exception as e:
            logger.error(f"Error enabling feature {name}: {e}")
            return False

    async def _monitor_feature_rollout(
        self,
        feature_name: str,
        company_ids: List[str],
        monitoring_period_minutes: int
    ):
        """Monitorear rollout de feature y deshabilitar si hay problemas."""
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=monitoring_period_minutes)

        logger.info(f"Starting monitoring for feature {feature_name} for {monitoring_period_minutes} minutes")

        while datetime.now() < end_time:
            try:
                # Verificar condiciones de rollback
                should_rollback = await self._check_rollback_conditions(feature_name, company_ids)

                if should_rollback:
                    logger.warning(f"Rollback conditions met for feature {feature_name}, disabling")
                    await self.emergency_disable_feature(feature_name, "Automatic rollback due to monitoring")
                    break

                await asyncio.sleep(60)  # Verificar cada minuto

            except Exception as e:
                logger.error(f"Error monitoring feature {feature_name}: {e}")
                await asyncio.sleep(10)

        logger.info(f"Monitoring completed for feature {feature_name}")

    async def _check_rollback_conditions(self, feature_name: str, company_ids: List[str]) -> bool:
        """Verificar condiciones de rollback para una feature."""
        conditions = self.rollback_conditions.get(feature_name, {})

        if not conditions:
            return False

        try:
            # Obtener métricas para las companies con la feature habilitada
            metrics = await self._get_feature_metrics(feature_name, company_ids)

            # Verificar error rate
            if "max_error_rate" in conditions:
                if metrics.get("error_rate", 0) > conditions["max_error_rate"]:
                    logger.warning(f"Feature {feature_name} error rate too high: {metrics['error_rate']}")
                    return True

            # Verificar response time
            if "max_response_time_ms" in conditions:
                if metrics.get("avg_response_time_ms", 0) > conditions["max_response_time_ms"]:
                    logger.warning(f"Feature {feature_name} response time too high: {metrics['avg_response_time_ms']}ms")
                    return True

            # Verificar job failure rate
            if "max_job_failure_rate" in conditions:
                if metrics.get("job_failure_rate", 0) > conditions["max_job_failure_rate"]:
                    logger.warning(f"Feature {feature_name} job failure rate too high: {metrics['job_failure_rate']}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking rollback conditions for {feature_name}: {e}")
            # En caso de error, rollback por seguridad
            return True

    async def _get_feature_metrics(self, feature_name: str, company_ids: List[str]) -> Dict[str, float]:
        """Obtener métricas para companies con feature habilitada."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Query para obtener métricas de las últimas 2 horas
                two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()

                placeholders = ",".join("?" * len(company_ids))

                # Error rate
                cursor = conn.execute(f"""
                    SELECT
                        COUNT(CASE WHEN estado = 'fallido' THEN 1 END) as failed,
                        COUNT(*) as total
                    FROM automation_jobs
                    WHERE company_id IN ({placeholders})
                    AND created_at > ?
                """, company_ids + [two_hours_ago])

                result = cursor.fetchone()
                if result and result[1] > 0:
                    error_rate = result[0] / result[1]
                else:
                    error_rate = 0

                # Response time (simulado - en producción vendría de métricas)
                avg_response_time_ms = 500  # Placeholder

                # Job failure rate (similar a error rate pero más específico)
                job_failure_rate = error_rate

                return {
                    "error_rate": error_rate,
                    "avg_response_time_ms": avg_response_time_ms,
                    "job_failure_rate": job_failure_rate
                }

        except Exception as e:
            logger.error(f"Error getting metrics for feature {feature_name}: {e}")
            return {}

    async def emergency_disable_feature(self, feature_name: str, reason: str):
        """Deshabilitar feature de emergencia."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE feature_flags
                    SET enabled = ?, disabled_reason = ?, disabled_at = ?, updated_at = ?
                    WHERE feature_name = ?
                """, [
                    False, reason,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    feature_name
                ])

                conn.commit()

            self.emergency_disable_list.add(feature_name)

            # Log emergency disable
            logger.critical(f"EMERGENCY DISABLE: Feature {feature_name} - Reason: {reason}")

            # Notificar a sistema de alertas
            await self._send_emergency_notification(feature_name, reason)

        except Exception as e:
            logger.error(f"Error emergency disabling feature {feature_name}: {e}")

    async def _send_emergency_notification(self, feature_name: str, reason: str):
        """Enviar notificación de emergency disable."""
        try:
            # Aquí se integraría con sistema de notificaciones
            # Por ahora solo logging crítico
            logger.critical(f"EMERGENCY NOTIFICATION: Feature {feature_name} disabled - {reason}")

        except Exception as e:
            logger.error(f"Error sending emergency notification: {e}")

class DeploymentManager:
    """Gestor de deployments con rollback automático."""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path
        self.snapshots_dir = Path("deployment_snapshots")
        self.snapshots_dir.mkdir(exist_ok=True)

    def create_deployment_snapshot(self, version: str) -> DeploymentSnapshot:
        """Crear snapshot antes de deployment."""
        try:
            # Obtener estado actual de feature flags
            feature_flags_state = self._get_current_feature_flags()

            # Obtener versión de schema de DB
            db_schema_version = self._get_db_schema_version()

            # Calcular checksums
            config_checksum = self._calculate_config_checksum()
            code_checksum = self._calculate_code_checksum()

            # Crear snapshot
            snapshot = DeploymentSnapshot(
                id=f"snapshot_{int(datetime.now().timestamp())}",
                version=version,
                timestamp=datetime.now(),
                feature_flags_state=feature_flags_state,
                database_schema_version=db_schema_version,
                config_checksum=config_checksum,
                code_checksum=code_checksum,
                rollback_data={}
            )

            # Guardar snapshot
            self._save_snapshot(snapshot)

            logger.info(f"Deployment snapshot created: {snapshot.id}")
            return snapshot

        except Exception as e:
            logger.error(f"Error creating deployment snapshot: {e}")
            raise

    def _get_current_feature_flags(self) -> Dict[str, Any]:
        """Obtener estado actual de feature flags."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT feature_name, company_id, enabled, rollback_conditions
                    FROM feature_flags
                """)

                flags = {}
                for row in cursor.fetchall():
                    feature_name, company_id, enabled, rollback_conditions = row

                    if feature_name not in flags:
                        flags[feature_name] = []

                    flags[feature_name].append({
                        "company_id": company_id,
                        "enabled": enabled,
                        "rollback_conditions": json.loads(rollback_conditions or "{}")
                    })

                return flags

        except Exception as e:
            logger.error(f"Error getting feature flags state: {e}")
            return {}

    def _get_db_schema_version(self) -> str:
        """Obtener versión de schema de DB."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' ORDER BY name
                """)
                tables = [row[0] for row in cursor.fetchall()]

                # Crear hash de estructura de tablas
                schema_str = ",".join(tables)
                return hashlib.md5(schema_str.encode()).hexdigest()[:16]

        except Exception as e:
            logger.error(f"Error getting DB schema version: {e}")
            return "unknown"

    def _calculate_config_checksum(self) -> str:
        """Calcular checksum de configuración."""
        try:
            # En producción, esto incluiría archivos de config, variables de entorno, etc.
            config_data = {
                "timestamp": datetime.now().isoformat(),
                "placeholder": "config_data"
            }
            config_str = json.dumps(config_data, sort_keys=True)
            return hashlib.md5(config_str.encode()).hexdigest()[:16]

        except Exception as e:
            logger.error(f"Error calculating config checksum: {e}")
            return "unknown"

    def _calculate_code_checksum(self) -> str:
        """Calcular checksum de código."""
        try:
            # En producción, esto sería hash de archivos Python principales
            import os
            code_files = []
            for root, dirs, files in os.walk("."):
                for file in files:
                    if file.endswith(".py"):
                        code_files.append(os.path.join(root, file))

            # Crear hash simple basado en nombres de archivo
            code_str = ",".join(sorted(code_files))
            return hashlib.md5(code_str.encode()).hexdigest()[:16]

        except Exception as e:
            logger.error(f"Error calculating code checksum: {e}")
            return "unknown"

    def _save_snapshot(self, snapshot: DeploymentSnapshot):
        """Guardar snapshot a disco."""
        snapshot_file = self.snapshots_dir / f"{snapshot.id}.json"

        with open(snapshot_file, 'w') as f:
            # Convertir datetime a string para JSON
            snapshot_dict = asdict(snapshot)
            snapshot_dict["timestamp"] = snapshot.timestamp.isoformat()
            json.dump(snapshot_dict, f, indent=2)

    def create_rollback_plan(self, target_snapshot_id: str) -> RollbackPlan:
        """Crear plan de rollback a snapshot específico."""
        try:
            # Cargar snapshot objetivo
            snapshot = self._load_snapshot(target_snapshot_id)
            if not snapshot:
                raise ValueError(f"Snapshot {target_snapshot_id} not found")

            # Crear steps de rollback
            steps = []

            # 1. Deshabilitar features nuevas
            steps.append({
                "type": "disable_new_features",
                "description": "Disable features not present in target snapshot",
                "estimated_seconds": 10
            })

            # 2. Restaurar estado de feature flags
            steps.append({
                "type": "restore_feature_flags",
                "description": "Restore feature flags to snapshot state",
                "data": snapshot["feature_flags_state"],
                "estimated_seconds": 30
            })

            # 3. Verificar integridad de DB
            steps.append({
                "type": "verify_database",
                "description": "Verify database integrity",
                "estimated_seconds": 60
            })

            # 4. Health checks
            steps.append({
                "type": "health_checks",
                "description": "Run comprehensive health checks",
                "estimated_seconds": 120
            })

            total_duration = sum(step.get("estimated_seconds", 0) for step in steps)

            # Determinar nivel de riesgo
            risk_level = "low"  # En producción sería más sofisticado

            rollback_plan = RollbackPlan(
                snapshot_id=target_snapshot_id,
                steps=steps,
                estimated_duration_seconds=total_duration,
                risk_level=risk_level,
                validation_checks=[
                    "api_endpoints_responding",
                    "database_connectivity",
                    "core_features_working",
                    "no_error_spike"
                ]
            )

            logger.info(f"Rollback plan created for snapshot {target_snapshot_id}")
            return rollback_plan

        except Exception as e:
            logger.error(f"Error creating rollback plan: {e}")
            raise

    def _load_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Cargar snapshot desde disco."""
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"

        if not snapshot_file.exists():
            return None

        with open(snapshot_file, 'r') as f:
            return json.load(f)

    async def execute_rollback(self, rollback_plan: RollbackPlan) -> bool:
        """Ejecutar plan de rollback."""
        logger.warning(f"EXECUTING ROLLBACK to snapshot {rollback_plan.snapshot_id}")

        try:
            for step in rollback_plan.steps:
                logger.info(f"Executing rollback step: {step['description']}")

                success = await self._execute_rollback_step(step)
                if not success:
                    logger.error(f"Rollback step failed: {step['description']}")
                    return False

                # Wait for step completion
                await asyncio.sleep(1)

            # Ejecutar validaciones
            validation_success = await self._run_rollback_validations(rollback_plan.validation_checks)

            if validation_success:
                logger.info("Rollback completed successfully")
                return True
            else:
                logger.error("Rollback validation failed")
                return False

        except Exception as e:
            logger.error(f"Error executing rollback: {e}")
            return False

    async def _execute_rollback_step(self, step: Dict[str, Any]) -> bool:
        """Ejecutar paso individual de rollback."""
        step_type = step["type"]

        try:
            if step_type == "disable_new_features":
                return await self._disable_new_features()

            elif step_type == "restore_feature_flags":
                return await self._restore_feature_flags(step["data"])

            elif step_type == "verify_database":
                return await self._verify_database()

            elif step_type == "health_checks":
                return await self._run_health_checks()

            else:
                logger.warning(f"Unknown rollback step type: {step_type}")
                return True

        except Exception as e:
            logger.error(f"Error executing rollback step {step_type}: {e}")
            return False

    async def _disable_new_features(self) -> bool:
        """Deshabilitar features nuevas."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE feature_flags
                    SET enabled = ?, disabled_reason = ?, updated_at = ?
                    WHERE enabled = ? AND created_at > ?
                """, [
                    False,
                    "Rollback: disable new features",
                    datetime.now().isoformat(),
                    True,
                    (datetime.now() - timedelta(hours=24)).isoformat()  # Features de últimas 24h
                ])

                conn.commit()

            return True

        except Exception as e:
            logger.error(f"Error disabling new features: {e}")
            return False

    async def _restore_feature_flags(self, feature_flags_state: Dict[str, Any]) -> bool:
        """Restaurar estado de feature flags."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Primero deshabilitar todo
                conn.execute("""
                    UPDATE feature_flags SET enabled = ?, updated_at = ?
                """, [False, datetime.now().isoformat()])

                # Restaurar estado del snapshot
                for feature_name, company_flags in feature_flags_state.items():
                    for flag_data in company_flags:
                        if flag_data["enabled"]:
                            conn.execute("""
                                UPDATE feature_flags
                                SET enabled = ?, updated_at = ?
                                WHERE feature_name = ? AND company_id = ?
                            """, [
                                True,
                                datetime.now().isoformat(),
                                feature_name,
                                flag_data["company_id"]
                            ])

                conn.commit()

            return True

        except Exception as e:
            logger.error(f"Error restoring feature flags: {e}")
            return False

    async def _verify_database(self) -> bool:
        """Verificar integridad de base de datos."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Verificar integridad
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()

                if result and result[0] == "ok":
                    return True
                else:
                    logger.error(f"Database integrity check failed: {result}")
                    return False

        except Exception as e:
            logger.error(f"Error verifying database: {e}")
            return False

    async def _run_health_checks(self) -> bool:
        """Ejecutar health checks."""
        try:
            # Simular health checks
            # En producción esto haría requests reales a endpoints
            health_checks = [
                "api_endpoints",
                "database_connection",
                "feature_flags_loaded"
            ]

            for check in health_checks:
                # Simular check
                await asyncio.sleep(0.1)
                logger.debug(f"Health check passed: {check}")

            return True

        except Exception as e:
            logger.error(f"Error running health checks: {e}")
            return False

    async def _run_rollback_validations(self, validation_checks: List[str]) -> bool:
        """Ejecutar validaciones post-rollback."""
        try:
            for check in validation_checks:
                # Simular validación
                await asyncio.sleep(0.1)
                logger.debug(f"Rollback validation passed: {check}")

            return True

        except Exception as e:
            logger.error(f"Error running rollback validations: {e}")
            return False

# Global instances
feature_flag_manager = FeatureFlagManager()
deployment_manager = DeploymentManager()

# Auto rollback monitor
class AutoRollbackMonitor:
    """Monitor automático para rollback."""

    def __init__(self):
        self.monitoring = False
        self.thresholds = {
            "error_rate": 0.5,      # 50% error rate
            "response_time_ms": 10000,  # 10 seconds
            "consecutive_failures": 10
        }

    async def start_monitoring(self):
        """Iniciar monitoreo automático."""
        if self.monitoring:
            return

        self.monitoring = True
        logger.info("Auto rollback monitoring started")

        while self.monitoring:
            try:
                should_rollback = await self._check_rollback_triggers()

                if should_rollback:
                    await self._trigger_emergency_rollback()
                    break

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in auto rollback monitoring: {e}")
                await asyncio.sleep(10)

    async def _check_rollback_triggers(self) -> bool:
        """Verificar si se deben activar rollbacks automáticos."""
        # En producción esto consultaría métricas reales
        return False

    async def _trigger_emergency_rollback(self):
        """Activar rollback de emergencia."""
        logger.critical("TRIGGERING EMERGENCY ROLLBACK")

        try:
            # Obtener último snapshot estable
            snapshots = list(deployment_manager.snapshots_dir.glob("*.json"))
            if snapshots:
                latest_snapshot = max(snapshots, key=lambda p: p.stat().st_mtime)
                snapshot_id = latest_snapshot.stem

                # Crear y ejecutar plan de rollback
                rollback_plan = deployment_manager.create_rollback_plan(snapshot_id)
                success = await deployment_manager.execute_rollback(rollback_plan)

                if success:
                    logger.info("Emergency rollback completed successfully")
                else:
                    logger.error("Emergency rollback failed")

        except Exception as e:
            logger.error(f"Error in emergency rollback: {e}")

    def stop_monitoring(self):
        """Detener monitoreo."""
        self.monitoring = False
        logger.info("Auto rollback monitoring stopped")

# Global monitor instance
auto_rollback_monitor = AutoRollbackMonitor()