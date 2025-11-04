"""
Sistema de Observabilidad - Mitigación de riesgos de monitoreo

Sistema completo de logs, métricas, y alertas para producción.
"""

import logging
import time
import json
import sqlite3
import asyncio
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque

# Configuración de logging estructurado
class StructuredFormatter(logging.Formatter):
    """Formatter para logs estructurados."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Agregar contexto si existe
        if hasattr(record, 'automation_context'):
            log_entry["automation_context"] = record.automation_context

        if hasattr(record, 'performance_metrics'):
            log_entry["performance_metrics"] = record.performance_metrics

        if hasattr(record, 'user_context'):
            log_entry["user_context"] = record.user_context

        return json.dumps(log_entry)

class MetricType(Enum):
    """Tipos de métricas."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class Metric:
    """Métrica del sistema."""
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str]
    timestamp: datetime

class MetricsCollector:
    """Recolector de métricas del sistema."""

    def __init__(self, db_path: str = "expenses.db"):
        self.db_path = db_path
        self.metrics_buffer: deque = deque(maxlen=10000)
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def increment_counter(self, name: str, value: float = 1, labels: Dict[str, str] = None):
        """Incrementar contador."""
        with self.lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self.counters[key] += value

            metric = Metric(name, MetricType.COUNTER, self.counters[key], labels or {}, datetime.now())
            self.metrics_buffer.append(metric)

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Establecer gauge."""
        with self.lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self.gauges[key] = value

            metric = Metric(name, MetricType.GAUGE, value, labels or {}, datetime.now())
            self.metrics_buffer.append(metric)

    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Registrar valor en histograma."""
        with self.lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self.histograms[key].append(value)

            # Mantener solo los últimos 1000 valores
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]

            metric = Metric(name, MetricType.HISTOGRAM, value, labels or {}, datetime.now())
            self.metrics_buffer.append(metric)

    def time_operation(self, name: str, labels: Dict[str, str] = None):
        """Context manager para medir tiempo de operación."""
        return TimerContext(self, name, labels)

    def get_metric_summary(self) -> Dict[str, Any]:
        """Obtener resumen de métricas."""
        with self.lock:
            summary = {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": {},
                "timers": {},
                "timestamp": datetime.now().isoformat()
            }

            # Calcular estadísticas de histogramas
            for key, values in self.histograms.items():
                if values:
                    summary["histograms"][key] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "p95": self._percentile(values, 95),
                        "p99": self._percentile(values, 99)
                    }

            # Calcular estadísticas de timers
            for key, values in self.timers.items():
                if values:
                    summary["timers"][key] = {
                        "count": len(values),
                        "min_ms": min(values),
                        "max_ms": max(values),
                        "avg_ms": sum(values) / len(values),
                        "p95_ms": self._percentile(values, 95),
                        "p99_ms": self._percentile(values, 99)
                    }

            return summary

    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calcular percentil."""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    async def persist_metrics(self):
        """Persistir métricas en base de datos."""
        if not self.metrics_buffer:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Crear tabla si no existe
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS automation_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        type TEXT NOT NULL,
                        value REAL NOT NULL,
                        labels TEXT,
                        timestamp TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Crear índice para queries eficientes
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_name_timestamp
                    ON automation_metrics(name, timestamp)
                """)

                # Insertar métricas en batch
                metrics_to_insert = []
                with self.lock:
                    while self.metrics_buffer and len(metrics_to_insert) < 500:
                        metric = self.metrics_buffer.popleft()
                        metrics_to_insert.append((
                            metric.name,
                            metric.type.value,
                            metric.value,
                            json.dumps(metric.labels),
                            metric.timestamp.isoformat()
                        ))

                if metrics_to_insert:
                    conn.executemany("""
                        INSERT INTO automation_metrics (name, type, value, labels, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, metrics_to_insert)

                # Limpiar métricas antiguas (más de 30 días)
                cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
                conn.execute("""
                    DELETE FROM automation_metrics
                    WHERE timestamp < ?
                """, [cutoff_date])

                conn.commit()

        except Exception as e:
            logging.error(f"Error persisting metrics: {e}")

class TimerContext:
    """Context manager para medir tiempo."""

    def __init__(self, collector: MetricsCollector, name: str, labels: Dict[str, str] = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000

            with self.collector.lock:
                key = f"{self.name}:{json.dumps(self.labels or {}, sort_keys=True)}"
                self.collector.timers[key].append(duration_ms)

                # Mantener solo los últimos 1000 valores
                if len(self.collector.timers[key]) > 1000:
                    self.collector.timers[key] = self.collector.timers[key][-1000:]

                metric = Metric(self.name, MetricType.TIMER, duration_ms, self.labels or {}, datetime.now())
                self.collector.metrics_buffer.append(metric)

class AlertManager:
    """Gestor de alertas del sistema."""

    def __init__(self):
        self.alert_rules: List[AlertRule] = []
        self.alert_history: deque = deque(maxlen=1000)
        self.notification_handlers: List[Callable] = []

    def add_alert_rule(self, rule: 'AlertRule'):
        """Agregar regla de alerta."""
        self.alert_rules.append(rule)

    def add_notification_handler(self, handler: Callable):
        """Agregar manejador de notificaciones."""
        self.notification_handlers.append(handler)

    async def check_alerts(self, metrics_summary: Dict[str, Any]):
        """Verificar reglas de alerta."""
        alerts_triggered = []

        for rule in self.alert_rules:
            if rule.should_trigger(metrics_summary):
                alert = Alert(
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=rule.generate_message(metrics_summary),
                    metrics=rule.extract_relevant_metrics(metrics_summary),
                    timestamp=datetime.now()
                )

                alerts_triggered.append(alert)
                self.alert_history.append(alert)

        # Enviar notificaciones
        for alert in alerts_triggered:
            await self._send_notifications(alert)

        return alerts_triggered

    async def _send_notifications(self, alert: 'Alert'):
        """Enviar notificaciones de alerta."""
        for handler in self.notification_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logging.error(f"Error sending alert notification: {e}")

@dataclass
class Alert:
    """Alerta del sistema."""
    rule_name: str
    severity: str
    message: str
    metrics: Dict[str, Any]
    timestamp: datetime

class AlertRule:
    """Regla de alerta."""

    def __init__(self, name: str, severity: str, condition: Callable, message_template: str):
        self.name = name
        self.severity = severity  # "critical", "warning", "info"
        self.condition = condition
        self.message_template = message_template
        self.last_triggered = None
        self.cooldown_minutes = 10  # Evitar spam

    def should_trigger(self, metrics_summary: Dict[str, Any]) -> bool:
        """Verificar si la regla debe dispararse."""
        # Verificar cooldown
        if self.last_triggered:
            if datetime.now() - self.last_triggered < timedelta(minutes=self.cooldown_minutes):
                return False

        # Verificar condición
        if self.condition(metrics_summary):
            self.last_triggered = datetime.now()
            return True

        return False

    def generate_message(self, metrics_summary: Dict[str, Any]) -> str:
        """Generar mensaje de alerta."""
        return self.message_template.format(**metrics_summary)

    def extract_relevant_metrics(self, metrics_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Extraer métricas relevantes para la alerta."""
        return metrics_summary

class SystemObserver:
    """Observador principal del sistema."""

    def __init__(self, db_path: str = "expenses.db"):
        self.metrics_collector = MetricsCollector(db_path)
        self.alert_manager = AlertManager()
        self.logger = self._setup_structured_logging()
        self.system_stats_task = None
        self.metrics_persistence_task = None

        # Configurar alertas predeterminadas
        self._setup_default_alerts()

    def _setup_structured_logging(self) -> logging.Logger:
        """Configurar logging estructurado."""
        logger = logging.getLogger("automation_system")
        logger.setLevel(logging.INFO)

        # Handler para archivo con formato estructurado
        file_handler = logging.FileHandler("logs/automation_structured.log")
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)

        # Handler para consola con formato legible
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(console_handler)

        return logger

    def _setup_default_alerts(self):
        """Configurar alertas predeterminadas."""
        # Alta tasa de errores
        self.alert_manager.add_alert_rule(AlertRule(
            name="high_error_rate",
            severity="critical",
            condition=lambda m: self._get_error_rate(m) > 0.2,
            message_template="High error rate detected: {error_rate:.2%}"
        ))

        # Queue muy grande
        self.alert_manager.add_alert_rule(AlertRule(
            name="large_job_queue",
            severity="warning",
            condition=lambda m: m.get("gauges", {}).get("job_queue_size", 0) > 50,
            message_template="Job queue is large: {job_queue_size} pending jobs"
        ))

        # Tiempo de respuesta alto
        self.alert_manager.add_alert_rule(AlertRule(
            name="slow_api_response",
            severity="warning",
            condition=lambda m: self._get_avg_response_time(m) > 2000,
            message_template="Slow API response times: {avg_response_time_ms:.0f}ms"
        ))

        # Uso alto de CPU
        self.alert_manager.add_alert_rule(AlertRule(
            name="high_cpu_usage",
            severity="warning",
            condition=lambda m: m.get("gauges", {}).get("system_cpu_percent", 0) > 80,
            message_template="High CPU usage: {system_cpu_percent:.1f}%"
        ))

    def _get_error_rate(self, metrics: Dict[str, Any]) -> float:
        """Calcular tasa de errores."""
        counters = metrics.get("counters", {})
        total_requests = sum(v for k, v in counters.items() if "api_request" in k)
        error_requests = sum(v for k, v in counters.items() if "api_error" in k)

        if total_requests == 0:
            return 0
        return error_requests / total_requests

    def _get_avg_response_time(self, metrics: Dict[str, Any]) -> float:
        """Obtener tiempo promedio de respuesta."""
        timers = metrics.get("timers", {})
        api_timer = timers.get("api_request_duration", {})
        return api_timer.get("avg_ms", 0)

    async def start_monitoring(self):
        """Iniciar monitoreo del sistema."""
        self.logger.info("Starting system monitoring")

        # Tarea para recolectar estadísticas del sistema
        self.system_stats_task = asyncio.create_task(self._collect_system_stats())

        # Tarea para persistir métricas
        self.metrics_persistence_task = asyncio.create_task(self._metrics_persistence_loop())

        # Tarea para verificar alertas
        asyncio.create_task(self._alert_checking_loop())

    async def stop_monitoring(self):
        """Detener monitoreo del sistema."""
        self.logger.info("Stopping system monitoring")

        if self.system_stats_task:
            self.system_stats_task.cancel()

        if self.metrics_persistence_task:
            self.metrics_persistence_task.cancel()

    async def _collect_system_stats(self):
        """Recolectar estadísticas del sistema."""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics_collector.set_gauge("system_cpu_percent", cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                self.metrics_collector.set_gauge("system_memory_percent", memory.percent)
                self.metrics_collector.set_gauge("system_memory_available_mb", memory.available / 1024 / 1024)

                # Disk usage
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                self.metrics_collector.set_gauge("system_disk_percent", disk_percent)

                # Network stats
                network = psutil.net_io_counters()
                self.metrics_collector.increment_counter("system_bytes_sent", network.bytes_sent)
                self.metrics_collector.increment_counter("system_bytes_recv", network.bytes_recv)

            except Exception as e:
                self.logger.error(f"Error collecting system stats: {e}")

            await asyncio.sleep(60)  # Cada minuto

    async def _metrics_persistence_loop(self):
        """Loop para persistir métricas."""
        while True:
            try:
                await self.metrics_collector.persist_metrics()
                await asyncio.sleep(30)  # Cada 30 segundos
            except Exception as e:
                self.logger.error(f"Error in metrics persistence: {e}")
                await asyncio.sleep(10)

    async def _alert_checking_loop(self):
        """Loop para verificar alertas."""
        while True:
            try:
                metrics_summary = self.metrics_collector.get_metric_summary()
                alerts = await self.alert_manager.check_alerts(metrics_summary)

                if alerts:
                    self.logger.warning(f"Triggered {len(alerts)} alerts")

                await asyncio.sleep(60)  # Cada minuto
            except Exception as e:
                self.logger.error(f"Error checking alerts: {e}")
                await asyncio.sleep(10)

    def log_automation_event(self, event_type: str, job_id: int, data: Dict[str, Any] = None):
        """Log evento de automatización."""
        self.logger.info(
            f"Automation event: {event_type}",
            extra={
                "automation_context": {
                    "event_type": event_type,
                    "job_id": job_id,
                    "data": data or {}
                }
            }
        )

        # Incrementar contador de eventos
        self.metrics_collector.increment_counter(
            "automation_events",
            labels={"event_type": event_type}
        )

    def log_performance_metric(self, operation: str, duration_ms: float, success: bool):
        """Log métrica de performance."""
        self.logger.info(
            f"Performance metric: {operation}",
            extra={
                "performance_metrics": {
                    "operation": operation,
                    "duration_ms": duration_ms,
                    "success": success
                }
            }
        )

        # Registrar en histograma
        self.metrics_collector.record_histogram(
            "operation_duration_ms",
            duration_ms,
            labels={"operation": operation, "success": str(success)}
        )

# Global instance
system_observer = SystemObserver()

# Decorador para instrumentar funciones
def instrument_function(operation_name: str):
    """Decorador para instrumentar funciones automáticamente."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                system_observer.log_performance_metric(operation_name, duration_ms, success)

                if error:
                    system_observer.logger.error(
                        f"Function {func.__name__} failed: {error}",
                        extra={
                            "automation_context": {
                                "function": func.__name__,
                                "operation": operation_name,
                                "error": error
                            }
                        }
                    )

        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                system_observer.log_performance_metric(operation_name, duration_ms, success)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator