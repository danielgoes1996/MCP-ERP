#!/usr/bin/env python3
"""
Monitor de Salud del Sistema de Automatización

Monitorea métricas clave y alerta sobre problemas.
"""

import time
import json
import sqlite3
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class HealthMetric:
    """Métrica de salud del sistema."""
    name: str
    value: float
    threshold: float
    status: str  # OK, WARNING, CRITICAL
    message: str
    timestamp: datetime

@dataclass
class Alert:
    """Alerta del sistema."""
    level: str  # WARNING, CRITICAL
    message: str
    metrics: List[HealthMetric]
    timestamp: datetime

class AutomationHealthMonitor:
    """Monitor de salud del sistema de automatización."""

    def __init__(self, base_url: str = "http://localhost:8000", db_path: str = "expenses.db"):
        self.base_url = base_url
        self.db_path = db_path
        self.alerts_sent = []

    def check_system_health(self) -> Dict[str, Any]:
        """Verificar salud general del sistema."""
        logger.info("🔍 Verificando salud del sistema...")

        metrics = []
        alerts = []

        # 1. API Response Time
        api_metric = self._check_api_response_time()
        metrics.append(api_metric)
        if api_metric.status != "OK":
            alerts.append(Alert("WARNING", "API response time high", [api_metric], datetime.now()))

        # 2. Database Health
        db_metric = self._check_database_health()
        metrics.append(db_metric)
        if db_metric.status == "CRITICAL":
            alerts.append(Alert("CRITICAL", "Database connection issues", [db_metric], datetime.now()))

        # 3. Job Queue Status
        queue_metric = self._check_job_queue()
        metrics.append(queue_metric)
        if queue_metric.status != "OK":
            alerts.append(Alert("WARNING", "Job queue backed up", [queue_metric], datetime.now()))

        # 4. Error Rate
        error_metric = self._check_error_rate()
        metrics.append(error_metric)
        if error_metric.status == "CRITICAL":
            alerts.append(Alert("CRITICAL", "High error rate detected", [error_metric], datetime.now()))

        # 5. Service Availability
        service_metrics = self._check_service_availability()
        metrics.extend(service_metrics)

        # 6. Resource Usage
        resource_metrics = self._check_resource_usage()
        metrics.extend(resource_metrics)

        # 7. Feature Flag Health
        ff_metric = self._check_feature_flags()
        metrics.append(ff_metric)

        # Overall status
        critical_count = len([m for m in metrics if m.status == "CRITICAL"])
        warning_count = len([m for m in metrics if m.status == "WARNING"])

        overall_status = "CRITICAL" if critical_count > 0 else "WARNING" if warning_count > 0 else "OK"

        return {
            "overall_status": overall_status,
            "metrics": [self._metric_to_dict(m) for m in metrics],
            "alerts": [self._alert_to_dict(a) for a in alerts],
            "summary": {
                "total_metrics": len(metrics),
                "ok_count": len([m for m in metrics if m.status == "OK"]),
                "warning_count": warning_count,
                "critical_count": critical_count
            },
            "timestamp": datetime.now().isoformat()
        }

    def _check_api_response_time(self) -> HealthMetric:
        """Verificar tiempo de respuesta de API."""
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/health", timeout=10)
            response_time = (time.time() - start_time) * 1000

            if response.status_code != 200:
                return HealthMetric(
                    "api_response_time", response_time, 500,
                    "CRITICAL", f"API not responding: {response.status_code}",
                    datetime.now()
                )

            status = "OK" if response_time < 500 else "WARNING" if response_time < 2000 else "CRITICAL"
            message = f"API responding in {response_time:.0f}ms"

            return HealthMetric("api_response_time", response_time, 500, status, message, datetime.now())

        except Exception as e:
            return HealthMetric(
                "api_response_time", 0, 500,
                "CRITICAL", f"API unreachable: {e}",
                datetime.now()
            )

    def _check_database_health(self) -> HealthMetric:
        """Verificar salud de la base de datos."""
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                # Test basic query
                cursor = conn.execute("SELECT COUNT(*) FROM tickets")
                ticket_count = cursor.fetchone()[0]

                # Check recent activity
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tickets WHERE created_at > ?",
                    [(datetime.now() - timedelta(hours=24)).isoformat()]
                )
                recent_tickets = cursor.fetchone()[0]

                message = f"DB OK: {ticket_count} total tickets, {recent_tickets} in 24h"
                return HealthMetric("database_health", ticket_count, 0, "OK", message, datetime.now())

        except Exception as e:
            return HealthMetric(
                "database_health", 0, 0,
                "CRITICAL", f"Database error: {e}",
                datetime.now()
            )

    def _check_job_queue(self) -> HealthMetric:
        """Verificar estado de la cola de jobs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check for stuck jobs
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM automation_jobs
                    WHERE estado = 'en_progreso' AND started_at < ?
                """, [(datetime.now() - timedelta(hours=2)).isoformat()])

                stuck_jobs = cursor.fetchone()[0] if cursor.fetchone() else 0

                # Check pending jobs
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM automation_jobs WHERE estado = 'pendiente'"
                )
                pending_jobs = cursor.fetchone()[0] if cursor.fetchone() else 0

                if stuck_jobs > 0:
                    status = "CRITICAL"
                    message = f"{stuck_jobs} stuck jobs, {pending_jobs} pending"
                elif pending_jobs > 10:
                    status = "WARNING"
                    message = f"High queue: {pending_jobs} pending jobs"
                else:
                    status = "OK"
                    message = f"Queue healthy: {pending_jobs} pending"

                return HealthMetric("job_queue", pending_jobs, 10, status, message, datetime.now())

        except Exception as e:
            return HealthMetric(
                "job_queue", 0, 10,
                "WARNING", f"Cannot check queue: {e}",
                datetime.now()
            )

    def _check_error_rate(self) -> HealthMetric:
        """Verificar tasa de errores."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count failed jobs in last hour
                one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

                cursor = conn.execute("""
                    SELECT
                        COUNT(CASE WHEN estado = 'fallido' THEN 1 END) as failed,
                        COUNT(*) as total
                    FROM automation_jobs
                    WHERE completed_at > ?
                """, [one_hour_ago])

                result = cursor.fetchone()
                if result and result[1] > 0:
                    failed, total = result
                    error_rate = (failed / total) * 100
                else:
                    error_rate = 0

                if error_rate > 20:
                    status = "CRITICAL"
                elif error_rate > 10:
                    status = "WARNING"
                else:
                    status = "OK"

                message = f"Error rate: {error_rate:.1f}% ({failed if 'failed' in locals() else 0}/{total if 'total' in locals() else 0} jobs)"
                return HealthMetric("error_rate", error_rate, 10, status, message, datetime.now())

        except Exception as e:
            return HealthMetric(
                "error_rate", 0, 10,
                "WARNING", f"Cannot calculate error rate: {e}",
                datetime.now()
            )

    def _check_service_availability(self) -> List[HealthMetric]:
        """Verificar disponibilidad de servicios externos."""
        metrics = []

        # Check v2 endpoints
        try:
            response = requests.get(f"{self.base_url}/invoicing/v2/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                services = health_data.get("services", [])

                for service in services:
                    name = service.get("name", "unknown")
                    status = "OK" if service.get("status") == "healthy" else "WARNING"
                    message = f"Service {name}: {service.get('status', 'unknown')}"

                    metrics.append(HealthMetric(
                        f"service_{name.lower().replace(' ', '_')}",
                        1 if status == "OK" else 0,
                        1, status, message, datetime.now()
                    ))
            else:
                metrics.append(HealthMetric(
                    "v2_endpoints", 0, 1,
                    "WARNING", "v2 endpoints not responding",
                    datetime.now()
                ))

        except Exception as e:
            metrics.append(HealthMetric(
                "v2_endpoints", 0, 1,
                "WARNING", f"Cannot check v2 endpoints: {e}",
                datetime.now()
            ))

        return metrics

    def _check_resource_usage(self) -> List[HealthMetric]:
        """Verificar uso de recursos."""
        metrics = []

        try:
            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = "OK" if cpu_percent < 80 else "WARNING" if cpu_percent < 95 else "CRITICAL"
            metrics.append(HealthMetric(
                "cpu_usage", cpu_percent, 80,
                cpu_status, f"CPU: {cpu_percent:.1f}%",
                datetime.now()
            ))

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_status = "OK" if memory_percent < 80 else "WARNING" if memory_percent < 95 else "CRITICAL"
            metrics.append(HealthMetric(
                "memory_usage", memory_percent, 80,
                memory_status, f"Memory: {memory_percent:.1f}%",
                datetime.now()
            ))

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_status = "OK" if disk_percent < 85 else "WARNING" if disk_percent < 95 else "CRITICAL"
            metrics.append(HealthMetric(
                "disk_usage", disk_percent, 85,
                disk_status, f"Disk: {disk_percent:.1f}%",
                datetime.now()
            ))

        except ImportError:
            metrics.append(HealthMetric(
                "resource_monitoring", 0, 1,
                "WARNING", "psutil not available for resource monitoring",
                datetime.now()
            ))
        except Exception as e:
            metrics.append(HealthMetric(
                "resource_monitoring", 0, 1,
                "WARNING", f"Cannot check resources: {e}",
                datetime.now()
            ))

        return metrics

    def _check_feature_flags(self) -> HealthMetric:
        """Verificar configuración de feature flags."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM feature_flags")
                ff_count = cursor.fetchone()[0]

                cursor = conn.execute("""
                    SELECT COUNT(DISTINCT company_id) FROM feature_flags
                """)
                company_count = cursor.fetchone()[0]

                if ff_count == 0:
                    status = "WARNING"
                    message = "No feature flags configured"
                else:
                    status = "OK"
                    message = f"{ff_count} feature flags for {company_count} companies"

                return HealthMetric("feature_flags", ff_count, 1, status, message, datetime.now())

        except Exception as e:
            return HealthMetric(
                "feature_flags", 0, 1,
                "WARNING", f"Cannot check feature flags: {e}",
                datetime.now()
            )

    def _metric_to_dict(self, metric: HealthMetric) -> Dict[str, Any]:
        """Convertir métrica a diccionario."""
        return {
            "name": metric.name,
            "value": metric.value,
            "threshold": metric.threshold,
            "status": metric.status,
            "message": metric.message,
            "timestamp": metric.timestamp.isoformat()
        }

    def _alert_to_dict(self, alert: Alert) -> Dict[str, Any]:
        """Convertir alerta a diccionario."""
        return {
            "level": alert.level,
            "message": alert.message,
            "metrics": [self._metric_to_dict(m) for m in alert.metrics],
            "timestamp": alert.timestamp.isoformat()
        }

    def send_alerts(self, alerts: List[Alert], webhook_url: Optional[str] = None):
        """Enviar alertas por webhook o email."""
        for alert in alerts:
            alert_key = f"{alert.level}_{alert.message}_{alert.timestamp.strftime('%Y%m%d_%H')}"

            # Evitar spam - solo enviar cada alerta una vez por hora
            if alert_key in self.alerts_sent:
                continue

            try:
                if webhook_url:
                    self._send_webhook_alert(alert, webhook_url)
                else:
                    self._log_alert(alert)

                self.alerts_sent.append(alert_key)

            except Exception as e:
                logger.error(f"Error sending alert: {e}")

    def _send_webhook_alert(self, alert: Alert, webhook_url: str):
        """Enviar alerta por webhook."""
        payload = {
            "alert": self._alert_to_dict(alert),
            "system": "automation_health_monitor"
        }

        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Alert sent to webhook: {alert.level} - {alert.message}")

    def _log_alert(self, alert: Alert):
        """Log alerta (fallback)."""
        emoji = "🚨" if alert.level == "CRITICAL" else "⚠️"
        logger.warning(f"{emoji} ALERT {alert.level}: {alert.message}")

        for metric in alert.metrics:
            logger.warning(f"  - {metric.name}: {metric.value} (threshold: {metric.threshold}) - {metric.message}")

    def continuous_monitoring(self, interval_seconds: int = 60, webhook_url: Optional[str] = None):
        """Monitoreo continuo."""
        logger.info(f"🔄 Iniciando monitoreo continuo cada {interval_seconds}s")

        while True:
            try:
                health_report = self.check_system_health()

                # Log summary
                summary = health_report["summary"]
                status = health_report["overall_status"]
                logger.info(f"Health check: {status} - {summary['ok_count']}/{summary['total_metrics']} OK")

                # Send alerts
                alerts = [Alert(
                    a["level"], a["message"],
                    [HealthMetric(m["name"], m["value"], m["threshold"], m["status"], m["message"], datetime.fromisoformat(m["timestamp"]))
                     for m in a["metrics"]],
                    datetime.fromisoformat(a["timestamp"])
                ) for a in health_report["alerts"]]

                if alerts:
                    self.send_alerts(alerts, webhook_url)

                # Save to file for historical tracking
                with open(f"health_report_{datetime.now().strftime('%Y%m%d')}.json", "w") as f:
                    json.dump(health_report, f, indent=2)

            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")

            time.sleep(interval_seconds)

def main():
    """Función principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor de salud del sistema de automatización")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL del servidor")
    parser.add_argument("--db", default="expenses.db", help="Path a la base de datos")
    parser.add_argument("--webhook", help="URL del webhook para alertas")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo de monitoreo en segundos")
    parser.add_argument("--continuous", action="store_true", help="Monitoreo continuo")
    parser.add_argument("--report", action="store_true", help="Generar reporte único")

    args = parser.parse_args()

    monitor = AutomationHealthMonitor(args.url, args.db)

    if args.continuous:
        monitor.continuous_monitoring(args.interval, args.webhook)
    else:
        health_report = monitor.check_system_health()
        print(json.dumps(health_report, indent=2))

        if health_report["overall_status"] != "OK":
            exit(1)

if __name__ == "__main__":
    main()