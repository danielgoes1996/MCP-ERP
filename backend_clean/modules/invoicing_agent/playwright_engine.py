"""
Playwright-based Automation Engine
Implementación alternativa con mejor DOM extraction y manejo de elementos modernos
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)

class PlaywrightAutomationEngine:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def initialize(self):
        """Inicializar Playwright"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        self.page = await self.context.new_page()

        # Habilitar logs de red y consola
        self.page.on("console", lambda msg: logger.info(f"Console: {msg.text}"))

    async def extract_clean_dom(self, url: str) -> Dict[str, Any]:
        """
        Extrae DOM más limpio que Selenium
        Playwright maneja mejor JavaScript y elementos dinámicos
        """
        try:
            await self.page.goto(url, wait_until="networkidle")

            # Esperar que la página esté completamente cargada
            await self.page.wait_for_load_state("domcontentloaded")

            # Extraer información estructurada
            dom_info = await self.page.evaluate("""
                () => {
                    // Función para encontrar botones de facturación
                    const findInvoiceButtons = () => {
                        const buttons = [];
                        const selectors = [
                            'button[id*="factur"]',
                            'button[onclick*="factur"]',
                            'button[class*="factur"]',
                            'input[value*="factur"]',
                            'a[href*="factur"]'
                        ];

                        selectors.forEach(selector => {
                            document.querySelectorAll(selector).forEach(el => {
                                if (el.offsetParent !== null) { // Elemento visible
                                    buttons.push({
                                        tagName: el.tagName,
                                        id: el.id,
                                        className: el.className,
                                        textContent: el.textContent?.trim(),
                                        onclick: el.onclick?.toString(),
                                        href: el.href,
                                        selector: selector
                                    });
                                }
                            });
                        });

                        return buttons;
                    };

                    return {
                        url: window.location.href,
                        title: document.title,
                        forms: Array.from(document.forms).map(form => ({
                            id: form.id,
                            action: form.action,
                            method: form.method,
                            elements: form.elements.length
                        })),
                        invoiceButtons: findInvoiceButtons(),
                        allButtons: Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]'))
                            .filter(btn => btn.offsetParent !== null)
                            .map(btn => ({
                                id: btn.id,
                                className: btn.className,
                                textContent: btn.textContent?.trim() || btn.value,
                                type: btn.type
                            })),
                        hasPostBack: document.body.innerHTML.includes('__doPostBack'),
                        viewState: document.querySelector('input[name="__VIEWSTATE"]')?.value ? 'present' : 'absent'
                    };
                }
            """)

            return dom_info

        except Exception as e:
            logger.error(f"Error extracting DOM: {e}")
            return {}

    async def smart_click(self, selector: str) -> bool:
        """
        Click inteligente con mejor manejo que Selenium
        """
        try:
            # Esperar que el elemento esté visible y habilitado
            await self.page.wait_for_selector(selector, state="visible", timeout=10000)

            # Verificar que es clickeable
            element = self.page.locator(selector)
            await element.wait_for(state="attached")

            # Scroll si es necesario
            await element.scroll_into_view_if_needed()

            # Click con retry automático
            await element.click(timeout=5000)

            # Esperar navegación si ocurre
            try:
                await self.page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass  # No hay navegación, está bien

            return True

        except Exception as e:
            logger.error(f"Error clicking {selector}: {e}")
            return False

    async def find_facturar_button(self) -> Optional[str]:
        """
        Encuentra botón de facturar usando lógica mejorada de Playwright
        """
        dom_info = await self.extract_clean_dom(self.page.url)

        # Priorizar botones específicos de facturación
        if dom_info.get('invoiceButtons'):
            for btn in dom_info['invoiceButtons']:
                if 'facturar' in btn.get('textContent', '').lower():
                    if btn.get('id'):
                        return f"#{btn['id']}"
                    elif btn.get('className'):
                        return f".{btn['className'].split()[0]}"

        # Fallback a selectores directos
        fallback_selectors = [
            "#facturar",
            "button[onclick*='facturar']",
            "#imgbtnFacturarFast",
            "#imgbtnFacturarLarge"
        ]

        for selector in fallback_selectors:
            try:
                if await self.page.locator(selector).is_visible():
                    return selector
            except:
                continue

        return None

    async def navigate_invoice_flow(self, start_url: str) -> Dict[str, Any]:
        """
        Flujo completo de navegación de facturación
        """
        result = {
            'success': False,
            'steps': [],
            'final_url': '',
            'dom_info': {}
        }

        try:
            # Paso 1: Navegar a URL inicial
            await self.page.goto(start_url, wait_until="networkidle")
            result['steps'].append({
                'step': 1,
                'action': 'navigate',
                'url': self.page.url,
                'success': True
            })

            # Paso 2: Buscar y hacer click en facturar
            facturar_selector = await self.find_facturar_button()
            if facturar_selector:
                click_success = await self.smart_click(facturar_selector)
                result['steps'].append({
                    'step': 2,
                    'action': 'click_facturar',
                    'selector': facturar_selector,
                    'success': click_success
                })

                if click_success:
                    # Paso 3: Verificar llegada a formulario
                    await asyncio.sleep(2)  # Esperar carga
                    final_dom = await self.extract_clean_dom(self.page.url)

                    result['success'] = len(final_dom.get('forms', [])) > 0
                    result['final_url'] = self.page.url
                    result['dom_info'] = final_dom

        except Exception as e:
            logger.error(f"Error in navigation flow: {e}")
            result['error'] = str(e)

        return result

    async def cleanup(self):
        """Limpiar recursos"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

# Función de comparación para evaluar diferencias
async def compare_selenium_vs_playwright(url: str):
    """
    Compara extracción de DOM entre Selenium y Playwright
    """
    # Probar con Playwright
    pw_engine = PlaywrightAutomationEngine()
    await pw_engine.initialize()

    pw_result = await pw_engine.navigate_invoice_flow(url)
    await pw_engine.cleanup()

    return {
        'playwright_result': pw_result,
        'recommendation': 'playwright' if pw_result['success'] else 'selenium'
    }