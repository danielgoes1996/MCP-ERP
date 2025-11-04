"""
Executor Determinista con Playwright - Motor de Automatización
Ejecuta planes RPA de forma segura, robusta y con recovery automático.
Incluye capturas de pantalla, logs detallados y manejo de errores avanzado.
"""

import asyncio
import json
import logging
import os
import time
import traceback
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable
from pathlib import Path
import uuid

from .ai_rpa_planner import RPAPlan, RPAAction, ActionType

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Estados de ejecución"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionStep:
    """Resultado de ejecución de un paso"""
    step_number: int
    action: RPAAction
    status: ExecutionStatus
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    extracted_data: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionResult:
    """Resultado completo de ejecución"""
    execution_id: str
    plan_id: str
    status: ExecutionStatus
    start_time: float
    steps: List[ExecutionStep]
    extracted_data: Dict[str, Any]
    screenshots: List[str]
    downloads: List[str]
    logs: List[str]
    errors: List[str]
    browser_info: Dict[str, Any]
    end_time: Optional[float] = None
    total_duration_ms: Optional[int] = None
    success_rate: float = 0.0


class PlaywrightExecutor:
    """
    Executor que ejecuta planes RPA usando Playwright de forma determinista.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Configuración de directorios
        self.screenshots_dir = Path("automation_screenshots")
        self.downloads_dir = Path("automation_downloads")
        self.logs_dir = Path("automation_logs")

        # Crear directorios si no existen
        for directory in [self.screenshots_dir, self.downloads_dir, self.logs_dir]:
            directory.mkdir(exist_ok=True)

        # Configuraciones por defecto
        self.default_timeout = 30000  # 30 segundos
        self.default_navigation_timeout = 60000  # 1 minuto
        self.screenshot_on_error = True
        self.save_har = True  # Guardar tráfico de red

        # Variables de estado
        self._current_execution = None
        self._browser = None
        self._page = None

    async def execute_plan(
        self,
        plan: RPAPlan,
        input_data: Dict[str, Any],
        execution_config: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Ejecutar un plan RPA completo.

        Args:
            plan: Plan de automatización a ejecutar
            input_data: Datos de entrada (RFC, folio, etc.)
            execution_config: Configuración específica de ejecución

        Returns:
            Resultado completo de la ejecución
        """

        execution_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(f"Iniciando ejecución {execution_id} del plan {plan.plan_id}")

        # Crear resultado de ejecución
        result = ExecutionResult(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            status=ExecutionStatus.RUNNING,
            start_time=start_time,
            steps=[],
            extracted_data={},
            screenshots=[],
            downloads=[],
            logs=[],
            errors=[],
            browser_info={}
        )

        self._current_execution = result

        try:
            # Configurar y lanzar browser
            await self._setup_browser(plan.browser_config, execution_config)

            # Configurar página
            await self._setup_page(plan, input_data)

            # Ejecutar acciones del plan
            for i, action in enumerate(plan.actions):
                step_result = await self._execute_action(
                    action=action,
                    step_number=i + 1,
                    input_data=input_data
                )

                result.steps.append(step_result)

                # Si el paso falló y no se puede continuar
                if step_result.status == ExecutionStatus.FAILED:
                    if not await self._can_continue_after_failure(action, step_result):
                        logger.error(f"Ejecución detenida en paso {i + 1}: {step_result.error_message}")
                        result.status = ExecutionStatus.FAILED
                        break

            # Verificar validaciones de éxito
            if result.status == ExecutionStatus.RUNNING:
                success = await self._validate_success(plan.success_validations)
                result.status = ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED

            # Estadísticas finales
            result.end_time = time.time()
            result.total_duration_ms = int((result.end_time - result.start_time) * 1000)
            result.success_rate = self._calculate_success_rate(result.steps)

            logger.info(f"Ejecución {execution_id} completada: {result.status.value} ({result.total_duration_ms}ms)")

        except asyncio.TimeoutError:
            logger.error(f"Timeout en ejecución {execution_id}")
            result.status = ExecutionStatus.TIMEOUT
            result.errors.append("Timeout general de ejecución")

        except Exception as e:
            logger.error(f"Error crítico en ejecución {execution_id}: {e}")
            result.status = ExecutionStatus.FAILED
            result.errors.append(f"Error crítico: {str(e)}")

            # Screenshot de error
            if self.screenshot_on_error and self._page:
                try:
                    error_screenshot = await self._take_screenshot("critical_error")
                    result.screenshots.append(error_screenshot)
                except:
                    pass

        finally:
            # Limpiar recursos
            await self._cleanup_browser()

        return result

    async def _setup_browser(
        self,
        browser_config: Dict[str, Any],
        execution_config: Optional[Dict[str, Any]]
    ):
        """Configurar y lanzar el browser"""

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().__aenter__()

            # Configuración del browser
            config = {
                "headless": browser_config.get("headless", False),
                "slow_mo": execution_config.get("slow_mo", 100) if execution_config else 100,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor"
                ]
            }

            # Lanzar browser
            self._browser = await self._playwright.chromium.launch(**config)

            # Crear contexto con configuración específica
            context_config = {
                "viewport": browser_config.get("viewport", {"width": 1920, "height": 1080}),
                "user_agent": browser_config.get("user_agent",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
                "locale": "es-MX",
                "timezone_id": "America/Mexico_City"
            }

            # Configurar descarga de archivos
            if self.downloads_dir:
                context_config["accept_downloads"] = True

            # Configurar HAR si está habilitado
            if self.save_har:
                har_path = self.logs_dir / f"execution_{self._current_execution.execution_id}.har"
                context_config["record_har_path"] = str(har_path)

            self._context = await self._browser.new_context(**context_config)

            # Crear página
            self._page = await self._context.new_page()

            # Configurar timeouts
            self._page.set_default_timeout(self.default_timeout)
            self._page.set_default_navigation_timeout(self.default_navigation_timeout)

            logger.info("Browser configurado exitosamente")

        except Exception as e:
            logger.error(f"Error configurando browser: {e}")
            raise

    async def _setup_page(self, plan: RPAPlan, input_data: Dict[str, Any]):
        """Configurar la página antes de la ejecución"""

        # Configurar interceptores de requests si es necesario
        await self._page.route("**/*", self._handle_route)

        # Configurar handlers de eventos
        self._page.on("console", self._handle_console_message)
        self._page.on("pageerror", self._handle_page_error)
        self._page.on("response", self._handle_response)

        # Inyectar scripts de utilidad
        await self._page.add_init_script("""
            // Ocultar indicadores de automatización
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Funciones de utilidad
            window.automation_utils = {
                highlightElement: (selector) => {
                    const el = document.querySelector(selector);
                    if (el) {
                        el.style.border = '3px solid red';
                        el.style.backgroundColor = 'yellow';
                        setTimeout(() => {
                            el.style.border = '';
                            el.style.backgroundColor = '';
                        }, 2000);
                    }
                },

                getElementText: (selector) => {
                    const el = document.querySelector(selector);
                    return el ? el.textContent.trim() : null;
                },

                isElementVisible: (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }
            };
        """)

    async def _execute_action(
        self,
        action: RPAAction,
        step_number: int,
        input_data: Dict[str, Any]
    ) -> ExecutionStep:
        """Ejecutar una acción individual"""

        start_time = time.time()

        step_result = ExecutionStep(
            step_number=step_number,
            action=action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time
        )

        logger.info(f"Ejecutando paso {step_number}: {action.action_type.value} - {action.description}")

        try:
            # Procesar valor dinámico si existe
            processed_value = self._process_dynamic_value(action.value, input_data) if action.value else None

            # Ejecutar acción según tipo
            if action.action_type == ActionType.NAVIGATE:
                await self._action_navigate(processed_value, action)

            elif action.action_type == ActionType.WAIT_FOR_ELEMENT:
                await self._action_wait_for_element(action.selector, action)

            elif action.action_type == ActionType.CLICK:
                await self._action_click(action.selector, action)

            elif action.action_type == ActionType.TYPE:
                await self._action_type(action.selector, processed_value, action)

            elif action.action_type == ActionType.SELECT:
                await self._action_select(action.selector, processed_value, action)

            elif action.action_type == ActionType.UPLOAD_FILE:
                await self._action_upload_file(action.selector, processed_value, action)

            elif action.action_type == ActionType.WAIT_FOR_NAVIGATION:
                await self._action_wait_for_navigation(action)

            elif action.action_type == ActionType.WAIT_TIME:
                await self._action_wait_time(int(processed_value), action)

            elif action.action_type == ActionType.SCROLL:
                await self._action_scroll(action.selector, action)

            elif action.action_type == ActionType.TAKE_SCREENSHOT:
                screenshot_path = await self._action_take_screenshot(action.description)
                step_result.screenshot_path = screenshot_path

            elif action.action_type == ActionType.EXTRACT_TEXT:
                extracted_text = await self._action_extract_text(action.selector, action)
                step_result.extracted_data = {"text": extracted_text}

            elif action.action_type == ActionType.VALIDATE:
                validation_result = await self._action_validate(action)
                step_result.extracted_data = {"validation": validation_result}

            elif action.action_type == ActionType.CONDITIONAL:
                await self._action_conditional(action, input_data)

            else:
                raise ValueError(f"Tipo de acción no soportado: {action.action_type}")

            step_result.status = ExecutionStatus.COMPLETED

        except asyncio.TimeoutError:
            step_result.status = ExecutionStatus.TIMEOUT
            step_result.error_message = f"Timeout después de {action.timeout}ms"
            logger.error(f"Timeout en paso {step_number}: {action.description}")

        except Exception as e:
            step_result.status = ExecutionStatus.FAILED
            step_result.error_message = str(e)
            logger.error(f"Error en paso {step_number}: {e}")

            # Intentar retry si está configurado
            if step_result.retry_count < action.retry_count:
                logger.info(f"Reintentando paso {step_number} ({step_result.retry_count + 1}/{action.retry_count})")
                step_result.retry_count += 1
                await asyncio.sleep(2)  # Esperar antes de reintentar
                return await self._execute_action(action, step_number, input_data)

            # Screenshot en caso de error
            if self.screenshot_on_error:
                try:
                    error_screenshot = await self._take_screenshot(f"error_step_{step_number}")
                    step_result.screenshot_path = error_screenshot
                except:
                    pass

        finally:
            step_result.end_time = time.time()
            step_result.duration_ms = int((step_result.end_time - step_result.start_time) * 1000)

        return step_result

    # ===============================================================
    # IMPLEMENTACIÓN DE ACCIONES ESPECÍFICAS
    # ===============================================================

    async def _action_navigate(self, url: str, action: RPAAction):
        """Navegar a una URL"""
        logger.info(f"Navegando a: {url}")
        await self._page.goto(url, wait_until="networkidle", timeout=action.timeout)

    async def _action_wait_for_element(self, selector: str, action: RPAAction):
        """Esperar a que un elemento aparezca"""
        logger.info(f"Esperando elemento: {selector}")
        await self._page.wait_for_selector(selector, timeout=action.timeout)

    async def _action_click(self, selector: str, action: RPAAction):
        """Hacer click en un elemento"""
        logger.info(f"Haciendo click en: {selector}")

        # Esperar a que el elemento sea visible y clickeable
        element = await self._page.wait_for_selector(selector, state="visible", timeout=action.timeout)

        # Scroll al elemento si es necesario
        await element.scroll_into_view_if_needed()

        # Resaltar elemento antes de click (para debugging)
        await self._page.evaluate(f"window.automation_utils.highlightElement('{selector}')")

        # Hacer click
        await element.click()

    async def _action_type(self, selector: str, text: str, action: RPAAction):
        """Escribir texto en un elemento"""
        logger.info(f"Escribiendo en {selector}: {text}")

        element = await self._page.wait_for_selector(selector, timeout=action.timeout)

        # Limpiar campo primero
        await element.clear()

        # Escribir texto con delay natural
        await element.type(text, delay=100)

    async def _action_select(self, selector: str, value: str, action: RPAAction):
        """Seleccionar opción en un select"""
        logger.info(f"Seleccionando en {selector}: {value}")

        await self._page.wait_for_selector(selector, timeout=action.timeout)
        await self._page.select_option(selector, value)

    async def _action_upload_file(self, selector: str, file_path: str, action: RPAAction):
        """Subir un archivo"""
        logger.info(f"Subiendo archivo {file_path} en: {selector}")

        file_input = await self._page.wait_for_selector(selector, timeout=action.timeout)
        await file_input.set_input_files(file_path)

    async def _action_wait_for_navigation(self, action: RPAAction):
        """Esperar navegación"""
        logger.info("Esperando navegación")
        await self._page.wait_for_load_state("networkidle", timeout=action.timeout)

    async def _action_wait_time(self, milliseconds: int, action: RPAAction):
        """Esperar tiempo específico"""
        logger.info(f"Esperando {milliseconds}ms")
        await asyncio.sleep(milliseconds / 1000.0)

    async def _action_scroll(self, selector: Optional[str], action: RPAAction):
        """Hacer scroll"""
        if selector:
            logger.info(f"Haciendo scroll al elemento: {selector}")
            element = await self._page.wait_for_selector(selector, timeout=action.timeout)
            await element.scroll_into_view_if_needed()
        else:
            logger.info("Haciendo scroll hacia abajo")
            await self._page.evaluate("window.scrollBy(0, 500)")

    async def _action_take_screenshot(self, description: str) -> str:
        """Tomar captura de pantalla"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}_{description.replace(' ', '_')}.png"
        screenshot_path = self.screenshots_dir / filename

        await self._page.screenshot(path=str(screenshot_path), full_page=True)

        logger.info(f"Screenshot guardado: {screenshot_path}")
        return str(screenshot_path)

    async def _action_extract_text(self, selector: str, action: RPAAction) -> str:
        """Extraer texto de un elemento"""
        logger.info(f"Extrayendo texto de: {selector}")

        element = await self._page.wait_for_selector(selector, timeout=action.timeout)
        text = await element.inner_text()

        return text.strip()

    async def _action_validate(self, action: RPAAction) -> Dict[str, Any]:
        """Ejecutar validación"""
        validation_type = action.options.get("validation_type", "element_present")

        if validation_type == "element_present":
            selector = action.options.get("selector")
            try:
                await self._page.wait_for_selector(selector, timeout=5000)
                return {"valid": True, "message": f"Elemento {selector} presente"}
            except:
                return {"valid": False, "message": f"Elemento {selector} no encontrado"}

        elif validation_type == "url_contains":
            expected = action.options.get("expected")
            current_url = self._page.url
            valid = expected in current_url
            return {
                "valid": valid,
                "message": f"URL {'contiene' if valid else 'no contiene'} '{expected}'",
                "current_url": current_url
            }

        elif validation_type == "text_present":
            text = action.options.get("text")
            try:
                await self._page.wait_for_function(
                    f"document.body.innerText.includes('{text}')",
                    timeout=5000
                )
                return {"valid": True, "message": f"Texto '{text}' encontrado"}
            except:
                return {"valid": False, "message": f"Texto '{text}' no encontrado"}

        return {"valid": False, "message": "Tipo de validación no soportado"}

    async def _action_conditional(self, action: RPAAction, input_data: Dict[str, Any]):
        """Ejecutar acción condicional"""
        condition = action.options.get("condition")
        # Implementar lógica condicional básica
        # Por ahora, solo ejecutar si la condición es True
        if condition:
            logger.info(f"Ejecutando acción condicional: {condition}")

    # ===============================================================
    # FUNCIONES DE UTILIDAD
    # ===============================================================

    def _process_dynamic_value(self, value: str, input_data: Dict[str, Any]) -> str:
        """Procesar valores dinámicos usando plantillas"""

        if not value or not isinstance(value, str):
            return value

        # Reemplazar variables usando template simple
        # ${variable} -> valor de input_data
        import re

        def replace_var(match):
            var_name = match.group(1)
            return str(input_data.get(var_name, f"${{{var_name}}}"))

        processed = re.sub(r'\$\{([^}]+)\}', replace_var, value)
        return processed

    async def _validate_success(self, validations: List[Dict[str, Any]]) -> bool:
        """Validar condiciones de éxito"""

        if not validations:
            return True

        for validation in validations:
            validation_type = validation.get("type")

            try:
                if validation_type == "element_present":
                    selector = validation.get("selector")
                    await self._page.wait_for_selector(selector, timeout=5000)

                elif validation_type == "url_contains":
                    expected = validation.get("value")
                    if expected not in self._page.url:
                        return False

                elif validation_type == "text_present":
                    text = validation.get("value")
                    content = await self._page.content()
                    if text not in content:
                        return False

            except Exception as e:
                logger.warning(f"Validación falló: {validation} - {e}")
                return False

        return True

    def _calculate_success_rate(self, steps: List[ExecutionStep]) -> float:
        """Calcular tasa de éxito de los pasos"""

        if not steps:
            return 0.0

        successful_steps = sum(1 for step in steps if step.status == ExecutionStatus.COMPLETED)
        return (successful_steps / len(steps)) * 100.0

    async def _can_continue_after_failure(self, action: RPAAction, step_result: ExecutionStep) -> bool:
        """Determinar si se puede continuar después de un fallo"""

        # Acciones críticas que detienen la ejecución
        critical_actions = [ActionType.NAVIGATE, ActionType.WAIT_FOR_ELEMENT]

        if action.action_type in critical_actions:
            return False

        # Si el error es de timeout, puede ser recuperable
        if step_result.status == ExecutionStatus.TIMEOUT:
            return True

        return False

    async def _take_screenshot(self, suffix: str = "general") -> str:
        """Tomar screenshot con timestamp"""

        if not self._page:
            return ""

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}_{suffix}.png"
            screenshot_path = self.screenshots_dir / filename

            await self._page.screenshot(path=str(screenshot_path), full_page=True)
            return str(screenshot_path)

        except Exception as e:
            logger.error(f"Error tomando screenshot: {e}")
            return ""

    # ===============================================================
    # HANDLERS DE EVENTOS
    # ===============================================================

    async def _handle_route(self, route):
        """Interceptar requests si es necesario"""
        # Por ahora, permitir todos los requests
        await route.continue_()

    def _handle_console_message(self, msg):
        """Manejar mensajes de consola del browser"""
        if self._current_execution:
            self._current_execution.logs.append(f"Console {msg.type}: {msg.text}")

    def _handle_page_error(self, error):
        """Manejar errores de página"""
        if self._current_execution:
            self._current_execution.errors.append(f"Page error: {str(error)}")

    def _handle_response(self, response):
        """Manejar respuestas HTTP"""
        # Log de respuestas importantes
        if response.status >= 400:
            logger.warning(f"HTTP {response.status}: {response.url}")

    async def _cleanup_browser(self):
        """Limpiar recursos del browser"""

        try:
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if hasattr(self, '_playwright'):
                await self._playwright.__aexit__(None, None, None)

            logger.info("Recursos del browser limpiados")

        except Exception as e:
            logger.error(f"Error limpiando browser: {e}")

    # ===============================================================
    # MÉTODOS DE UTILIDAD PÚBLICOS
    # ===============================================================

    async def validate_plan_feasibility(self, plan: RPAPlan) -> Dict[str, Any]:
        """Validar si un plan es ejecutable"""

        validation_result = {
            "feasible": True,
            "warnings": [],
            "errors": []
        }

        # Validar URL
        if not plan.portal_url:
            validation_result["errors"].append("URL del portal no especificada")
            validation_result["feasible"] = False

        # Validar acciones
        for i, action in enumerate(plan.actions):
            if action.action_type in [ActionType.CLICK, ActionType.TYPE, ActionType.SELECT]:
                if not action.selector:
                    validation_result["warnings"].append(
                        f"Acción {i+1} ({action.action_type.value}) sin selector"
                    )

        return validation_result

    async def get_page_info(self) -> Dict[str, Any]:
        """Obtener información de la página actual"""

        if not self._page:
            return {}

        try:
            return {
                "url": self._page.url,
                "title": await self._page.title(),
                "viewport": self._page.viewport_size,
                "user_agent": await self._page.evaluate("navigator.userAgent")
            }
        except:
            return {}


# Función de conveniencia para ejecutar un plan
async def execute_rpa_plan(
    plan: RPAPlan,
    input_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> ExecutionResult:
    """
    Ejecutar un plan RPA con configuración específica.

    Args:
        plan: Plan de automatización
        input_data: Datos de entrada para el plan
        config: Configuración de ejecución

    Returns:
        Resultado completo de la ejecución
    """

    executor = PlaywrightExecutor(config)
    return await executor.execute_plan(plan, input_data, config)


if __name__ == "__main__":
    # Test del executor
    import asyncio
    from .ai_rpa_planner import RPAPlan, RPAAction

    async def test_playwright_executor():
        """Test del executor con plan simple"""

        print("=== TEST DEL EXECUTOR PLAYWRIGHT ===")

        # Crear plan de prueba
        test_actions = [
            RPAAction(
                action_type=ActionType.NAVIGATE,
                value="https://httpbin.org/forms/post",
                description="Navegar a página de prueba"
            ),
            RPAAction(
                action_type=ActionType.TAKE_SCREENSHOT,
                description="Captura inicial"
            ),
            RPAAction(
                action_type=ActionType.WAIT_FOR_ELEMENT,
                selector="input[name='custname']",
                description="Esperar campo de nombre"
            ),
            RPAAction(
                action_type=ActionType.TYPE,
                selector="input[name='custname']",
                value="${company_name}",
                description="Ingresar nombre de empresa"
            ),
            RPAAction(
                action_type=ActionType.TAKE_SCREENSHOT,
                description="Captura final"
            )
        ]

        test_plan = RPAPlan(
            plan_id="test_plan_001",
            merchant_name="Test Merchant",
            portal_url="https://httpbin.org/forms/post",
            browser_config={"headless": True},
            actions=test_actions,
            input_schema={"company_name": "Nombre de la empresa"},
            success_validations=[],
            created_at=datetime.now().isoformat(),
            confidence_score=0.9,
            estimated_duration_seconds=30
        )

        # Datos de entrada
        input_data = {
            "company_name": "Mi Empresa SA de CV"
        }

        try:
            result = await execute_rpa_plan(test_plan, input_data)

            print(f"✅ Ejecución completada:")
            print(f"Status: {result.status.value}")
            print(f"Duración: {result.total_duration_ms}ms")
            print(f"Pasos ejecutados: {len(result.steps)}")
            print(f"Tasa de éxito: {result.success_rate:.1f}%")
            print(f"Screenshots: {len(result.screenshots)}")

            if result.errors:
                print(f"Errores: {result.errors}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Ejecutar test
    asyncio.run(test_playwright_executor())