"""
Playwright Simple Engine para Litromil
Implementación focused y específica para automatizar litromil.com
"""

import asyncio
import logging
import time
import json
from typing import Dict, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright

logger = logging.getLogger(__name__)

class PlaywrightLitromilEngine:
    def __init__(self, ticket_id: int):
        self.ticket_id = ticket_id
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        self.execution_log = []
        self.start_time = time.time()

    def _log(self, message: str, level: str = "INFO"):
        """Log message con timestamp"""
        timestamp = time.time() - self.start_time
        log_entry = f"[{timestamp:.2f}s] {level}: {message}"
        self.execution_log.append(log_entry)
        if level == "ERROR":
            logger.error(log_entry)
        else:
            logger.info(log_entry)

    async def initialize(self) -> bool:
        """Inicializar Playwright"""
        try:
            self._log("Inicializando Playwright...")

            self.playwright = await async_playwright().start()

            # Browser con configuración optimizada
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Visible para debugging
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )

            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            self.page = await self.context.new_page()

            # Console logging
            self.page.on("console", lambda msg: self._log(f"Console: {msg.text}"))

            self._log("✅ Playwright inicializado correctamente")
            return True

        except Exception as e:
            self._log(f"❌ Error inicializando Playwright: {e}", "ERROR")
            return False

    async def automate_litromil_invoice(self, start_url: str = "https://litromil.com") -> Dict[str, Any]:
        """
        Automatización específica para litromil.com
        """
        results = {
            "success": False,
            "steps": [],
            "final_url": start_url,
            "execution_log": [],
            "screenshots": []
        }

        try:
            # Paso 1: Navegar a litromil.com
            self._log(f"🚀 Navegando a {start_url}")
            await self.page.goto(start_url, wait_until="networkidle", timeout=30000)

            current_url = self.page.url
            self._log(f"📍 URL actual: {current_url}")

            # Screenshot inicial
            screenshot1 = f"pw_step1_initial_{int(time.time())}.png"
            await self.page.screenshot(path=f"/Users/danielgoes96/Desktop/mcp-server/static/automation_screenshots/{screenshot1}")
            results["screenshots"].append(screenshot1)

            # Paso 2: Buscar enlaces de facturación
            self._log("🔍 Buscando elementos de facturación...")

            facturar_elements = await self.page.evaluate("""
                () => {
                    const elements = [];
                    const links = document.querySelectorAll('a');

                    links.forEach((link, index) => {
                        const text = link.textContent?.toLowerCase() || '';
                        const href = link.href || '';

                        if (text.includes('factur') || href.includes('factur') || href.includes('litromil')) {
                            elements.push({
                                index: index,
                                text: link.textContent?.trim(),
                                href: href,
                                visible: link.offsetParent !== null,
                                classes: link.className
                            });
                        }
                    });

                    return elements;
                }
            """)

            self._log(f"🎯 Encontrados {len(facturar_elements)} elementos de facturación")
            for elem in facturar_elements:
                self._log(f"   - '{elem['text']}' → {elem['href']}")

            # Paso 3: Intentar click en el enlace principal de facturación
            target_url = None
            for elem in facturar_elements:
                if elem.get('href') and 'litromil.dynalias.net:8088' in elem['href'] and elem.get('visible'):
                    target_url = elem['href']
                    link_text = elem['text']
                    self._log(f"🎯 Seleccionado: '{link_text}' → {target_url}")
                    break

            if not target_url:
                self._log("❌ No se encontró enlace válido de facturación", "ERROR")
                return results

            # Paso 4: Click en el enlace
            try:
                self._log(f"👆 Haciendo click en enlace de facturación...")

                # Estrategias múltiples para el click
                success = False

                # Estrategia 1: Click normal
                try:
                    link_locator = self.page.locator(f'a[href="{target_url}"]').first
                    await link_locator.click(timeout=10000)

                    # Esperar navegación con timeout más corto
                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        await asyncio.sleep(2)

                    new_url = self.page.url
                    if new_url != current_url:
                        success = True
                        self._log(f"✅ Click normal exitoso: {new_url}")
                except Exception as e:
                    self._log(f"⚠️ Click normal falló: {e}")

                # Estrategia 2: Navegación directa si el click falló
                if not success:
                    self._log(f"🔄 Intentando navegación directa a: {target_url}")
                    await self.page.goto(target_url, wait_until="networkidle", timeout=30000)
                    new_url = self.page.url
                    success = True
                    self._log(f"✅ Navegación directa exitosa: {new_url}")

                # Verificar que llegamos al portal correcto
                if 'litromil.dynalias.net' not in new_url:
                    self._log("⚠️ No llegamos al portal interno, reintentando...")
                    await self.page.goto("http://litromil.dynalias.net:8088/litromil/", wait_until="networkidle", timeout=30000)
                    new_url = self.page.url

                self._log(f"📍 URL final tras navegación: {new_url}")

                # Screenshot después del click
                screenshot2 = f"pw_step2_after_click_{int(time.time())}.png"
                await self.page.screenshot(path=f"/Users/danielgoes96/Desktop/mcp-server/static/automation_screenshots/{screenshot2}")
                results["screenshots"].append(screenshot2)

            except Exception as click_error:
                self._log(f"❌ Error en click: {click_error}", "ERROR")
                return results

            # Paso 5: Buscar botón de facturación en la nueva página
            self._log("🔍 Buscando botón 'Facturar' en portal interno...")

            # Esperar que la página cargue completamente
            await asyncio.sleep(3)

            # Buscar botón facturar
            facturar_buttons = await self.page.evaluate("""
                () => {
                    const buttons = [];

                    // Buscar todos los botones con texto "facturar"
                    document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach((btn, index) => {
                        const text = (btn.textContent || btn.value || '').toLowerCase();
                        const id = btn.id || '';
                        const onclick = btn.onclick?.toString() || '';

                        if (text.includes('facturar') || id.includes('facturar') || onclick.includes('facturar')) {
                            buttons.push({
                                index: index,
                                text: btn.textContent?.trim() || btn.value,
                                id: id,
                                onclick: onclick,
                                visible: btn.offsetParent !== null,
                                tag: btn.tagName
                            });
                        }
                    });

                    return buttons;
                }
            """)

            self._log(f"🎯 Encontrados {len(facturar_buttons)} botones de facturación")
            for btn in facturar_buttons:
                self._log(f"   - {btn['tag']} #{btn['id']}: '{btn['text']}' (visible: {btn['visible']})")

            # Paso 6: Click en botón facturar
            if facturar_buttons:
                target_button = None

                # Priorizar botón con id="facturar"
                for btn in facturar_buttons:
                    if btn.get('id') == 'facturar' and btn.get('visible'):
                        target_button = btn
                        break

                # Si no hay con id, tomar el primero visible
                if not target_button:
                    for btn in facturar_buttons:
                        if btn.get('visible'):
                            target_button = btn
                            break

                if target_button:
                    self._log(f"👆 Haciendo click en botón: {target_button['id']} - '{target_button['text']}'")

                    try:
                        # Click directo por ID si está disponible
                        if target_button.get('id'):
                            button_locator = self.page.locator(f"#{target_button['id']}")
                        else:
                            button_locator = self.page.locator("button").filter(has_text=target_button['text']).first

                        await button_locator.click(timeout=10000)

                        # Esperar navegación o cambios
                        try:
                            await self.page.wait_for_load_state("networkidle", timeout=15000)
                        except:
                            await asyncio.sleep(3)  # Esperar cambios dinámicos

                        final_url = self.page.url
                        self._log(f"📍 URL final: {final_url}")

                        # Screenshot final
                        screenshot3 = f"pw_step3_final_{int(time.time())}.png"
                        await self.page.screenshot(path=f"/Users/danielgoes96/Desktop/mcp-server/static/automation_screenshots/{screenshot3}")
                        results["screenshots"].append(screenshot3)

                        # Verificar si llegamos a formularios
                        forms_info = await self.page.evaluate("""
                            () => {
                                const forms = Array.from(document.forms).map(form => ({
                                    id: form.id,
                                    inputs: Array.from(form.elements).length
                                }));

                                // Buscar texto de opciones de facturación de manera más compatible
                                const pageText = document.body.textContent || '';
                                const hasEstacion = pageText.includes('Estación') || pageText.includes('estacion');
                                const hasFolio = pageText.includes('Folio') || pageText.includes('folio');
                                const hasWebId = pageText.includes('Web ID') || pageText.includes('webid');

                                // También buscar botones específicos
                                const buttons = Array.from(document.querySelectorAll('button, input[type="button"]'));
                                const buttonTexts = buttons.map(btn => btn.textContent || btn.value || '').join(' ').toLowerCase();

                                return {
                                    forms: forms,
                                    hasInvoiceOptions: hasEstacion || hasFolio || hasWebId,
                                    hasEstacion,
                                    hasFolio,
                                    hasWebId,
                                    pageText: pageText.slice(0, 500),
                                    buttonTexts: buttonTexts,
                                    totalButtons: buttons.length
                                };
                            }
                        """)

                        self._log(f"📋 Análisis final: {json.dumps(forms_info, indent=2)}")

                        if forms_info.get('hasInvoiceOptions'):
                            self._log("🎉 ¡ÉXITO! Llegamos a la página de opciones de facturación")
                            results["success"] = True
                            results["message"] = "Navegación exitosa a formularios de facturación"
                        else:
                            self._log("⚠️ Navegación completada pero no se detectaron formularios de facturación")

                        results["final_analysis"] = forms_info
                        results["final_url"] = final_url

                    except Exception as btn_error:
                        self._log(f"❌ Error haciendo click en botón: {btn_error}", "ERROR")
                else:
                    self._log("❌ No se encontró botón de facturación clickeable", "ERROR")
            else:
                self._log("❌ No se encontraron botones de facturación", "ERROR")

        except Exception as e:
            self._log(f"❌ Error general: {e}", "ERROR")

        finally:
            results["execution_log"] = self.execution_log
            results["total_time"] = time.time() - self.start_time

        return results

    async def cleanup(self):
        """Limpiar recursos"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self._log("🧹 Recursos limpiados")
        except Exception as e:
            self._log(f"Error limpiando: {e}", "ERROR")

# Función helper para testing
async def test_playwright_litromil(ticket_id: int = 86):
    """Test function para probar Playwright con litromil"""
    engine = PlaywrightLitromilEngine(ticket_id)

    try:
        if not await engine.initialize():
            return {"success": False, "error": "Failed to initialize"}

        result = await engine.automate_litromil_invoice()
        return result

    finally:
        await engine.cleanup()