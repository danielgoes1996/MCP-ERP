#!/usr/bin/env python3
"""
Ejemplo de Flujo Optimizado de Costos
Demuestra cómo el sistema minimiza el uso de GPT Vision solo para casos necesarios
"""

import asyncio
import logging
from typing import Dict, Any

# Configurar logging para ver decisiones de costos
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CostOptimizationDemo:
    """
    Demo que muestra los diferentes escenarios y cuándo se usa GPT Vision
    """

    async def scenario_1_success_with_ocr_only(self):
        """
        ESCENARIO 1: OCR funciona perfecto, NO usar GPT Vision (AHORRO)
        """
        print("\n🟢 ESCENARIO 1: OCR EXITOSO - SIN GPT VISION")
        print("=" * 50)

        from core.intelligent_field_validator import validate_single_field

        # Simular ticket claro con folio obvio
        ticket_image = "base64_image_here"

        result = await validate_single_field(
            image_data=ticket_image,
            field_name="folio"
            # NO portal_error, NO force_gpt
        )

        print(f"📄 Resultado: '{result.final_value}'")
        print(f"🎯 Confianza: {result.confidence:.2%}")
        print(f"💰 Método: {result.method_used}")
        print(f"💵 Costo: $0.00 (OCR gratis)")

        assert "gpt_vision" not in result.method_used
        print("✅ ÉXITO: Ahorro de dinero, GPT Vision no usado")

    async def scenario_2_portal_rejects_use_gpt(self):
        """
        ESCENARIO 2: Portal rechaza, SÍ usar GPT Vision (JUSTIFICADO)
        """
        print("\n🔴 ESCENARIO 2: PORTAL RECHAZA - GPT VISION JUSTIFICADO")
        print("=" * 50)

        from core.intelligent_field_validator import validate_single_field

        ticket_image = "base64_image_here"

        # Portal OXXO rechazó el folio
        portal_error = "El folio ingresado no existe en nuestros registros"

        result = await validate_single_field(
            image_data=ticket_image,
            field_name="folio",
            portal_error=portal_error  # ← Esto justifica GPT Vision
        )

        print(f"🚨 Error portal: {portal_error}")
        print(f"📄 Folio corregido: '{result.final_value}'")
        print(f"🎯 Confianza: {result.confidence:.2%}")
        print(f"💰 Método: {result.method_used}")
        print(f"💵 Costo: ~$0.01 (GPT Vision justificado)")
        print(f"🧠 Razonamiento: {result.gpt_reasoning[:100]}...")

        assert "gpt_vision" in result.method_used
        print("✅ ÉXITO: Gasto justificado, portal acepta valor corregido")

    async def scenario_3_ambiguous_candidates(self):
        """
        ESCENARIO 3: Múltiples candidatos confusos + baja confianza
        """
        print("\n🟡 ESCENARIO 3: CANDIDATOS AMBIGUOS - GPT VISION CONDICIONAL")
        print("=" * 50)

        # Simular OCR que encontró múltiples números similares
        # En realidad esto lo haría el sistema automáticamente

        from core.intelligent_field_validator import intelligent_validator

        # Simular resultado con múltiples candidatos + baja confianza
        print("📋 Candidatos OCR encontrados: ['123456', '128456', '123856']")
        print("📊 Confianza OCR: 0.45 (baja)")
        print("🤔 Decisión: ¿Usar GPT Vision?")

        # El sistema DECIDIRÁ automáticamente basado en umbrales
        # Si confianza < 0.6 Y candidatos >= 2 → GPT Vision
        print("💰 Resultado: GPT Vision ACTIVADO (múltiples candidatos + baja confianza)")
        print("✅ Justificado por ambigüedad, no por error de portal")

    async def scenario_4_single_confident_candidate(self):
        """
        ESCENARIO 4: Un solo candidato confiable, NO usar GPT Vision
        """
        print("\n🟢 ESCENARIO 4: CANDIDATO ÚNICO CONFIABLE - AHORRO")
        print("=" * 50)

        print("📋 Candidatos OCR: ['A-789456'] (único)")
        print("📊 Confianza OCR: 0.85 (alta)")
        print("🤔 Decisión: ¿Usar GPT Vision?")
        print("💰 Resultado: GPT Vision NO USADO (candidato único + alta confianza)")
        print("💵 Ahorro: $0.01 por ticket")
        print("✅ Eficiencia: OCR suficiente para este caso")

    async def scenario_5_cost_analysis_report(self):
        """
        ESCENARIO 5: Análisis de costos y recomendaciones
        """
        print("\n📊 ESCENARIO 5: ANÁLISIS DE COSTOS")
        print("=" * 50)

        from core.cost_analytics import CostAnalytics

        # Simular analytics con datos de ejemplo
        analytics = CostAnalytics(":memory:")

        # Simular diferentes tipos de uso
        test_scenarios = [
            # (field, reason, conf_before, conf_after, success, merchant)
            ("folio", "Portal rechazó: Folio no válido", 0.7, 0.95, True, "oxxo"),
            ("folio", "Portal rechazó: Folio no válido", 0.6, 0.9, True, "oxxo"),
            ("rfc_emisor", "2 candidatos ambiguos + baja confianza", 0.4, 0.8, True, "walmart"),
            ("monto_total", "Portal rechazó: Monto incorrecto", 0.8, 0.95, True, "pemex"),
            ("folio", "Forzado por usuario", 0.9, 0.92, True, "costco"),  # Gasto innecesario
        ]

        for field, reason, conf_before, conf_after, success, merchant in test_scenarios:
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

        print(f"📈 REPORTE DE COSTOS (último día):")
        print(f"   Total llamadas GPT: {report.total_gpt_calls}")
        print(f"   Costo total: ${report.total_cost_usd:.4f}")
        print(f"   Tasa de éxito: {report.success_rate:.1%}")
        print(f"   Costo por extracción exitosa: ${report.cost_per_successful_extraction:.4f}")

        print(f"\n💡 RECOMENDACIONES:")
        for rec in report.recommendations:
            print(f"   {rec}")

        print(f"\n🔍 BREAKDOWN POR RAZÓN:")
        for reason, stats in report.breakdown_by_reason.items():
            success_rate = stats['success'] / stats['count'] if stats['count'] > 0 else 0
            print(f"   📊 {reason[:30]:<30} | {stats['count']} calls | ${stats['cost']:.4f} | {success_rate:.1%}")

    async def scenario_6_real_world_volume(self):
        """
        ESCENARIO 6: Volumen real y proyección de costos
        """
        print("\n📦 ESCENARIO 6: ANÁLISIS DE VOLUMEN REAL")
        print("=" * 50)

        # Proyecciones basadas en uso real
        daily_tickets = 1000
        portal_error_rate = 0.05  # 5% de tickets tienen errores de portal
        ambiguous_rate = 0.02     # 2% tienen candidatos ambiguos

        gpt_usage_rate = portal_error_rate + ambiguous_rate
        daily_gpt_calls = daily_tickets * gpt_usage_rate
        cost_per_call = 0.01  # $0.01 por llamada GPT Vision
        daily_cost = daily_gpt_calls * cost_per_call
        monthly_cost = daily_cost * 30

        print(f"📊 PROYECCIÓN DE COSTOS:")
        print(f"   Tickets diarios: {daily_tickets:,}")
        print(f"   Tasa de uso GPT Vision: {gpt_usage_rate:.1%}")
        print(f"   Llamadas GPT diarias: {daily_gpt_calls:.0f}")
        print(f"   Costo diario: ${daily_cost:.2f}")
        print(f"   Costo mensual: ${monthly_cost:.2f}")

        print(f"\n🎯 OPTIMIZACIONES IMPLEMENTADAS:")
        print(f"   ✅ Solo usar GPT cuando portal rechaza (casos reales)")
        print(f"   ✅ Heurísticas baratas para candidatos únicos")
        print(f"   ✅ Umbrales de confianza ajustables")
        print(f"   ✅ Tracking completo para optimización continua")

        # Comparación con uso naive
        naive_usage_rate = 0.5  # 50% si usáramos GPT para todo
        naive_monthly_cost = daily_tickets * naive_usage_rate * cost_per_call * 30

        savings = naive_monthly_cost - monthly_cost
        print(f"\n💰 AHORRO vs USO NAIVE:")
        print(f"   Costo naive (50% uso): ${naive_monthly_cost:.2f}/mes")
        print(f"   Costo optimizado: ${monthly_cost:.2f}/mes")
        print(f"   🎉 AHORRO: ${savings:.2f}/mes ({(savings/naive_monthly_cost)*100:.1f}%)")

    async def run_all_scenarios(self):
        """Ejecutar todos los escenarios de demostración"""
        print("🚀 DEMO: FLUJO OPTIMIZADO DE COSTOS GPT VISION")
        print("=" * 70)
        print("Demostrando cuándo SÍ y cuándo NO usar GPT Vision para minimizar costos")

        await self.scenario_1_success_with_ocr_only()
        await self.scenario_2_portal_rejects_use_gpt()
        await self.scenario_3_ambiguous_candidates()
        await self.scenario_4_single_confident_candidate()
        await self.scenario_5_cost_analysis_report()
        await self.scenario_6_real_world_volume()

        print(f"\n🎯 RESUMEN DE ESTRATEGIA DE COSTOS:")
        print(f"   🟢 Casos BARATOS (OCR solo): Candidato único + alta confianza")
        print(f"   🔴 Casos COSTOSOS (GPT Vision): Portal rechaza + error específico")
        print(f"   🟡 Casos CONDICIONALES: Múltiples candidatos + baja confianza")
        print(f"   📊 Tracking completo para optimización continua")

        print(f"\n💡 BENEFICIOS CLAVE:")
        print(f"   💰 Ahorro del 80-90% en costos de GPT Vision")
        print(f"   🎯 Precisión máxima solo cuando es necesario")
        print(f"   📈 Métricas para optimización continua")
        print(f"   🔧 Umbrales ajustables según presupuesto")


async def main():
    """Ejecutar demo completo"""
    demo = CostOptimizationDemo()
    await demo.run_all_scenarios()


if __name__ == "__main__":
    asyncio.run(main())