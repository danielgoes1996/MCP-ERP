"""
Sistema de Optimización de Performance para Transacciones Batch
Punto 12: Acciones de Gastos - Batch Performance Optimization

Este módulo proporciona:
- Optimización inteligente de tamaños de lote
- Pool de conexiones eficiente
- Paralelización controlada
- Monitoreo de performance en tiempo real
- Adaptive batching basado en carga del sistema
- Circuit breakers para prevenir sobrecarga
"""

from __future__ import annotations

import asyncio
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class BatchStrategy(Enum):
    """Estrategias de procesamiento por lotes"""
    FIXED_SIZE = "fixed_size"
    ADAPTIVE_SIZE = "adaptive_size"
    PARALLEL_BATCH = "parallel_batch"
    STREAMING = "streaming"
    PRIORITY_BASED = "priority_based"


class SystemLoad(Enum):
    """Niveles de carga del sistema"""
    LOW = "low"          # < 30% CPU, < 50% memoria
    MEDIUM = "medium"    # 30-70% CPU, 50-80% memoria
    HIGH = "high"        # 70-90% CPU, 80-95% memoria
    CRITICAL = "critical" # > 90% CPU, > 95% memoria


@dataclass
class BatchConfig:
    """Configuración de procesamiento por lotes"""
    base_batch_size: int = 100
    min_batch_size: int = 10
    max_batch_size: int = 1000
    max_parallel_batches: int = 5
    timeout_seconds: int = 300
    retry_attempts: int = 3
    adaptive_threshold: float = 0.8  # Umbral para ajuste adaptativo
    circuit_breaker_threshold: int = 5  # Fallos consecutivos para abrir circuito


@dataclass
class BatchMetrics:
    """Métricas de performance del lote"""
    batch_id: str
    batch_size: int
    execution_time_ms: int
    records_processed: int
    records_successful: int
    records_failed: int
    throughput_rps: float  # Records per second
    memory_usage_mb: float
    cpu_usage_percent: float
    database_connections: int
    errors: List[str]


@dataclass
class SystemMetrics:
    """Métricas del sistema"""
    cpu_percent: float
    memory_percent: float
    available_memory_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_mb: float
    active_connections: int
    load: SystemLoad
    timestamp: datetime


class BatchPerformanceOptimizer:
    """Optimizador de performance para operaciones batch"""

    def __init__(self, db_adapter, config: Optional[BatchConfig] = None):
        self.db = db_adapter
        self.config = config or BatchConfig()

        # Estado interno
        self.current_batch_size = self.config.base_batch_size
        self.performance_history: List[BatchMetrics] = []
        self.system_metrics_history: List[SystemMetrics] = []
        self.circuit_breaker_state = "closed"  # closed, open, half-open
        self.consecutive_failures = 0

        # Pool de workers
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_parallel_batches)

        # Locks para concurrencia
        self._metrics_lock = asyncio.Lock()
        self._adaptation_lock = asyncio.Lock()

    async def execute_batch_operation(
        self,
        operation_func: Callable,
        data: List[Any],
        strategy: BatchStrategy = BatchStrategy.ADAPTIVE_SIZE,
        priority: int = 5  # 1=highest, 10=lowest
    ) -> Tuple[bool, List[BatchMetrics]]:
        """Ejecuta operación por lotes optimizada"""

        if not data:
            return True, []

        # Verificar circuit breaker
        if self.circuit_breaker_state == "open":
            if not await self._should_attempt_recovery():
                raise RuntimeError("Circuit breaker is open - system overloaded")
            else:
                self.circuit_breaker_state = "half-open"

        # Obtener métricas del sistema
        system_metrics = await self._get_system_metrics()

        # Ajustar estrategia basada en carga del sistema
        strategy = self._adapt_strategy_to_load(strategy, system_metrics.load)

        # Dividir datos en lotes optimizados
        batches = await self._create_optimized_batches(data, strategy, system_metrics)

        batch_results = []
        overall_success = True

        try:
            if strategy == BatchStrategy.PARALLEL_BATCH and system_metrics.load in [SystemLoad.LOW, SystemLoad.MEDIUM]:
                # Procesamiento paralelo
                batch_results = await self._execute_parallel_batches(operation_func, batches, priority)
            else:
                # Procesamiento secuencial
                batch_results = await self._execute_sequential_batches(operation_func, batches, priority)

            # Analizar resultados
            overall_success = all(result.records_failed == 0 for result in batch_results)

            # Actualizar circuit breaker
            if overall_success:
                self.consecutive_failures = 0
                if self.circuit_breaker_state == "half-open":
                    self.circuit_breaker_state = "closed"
            else:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.config.circuit_breaker_threshold:
                    self.circuit_breaker_state = "open"

            # Adaptar configuración para futuras operaciones
            await self._adapt_batch_configuration(batch_results, system_metrics)

            return overall_success, batch_results

        except Exception as e:
            logger.error(f"Batch operation failed: {e}")
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.config.circuit_breaker_threshold:
                self.circuit_breaker_state = "open"
            raise

    async def get_performance_recommendations(
        self,
        operation_type: str,
        expected_record_count: int
    ) -> Dict[str, Any]:
        """Proporciona recomendaciones de performance"""

        system_metrics = await self._get_system_metrics()

        # Calcular tiempo estimado
        avg_throughput = self._calculate_average_throughput(operation_type)
        estimated_duration_seconds = expected_record_count / max(avg_throughput, 1)

        # Recomendar estrategia óptima
        recommended_strategy = self._recommend_strategy(expected_record_count, system_metrics)

        # Calcular tamaño de lote óptimo
        optimal_batch_size = await self._calculate_optimal_batch_size(
            expected_record_count,
            system_metrics,
            operation_type
        )

        return {
            "recommended_strategy": recommended_strategy.value,
            "optimal_batch_size": optimal_batch_size,
            "estimated_duration_seconds": int(estimated_duration_seconds),
            "estimated_batches": (expected_record_count // optimal_batch_size) + 1,
            "system_load": system_metrics.load.value,
            "memory_available_mb": system_metrics.available_memory_mb,
            "recommended_parallel_batches": min(
                self.config.max_parallel_batches,
                max(1, int(system_metrics.available_memory_mb / 100))  # 1 batch per 100MB available
            ),
            "warnings": self._generate_performance_warnings(system_metrics, expected_record_count)
        }

    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas en tiempo real"""

        system_metrics = await self._get_system_metrics()

        # Métricas de performance recientes
        recent_metrics = [m for m in self.performance_history
                         if (datetime.utcnow() - datetime.fromisoformat(m.batch_id.split('_')[1])).total_seconds() < 300]

        avg_throughput = sum(m.throughput_rps for m in recent_metrics) / max(len(recent_metrics), 1)
        avg_success_rate = sum(m.records_successful / max(m.records_processed, 1) for m in recent_metrics) / max(len(recent_metrics), 1)

        return {
            "system_metrics": {
                "cpu_percent": system_metrics.cpu_percent,
                "memory_percent": system_metrics.memory_percent,
                "load_level": system_metrics.load.value,
                "active_connections": system_metrics.active_connections
            },
            "batch_metrics": {
                "current_batch_size": self.current_batch_size,
                "average_throughput_rps": round(avg_throughput, 2),
                "average_success_rate": round(avg_success_rate * 100, 2),
                "circuit_breaker_state": self.circuit_breaker_state,
                "consecutive_failures": self.consecutive_failures
            },
            "performance_trends": {
                "batches_last_5min": len(recent_metrics),
                "total_records_processed_5min": sum(m.records_processed for m in recent_metrics),
                "average_execution_time_ms": sum(m.execution_time_ms for m in recent_metrics) / max(len(recent_metrics), 1)
            }
        }

    # Métodos privados de implementación

    async def _get_system_metrics(self) -> SystemMetrics:
        """Obtiene métricas actuales del sistema"""

        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            net_io = psutil.net_io_counters()

            # Determinar nivel de carga
            if cpu_percent > 90 or memory.percent > 95:
                load = SystemLoad.CRITICAL
            elif cpu_percent > 70 or memory.percent > 80:
                load = SystemLoad.HIGH
            elif cpu_percent > 30 or memory.percent > 50:
                load = SystemLoad.MEDIUM
            else:
                load = SystemLoad.LOW

            # Obtener conexiones de BD activas
            active_connections = await self._get_active_db_connections()

            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                available_memory_mb=memory.available / (1024 * 1024),
                disk_io_read_mb=disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
                disk_io_write_mb=disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
                network_io_mb=(net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024) if net_io else 0,
                active_connections=active_connections,
                load=load,
                timestamp=datetime.utcnow()
            )

            # Mantener histórico
            async with self._metrics_lock:
                self.system_metrics_history.append(metrics)
                # Mantener solo últimas 100 mediciones
                if len(self.system_metrics_history) > 100:
                    self.system_metrics_history = self.system_metrics_history[-100:]

            return metrics

        except Exception as e:
            logger.warning(f"Failed to get system metrics: {e}")
            # Valores por defecto conservadores
            return SystemMetrics(
                cpu_percent=50.0,
                memory_percent=50.0,
                available_memory_mb=1000.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_io_mb=0.0,
                active_connections=10,
                load=SystemLoad.MEDIUM,
                timestamp=datetime.utcnow()
            )

    async def _get_active_db_connections(self) -> int:
        """Obtiene número de conexiones activas a la BD"""
        try:
            result = await self.db.fetch_one(
                "SELECT count(*) as count FROM pg_stat_activity WHERE state = 'active'"
            )
            return result["count"] if result else 5
        except:
            return 5  # Valor por defecto

    def _adapt_strategy_to_load(self, strategy: BatchStrategy, load: SystemLoad) -> BatchStrategy:
        """Adapta la estrategia según la carga del sistema"""

        if load == SystemLoad.CRITICAL:
            # Bajo carga crítica, usar estrategia más conservadora
            return BatchStrategy.FIXED_SIZE
        elif load == SystemLoad.HIGH:
            # Carga alta, evitar paralelización
            if strategy == BatchStrategy.PARALLEL_BATCH:
                return BatchStrategy.ADAPTIVE_SIZE
        elif load == SystemLoad.LOW:
            # Carga baja, optimizar para velocidad
            if strategy == BatchStrategy.FIXED_SIZE:
                return BatchStrategy.PARALLEL_BATCH

        return strategy

    async def _create_optimized_batches(
        self,
        data: List[Any],
        strategy: BatchStrategy,
        system_metrics: SystemMetrics
    ) -> List[List[Any]]:
        """Crea lotes optimizados según la estrategia"""

        if strategy == BatchStrategy.FIXED_SIZE:
            batch_size = self.current_batch_size
        elif strategy == BatchStrategy.ADAPTIVE_SIZE:
            batch_size = await self._calculate_adaptive_batch_size(system_metrics)
        else:
            batch_size = await self._calculate_optimal_batch_size(len(data), system_metrics, "generic")

        # Ajustar según carga del sistema
        if system_metrics.load == SystemLoad.CRITICAL:
            batch_size = min(batch_size, self.config.min_batch_size)
        elif system_metrics.load == SystemLoad.HIGH:
            batch_size = int(batch_size * 0.7)

        # Asegurar límites
        batch_size = max(self.config.min_batch_size,
                        min(batch_size, self.config.max_batch_size))

        # Crear lotes
        batches = []
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batches.append(batch)

        logger.info(f"Created {len(batches)} batches with size {batch_size} "
                   f"for {len(data)} records (load: {system_metrics.load.value})")

        return batches

    async def _calculate_adaptive_batch_size(self, system_metrics: SystemMetrics) -> int:
        """Calcula tamaño de lote adaptativo"""

        base_size = self.current_batch_size

        # Ajustar según memoria disponible
        if system_metrics.available_memory_mb < 500:
            base_size = int(base_size * 0.5)
        elif system_metrics.available_memory_mb > 2000:
            base_size = int(base_size * 1.5)

        # Ajustar según CPU
        if system_metrics.cpu_percent > 80:
            base_size = int(base_size * 0.7)
        elif system_metrics.cpu_percent < 30:
            base_size = int(base_size * 1.3)

        # Ajustar según performance histórica
        if len(self.performance_history) > 5:
            recent_avg_throughput = sum(
                m.throughput_rps for m in self.performance_history[-5:]
            ) / 5

            if recent_avg_throughput < 10:  # Baja throughput
                base_size = max(base_size - 20, self.config.min_batch_size)
            elif recent_avg_throughput > 50:  # Alta throughput
                base_size = min(base_size + 20, self.config.max_batch_size)

        return max(self.config.min_batch_size,
                  min(base_size, self.config.max_batch_size))

    async def _calculate_optimal_batch_size(
        self,
        total_records: int,
        system_metrics: SystemMetrics,
        operation_type: str
    ) -> int:
        """Calcula el tamaño óptimo de lote"""

        # Tamaño base según tipo de operación
        base_sizes = {
            "update": 100,
            "insert": 200,
            "delete": 50,
            "select": 500,
            "generic": 100
        }

        base_size = base_sizes.get(operation_type, 100)

        # Factor de memoria disponible
        memory_factor = min(2.0, system_metrics.available_memory_mb / 1000)

        # Factor de carga del sistema
        load_factors = {
            SystemLoad.LOW: 1.5,
            SystemLoad.MEDIUM: 1.0,
            SystemLoad.HIGH: 0.7,
            SystemLoad.CRITICAL: 0.4
        }

        load_factor = load_factors[system_metrics.load]

        # Calcular tamaño óptimo
        optimal_size = int(base_size * memory_factor * load_factor)

        # Ajustar según el total de registros
        if total_records < optimal_size:
            optimal_size = total_records
        elif total_records < optimal_size * 2:
            # Para conjuntos pequeños, usar lotes más pequeños
            optimal_size = max(optimal_size // 2, self.config.min_batch_size)

        return max(self.config.min_batch_size,
                  min(optimal_size, self.config.max_batch_size))

    async def _execute_parallel_batches(
        self,
        operation_func: Callable,
        batches: List[List[Any]],
        priority: int
    ) -> List[BatchMetrics]:
        """Ejecuta lotes en paralelo"""

        semaphore = asyncio.Semaphore(self.config.max_parallel_batches)
        results = []

        async def process_batch_with_semaphore(batch_data: List[Any], batch_index: int):
            async with semaphore:
                return await self._execute_single_batch(
                    operation_func, batch_data, f"parallel_{batch_index}", priority
                )

        # Ejecutar lotes en paralelo
        tasks = [
            process_batch_with_semaphore(batch, i)
            for i, batch in enumerate(batches)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrar excepciones
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch execution failed: {result}")
                # Crear métrica de fallo
                valid_results.append(BatchMetrics(
                    batch_id=f"failed_{int(time.time())}",
                    batch_size=0,
                    execution_time_ms=0,
                    records_processed=0,
                    records_successful=0,
                    records_failed=1,
                    throughput_rps=0.0,
                    memory_usage_mb=0.0,
                    cpu_usage_percent=0.0,
                    database_connections=0,
                    errors=[str(result)]
                ))
            else:
                valid_results.append(result)

        return valid_results

    async def _execute_sequential_batches(
        self,
        operation_func: Callable,
        batches: List[List[Any]],
        priority: int
    ) -> List[BatchMetrics]:
        """Ejecuta lotes secuencialmente"""

        results = []

        for i, batch in enumerate(batches):
            try:
                result = await self._execute_single_batch(
                    operation_func, batch, f"sequential_{i}", priority
                )
                results.append(result)

                # Pausa adaptativa entre lotes
                await self._adaptive_pause_between_batches(result)

            except Exception as e:
                logger.error(f"Sequential batch {i} failed: {e}")
                results.append(BatchMetrics(
                    batch_id=f"failed_seq_{i}",
                    batch_size=len(batch),
                    execution_time_ms=0,
                    records_processed=len(batch),
                    records_successful=0,
                    records_failed=len(batch),
                    throughput_rps=0.0,
                    memory_usage_mb=0.0,
                    cpu_usage_percent=0.0,
                    database_connections=0,
                    errors=[str(e)]
                ))

        return results

    async def _execute_single_batch(
        self,
        operation_func: Callable,
        batch_data: List[Any],
        batch_id: str,
        priority: int
    ) -> BatchMetrics:
        """Ejecuta un lote individual con métricas"""

        start_time = time.time()
        start_memory = psutil.virtual_memory().used / (1024 * 1024)
        start_cpu = psutil.cpu_percent()

        try:
            # Ejecutar operación
            result = await operation_func(batch_data)

            # Extraer resultados
            if isinstance(result, dict):
                successful = result.get('successful', len(batch_data))
                failed = result.get('failed', 0)
            elif isinstance(result, bool):
                successful = len(batch_data) if result else 0
                failed = 0 if result else len(batch_data)
            else:
                successful = len(batch_data)
                failed = 0

            errors = []

        except Exception as e:
            successful = 0
            failed = len(batch_data)
            errors = [str(e)]

        # Calcular métricas
        end_time = time.time()
        execution_time_ms = int((end_time - start_time) * 1000)
        end_memory = psutil.virtual_memory().used / (1024 * 1024)
        end_cpu = psutil.cpu_percent()

        throughput_rps = successful / max((end_time - start_time), 0.001)

        metrics = BatchMetrics(
            batch_id=f"{batch_id}_{datetime.utcnow().isoformat()}",
            batch_size=len(batch_data),
            execution_time_ms=execution_time_ms,
            records_processed=len(batch_data),
            records_successful=successful,
            records_failed=failed,
            throughput_rps=throughput_rps,
            memory_usage_mb=end_memory - start_memory,
            cpu_usage_percent=end_cpu - start_cpu,
            database_connections=await self._get_active_db_connections(),
            errors=errors
        )

        # Almacenar métricas
        async with self._metrics_lock:
            self.performance_history.append(metrics)
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-1000:]

        return metrics

    async def _adaptive_pause_between_batches(self, last_batch_metrics: BatchMetrics):
        """Pausa adaptativa entre lotes para evitar sobrecarga"""

        base_pause = 0.1  # 100ms base

        # Aumentar pausa si hay alta carga
        system_metrics = await self._get_system_metrics()

        if system_metrics.load == SystemLoad.CRITICAL:
            pause = base_pause * 5
        elif system_metrics.load == SystemLoad.HIGH:
            pause = base_pause * 2
        elif last_batch_metrics.throughput_rps < 5:  # Performance muy baja
            pause = base_pause * 1.5
        else:
            pause = base_pause

        await asyncio.sleep(pause)

    async def _adapt_batch_configuration(
        self,
        batch_results: List[BatchMetrics],
        system_metrics: SystemMetrics
    ):
        """Adapta la configuración basada en resultados"""

        if not batch_results:
            return

        async with self._adaptation_lock:
            # Calcular métricas promedio
            avg_throughput = sum(m.throughput_rps for m in batch_results) / len(batch_results)
            avg_success_rate = sum(m.records_successful / max(m.records_processed, 1)
                                 for m in batch_results) / len(batch_results)

            # Adaptar tamaño de lote
            if avg_success_rate < 0.9:  # Baja tasa de éxito
                self.current_batch_size = max(
                    int(self.current_batch_size * 0.8),
                    self.config.min_batch_size
                )
            elif avg_throughput > 20 and avg_success_rate > 0.95:  # Alta performance
                self.current_batch_size = min(
                    int(self.current_batch_size * 1.1),
                    self.config.max_batch_size
                )

            logger.debug(f"Adapted batch size to {self.current_batch_size} "
                        f"(throughput: {avg_throughput:.2f}, success: {avg_success_rate:.2%})")

    async def _should_attempt_recovery(self) -> bool:
        """Determina si se debe intentar recuperación del circuit breaker"""

        # Esperar al menos 60 segundos antes de intentar recuperación
        if len(self.performance_history) == 0:
            return True

        last_failure_time = max(
            datetime.fromisoformat(m.batch_id.split('_')[1])
            for m in self.performance_history
            if m.records_failed > 0
        )

        return (datetime.utcnow() - last_failure_time).total_seconds() > 60

    def _calculate_average_throughput(self, operation_type: str) -> float:
        """Calcula throughput promedio para tipo de operación"""

        relevant_metrics = [
            m for m in self.performance_history[-20:]  # Últimas 20 operaciones
            if operation_type in m.batch_id or operation_type == "generic"
        ]

        if not relevant_metrics:
            return 10.0  # Valor por defecto conservador

        return sum(m.throughput_rps for m in relevant_metrics) / len(relevant_metrics)

    def _recommend_strategy(
        self,
        record_count: int,
        system_metrics: SystemMetrics
    ) -> BatchStrategy:
        """Recomienda la mejor estrategia para la operación"""

        if system_metrics.load in [SystemLoad.HIGH, SystemLoad.CRITICAL]:
            return BatchStrategy.FIXED_SIZE
        elif record_count < 100:
            return BatchStrategy.FIXED_SIZE
        elif record_count > 1000 and system_metrics.load == SystemLoad.LOW:
            return BatchStrategy.PARALLEL_BATCH
        else:
            return BatchStrategy.ADAPTIVE_SIZE

    def _generate_performance_warnings(
        self,
        system_metrics: SystemMetrics,
        record_count: int
    ) -> List[str]:
        """Genera advertencias de performance"""

        warnings = []

        if system_metrics.load == SystemLoad.CRITICAL:
            warnings.append("Sistema bajo carga crítica - considerese ejecutar más tarde")
        elif system_metrics.load == SystemLoad.HIGH:
            warnings.append("Sistema bajo carga alta - reducirse paralelización")

        if system_metrics.available_memory_mb < 200:
            warnings.append("Memoria disponible baja - lotes serán más pequeños")

        if record_count > 10000:
            warnings.append("Operación muy grande - considerese dividir en múltiples ejecuciones")

        if system_metrics.active_connections > 50:
            warnings.append("Alto número de conexiones BD - podría afectar performance")

        return warnings


# Singleton instance
batch_optimizer = BatchPerformanceOptimizer(None)  # Se inicializa con el adaptador de BD


# Helper functions para uso fácil

async def optimize_batch_operation(
    operation_func: Callable,
    data: List[Any],
    strategy: BatchStrategy = BatchStrategy.ADAPTIVE_SIZE
) -> Tuple[bool, List[BatchMetrics]]:
    """Helper para ejecutar operación batch optimizada"""
    return await batch_optimizer.execute_batch_operation(operation_func, data, strategy)


async def get_batch_recommendations(
    operation_type: str,
    record_count: int
) -> Dict[str, Any]:
    """Helper para obtener recomendaciones"""
    return await batch_optimizer.get_performance_recommendations(operation_type, record_count)