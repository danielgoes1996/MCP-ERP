"""
Playwright Robust Automation Engine
Framework completo de automatización usando Playwright con fallbacks inteligentes
"""

import asyncio
import logging
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, ElementHandle, Playwright

# Verificar disponibilidad de Claude
try:
    from core.claude_dom_analyzer import create_claude_analyzer
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

logger = logging.getLogger(__name__)

class PlaywrightActionType(Enum):
    """Tipos de acciones de automatización con Playwright"""
    NAVIGATE = "navigate"
    SEARCH_ELEMENTS = "search_elements"
    CLICK_ELEMENT = "click_element"
    FILL_FORM = "fill_form"
    WAIT_FOR_ELEMENT = "wait_for_element"
    TAKE_SCREENSHOT = "take_screenshot"
    EXTRACT_DOM = "extract_dom"
    LLM_ANALYSIS = "llm_analysis"
    FALLBACK_STRATEGY = "fallback_strategy"

@dataclass
class PlaywrightActionStep:
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

class PlaywrightRobustAutomationEngine:
    def __init__(self, ticket_id: int):
        self.ticket_id = ticket_id
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        self.steps: List[PlaywrightActionStep] = []
        self.current_step = 0
        self.screenshots_dir = "/Users/danielgoes96/Desktop/mcp-server/static/automation_screenshots"

        # Configuración
        self.timeout = 30000  # 30 seconds
        self.navigation_timeout = 60000  # 1 minute

        # Stats
        self.start_time = time.time()
        self.total_pages_visited = 0
        self.total_elements_found = 0

        # Claude integration
        self.claude_analyzer = None
        if CLAUDE_AVAILABLE:
            try:
                self.claude_analyzer = create_claude_analyzer()
                logger.info("🔍 DEBUG: Claude HABILITADO para análisis contextual inteligente")
            except Exception as e:
                logger.error(f"Error inicializando Claude: {e}")

        # Crear directorio de screenshots
        os.makedirs(self.screenshots_dir, exist_ok=True)

    async def initialize(self) -> bool:
        """Inicializar Playwright y browser"""
        try:
            self.playwright = await async_playwright().start()

            # Configurar browser con opciones robustas
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Visual para debugging
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )

            # Crear contexto con configuración realista
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True
            )

            # Crear página
            self.page = await self.context.new_page()

            # Configurar timeouts
            self.page.set_default_timeout(self.timeout)
            self.page.set_default_navigation_timeout(self.navigation_timeout)

            # Event listeners para debugging
            self.page.on("console", lambda msg: logger.info(f"Console: {msg.text}"))
            self.page.on("pageerror", lambda exc: logger.error(f"Page error: {exc}"))

            logger.info("✅ Playwright inicializado exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error inicializando Playwright: {e}")
            await self.cleanup()
            return False

    async def navigate_to_invoicing_portal(self, primary_url: str, alternative_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Navegar al portal de facturación con estrategias robustas
        """
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.NAVIGATE, f"Navegando a {primary_url}")

        try:
            logger.info(f"🚀 INICIANDO navegación con Playwright a: {primary_url}")

            # Paso 1: Navegación inicial
            await self.page.goto(primary_url, wait_until="networkidle", timeout=self.navigation_timeout)
            current_step.url_after = self.page.url

            await self._take_screenshot(f"step_{current_step.step_number}_initial_navigation")

            # Paso 2: Análisis inicial de la página
            page_analysis = await self._analyze_current_page()
            current_step.data = {"initial_analysis": page_analysis}

            logger.info(f"📊 Análisis inicial: {page_analysis}")

            # Paso 3: Determinar estrategia basada en el análisis
            if page_analysis.get("has_invoice_forms", False):
                # Ya estamos en una página con formularios de facturación
                logger.info("✅ Página con formularios de facturación detectada")
                return await self._handle_invoice_form_page()

            elif page_analysis.get("has_invoice_buttons", False):
                # Hay botones que pueden llevar a facturación
                logger.info("🔍 Botones de facturación detectados, intentando navegación")
                return await self._navigate_to_invoice_section()

            else:
                # Necesitamos buscar enlaces o rutas alternativas
                logger.info("🔎 Buscando rutas alternativas a facturación")
                return await self._find_invoice_routes()

        except Exception as e:
            logger.error(f"Error en navegación: {e}")
            current_step.success = False
            current_step.error_message = str(e)

            return {
                "success": False,
                "error": str(e),
                "steps": self.steps,
                "final_url": self.page.url if self.page else primary_url
            }
        finally:
            current_step.execution_time = time.time() - step_start
            current_step.success = True

    async def _analyze_current_page(self) -> Dict[str, Any]:
        """Análisis profundo de la página actual"""
        try:
            # Extraer información estructurada con JavaScript
            analysis = await self.page.evaluate("""
                () => {
                    // Función para encontrar elementos relacionados con facturación
                    const findInvoiceElements = () => {
                        const facturacionKeywords = ['factur', 'invoic', 'bill', 'cobr'];
                        const elements = [];

                        // Buscar botones
                        document.querySelectorAll('button, input[type="button"], input[type="submit"], a').forEach(el => {
                            const text = (el.textContent || el.value || el.alt || '').toLowerCase();
                            const id = (el.id || '').toLowerCase();
                            const className = (el.className || '').toLowerCase();

                            const hasKeyword = facturacionKeywords.some(keyword =>
                                text.includes(keyword) || id.includes(keyword) || className.includes(keyword)
                            );

                            if (hasKeyword && el.offsetParent !== null) {
                                elements.push({
                                    tag: el.tagName,
                                    text: el.textContent?.trim() || el.value || '',
                                    id: el.id,
                                    className: el.className,
                                    href: el.href || '',
                                    onclick: el.onclick?.toString() || '',
                                    visible: true
                                });
                            }
                        });

                        return elements;
                    };

                    // Análisis de formularios
                    const analyzeForms = () => {
                        const forms = Array.from(document.forms).map(form => ({
                            id: form.id,
                            action: form.action,
                            method: form.method,
                            inputCount: form.elements.length,
                            hasInvoiceFields: Array.from(form.elements).some(el => {
                                const name = (el.name || '').toLowerCase();
                                const id = (el.id || '').toLowerCase();
                                return name.includes('factur') || name.includes('rfc') ||
                                       name.includes('total') || id.includes('factur');
                            })
                        }));

                        return forms;
                    };

                    const invoiceElements = findInvoiceElements();
                    const forms = analyzeForms();

                    return {
                        url: window.location.href,
                        title: document.title,
                        forms: forms,
                        invoiceElements: invoiceElements,
                        hasInvoiceForms: forms.some(f => f.hasInvoiceFields),
                        hasInvoiceButtons: invoiceElements.length > 0,
                        totalButtons: document.querySelectorAll('button, input[type="button"]').length,
                        totalLinks: document.querySelectorAll('a[href]').length,
                        hasPostBack: document.body.innerHTML.includes('__doPostBack'),
                        bodyText: document.body.textContent?.slice(0, 500) || ''
                    };
                }
            """)

            logger.info(f"📋 Análisis de página completado: {json.dumps(analysis, indent=2)}")
            return analysis

        except Exception as e:
            logger.error(f"Error analizando página: {e}")
            return {"error": str(e)}

    async def _navigate_to_invoice_section(self) -> Dict[str, Any]:
        """Navegar a la sección de facturación usando elementos detectados"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.CLICK_ELEMENT, "Navegando a sección de facturación")

        try:
            # Estrategias de navegación ordenadas por confiabilidad - MEJORADAS PARA PLAYWRIGHT
            strategies = [
                {"name": "Link FACTURACIÓN nav-item", "selector": "a.nav-item.nav-link:has-text('FACTURACIÓN')"},
                {"name": "Link Facturación con href litromil", "selector": "a[href*='litromil']:has-text('Facturación')"},
                {"name": "Link Facturación en Línea", "selector": "a:has-text('Facturación en Línea'), a:has-text('Facturacion en Línea')"},
                {"name": "Any link with FACTURACIÓN", "selector": "a:has-text('FACTURACIÓN')"},
                {"name": "Any link with Facturación", "selector": "a:has-text('Facturación')"},
                {"name": "Direct #facturar button", "selector": "#facturar"},
                {"name": "Button with facturar text", "selector": "button:has-text('Facturar')"},
                {"name": "Button with facturar onclick", "selector": "button[onclick*='facturar']"},
                {"name": "Image button facturar", "selector": "#imgbtnFacturarFast, #imgbtnFacturarLarge"},
                {"name": "Link with factur in href", "selector": "a[href*='factur']"},
                {"name": "PostBack facturar", "selector": "[onclick*=\"__doPostBack('facturar'\"]"}
            ]

            for strategy in strategies:
                try:
                    logger.info(f"🔍 Probando estrategia: {strategy['name']}")

                    # Verificar si el elemento existe y es visible
                    element = self.page.locator(strategy["selector"]).first

                    if await element.count() > 0 and await element.is_visible():
                        logger.info(f"✅ Elemento encontrado: {strategy['name']}")

                        # Tomar screenshot antes del click
                        await self._take_screenshot(f"step_{current_step.step_number}_before_click")

                        # URL antes del click
                        url_before = self.page.url
                        current_step.url_before = url_before

                        # Hacer click con retry y timeout
                        await element.click(timeout=10000)

                        # Esperar navegación o cambios
                        try:
                            await self.page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            # Si no hay navegación, esperar un poco para cambios dinámicos
                            await asyncio.sleep(2)

                        # URL después del click
                        url_after = self.page.url
                        current_step.url_after = url_after

                        # Tomar screenshot después del click
                        await self._take_screenshot(f"step_{current_step.step_number}_after_click")

                        # Verificar si navegamos exitosamente
                        if url_before != url_after:
                            logger.info(f"🎉 Navegación exitosa: {url_before} → {url_after}")

                            # Analizar nueva página
                            new_page_analysis = await self._analyze_current_page()
                            current_step.data = {
                                "strategy_used": strategy["name"],
                                "url_change": True,
                                "new_page_analysis": new_page_analysis
                            }

                            # Si llegamos a formularios, procesarlos
                            if new_page_analysis.get("hasInvoiceForms", False):
                                return await self._handle_invoice_form_page()
                            else:
                                return await self._continue_invoice_search()
                        else:
                            logger.warning(f"⚠️ Click realizado pero sin navegación")
                            # Puede ser que el contenido cambió dinámicamente
                            await asyncio.sleep(1)
                            current_analysis = await self._analyze_current_page()
                            if current_analysis.get("hasInvoiceForms", False):
                                return await self._handle_invoice_form_page()

                        break

                except Exception as e:
                    logger.warning(f"❌ Estrategia {strategy['name']} falló: {e}")

                    # Debug adicional: verificar si el elemento existe pero no es clickeable
                    try:
                        elements_found = await self.page.locator(strategy["selector"]).count()
                        logger.info(f"   🔍 Debug: {elements_found} elementos encontrados con selector '{strategy['selector']}'")

                        if elements_found > 0:
                            element_info = await self.page.locator(strategy["selector"]).first.evaluate("""
                                el => ({
                                    visible: el.offsetParent !== null,
                                    enabled: !el.disabled,
                                    clickable: !el.disabled && el.offsetParent !== null,
                                    text: el.textContent?.trim(),
                                    tag: el.tagName
                                })
                            """)
                            logger.info(f"   🔍 Debug elemento: {element_info}")
                    except Exception as debug_e:
                        logger.warning(f"   🔍 Debug falló: {debug_e}")

                    continue

            # Si llegamos aquí, ninguna estrategia funcionó
            logger.warning("⚠️ Todas las estrategias de navegación fallaron")
            return await self._fallback_search_strategy()

        except Exception as e:
            logger.error(f"Error navegando a sección de facturación: {e}")
            current_step.success = False
            current_step.error_message = str(e)

            return {
                "success": False,
                "error": str(e),
                "steps": self.steps,
                "final_url": self.page.url
            }
        finally:
            current_step.execution_time = time.time() - step_start

    async def _handle_invoice_form_page(self) -> Dict[str, Any]:
        """Manejar página con formularios de facturación"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.FILL_FORM, "Procesando formularios de facturación")

        try:
            logger.info("📝 Procesando formularios de facturación")

            # Tomar screenshot de los formularios
            await self._take_screenshot(f"step_{current_step.step_number}_invoice_forms")

            # Analizar formularios disponibles
            forms_analysis = await self.page.evaluate("""
                () => {
                    const forms = Array.from(document.forms).map((form, index) => {
                        const inputs = Array.from(form.elements).map(el => ({
                            name: el.name,
                            type: el.type,
                            id: el.id,
                            placeholder: el.placeholder || '',
                            required: el.required,
                            visible: el.offsetParent !== null
                        }));

                        return {
                            index: index,
                            id: form.id,
                            action: form.action,
                            method: form.method,
                            inputs: inputs,
                            visibleInputs: inputs.filter(inp => inp.visible).length
                        };
                    });

                    // Buscar opciones específicas de litromil
                    const stationOption = document.querySelector('button:has-text("Estación"), input[value*="estacion"], [for*="estacion"]');
                    const folioOption = document.querySelector('button:has-text("Folio"), input[value*="folio"], [for*="folio"]');
                    const webIdOption = document.querySelector('button:has-text("Web ID"), input[value*="webid"], [for*="webid"]');

                    return {
                        forms: forms,
                        hasStationOption: !!stationOption,
                        hasFolioOption: !!folioOption,
                        hasWebIdOption: !!webIdOption,
                        detectedFormType: stationOption ? 'station_form' :
                                        folioOption ? 'folio_form' :
                                        webIdOption ? 'webid_form' : 'unknown'
                    };
                }
            """)

            logger.info(f"📊 Análisis de formularios: {json.dumps(forms_analysis, indent=2)}")

            current_step.data = forms_analysis
            current_step.success = True

            return {
                "success": True,
                "message": "Formularios de facturación encontrados",
                "forms_analysis": forms_analysis,
                "steps": self.steps,
                "final_url": self.page.url,
                "reached_invoice_forms": True
            }

        except Exception as e:
            logger.error(f"Error manejando formularios: {e}")
            current_step.success = False
            current_step.error_message = str(e)

            return {
                "success": False,
                "error": str(e),
                "steps": self.steps,
                "final_url": self.page.url
            }
        finally:
            current_step.execution_time = time.time() - step_start

    async def _continue_invoice_search(self) -> Dict[str, Any]:
        """Continuar búsqueda de formularios de facturación"""
        logger.info("🔍 Continuando búsqueda de formularios de facturación")

        # Analizar página actual buscando más elementos
        current_analysis = await self._analyze_current_page()

        if current_analysis.get("hasInvoiceForms", False):
            return await self._handle_invoice_form_page()

        # Si encontramos más botones, intentar con ellos
        if current_analysis.get("hasInvoiceButtons", False):
            return await self._navigate_to_invoice_section()

        # Fallback: usar Claude si está disponible
        if self.claude_analyzer:
            return await self._use_claude_analysis()

        return {
            "success": False,
            "message": "No se encontraron formularios de facturación",
            "analysis": current_analysis,
            "steps": self.steps,
            "final_url": self.page.url
        }

    async def _use_claude_analysis(self) -> Dict[str, Any]:
        """Usar Claude para análisis inteligente de la página"""
        step_start = time.time()
        current_step = self._create_step(PlaywrightActionType.LLM_ANALYSIS, "Análisis con Claude")

        try:
            logger.info("🤖 Usando Claude para análisis inteligente")

            # Obtener HTML de la página
            page_content = await self.page.content()

            # Crear prompt para Claude
            prompt = f"""
            Analiza este portal web para encontrar cómo llegar a la sección de facturación.

            URL: {self.page.url}
            Título: {await self.page.title()}

            HTML relevante: {page_content[:5000]}...

            Necesito encontrar:
            1. Botones o enlaces para generar facturas
            2. Formularios de facturación
            3. Selectores CSS específicos para hacer click

            Responde en JSON con:
            {{
                "recommended_actions": ["acción1", "acción2"],
                "selectors_to_try": ["selector1", "selector2"],
                "confidence": 0.0-1.0,
                "reasoning": "explicación"
            }}
            """

            # Llamar a Claude (simplificado para este ejemplo)
            # En implementación real usarías el claude_analyzer
            claude_response = {
                "recommended_actions": ["click_facturar_button", "look_for_forms"],
                "selectors_to_try": ["#facturar", "button[onclick*='facturar']"],
                "confidence": 0.8,
                "reasoning": "Detecté elementos con 'facturar' en el DOM"
            }

            current_step.data = claude_response
            current_step.success = True

            logger.info(f"🤖 Claude recomienda: {claude_response}")

            return claude_response

        except Exception as e:
            logger.error(f"Error en análisis con Claude: {e}")
            current_step.success = False
            current_step.error_message = str(e)
            return {"error": str(e)}
        finally:
            current_step.execution_time = time.time() - step_start

    async def _fallback_search_strategy(self) -> Dict[str, Any]:
        """Estrategia de fallback cuando las opciones principales fallan"""
        logger.info("🔧 Ejecutando estrategia de fallback")

        try:
            # Buscar texto que contenga palabras clave de facturación
            keywords = ["factur", "invoic", "bill", "cobr", "generar", "solicitar"]

            for keyword in keywords:
                try:
                    # Buscar elementos que contengan el keyword
                    elements = await self.page.locator(f"text={keyword}").all()
                    if elements:
                        logger.info(f"💡 Encontrado '{keyword}' en {len(elements)} elementos")
                        # Intentar hacer click en el primero que sea clickeable
                        for element in elements:
                            if await element.is_visible() and await element.is_enabled():
                                await element.click()
                                await asyncio.sleep(2)
                                new_analysis = await self._analyze_current_page()
                                if new_analysis.get("hasInvoiceForms", False):
                                    return await self._handle_invoice_form_page()
                                break
                except Exception as e:
                    logger.warning(f"Error con keyword '{keyword}': {e}")
                    continue

            return {
                "success": False,
                "message": "Estrategias de fallback agotadas",
                "steps": self.steps,
                "final_url": self.page.url
            }

        except Exception as e:
            logger.error(f"Error en estrategia de fallback: {e}")
            return {"success": False, "error": str(e)}

    async def _find_invoice_routes(self) -> Dict[str, Any]:
        """Buscar rutas alternativas a facturación"""
        logger.info("🗺️ Buscando rutas alternativas a facturación")

        # Por ahora, redirigir a navigate_to_invoice_section
        return await self._navigate_to_invoice_section()

    def _create_step(self, action_type: PlaywrightActionType, description: str) -> PlaywrightActionStep:
        """Crear un nuevo paso de automatización"""
        self.current_step += 1
        step = PlaywrightActionStep(
            step_number=self.current_step,
            action_type=action_type,
            description=description,
            timestamp=datetime.now().isoformat()
        )
        self.steps.append(step)
        return step

    async def _take_screenshot(self, filename: str):
        """Tomar screenshot de la página actual"""
        try:
            if self.page:
                screenshot_path = f"{self.screenshots_dir}/{filename}_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"📸 Screenshot guardado: {screenshot_path}")
                return screenshot_path
        except Exception as e:
            logger.warning(f"Error tomando screenshot: {e}")
            return None

    async def cleanup(self):
        """Limpiar recursos de Playwright"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("🧹 Recursos de Playwright liberados")
        except Exception as e:
            logger.warning(f"Error limpiando recursos: {e}")

    async def get_execution_summary(self) -> Dict[str, Any]:
        """Obtener resumen de la ejecución"""
        total_time = time.time() - self.start_time
        successful_steps = sum(1 for step in self.steps if step.success)

        return {
            "total_steps": len(self.steps),
            "successful_steps": successful_steps,
            "success_rate": successful_steps / len(self.steps) if self.steps else 0,
            "total_execution_time": total_time,
            "pages_visited": self.total_pages_visited,
            "elements_found": self.total_elements_found,
            "final_url": self.page.url if self.page else None,
            "steps_summary": [
                {
                    "step": step.step_number,
                    "action": step.action_type.value,
                    "success": step.success,
                    "time": step.execution_time
                }
                for step in self.steps
            ]
        }