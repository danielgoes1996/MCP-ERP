"""
Configuración de la Nueva Stack de Servicios

Arquitectura optimizada:
- Selenium → Automatización web
- Claude → Análisis DOM + explicación errores + priorización URLs
- Google Cloud Vision → OCR principal
- 2Captcha → Resolver captchas automáticamente
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ServiceConfig:
    """Configuración de servicios"""
    service_name: str
    is_available: bool
    api_key_env: str
    fallback_available: bool
    cost_per_request: float
    description: str

class ServiceStackManager:
    """Gestor de la stack de servicios optimizada"""

    def __init__(self):
        self.services = self._initialize_services()

    def _initialize_services(self) -> Dict[str, ServiceConfig]:
        """Inicializar configuración de servicios"""

        services = {}

        # Selenium (siempre requerido)
        try:
            import selenium
            selenium_available = True
        except ImportError:
            selenium_available = False

        services['selenium'] = ServiceConfig(
            service_name="Selenium WebDriver",
            is_available=selenium_available,
            api_key_env="",
            fallback_available=False,
            cost_per_request=0.0,
            description="Automatización web - REQUERIDO"
        )

        # Claude (reemplaza OpenAI)
        try:
            from core.ai_pipeline.automation.claude_dom_analyzer import create_claude_analyzer
            claude_analyzer = create_claude_analyzer()
            claude_available = claude_analyzer.is_available()
        except ImportError:
            claude_available = False

        services['claude'] = ServiceConfig(
            service_name="Claude (Anthropic)",
            is_available=claude_available,
            api_key_env="ANTHROPIC_API_KEY",
            fallback_available=True,  # Análisis heurístico
            cost_per_request=0.01,  # Aproximado
            description="Análisis DOM, explicación errores, priorización URLs"
        )

        # Google Cloud Vision (reemplaza OCR legacy)
        try:
            from core.google_vision_ocr import create_vision_ocr
            vision_ocr = create_vision_ocr()
            vision_available = vision_ocr.is_available()
        except ImportError:
            vision_available = False

        services['google_vision'] = ServiceConfig(
            service_name="Google Cloud Vision",
            is_available=vision_available,
            api_key_env="GOOGLE_APPLICATION_CREDENTIALS",
            fallback_available=True,  # OCR legacy si existe
            cost_per_request=0.0015,  # Por 1000 caracteres
            description="OCR principal para extraer datos de tickets"
        )

        # 2Captcha (reemplaza GPT-4 Vision para captchas)
        try:
            from core.ai_pipeline.automation.captcha_solver import create_captcha_solver
            captcha_solver = create_captcha_solver()
            captcha_available = captcha_solver.is_available()
        except ImportError:
            captcha_available = False

        services['twocaptcha'] = ServiceConfig(
            service_name="2Captcha",
            is_available=captcha_available,
            api_key_env="TWOCAPTCHA_API_KEY",
            fallback_available=True,  # Intervención manual
            cost_per_request=0.001,  # Por captcha
            description="Resolver reCAPTCHAs/hCAPTCHAs automáticamente"
        )

        return services

    def get_service_status(self) -> Dict[str, Any]:
        """Obtener estado de todos los servicios"""

        status = {
            "architecture": "optimized_stack_v1",
            "total_services": len(self.services),
            "available_services": sum(1 for s in self.services.values() if s.is_available),
            "services": {}
        }

        for service_key, config in self.services.items():
            status["services"][service_key] = {
                "name": config.service_name,
                "available": config.is_available,
                "has_fallback": config.fallback_available,
                "cost_per_request": config.cost_per_request,
                "description": config.description,
                "status": "✅ Disponible" if config.is_available else "❌ No configurado"
            }

        # Calcular estado general
        critical_services = ['selenium']  # Servicios críticos
        critical_available = all(
            self.services[service].is_available
            for service in critical_services
        )

        status["overall_status"] = "✅ Operacional" if critical_available else "⚠️ Configuración incompleta"
        status["readiness_score"] = self.calculate_readiness_score()

        return status

    def calculate_readiness_score(self) -> float:
        """Calcular score de preparación del sistema"""

        weights = {
            'selenium': 0.4,      # Crítico
            'claude': 0.3,        # Importante (tiene fallback)
            'google_vision': 0.2, # Importante (tiene fallback)
            'twocaptcha': 0.1     # Útil (tiene fallback)
        }

        score = 0.0
        for service_key, weight in weights.items():
            if service_key in self.services and self.services[service_key].is_available:
                score += weight

        return score

    def get_missing_services(self) -> List[Dict[str, str]]:
        """Obtener servicios faltantes con instrucciones"""

        missing = []

        for service_key, config in self.services.items():
            if not config.is_available and config.api_key_env:
                missing.append({
                    "service": config.service_name,
                    "env_var": config.api_key_env,
                    "description": config.description,
                    "setup_instruction": self._get_setup_instruction(service_key)
                })

        return missing

    def _get_setup_instruction(self, service_key: str) -> str:
        """Obtener instrucciones de configuración"""

        instructions = {
            'claude': "1. Crear cuenta en https://console.anthropic.com\n2. Generar API key\n3. export ANTHROPIC_API_KEY=your_key",
            'google_vision': "1. Crear proyecto en Google Cloud\n2. Habilitar Vision API\n3. Crear service account y descargar JSON\n4. export GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json",
            'twocaptcha': "1. Crear cuenta en https://2captcha.com\n2. Obtener API key del dashboard\n3. export TWOCAPTCHA_API_KEY=your_key"
        }

        return instructions.get(service_key, "Ver documentación del servicio")

    def validate_architecture(self) -> Dict[str, Any]:
        """Validar que la arquitectura esté correctamente configurada"""

        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        # Verificar servicios críticos
        if not self.services['selenium'].is_available:
            validation["valid"] = False
            validation["errors"].append("Selenium no disponible - requerido para automatización")

        # Verificar fallbacks
        if not self.services['claude'].is_available:
            validation["warnings"].append("Claude no disponible - usando análisis heurístico")

        if not self.services['google_vision'].is_available:
            validation["warnings"].append("Google Vision no disponible - limitando capacidad OCR")

        if not self.services['twocaptcha'].is_available:
            validation["warnings"].append("2Captcha no disponible - captchas requerirán intervención manual")

        # Recomendaciones
        readiness = self.calculate_readiness_score()
        if readiness < 0.8:
            validation["recommendations"].append(
                f"Score de preparación: {readiness:.1%} - considera configurar servicios faltantes"
            )

        if readiness >= 0.9:
            validation["recommendations"].append("🎯 Arquitectura completamente optimizada!")

        return validation

# Instancia global
service_stack = ServiceStackManager()

def get_service_stack() -> ServiceStackManager:
    """Obtener instancia del gestor de servicios"""
    return service_stack

def print_service_status():
    """Imprimir estado de servicios para debugging"""

    print("\n🎯 NUEVA ARQUITECTURA DE SERVICIOS")
    print("=" * 50)

    status = service_stack.get_service_status()

    print(f"Estado general: {status['overall_status']}")
    print(f"Score de preparación: {status['readiness_score']:.1%}")
    print(f"Servicios disponibles: {status['available_services']}/{status['total_services']}")

    print(f"\n📋 SERVICIOS:")
    for service_key, info in status["services"].items():
        print(f"   {info['status']} {info['name']}")
        print(f"      → {info['description']}")
        if info['cost_per_request'] > 0:
            print(f"      → Costo: ${info['cost_per_request']:.4f} por request")

    # Mostrar servicios faltantes
    missing = service_stack.get_missing_services()
    if missing:
        print(f"\n⚠️  SERVICIOS FALTANTES:")
        for service in missing:
            print(f"   • {service['service']}")
            print(f"     ENV: {service['env_var']}")
            print(f"     Setup: {service['setup_instruction'].split(chr(10))[0]}")

    # Validación
    validation = service_stack.validate_architecture()
    if validation["errors"]:
        print(f"\n❌ ERRORES:")
        for error in validation["errors"]:
            print(f"   • {error}")

    if validation["warnings"]:
        print(f"\n⚠️  ADVERTENCIAS:")
        for warning in validation["warnings"]:
            print(f"   • {warning}")

    print("\n" + "=" * 50)

# Función de migración
def migrate_from_openai_stack():
    """Ayudar en la migración desde OpenAI stack"""

    print("\n🔄 MIGRACIÓN DESDE OPENAI STACK")
    print("=" * 40)

    migration_steps = [
        "✅ Selenium → Sin cambios (ya implementado)",
        "🔄 OpenAI GPT-4 → Claude (para análisis DOM)",
        "🔄 GPT-4 Vision → Google Cloud Vision (para OCR)",
        "🔄 Manual captcha → 2Captcha (automático)",
        "✅ Persistencia → Sin cambios",
        "✅ Fallbacks → Mejorados con análisis heurístico"
    ]

    for step in migration_steps:
        print(f"   {step}")

    print(f"\n💰 BENEFICIOS:")
    benefits = [
        "Menor costo por request",
        "Mayor especialización por servicio",
        "Mejor manejo de HTML complejo (Claude)",
        "Captchas automáticos sin intervención",
        "Fallbacks más robustos"
    ]

    for benefit in benefits:
        print(f"   • {benefit}")

if __name__ == "__main__":
    print_service_status()
    migrate_from_openai_stack()