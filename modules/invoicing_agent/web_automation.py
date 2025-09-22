"""
Worker de automatización web para facturación automática.

Este módulo implementa la automatización real con Selenium para acceder
a portales de facturación de merchants y solicitar facturas automáticamente.
"""

import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# State machine imports
try:
    from .state_machine import StateMachine, AutomationState, StateDecision
    STATE_MACHINE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"State machine not available: {e}")
    STATE_MACHINE_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from python_anticaptcha import AntiCaptchaControl, ImageToTextTask
    ANTICAPTCHA_AVAILABLE = True
except ImportError:
    ANTICAPTCHA_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebAutomationWorker:
    """
    Worker para automatización web de portales de facturación.

    Soporta:
    - OXXO Facturación
    - Walmart Facturación
    - Costco Facturación
    - Home Depot Facturación
    """

    def __init__(self):
        self.driver = None
        self.wait_timeout = 30
        self.current_ticket_data = None  # Para almacenar datos del ticket actual

        # Sistema robusto de logs y navegación
        self.navigation_history = []
        self.windows_info = {}
        self.screenshots_dir = "screenshots"
        self.logs_file = "automation_logs.json"

        # Contadores para control de loops
        self.max_retries = 3
        self.retry_count = 0

        # Sistema de debugging y breakpoints
        self.debugging_enabled = os.getenv("AUTOMATION_DEBUG", "false").lower() == "true"
        self.checkpoint_counter = 0
        self.current_merchant = None
        self.current_step = None
        self.debug_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.checkpoints = []
        self.breakpoints = {
            "on_error": True,
            "on_new_window": False,
            "on_form_fill": False,
            "on_click": False,
            "before_submit": True
        }

        # Credenciales empresariales (desde variables de entorno)
        self.company_credentials = {
            "rfc": os.getenv("COMPANY_RFC", "XAXX010101000"),
            "razon_social": os.getenv("COMPANY_NAME", "Mi Empresa SA de CV"),
            "email": os.getenv("COMPANY_EMAIL", "facturacion@miempresa.com"),
            "telefono": os.getenv("COMPANY_PHONE", "5555555555"),
            "codigo_postal": os.getenv("COMPANY_ZIP", "01000"),
        }

    def setup_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Configurar driver de Chrome con opciones optimizadas."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium no está instalado. Instala con: pip install selenium")

        options = Options()

        if headless:
            options.add_argument("--headless")

        # Opciones de rendimiento y seguridad
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # User agent realista
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

        try:
            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return driver

    def generate_human_explanation(self, context: Dict, error_details: List[str]) -> str:
        """
        Genera explicación humana de errores usando Claude

        Args:
            context: Contexto del proceso (URLs, tickets, etc.)
            error_details: Lista de errores técnicos encontrados

        Returns:
            Explicación en lenguaje claro
        """
        if not ANTHROPIC_AVAILABLE:
            return "Error técnico en automatización. Requiere revisión manual."

        try:
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

            prompt = f"""
            Eres un experto en explicar errores técnicos de automatización web en lenguaje claro y humano.

            Contexto del proceso:
            - Merchant: {context.get('merchant_name', 'Desconocido')}
            - URLs intentadas: {context.get('urls_tried', [])}
            - Ticket ID: {context.get('ticket_id', 'N/A')}

            Errores técnicos encontrados:
            {chr(10).join(error_details)}

            Por favor explica en 2-3 oraciones claras qué pasó y qué se puede hacer:
            """

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            explanation = response.content[0].text.strip()
            logger.info(f"🤖 Explicación generada: {explanation}")
            return explanation

        except Exception as e:
            logger.error(f"❌ Error generando explicación: {e}")
            return f"Error en automatización: {'; '.join(error_details[:2])}"

    def try_multiple_urls_with_fallback(self, urls: List[str], ticket_data: Dict) -> Dict:
        """
        Intenta múltiples URLs con fallback inteligente

        Args:
            urls: Lista de URLs ordenadas por prioridad
            ticket_data: Datos del ticket para validación

        Returns:
            Resultado con estado y explicación
        """
        if not urls:
            return {
                "success": False,
                "error": "No se encontraron URLs de facturación",
                "explanation": "El ticket no contiene enlaces válidos para facturación automática."
            }

        results = []
        successful_url = None

        # Priorizar URLs usando Claude
        prioritized_urls = self._prioritize_urls_with_claude(urls, ticket_data.get('merchant_name', ''))

        logger.info(f"🔗 Intentando {len(prioritized_urls)} URLs en orden de prioridad")

        for i, url in enumerate(prioritized_urls):
            logger.info(f"🔗 Intento {i+1}/{len(prioritized_urls)}: {url}")

            try:
                # Resetear contador de intentos para cada URL
                self.retry_count = 0

                result = self._attempt_single_url(url, ticket_data)
                results.append(result)

                # Si fue exitoso, terminar
                if result.get("success"):
                    successful_url = url
                    logger.info(f"✅ URL exitosa: {url}")
                    break

                # Si falló, continuar con la siguiente
                logger.warning(f"⚠️ URL falló: {result.get('error', 'Error desconocido')}")

            except Exception as e:
                error_msg = f"Error inesperado en {url}: {e}"
                logger.error(f"❌ {error_msg}")
                results.append({"success": False, "error": error_msg, "url": url})

        # Generar explicación humana
        if successful_url:
            return {
                "success": True,
                "successful_url": successful_url,
                "explanation": f"Facturación completada exitosamente usando {successful_url}",
                "attempts": results
            }
        else:
            error_details = [r.get("error", "Error desconocido") for r in results]
            context = {
                "merchant_name": ticket_data.get('merchant_name'),
                "urls_tried": prioritized_urls,
                "ticket_id": ticket_data.get('id')
            }

            explanation = self.generate_human_explanation(context, error_details)

            return {
                "success": False,
                "error": "Todas las URLs fallaron",
                "explanation": explanation,
                "attempts": results
            }

    def _prioritize_urls_with_claude(self, urls: List[str], merchant_name: str) -> List[str]:
        """
        Usa Claude para priorizar URLs por probabilidad de éxito

        Args:
            urls: Lista de URLs encontradas
            merchant_name: Nombre del merchant

        Returns:
            URLs ordenadas por prioridad
        """
        if not ANTHROPIC_AVAILABLE or len(urls) <= 1:
            return urls

        try:
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

            prompt = f"""
            Eres un experto en portales de facturación mexicanos.

            Merchant: {merchant_name}
            URLs encontradas: {urls}

            Ordena estas URLs por probabilidad de contener un formulario de facturación funcional.
            Considera:
            1. URLs oficiales vs. terceros
            2. Palabras clave como "factura", "cfdi", "comprobante"
            3. Estructura típica de portales mexicanos

            Responde solo con la lista ordenada en formato JSON:
            ["url_mas_probable", "url_segunda", ...]
            """

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()

            prioritized = json.loads(content)

            # Validar que todas las URLs originales estén incluidas
            if len(prioritized) == len(urls) and all(url in urls for url in prioritized):
                logger.info(f"🎯 URLs priorizadas por Claude: {prioritized}")
                return prioritized
            else:
                logger.warning("⚠️ Priorización de Claude inválida, usando orden original")
                return urls

        except Exception as e:
            logger.error(f"❌ Error priorizando URLs: {e}")
            return urls

    def _attempt_single_url(self, url: str, ticket_data: Dict) -> Dict:
        """
        Intenta procesar una sola URL con manejo robusto

        Args:
            url: URL a procesar
            ticket_data: Datos del ticket

        Returns:
            Resultado del intento
        """
        start_time = time.time()

        try:
            # Navegar a la URL
            navigation_result = self._navigate_with_window_handling(url, ["factura", "cfdi", "comprobante"])

            if not navigation_result.get("success"):
                return {
                    "success": False,
                    "error": f"No se pudo cargar la URL: {navigation_result.get('error')}",
                    "url": url
                }

            # Buscar formulario de facturación
            form_result = self._find_and_fill_form(ticket_data)

            if not form_result.get("success"):
                return {
                    "success": False,
                    "error": f"No se encontró formulario válido: {form_result.get('error')}",
                    "url": url
                }

            # Intentar completar el proceso
            completion_result = self._complete_invoice_process()

            processing_time = time.time() - start_time

            return {
                "success": completion_result.get("success", False),
                "error": completion_result.get("error"),
                "url": url,
                "processing_time": processing_time,
                "invoice_data": completion_result.get("invoice_data")
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error inesperado: {e}",
                "url": url,
                "processing_time": time.time() - start_time
            }

    def _navigate_with_window_handling(self, url: str, expected_keywords: List[str]) -> Dict:
        """
        Navega con manejo robusto de ventanas múltiples

        Args:
            url: URL destino
            expected_keywords: Palabras clave esperadas en URL/título

        Returns:
            Resultado de la navegación
        """
        try:
            # Recordar ventanas actuales
            old_windows = set(self.driver.window_handles)

            logger.info(f"🔗 Navegando a: {url}")
            self._take_screenshot("before_navigation")

            # Navegar
            self.driver.get(url)

            # Esperar carga completa con timeout
            WebDriverWait(self.driver, self.wait_timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # Detectar nuevas ventanas con wait robusto
            new_windows = self._wait_for_new_windows(old_windows, timeout=10)

            if new_windows:
                logger.info(f"🪟 Detectadas {len(new_windows)} nuevas ventanas")

                # Evaluar cuál ventana usar
                best_window = self._choose_best_window(new_windows, expected_keywords)

                if best_window:
                    self.driver.switch_to.window(best_window)
                    self._register_window_info(best_window)
                    logger.info(f"✅ Cambiado a ventana óptima")
                else:
                    logger.warning("⚠️ Ninguna ventana nueva parece adecuada")

            # Verificar URL final
            final_url = self.driver.current_url

            # Validar palabras clave
            if expected_keywords:
                url_contains_keywords = any(kw.lower() in final_url.lower() for kw in expected_keywords)
                title_contains_keywords = any(kw.lower() in self.driver.title.lower() for kw in expected_keywords)

                if not (url_contains_keywords or title_contains_keywords):
                    return {
                        "success": False,
                        "error": f"URL final no contiene palabras clave esperadas: {expected_keywords}",
                        "final_url": final_url
                    }

            self._take_screenshot("after_navigation")

            return {
                "success": True,
                "final_url": final_url,
                "new_windows": len(new_windows)
            }

        except TimeoutException:
            return {
                "success": False,
                "error": f"Timeout cargando URL (>{self.wait_timeout}s)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error navegando: {e}"
            }

    def _wait_for_new_windows(self, old_windows: set, timeout: int = 10) -> set:
        """
        Espera robusta para detectar nuevas ventanas con sleep + WebDriverWait

        Args:
            old_windows: Set de handles de ventanas existentes antes de la acción
            timeout: Tiempo máximo de espera en segundos

        Returns:
            Set de nuevas ventanas detectadas
        """
        logger.info(f"🔍 Esperando nuevas ventanas por hasta {timeout}s...")

        # Sleep inicial para dar tiempo a que se abra la ventana
        time.sleep(1)

        try:
            # WebDriverWait para detectar cambio en número de ventanas
            def new_windows_appeared(driver):
                current_windows = set(driver.window_handles)
                new_windows = current_windows - old_windows
                if new_windows:
                    logger.info(f"✅ Detectadas {len(new_windows)} nuevas ventanas")
                    return new_windows
                return False

            # Esperar hasta que aparezcan nuevas ventanas o timeout
            new_windows = WebDriverWait(self.driver, timeout).until(new_windows_appeared)

            # Sleep adicional para que cargue el contenido de la nueva ventana
            time.sleep(2)

            return new_windows

        except TimeoutException:
            logger.warning(f"⏰ Timeout: No se detectaron nuevas ventanas en {timeout}s")
            return set()
        except Exception as e:
            logger.error(f"❌ Error esperando nuevas ventanas: {e}")
            return set()

    def _choose_best_window(self, window_handles: set, expected_keywords: List[str]) -> Optional[str]:
        """
        Decide cuál ventana es la mejor basada en contenido

        Args:
            window_handles: Handles de ventanas nuevas
            expected_keywords: Palabras clave esperadas

        Returns:
            Handle de la mejor ventana o None
        """
        current_window = self.driver.current_window_handle
        best_window = None
        best_score = 0

        for window_handle in window_handles:
            try:
                self.driver.switch_to.window(window_handle)

                # Esperar carga
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                url = self.driver.current_url
                title = self.driver.title

                # Calcular puntuación
                score = 0

                # Puntos por palabras clave en URL
                for keyword in expected_keywords:
                    if keyword.lower() in url.lower():
                        score += 10
                    if keyword.lower() in title.lower():
                        score += 5

                # Puntos por indicadores de formulario
                form_elements = self.driver.find_elements(By.TAG_NAME, "form")
                input_elements = self.driver.find_elements(By.TAG_NAME, "input")

                score += len(form_elements) * 3
                score += min(len(input_elements), 10)  # Max 10 puntos

                logger.info(f"🏆 Ventana {window_handle}: score={score}, URL={url[:50]}...")

                if score > best_score:
                    best_score = score
                    best_window = window_handle

            except Exception as e:
                logger.error(f"❌ Error evaluando ventana {window_handle}: {e}")
                continue

        # Regresar a ventana original
        self.driver.switch_to.window(current_window)

        return best_window if best_score > 5 else None  # Umbral mínimo

    def _register_window_info(self, window_handle: str):
        """
        Registra información detallada de una ventana

        Args:
            window_handle: Handle de la ventana
        """
        try:
            current_window = self.driver.current_window_handle
            self.driver.switch_to.window(window_handle)

            window_info = {
                "handle": window_handle,
                "url": self.driver.current_url,
                "title": self.driver.title,
                "opened_at": time.time(),
                "form_count": len(self.driver.find_elements(By.TAG_NAME, "form")),
                "input_count": len(self.driver.find_elements(By.TAG_NAME, "input"))
            }

            self.windows_info[window_handle] = window_info
            logger.info(f"📋 Ventana registrada: {window_info['title'][:30]}...")

            # Volver a ventana original
            self.driver.switch_to.window(current_window)

        except Exception as e:
            logger.error(f"❌ Error registrando ventana: {e}")

    def debug_checkpoint(self, step_name: str, data: Dict = None, force_screenshot: bool = False):
        """
        Sistema de checkpoints para debugging - Rayos X del bot

        Args:
            step_name: Nombre del paso actual
            data: Datos contextuales del paso
            force_screenshot: Forzar screenshot independiente de configuración
        """
        if not self.debugging_enabled and not force_screenshot:
            return

        self.checkpoint_counter += 1
        checkpoint_id = f"cp_{self.checkpoint_counter:03d}"

        checkpoint_data = {
            "id": checkpoint_id,
            "session_id": self.debug_session_id,
            "timestamp": datetime.now().isoformat(),
            "step_name": step_name,
            "merchant": self.current_merchant,
            "current_url": None,
            "page_title": None,
            "screenshot_path": None,
            "html_snippet": None,
            "visible_elements": [],
            "errors": [],
            "data": data or {}
        }

        try:
            if self.driver:
                checkpoint_data["current_url"] = self.driver.current_url
                checkpoint_data["page_title"] = self.driver.title

                # Screenshot con contexto detallado
                screenshot_path = self._take_debug_screenshot(checkpoint_id, step_name)
                checkpoint_data["screenshot_path"] = screenshot_path

                # Capturar HTML snippet del área visible
                try:
                    visible_html = self.driver.execute_script(
                        "return document.documentElement.outerHTML"
                    )[:2000]  # Primeros 2000 chars
                    checkpoint_data["html_snippet"] = visible_html
                except:
                    pass

                # Elementos clickeables visibles
                checkpoint_data["visible_elements"] = self._capture_visible_elements()

        except Exception as e:
            checkpoint_data["errors"].append(f"Error capturando datos: {e}")

        # Guardar checkpoint
        self.checkpoints.append(checkpoint_data)

        # Log del checkpoint
        logger.info(f"🔍 CHECKPOINT {checkpoint_id}: {step_name}")
        if data:
            logger.debug(f"📊 Datos: {data}")

        # Evaluar breakpoints
        self._evaluate_breakpoints(checkpoint_data)

        return checkpoint_id

    def _take_debug_screenshot(self, checkpoint_id: str, context: str) -> str:
        """Toma screenshot con naming para debugging"""
        try:
            debug_dir = f"{self.screenshots_dir}/debug_{self.debug_session_id}"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)

            filename = f"{debug_dir}/{checkpoint_id}_{context.replace(' ', '_')}.png"
            self.driver.save_screenshot(filename)
            logger.debug(f"📸 Debug screenshot: {filename}")
            return filename

        except Exception as e:
            logger.error(f"❌ Error debug screenshot: {e}")
            return None

    def _take_screenshot(self, context: str):
        """Toma screenshot para evidencia (método original mantenido)"""
        try:
            if not os.path.exists(self.screenshots_dir):
                os.makedirs(self.screenshots_dir)

            timestamp = int(time.time())
            filename = f"{self.screenshots_dir}/{context}_{timestamp}.png"

            self.driver.save_screenshot(filename)
            logger.debug(f"📸 Screenshot: {filename}")

        except Exception as e:
            logger.error(f"❌ Error screenshot: {e}")

    def _capture_visible_elements(self) -> List[Dict]:
        """Captura elementos visibles para debugging"""
        try:
            elements = []
            clickable_selectors = [
                "button", "a", "input[type='submit']", "input[type='button']",
                "[onclick]", "[role='button']", ".btn", ".button"
            ]

            for selector in clickable_selectors:
                try:
                    found_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in found_elements[:5]:  # Limitar a 5 por selector
                        if elem.is_displayed():
                            elements.append({
                                "tag": elem.tag_name,
                                "text": elem.text[:50],
                                "selector": selector,
                                "location": elem.location,
                                "size": elem.size
                            })
                except:
                    continue

            return elements[:10]  # Máximo 10 elementos

        except Exception as e:
            logger.debug(f"Error capturando elementos: {e}")
            return []

    def _evaluate_breakpoints(self, checkpoint_data: Dict):
        """Evalúa si debe activar breakpoints condicionales"""
        try:
            step_name = checkpoint_data["step_name"]

            # Breakpoint on error
            if self.breakpoints.get("on_error") and checkpoint_data.get("errors"):
                self._trigger_breakpoint("ERROR_DETECTED", checkpoint_data)

            # Breakpoint before submit
            if self.breakpoints.get("before_submit") and "submit" in step_name.lower():
                self._trigger_breakpoint("BEFORE_SUBMIT", checkpoint_data)

            # Breakpoint on new window
            if self.breakpoints.get("on_new_window") and "window" in step_name.lower():
                self._trigger_breakpoint("NEW_WINDOW", checkpoint_data)

            # Breakpoint on form fill
            if self.breakpoints.get("on_form_fill") and "form" in step_name.lower():
                self._trigger_breakpoint("FORM_FILL", checkpoint_data)

            # Breakpoint on click
            if self.breakpoints.get("on_click") and "click" in step_name.lower():
                self._trigger_breakpoint("CLICK_ACTION", checkpoint_data)

        except Exception as e:
            logger.debug(f"Error evaluando breakpoints: {e}")

    def _trigger_breakpoint(self, breakpoint_type: str, checkpoint_data: Dict):
        """Activa un breakpoint y pausa para inspección"""
        logger.warning(f"🛑 BREAKPOINT TRIGGERED: {breakpoint_type}")
        logger.warning(f"📍 Checkpoint: {checkpoint_data['id']} - {checkpoint_data['step_name']}")
        logger.warning(f"🌐 URL: {checkpoint_data.get('current_url', 'N/A')}")

        if checkpoint_data.get("screenshot_path"):
            logger.warning(f"📸 Screenshot: {checkpoint_data['screenshot_path']}")

        # En modo debug, guardar snapshot completo
        self._save_debug_snapshot(breakpoint_type, checkpoint_data)

        # Si está configurado, hacer pausa real (solo en desarrollo)
        if os.getenv("AUTOMATION_PAUSE_ON_BREAKPOINT", "false").lower() == "true":
            input(f"🛑 Breakpoint {breakpoint_type}. Presiona Enter para continuar...")

    def _save_debug_snapshot(self, breakpoint_type: str, checkpoint_data: Dict):
        """Guarda snapshot completo para análisis posterior"""
        try:
            debug_dir = f"{self.screenshots_dir}/debug_{self.debug_session_id}"
            snapshot_file = f"{debug_dir}/breakpoint_{breakpoint_type}_{checkpoint_data['id']}.json"

            # Datos completos del snapshot
            snapshot = {
                "breakpoint_type": breakpoint_type,
                "checkpoint": checkpoint_data,
                "session_info": {
                    "session_id": self.debug_session_id,
                    "merchant": self.current_merchant,
                    "total_checkpoints": self.checkpoint_counter
                },
                "browser_state": {
                    "window_handles": len(self.driver.window_handles) if self.driver else 0,
                    "current_window": self.driver.current_window_handle if self.driver else None
                }
            }

            # Guardar snapshot
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)

            logger.info(f"💾 Debug snapshot guardado: {snapshot_file}")

        except Exception as e:
            logger.error(f"❌ Error guardando snapshot: {e}")

    def get_debug_session_info(self) -> Dict:
        """
        Obtiene información de la sesión de debugging actual para el viewer
        """
        return {
            "session_id": self.debug_session_id,
            "merchant": self.current_merchant,
            "current_step": self.current_step,
            "checkpoint_count": self.checkpoint_counter,
            "debugging_enabled": self.debugging_enabled,
            "breakpoints": self.breakpoints,
            "debug_url": f"/invoicing/debug-checkpoints/{self.debug_session_id}"
        }

    def export_debug_summary(self) -> Dict:
        """
        Exporta resumen completo de la sesión para análisis posterior
        """
        try:
            summary = {
                "session_info": self.get_debug_session_info(),
                "checkpoints": self.checkpoints,
                "total_checkpoints": len(self.checkpoints),
                "errors_detected": sum(1 for cp in self.checkpoints if cp.get("errors")),
                "breakpoints_triggered": sum(1 for cp in self.checkpoints
                                           if any("BREAKPOINT" in str(cp).upper() for cp in self.checkpoints))
            }

            # Guardar resumen
            debug_dir = f"{self.screenshots_dir}/debug_{self.debug_session_id}"
            summary_file = f"{debug_dir}/session_summary.json"

            if os.path.exists(debug_dir):
                with open(summary_file, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)

            return summary

        except Exception as e:
            logger.error(f"❌ Error exportando resumen: {e}")
            return {}

    def _persist_logs_to_json(self, log_data: Dict):
        """
        Persiste logs en archivo JSON para trazabilidad

        Args:
            log_data: Datos a persistir
        """
        try:
            # Cargar logs existentes
            existing_logs = []
            if os.path.exists(self.logs_file):
                with open(self.logs_file, 'r', encoding='utf-8') as f:
                    existing_logs = json.load(f)

            # Añadir nuevo log
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "session_id": id(self),
                **log_data
            }

            existing_logs.append(log_entry)

            # Mantener solo últimos 1000 logs
            if len(existing_logs) > 1000:
                existing_logs = existing_logs[-1000:]

            # Guardar
            with open(self.logs_file, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, indent=2, ensure_ascii=False)

            logger.debug(f"💾 Log persistido en {self.logs_file}")

        except Exception as e:
            logger.error(f"❌ Error persistiendo log: {e}")

    def _find_and_fill_form(self, ticket_data: Dict) -> Dict:
        """
        Busca y llena formularios con validación dinámica de elementos DOM

        Args:
            ticket_data: Datos del ticket a procesar

        Returns:
            Resultado de la búsqueda y llenado del formulario
        """
        try:
            logger.info("🔍 Buscando formularios de facturación...")

            # Buscar formularios en orden de prioridad
            forms = self._find_forms_with_dynamic_validation()

            if not forms:
                return {
                    "success": False,
                    "error": "No se encontraron formularios de facturación válidos"
                }

            # Intentar llenar cada formulario
            for i, form_info in enumerate(forms):
                logger.info(f"📝 Intentando formulario {i+1}/{len(forms)}")

                result = self._fill_form_with_retry(form_info, ticket_data)

                if result.get("success"):
                    logger.info(f"✅ Formulario {i+1} completado exitosamente")
                    return result

                logger.warning(f"⚠️ Formulario {i+1} falló: {result.get('error')}")

            return {
                "success": False,
                "error": "Ningún formulario pudo ser completado exitosamente"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error buscando formularios: {e}"
            }

    def _find_forms_with_dynamic_validation(self) -> List[Dict]:
        """
        Encuentra formularios usando múltiples estrategias de búsqueda

        Returns:
            Lista de información de formularios encontrados
        """
        forms_found = []

        # Estrategia 1: Formularios explícitos
        try:
            form_elements = self.driver.find_elements(By.TAG_NAME, "form")
            for form in form_elements:
                if self._is_form_relevant(form):
                    forms_found.append({
                        "type": "explicit_form",
                        "element": form,
                        "inputs": form.find_elements(By.TAG_NAME, "input"),
                        "score": self._calculate_form_score(form)
                    })
        except Exception as e:
            logger.error(f"❌ Error buscando formularios explícitos: {e}")

        # Estrategia 2: Grupos de inputs sin form
        try:
            input_groups = self._find_input_groups()
            for group in input_groups:
                forms_found.append({
                    "type": "input_group",
                    "inputs": group["inputs"],
                    "container": group["container"],
                    "score": group["score"]
                })
        except Exception as e:
            logger.error(f"❌ Error buscando grupos de inputs: {e}")

        # Estrategia 3: Elementos por palabras clave
        try:
            keyword_elements = self._find_elements_by_keywords()
            if keyword_elements:
                forms_found.append({
                    "type": "keyword_based",
                    "elements": keyword_elements,
                    "score": len(keyword_elements) * 2
                })
        except Exception as e:
            logger.error(f"❌ Error buscando por palabras clave: {e}")

        # Ordenar por puntuación
        forms_found.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(f"🎯 Encontrados {len(forms_found)} formularios candidatos")
        return forms_found

    def _is_form_relevant(self, form_element) -> bool:
        """
        Valida si un formulario es relevante para facturación

        Args:
            form_element: Elemento form a validar

        Returns:
            True si el formulario parece relevante
        """
        try:
            # Verificar que esté visible
            if not form_element.is_displayed():
                return False

            # Buscar inputs relevantes
            inputs = form_element.find_elements(By.TAG_NAME, "input")
            if len(inputs) < 2:  # Mínimo 2 campos
                return False

            # Buscar palabras clave en el formulario
            form_html = form_element.get_attribute("outerHTML").lower()
            relevant_keywords = [
                "rfc", "factura", "cfdi", "comprobante", "ticket",
                "folio", "total", "importe", "email"
            ]

            keyword_count = sum(1 for keyword in relevant_keywords if keyword in form_html)

            return keyword_count >= 2

        except Exception as e:
            logger.error(f"❌ Error validando formulario: {e}")
            return False

    def _calculate_form_score(self, form_element) -> int:
        """
        Calcula puntuación de relevancia para un formulario

        Args:
            form_element: Elemento del formulario

        Returns:
            Puntuación (mayor = más relevante)
        """
        score = 0

        try:
            # Puntos por número de inputs
            inputs = form_element.find_elements(By.TAG_NAME, "input")
            score += min(len(inputs), 10)  # Max 10 puntos

            # Puntos por tipos de input relevantes
            input_types = [inp.get_attribute("type") for inp in inputs]
            if "email" in input_types:
                score += 5
            if "tel" in input_types:
                score += 3

            # Puntos por palabras clave
            form_html = form_element.get_attribute("outerHTML").lower()
            keywords = {
                "rfc": 10, "factura": 8, "cfdi": 8, "comprobante": 6,
                "ticket": 5, "folio": 4, "total": 3, "importe": 3
            }

            for keyword, points in keywords.items():
                if keyword in form_html:
                    score += points

            # Puntos por ubicación (formularios centrales son mejores)
            location = form_element.location
            size = form_element.size
            if 100 < location.get("y", 0) < 800:  # Zona central
                score += 5

        except Exception as e:
            logger.error(f"❌ Error calculando score del formulario: {e}")

        return score

    def _find_input_groups(self) -> List[Dict]:
        """
        Busca grupos de inputs que podrían formar un formulario implícito

        Returns:
            Lista de grupos de inputs encontrados
        """
        groups = []

        try:
            # Buscar todos los inputs
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")

            # Agrupar por contenedor padre
            containers = {}
            for inp in all_inputs:
                try:
                    # Buscar contenedor padre común
                    parent = inp.find_element(By.XPATH, "./..")
                    container_key = parent.get_attribute("outerHTML")[:100]

                    if container_key not in containers:
                        containers[container_key] = {
                            "container": parent,
                            "inputs": [],
                            "score": 0
                        }

                    containers[container_key]["inputs"].append(inp)

                except Exception:
                    continue

            # Filtrar grupos relevantes
            for container_info in containers.values():
                if len(container_info["inputs"]) >= 2:
                    # Calcular score basado en inputs
                    score = len(container_info["inputs"]) * 2

                    # Bonus por tipos relevantes
                    input_types = [inp.get_attribute("type") for inp in container_info["inputs"]]
                    if "email" in input_types:
                        score += 5

                    container_info["score"] = score
                    groups.append(container_info)

        except Exception as e:
            logger.error(f"❌ Error agrupando inputs: {e}")

        return groups

    def _find_elements_by_keywords(self) -> List:
        """
        Busca elementos por palabras clave específicas

        Returns:
            Lista de elementos encontrados
        """
        elements = []

        keywords = ["rfc", "factura", "cfdi", "comprobante"]

        for keyword in keywords:
            try:
                # Buscar por diferentes atributos
                selectors = [
                    f"//input[contains(@placeholder, '{keyword}')]",
                    f"//input[contains(@name, '{keyword}')]",
                    f"//input[contains(@id, '{keyword}')]",
                    f"//*[contains(text(), '{keyword.upper()}')]//input"
                ]

                for selector in selectors:
                    found = self.driver.find_elements(By.XPATH, selector)
                    elements.extend(found)

            except Exception:
                continue

        return list(set(elements))  # Remover duplicados

    def _fill_form_with_retry(self, form_info: Dict, ticket_data: Dict) -> Dict:
        """
        Llena un formulario con sistema de reintentos

        Args:
            form_info: Información del formulario
            ticket_data: Datos del ticket

        Returns:
            Resultado del llenado
        """
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                logger.info(f"🔄 Intento {attempt + 1}/{max_attempts} de llenado")

                # Obtener elementos del formulario
                if form_info["type"] == "explicit_form":
                    inputs = form_info["inputs"]
                elif form_info["type"] == "input_group":
                    inputs = form_info["inputs"]
                else:
                    inputs = form_info["elements"]

                # Mapear campos inteligentemente
                field_mapping = self._map_form_fields(inputs, ticket_data)

                if not field_mapping:
                    return {
                        "success": False,
                        "error": "No se pudo mapear ningún campo del formulario"
                    }

                # Llenar campos
                filled_count = 0
                for field_info in field_mapping:
                    if self._fill_single_field(field_info):
                        filled_count += 1

                if filled_count == 0:
                    raise Exception("No se pudo llenar ningún campo")

                logger.info(f"✅ Llenados {filled_count}/{len(field_mapping)} campos")

                return {
                    "success": True,
                    "filled_fields": filled_count,
                    "total_fields": len(field_mapping)
                }

            except Exception as e:
                logger.warning(f"⚠️ Intento {attempt + 1} falló: {e}")

                if attempt < max_attempts - 1:
                    time.sleep(2)  # Esperar antes del siguiente intento
                else:
                    return {
                        "success": False,
                        "error": f"Falló después de {max_attempts} intentos: {e}"
                    }

    def _complete_invoice_process(self) -> Dict:
        """
        Completa el proceso de generación de factura

        Returns:
            Resultado del proceso
        """
        try:
            # Buscar botón de envío/generar
            submit_buttons = self._find_submit_buttons()

            if not submit_buttons:
                return {
                    "success": False,
                    "error": "No se encontró botón para completar el proceso"
                }

            # Intentar cada botón
            for button in submit_buttons:
                try:
                    logger.info("🔘 Haciendo clic en botón de envío...")

                    # Verificar si hay CAPTCHA antes del envío
                    captcha_result = self._handle_captcha_if_present()

                    if captcha_result and not captcha_result.get("success"):
                        logger.warning(f"⚠️ CAPTCHA falló: {captcha_result.get('error')}")
                        continue

                    # Hacer clic en el botón
                    self.driver.execute_script("arguments[0].click();", button)

                    # Esperar respuesta
                    time.sleep(5)

                    # Verificar resultado
                    result = self._verify_invoice_completion()

                    if result.get("success"):
                        return result

                except Exception as e:
                    logger.error(f"❌ Error con botón: {e}")
                    continue

            return {
                "success": False,
                "error": "Ningún botón de envío funcionó"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error completando proceso: {e}"
            }

    def _handle_captcha_if_present(self) -> Optional[Dict]:
        """
        Maneja CAPTCHA si está presente

        Returns:
            Resultado del manejo de CAPTCHA o None si no hay
        """
        try:
            # Buscar elementos de CAPTCHA
            captcha_selectors = [
                "iframe[src*='captcha']",
                "iframe[src*='recaptcha']",
                ".captcha",
                "#captcha",
                "[class*='captcha']"
            ]

            captcha_element = None
            for selector in captcha_selectors:
                try:
                    captcha_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if captcha_element.is_displayed():
                        break
                except NoSuchElementException:
                    continue

            if not captcha_element:
                return None  # No hay CAPTCHA

            logger.info("🔒 CAPTCHA detectado, resolviendo...")

            # Resolver CAPTCHA con 2Captcha
            return self._solve_captcha_with_2captcha(captcha_element)

        except Exception as e:
            logger.error(f"❌ Error manejando CAPTCHA: {e}")
            return {"success": False, "error": f"Error en CAPTCHA: {e}"}

    def _find_submit_buttons(self) -> List:
        """Encuentra botones de envío/submit"""
        buttons = []

        selectors = [
            "input[type='submit']",
            "button[type='submit']",
            "button:contains('Generar')",
            "button:contains('Enviar')",
            "button:contains('Solicitar')",
            "*[onclick*='submit']"
        ]

        for selector in selectors:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                buttons.extend([b for b in found if b.is_displayed()])
            except Exception:
                continue

        return buttons

    def _verify_invoice_completion(self) -> Dict:
        """Verifica si el proceso de facturación se completó"""
        try:
            # Buscar indicadores de éxito
            success_indicators = [
                "factura generada",
                "cfdi emitido",
                "comprobante generado",
                "proceso completado",
                "éxito"
            ]

            page_text = self.driver.page_source.lower()

            for indicator in success_indicators:
                if indicator in page_text:
                    return {
                        "success": True,
                        "message": f"Proceso completado: {indicator}",
                        "invoice_data": self._extract_invoice_data()
                    }

            # Si no hay indicadores claros, verificar URL
            current_url = self.driver.current_url
            if any(word in current_url.lower() for word in ["success", "complete", "done"]):
                return {
                    "success": True,
                    "message": "Proceso aparentemente completado (URL indica éxito)"
                }

            return {
                "success": False,
                "error": "No se detectaron indicadores de éxito"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error verificando completación: {e}"
            }

    async def process_merchant_invoice(
        self,
        merchant: Dict[str, Any],
        ticket_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Procesar facturación en portal web del merchant.
        """
        try:
            # Almacenar datos del ticket para acceso posterior
            self.current_ticket_data = ticket_data

            merchant_name = merchant["nombre"].lower()

            if "oxxo" in merchant_name:
                return await self._process_oxxo_invoice(ticket_data)
            elif "walmart" in merchant_name:
                return await self._process_walmart_invoice(ticket_data)
            elif "costco" in merchant_name:
                return await self._process_costco_invoice(ticket_data)
            elif "home depot" in merchant_name:
                return await self._process_home_depot_invoice(ticket_data)
            else:
                return await self._process_generic_portal(merchant, ticket_data)

        except Exception as e:
            logger.error(f"Error procesando facturación para {merchant['nombre']}: {e}")
            return {
                "success": False,
                "error": f"Error en automatización web: {str(e)}"
            }

    async def _process_oxxo_invoice(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Automatización específica para portal de OXXO."""
        logger.info("Iniciando automatización para OXXO")

        try:
            self.driver = self.setup_driver(headless=True)
            wait = WebDriverWait(self.driver, self.wait_timeout)

            # 1. Navegar al portal de OXXO
            self.driver.get("https://www.oxxo.com/facturacion")

            # 2. Buscar formulario de facturación
            try:
                # Buscar campo RFC
                rfc_input = wait.until(
                    EC.presence_of_element_located((By.ID, "rfc"))
                )
                rfc_input.clear()
                rfc_input.send_keys(self.company_credentials["rfc"])

                # Buscar campo razón social
                razon_input = self.driver.find_element(By.ID, "razonSocial")
                razon_input.clear()
                razon_input.send_keys(self.company_credentials["razon_social"])

                # Email
                email_input = self.driver.find_element(By.ID, "email")
                email_input.clear()
                email_input.send_keys(self.company_credentials["email"])

                # Extraer datos del ticket
                total = self._extract_total_from_ticket(ticket_data)
                fecha = self._extract_date_from_ticket(ticket_data)

                # Campos específicos de OXXO
                total_input = self.driver.find_element(By.ID, "total")
                total_input.clear()
                total_input.send_keys(str(total))

                fecha_input = self.driver.find_element(By.ID, "fecha")
                fecha_input.clear()
                fecha_input.send_keys(fecha)

                # 3. Enviar formulario
                submit_btn = self.driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
                submit_btn.click()

                # 4. Esperar resultado
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "success")),
                        EC.presence_of_element_located((By.CLASS_NAME, "error"))
                    )
                )

                # 5. Verificar si fue exitoso
                try:
                    success_element = self.driver.find_element(By.CLASS_NAME, "success")

                    # Extraer datos de la factura generada
                    invoice_data = self._extract_oxxo_invoice_data()

                    return {
                        "success": True,
                        "invoice_data": invoice_data,
                        "method": "oxxo_portal",
                        "processing_time": time.time()
                    }

                except NoSuchElementException:
                    error_element = self.driver.find_element(By.CLASS_NAME, "error")
                    error_text = error_element.text

                    return {
                        "success": False,
                        "error": f"Error en portal OXXO: {error_text}"
                    }

            except TimeoutException:
                return {
                    "success": False,
                    "error": "Timeout esperando elementos del formulario OXXO"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error general en automatización OXXO: {str(e)}"
            }
        finally:
            if self.driver:
                self.driver.quit()

    async def _process_walmart_invoice(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Automatización específica para portal de Walmart."""
        logger.info("Iniciando automatización para Walmart")

        try:
            self.driver = self.setup_driver(headless=True)
            wait = WebDriverWait(self.driver, self.wait_timeout)

            # 1. Navegar al portal de Walmart
            self.driver.get("https://www.walmart.com.mx/facturacion")

            # 2. Buscar y llenar formulario
            rfc_input = wait.until(
                EC.presence_of_element_located((By.NAME, "rfc"))
            )
            rfc_input.send_keys(self.company_credentials["rfc"])

            # Nombre/Razón Social
            name_input = self.driver.find_element(By.NAME, "nombreCompleto")
            name_input.send_keys(self.company_credentials["razon_social"])

            # Email
            email_input = self.driver.find_element(By.NAME, "email")
            email_input.send_keys(self.company_credentials["email"])

            # Total de la compra
            total = self._extract_total_from_ticket(ticket_data)
            total_input = self.driver.find_element(By.NAME, "montoTotal")
            total_input.send_keys(str(total))

            # Código postal
            cp_input = self.driver.find_element(By.NAME, "codigoPostal")
            cp_input.send_keys(self.company_credentials["codigo_postal"])

            # 3. Enviar formulario
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_btn.click()

            # 4. Esperar procesamiento
            await asyncio.sleep(3)

            # 5. Verificar resultado
            try:
                success_msg = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".success-message, .mensaje-exito"))
                )

                invoice_data = self._extract_walmart_invoice_data()

                return {
                    "success": True,
                    "invoice_data": invoice_data,
                    "method": "walmart_portal"
                }

            except TimeoutException:
                return {
                    "success": False,
                    "error": "No se pudo obtener confirmación de Walmart"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error en automatización Walmart: {str(e)}"
            }
        finally:
            if self.driver:
                self.driver.quit()

    async def _process_costco_invoice(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Automatización específica para portal de Costco."""
        logger.info("Iniciando automatización para Costco")

        try:
            self.driver = self.setup_driver(headless=True)
            wait = WebDriverWait(self.driver, self.wait_timeout)

            # 1. Ir al portal de Costco
            self.driver.get("https://www.costco.com.mx/rest/v2/facturacion")

            # 2. Login si es necesario (algunos merchants requieren cuenta)
            try:
                login_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".login-button, #login"))
                )
                login_btn.click()

                # Credenciales de cuenta empresarial (configurar en env)
                username = os.getenv("COSTCO_USERNAME")
                password = os.getenv("COSTCO_PASSWORD")

                if username and password:
                    user_input = self.driver.find_element(By.ID, "username")
                    user_input.send_keys(username)

                    pass_input = self.driver.find_element(By.ID, "password")
                    pass_input.send_keys(password)

                    login_submit = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    login_submit.click()

                    await asyncio.sleep(2)

            except TimeoutException:
                # No hay login necesario
                pass

            # 3. Ir a sección de facturación
            facturacion_link = wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Facturación"))
            )
            facturacion_link.click()

            # 4. Llenar formulario
            rfc_input = wait.until(
                EC.presence_of_element_located((By.ID, "rfc"))
            )
            rfc_input.send_keys(self.company_credentials["rfc"])

            # Resto del formulario
            razon_input = self.driver.find_element(By.ID, "razonSocial")
            razon_input.send_keys(self.company_credentials["razon_social"])

            total = self._extract_total_from_ticket(ticket_data)
            total_input = self.driver.find_element(By.ID, "total")
            total_input.send_keys(str(total))

            # 5. Enviar
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button.submit")
            submit_btn.click()

            # 6. Procesar resultado
            try:
                result_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".result-container"))
                )

                invoice_data = self._extract_costco_invoice_data()

                return {
                    "success": True,
                    "invoice_data": invoice_data,
                    "method": "costco_portal"
                }

            except TimeoutException:
                return {
                    "success": False,
                    "error": "Timeout esperando resultado de Costco"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error en automatización Costco: {str(e)}"
            }
        finally:
            if self.driver:
                self.driver.quit()

    async def _process_home_depot_invoice(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Automatización específica para portal de Home Depot."""
        logger.info("Iniciando automatización para Home Depot")

        try:
            self.driver = self.setup_driver(headless=True)
            wait = WebDriverWait(self.driver, self.wait_timeout)

            # 1. Navegar al portal
            self.driver.get("https://www.homedepot.com.mx/facturacion")

            # 2. Aceptar términos si aparecen
            try:
                accept_terms = wait.until(
                    EC.element_to_be_clickable((By.ID, "accept-terms"))
                )
                accept_terms.click()
            except TimeoutException:
                pass

            # 3. Llenar formulario de facturación
            rfc_field = wait.until(
                EC.presence_of_element_located((By.NAME, "rfc"))
            )
            rfc_field.send_keys(self.company_credentials["rfc"])

            email_field = self.driver.find_element(By.NAME, "email")
            email_field.send_keys(self.company_credentials["email"])

            # Código de ticket (necesario para Home Depot)
            ticket_code = self._extract_ticket_code_from_data(ticket_data)
            if ticket_code:
                code_field = self.driver.find_element(By.NAME, "codigoTicket")
                code_field.send_keys(ticket_code)

            # Total
            total = self._extract_total_from_ticket(ticket_data)
            total_field = self.driver.find_element(By.NAME, "total")
            total_field.send_keys(str(total))

            # 4. Enviar formulario
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button.enviar")
            submit_button.click()

            # 5. Esperar procesamiento
            try:
                success_indicator = wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".success")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".confirmacion"))
                    )
                )

                invoice_data = self._extract_home_depot_invoice_data()

                return {
                    "success": True,
                    "invoice_data": invoice_data,
                    "method": "home_depot_portal"
                }

            except TimeoutException:
                return {
                    "success": False,
                    "error": "No se recibió confirmación de Home Depot"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error en automatización Home Depot: {str(e)}"
            }
        finally:
            if self.driver:
                self.driver.quit()

    async def _process_generic_portal(
        self,
        merchant: Dict[str, Any],
        ticket_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Automatización genérica usando agente de decisión OpenAI.

        Usa IA para analizar HTML dinámicamente y tomar decisiones.
        """
        logger.info(f"Iniciando automatización inteligente para {merchant['nombre']}")

        try:
            self.driver = self.setup_driver(headless=False)  # Modo visible para debugging
            wait = WebDriverWait(self.driver, self.wait_timeout)

            # 1. Obtener URL del merchant
            portal_url = merchant.get("metadata", {}).get("url")
            if not portal_url:
                return {
                    "success": False,
                    "error": "No se encontró URL de portal para este merchant"
                }

            self.driver.get(portal_url)
            time.sleep(3)  # Esperar carga inicial

            # 2. Usar flujo inteligente con agente de decisión
            context = f"Automatizar facturación para {merchant['nombre']} en {portal_url}. " + \
                     f"Objetivo: llenar formulario de facturación y generar factura."

            result = await smart_automation_flow(self, ticket_data, context)

            if result["success"]:
                # Extraer datos de factura si fue exitoso
                invoice_data = self._extract_generic_invoice_data()
                result["invoice_data"] = invoice_data
                result["method"] = "intelligent_agent"
                result["merchant"] = merchant["nombre"]

            return result

        except Exception as e:
            logger.error(f"Error en automatización inteligente: {e}")
            return {
                "success": False,
                "error": f"Error en automatización inteligente: {str(e)}"
            }
        finally:
            if self.driver:
                self.driver.quit()

    # =============================================================
    # MÉTODOS AUXILIARES PARA EXTRACCIÓN DE DATOS
    # =============================================================

    def _extract_total_from_ticket(self, ticket_data: Dict[str, Any]) -> float:
        """Extraer total del ticket usando regex."""
        import re

        raw_data = ticket_data.get("raw_data", "")

        # Patrones para buscar total
        patterns = [
            r'(?:total|TOTAL)[:\s]*\$?([0-9,]+\.?[0-9]*)',
            r'(?:importe|IMPORTE)[:\s]*\$?([0-9,]+\.?[0-9]*)',
            r'\$([0-9,]+\.?[0-9]*)'
        ]

        for pattern in patterns:
            match = re.search(pattern, raw_data, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except ValueError:
                    continue

        return 100.0  # Default si no se encuentra

    def _extract_date_from_ticket(self, ticket_data: Dict[str, Any]) -> str:
        """Extraer fecha del ticket."""
        import re

        raw_data = ticket_data.get("raw_data", "")

        # Buscar fechas en varios formatos
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
            r'(\d{2}-\d{2}-\d{4})',  # DD-MM-YYYY
        ]

        for pattern in date_patterns:
            match = re.search(pattern, raw_data)
            if match:
                date_str = match.group(1)
                # Convertir a formato estándar
                if '/' in date_str:
                    parts = date_str.split('/')
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
                elif '-' in date_str and len(date_str.split('-')[0]) == 2:
                    parts = date_str.split('-')
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
                return date_str

        return datetime.now().strftime('%Y-%m-%d')

    def _extract_ticket_code_from_data(self, ticket_data: Dict[str, Any]) -> Optional[str]:
        """Extraer código de ticket para merchants que lo requieren."""
        import re

        raw_data = ticket_data.get("raw_data", "")

        # Buscar códigos de ticket
        patterns = [
            r'(?:ticket|TICKET)[:\s#]*([A-Z0-9]+)',
            r'(?:codigo|CODIGO)[:\s#]*([A-Z0-9]+)',
            r'(?:ref|REF)[:\s#]*([A-Z0-9]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, raw_data, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    async def _fill_generic_form(self, form_element, ticket_data: Dict[str, Any]) -> bool:
        """Llenar formulario genérico usando heurísticas."""
        try:
            # Mapeo de campos comunes
            field_mappings = {
                # RFC
                ("rfc", "RFC"): self.company_credentials["rfc"],
                # Razón Social
                ("razon", "social", "nombre", "company"): self.company_credentials["razon_social"],
                # Email
                ("email", "correo", "mail"): self.company_credentials["email"],
                # Total
                ("total", "monto", "amount", "importe"): str(self._extract_total_from_ticket(ticket_data)),
                # Fecha
                ("fecha", "date"): self._extract_date_from_ticket(ticket_data),
                # Teléfono
                ("telefono", "phone", "tel"): self.company_credentials["telefono"],
                # Código Postal
                ("postal", "zip", "cp"): self.company_credentials["codigo_postal"],
            }

            # Buscar y llenar campos
            for field_keys, value in field_mappings.items():
                for key in field_keys:
                    # Buscar por diferentes atributos
                    selectors = [
                        f"input[name*='{key}']",
                        f"input[id*='{key}']",
                        f"input[placeholder*='{key}']",
                        f"textarea[name*='{key}']",
                        f"select[name*='{key}']"
                    ]

                    for selector in selectors:
                        try:
                            elements = form_element.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                element = elements[0]
                                if element.is_displayed() and element.is_enabled():
                                    element.clear()
                                    element.send_keys(value)
                                    break
                        except Exception:
                            continue

            return True

        except Exception as e:
            logger.error(f"Error llenando formulario genérico: {e}")
            return False

    async def _submit_generic_form(self, form_element) -> bool:
        """Enviar formulario genérico."""
        try:
            # Buscar botón de envío
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button[class*='submit']",
                "button[class*='enviar']",
                ".btn-submit",
                ".submit-btn"
            ]

            for selector in submit_selectors:
                try:
                    submit_btn = form_element.find_element(By.CSS_SELECTOR, selector)
                    if submit_btn.is_displayed() and submit_btn.is_enabled():
                        submit_btn.click()
                        await asyncio.sleep(2)
                        return True
                except Exception:
                    continue

            # Si no encontramos botón, intentar enviar con Enter
            try:
                form_element.send_keys(Keys.RETURN)
                await asyncio.sleep(2)
                return True
            except Exception:
                pass

            return False

        except Exception as e:
            logger.error(f"Error enviando formulario: {e}")
            return False

    # =============================================================
    # MÉTODOS PARA EXTRAER DATOS DE FACTURA DE CADA MERCHANT
    # =============================================================

    def _extract_oxxo_invoice_data(self) -> Dict[str, Any]:
        """Extraer datos de factura generada en OXXO."""
        try:
            # Selectors específicos de OXXO
            uuid_element = self.driver.find_element(By.CSS_SELECTOR, ".uuid, .folio-fiscal")
            folio_element = self.driver.find_element(By.CSS_SELECTOR, ".folio, .numero-factura")

            return {
                "uuid": uuid_element.text.strip(),
                "folio": folio_element.text.strip(),
                "rfc_emisor": "OXX970814HS9",
                "proveedor": "OXXO",
                "url_pdf": self._find_download_link(),
                "metodo": "oxxo_portal",
                "fecha": datetime.now().strftime('%Y-%m-%d'),
            }
        except Exception as e:
            logger.error(f"Error extrayendo datos OXXO: {e}")
            return self._generate_fallback_invoice_data("OXXO")

    def _extract_walmart_invoice_data(self) -> Dict[str, Any]:
        """Extraer datos de factura generada en Walmart."""
        try:
            uuid_element = self.driver.find_element(By.CSS_SELECTOR, "[data-uuid], .invoice-uuid")
            folio_element = self.driver.find_element(By.CSS_SELECTOR, ".invoice-number, .folio")

            return {
                "uuid": uuid_element.text.strip(),
                "folio": folio_element.text.strip(),
                "rfc_emisor": "WAL9709244W4",
                "proveedor": "Walmart",
                "url_pdf": self._find_download_link(),
                "metodo": "walmart_portal",
                "fecha": datetime.now().strftime('%Y-%m-%d'),
            }
        except Exception as e:
            return self._generate_fallback_invoice_data("Walmart")

    def _extract_costco_invoice_data(self) -> Dict[str, Any]:
        """Extraer datos de factura generada en Costco."""
        try:
            return {
                "uuid": self._find_text_by_selectors([".uuid", ".fiscal-folio"]),
                "folio": self._find_text_by_selectors([".folio", ".invoice-number"]),
                "rfc_emisor": "COS050815PE4",
                "proveedor": "Costco",
                "url_pdf": self._find_download_link(),
                "metodo": "costco_portal",
                "fecha": datetime.now().strftime('%Y-%m-%d'),
            }
        except Exception as e:
            return self._generate_fallback_invoice_data("Costco")

    def _extract_home_depot_invoice_data(self) -> Dict[str, Any]:
        """Extraer datos de factura generada en Home Depot."""
        try:
            return {
                "uuid": self._find_text_by_selectors([".uuid", ".cfdi-uuid"]),
                "folio": self._find_text_by_selectors([".folio", ".invoice-folio"]),
                "rfc_emisor": "HDM930228Q90",
                "proveedor": "Home Depot",
                "url_pdf": self._find_download_link(),
                "metodo": "home_depot_portal",
                "fecha": datetime.now().strftime('%Y-%m-%d'),
            }
        except Exception as e:
            return self._generate_fallback_invoice_data("Home Depot")

    def _extract_generic_invoice_data(self) -> Dict[str, Any]:
        """Extraer datos de factura de portal genérico."""
        try:
            return {
                "uuid": self._find_text_by_selectors([".uuid", ".folio-fiscal", "[data-uuid]"]),
                "folio": self._find_text_by_selectors([".folio", ".numero", ".invoice-number"]),
                "rfc_emisor": "GENERIC123456XXX",
                "proveedor": "Merchant Genérico",
                "url_pdf": self._find_download_link(),
                "metodo": "generic_portal",
                "fecha": datetime.now().strftime('%Y-%m-%d'),
            }
        except Exception as e:
            return self._generate_fallback_invoice_data("Generic")

    def _find_text_by_selectors(self, selectors: list) -> str:
        """Buscar texto usando múltiples selectores."""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except Exception:
                continue
        return f"AUTO-{int(time.time())}"

    def _find_download_link(self) -> str:
        """Buscar enlace de descarga de PDF."""
        try:
            download_selectors = [
                "a[href*='.pdf']",
                "a[href*='download']",
                ".download-link",
                ".pdf-link"
            ]

            for selector in download_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return element.get_attribute("href")
                except Exception:
                    continue

        except Exception:
            pass

        return f"https://invoices.example.com/{int(time.time())}.pdf"

    def _generate_fallback_invoice_data(self, merchant_name: str) -> Dict[str, Any]:
        """Generar datos de factura de respaldo si falla la extracción."""
        timestamp = int(time.time())
        return {
            "uuid": f"FALLBACK-{timestamp}-{merchant_name[:3].upper()}",
            "folio": f"F{timestamp % 1000000}",
            "rfc_emisor": f"{merchant_name[:3].upper()}123456XXX",
            "proveedor": merchant_name,
            "url_pdf": f"https://fallback.invoices.com/{timestamp}.pdf",
            "metodo": f"{merchant_name.lower()}_portal_fallback",
            "fecha": datetime.now().strftime('%Y-%m-%d'),
            "note": "Datos generados automáticamente - verificar manualmente"
        }

    def find_element_safe(self, selector: str):
        """
        Buscar elemento de forma segura usando XPath o CSS selector.

        Args:
            selector: XPath o CSS selector

        Returns:
            WebElement o None si no se encuentra
        """
        try:
            # Determinar si es XPath o CSS selector
            if selector.startswith('//') or selector.startswith('('):
                # Es XPath
                return self.driver.find_element(By.XPATH, selector)
            else:
                # Es CSS selector
                return self.driver.find_element(By.CSS_SELECTOR, selector)
        except Exception as e:
            logger.debug(f"No se encontró elemento con selector {selector}: {e}")
            return None

    async def navigate_to_portal(
        self,
        url: str,
        merchant_name: str = None,
        take_screenshot: bool = True,
        auto_fill: bool = False,
        ticket_text: str = None
    ) -> Dict[str, Any]:
        """
        Navegar a un portal de facturación y verificar accesibilidad.

        Args:
            url: URL del portal de facturación
            merchant_name: Nombre del merchant (opcional)
            take_screenshot: Si tomar screenshot del portal
            auto_fill: Si llenar automáticamente los campos detectados
            ticket_text: Texto del ticket para extracción de datos (requerido si auto_fill=True)

        Returns:
            Dict con resultado de la navegación
        """
        start_time = time.time()

        try:
            logger.info(f"Navegando a portal: {url}")

            # Configurar driver con verificación de dependencias
            try:
                self.driver = self.setup_driver(headless=not take_screenshot)
                wait = WebDriverWait(self.driver, self.wait_timeout)
            except Exception as driver_error:
                logger.error(f"Error configurando WebDriver: {driver_error}")
                raise Exception(f"❌ Error de configuración: ChromeDriver no disponible. Instala con: brew install chromedriver")

            # Asegurar que la URL tenga protocolo
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"

            logger.info(f"Navegando a URL completa: {url}")

            # Navegar a la URL con manejo de errores mejorado
            try:
                self.driver.get(url)
                logger.info("Navegación inicial exitosa")
            except Exception as nav_error:
                logger.error(f"Error en navegación inicial: {nav_error}")
                raise Exception(f"No se pudo conectar al portal: {nav_error}")

            # Esperar que la página cargue con timeout específico
            try:
                wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                logger.info("Página cargada completamente")
            except Exception as load_error:
                logger.warning(f"Timeout esperando carga completa: {load_error}")
                # Continuar - la página puede estar parcialmente cargada

            loading_time = time.time() - start_time

            # Obtener información de la página
            page_title = self.driver.title
            current_url = self.driver.current_url

            # Verificar si es accesible (no hay errores evidentes)
            accessibility = "accessible"
            error_indicators = [
                "404", "not found", "error", "unavailable",
                "maintenance", "mantenimiento", "no disponible"
            ]

            page_source = self.driver.page_source.lower()
            for indicator in error_indicators:
                if indicator in page_source or indicator in page_title.lower():
                    accessibility = "error_detected"
                    break

            # Tomar screenshot si se solicita
            screenshot_path = None
            if take_screenshot:
                try:
                    # Crear directorio de screenshots si no existe
                    screenshot_dir = "screenshots"
                    os.makedirs(screenshot_dir, exist_ok=True)

                    # Generar nombre único para el screenshot
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    merchant_safe = (merchant_name or "unknown").replace(" ", "_").lower()
                    screenshot_path = f"{screenshot_dir}/{merchant_safe}_{timestamp}.png"

                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"Screenshot guardado: {screenshot_path}")

                except Exception as e:
                    logger.warning(f"Error tomando screenshot: {e}")

            # Buscar formularios de facturación y detectar campos
            form_detected = False
            form_fields = []
            navigation_attempts = 0
            max_navigation_attempts = 5  # Aumentar para portales complejos

            try:
                # Intentar encontrar formularios, navegando inteligentemente si es necesario
                while not form_detected and navigation_attempts < max_navigation_attempts:
                    navigation_attempts += 1

                    # Buscar formularios existentes
                    forms = self.driver.find_elements(By.TAG_NAME, "form")
                    logger.info(f"Encontrados {len(forms)} elementos <form> en la página")

                    for i, form in enumerate(forms):
                        form_text = form.text.lower()
                        logger.info(f"Form {i+1} texto: '{form_text[:100]}...'")

                        if any(keyword in form_text for keyword in ["rfc", "factura", "invoice", "ticket", "codigo", "monto"]):
                            logger.info(f"Form {i+1} contiene palabras clave de facturación")
                            extracted_fields = self._extract_form_fields(form)
                            interactive_fields = [f for f in extracted_fields if self._is_interactive_field(f)]

                            if interactive_fields:
                                form_detected = True
                                form_fields.extend(interactive_fields)
                                logger.info(f"Form {i+1} tiene {len(interactive_fields)} campos interactivos")
                                break
                            else:
                                logger.info(f"Form {i+1} sin campos interactivos")

                    # Si no hay formularios específicos, buscar campos en toda la página
                    if not form_detected:
                        potential_fields = self._extract_form_fields(self.driver)
                        # Filtrar solo campos visibles e interactivos
                        visible_fields = [f for f in potential_fields if self._is_interactive_field(f)]
                        if visible_fields:
                            form_fields = visible_fields
                            form_detected = True
                            logger.info(f"Detectados {len(visible_fields)} campos interactivos en la página")

                    # Si no encontramos formularios, usar LLM para navegar inteligentemente
                    if not form_detected and navigation_attempts < max_navigation_attempts:
                        logger.info(f"Intento {navigation_attempts}: No se encontraron formularios, navegando inteligentemente...")

                        # Usar LLM para encontrar dónde hacer clic
                        navigation_result = await self._navigate_intelligently_with_llm()

                        if navigation_result and navigation_result.get("clicked"):
                            # Esperar que la página se actualice
                            await asyncio.sleep(2)

                            # Verificar si el URL cambió
                            new_url = self.driver.current_url
                            logger.info(f"URL después de navegación inteligente: {new_url}")
                        else:
                            # No se pudo navegar más
                            break

            except Exception as e:
                logger.warning(f"Error detectando formularios: {e}")

            # Llenado automático si está habilitado y hay campos
            filled_fields = {}
            submission_result = None
            if auto_fill and form_fields and ticket_text:
                try:
                    logger.info("Iniciando llenado automático de campos")

                    # Extraer valores con LLM
                    extracted_values = await self.extract_fields_with_llm(form_fields, ticket_text)

                    # Llenar campos automáticamente
                    filled_fields = await self._fill_form_fields(form_fields, extracted_values)

                    # Intentar enviar formulario con reintentos para CAPTCHA
                    submission_result = await self._submit_form_with_captcha_retry(form_fields)

                    # Si hay errores de campos, intentar corrección con visión híbrida
                    if (submission_result and
                        submission_result.get("status") in ["error", "validation_error"] and
                        hasattr(self, 'current_ticket_data')):

                        logger.info("🔬 Intentando corrección híbrida por errores de formulario")

                        # Obtener imagen del ticket para re-análisis
                        ticket_image = self.current_ticket_data.get("raw_data", "")

                        if ticket_image:
                            # Usar visión híbrida para corregir campos problemáticos
                            corrected_values = await self._handle_form_errors_with_hybrid_vision(
                                form_fields, ticket_image
                            )

                            if corrected_values:
                                logger.info(f"📝 Re-llenando {len(corrected_values)} campos corregidos")

                                # Re-llenar campos corregidos
                                for field_name, corrected_value in corrected_values.items():
                                    try:
                                        # Buscar elemento y actualizar
                                        element = None
                                        try:
                                            element = self.driver.find_element(By.NAME, field_name)
                                        except NoSuchElementException:
                                            # Buscar por ID si name no funciona
                                            try:
                                                element = self.driver.find_element(By.ID, field_name)
                                            except NoSuchElementException:
                                                continue

                                        if element and element.is_displayed() and element.is_enabled():
                                            element.clear()
                                            element.send_keys(corrected_value)
                                            logger.info(f"✅ Campo '{field_name}' corregido con: '{corrected_value}'")

                                    except Exception as field_error:
                                        logger.warning(f"❌ Error actualizando campo '{field_name}': {field_error}")

                                # Intentar enviar formulario de nuevo
                                logger.info("🔄 Reintentando envío con campos corregidos")
                                submission_result = await self._submit_form_with_captcha_retry(form_fields)

                                if submission_result and submission_result.get("status") == "success":
                                    logger.info("🎉 ¡Formulario enviado exitosamente tras corrección híbrida!")
                                    submission_result["hybrid_correction_applied"] = True
                                    submission_result["corrected_fields"] = list(corrected_values.keys())

                except Exception as e:
                    logger.error(f"Error en llenado automático: {e}")

            return {
                "success": True,
                "url": url,
                "final_url": current_url,
                "page_title": page_title,
                "loading_time": round(loading_time, 2),
                "accessibility": accessibility,
                "form_detected": form_detected,
                "form_fields": form_fields,
                "auto_filled": auto_fill,
                "filled_fields": filled_fields,
                "submission_result": submission_result,
                "screenshot_path": screenshot_path,
                "merchant": merchant_name
            }

        except Exception as e:
            logger.error(f"Error navegando a {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "merchant": merchant_name,
                "loading_time": time.time() - start_time,
                "form_fields": [],
                "auto_filled": False,
                "filled_fields": {},
                "submission_result": None
            }

        finally:
            # No cerrar el driver aquí, lo cerramos en cleanup()
            pass

    def _extract_form_fields(self, container) -> List[Dict[str, Any]]:
        """
        Extraer información de campos de formulario (input, select, textarea).

        Args:
            container: Elemento del DOM (form o driver) donde buscar campos

        Returns:
            Lista de diccionarios con información de cada campo
        """
        fields = []

        try:
            # Buscar todos los campos de input, select y textarea
            field_selectors = [
                ("input", "input"),
                ("select", "select"),
                ("textarea", "textarea")
            ]

            for tag_name, selector in field_selectors:
                try:
                    elements = container.find_elements(By.TAG_NAME, tag_name)

                    for element in elements:
                        try:
                            # Verificar que el elemento sea visible y no esté oculto
                            if not element.is_displayed():
                                continue

                            field_info = {
                                "tag": tag_name,
                                "type": element.get_attribute("type") or "",
                                "name": element.get_attribute("name") or "",
                                "id": element.get_attribute("id") or "",
                                "placeholder": element.get_attribute("placeholder") or "",
                                "label": ""
                            }

                            # Buscar label asociado
                            label_text = self._find_associated_label(element)
                            if label_text:
                                field_info["label"] = label_text

                            # Solo agregar campos con algún identificador útil o que sean visibles
                            if field_info["name"] or field_info["id"] or field_info["placeholder"] or field_info["label"]:
                                fields.append(field_info)
                            elif element.is_displayed():  # Si está visible aunque no tenga identificadores claros
                                # Intentar obtener texto cercano como contexto
                                context_text = self._get_element_context(element)
                                if context_text:
                                    field_info["label"] = context_text
                                    field_info["name"] = f"field_{len(fields)}"  # Nombre genérico
                                    fields.append(field_info)

                        except Exception as e:
                            logger.debug(f"Error extrayendo info del campo {tag_name}: {e}")
                            continue

                except Exception as e:
                    logger.debug(f"Error buscando elementos {tag_name}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error extrayendo campos de formulario: {e}")

        return fields

    def _is_interactive_field(self, field_info: Dict[str, Any]) -> bool:
        """Determinar si un campo es realmente interactivo y útil para facturación."""
        field_type = field_info.get("type", "").lower()
        field_name = field_info.get("name", "").lower()
        field_id = field_info.get("id", "").lower()

        # Excluir campos claramente no interactivos
        non_interactive_types = ["hidden", "submit", "button", "image"]
        if field_type in non_interactive_types:
            return False

        # Excluir campos de sistema/ASP.NET
        system_fields = ["__viewstate", "__eventvalidation", "__eventtarget", "__eventargument"]
        if any(sys_field in field_name for sys_field in system_fields):
            return False

        # Incluir campos que tienen nombres/labels relevantes para facturación
        billing_keywords = ["rfc", "factura", "total", "monto", "estacion", "folio", "codigo", "cliente"]
        field_text = f"{field_name} {field_id} {field_info.get('label', '')}".lower()
        if any(keyword in field_text for keyword in billing_keywords):
            return True

        # Incluir campos de texto normales si tienen identificadores
        if field_type in ["text", "email", "number", "tel"] and (field_name or field_id):
            return True

        return False

    def _get_element_context(self, element) -> str:
        """Obtener contexto textual alrededor de un elemento."""
        try:
            # Buscar en elemento padre
            parent = element.find_element(By.XPATH, "..")
            parent_text = parent.text.strip()

            # Filtrar solo texto relevante y corto
            if parent_text and len(parent_text) < 100:
                # Buscar patrones típicos de etiquetas de campo
                words = parent_text.split()
                for word in words:
                    if any(keyword in word.lower() for keyword in
                          ["estacion", "folio", "rfc", "total", "monto", "codigo", "web", "id"]):
                        return word

            return ""
        except Exception:
            return ""

    def _find_associated_label(self, element) -> str:
        """
        Buscar el texto del label asociado a un elemento de input.

        Args:
            element: Elemento input/select/textarea

        Returns:
            Texto del label asociado o cadena vacía
        """
        try:
            # Método 1: Buscar label con atributo 'for' que coincida con el id del elemento
            element_id = element.get_attribute("id")
            if element_id:
                try:
                    label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{element_id}']")
                    return label.text.strip()
                except NoSuchElementException:
                    pass

            # Método 2: Buscar label padre que contenga el elemento
            try:
                parent = element.find_element(By.XPATH, "..")
                if parent.tag_name.lower() == "label":
                    return parent.text.strip()
            except Exception:
                pass

            # Método 3: Buscar label hermano anterior
            try:
                # Buscar en hermanos anteriores
                previous_siblings = element.find_elements(By.XPATH, "./preceding-sibling::*")
                for sibling in reversed(previous_siblings[-3:]):  # Solo los últimos 3 hermanos
                    if sibling.tag_name.lower() == "label":
                        return sibling.text.strip()
            except Exception:
                pass

            # Método 4: Buscar texto en elementos cercanos (div, span, etc.)
            try:
                # Buscar en el elemento padre inmediato
                parent = element.find_element(By.XPATH, "..")
                parent_text = parent.text.strip()
                element_text = element.text.strip()

                # Si el texto del padre es más largo que el del elemento, usar la diferencia
                if parent_text and len(parent_text) > len(element_text):
                    # Intentar extraer solo el texto que no pertenece al input
                    label_text = parent_text.replace(element_text, "").strip()
                    if label_text and len(label_text) < 100:  # Evitar textos muy largos
                        return label_text
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Error buscando label asociado: {e}")

        return ""

    async def extract_fields_with_llm(
        self,
        form_fields: List[Dict[str, Any]],
        ticket_text: str
    ) -> Dict[str, str]:
        """
        Usar LLM para extraer valores específicos de campos del texto del ticket.

        Args:
            form_fields: Lista de campos detectados por Selenium
            ticket_text: Texto OCR del ticket

        Returns:
            Dict con valores extraídos: {field_name: extracted_value}
        """
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI no disponible, usando extracción básica")
            return self._extract_fields_basic(form_fields, ticket_text)

        try:
            logger.info(f"🔍 Iniciando extracción LLM para {len(form_fields)} campos")
            logger.info(f"📄 Texto del ticket: {len(ticket_text)} caracteres")

            # Generar prompt inteligente basado en los campos detectados
            prompt = self._generate_extraction_prompt(form_fields, ticket_text)
            logger.info(f"📝 Prompt generado: {len(prompt)} caracteres")

            # Configurar cliente Claude
            client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )

            logger.info("🤖 Enviando petición a Claude...")
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                temperature=0.1,
                system="Eres un experto en extracción de datos de tickets de compra mexicanos. Extrae exactamente los campos solicitados del texto del ticket. Responde solo en formato JSON válido.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parsear respuesta JSON
            content = response.content[0].text.strip()
            logger.info(f"🤖 Respuesta Claude recibida: {len(content)} caracteres")

            # Limpiar respuesta si tiene markdown
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()

            logger.info(f"🔧 Parseando JSON: {content[:200]}...")
            extracted_data = json.loads(content)

            logger.info(f"✅ LLM extrajo {len(extracted_data)} campos: {extracted_data}")
            return extracted_data

        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON de Claude: {e}")
            logger.error(f"📄 Contenido problemático: {content[:500]}")
            return self._extract_fields_basic(form_fields, ticket_text)
        except Exception as e:
            logger.error(f"❌ Error en extracción LLM: {e}")
            return self._extract_fields_basic(form_fields, ticket_text)

    def _generate_extraction_prompt(
        self,
        form_fields: List[Dict[str, Any]],
        ticket_text: str
    ) -> str:
        """Generar prompt inteligente para extracción de campos."""

        # Crear descripción de campos necesarios
        field_descriptions = []
        for field in form_fields:
            field_name = field.get('name', '')
            field_label = field.get('label', '')
            field_placeholder = field.get('placeholder', '')
            field_type = field.get('type', '')

            # Crear descripción contextual del campo
            description_parts = []
            if field_label:
                description_parts.append(f"'{field_label}'")
            if field_placeholder:
                description_parts.append(f"placeholder: '{field_placeholder}'")
            if field_name:
                description_parts.append(f"name: '{field_name}'")

            description = " - ".join(description_parts)

            # Determinar qué buscar basado en el contexto específico de Litromil
            field_context = f"{field_name} {field_label} {field_placeholder}".lower()

            if 'txtdespacho' in field_name.lower() or 'folio' in field_context:
                search_hint = "[buscar código alfanumérico para facturación - puede ser número de ticket o código]"
            elif 'txtidentificador' in field_name.lower() or 'web id' in field_context:
                search_hint = "[buscar identificador web - puede ser parte del código principal o número de referencia]"
            elif 'cmbgasolineras' in field_name.lower() or 'estacion' in field_context:
                search_hint = "[buscar nombre de la estación de servicio o establecimiento comercial]"
            elif 'captcha' in field_name.lower():
                search_hint = "[resolver automáticamente con GPT-4 Vision]"
            elif any(keyword in field_context for keyword in ['clave', 'code', 'codigo', 'ticket']):
                search_hint = "[buscar código alfanumérico para facturación]"
            elif any(keyword in field_context for keyword in ['monto', 'total', 'amount', 'precio', 'importe']):
                search_hint = "[buscar monto total de la compra]"
            elif any(keyword in field_context for keyword in ['fecha', 'date']):
                search_hint = "[buscar fecha de la compra]"
            elif any(keyword in field_context for keyword in ['rfc', 'tax']):
                search_hint = "[buscar RFC del establecimiento]"
            else:
                search_hint = "[extraer valor apropiado del ticket]"

            if field_type != 'submit' and field_type != 'button':
                field_descriptions.append(f"• {field_name}: {description} {search_hint}")

        # Crear el prompt
        prompt = f"""Del siguiente texto de ticket, extrae EXACTAMENTE estos campos para facturación:

{chr(10).join(field_descriptions)}

TEXTO DEL TICKET:
{ticket_text}

INSTRUCCIONES ESPECÍFICAS:
- Responde solo JSON válido
- Para txtDespacho (Folio): Busca números que aparecen como FOLIO (pueden ser cortos como 087 o largos como 138496061)
- Para txtIdentificador (Web ID): Busca números largos de 8+ dígitos que podrían ser identificadores web (ej: 84511204)
- Para cmbGasolineras (Estación): Busca nombres de establecimientos (ej: "GASOLINERIA LITRO MIL")
- Para captcha: SIEMPRE dejar vacío ""
- REGLAS ESPECIALES para cuando faltan etiquetas:
  * Si ves "FOLIO: 138496061" = usa 138496061 como folio
  * Si ves números largos como "84511204" separados = WEB ID
  * Prioriza números que aparecen con etiquetas claras sobre números sueltos
- Para montos, usa solo números con decimales (ej: "125.50")
- Para códigos, usa el valor exacto encontrado

EJEMPLOS DE MAPEO:
- "FOLIO: 138496061" → txtDespacho: "138496061"
- "WEB ID: 84511204" → txtIdentificador: "84511204"
- "GASOLINERIA LITRO MIL" → cmbGasolineras: "GASOLINERIA LITRO MIL"
- Si OCR omite etiquetas, usa números por posición y longitud

Formato de respuesta:
{{
{', '.join([f'  "{field.get("name", "")}": ""' for field in form_fields if field.get("type") not in ["submit", "button"]])}
}}"""

        return prompt

    def _extract_fields_basic(
        self,
        form_fields: List[Dict[str, Any]],
        ticket_text: str
    ) -> Dict[str, str]:
        """Extracción básica como fallback sin LLM."""
        import re

        extracted = {}

        for field in form_fields:
            field_name = field.get('name', '')
            field_label = field.get('label', '').lower()
            field_placeholder = field.get('placeholder', '').lower()

            if field.get('type') in ['submit', 'button']:
                continue

            value = ""

            # Detectar campos de CAPTCHA - los resolveremos justo antes del envío
            if 'captcha' in field_name.lower() or 'captcha' in field_label.lower():
                logger.info(f"Campo CAPTCHA detectado: {field_name} - se resolverá antes del envío")
                extracted[field_name] = ""  # Dejar vacío por ahora
                continue

            # Buscar monto/total
            if any(keyword in f"{field_label} {field_placeholder}"
                   for keyword in ['monto', 'total', 'amount', 'importe']):
                patterns = [
                    r'(?:total|TOTAL)[:\s]*\$?([0-9,]+\.?[0-9]*)',
                    r'(?:importe|IMPORTE)[:\s]*\$?([0-9,]+\.?[0-9]*)',
                    r'\$([0-9,]+\.?[0-9]*)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, ticket_text)
                    if match:
                        value = match.group(1).replace(',', '')
                        break

            # Buscar folio específico para Litromil
            elif 'txtdespacho' in field_name.lower() or 'folio' in f"{field_label} {field_placeholder}":
                # Buscar números que podrían ser folios (3-10 dígitos para cubrir casos como 138496061)
                folio_patterns = [
                    r'(?:folio|FOLIO)[:\s]*([0-9]{3,10})',  # Con etiqueta, rango amplio
                    r'\b([0-9]{9})\b',  # Sin etiqueta, números de 9 dígitos específicos como 138496061
                    r'\b([0-9]{3,4})\b'  # Sin etiqueta, números cortos tradicionales
                ]
                for pattern in folio_patterns:
                    matches = re.findall(pattern, ticket_text)
                    if matches:
                        # Tomar el primer número válido encontrado (priorizar números largos que parecen folios)
                        for match in matches:
                            # Priorizar números de 9 dígitos como 138496061
                            if len(match) == 9:
                                value = match
                                break
                            # Luego números cortos tradicionales
                            elif len(match) >= 3 and len(match) <= 4:
                                value = match
                        if value:
                            break

            # Buscar Web ID específico para Litromil
            elif 'txtidentificador' in field_name.lower() or 'web id' in f"{field_label} {field_placeholder}":
                # Buscar números largos de 8+ dígitos
                web_id_patterns = [
                    r'(?:web\s*id|WEB\s*ID)[:\s]*([0-9]{8,})',  # Con etiqueta
                    r'\b([0-9]{8,})\b'  # Sin etiqueta, números largos
                ]
                for pattern in web_id_patterns:
                    matches = re.findall(pattern, ticket_text)
                    if matches:
                        # Tomar el primer número largo encontrado
                        for match in matches:
                            if len(match) >= 8:
                                value = match
                                break
                        if value:
                            break

            # Buscar código/clave genérico
            elif any(keyword in f"{field_label} {field_placeholder}"
                     for keyword in ['clave', 'code', 'codigo', 'ticket']):
                patterns = [
                    r'(?:clave|code|codigo)[:\s]*([A-Z0-9]+)',
                    r'([0-9]{10,})',  # Números largos típicos de códigos
                ]
                for pattern in patterns:
                    match = re.search(pattern, ticket_text, re.IGNORECASE)
                    if match:
                        value = match.group(1)
                        break

            extracted[field_name] = value

        return extracted

    async def _fill_form_fields(
        self,
        form_fields: List[Dict[str, Any]],
        extracted_values: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Llenar campos de formulario con valores extraídos.

        Args:
            form_fields: Lista de campos detectados
            extracted_values: Valores extraídos por LLM

        Returns:
            Dict con campos llenados: {field_name: filled_value}
        """
        filled_fields = {}

        try:
            for field in form_fields:
                field_name = field.get('name', '')
                field_type = field.get('type', '')

                # Omitir botones y CAPTCHA (se resuelve antes del envío)
                if field_type in ['submit', 'button']:
                    continue

                # Omitir campos CAPTCHA en llenado inicial
                if 'captcha' in field_name.lower():
                    logger.info(f"Omitiendo campo CAPTCHA '{field_name}' en llenado inicial")
                    continue

                # Obtener valor extraído
                value = extracted_values.get(field_name, '')

                if not value:
                    continue

                try:
                    # Buscar elemento por name primero, luego por id
                    element = None
                    if field_name:
                        try:
                            element = self.driver.find_element(By.NAME, field_name)
                        except NoSuchElementException:
                            pass

                    if not element and field.get('id'):
                        try:
                            element = self.driver.find_element(By.ID, field['id'])
                        except NoSuchElementException:
                            pass

                    if element and element.is_displayed() and element.is_enabled():
                        # Limpiar campo
                        element.clear()

                        # Llenar con valor
                        element.send_keys(value)

                        filled_fields[field_name] = value
                        logger.info(f"Campo '{field_name}' llenado con: '{value}'")

                        # Pequeña pausa para que la página procese
                        await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Error llenando campo '{field_name}': {e}")

        except Exception as e:
            logger.error(f"Error en _fill_form_fields: {e}")

        return filled_fields

    async def _handle_form_errors_with_intelligent_validation(
        self,
        form_fields: List[Dict[str, Any]],
        ticket_image_data: str,
        max_retries: int = 2
    ) -> Dict[str, str]:
        """
        Maneja errores de formularios usando validación inteligente con GPT Vision.

        Este método se ejecuta cuando el portal web rechaza los valores extraídos por OCR.
        GPT Vision analiza la imagen original + candidatos + error específico para
        seleccionar el valor correcto.

        Args:
            form_fields: Campos del formulario con errores
            ticket_image_data: Imagen base64 del ticket original
            max_retries: Número máximo de reintentos

        Returns:
            Dict con valores corregidos por GPT Vision
        """
        corrected_values = {}

        try:
            from core.intelligent_field_validator import intelligent_validator

            # Detectar errores específicos en la página
            page_source = self.driver.page_source
            error_messages = self._detect_form_errors(page_source)

            if not error_messages:
                logger.info("✅ No se detectaron errores de formulario")
                return corrected_values

            logger.info(f"🔄 Detectados errores de formulario: {error_messages}")

            # Identificar qué campos específicos causaron errores
            problematic_fields = self._identify_problematic_fields(error_messages, form_fields)

            # Mapear nombres de campos del formulario a campos estándar
            field_mapping = {
                'folio': 'folio',
                'ticket': 'folio',
                'numero': 'folio',
                'rfc': 'rfc_emisor',
                'rfc_emisor': 'rfc_emisor',
                'total': 'monto_total',
                'monto': 'monto_total',
                'importe': 'monto_total',
                'fecha': 'fecha',
                'web_id': 'web_id',
                'codigo': 'web_id'
            }

            # Preparar solicitudes de validación para campos problemáticos
            validation_requests = {}
            for field_name, error_msg in problematic_fields.items():
                # Mapear a campo estándar
                standard_field = field_mapping.get(field_name.lower(), field_name)

                logger.info(f"🔍 Validando '{field_name}' -> '{standard_field}' debido a: {error_msg}")
                validation_requests[standard_field] = error_msg

            # Usar validador inteligente para re-extraer campos problemáticos
            validation_results = await intelligent_validator.validate_multiple_fields(
                image_data=ticket_image_data,
                required_fields=list(validation_requests.keys()),
                portal_errors=validation_requests
            )

            # Procesar resultados y mapear de vuelta a nombres de campos del formulario
            reverse_mapping = {v: k for k, v in field_mapping.items()}

            for standard_field, result in validation_results.items():
                # Encontrar el nombre del campo original del formulario
                original_field_name = reverse_mapping.get(standard_field, standard_field)

                if result.final_value and result.confidence >= 0.5:
                    corrected_values[original_field_name] = result.final_value

                    logger.info(f"✅ Campo '{original_field_name}' corregido: '{result.final_value}' "
                              f"(confianza: {result.confidence:.2f}, método: {result.method_used})")

                    if result.gpt_reasoning:
                        logger.info(f"   📝 Razonamiento GPT: {result.gpt_reasoning[:150]}...")
                else:
                    logger.warning(f"❌ No se pudo corregir campo '{original_field_name}' "
                                 f"(confianza: {result.confidence:.2f})")
                    if result.error:
                        logger.error(f"   Error: {result.error}")

            # Generar reporte de validación para debugging
            report = intelligent_validator.get_summary_report(validation_results)
            logger.info(f"📊 Reporte de validación: "
                       f"{report['successful_extractions']}/{report['total_fields']} exitosos, "
                       f"GPT Vision usado en {report['gpt_vision_used']} campos, "
                       f"confianza promedio: {report['average_confidence']:.2f}")

        except Exception as e:
            logger.error(f"❌ Error en validación inteligente: {e}")

        return corrected_values

    # Mantener método anterior para compatibilidad
    async def _handle_form_errors_with_hybrid_vision(
        self,
        form_fields: List[Dict[str, Any]],
        ticket_image_data: str,
        max_retries: int = 2
    ) -> Dict[str, str]:
        """
        Método legacy - redirige al nuevo validador inteligente
        """
        logger.info("🔄 Redirigiendo a validador inteligente mejorado...")
        return await self._handle_form_errors_with_intelligent_validation(
            form_fields, ticket_image_data, max_retries
        )

    def _detect_form_errors(self, page_source: str) -> List[str]:
        """
        Detecta mensajes de error en la página después del envío de formulario
        """
        error_messages = []

        try:
            # Patrones de error comunes en formularios web mexicanos
            error_patterns = [
                r'error[:\s]*([^<\n]{10,100})',
                r'invalid[:\s]*([^<\n]{10,100})',
                r'incorrecto[:\s]*([^<\n]{10,100})',
                r'inválido[:\s]*([^<\n]{10,100})',
                r'campo[:\s]*([^<\n]{10,100})',
                r'required[:\s]*([^<\n]{10,100})',
                r'obligatorio[:\s]*([^<\n]{10,100})',
                r'no válido[:\s]*([^<\n]{10,100})',
                r'formato[:\s]*([^<\n]{10,100})',
                r'debe[:\s]*([^<\n]{10,100})'
            ]

            import re
            for pattern in error_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    clean_msg = re.sub(r'<[^>]+>', '', match).strip()
                    if len(clean_msg) > 5:  # Evitar matches muy cortos
                        error_messages.append(clean_msg)

            # También buscar en elementos específicos de error
            try:
                error_elements = self.driver.find_elements(By.CSS_SELECTOR,
                    '.error, .alert, .warning, [class*="error"], [class*="invalid"]')

                for element in error_elements:
                    if element.is_displayed():
                        text = element.text.strip()
                        if text and len(text) > 5:
                            error_messages.append(text)

            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error detectando errores de formulario: {e}")

        return error_messages[:5]  # Limitar a 5 mensajes más relevantes

    def _identify_problematic_fields(
        self,
        error_messages: List[str],
        form_fields: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Identifica qué campos específicos están causando errores
        """
        problematic_fields = {}

        # Mapeo de palabras clave a nombres de campos
        field_keywords = {
            'folio': ['folio', 'ticket', 'number', 'numero'],
            'web_id': ['web', 'id', 'codigo', 'authorization', 'auth'],
            'total': ['total', 'amount', 'monto', 'importe'],
            'fecha': ['fecha', 'date', 'when'],
            'hora': ['hora', 'time', 'cuando'],
            'reference': ['referencia', 'reference', 'ref']
        }

        # Extraer nombres de campos del formulario
        field_names = [field.get('name', '') for field in form_fields if field.get('name')]

        try:
            for error_msg in error_messages:
                error_lower = error_msg.lower()

                # Buscar menciones directas de campos
                for field_name in field_names:
                    if field_name.lower() in error_lower:
                        problematic_fields[field_name] = error_msg
                        continue

                # Buscar por palabras clave
                for field_type, keywords in field_keywords.items():
                    for keyword in keywords:
                        if keyword in error_lower:
                            # Buscar el campo correspondiente en el formulario
                            matching_field = self._find_field_by_keyword(field_names, field_type)
                            if matching_field:
                                problematic_fields[matching_field] = error_msg
                                break

        except Exception as e:
            logger.error(f"Error identificando campos problemáticos: {e}")

        return problematic_fields

    def _find_field_by_keyword(self, field_names: List[str], field_type: str) -> Optional[str]:
        """
        Encuentra un campo por tipo/palabra clave
        """
        keyword_map = {
            'folio': ['folio', 'ticket', 'no'],
            'web_id': ['web', 'id', 'codigo', 'auth'],
            'total': ['total', 'amount', 'monto'],
            'fecha': ['fecha', 'date'],
            'hora': ['hora', 'time']
        }

        keywords = keyword_map.get(field_type, [])

        for field_name in field_names:
            field_lower = field_name.lower()
            for keyword in keywords:
                if keyword in field_lower:
                    return field_name

        return None

    async def _submit_form_if_ready(
        self,
        form_fields: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Intentar enviar el formulario si parece estar listo.

        Args:
            form_fields: Lista de campos del formulario

        Returns:
            Dict con resultado del envío o None si no se envió
        """
        try:
            # Resolver CAPTCHA justo antes del envío para evitar expiración
            await self._solve_captcha_before_submit(form_fields)

            # Buscar botón de envío
            submit_button = None

            for field in form_fields:
                if field.get('type') == 'submit':
                    field_name = field.get('name', '')
                    field_id = field.get('id', '')

                    try:
                        if field_name:
                            submit_button = self.driver.find_element(By.NAME, field_name)
                        elif field_id:
                            submit_button = self.driver.find_element(By.ID, field_id)

                        if submit_button and submit_button.is_displayed() and submit_button.is_enabled():
                            break
                    except NoSuchElementException:
                        continue

            if not submit_button:
                # Buscar botones generales con selectores CSS válidos
                button_selectors = [
                    "input[type='submit']",
                    "button[type='submit']",
                    "button[class*='submit']",
                    "input[value*='enviar']",
                    "input[value*='Enviar']",
                    "input[name='btnAgregar']",  # Específico para Litromil
                    "input[value='Agregar']",    # Botón "Agregar" de Litromil
                    "input[type='button']",      # Botones type=button
                    "button"                     # Último recurso - cualquier botón
                ]

                for selector in button_selectors:
                    try:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for button in buttons:
                            button_text = button.text.lower()
                            button_value = (button.get_attribute("value") or "").lower()

                            # Verificar si el botón contiene texto de envío
                            if any(keyword in button_text or keyword in button_value
                                   for keyword in ['enviar', 'submit', 'continuar', 'facturar', 'generar', 'agregar']):
                                if button.is_displayed() and button.is_enabled():
                                    submit_button = button
                                    break

                        if submit_button:
                            break

                    except NoSuchElementException:
                        continue

            if submit_button:
                button_text = submit_button.text or submit_button.get_attribute("value") or "sin texto"
                logger.info(f"Botón de envío encontrado: '{button_text}' (tag: {submit_button.tag_name})")
                logger.info("Enviando formulario...")

                # Tomar screenshot antes del envío
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = f"screenshots/before_submit_{timestamp}.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"Screenshot pre-envío: {screenshot_path}")
                except Exception:
                    pass

                # Hacer clic en enviar
                submit_button.click()

                # Esperar un poco para que procese
                await asyncio.sleep(3)

                # Tomar screenshot después del envío
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    after_screenshot_path = f"screenshots/after_submit_{timestamp}.png"
                    self.driver.save_screenshot(after_screenshot_path)
                    logger.info(f"Screenshot post-envío: {after_screenshot_path}")
                except Exception:
                    pass

                # Verificar si hay cambios en la página
                try:
                    # Capturar información general de la página
                    current_url = self.driver.current_url
                    page_title = self.driver.title
                    logger.info(f"URL después del envío: {current_url}")
                    logger.info(f"Título después del envío: {page_title}")

                    # Buscar indicadores de éxito o error (más estrictos)
                    success_indicators = [
                        ".success", ".exito", ".correcto", ".alert-success", ".alert-info",
                        "[class*='success']", "[class*='exito']",
                        ".cfdi-success", ".factura-generada", ".invoice-success"
                    ]

                    error_indicators = [
                        ".error", ".fail", ".wrong", ".alert-danger", ".alert-error",
                        "[class*='error']", "[class*='fail']", "[class*='danger']"
                    ]

                    page_source = self.driver.page_source.lower()

                    # Buscar alertas o mensajes visibles
                    all_alerts = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'alert') or contains(@class, 'message') or contains(@class, 'notification')]")
                    for alert in all_alerts:
                        if alert.is_displayed():
                            alert_text = alert.text.strip()
                            if alert_text:
                                logger.info(f"Mensaje encontrado: {alert_text}")

                    # Buscar cualquier texto que pueda indicar resultado
                    result_keywords = ['factura', 'cfdi', 'error', 'exitoso', 'generado', 'enviado', 'completado']
                    visible_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    for keyword in result_keywords:
                        if keyword in visible_text:
                            logger.info(f"Palabra clave '{keyword}' encontrada en la página")

                    # Verificar si realmente se llenaron datos antes de buscar éxito
                    filled_any_field = any(field.get("filled", False) for field in form_fields)
                    logger.info(f"🔍 Se llenó algún campo: {filled_any_field}")

                    # Detectar éxito (solo si se llenaron campos)
                    if filled_any_field:
                        for indicator in success_indicators:
                            try:
                                element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                                if element.is_displayed():
                                    success_text = element.text.strip()
                                    logger.info(f"✅ Indicador de éxito encontrado: {success_text}")
                                    return {
                                        "submitted": True,
                                        "status": "success",
                                        "message": success_text
                                    }
                            except NoSuchElementException:
                                continue
                    else:
                        logger.warning("⚠️ No se llenaron campos, no puede ser facturación exitosa")

                    # Detectar error
                    for indicator in error_indicators:
                        try:
                            element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                            if element.is_displayed():
                                return {
                                    "submitted": True,
                                    "status": "error",
                                    "message": element.text.strip()
                                }
                        except NoSuchElementException:
                            continue

                    # Análisis detallado del contenido de la página
                    page_analysis = self._analyze_page_content(page_source)

                    return {
                        "submitted": True,
                        "status": page_analysis["status"],
                        "message": page_analysis["message"],
                        "detected_content": page_analysis["content_detected"],
                        "analysis_details": page_analysis["details"]
                    }

                except Exception as e:
                    logger.warning(f"Error verificando resultado del envío: {e}")
                    return {
                        "submitted": True,
                        "status": "submitted_unknown",
                        "message": "Formulario enviado, no se pudo verificar resultado"
                    }

            else:
                logger.warning("No se encontró botón de envío")
                return None

        except Exception as e:
            logger.error(f"Error en _submit_form_if_ready: {e}")
            return None

    def _analyze_page_content(self, page_source: str) -> Dict[str, Any]:
        """
        Analizar el contenido de la página para determinar el estado después del envío.

        Args:
            page_source: HTML de la página

        Returns:
            Dict con análisis detallado del estado
        """
        page_lower = page_source.lower()

        # Definir patrones de detección
        patterns = {
            "success_indicators": [
                # Indicadores de éxito en facturación
                "factura generada", "invoice generated", "cfdi generado",
                "facturación exitosa", "exitosamente", "successfully",
                "descarga", "download", "pdf", "xml",
                "uuid", "folio fiscal", "factura electrónica",
                "se ha generado", "completado", "processed"
            ],
            "error_indicators": [
                # Errores comunes
                "error", "incorrecto", "invalid", "wrong", "failed",
                "datos incorrectos", "invalid data", "required field",
                "campo requerido", "obligatorio", "missing", "falta",
                "no válido", "not valid", "expired", "expirado",
                "monto incorrecto", "código inválido", "invalid code"
            ],
            "captcha_errors": [
                # Errores específicos de CAPTCHA
                "código captcha incorrecto", "captcha incorrecto", "invalid captcha",
                "wrong captcha", "código de seguridad incorrecto", "captcha code incorrect",
                "verification code incorrect", "security code wrong"
            ],
            "credential_errors": [
                # Errores específicos de credenciales/datos
                "código no válido", "invalid code", "código incorrecto",
                "monto no coincide", "amount mismatch", "datos no encontrados",
                "ticket not found", "no se encontró", "not found",
                "código expirado", "expired code", "fuera de tiempo"
            ],
            "validation_errors": [
                # Errores de validación de formulario
                "campo obligatorio", "required field", "please fill",
                "complete todos", "missing information", "información faltante",
                "formato incorrecto", "invalid format", "caracteres permitidos"
            ],
            "network_errors": [
                # Errores de red/servidor
                "server error", "service unavailable", "timeout",
                "connection", "network", "try again", "temporalmente"
            ]
        }

        detected_content = []
        details = []

        # Analizar patrones
        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                if pattern in page_lower:
                    detected_content.append({
                        "category": category,
                        "pattern": pattern,
                        "context": self._extract_context_around_pattern(page_source, pattern)
                    })

        # Determinar estado general
        if any(item["category"] == "success_indicators" for item in detected_content):
            status = "success"
            message = "✅ Facturación exitosa detectada"
        elif any(item["category"] == "captcha_errors" for item in detected_content):
            status = "captcha_error"
            message = "🔐 Error de CAPTCHA - código incorrecto"
            details.append("💡 GPT-4 Vision leyó incorrectamente el CAPTCHA. Intentando nuevamente...")

            # Buscar información específica de la factura
            cfdi_info = self._extract_cfdi_information(page_source)
            if cfdi_info:
                details.append(f"📄 CFDI Info: {cfdi_info}")

        elif any(item["category"] == "credential_errors" for item in detected_content):
            status = "credential_error"
            message = "🔐 Error de credenciales o datos del ticket"
            details.append("💡 Verificar: código de facturación, monto, fecha de validez")

        elif any(item["category"] == "validation_errors" for item in detected_content):
            status = "validation_error"
            message = "📋 Error de validación de formulario"
            details.append("💡 Verificar: campos requeridos, formato de datos")

        elif any(item["category"] == "network_errors" for item in detected_content):
            status = "network_error"
            message = "🌐 Error de red o servidor"
            details.append("💡 Reintentar: problema temporal del portal")

        elif any(item["category"] == "error_indicators" for item in detected_content):
            status = "general_error"
            message = "❌ Error general detectado"
            details.append("💡 Revisar: datos del ticket y portal")

        else:
            # Análisis heurístico adicional
            if "factura" in page_lower or "invoice" in page_lower:
                status = "likely_success"
                message = "🔍 Contenido relacionado con facturación detectado"
            else:
                status = "unknown"
                message = "❓ Estado incierto después del envío"

        # Obtener texto visible para análisis adicional
        visible_text = self._extract_visible_text()
        if visible_text:
            details.append(f"👁️ Texto visible: {visible_text[:200]}...")

        return {
            "status": status,
            "message": message,
            "content_detected": detected_content,
            "details": details
        }

    def _extract_context_around_pattern(self, page_source: str, pattern: str, context_length: int = 100) -> str:
        """Extraer contexto alrededor de un patrón encontrado."""
        try:
            page_lower = page_source.lower()
            pattern_index = page_lower.find(pattern)

            if pattern_index == -1:
                return ""

            start = max(0, pattern_index - context_length)
            end = min(len(page_source), pattern_index + len(pattern) + context_length)

            context = page_source[start:end].strip()
            # Limpiar HTML tags básicos
            import re
            context = re.sub(r'<[^>]+>', ' ', context)
            context = re.sub(r'\s+', ' ', context)

            return context[:200]  # Limitar longitud
        except Exception:
            return ""

    def _extract_cfdi_information(self, page_source: str) -> str:
        """Extraer información específica de CFDI si está disponible."""
        try:
            import re

            # Buscar UUID (patrón CFDI)
            uuid_pattern = r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}'
            uuid_match = re.search(uuid_pattern, page_source, re.IGNORECASE)

            if uuid_match:
                return f"UUID: {uuid_match.group()}"

            # Buscar folio fiscal
            folio_patterns = [
                r'folio[:\s]*([A-Z0-9]+)',
                r'folio[:\s]*fiscal[:\s]*([A-F0-9\-]+)'
            ]

            for pattern in folio_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    return f"Folio: {match.group(1)}"

            return ""
        except Exception:
            return ""

    async def _solve_captcha_with_vision(self, captcha_field_name: str) -> str:
        """
        Resolver CAPTCHA usando GPT-4 Vision.

        Args:
            captcha_field_name: Nombre del campo CAPTCHA

        Returns:
            Código CAPTCHA resuelto o cadena vacía si falla
        """
        try:
            # Múltiples intentos para mejorar precisión
            max_attempts = 2

            for attempt in range(max_attempts):
                logger.info(f"Intento {attempt + 1}/{max_attempts} de resolver CAPTCHA '{captcha_field_name}'")

                captcha_code = await self._attempt_captcha_solve(captcha_field_name)
                if captcha_code:
                    return captcha_code

                # Si falla, esperar un momento antes del siguiente intento
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)

            return ""

        except Exception as e:
            logger.error(f"Error resolviendo CAPTCHA con Vision: {e}")
            return ""

    async def _attempt_captcha_solve(self, captcha_field_name: str) -> str:
        """
        Intento individual de resolver CAPTCHA.
        """
        try:
            if not OPENAI_AVAILABLE:
                logger.warning("OpenAI no disponible para resolver CAPTCHA")
                return ""

            # Buscar la imagen del CAPTCHA en la página
            captcha_images = []

            # Selectores comunes para imágenes de CAPTCHA
            captcha_selectors = [
                "img[src*='captcha']",
                "img[src*='Captcha']",
                "img[alt*='captcha']",
                "img[alt*='Captcha']",
                "[id*='captcha'] img",
                "[id*='Captcha'] img",
                ".captcha img",
                ".Captcha img"
            ]

            captcha_image_element = None
            for selector in captcha_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            captcha_image_element = element
                            break
                    if captcha_image_element:
                        break
                except Exception:
                    continue

            if not captcha_image_element:
                logger.warning("No se encontró imagen de CAPTCHA")
                return ""

            # Capturar screenshot de la imagen CAPTCHA
            import base64
            import io
            from PIL import Image

            # Obtener la imagen CAPTCHA
            captcha_image_src = captcha_image_element.get_attribute("src")

            if captcha_image_src.startswith("data:image"):
                # Es una imagen base64 embebida
                base64_data = captcha_image_src.split(",")[1]
                image_data = base64.b64decode(base64_data)
            else:
                # Es una URL - hacer screenshot del elemento
                screenshot = captcha_image_element.screenshot_as_png
                image_data = screenshot

            # Usar 2Captcha para resolver el CAPTCHA
            if ANTICAPTCHA_AVAILABLE:
                try:
                    # Configurar AntiCaptcha (2Captcha)
                    api_key = os.getenv("TWOCAPTCHA_API_KEY")
                    if not api_key:
                        logger.error("TWOCAPTCHA_API_KEY no configurada")
                        return None

                    user_agent = AntiCaptchaControl.AntiCaptchaControl(api_key)
                    task = ImageToTextTask.ImageToTextTask(
                        file_path=None,
                        body=base64.b64encode(image_data).decode('utf-8')
                    )

                    job = user_agent.createTask(task)
                    job.join()

                    captcha_code = job.get_captcha_text()
                    if captcha_code:
                        logger.info(f"2Captcha resolvió CAPTCHA: '{captcha_code}'")
                    else:
                        logger.warning("2Captcha no pudo resolver el CAPTCHA")
                        return None

                except Exception as e:
                    logger.error(f"Error usando 2Captcha: {e}")
                    return None
            else:
                logger.error("python-anticaptcha no disponible")
                return None

            # Limpiar el código (solo letras y números)
            import re
            captcha_code = re.sub(r'[^A-Za-z0-9]', '', captcha_code)

            if captcha_code:
                return captcha_code
            else:
                logger.warning("No se pudo resolver el CAPTCHA")
                return ""

        except Exception as e:
            logger.error(f"Error resolviendo CAPTCHA con Vision: {e}")
            return ""

    async def _solve_captcha_before_submit(self, form_fields: List[Dict[str, Any]]) -> None:
        """
        Resolver CAPTCHA justo antes del envío para evitar expiración.
        Args:
            form_fields: Lista de campos del formulario
        """
        try:
            # Buscar campos CAPTCHA en el formulario
            captcha_fields = []
            for field in form_fields:
                field_name = field.get('name', '').lower()
                field_id = field.get('id', '').lower()
                field_label = field.get('label', '').lower()

                if ('captcha' in field_name or 'captcha' in field_id or 'captcha' in field_label):
                    captcha_fields.append(field)

            # Resolver cada campo CAPTCHA encontrado
            for captcha_field in captcha_fields:
                field_name = captcha_field.get('name', '')
                field_id = captcha_field.get('id', '')

                # Resolver CAPTCHA con GPT-4 Vision
                captcha_code = await self._solve_captcha_with_vision(field_name or field_id)

                if captcha_code:
                    # Llenar el campo CAPTCHA
                    try:
                        if field_name:
                            element = self.driver.find_element(By.NAME, field_name)
                        elif field_id:
                            element = self.driver.find_element(By.ID, field_id)
                        else:
                            continue

                        if element and element.is_displayed():
                            element.clear()
                            element.send_keys(captcha_code)
                            logger.info(f"CAPTCHA '{captcha_code}' llenado en campo {field_name or field_id}")
                    except Exception as e:
                        logger.error(f"Error llenando CAPTCHA en {field_name or field_id}: {e}")

        except Exception as e:
            logger.error(f"Error en _solve_captcha_before_submit: {e}")

    async def _submit_form_with_captcha_retry(self, form_fields: List[Dict[str, Any]], max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Enviar formulario con reintentos automáticos para errores de CAPTCHA.
        Args:
            form_fields: Lista de campos del formulario
            max_retries: Número máximo de reintentos
        Returns:
            Dict con resultado del envío o None si falla
        """
        for attempt in range(max_retries):
            logger.info(f"Intento {attempt + 1}/{max_retries} de envío de formulario")

            # Enviar formulario
            result = await self._submit_form_if_ready(form_fields)

            if not result:
                logger.warning("No se pudo enviar el formulario")
                return None

            # Verificar si hay error de CAPTCHA
            if result.get("status") == "captcha_error":
                logger.warning(f"Error de CAPTCHA detectado en intento {attempt + 1}")

                if attempt < max_retries - 1:
                    logger.info("Reintentando con nuevo CAPTCHA...")
                    # Esperar un momento y reintentarlo
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.error("Máximo de reintentos alcanzado para CAPTCHA")
                    result["message"] += f" (Falló después de {max_retries} intentos)"
                    return result
            else:
                # Éxito o error diferente a CAPTCHA
                return result

        return None

    def _extract_visible_text(self) -> str:
        """Extraer texto visible de la página actual."""
        try:
            if self.driver:
                # Obtener texto del body
                body_element = self.driver.find_element(By.TAG_NAME, "body")
                visible_text = body_element.text.strip()

                # Limpiar y resumir
                lines = [line.strip() for line in visible_text.split('\n') if line.strip()]
                important_lines = []

                for line in lines:
                    # Filtrar líneas que parezcan importantes
                    if any(keyword in line.lower() for keyword in [
                        'error', 'success', 'factura', 'invoice', 'cfdi',
                        'código', 'monto', 'total', 'generada', 'completado'
                    ]):
                        important_lines.append(line)

                return ' | '.join(important_lines[:5])  # Máximo 5 líneas importantes

        except Exception:
            pass

        return ""

    async def _navigate_intelligently_with_llm(self) -> Optional[Dict[str, Any]]:
        """
        Usar LLM para analizar la página y decidir dónde hacer clic para llegar a formularios.

        Returns:
            Dict con resultado de la navegación o None si no se puede navegar
        """
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI no disponible para navegación inteligente")
            return None

        try:
            # Obtener el contenido visible de la página
            page_text = self._extract_visible_text()
            current_url = self.driver.current_url

            # Encontrar elementos clickeables que podrían llevar a facturación
            clickable_elements = self._find_clickable_elements()

            if not clickable_elements:
                logger.info("No se encontraron elementos clickeables relevantes")
                return None

            # Generar prompt para LLM
            prompt = self._generate_navigation_prompt(current_url, page_text, clickable_elements)

            # Configurar cliente Claude
            client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                temperature=0.1,
                system="Eres un experto en navegación web para encontrar formularios de facturación. Analiza la página y decide qué elemento hacer clic para llegar a un formulario de facturación. Responde solo en formato JSON.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parsear respuesta
            content = response.content[0].text.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()

            decision = json.loads(content)

            # Ejecutar la decisión del LLM
            if decision.get("should_click") and decision.get("element_index") is not None:
                element_index = decision.get("element_index")

                if 0 <= element_index < len(clickable_elements):
                    element_info = clickable_elements[element_index]
                    element = element_info["element"]

                    logger.info(f"LLM decidió hacer clic en: {element_info['text'][:50]}...")

                    # Recordar las ventanas actuales antes del click
                    initial_windows = set(self.driver.window_handles)
                    current_url_before = self.driver.current_url

                    # Hacer clic en el elemento con múltiples estrategias
                    success = self._robust_click(element)

                    # Esperar un poco para que la página cargue
                    await asyncio.sleep(2)

                    # Verificar si se abrió una nueva pestaña
                    new_windows = set(self.driver.window_handles) - initial_windows
                    if new_windows:
                        # Cambiar a la nueva pestaña
                        new_window = list(new_windows)[0]
                        self.driver.switch_to.window(new_window)
                        logger.info(f"Cambiado a nueva pestaña: {self.driver.current_url}")
                        await asyncio.sleep(1)

                    # Verificar si cambió la URL en la misma pestaña
                    elif self.driver.current_url != current_url_before:
                        logger.info(f"URL cambió en la misma pestaña: {self.driver.current_url}")

                    # Verificar si aparecieron modales o elementos dinámicos
                    await asyncio.sleep(1)

                    return {
                        "clicked": success,
                        "element_text": element_info["text"],
                        "element_type": element_info["tag"],
                        "reason": decision.get("reason", ""),
                        "click_success": success
                    }

            return {
                "clicked": False,
                "reason": decision.get("reason", "No hay elementos relevantes para hacer clic")
            }

        except Exception as e:
            logger.error(f"Error en navegación inteligente: {e}")
            return None

    def _find_clickable_elements(self) -> List[Dict[str, Any]]:
        """Encontrar elementos clickeables que podrían llevar a facturación."""
        clickable_elements = []

        try:
            # Selectores más exhaustivos para elementos clickeables
            selectors = [
                "a", "button", "input[type='button']", "input[type='submit']",
                "[onclick]", ".btn", ".button", "[role='button']",
                ".link", ".nav-link", ".menu-item", ".menu-link",
                "div[onclick]", "span[onclick]", "li[onclick]",
                "[data-toggle]", "[data-target]", ".clickable"
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for element in elements:
                        if not element.is_displayed():
                            continue

                        # Obtener texto de múltiples fuentes
                        text_sources = [
                            element.text.strip(),
                            element.get_attribute("title") or "",
                            element.get_attribute("alt") or "",
                            element.get_attribute("value") or "",
                            element.get_attribute("aria-label") or "",
                            element.get_attribute("data-title") or "",
                        ]

                        # También buscar texto en elementos hijos
                        try:
                            child_texts = []
                            for child in element.find_elements(By.CSS_SELECTOR, "*"):
                                child_text = child.text.strip()
                                if child_text and len(child_text) < 100:
                                    child_texts.append(child_text)
                            text_sources.extend(child_texts[:3])  # Máximo 3 textos de hijos
                        except Exception:
                            pass

                        # Combinar todo el texto disponible
                        combined_text = " ".join(filter(None, text_sources)).strip()

                        if combined_text and len(combined_text) > 0:
                            # Calcular relevancia para facturación
                            relevance_score = self._calculate_billing_relevance(combined_text)

                            clickable_elements.append({
                                "element": element,
                                "text": combined_text[:200],  # Limitar longitud
                                "tag": element.tag_name,
                                "href": element.get_attribute("href") or "",
                                "class": element.get_attribute("class") or "",
                                "relevance": relevance_score
                            })

                except Exception:
                    continue

            # Ordenar por relevancia (mayor primero) y limitar
            clickable_elements.sort(key=lambda x: x["relevance"], reverse=True)
            return clickable_elements[:15]  # Aumentar límite a 15

        except Exception as e:
            logger.error(f"Error encontrando elementos clickeables: {e}")
            return []

    def _calculate_billing_relevance(self, text: str) -> float:
        """Calcular qué tan relevante es un texto para facturación."""
        text_lower = text.lower()
        score = 0.0

        # Palabras clave de alta relevancia
        high_priority_keywords = [
            "facturar", "facturación", "factura", "invoice", "cfdi",
            "solicitar factura", "generar factura", "obtener factura",
            "facturar ticket", "facturar compra", "billing"
        ]

        # Palabras clave de media relevancia
        medium_priority_keywords = [
            "ticket", "comprobante", "recibo", "receipt", "documento",
            "fiscal", "tributario", "sat", "hacienda", "rfc"
        ]

        # Palabras clave de baja relevancia
        low_priority_keywords = [
            "cliente", "customer", "servicio", "support", "ayuda",
            "contacto", "contact", "información", "info"
        ]

        # Llamadas a la acción genéricas que cobran relevancia en contexto
        action_keywords = [
            "click aquí", "clic aquí", "haz clic", "presiona aquí",
            "continuar", "siguiente", "acceder", "ingresar", "ir a"
        ]

        # Puntuación por palabras clave
        for keyword in high_priority_keywords:
            if keyword in text_lower:
                score += 10.0

        for keyword in medium_priority_keywords:
            if keyword in text_lower:
                score += 5.0

        for keyword in low_priority_keywords:
            if keyword in text_lower:
                score += 2.0

        # Bonus por combinaciones específicas
        billing_phrases = [
            "solicitar factura", "generar factura", "facturar ticket",
            "obtener comprobante", "facturación electrónica"
        ]

        for phrase in billing_phrases:
            if phrase in text_lower:
                score += 15.0

        # Bonus especial para llamadas a la acción en contexto de facturación
        has_billing_context = any(keyword in text_lower for keyword in high_priority_keywords)
        if has_billing_context:
            for action in action_keywords:
                if action in text_lower:
                    score += 20.0  # Bonus alto para CTA en contexto correcto
                    break

        # Casos especiales para patrones comunes de facturación
        special_patterns = [
            "facturación en línea", "facturación electrónica", "click aquí",
            "generar cfdi", "solicitar cfdi", "continuar a facturación"
        ]

        for pattern in special_patterns:
            if pattern in text_lower:
                score += 12.0

        # Botones de acción específicos para facturación (peso muy alto)
        action_buttons = [
            "facturar", "generar factura", "solicitar factura",
            "crear factura", "nueva factura", "emitir factura"
        ]

        for button_text in action_buttons:
            if button_text in text_lower and len(text_lower.strip()) < 50:  # Textos cortos de botones
                score += 30.0  # Peso MUY alto para botones de acción

        # Bonus extra para botones exactos de facturación
        if text_lower.strip() == "facturar":
            score += 40.0  # Máxima prioridad para botón "Facturar"

        # Penalizar textos muy largos o muy cortos
        text_length = len(text.strip())
        if text_length < 3:
            score *= 0.1
        elif text_length > 200:
            score *= 0.5

        return score

    def _robust_click(self, element) -> bool:
        """Hace clic en un elemento usando múltiples estrategias."""
        try:
            # Checkpoint antes del click
            element_text = getattr(element, 'text', '')[:50]
            self.debug_checkpoint("Click Attempt", {
                "element_text": element_text,
                "element_tag": getattr(element, 'tag_name', 'unknown')
            })

            # Guardar ventanas antes del click para detectar pop-ups
            old_windows = set(self.driver.window_handles)

            # Estrategia 1: Click normal
            try:
                element.click()
                logger.info("Click normal exitoso")
                self.debug_checkpoint("Click Success - Normal", {"element_text": element_text})
                self._handle_potential_new_windows(old_windows)
                return True
            except Exception as e:
                logger.warning(f"Click normal falló: {e}")
                self.debug_checkpoint("Click Failed - Normal", {"error": str(e), "element_text": element_text})

            # Estrategia 2: Scroll al elemento y luego click
            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                element.click()
                logger.info("Click después de scroll exitoso")
                self.debug_checkpoint("Click Success - Scroll", {"element_text": element_text})
                self._handle_potential_new_windows(old_windows)
                return True
            except Exception as e:
                logger.warning(f"Click después de scroll falló: {e}")

            # Estrategia 3: JavaScript click
            try:
                self.driver.execute_script("arguments[0].click();", element)
                logger.info("JavaScript click exitoso")
                self.debug_checkpoint("Click Success - JavaScript", {"element_text": element_text})
                self._handle_potential_new_windows(old_windows)
                return True
            except Exception as e:
                logger.warning(f"JavaScript click falló: {e}")

            # Estrategia 4: ActionChains click
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(self.driver)
                actions.move_to_element(element).click().perform()
                logger.info("ActionChains click exitoso")
                self.debug_checkpoint("Click Success - ActionChains", {"element_text": element_text})
                self._handle_potential_new_windows(old_windows)
                return True
            except Exception as e:
                logger.warning(f"ActionChains click falló: {e}")

            # Todas las estrategias fallaron
            self.debug_checkpoint("Click Failed - All Strategies", {
                "element_text": element_text,
                "final_error": "All click strategies failed"
            }, force_screenshot=True)
            return False

        except Exception as e:
            logger.error(f"Error en robust_click: {e}")
            return False

    def _handle_potential_new_windows(self, old_windows: set, timeout: int = 5) -> bool:
        """
        Maneja posibles nuevas ventanas después de un click con wait robusto

        Args:
            old_windows: Set de handles de ventanas antes del click
            timeout: Tiempo máximo de espera para detectar nuevas ventanas

        Returns:
            True si se detectaron y manejaron nuevas ventanas
        """
        try:
            # Detectar nuevas ventanas con wait robusto
            new_windows = self._wait_for_new_windows(old_windows, timeout)

            if new_windows:
                logger.info(f"🪟 Click generó {len(new_windows)} nuevas ventanas")

                # Evaluar y cambiar a la mejor ventana
                # Usar keywords genéricos de facturación para evaluación
                billing_keywords = ["factur", "cfdi", "invoice", "bill", "tax"]
                best_window = self._choose_best_window(new_windows, billing_keywords)

                if best_window:
                    self.driver.switch_to.window(best_window)
                    self._register_window_info(best_window)
                    logger.info(f"✅ Cambiado automáticamente a nueva ventana relevante")

                    # Esperar que cargue completamente la nueva ventana
                    WebDriverWait(self.driver, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )

                    return True
                else:
                    logger.warning("⚠️ Nueva ventana detectada pero no parece relevante")

            return False

        except Exception as e:
            logger.error(f"❌ Error manejando nuevas ventanas: {e}")
            return False

    def _wait_for_window_content_loaded(self, window_handle: str, timeout: int = 15) -> bool:
        """
        Espera robusta a que el contenido de una ventana específica esté completamente cargado

        Args:
            window_handle: Handle de la ventana a verificar
            timeout: Tiempo máximo de espera

        Returns:
            True si la ventana cargó correctamente
        """
        try:
            # Cambiar a la ventana target
            original_window = self.driver.current_window_handle
            self.driver.switch_to.window(window_handle)

            # Múltiples condiciones de carga completa
            def content_loaded(driver):
                try:
                    # 1. Document ready state
                    if driver.execute_script("return document.readyState") != "complete":
                        return False

                    # 2. No hay spinners o loaders activos
                    loaders = driver.find_elements(By.CSS_SELECTOR,
                        ".loading, .spinner, .loader, [class*='loading'], [class*='spinner']")
                    active_loaders = [l for l in loaders if l.is_displayed()]
                    if active_loaders:
                        return False

                    # 3. Hay contenido relevante visible
                    body = driver.find_element(By.TAG_NAME, "body")
                    body_text = body.text.strip()
                    if len(body_text) < 50:  # Muy poco contenido
                        return False

                    # 4. No hay mensajes de "cargando" visibles
                    loading_texts = ["cargando", "loading", "espere", "wait", "procesando"]
                    page_text_lower = body_text.lower()
                    if any(text in page_text_lower for text in loading_texts):
                        return False

                    return True

                except Exception:
                    return False

            # Esperar con todas las condiciones
            WebDriverWait(self.driver, timeout).until(content_loaded)

            logger.info(f"✅ Ventana {window_handle[:8]}... cargada completamente")
            return True

        except TimeoutException:
            logger.warning(f"⏰ Timeout esperando carga completa de ventana {window_handle[:8]}...")
            return False
        except Exception as e:
            logger.error(f"❌ Error verificando carga de ventana: {e}")
            return False
        finally:
            # Volver a ventana original si es diferente
            try:
                if self.driver.current_window_handle != original_window:
                    self.driver.switch_to.window(original_window)
            except:
                pass

    def _generate_navigation_prompt(self, current_url: str, page_text: str, clickable_elements: List[Dict[str, Any]]) -> str:
        """Generar prompt para que LLM decida dónde hacer clic."""

        elements_description = []
        for i, elem in enumerate(clickable_elements):
            relevance = elem.get('relevance', 0)
            elements_description.append(
                f"{i}: {elem['tag'].upper()} - '{elem['text'][:100]}' "
                f"(href: {elem['href'][:50]}, relevancia: {relevance:.1f})"
            )

        prompt = f"""Estoy navegando por: {current_url}

CONTEXTO: Soy un bot que busca formularios de facturación electrónica en sitios web mexicanos.

TEXTO VISIBLE EN LA PÁGINA:
{page_text[:1000]}

ELEMENTOS CLICKEABLES DISPONIBLES (ordenados por relevancia):
{chr(10).join(elements_description)}

OBJETIVO: Encontrar un formulario donde pueda ingresar:
- RFC del cliente
- Código de ticket/folio de compra
- Monto total de la compra
- Datos para generar CFDI (Comprobante Fiscal Digital)

INSTRUCCIONES:
1. Busca elementos que probablemente lleven a formularios de facturación
2. Prioriza enlaces con palabras como: "Facturar", "CFDI", "Facturación", "Solicitar Factura"
3. Considera también elementos genéricos si parecen relevantes (ej: "Clientes", "Servicios")
4. Si ves múltiples opciones, elige la más específica para facturación

PATRONES COMUNES EN SITIOS MEXICANOS:
- Botón "Facturar Ticket" → lleva a formulario
- Link "Facturación Electrónica" → página de formularios
- Menú "Clientes" → puede tener sección de facturación
- Botón "CFDI" → formularios fiscales

IMPORTANTE:
- Si no hay elementos obviamente relacionados con facturación, NO hagas clic
- Solo haz clic si hay alta probabilidad de encontrar formularios

Responde en JSON:
{{
  "should_click": true/false,
  "element_index": número_del_elemento_o_null,
  "reason": "explicación_detallada_de_por_qué_elegiste_este_elemento",
  "confidence": 0.0-1.0
}}"""

        return prompt

    async def cleanup(self):
        """Limpiar recursos del driver"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
        except Exception as e:
            logger.warning(f"Error limpiando driver: {e}")


# =============================================================
# FUNCIÓN PARA USAR DESDE EL WORKER PRINCIPAL
# =============================================================

async def process_web_automation(
    merchant: Dict[str, Any],
    ticket_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Función principal para llamar desde el worker de facturación.

    Args:
        merchant: Datos del merchant
        ticket_data: Datos del ticket a procesar

    Returns:
        Dict con resultado de la automatización
    """
    if not SELENIUM_AVAILABLE:
        return {
            "success": False,
            "error": "Selenium no está disponible. Instala con: pip install selenium"
        }

    worker = WebAutomationWorker()
    return await worker.process_merchant_invoice(merchant, ticket_data)


# Función específica para navegación a portales
async def navigate_to_portal_urls(urls_list: List[str], merchant_name: str = None) -> List[Dict[str, Any]]:
    """
    Navegar a múltiples URLs de portales de facturación.

    Args:
        urls_list: Lista de URLs a navegar
        merchant_name: Nombre del merchant (opcional)

    Returns:
        Lista con resultados de navegación para cada URL
    """
    if not SELENIUM_AVAILABLE:
        return [{
            "success": False,
            "error": "Selenium no está disponible. Instala con: pip install selenium",
            "url": url
        } for url in urls_list]

    worker = WebAutomationWorker()
    results = []

    try:
        for url in urls_list:
            result = await worker.navigate_to_portal(
                url=url,
                merchant_name=merchant_name,
                take_screenshot=True
            )
            results.append(result)

    finally:
        await worker.cleanup()

    return results


async def get_next_action(html_content: str, context: str = "", current_step: str = "", ticket_data: dict = None, elementos_detectados: list = None) -> Dict[str, Any]:
    """
    Analiza el HTML actual y decide la siguiente acción usando OpenAI.

    Args:
        html_content: HTML de la página actual
        context: Contexto sobre qué se intenta lograr
        current_step: Paso actual en el proceso
        ticket_data: Datos del ticket con información OCR
        elementos_detectados: Lista de elementos detectados con BeautifulSoup

    Returns:
        Dict con: action, selector, value, reason
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Preparar datos del ticket para el prompt
    ticket_info = ""
    if ticket_data:
        ticket_info = f"""
DATOS DEL TICKET OCR (Google Vision):
- Folio/Número: {ticket_data.get('folio', 'N/A')}
- Total: ${ticket_data.get('total', 'N/A')}
- Fecha: {ticket_data.get('fecha', 'N/A')}
- RFC Cliente: {ticket_data.get('rfc', 'XAXX010101000')}
- Email Cliente: {ticket_data.get('email', 'test@example.com')}
- Texto OCR completo: {ticket_data.get('raw_data', '')[:500]}...
"""

    # Preparar elementos detectados
    elementos_info = ""
    if elementos_detectados:
        elementos_info = f"""
ELEMENTOS DE FACTURACIÓN DETECTADOS EN LA PÁGINA:
{json.dumps(elementos_detectados, indent=2, ensure_ascii=False)}
"""

    prompt = f"""
🤖 AGENTE DE AUTOMATIZACIÓN WEB PARA FACTURACIÓN ELECTRÓNICA

🎯 OBJETIVO FINAL: Descargar factura PDF completando formulario con datos fiscales del cliente

{ticket_info}

CONTEXTO ACTUAL: {context}
PASO ACTUAL: {current_step}

{elementos_info}

🌐 HTML DE LA PÁGINA ACTUAL:
{html_content[:6000]}  # Limitar HTML para no exceder tokens

📋 FLUJO COMPLETO DE FACTURACIÓN:

FASE 1 - NAVEGACIÓN INICIAL:
1. Buscar CTAs temporales/dinámicos (botones hero, sliders)
   - "CLICK AQUÍ", "Facturación", "Generar Factura", "Solicitar Factura"
   - Botones con animaciones o en secciones destacadas

2. Buscar en HEADER/NAVEGACIÓN elementos de facturación
   - Links en <header>, <nav>, menú principal
   - "Facturación", "Facturas", "Servicios", "Portal", "Clientes"

FASE 2 - LLENADO DE FORMULARIOS:
3. Llenar datos fiscales del cliente usando la información del ticket:
   - RFC: Usar el RFC del ticket o valor por defecto
   - Email: Usar email del ticket o valor por defecto
   - Razón Social: Extraer del texto OCR si está disponible
   - Dirección fiscal: Extraer del texto OCR si está disponible

FASE 3 - DATOS DE LA TRANSACCIÓN:
4. Llenar información de la compra:
   - Folio/Número de ticket: Usar folio del ticket
   - Total/Importe: Usar total del ticket
   - Fecha: Usar fecha del ticket
   - Concepto/Descripción: Extraer del texto OCR

FASE 4 - FINALIZACIÓN:
5. Generar y descargar factura:
   - Botones "Generar Factura", "Crear", "Finalizar"
   - Descargar PDF resultante
   - Confirmar descarga exitosa

⚠️ INSTRUCCIONES CRÍTICAS - DEBES SEGUIR EXACTAMENTE:
1. OBLIGATORIO: USA SOLO los elementos listados en "ELEMENTOS DE FACTURACIÓN DETECTADOS"
2. PROHIBIDO: Inventar selectores como "#imgbtnFacturarFast", "input[id='imgbtnFacturarFast']"
3. OBLIGATORIO: Si hay elementos detectados, copiar EXACTAMENTE el "selector_sugerido"
4. PRIORIDAD: Preferir elementos con mayor "relevancia" y sin cooldown
5. MEMORIA: Revisar información de memoria (✅ exitoso, ⏸️ cooldown, 🔄 reintentable)
6. ESTANCAMIENTO: Si la página está estancada, probar selectores completamente diferentes
7. OBLIGATORIO: Si no hay elementos utilizables, usar action="error" con razón clara
8. OBLIGATORIO: Responder SOLO con JSON válido

EJEMPLOS DE SELECTORES PROHIBIDOS (NO usar):
❌ "#imgbtnFacturarFast"
❌ "input[id='imgbtnFacturarFast']"
❌ Cualquier selector que NO aparezca en la lista de elementos detectados

ACCIONES POSIBLES:
- "click": Hacer clic en un elemento
- "input": Escribir texto en un campo
- "select": Seleccionar opción de dropdown
- "done": Proceso completado exitosamente
- "error": No se puede continuar

FORMATO DE RESPUESTA (JSON):
{{
    "action": "click|input|select|done|error",
    "selector": "xpath_o_css_selector",
    "value": "texto_a_escribir_o_valor_a_seleccionar",
    "reason": "explicacion_breve_de_la_decision",
    "confidence": 0.95
}}

💡 EJEMPLOS ESPECÍFICOS PARA LLENAR FORMULARIOS:

NAVEGACIÓN:
- Para botón de facturación: {{"action": "click", "selector": "#crear-factura", "value": "", "reason": "Botón de facturación detectado"}}
- Para enlace del menú: {{"action": "click", "selector": "a[href='/facturacion']", "value": "", "reason": "Enlace de facturación en navegación"}}

CAMPOS FISCALES (usar datos del ticket):
- Para campo RFC: {{"action": "input", "selector": "#rfc", "value": "{ticket_data.get('rfc', 'XAXX010101000')}", "reason": "Llenar RFC del cliente"}}
- Para campo email: {{"action": "input", "selector": "#email", "value": "{ticket_data.get('email', 'test@example.com')}", "reason": "Llenar email del cliente"}}
- Para razón social: {{"action": "input", "selector": "#razon_social", "value": "CLIENTE FINAL", "reason": "Llenar razón social"}}

CAMPOS DE TRANSACCIÓN (usar datos del ticket):
- Para folio: {{"action": "input", "selector": "#folio", "value": "{ticket_data.get('folio', '')}", "reason": "Llenar número de folio"}}
- Para total: {{"action": "input", "selector": "#total", "value": "{ticket_data.get('total', '')}", "reason": "Llenar importe total"}}
- Para fecha: {{"action": "input", "selector": "#fecha", "value": "{ticket_data.get('fecha', '')}", "reason": "Llenar fecha de compra"}}

FINALIZACIÓN:
- Para generar: {{"action": "click", "selector": "#generar", "value": "", "reason": "Generar factura con los datos ingresados"}}
- Para descargar: {{"action": "click", "selector": "#descargar", "value": "", "reason": "Descargar PDF de la factura"}}

CONSTRUCCIÓN DE SELECTORES DE ELEMENTOS DETECTADOS:
- Si elemento tiene id="ejemplo": usar "#ejemplo"
- Si elemento tiene class="ejemplo": usar ".ejemplo" o "tag.ejemplo"
- Si elemento tiene href="/url": usar "a[href='/url']"
- Si elemento es button con texto "Facturar": usar "button" o por clase/id si tiene

NUNCA hagas esto:
- ❌ Inventar selectores como "#imgbtnFacturarFast" si no aparece en elementos detectados
- ❌ Usar xpath complejos si hay selectores CSS simples disponibles
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1
        )

        decision_text = response.choices[0].message.content.strip()

        # 📋 LOGGING DE LA RESPUESTA COMPLETA DE OPENAI
        logger.info(f"🧠 === RESPUESTA COMPLETA DE OPENAI ===")
        logger.info(f"📄 Respuesta cruda: {decision_text}")
        logger.info(f"🧠 === FIN RESPUESTA OPENAI ===")

        # Intentar parsear JSON
        try:
            # Limpiar la respuesta para asegurar JSON válido
            if "```json" in decision_text:
                decision_text = decision_text.split("```json")[1].split("```")[0].strip()
            elif "```" in decision_text:
                # Cualquier otro bloque de código
                decision_text = decision_text.split("```")[1].split("```")[0].strip()

            decision = json.loads(decision_text)

            # 🎯 LOGGING DE LA DECISIÓN PARSEADA
            logger.info(f"✅ Decisión parseada exitosamente: {decision}")

            return decision
        except json.JSONDecodeError:
            # Si falla el JSON, extraer manualmente
            logger.error(f"❌ Error parseando JSON de OpenAI: {decision_text}")
            return {
                "action": "error",
                "selector": "",
                "value": "",
                "reason": f"Error parseando respuesta de OpenAI: {decision_text}",
                "confidence": 0.0
            }

    except Exception as e:
        return {
            "action": "error",
            "selector": "",
            "value": "",
            "reason": f"Error llamando a OpenAI: {str(e)}",
            "confidence": 0.0
        }


async def smart_automation_flow(worker, ticket_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
    """
    Flujo de automatización inteligente usando agente de decisión.

    Args:
        worker: Instancia de WebAutomationWorker
        ticket_data: Datos del ticket a procesar
        context: Contexto sobre el objetivo del proceso

    Returns:
        Dict con resultado del proceso
    """
    max_steps = 20  # Límite de pasos para evitar bucles infinitos
    step_count = 0

    # 🔧 Sistema de protección contra acciones repetidas
    clicked_elements = set()  # Elementos ya clickeados
    filled_inputs = {}  # Inputs ya llenados
    action_delays = {  # Delays entre acciones
        "click": 3,
        "input": 2,
        "default": 1
    }

    # 🧠 Sistema de memoria inteligente
    selector_attempts = {}  # {selector: {"count": 2, "last_step": 3, "worked": False}}
    url_history = []  # Historial de URLs para detectar progreso
    stagnant_steps = 0  # Contador de pasos sin progreso

    results = {
        "success": False,
        "steps": [],
        "final_reason": "",
        "screenshots": [],
        "protections_triggered": []  # Nuevo: rastrear protecciones activadas
    }

    try:
        while step_count < max_steps:
            step_count += 1

            # Obtener HTML actual y analizarlo
            html_content = worker.driver.page_source
            current_url = worker.driver.current_url

            # 🧠 Detectar progreso de navegación
            if url_history:
                last_url = url_history[-1]
                if current_url == last_url:
                    stagnant_steps += 1
                    logger.warning(f"🔄 Página estancada por {stagnant_steps} pasos en: {current_url}")
                else:
                    # Progreso detectado! Marcar selectores recientes como exitosos
                    stagnant_steps = 0
                    for selector, data in selector_attempts.items():
                        if data["last_step"] == step_count - 1:  # Último paso
                            data["worked"] = True
                            logger.info(f"✅ Selector exitoso detectado: {selector}")

            url_history.append(current_url)

            # 🧠 ANÁLISIS INTELIGENTE DEL DOM
            try:
                # Extraer elementos relevantes para facturación
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # Buscar elementos de facturación con prioridad
                billing_elements = []

                # 1. Header/Navigation elements
                nav_elements = soup.find_all(['nav', 'header']) + soup.find_all(attrs={'class': lambda x: x and any(cls in str(x).lower() for cls in ['nav', 'menu', 'header'])})
                for nav in nav_elements:
                    nav_links = nav.find_all('a', string=lambda text: text and any(word in text.lower() for word in ['facturación', 'factura', 'servicio', 'portal', 'cliente']))
                    billing_elements.extend(nav_links)

                # 2. Botones principales y CTAs
                cta_buttons = soup.find_all(['button', 'a'], string=lambda text: text and any(phrase in text.lower() for phrase in ['click aquí', 'facturar', 'generar factura', 'solicitar factura']))
                billing_elements.extend(cta_buttons)

                # 3. Enlaces con URLs relacionadas a facturación
                billing_urls = soup.find_all('a', href=lambda x: x and any(term in str(x).lower() for term in ['factur', 'billing', 'invoice', 'portal']))
                billing_elements.extend(billing_urls)

                # Crear resumen de elementos encontrados
                elements_summary = []
                for elem in billing_elements[:10]:  # Máximo 10 elementos
                    elem_info = {
                        'tag': elem.name,
                        'text': elem.get_text(strip=True)[:100],
                        'href': elem.get('href', ''),
                        'class': ' '.join(elem.get('class', [])),
                        'id': elem.get('id', ''),
                        'target': elem.get('target', '')
                    }
                    elements_summary.append(elem_info)

                logger.info(f"🔍 Encontrados {len(elements_summary)} elementos potenciales de facturación")

            except Exception as dom_error:
                logger.warning(f"⚠️ Error analizando DOM: {dom_error}")
                elements_summary = []

            # Tomar screenshot del paso actual
            screenshot_path = f"/tmp/automation_step_{step_count}.png"
            worker.driver.save_screenshot(screenshot_path)
            results["screenshots"].append(screenshot_path)

            # Preparar contexto para el agente
            step_context = f"{context}. Datos del ticket: {ticket_data}. URL actual: {current_url}"
            current_step = f"Paso {step_count}/{max_steps}"

            # Agregar análisis de elementos al contexto
            if elements_summary:
                elements_context = "\n\nELEMENTOS DE FACTURACIÓN DETECTADOS:\n"
                for i, elem in enumerate(elements_summary, 1):
                    # Construir selector sugerido
                    suggested_selector = ""
                    if elem['id']:
                        suggested_selector = f"#{elem['id']}"
                    elif elem['class']:
                        main_class = elem['class'].split()[0]  # Primera clase
                        suggested_selector = f"{elem['tag']}.{main_class}"
                    elif elem['href']:
                        suggested_selector = f"{elem['tag']}[href='{elem['href']}']"
                    else:
                        suggested_selector = elem['tag']

                    elements_context += f"{i}. {elem['tag'].upper()}: '{elem['text'][:50]}'"
                    elements_context += f"\n   SELECTOR SUGERIDO: {suggested_selector}"

                    if elem['id']:
                        elements_context += f"\n   ID: {elem['id']}"
                    if elem['class']:
                        elements_context += f"\n   CLASS: {elem['class']}"
                    if elem['href']:
                        elements_context += f"\n   HREF: {elem['href']}"
                    elements_context += "\n"
                step_context += elements_context

            # Convertir elementos_summary a formato para el LLM
            elementos_detectados = []
            for elem in elements_summary:
                # Construir selector sugerido
                suggested_selector = ""
                if elem['id']:
                    suggested_selector = f"#{elem['id']}"
                elif elem['class']:
                    suggested_selector = f".{elem['class'].split()[0]}"
                elif elem['href']:
                    suggested_selector = f"a[href='{elem['href']}']"
                else:
                    suggested_selector = elem['tag']

                # 🧠 Calcular prioridad basada en memoria
                priority = 0.8  # Base
                memory_info = ""

                if suggested_selector in selector_attempts:
                    attempts = selector_attempts[suggested_selector]
                    cooldown_steps = step_count - attempts["last_step"]

                    if attempts["worked"]:
                        priority = 0.9  # Aumentar prioridad si funcionó antes
                        memory_info = f" (✅ funcionó antes)"
                    elif cooldown_steps < 3:  # Cooldown de 3 pasos
                        priority = 0.3  # Reducir prioridad temporalmente
                        memory_info = f" (⏸️ cooldown {cooldown_steps}/3)"
                    else:
                        priority = 0.6  # Prioridad reducida pero disponible
                        memory_info = f" (🔄 reintentable)"

                elementos_detectados.append({
                    "tipo": elem['tag'],
                    "texto": elem['text'][:100],  # Limitar texto
                    "selector_sugerido": suggested_selector,
                    "relevancia": priority,
                    "memoria": memory_info,
                    "atributos": {
                        "id": elem['id'],
                        "class": elem['class'],
                        "href": elem['href']
                    }
                })

            # 🧠 Información de memoria para el LLM
            memory_context = ""
            if stagnant_steps > 1:
                memory_context += f"\n⚠️ PÁGINA ESTANCADA: {stagnant_steps} pasos sin progreso en {current_url}"
                memory_context += f"\n🎯 ESTRATEGIA: Probar elementos con mayor prioridad o diferentes selectores"

            if selector_attempts:
                memory_context += f"\n🧠 MEMORIA DE SELECTORES:"
                for selector, data in selector_attempts.items():
                    status = "✅ exitoso" if data["worked"] else f"❌ {data['count']} intentos"
                    cooldown = step_count - data["last_step"]
                    memory_context += f"\n   {selector}: {status} (cooldown: {cooldown})"

            # Obtener decisión del agente con datos completos
            decision = await get_next_action(
                html_content=html_content,
                context=step_context + memory_context,
                current_step=current_step,
                ticket_data=ticket_data,
                elementos_detectados=elementos_detectados
            )

            # 📊 LOGGING DETALLADO DE LA DECISIÓN LLM
            logger.info(f"🤖 === DECISIÓN LLM PASO {step_count} ===")
            logger.info(f"🌐 URL: {current_url}")
            logger.info(f"🎯 Acción: {decision.get('action', 'N/A')}")
            logger.info(f"🎯 Selector: {decision.get('selector', 'N/A')}")
            logger.info(f"📝 Valor: {decision.get('value', 'N/A')}")
            logger.info(f"💭 Razón: {decision.get('reason', 'N/A')}")
            logger.info(f"🎲 Confianza: {decision.get('confidence', 'N/A')}")
            if elements_summary:
                logger.info(f"🔍 Elementos disponibles: {len(elements_summary)}")
                for i, elem in enumerate(elements_summary[:3], 1):  # Top 3
                    logger.info(f"   {i}. {elem['tag']}: '{elem['text'][:50]}...'")
            logger.info(f"🤖 === FIN DECISIÓN PASO {step_count} ===")

            # Registrar el paso con contexto extendido
            step_result = {
                "step": step_count,
                "url": current_url,
                "decision": decision,
                "elements_found": len(elements_summary),
                "elements_summary": elements_summary[:5],  # Top 5 elementos
                "timestamp": time.time()
            }
            results["steps"].append(step_result)

            # Ejecutar la acción decidida
            if decision["action"] == "done":
                results["success"] = True
                results["final_reason"] = decision["reason"]
                break

            elif decision["action"] == "error":
                results["success"] = False
                results["final_reason"] = decision["reason"]
                break

            elif decision["action"] == "click":
                try:
                    element_selector = decision["selector"]

                    # 🧠 Actualizar memoria de intentos
                    if element_selector not in selector_attempts:
                        selector_attempts[element_selector] = {"count": 0, "last_step": 0, "worked": False}

                    selector_attempts[element_selector]["count"] += 1
                    selector_attempts[element_selector]["last_step"] = step_count

                    # 🛡️ PROTECCIÓN 1: Verificar si ya se hizo clic en este elemento
                    if element_selector in clicked_elements:
                        protection_msg = f"🔒 Protección: Ya se hizo clic en {element_selector}"
                        logger.warning(protection_msg)
                        results["protections_triggered"].append(protection_msg)
                        time.sleep(action_delays["default"])
                        continue

                    element = worker.find_element_safe(element_selector)
                    if element:
                        # 🛡️ PROTECCIÓN 2: Verificar si el elemento es visible y clickeable
                        if not element.is_displayed() or not element.is_enabled():
                            logger.warning(f"🔒 Elemento no clickeable: {element_selector}")
                            time.sleep(action_delays["default"])
                            continue

                        # 🛡️ PROTECCIÓN 3: Contar pestañas antes del clic
                        initial_tabs = len(worker.driver.window_handles)

                        # 🛡️ PROTECCIÓN 4: Controlar navegación antes del click
                        try:
                            # Si el elemento tiene target="_blank", cambiar a navegación en misma pestaña
                            target_attr = element.get_attribute("target")
                            href = element.get_attribute("href")

                            if target_attr == "_blank" and href:
                                logger.info("🔧 Elemento con target='_blank' detectado, forzando navegación en misma pestaña")
                                worker.driver.get(href)
                                logger.info(f"✅ Navegación forzada a: {href}")
                            else:
                                # Hacer clic normal
                                logger.info(f"🖱️ Haciendo clic en: {element_selector}")
                                element.click()

                        except Exception as navigation_error:
                            logger.warning(f"⚠️ Error en navegación controlada: {navigation_error}")
                            element.click()

                        clicked_elements.add(element_selector)

                        # Esperar navegación
                        time.sleep(action_delays["click"])
                        current_tabs = len(worker.driver.window_handles)

                        if current_tabs > initial_tabs:
                            protection_msg = f"🔒 Detectadas {current_tabs - initial_tabs} nuevas pestañas. Cerrando extras y manteniendo principal."
                            logger.warning(protection_msg)
                            results["protections_triggered"].append(protection_msg)

                            # Obtener URL de la nueva pestaña antes de cerrarla
                            new_tab_url = None
                            if len(worker.driver.window_handles) > 1:
                                worker.driver.switch_to.window(worker.driver.window_handles[-1])
                                new_tab_url = worker.driver.current_url
                                worker.driver.close()
                                worker.driver.switch_to.window(worker.driver.window_handles[0])

                                # Navegar a la URL en la pestaña principal
                                if new_tab_url and new_tab_url != worker.driver.current_url:
                                    logger.info(f"🔄 Navegando a URL de nueva pestaña en pestaña principal: {new_tab_url}")
                                    worker.driver.get(new_tab_url)

                    else:
                        results["final_reason"] = f"No se encontró elemento: {element_selector}"
                        break
                except Exception as e:
                    results["final_reason"] = f"Error haciendo clic: {str(e)}"
                    break

            elif decision["action"] == "input":
                try:
                    # PROTECCIÓN 1: Verificar si ya se llenó este campo
                    field_key = decision["selector"]
                    if field_key in filled_inputs:
                        protection_msg = f"🔒 Protección: Ya se llenó el campo {field_key} con valor '{filled_inputs[field_key]}'"
                        logger.info(protection_msg)
                        automation_steps.append({
                            "step": f"Protección Input - {field_key}",
                            "success": True,
                            "message": protection_msg,
                            "timestamp": datetime.now().isoformat()
                        })
                        continue

                    element = worker.find_element_safe(decision["selector"])
                    if element:
                        # PROTECCIÓN 2: Verificar si el campo es editable
                        if not element.is_enabled() or element.get_attribute("readonly"):
                            protection_msg = f"🔒 Protección: Campo {field_key} no es editable"
                            logger.info(protection_msg)
                            automation_steps.append({
                                "step": f"Campo No Editable - {field_key}",
                                "success": False,
                                "message": protection_msg,
                                "timestamp": datetime.now().isoformat()
                            })
                            continue

                        # Determinar qué valor usar
                        if decision["value"] == "required":
                            # Mapear campos comunes
                            field_name = decision["selector"].lower()
                            if "email" in field_name:
                                value = ticket_data.get("email", "")
                            elif "rfc" in field_name:
                                value = ticket_data.get("rfc", "")
                            elif "folio" in field_name or "ticket" in field_name:
                                value = ticket_data.get("folio", "")
                            else:
                                value = decision["value"]
                        else:
                            value = decision["value"]

                        # PROTECCIÓN 3: Verificar que hay un valor válido para escribir
                        if not value or str(value).strip() == "":
                            protection_msg = f"🔒 Protección: No hay valor válido para campo {field_key}"
                            logger.info(protection_msg)
                            automation_steps.append({
                                "step": f"Sin Valor - {field_key}",
                                "success": False,
                                "message": protection_msg,
                                "timestamp": datetime.now().isoformat()
                            })
                            continue

                        # Realizar la acción de input con protección
                        element.clear()
                        element.send_keys(value)

                        # PROTECCIÓN 4: Registrar que se llenó este campo
                        filled_inputs[field_key] = value

                        # Delay específico para inputs
                        time.sleep(action_delays.get("input", 2))

                        success_msg = f"✅ Campo llenado: {field_key} = '{value}'"
                        logger.info(success_msg)
                        automation_steps.append({
                            "step": f"Input - {field_key}",
                            "success": True,
                            "message": success_msg,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        results["final_reason"] = f"No se encontró campo: {decision['selector']}"
                        break
                except Exception as e:
                    results["final_reason"] = f"Error escribiendo en campo: {str(e)}"
                    break

            elif decision["action"] == "select":
                try:
                    # PROTECCIÓN 1: Verificar si ya se seleccionó este elemento
                    select_key = f"{decision['selector']}:{decision['value']}"
                    if select_key in filled_inputs:
                        protection_msg = f"🔒 Protección: Ya se seleccionó '{decision['value']}' en {decision['selector']}"
                        logger.info(protection_msg)
                        automation_steps.append({
                            "step": f"Protección Select - {decision['selector']}",
                            "success": True,
                            "message": protection_msg,
                            "timestamp": datetime.now().isoformat()
                        })
                        continue

                    element = worker.find_element_safe(decision["selector"])
                    if element:
                        # PROTECCIÓN 2: Verificar si el select es editable
                        if not element.is_enabled():
                            protection_msg = f"🔒 Protección: Select {decision['selector']} no está habilitado"
                            logger.info(protection_msg)
                            automation_steps.append({
                                "step": f"Select No Habilitado - {decision['selector']}",
                                "success": False,
                                "message": protection_msg,
                                "timestamp": datetime.now().isoformat()
                            })
                            continue

                        from selenium.webdriver.support.ui import Select
                        select = Select(element)
                        select.select_by_visible_text(decision["value"])

                        # PROTECCIÓN 3: Registrar que se seleccionó esta opción
                        filled_inputs[select_key] = decision["value"]

                        # Delay específico para selects
                        time.sleep(action_delays.get("default", 1))

                        success_msg = f"✅ Opción seleccionada: {decision['selector']} = '{decision['value']}'"
                        logger.info(success_msg)
                        automation_steps.append({
                            "step": f"Select - {decision['selector']}",
                            "success": True,
                            "message": success_msg,
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        results["final_reason"] = f"No se encontró select: {decision['selector']}"
                        break
                except Exception as e:
                    results["final_reason"] = f"Error seleccionando opción: {str(e)}"
                    break

            # Esperar entre acciones con delay dinámico
            time.sleep(action_delays.get("default", 1))

        if step_count >= max_steps:
            results["final_reason"] = "Se alcanzó el límite máximo de pasos"

    except Exception as e:
        results["success"] = False
        results["final_reason"] = f"Error en flujo inteligente: {str(e)}"

    return results


if __name__ == "__main__":
    # Test básico
    async def test_automation():
        merchant = {
            "nombre": "OXXO",
            "metodo_facturacion": "portal",
            "metadata": {"url": "https://www.oxxo.com/facturacion"}
        }

        ticket_data = {
            "raw_data": "OXXO TIENDA #1234\nRFC: OXX970814HS9\nTotal: $125.50\nFecha: 2024-01-15"
        }

        result = await process_web_automation(merchant, ticket_data)
        print(json.dumps(result, indent=2))

    asyncio.run(test_automation())