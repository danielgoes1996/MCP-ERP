"""
Sistema de Fallbacks Robustos para el módulo de tickets.
Maneja elegantemente las fallas de servicios externos.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Estado de un servicio."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class FallbackResult:
    """Resultado de un intento de fallback."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    service_used: Optional[str] = None
    attempt_number: int = 0
    processing_time_ms: int = 0


class RobustFallbackSystem:
    """
    Sistema de fallbacks robusto que maneja fallas de servicios
    con circuit breakers y recuperación automática.
    """

    def __init__(self):
        self.service_health = {}
        self.circuit_breakers = {}
        self.retry_counts = {}
        self.last_failure_times = {}

    def register_service(self, service_name: str, health_check: Optional[Callable] = None):
        """Registrar un servicio en el sistema de fallbacks."""
        self.service_health[service_name] = ServiceStatus.UNKNOWN
        self.circuit_breakers[service_name] = False  # False = cerrado (funcionando)
        self.retry_counts[service_name] = 0
        self.last_failure_times[service_name] = 0

    async def try_with_fallbacks(
        self,
        primary_func: Callable,
        fallback_funcs: List[Callable],
        service_names: List[str],
        max_retries: int = 2,
        timeout_seconds: int = 30
    ) -> FallbackResult:
        """
        Intentar ejecutar una función con fallbacks automáticos.

        Args:
            primary_func: Función principal a ejecutar
            fallback_funcs: Lista de funciones de fallback
            service_names: Nombres de servicios correspondientes
            max_retries: Máximo número de reintentos por servicio
            timeout_seconds: Timeout por intento

        Returns:
            Resultado del intento exitoso o el último error
        """
        all_functions = [primary_func] + fallback_funcs
        all_services = service_names

        for i, (func, service_name) in enumerate(zip(all_functions, all_services)):
            # Verificar circuit breaker
            if self._is_circuit_breaker_open(service_name):
                logger.warning(f"Circuit breaker abierto para {service_name}, saltando")
                continue

            attempt_number = 0
            while attempt_number < max_retries:
                attempt_number += 1
                start_time = time.time()

                try:
                    # Ejecutar con timeout
                    result = await asyncio.wait_for(
                        func() if asyncio.iscoroutinefunction(func) else asyncio.to_thread(func),
                        timeout=timeout_seconds
                    )

                    processing_time = int((time.time() - start_time) * 1000)

                    # Éxito - actualizar estado
                    self._mark_service_healthy(service_name)

                    return FallbackResult(
                        success=True,
                        result=result,
                        service_used=service_name,
                        attempt_number=attempt_number,
                        processing_time_ms=processing_time
                    )

                except asyncio.TimeoutError:
                    error_msg = f"{service_name} timeout después de {timeout_seconds}s"
                    logger.warning(f"Intento {attempt_number}/{max_retries}: {error_msg}")
                    self._mark_service_failed(service_name, error_msg)

                except Exception as e:
                    error_msg = f"{service_name} error: {str(e)}"
                    logger.warning(f"Intento {attempt_number}/{max_retries}: {error_msg}")
                    self._mark_service_failed(service_name, error_msg)

                    # Esperar antes de reintentar
                    if attempt_number < max_retries:
                        await asyncio.sleep(min(2 ** attempt_number, 10))  # Exponential backoff

        # Todos los servicios fallaron
        return FallbackResult(
            success=False,
            error="Todos los servicios fallaron",
            service_used=None
        )

    def _is_circuit_breaker_open(self, service_name: str) -> bool:
        """Verificar si el circuit breaker está abierto."""
        if service_name not in self.circuit_breakers:
            return False

        # Si está abierto, verificar si es hora de intentar nuevamente
        if self.circuit_breakers[service_name]:
            time_since_failure = time.time() - self.last_failure_times[service_name]
            if time_since_failure > 300:  # 5 minutos
                logger.info(f"Intentando reabrir circuit breaker para {service_name}")
                self.circuit_breakers[service_name] = False
                self.retry_counts[service_name] = 0
                return False

        return self.circuit_breakers[service_name]

    def _mark_service_healthy(self, service_name: str):
        """Marcar servicio como saludable."""
        self.service_health[service_name] = ServiceStatus.HEALTHY
        self.circuit_breakers[service_name] = False
        self.retry_counts[service_name] = 0

    def _mark_service_failed(self, service_name: str, error: str):
        """Marcar servicio como fallido."""
        self.service_health[service_name] = ServiceStatus.FAILED
        self.retry_counts[service_name] += 1
        self.last_failure_times[service_name] = time.time()

        # Abrir circuit breaker después de 3 fallas
        if self.retry_counts[service_name] >= 3:
            logger.warning(f"Abriendo circuit breaker para {service_name}")
            self.circuit_breakers[service_name] = True

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Obtener estado actual de un servicio."""
        return self.service_health.get(service_name, ServiceStatus.UNKNOWN)

    def get_health_summary(self) -> Dict[str, Any]:
        """Obtener resumen de salud de todos los servicios."""
        return {
            "services": {
                name: {
                    "status": status.value,
                    "circuit_breaker_open": self.circuit_breakers.get(name, False),
                    "retry_count": self.retry_counts.get(name, 0),
                    "last_failure": self.last_failure_times.get(name, 0)
                }
                for name, status in self.service_health.items()
            },
            "overall_health": self._calculate_overall_health()
        }

    def _calculate_overall_health(self) -> str:
        """Calcular salud general del sistema."""
        if not self.service_health:
            return "unknown"

        healthy_count = sum(1 for status in self.service_health.values()
                          if status == ServiceStatus.HEALTHY)
        total_count = len(self.service_health)

        if healthy_count == total_count:
            return "healthy"
        elif healthy_count >= total_count * 0.5:
            return "degraded"
        else:
            return "failed"


# Instancia global para usar en todo el módulo
fallback_system = RobustFallbackSystem()


# Funciones helper para fácil uso
async def try_ocr_with_fallbacks(image_data: str, context_hint: str = None) -> FallbackResult:
    """Helper para OCR con fallbacks automáticos."""
    from core.advanced_ocr_service import AdvancedOCRService

    service = AdvancedOCRService()

    async def google_vision():
        return await service._extract_with_google_vision(image_data, context_hint)

    async def tesseract():
        return await service._extract_with_tesseract(image_data)

    async def simulation():
        return await service._extract_with_simulation(image_data, context_hint)

    return await fallback_system.try_with_fallbacks(
        primary_func=google_vision,
        fallback_funcs=[tesseract, simulation],
        service_names=["google_vision", "tesseract", "simulation"],
        max_retries=2,
        timeout_seconds=30
    )


async def try_llm_analysis_with_fallbacks(text: str, prompt: str) -> FallbackResult:
    """Helper para análisis LLM con fallbacks."""
    try:
        import openai
        client = openai.AsyncOpenAI()

        async def openai_analysis():
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=800,
                temperature=0.1
            )
            return response.choices[0].message.content

        async def basic_analysis():
            # Análisis básico sin LLM
            lines = text.split('\n')
            analysis = {
                "merchant_name": "Unknown",
                "category": "otros",
                "confidence": 0.3,
                "method": "basic_fallback"
            }

            # Buscar patrones conocidos
            for line in lines:
                line_lower = line.lower()
                if any(merchant in line_lower for merchant in ['oxxo', 'walmart', 'pemex', 'costco']):
                    for merchant in ['oxxo', 'walmart', 'pemex', 'costco']:
                        if merchant in line_lower:
                            analysis["merchant_name"] = merchant.upper()
                            analysis["confidence"] = 0.8
                            break
                    break

            return analysis

        return await fallback_system.try_with_fallbacks(
            primary_func=openai_analysis,
            fallback_funcs=[basic_analysis],
            service_names=["openai", "basic_analysis"],
            max_retries=2,
            timeout_seconds=15
        )

    except ImportError:
        # OpenAI no disponible, usar solo análisis básico
        async def basic_analysis():
            return {"merchant_name": "Unknown", "category": "otros", "confidence": 0.3}

        return await fallback_system.try_with_fallbacks(
            primary_func=basic_analysis,
            fallback_funcs=[],
            service_names=["basic_analysis"],
            max_retries=1
        )


# Registrar servicios al importar el módulo
fallback_system.register_service("google_vision")
fallback_system.register_service("tesseract")
fallback_system.register_service("simulation")
fallback_system.register_service("openai")
fallback_system.register_service("basic_analysis")