"""
Multi-Tenancy Scaling - Mitigación de riesgos de escalabilidad

Arquitectura escalable multi-tenant con aislamiento y límites.
"""

import asyncio
import json
import sqlite3
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import threading
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class TenantTier(Enum):
    """Tiers de tenants con diferentes límites."""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class ResourceType(Enum):
    """Tipos de recursos a limitar."""
    API_CALLS_PER_MINUTE = "api_calls_per_minute"
    CONCURRENT_JOBS = "concurrent_jobs"
    STORAGE_MB = "storage_mb"
    AUTOMATION_JOBS_PER_DAY = "automation_jobs_per_day"
    WEBHOOK_CALLS_PER_HOUR = "webhook_calls_per_hour"

@dataclass
class TenantLimits:
    """Límites por tenant."""
    tenant_id: str
    tier: TenantTier
    api_calls_per_minute: int
    concurrent_jobs: int
    storage_mb: int
    automation_jobs_per_day: int
    webhook_calls_per_hour: int
    custom_limits: Dict[str, int]

@dataclass
class TenantUsage:
    """Uso actual de recursos por tenant."""
    tenant_id: str
    api_calls_current_minute: int
    concurrent_jobs_active: int
    storage_used_mb: float
    automation_jobs_today: int
    webhook_calls_current_hour: int
    last_updated: datetime

class TenantResourceManager:
    """Gestor de recursos multi-tenant."""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path
        self.tenant_limits: Dict[str, TenantLimits] = {}
        self.tenant_usage: Dict[str, TenantUsage] = {}
        self.usage_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.lock = threading.Lock()

        # Límites por defecto por tier
        self.default_limits = {
            TenantTier.FREE: TenantLimits(
                tenant_id="", tier=TenantTier.FREE,
                api_calls_per_minute=100,
                concurrent_jobs=2,
                storage_mb=100,
                automation_jobs_per_day=50,
                webhook_calls_per_hour=20,
                custom_limits={}
            ),
            TenantTier.BASIC: TenantLimits(
                tenant_id="", tier=TenantTier.BASIC,
                api_calls_per_minute=500,
                concurrent_jobs=5,
                storage_mb=1000,
                automation_jobs_per_day=200,
                webhook_calls_per_hour=100,
                custom_limits={}
            ),
            TenantTier.PROFESSIONAL: TenantLimits(
                tenant_id="", tier=TenantTier.PROFESSIONAL,
                api_calls_per_minute=2000,
                concurrent_jobs=20,
                storage_mb=5000,
                automation_jobs_per_day=1000,
                webhook_calls_per_hour=500,
                custom_limits={}
            ),
            TenantTier.ENTERPRISE: TenantLimits(
                tenant_id="", tier=TenantTier.ENTERPRISE,
                api_calls_per_minute=10000,
                concurrent_jobs=100,
                storage_mb=50000,
                automation_jobs_per_day=10000,
                webhook_calls_per_hour=2000,
                custom_limits={}
            )
        }

    def initialize_tenant(self, tenant_id: str, tier: TenantTier = TenantTier.FREE) -> bool:
        """Inicializar tenant con límites."""
        try:
            # Crear límites basados en tier
            limits = TenantLimits(
                tenant_id=tenant_id,
                tier=tier,
                **{k: v for k, v in asdict(self.default_limits[tier]).items()
                   if k not in ['tenant_id', 'tier']}
            )

            # Inicializar uso
            usage = TenantUsage(
                tenant_id=tenant_id,
                api_calls_current_minute=0,
                concurrent_jobs_active=0,
                storage_used_mb=0.0,
                automation_jobs_today=0,
                webhook_calls_current_hour=0,
                last_updated=datetime.now()
            )

            with self.lock:
                self.tenant_limits[tenant_id] = limits
                self.tenant_usage[tenant_id] = usage

            # Persistir en DB
            self._persist_tenant_config(tenant_id, limits)

            logger.info(f"Tenant {tenant_id} initialized with tier {tier.value}")
            return True

        except Exception as e:
            logger.error(f"Error initializing tenant {tenant_id}: {e}")
            return False

    def _persist_tenant_config(self, tenant_id: str, limits: TenantLimits):
        """Persistir configuración de tenant."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tenant_config (
                        tenant_id TEXT PRIMARY KEY,
                        tier TEXT NOT NULL,
                        api_calls_per_minute INTEGER,
                        concurrent_jobs INTEGER,
                        storage_mb INTEGER,
                        automation_jobs_per_day INTEGER,
                        webhook_calls_per_hour INTEGER,
                        custom_limits TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.execute("""
                    INSERT OR REPLACE INTO tenant_config (
                        tenant_id, tier, api_calls_per_minute, concurrent_jobs,
                        storage_mb, automation_jobs_per_day, webhook_calls_per_hour,
                        custom_limits, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    tenant_id, limits.tier.value,
                    limits.api_calls_per_minute, limits.concurrent_jobs,
                    limits.storage_mb, limits.automation_jobs_per_day,
                    limits.webhook_calls_per_hour,
                    json.dumps(limits.custom_limits),
                    datetime.now().isoformat()
                ])

                conn.commit()

        except Exception as e:
            logger.error(f"Error persisting tenant config: {e}")

    async def check_resource_limit(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        requested_amount: int = 1
    ) -> bool:
        """Verificar si tenant puede usar recursos."""
        if tenant_id not in self.tenant_limits:
            logger.warning(f"Tenant {tenant_id} not found, initializing with FREE tier")
            self.initialize_tenant(tenant_id, TenantTier.FREE)

        limits = self.tenant_limits[tenant_id]
        usage = self.tenant_usage.get(tenant_id)

        if not usage:
            logger.error(f"Usage data not found for tenant {tenant_id}")
            return False

        # Verificar límite específico
        if resource_type == ResourceType.API_CALLS_PER_MINUTE:
            return usage.api_calls_current_minute + requested_amount <= limits.api_calls_per_minute

        elif resource_type == ResourceType.CONCURRENT_JOBS:
            return usage.concurrent_jobs_active + requested_amount <= limits.concurrent_jobs

        elif resource_type == ResourceType.STORAGE_MB:
            return usage.storage_used_mb + requested_amount <= limits.storage_mb

        elif resource_type == ResourceType.AUTOMATION_JOBS_PER_DAY:
            return usage.automation_jobs_today + requested_amount <= limits.automation_jobs_per_day

        elif resource_type == ResourceType.WEBHOOK_CALLS_PER_HOUR:
            return usage.webhook_calls_current_hour + requested_amount <= limits.webhook_calls_per_hour

        return False

    async def consume_resource(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int = 1
    ) -> bool:
        """Consumir recursos si están disponibles."""
        # Verificar límite
        if not await self.check_resource_limit(tenant_id, resource_type, amount):
            logger.warning(f"Resource limit exceeded for tenant {tenant_id}: {resource_type.value}")
            return False

        # Consumir recurso
        with self.lock:
            usage = self.tenant_usage[tenant_id]

            if resource_type == ResourceType.API_CALLS_PER_MINUTE:
                usage.api_calls_current_minute += amount

            elif resource_type == ResourceType.CONCURRENT_JOBS:
                usage.concurrent_jobs_active += amount

            elif resource_type == ResourceType.STORAGE_MB:
                usage.storage_used_mb += amount

            elif resource_type == ResourceType.AUTOMATION_JOBS_PER_DAY:
                usage.automation_jobs_today += amount

            elif resource_type == ResourceType.WEBHOOK_CALLS_PER_HOUR:
                usage.webhook_calls_current_hour += amount

            usage.last_updated = datetime.now()

            # Registrar uso para métricas
            self.usage_windows[tenant_id].append({
                "timestamp": datetime.now().isoformat(),
                "resource_type": resource_type.value,
                "amount": amount
            })

        return True

    async def release_resource(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int = 1
    ):
        """Liberar recursos (ej. concurrent jobs)."""
        with self.lock:
            if tenant_id in self.tenant_usage:
                usage = self.tenant_usage[tenant_id]

                if resource_type == ResourceType.CONCURRENT_JOBS:
                    usage.concurrent_jobs_active = max(0, usage.concurrent_jobs_active - amount)

                elif resource_type == ResourceType.STORAGE_MB:
                    usage.storage_used_mb = max(0, usage.storage_used_mb - amount)

                usage.last_updated = datetime.now()

    async def reset_time_based_counters(self):
        """Reset contadores basados en tiempo."""
        current_time = datetime.now()

        with self.lock:
            for tenant_id, usage in self.tenant_usage.items():
                # Reset minute-based counters
                if current_time.minute != usage.last_updated.minute:
                    usage.api_calls_current_minute = 0

                # Reset hour-based counters
                if current_time.hour != usage.last_updated.hour:
                    usage.webhook_calls_current_hour = 0

                # Reset day-based counters
                if current_time.date() != usage.last_updated.date():
                    usage.automation_jobs_today = 0

    def get_tenant_usage_stats(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Obtener estadísticas de uso de tenant."""
        if tenant_id not in self.tenant_limits or tenant_id not in self.tenant_usage:
            return None

        limits = self.tenant_limits[tenant_id]
        usage = self.tenant_usage[tenant_id]

        return {
            "tenant_id": tenant_id,
            "tier": limits.tier.value,
            "limits": asdict(limits),
            "current_usage": asdict(usage),
            "utilization": {
                "api_calls": usage.api_calls_current_minute / limits.api_calls_per_minute,
                "concurrent_jobs": usage.concurrent_jobs_active / limits.concurrent_jobs,
                "storage": usage.storage_used_mb / limits.storage_mb,
                "automation_jobs": usage.automation_jobs_today / limits.automation_jobs_per_day,
                "webhook_calls": usage.webhook_calls_current_hour / limits.webhook_calls_per_hour
            }
        }

    def get_all_tenants_summary(self) -> Dict[str, Any]:
        """Obtener resumen de todos los tenants."""
        summary = {
            "total_tenants": len(self.tenant_limits),
            "tenants_by_tier": defaultdict(int),
            "resource_utilization": defaultdict(list),
            "high_usage_tenants": []
        }

        for tenant_id in self.tenant_limits.keys():
            stats = self.get_tenant_usage_stats(tenant_id)
            if stats:
                # Contar por tier
                summary["tenants_by_tier"][stats["tier"]] += 1

                # Recopilar utilización
                for resource, utilization in stats["utilization"].items():
                    summary["resource_utilization"][resource].append(utilization)

                # Identificar tenants con alto uso
                avg_utilization = sum(stats["utilization"].values()) / len(stats["utilization"])
                if avg_utilization > 0.8:  # 80% de utilización promedio
                    summary["high_usage_tenants"].append({
                        "tenant_id": tenant_id,
                        "tier": stats["tier"],
                        "avg_utilization": avg_utilization
                    })

        # Calcular promedios
        for resource, utilizations in summary["resource_utilization"].items():
            if utilizations:
                summary["resource_utilization"][resource] = {
                    "avg": sum(utilizations) / len(utilizations),
                    "max": max(utilizations),
                    "count": len(utilizations)
                }

        return dict(summary)

class TenantIsolationManager:
    """Gestor de aislamiento entre tenants."""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path
        self.tenant_connections: Dict[str, Set[str]] = defaultdict(set)
        self.isolation_policies: Dict[str, Dict[str, Any]] = {}

    def configure_tenant_isolation(
        self,
        tenant_id: str,
        isolation_level: str = "standard",
        custom_policies: Dict[str, Any] = None
    ):
        """Configurar aislamiento de tenant."""
        policies = {
            "data_isolation": True,
            "network_isolation": isolation_level in ["high", "enterprise"],
            "resource_isolation": True,
            "logging_isolation": isolation_level in ["high", "enterprise"],
            "cache_isolation": isolation_level == "enterprise",
            "custom": custom_policies or {}
        }

        self.isolation_policies[tenant_id] = policies
        logger.info(f"Isolation configured for tenant {tenant_id}: {isolation_level}")

    @asynccontextmanager
    async def tenant_context(self, tenant_id: str, operation_id: str = None):
        """Context manager para operaciones aisladas por tenant."""
        operation_id = operation_id or f"op_{int(time.time())}"

        try:
            # Registrar conexión activa
            self.tenant_connections[tenant_id].add(operation_id)

            # Aplicar políticas de aislamiento
            await self._apply_isolation_policies(tenant_id)

            yield tenant_id

        finally:
            # Limpiar conexión
            if operation_id in self.tenant_connections[tenant_id]:
                self.tenant_connections[tenant_id].remove(operation_id)

            # Limpiar recursos de tenant si no hay conexiones activas
            if not self.tenant_connections[tenant_id]:
                await self._cleanup_tenant_resources(tenant_id)

    async def _apply_isolation_policies(self, tenant_id: str):
        """Aplicar políticas de aislamiento."""
        policies = self.isolation_policies.get(tenant_id, {})

        # Configurar aislamiento de datos (ej. filtros de DB)
        if policies.get("data_isolation"):
            # En queries reales, esto agregaría filtros WHERE tenant_id = ?
            pass

        # Configurar aislamiento de recursos
        if policies.get("resource_isolation"):
            # Aplicar límites de recursos específicos
            pass

    async def _cleanup_tenant_resources(self, tenant_id: str):
        """Limpiar recursos cuando tenant no tiene conexiones activas."""
        # Cache cleanup, connection pool cleanup, etc.
        logger.debug(f"Cleaning up resources for inactive tenant {tenant_id}")

    def get_active_tenants(self) -> List[str]:
        """Obtener lista de tenants activos."""
        return [tid for tid, connections in self.tenant_connections.items() if connections]

class TenantDataManager:
    """Gestor de datos aislados por tenant."""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path

    async def get_tenant_data(
        self,
        tenant_id: str,
        table: str,
        filters: Dict[str, Any] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Obtener datos filtrados por tenant."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Construir query con filtro de tenant
                where_clause = "WHERE company_id = ?"
                params = [tenant_id]

                if filters:
                    for field, value in filters.items():
                        where_clause += f" AND {field} = ?"
                        params.append(value)

                query = f"""
                    SELECT * FROM {table}
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                params.append(limit)

                cursor = conn.execute(query, params)
                columns = [description[0] for description in cursor.description]

                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

                return results

        except Exception as e:
            logger.error(f"Error getting tenant data for {tenant_id}: {e}")
            return []

    async def create_tenant_data(
        self,
        tenant_id: str,
        table: str,
        data: Dict[str, Any]
    ) -> Optional[int]:
        """Crear datos con aislamiento de tenant."""
        try:
            # Asegurar que company_id esté establecido
            data["company_id"] = tenant_id
            data["created_at"] = datetime.now().isoformat()
            data["updated_at"] = datetime.now().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                # Construir INSERT dinámico
                fields = list(data.keys())
                placeholders = ",".join("?" * len(fields))
                values = list(data.values())

                query = f"INSERT INTO {table} ({','.join(fields)}) VALUES ({placeholders})"

                cursor = conn.execute(query, values)
                row_id = cursor.lastrowid
                conn.commit()

                return row_id

        except Exception as e:
            logger.error(f"Error creating tenant data for {tenant_id}: {e}")
            return None

    async def update_tenant_data(
        self,
        tenant_id: str,
        table: str,
        record_id: int,
        data: Dict[str, Any]
    ) -> bool:
        """Actualizar datos con verificación de tenant."""
        try:
            # Verificar que el record pertenece al tenant
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(f"""
                    SELECT company_id FROM {table} WHERE id = ?
                """, [record_id])

                result = cursor.fetchone()
                if not result or result[0] != tenant_id:
                    logger.warning(f"Tenant {tenant_id} attempted to update record {record_id} they don't own")
                    return False

                # Actualizar datos
                data["updated_at"] = datetime.now().isoformat()

                set_clause = ",".join(f"{field} = ?" for field in data.keys())
                values = list(data.values()) + [record_id]

                query = f"UPDATE {table} SET {set_clause} WHERE id = ?"
                conn.execute(query, values)
                conn.commit()

                return True

        except Exception as e:
            logger.error(f"Error updating tenant data for {tenant_id}: {e}")
            return False

    async def delete_tenant_data(
        self,
        tenant_id: str,
        table: str,
        record_id: int
    ) -> bool:
        """Eliminar datos con verificación de tenant."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Verificar ownership y eliminar
                cursor = conn.execute(f"""
                    DELETE FROM {table}
                    WHERE id = ? AND company_id = ?
                """, [record_id, tenant_id])

                rows_affected = cursor.rowcount
                conn.commit()

                return rows_affected > 0

        except Exception as e:
            logger.error(f"Error deleting tenant data for {tenant_id}: {e}")
            return False

# Global instances
tenant_resource_manager = TenantResourceManager()
tenant_isolation_manager = TenantIsolationManager()
tenant_data_manager = TenantDataManager()

# Background tasks
async def tenant_maintenance_task():
    """Tarea de mantenimiento para tenants."""
    while True:
        try:
            # Reset contadores basados en tiempo
            await tenant_resource_manager.reset_time_based_counters()

            # Limpiar conexiones inactivas
            active_tenants = tenant_isolation_manager.get_active_tenants()
            logger.debug(f"Active tenants: {len(active_tenants)}")

            await asyncio.sleep(60)  # Cada minuto

        except Exception as e:
            logger.error(f"Error in tenant maintenance: {e}")
            await asyncio.sleep(10)

# Decorador para operaciones multi-tenant
def tenant_isolated(operation_name: str = None):
    """Decorador para operaciones aisladas por tenant."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extraer tenant_id de argumentos
            tenant_id = kwargs.get("tenant_id") or kwargs.get("company_id")

            if not tenant_id and args:
                # Intentar encontrar tenant_id en primer argumento si es dict
                if isinstance(args[0], dict):
                    tenant_id = args[0].get("tenant_id") or args[0].get("company_id")

            if not tenant_id:
                raise ValueError("tenant_id required for isolated operation")

            # Ejecutar con contexto de tenant
            async with tenant_isolation_manager.tenant_context(tenant_id):
                return await func(*args, **kwargs)

        return wrapper
    return decorator