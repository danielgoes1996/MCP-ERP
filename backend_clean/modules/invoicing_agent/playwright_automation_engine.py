"""
Playwright Automation Engine - Reemplazo completo del RobustAutomationEngine
Arquitectura modular y extensible para automatización de portales de facturación
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright

# Verificar disponibilidad de Claude
try:
    from core.claude_dom_analyzer import create_claude_analyzer
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

logger = logging.getLogger(__name__)

class PlaywrightActionType(Enum):
    """Tipos de acciones de automatización"""
    NAVIGATE = "navigate"
    SEARCH_ELEMENTS = "search_elements"
    CLICK_ELEMENT = "click_element"
    FILL_FORM = "fill_form"
    WAIT_FOR_ELEMENT = "wait_for_element"
    TAKE_SCREENSHOT = "take_screenshot"
    EXTRACT_DOM = "extract_dom"
    CLAUDE_ANALYSIS = "claude_analysis"
    FALLBACK_STRATEGY = "fallback_strategy"
    VALIDATE_SUCCESS = "validate_success"

class PortalType(Enum):
    """Tipos de portales de facturación"""
    LITROMIL = "litromil"
    ASP_NET = "asp_net"
    REACT_SPA = "react_spa"
    WORDPRESS = "wordpress"
    CUSTOM = "custom"

@dataclass
class PlaywrightStep:
    """Paso de automatización con Playwright"""
    step_number: int
    action_type: PlaywrightActionType
    description: str
    timestamp: str
    success: bool = False
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    url_before: Optional[str] = None
    url_after: Optional[str] = None
    elements_found: int = 0
    execution_time: float = 0.0
    data: Optional[Dict[str, Any]] = None

@dataclass
class PortalConfig:
    """Configuración específica por portal"""
    portal_type: PortalType
    base_urls: List[str]
    invoice_indicators: List[str]  # Palabras clave que indican facturación
    form_indicators: List[str]     # Indicadores de formularios de facturación
    success_indicators: List[str]  # Indicadores de éxito (Estación, Folio, etc.)
    navigation_strategies: List[Dict[str, str]]  # Estrategias ordenadas por prioridad
    timeouts: Dict[str, int]

class PlaywrightAutomationEngine:
    """Motor de automatización completo basado en Playwright"""

    def __init__(self, ticket_id: int, portal_config: Optional[PortalConfig] = None):
        self.ticket_id = ticket_id
        self.portal_config = portal_config or self._get_default_config()

        # Playwright components
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Tracking
        self.steps: List[PlaywrightStep] = []
        self.current_step = 0
        self.start_time = time.time()

        # Configuration
        self.screenshots_dir = Path("/Users/danielgoes96/Desktop/mcp-server/static/automation_screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)

        # Claude integration
        self.claude_analyzer = None
        if CLAUDE_AVAILABLE:
            try:
                self.claude_analyzer = create_claude_analyzer()
                self._log("🤖 Claude habilitado para análisis inteligente")
            except Exception as e:
                self._log(f"⚠️ Claude no disponible: {e}")

    def _get_default_config(self) -> PortalConfig:
        """Configuración por defecto (Litromil)"""
        return PortalConfig(
            portal_type=PortalType.LITROMIL,
            base_urls=["https://litromil.com", "http://litromil.dynalias.net:8088/litromil/"],
            invoice_indicators=["factur", "invoic", "bill", "cobr"],
            form_indicators=["estacion", "folio", "webid", "web id", "rfc"],
            success_indicators=["estación", "folio", "web id", "facturación electrónica"],
            navigation_strategies=[
                {"name": "Direct FACTURACIÓN link", "selector": "a:has-text('FACTURACIÓN')", "priority": 1},
                {"name": "Litromil portal link", "selector": "a[href*='litromil.dynalias.net']", "priority": 2},
                {"name": "Click Aquí link", "selector": "a:has-text('Click Aquí!')", "priority": 3},
                {"name": "Facturar button", "selector": "#facturar", "priority": 4},
                {"name": "Any facturación link", "selector": "a:has-text('Facturación')", "priority": 5}
            ],
            timeouts={
                "navigation": 30000,
                "element": 10000,
                "page_load": 30000
            }
        )

    def _log(self, message: str, level: str = "INFO"):
        """Logging con timestamp"""
        timestamp = time.time() - self.start_time
        log_entry = f"[{timestamp:.2f}s] {level}: {message}"
        if level == "ERROR":
            logger.error(log_entry)
        elif level == "WARNING":
            logger.warning(log_entry)
        else:
            logger.info(log_entry)

    async def initialize(self) -> bool:
        """Inicializar Playwright con configuración robusta"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.NAVIGATE, "Inicializando Playwright")

        try:
            self._log("🚀 Inicializando Playwright Engine...")

            self.playwright = await async_playwright().start()

            # Configurar browser con opciones optimizadas
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Visual para debugging
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )

            # Crear contexto con configuración realista
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                java_script_enabled=True
            )

            # Crear página principal
            self.page = await self.context.new_page()

            # Configurar timeouts
            self.page.set_default_timeout(self.portal_config.timeouts["element"])
            self.page.set_default_navigation_timeout(self.portal_config.timeouts["navigation"])

            # Event listeners
            self.page.on("console", lambda msg: self._log(f"Console: {msg.text}"))
            self.page.on("pageerror", lambda exc: self._log(f"Page error: {exc}", "ERROR"))
            self.page.on("request", lambda req: self._log(f"Request: {req.method} {req.url}") if "factur" in req.url.lower() else None)

            current_step.success = True
            current_step.execution_time = time.time() - step_start

            self._log("✅ Playwright inicializado correctamente")
            return True

        except Exception as e:
            current_step.success = False
            current_step.error_message = str(e)
            current_step.execution_time = time.time() - step_start

            self._log(f"❌ Error inicializando Playwright: {e}", "ERROR")
            await self.cleanup()
            return False

    async def navigate_to_invoicing_portal(self, primary_url: str, alternative_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Navegación principal al portal de facturación - Reemplazo de RobustAutomationEngine
        """
        self._log(f"🎯 Iniciando navegación a portal de facturación: {primary_url}")

        result = {
            "success": False,
            "message": "",
            "steps": [],
            "final_url": primary_url,
            "execution_summary": {},
            "screenshots": []
        }

        try:
            # Paso 1: Navegación inicial
            nav_result = await self._navigate_to_url(primary_url)
            if not nav_result["success"]:
                return self._finalize_result(result, False, f"Failed to navigate to {primary_url}")

            # Paso 2: Análisis de página inicial
            analysis_result = await self._analyze_current_page()
            if analysis_result.get("hasInvoiceOptions"):
                # Ya estamos en la página correcta
                return self._finalize_result(result, True, "Already on invoice form page", analysis_result)

            # Paso 3: Buscar y ejecutar navegación a facturación
            navigation_result = await self._execute_invoice_navigation()
            if not navigation_result["success"]:
                return self._finalize_result(result, False, navigation_result.get("message", "Navigation failed"))

            # Paso 4: Validar llegada a formularios
            final_analysis = await self._validate_invoice_page()
            success = final_analysis.get("hasInvoiceOptions", False)

            message = "Successfully navigated to invoice forms" if success else "Navigation completed but no invoice forms detected"
            return self._finalize_result(result, success, message, final_analysis)

        except Exception as e:
            self._log(f"❌ Error en navegación principal: {e}", "ERROR")
            return self._finalize_result(result, False, f"Navigation error: {str(e)}")

    async def _navigate_to_url(self, url: str) -> Dict[str, Any]:
        """Navegar a URL con manejo robusto"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.NAVIGATE, f"Navegando a {url}")

        try:
            self._log(f"🌐 Navegando a: {url}")

            await self.page.goto(url, wait_until="networkidle", timeout=self.portal_config.timeouts["navigation"])

            current_url = self.page.url
            current_step.url_after = current_url

            # Screenshot
            screenshot_path = await self._take_screenshot(f"navigate_{current_step.step_number}")
            current_step.screenshot_path = screenshot_path

            current_step.success = True
            current_step.execution_time = time.time() - step_start

            self._log(f"✅ Navegación exitosa a: {current_url}")
            return {"success": True, "url": current_url}

        except Exception as e:
            current_step.success = False
            current_step.error_message = str(e)
            current_step.execution_time = time.time() - step_start

            self._log(f"❌ Error navegando a {url}: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    async def _analyze_current_page(self) -> Dict[str, Any]:
        """Análisis profundo de página actual"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.EXTRACT_DOM, "Analizando página actual")

        try:
            self._log("🔍 Analizando página actual...")

            # JavaScript evaluation para análisis completo
            analysis = await self.page.evaluate("""
                (config) => {
                    const invoiceIndicators = config.invoice_indicators;
                    const formIndicators = config.form_indicators;
                    const successIndicators = config.success_indicators;

                    // Análisis de texto de página
                    const pageText = (document.body.textContent || '').toLowerCase();

                    // Buscar elementos de facturación
                    const invoiceElements = [];
                    document.querySelectorAll('a, button, input[type="button"], input[type="submit"]').forEach((el, index) => {
                        const text = (el.textContent || el.value || '').toLowerCase();
                        const href = el.href || '';
                        const id = el.id || '';
                        const className = el.className || '';

                        const hasInvoiceKeyword = invoiceIndicators.some(keyword =>
                            text.includes(keyword) || href.includes(keyword) ||
                            id.includes(keyword) || className.includes(keyword)
                        );

                        if (hasInvoiceKeyword && el.offsetParent !== null) {
                            invoiceElements.push({
                                index: index,
                                tag: el.tagName,
                                text: (el.textContent || el.value || '').trim(),
                                href: href,
                                id: id,
                                className: className,
                                visible: true
                            });
                        }
                    });

                    // Análisis de formularios
                    const forms = Array.from(document.forms).map((form, index) => ({
                        index: index,
                        id: form.id,
                        action: form.action,
                        method: form.method,
                        inputCount: form.elements.length,
                        hasInvoiceFields: Array.from(form.elements).some(el => {
                            const name = (el.name || '').toLowerCase();
                            const id = (el.id || '').toLowerCase();
                            return formIndicators.some(indicator =>
                                name.includes(indicator) || id.includes(indicator)
                            );
                        })
                    }));

                    // Detectar indicadores de éxito
                    const hasSuccessIndicators = successIndicators.some(indicator =>
                        pageText.includes(indicator.toLowerCase())
                    );

                    return {
                        url: window.location.href,
                        title: document.title,
                        pageText: pageText.slice(0, 1000),
                        invoiceElements: invoiceElements,
                        forms: forms,
                        hasInvoiceElements: invoiceElements.length > 0,
                        hasInvoiceOptions: hasSuccessIndicators || forms.some(f => f.hasInvoiceFields),
                        totalButtons: document.querySelectorAll('button, input[type="button"]').length,
                        totalLinks: document.querySelectorAll('a[href]').length,
                        hasPostBack: document.body.innerHTML.includes('__doPostBack')
                    };
                }
            """, {
                "invoice_indicators": self.portal_config.invoice_indicators,
                "form_indicators": self.portal_config.form_indicators,
                "success_indicators": self.portal_config.success_indicators
            })

            current_step.data = analysis
            current_step.elements_found = len(analysis.get("invoiceElements", []))
            current_step.success = True
            current_step.execution_time = time.time() - step_start

            self._log(f"📊 Análisis completado: {len(analysis.get('invoiceElements', []))} elementos de facturación")
            return analysis

        except Exception as e:
            current_step.success = False
            current_step.error_message = str(e)
            current_step.execution_time = time.time() - step_start

            self._log(f"❌ Error analizando página: {e}", "ERROR")
            return {"error": str(e)}

    async def _execute_invoice_navigation(self) -> Dict[str, Any]:
        """Ejecutar navegación a sección de facturación usando estrategias configuradas"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.CLICK_ELEMENT, "Navegando a sección de facturación")

        try:
            self._log("🎯 Ejecutando navegación a facturación...")

            # Ordenar estrategias por prioridad
            strategies = sorted(self.portal_config.navigation_strategies, key=lambda x: x["priority"])

            for strategy in strategies:
                try:
                    self._log(f"🔧 Probando estrategia: {strategy['name']}")

                    # Verificar si el elemento existe
                    element = self.page.locator(strategy["selector"]).first

                    if await element.count() > 0:
                        # Verificar visibilidad
                        is_visible = await element.is_visible()
                        if not is_visible:
                            self._log(f"   ⚠️ Elemento existe pero no es visible")
                            continue

                        self._log(f"   ✅ Elemento encontrado y visible")

                        # Screenshot antes del click
                        await self._take_screenshot(f"before_click_{current_step.step_number}")

                        # Obtener URL antes del click
                        url_before = self.page.url
                        current_step.url_before = url_before

                        # Hacer click
                        await element.click(timeout=self.portal_config.timeouts["element"])

                        # Esperar navegación o cambios
                        try:
                            await self.page.wait_for_load_state("networkidle", timeout=15000)
                        except:
                            await asyncio.sleep(2)  # Esperar cambios dinámicos

                        # Verificar cambio de URL
                        url_after = self.page.url
                        current_step.url_after = url_after

                        # Screenshot después del click
                        await self._take_screenshot(f"after_click_{current_step.step_number}")

                        if url_after != url_before:
                            current_step.success = True
                            current_step.data = {
                                "strategy_used": strategy["name"],
                                "url_change": True,
                                "selector": strategy["selector"]
                            }
                            current_step.execution_time = time.time() - step_start

                            self._log(f"🎉 Navegación exitosa: {url_before} → {url_after}")
                            return {"success": True, "strategy": strategy["name"], "final_url": url_after}
                        else:
                            self._log(f"   ⚠️ Click realizado pero sin cambio de URL")
                            # Continuar con siguiente estrategia

                    else:
                        self._log(f"   ❌ Elemento no encontrado: {strategy['selector']}")

                except Exception as e:
                    self._log(f"   ❌ Error con estrategia {strategy['name']}: {e}")
                    continue

            # Si llegamos aquí, todas las estrategias fallaron
            # Intentar navegación directa como última opción
            self._log("🔄 Todas las estrategias fallaron, intentando navegación directa...")

            for url in self.portal_config.base_urls[1:]:  # Skip first URL (already tried)
                try:
                    await self.page.goto(url, wait_until="networkidle", timeout=30000)
                    current_step.success = True
                    current_step.data = {"strategy_used": "direct_navigation", "url": url}
                    current_step.execution_time = time.time() - step_start

                    self._log(f"✅ Navegación directa exitosa a: {url}")
                    return {"success": True, "strategy": "direct_navigation", "final_url": url}
                except Exception as e:
                    self._log(f"❌ Navegación directa falló para {url}: {e}")
                    continue

            # Todo falló
            current_step.success = False
            current_step.error_message = "All navigation strategies failed"
            current_step.execution_time = time.time() - step_start

            return {"success": False, "message": "All navigation strategies failed"}

        except Exception as e:
            current_step.success = False
            current_step.error_message = str(e)
            current_step.execution_time = time.time() - step_start

            self._log(f"❌ Error ejecutando navegación: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    async def _validate_invoice_page(self) -> Dict[str, Any]:
        """Validar que llegamos a página de formularios de facturación"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.VALIDATE_SUCCESS, "Validando página de facturación")

        try:
            self._log("🔍 Validando llegada a formularios de facturación...")

            # Re-analizar página actual para validación
            analysis = await self._analyze_current_page()

            # Screenshot final
            await self._take_screenshot(f"final_validation_{current_step.step_number}")

            # Determinar éxito basado en indicadores
            has_forms = len(analysis.get("forms", [])) > 0
            has_invoice_options = analysis.get("hasInvoiceOptions", False)
            has_success_indicators = any(
                indicator.lower() in analysis.get("pageText", "").lower()
                for indicator in self.portal_config.success_indicators
            )

            success = has_invoice_options or has_success_indicators

            current_step.success = success
            current_step.data = {
                "has_forms": has_forms,
                "has_invoice_options": has_invoice_options,
                "has_success_indicators": has_success_indicators,
                "final_analysis": analysis
            }
            current_step.execution_time = time.time() - step_start

            if success:
                self._log("🎉 ¡Validación exitosa! Llegamos a formularios de facturación")
            else:
                self._log("⚠️ Validación falló: No se detectaron formularios de facturación")

            return analysis

        except Exception as e:
            current_step.success = False
            current_step.error_message = str(e)
            current_step.execution_time = time.time() - step_start

            self._log(f"❌ Error validando página: {e}", "ERROR")
            return {"error": str(e)}

    async def _take_screenshot(self, name: str) -> Optional[str]:
        """Tomar screenshot con nombre descriptivo"""
        try:
            timestamp = int(time.time())
            screenshot_name = f"{name}_{timestamp}.png"
            screenshot_path = self.screenshots_dir / screenshot_name

            await self.page.screenshot(path=str(screenshot_path), full_page=True)

            self._log(f"📸 Screenshot guardado: {screenshot_name}")
            return screenshot_name

        except Exception as e:
            self._log(f"⚠️ Error tomando screenshot: {e}", "WARNING")
            return None

    def _create_step(self, action_type: PlaywrightActionType, description: str) -> PlaywrightStep:
        """Crear nuevo paso de seguimiento"""
        self.current_step += 1
        step = PlaywrightStep(
            step_number=self.current_step,
            action_type=action_type,
            description=description,
            timestamp=datetime.now().isoformat()
        )
        self.steps.append(step)
        return step

    def _finalize_result(self, result: Dict[str, Any], success: bool, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Finalizar resultado con resumen completo"""
        result.update({
            "success": success,
            "message": message,
            "steps": [asdict(step) for step in self.steps],
            "final_url": self.page.url if self.page else "unknown",
            "execution_summary": {
                "total_steps": len(self.steps),
                "successful_steps": sum(1 for step in self.steps if step.success),
                "total_time": time.time() - self.start_time,
                "screenshots": [step.screenshot_path for step in self.steps if step.screenshot_path]
            }
        })

        if data:
            result["final_analysis"] = data

        return result

    async def cleanup(self):
        """Limpiar recursos de Playwright"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self._log("🧹 Recursos de Playwright liberados")
        except Exception as e:
            self._log(f"⚠️ Error limpiando recursos: {e}", "WARNING")

    # Métodos adicionales para compatibilidad con RobustAutomationEngine

    async def get_execution_summary(self) -> Dict[str, Any]:
        """Resumen de ejecución compatible"""
        return {
            "total_steps": len(self.steps),
            "successful_steps": sum(1 for step in self.steps if step.success),
            "success_rate": sum(1 for step in self.steps if step.success) / len(self.steps) if self.steps else 0,
            "total_execution_time": time.time() - self.start_time,
            "final_url": self.page.url if self.page else None,
            "steps_summary": [
                {
                    "step": step.step_number,
                    "action": step.action_type.value,
                    "success": step.success,
                    "time": step.execution_time,
                    "description": step.description
                }
                for step in self.steps
            ]
        }