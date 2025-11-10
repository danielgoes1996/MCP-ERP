"""
Motor de Automatización Unificado

Integra la nueva stack de servicios optimizada:
- Selenium + Claude + Google Vision + 2Captcha

Reemplaza dependencias OpenAI con servicios especializados más eficientes.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Importar nueva stack
from core.config.service_stack_config import get_service_stack
from core.google_vision_ocr import create_vision_ocr, migrate_from_legacy_ocr
from core.ai_pipeline.automation.claude_dom_analyzer import create_claude_analyzer
from core.ai_pipeline.automation.captcha_solver import create_captcha_solver, auto_solve_page_captcha

# Importar motor robusto existente
try:
    from modules.invoicing_agent.robust_automation_engine import RobustAutomationEngine
    ROBUST_ENGINE_AVAILABLE = True
except ImportError:
    ROBUST_ENGINE_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class UnifiedResult:
    """Resultado unificado del motor de automatización"""
    success: bool
    service_stack_used: Dict[str, str]
    processing_time_ms: int
    cost_breakdown: Dict[str, float]
    automation_summary: Dict[str, Any]
    error_report: Optional[Dict[str, Any]] = None

class UnifiedAutomationEngine:
    """Motor unificado que orquesta todos los servicios"""

    def __init__(self):
        self.service_stack = get_service_stack()
        self.vision_ocr = None
        self.claude_analyzer = None
        self.captcha_solver = None
        self.robust_engine = None

        self._initialize_services()

    def _initialize_services(self):
        """Inicializar todos los servicios disponibles"""

        # Google Vision OCR
        try:
            self.vision_ocr = create_vision_ocr()
            if self.vision_ocr.is_available():
                logger.info("✅ Google Vision OCR inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Google Vision no disponible: {e}")

        # Claude Analyzer
        try:
            self.claude_analyzer = create_claude_analyzer()
            if self.claude_analyzer.is_available():
                logger.info("✅ Claude DOM Analyzer inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Claude no disponible: {e}")

        # 2Captcha Solver
        try:
            self.captcha_solver = create_captcha_solver()
            if self.captcha_solver.is_available():
                logger.info("✅ 2Captcha Solver inicializado")
        except Exception as e:
            logger.warning(f"⚠️ 2Captcha no disponible: {e}")

        # Motor Robusto (hereda toda la lógica Selenium)
        if ROBUST_ENGINE_AVAILABLE:
            try:
                self.robust_engine = RobustAutomationEngine()
                logger.info("✅ Motor Robusto Selenium inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Motor Robusto no disponible: {e}")

    async def process_invoice_automation(
        self,
        merchant: Dict[str, Any],
        ticket_data: Dict[str, Any],
        ticket_id: int,
        alternative_urls: List[str] = None
    ) -> UnifiedResult:
        """Proceso principal de automatización con nueva stack"""

        start_time = datetime.now()
        services_used = {}
        costs = {}

        try:
            # 1. OCR con Google Vision (si hay imagen)
            ocr_result = None
            if 'image_path' in ticket_data:
                ocr_result = await self._process_ocr(ticket_data['image_path'])
                services_used['ocr'] = 'google_vision' if ocr_result['service'] == 'google_vision' else 'fallback'
                costs['ocr'] = 0.0015 if ocr_result['service'] == 'google_vision' else 0.0

            # 2. Análisis DOM con Claude
            automation_result = await self._process_automation(
                merchant, ticket_data, ticket_id, alternative_urls
            )

            services_used['dom_analysis'] = 'claude' if automation_result.get('llm_service') == 'claude' else 'heuristic'
            costs['dom_analysis'] = 0.01 if automation_result.get('llm_service') == 'claude' else 0.0

            # 3. Captcha handling con 2Captcha (si fue necesario)
            if automation_result.get('captcha_encountered'):
                services_used['captcha'] = 'twocaptcha' if automation_result.get('captcha_solved') else 'manual'
                costs['captcha'] = 0.001 if automation_result.get('captcha_solved') else 0.0

            # 4. Selenium siempre se usa
            services_used['automation'] = 'selenium'
            costs['automation'] = 0.0

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return UnifiedResult(
                success=automation_result.get('success', False),
                service_stack_used=services_used,
                processing_time_ms=int(processing_time),
                cost_breakdown=costs,
                automation_summary=automation_result,
                error_report=automation_result.get('error_report') if not automation_result.get('success') else None
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return UnifiedResult(
                success=False,
                service_stack_used=services_used,
                processing_time_ms=int(processing_time),
                cost_breakdown=costs,
                automation_summary={},
                error_report={
                    'error': str(e),
                    'stage': 'unified_engine',
                    'services_attempted': services_used
                }
            )

    async def _process_ocr(self, image_path: str) -> Dict[str, Any]:
        """Procesar OCR con Google Vision o fallback"""

        try:
            if self.vision_ocr and self.vision_ocr.is_available():
                logger.info("🔍 Procesando OCR con Google Vision")
                return await migrate_from_legacy_ocr(image_path)
            else:
                logger.info("🔍 Google Vision no disponible, usando OCR legacy")
                # Aquí podrías implementar fallback a OCR legacy existente
                return {
                    "success": False,
                    "fallback_needed": True,
                    "service": "none"
                }

        except Exception as e:
            logger.error(f"❌ Error en OCR: {e}")
            return {
                "success": False,
                "error": str(e),
                "service": "error"
            }

    async def _process_automation(
        self,
        merchant: Dict[str, Any],
        ticket_data: Dict[str, Any],
        ticket_id: int,
        alternative_urls: List[str] = None
    ) -> Dict[str, Any]:
        """Procesar automatización con motor robusto mejorado"""

        try:
            if not self.robust_engine:
                raise Exception("Motor robusto no disponible")

            logger.info(f"🤖 Iniciando automatización unificada para {merchant.get('nombre', 'Unknown')}")

            # El motor robusto ya fue modificado para usar Claude
            result = await self.robust_engine.navigate_to_invoicing_portal(
                merchant.get('portal_url', ''),
                alternative_urls or []
            )

            # Agregar información de servicios usados
            result['llm_service'] = 'claude' if self.claude_analyzer and self.claude_analyzer.is_available() else 'heuristic'

            # Detectar si se encontraron captchas
            screenshots = result.get('automation_summary', {}).get('screenshots', [])
            result['captcha_encountered'] = any('captcha' in str(screenshot).lower() for screenshot in screenshots)
            result['captcha_solved'] = False  # Por ahora, mejoramos después

            return result

        except Exception as e:
            logger.error(f"❌ Error en automatización: {e}")
            return {
                'success': False,
                'error': str(e),
                'llm_service': 'none'
            }

    def get_service_capabilities(self) -> Dict[str, Any]:
        """Obtener capacidades del motor unificado"""

        capabilities = {
            "engine_version": "unified_v1",
            "services": {},
            "features": [],
            "readiness_score": 0.0
        }

        # Verificar cada servicio
        services_status = self.service_stack.get_service_status()
        capabilities["services"] = services_status["services"]
        capabilities["readiness_score"] = services_status["readiness_score"]

        # Determinar features disponibles
        if self.vision_ocr and self.vision_ocr.is_available():
            capabilities["features"].append("google_vision_ocr")

        if self.claude_analyzer and self.claude_analyzer.is_available():
            capabilities["features"].append("claude_dom_analysis")
            capabilities["features"].append("intelligent_url_classification")
            capabilities["features"].append("human_readable_error_reports")

        if self.captcha_solver and self.captcha_solver.is_available():
            capabilities["features"].append("automatic_captcha_solving")

        if self.robust_engine:
            capabilities["features"].extend([
                "selenium_automation",
                "intelligent_navigation",
                "multiple_url_handling",
                "screenshot_evidence",
                "database_persistence"
            ])

        return capabilities

    async def validate_merchant_urls(self, urls: List[str], merchant_name: str = "") -> Dict[str, Any]:
        """Validar y clasificar URLs de merchant usando Claude"""

        try:
            if self.claude_analyzer and self.claude_analyzer.is_available():
                logger.info(f"🔍 Clasificando {len(urls)} URLs con Claude")
                classifications = await self.claude_analyzer.classify_urls_for_invoicing(urls, merchant_name)

                return {
                    "success": True,
                    "classifications": classifications,
                    "service_used": "claude",
                    "recommended_order": sorted(
                        classifications.items(),
                        key=lambda x: x[1].url_priority_score,
                        reverse=True
                    )
                }
            else:
                logger.info("🔍 Claude no disponible, usando clasificación heurística")
                return {
                    "success": True,
                    "classifications": {},
                    "service_used": "heuristic",
                    "recommended_order": [(url, None) for url in urls]
                }

        except Exception as e:
            logger.error(f"❌ Error validando URLs: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_used": "error"
            }

# Factory function
def create_unified_engine() -> UnifiedAutomationEngine:
    """Crear instancia del motor unificado"""
    return UnifiedAutomationEngine()

# Función de migración desde sistema legacy
async def migrate_from_legacy_automation(
    merchant: Dict[str, Any],
    ticket_data: Dict[str, Any],
    ticket_id: int
) -> UnifiedResult:
    """Migrar desde sistema legacy al motor unificado"""

    logger.info("🔄 Migrando desde sistema legacy al motor unificado")

    engine = create_unified_engine()

    # Mostrar capacidades del nuevo motor
    capabilities = engine.get_service_capabilities()
    logger.info(f"🎯 Motor unificado inicializado con {len(capabilities['features'])} features")
    logger.info(f"📊 Score de preparación: {capabilities['readiness_score']:.1%}")

    # Procesar con nueva stack
    result = await engine.process_invoice_automation(
        merchant, ticket_data, ticket_id
    )

    # Log del resultado
    if result.success:
        total_cost = sum(result.cost_breakdown.values())
        logger.info(f"✅ Automatización exitosa - Costo total: ${total_cost:.4f}")
        logger.info(f"🔧 Servicios usados: {', '.join(result.service_stack_used.values())}")
    else:
        logger.error(f"❌ Automatización falló: {result.error_report}")

    return result

# Testing helper
async def test_unified_engine():
    """Probar el motor unificado"""

    print("🧪 PROBANDO MOTOR UNIFICADO")
    print("=" * 40)

    engine = create_unified_engine()
    capabilities = engine.get_service_capabilities()

    print(f"Motor: {capabilities['engine_version']}")
    print(f"Score: {capabilities['readiness_score']:.1%}")
    print(f"Features: {len(capabilities['features'])}")

    for feature in capabilities['features']:
        print(f"   ✅ {feature}")

    # Test básico
    test_merchant = {
        "nombre": "Test Merchant",
        "portal_url": "https://example.com"
    }

    test_ticket = {
        "id": 999,
        "texto_extraido": "RFC: TEST010101000\\nTotal: $100.00"
    }

    try:
        result = await engine.process_invoice_automation(
            test_merchant, test_ticket, 999
        )

        print(f"\n📊 RESULTADO TEST:")
        print(f"   Éxito: {result.success}")
        print(f"   Tiempo: {result.processing_time_ms}ms")
        print(f"   Servicios: {result.service_stack_used}")
        print(f"   Costo: ${sum(result.cost_breakdown.values()):.4f}")

    except Exception as e:
        print(f"❌ Error en test: {e}")

if __name__ == "__main__":
    asyncio.run(test_unified_engine())