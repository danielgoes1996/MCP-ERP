#!/usr/bin/env python3
"""
Cost Analytics - Sistema de análisis y control de costos para GPT Vision

Rastrea cuándo, por qué y con qué frecuencia se usa GPT Vision para
optimizar costos y identificar oportunidades de mejora.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class GPTUsageEvent:
    """Evento de uso de GPT Vision para tracking de costos"""
    timestamp: str
    field_name: str
    reason: str
    tokens_estimated: int
    cost_estimated_usd: float
    confidence_before: float
    confidence_after: float
    success: bool
    merchant_type: str = "unknown"
    ticket_id: str = ""
    error_message: str = ""


@dataclass
class CostReport:
    """Reporte de costos y eficiencia"""
    total_gpt_calls: int
    total_cost_usd: float
    success_rate: float
    avg_confidence_improvement: float
    cost_per_successful_extraction: float
    breakdown_by_reason: Dict[str, Dict[str, Any]]
    breakdown_by_field: Dict[str, Dict[str, Any]]
    recommendations: List[str]


class CostAnalytics:
    """
    Sistema de análisis de costos para GPT Vision.

    Rastrea y analiza:
    - Cuándo se usa GPT Vision
    - Por qué se usa (razones)
    - Efectividad vs costo
    - Patrones de uso por merchant/campo
    - Recomendaciones de optimización
    """

    def __init__(self, db_path: str = "gpt_usage_analytics.db"):
        self.db_path = db_path
        self._init_database()

        # Precios de OpenAI (actualizar según pricing oficial)
        self.gpt4_vision_cost_per_token = 0.00001  # $0.01 per 1K tokens
        self.avg_tokens_per_image = 1000  # Estimación conservadora

    def _init_database(self):
        """Inicializar base de datos para tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gpt_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                field_name TEXT NOT NULL,
                reason TEXT NOT NULL,
                tokens_estimated INTEGER NOT NULL,
                cost_estimated_usd REAL NOT NULL,
                confidence_before REAL NOT NULL,
                confidence_after REAL NOT NULL,
                success INTEGER NOT NULL,
                merchant_type TEXT,
                ticket_id TEXT,
                error_message TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def track_gpt_usage(
        self,
        field_name: str,
        reason: str,
        confidence_before: float,
        confidence_after: float,
        success: bool,
        merchant_type: str = "unknown",
        ticket_id: str = "",
        error_message: str = ""
    ):
        """
        Registrar uso de GPT Vision para análisis posterior
        """
        try:
            # Calcular costo estimado
            tokens_estimated = self._estimate_tokens(reason)
            cost_estimated = tokens_estimated * self.gpt4_vision_cost_per_token

            event = GPTUsageEvent(
                timestamp=datetime.utcnow().isoformat(),
                field_name=field_name,
                reason=reason,
                tokens_estimated=tokens_estimated,
                cost_estimated_usd=cost_estimated,
                confidence_before=confidence_before,
                confidence_after=confidence_after,
                success=success,
                merchant_type=merchant_type,
                ticket_id=ticket_id,
                error_message=error_message
            )

            self._save_event(event)

            # Log para monitoreo inmediato
            logger.info(f"💰 GPT Usage tracked: {field_name} - ${cost_estimated:.4f} - {reason}")

        except Exception as e:
            logger.error(f"Error tracking GPT usage: {e}")

    def _estimate_tokens(self, reason: str) -> int:
        """
        Estimar tokens consumidos basado en el tipo de consulta
        """
        base_tokens = self.avg_tokens_per_image  # Imagen base

        # Tokens adicionales por contexto
        context_tokens = {
            "portal_error": 200,      # Error específico + candidatos
            "ambiguous_candidates": 150,  # Múltiples candidatos
            "critical_field": 100,    # Campo crítico sin candidatos
            "user_forced": 100        # Forzado por usuario
        }

        # Buscar keywords en reason para estimar tokens adicionales
        additional_tokens = 0
        for keyword, tokens in context_tokens.items():
            if keyword in reason.lower():
                additional_tokens += tokens
                break

        return base_tokens + additional_tokens

    def _save_event(self, event: GPTUsageEvent):
        """Guardar evento en base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO gpt_usage_events
            (timestamp, field_name, reason, tokens_estimated, cost_estimated_usd,
             confidence_before, confidence_after, success, merchant_type, ticket_id, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event.timestamp,
            event.field_name,
            event.reason,
            event.tokens_estimated,
            event.cost_estimated_usd,
            event.confidence_before,
            event.confidence_after,
            1 if event.success else 0,
            event.merchant_type,
            event.ticket_id,
            event.error_message
        ))

        conn.commit()
        conn.close()

    def generate_cost_report(self, days_back: int = 30) -> CostReport:
        """
        Generar reporte completo de costos y eficiencia
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Consultar eventos recientes
            cursor.execute('''
                SELECT * FROM gpt_usage_events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (cutoff_date,))

            events = cursor.fetchall()
            conn.close()

            if not events:
                return CostReport(
                    total_gpt_calls=0,
                    total_cost_usd=0.0,
                    success_rate=0.0,
                    avg_confidence_improvement=0.0,
                    cost_per_successful_extraction=0.0,
                    breakdown_by_reason={},
                    breakdown_by_field={},
                    recommendations=["No hay datos de uso de GPT Vision en el período seleccionado"]
                )

            # Procesar eventos
            total_calls = len(events)
            total_cost = sum(event[5] for event in events)  # cost_estimated_usd
            successful_calls = sum(1 for event in events if event[8])  # success
            success_rate = successful_calls / total_calls if total_calls > 0 else 0

            # Calcular mejora promedio de confianza
            confidence_improvements = [
                event[7] - event[6]  # confidence_after - confidence_before
                for event in events if event[8]  # solo exitosos
            ]
            avg_confidence_improvement = sum(confidence_improvements) / len(confidence_improvements) if confidence_improvements else 0

            # Costo por extracción exitosa
            cost_per_success = total_cost / successful_calls if successful_calls > 0 else 0

            # Breakdown por razón
            reason_stats = defaultdict(lambda: {"count": 0, "cost": 0.0, "success": 0})
            for event in events:
                reason = event[3]  # reason
                reason_stats[reason]["count"] += 1
                reason_stats[reason]["cost"] += event[5]  # cost_estimated_usd
                if event[8]:  # success
                    reason_stats[reason]["success"] += 1

            # Breakdown por campo
            field_stats = defaultdict(lambda: {"count": 0, "cost": 0.0, "success": 0})
            for event in events:
                field = event[2]  # field_name
                field_stats[field]["count"] += 1
                field_stats[field]["cost"] += event[5]  # cost_estimated_usd
                if event[8]:  # success
                    field_stats[field]["success"] += 1

            # Generar recomendaciones
            recommendations = self._generate_recommendations(
                reason_stats, field_stats, success_rate, avg_confidence_improvement
            )

            return CostReport(
                total_gpt_calls=total_calls,
                total_cost_usd=total_cost,
                success_rate=success_rate,
                avg_confidence_improvement=avg_confidence_improvement,
                cost_per_successful_extraction=cost_per_success,
                breakdown_by_reason=dict(reason_stats),
                breakdown_by_field=dict(field_stats),
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Error generating cost report: {e}")
            return CostReport(
                total_gpt_calls=0,
                total_cost_usd=0.0,
                success_rate=0.0,
                avg_confidence_improvement=0.0,
                cost_per_successful_extraction=0.0,
                breakdown_by_reason={},
                breakdown_by_field={},
                recommendations=[f"Error generando reporte: {e}"]
            )

    def _generate_recommendations(
        self,
        reason_stats: Dict,
        field_stats: Dict,
        success_rate: float,
        avg_confidence_improvement: float
    ) -> List[str]:
        """
        Generar recomendaciones de optimización basadas en análisis
        """
        recommendations = []

        # Análisis de tasa de éxito
        if success_rate < 0.7:
            recommendations.append(
                f"⚠️ Baja tasa de éxito ({success_rate:.1%}). "
                "Revisar calidad de imágenes o ajustar umbrales de confianza."
            )
        elif success_rate > 0.95:
            recommendations.append(
                f"✅ Excelente tasa de éxito ({success_rate:.1%}). "
                "Considerar ser más agresivo con heurísticas baratas."
            )

        # Análisis de mejora de confianza
        if avg_confidence_improvement < 0.1:
            recommendations.append(
                "⚠️ GPT Vision no está mejorando significativamente la confianza. "
                "Revisar si los casos de uso justifican el costo."
            )

        # Análisis por razón de uso
        if reason_stats:
            most_expensive_reason = max(reason_stats.items(), key=lambda x: x[1]["cost"])
            if most_expensive_reason[1]["cost"] > 5.0:  # Más de $5
                recommendations.append(
                    f"💰 La razón '{most_expensive_reason[0]}' es la más costosa "
                    f"(${most_expensive_reason[1]['cost']:.2f}). "
                    "Considerar optimizaciones específicas para este caso."
                )

        # Análisis por campo
        if field_stats:
            most_problematic_field = max(field_stats.items(), key=lambda x: x[1]["count"])
            if most_problematic_field[1]["count"] > len(field_stats) * 2:  # Campo muy problemático
                recommendations.append(
                    f"🎯 El campo '{most_problematic_field[0]}' requiere GPT Vision muy frecuentemente. "
                    "Considerar mejorar regex específicos para este campo."
                )

        # Recomendaciones generales
        if not recommendations:
            recommendations.append("✅ El uso de GPT Vision parece estar bien optimizado.")

        recommendations.append(
            "💡 Tip: Monitorea regularmente estos reportes para detectar "
            "oportunidades de optimización de costos."
        )

        return recommendations

    def get_daily_cost_trend(self, days: int = 7) -> Dict[str, float]:
        """
        Obtener tendencia de costos diarios
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DATE(timestamp) as date, SUM(cost_estimated_usd) as daily_cost
            FROM gpt_usage_events
            WHERE timestamp >= date('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        '''.format(days))

        results = cursor.fetchall()
        conn.close()

        return {date: cost for date, cost in results}

    def should_alert_on_costs(self, daily_budget: float = 10.0) -> tuple[bool, str]:
        """
        Verificar si se debe alertar sobre costos excesivos
        """
        today_costs = self.get_daily_cost_trend(1)
        today_total = sum(today_costs.values())

        if today_total > daily_budget:
            return True, f"Costo diario excedido: ${today_total:.2f} > ${daily_budget:.2f}"

        return False, f"Costo diario OK: ${today_total:.2f} / ${daily_budget:.2f}"

    def export_report_json(self, report: CostReport) -> str:
        """
        Exportar reporte como JSON para integración con dashboards
        """
        return json.dumps(asdict(report), indent=2, ensure_ascii=False)


# Instancia global
cost_analytics = CostAnalytics()


# Funciones de conveniencia
def track_gpt_usage(field_name: str, reason: str, **kwargs):
    """Función simple para tracking"""
    cost_analytics.track_gpt_usage(field_name, reason, **kwargs)


def get_cost_report(days_back: int = 30) -> CostReport:
    """Función simple para obtener reporte"""
    return cost_analytics.generate_cost_report(days_back)


if __name__ == "__main__":
    # Demo del sistema de analytics
    print("=== DEMO COST ANALYTICS ===")

    # Simular algunos eventos
    analytics = CostAnalytics(":memory:")  # DB en memoria para demo

    # Simular casos de uso
    test_events = [
        ("folio", "Portal rechazó: Folio no válido", 0.6, 0.9, True, "oxxo"),
        ("rfc_emisor", "2 candidatos ambiguos + baja confianza", 0.5, 0.8, True, "walmart"),
        ("monto_total", "Portal rechazó: Monto incorrecto", 0.7, 0.95, True, "pemex"),
        ("folio", "Campo crítico sin candidatos", 0.3, 0.6, False, "costco"),
        ("web_id", "Forzado por usuario", 0.8, 0.85, True, "oxxo"),
    ]

    for field, reason, conf_before, conf_after, success, merchant in test_events:
        analytics.track_gpt_usage(
            field_name=field,
            reason=reason,
            confidence_before=conf_before,
            confidence_after=conf_after,
            success=success,
            merchant_type=merchant
        )

    # Generar reporte
    report = analytics.generate_cost_report(days_back=1)

    print(f"\n📊 REPORTE DE COSTOS:")
    print(f"   Llamadas GPT Vision: {report.total_gpt_calls}")
    print(f"   Costo total: ${report.total_cost_usd:.4f}")
    print(f"   Tasa de éxito: {report.success_rate:.1%}")
    print(f"   Mejora promedio confianza: {report.avg_confidence_improvement:.2f}")
    print(f"   Costo por extracción exitosa: ${report.cost_per_successful_extraction:.4f}")

    print(f"\n📈 BREAKDOWN POR RAZÓN:")
    for reason, stats in report.breakdown_by_reason.items():
        success_rate = stats['success'] / stats['count'] if stats['count'] > 0 else 0
        print(f"   {reason[:40]}: {stats['count']} calls, ${stats['cost']:.4f}, {success_rate:.1%} éxito")

    print(f"\n🎯 RECOMENDACIONES:")
    for rec in report.recommendations:
        print(f"   {rec}")