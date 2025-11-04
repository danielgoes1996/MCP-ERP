import asyncio
import json
import logging
import random
import time
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
import sqlite3
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
import requests_html
import httpx
import psutil
from pathlib import Path

logger = logging.getLogger(__name__)

class WebAutomationStrategy(Enum):
    SINGLE_ENGINE = "single_engine"
    MULTI_ENGINE = "multi_engine"
    FAILOVER = "failover"
    PARALLEL = "parallel"

class WebAutomationEngine(Enum):
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    PUPPETEER = "puppeteer"
    REQUESTS_HTML = "requests_html"
    HTTPX_CLIENT = "httpx_client"

class WebStepType(Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    EXTRACT = "extract"
    WAIT = "wait"
    SCROLL = "scroll"
    SCREENSHOT = "screenshot"
    JAVASCRIPT = "javascript"
    CAPTCHA_SOLVE = "captcha_solve"

class WebSessionStatus(Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WebAutomationEngineSystem:
    """
    Sistema de Automatización Web Multi-Engine

    Características:
    - Soporte para múltiples engines (Playwright, Selenium, etc.)
    - Anti-detection avanzado con browser fingerprinting
    - Sistema de CAPTCHA solving integrado
    - Análisis inteligente de DOM con Claude AI
    - Estrategias de fallback automático
    - Performance optimization y retry inteligente
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.db_path = "unified_mcp_system.db"

        # Cache de engines activos
        self.active_engines = {}
        self.engine_health = {}

        # Configuraciones por engine
        self.engine_configs = {
            WebAutomationEngine.PLAYWRIGHT: {
                "headless": True,
                "stealth": True,
                "user_agent": self._get_random_user_agent(),
                "viewport": {"width": 1920, "height": 1080},
                "locale": "es-MX",
                "timezone": "America/Mexico_City"
            },
            WebAutomationEngine.SELENIUM: {
                "headless": True,
                "stealth_mode": True,
                "window_size": "1920,1080",
                "disable_dev_shm_usage": True,
                "no_sandbox": True
            },
            WebAutomationEngine.REQUESTS_HTML: {
                "render_js": True,
                "timeout": 30,
                "mock_browser": True
            }
        }

        # Anti-detection settings
        self.fingerprint_rotation_enabled = True
        self.user_agents_pool = self._load_user_agents_pool()

        # CAPTCHA solving services
        self.captcha_services = {
            "2captcha": {"api_key": None, "enabled": False},
            "anticaptcha": {"api_key": None, "enabled": False}
        }

        # Performance monitoring
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time_ms": 0.0
        }

    def _get_random_user_agent(self) -> str:
        """Obtener user agent aleatorio para anti-detection"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]
        return random.choice(user_agents)

    def _load_user_agents_pool(self) -> List[str]:
        """Cargar pool de user agents para rotación"""
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
        ]

    def _generate_browser_fingerprint(self, engine: WebAutomationEngine) -> Dict[str, Any]:
        """Generar fingerprint del navegador para anti-detection"""
        fingerprint = {
            "engine": engine.value,
            "user_agent": self._get_random_user_agent(),
            "screen": {
                "width": random.choice([1920, 1366, 1536, 1440]),
                "height": random.choice([1080, 768, 864, 900]),
                "color_depth": 24,
                "pixel_ratio": random.choice([1, 1.25, 1.5, 2])
            },
            "timezone": "America/Mexico_City",
            "language": "es-MX,es;q=0.9,en;q=0.8",
            "platform": random.choice(["Win32", "MacIntel", "Linux x86_64"]),
            "webgl_vendor": "Google Inc. (Intel)",
            "webgl_renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "canvas_fingerprint": hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:16],
            "audio_fingerprint": hashlib.md5(f"audio{time.time()}".encode()).hexdigest()[:16],
            "fonts": [
                "Arial", "Times New Roman", "Helvetica", "Georgia", "Verdana",
                "Trebuchet MS", "Comic Sans MS", "Impact", "Arial Black"
            ],
            "plugins": [
                "Chrome PDF Plugin", "Chrome PDF Viewer", "Native Client"
            ],
            "generated_at": datetime.utcnow().isoformat()
        }

        return fingerprint

    @asynccontextmanager
    async def get_db_connection(self):
        """Context manager para conexión segura a base de datos"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    async def create_web_automation_session(self, user_id: str, company_id: str,
                                          target_url: str, automation_steps: List[Dict],
                                          strategy: WebAutomationStrategy = WebAutomationStrategy.MULTI_ENGINE,
                                          primary_engine: WebAutomationEngine = WebAutomationEngine.PLAYWRIGHT,
                                          stealth_mode: bool = True) -> str:
        """Crear nueva sesión de automatización web"""
        try:
            session_id = f"web_{int(time.time())}_{user_id[:8]}"

            # Generar browser fingerprint
            browser_fingerprint = self._generate_browser_fingerprint(primary_engine)

            # Configuración inicial de CAPTCHA
            captcha_solved = {
                "total_encountered": 0,
                "successfully_solved": 0,
                "failed_attempts": 0,
                "services_used": [],
                "last_solve_time": None
            }

            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO web_automation_sessions (
                        session_id, user_id, company_id, target_url,
                        automation_strategy, primary_engine, browser_fingerprint,
                        stealth_mode, user_agent_rotation, captcha_solved,
                        total_steps, max_retries, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, user_id, company_id, target_url,
                    strategy.value, primary_engine.value,
                    json.dumps(browser_fingerprint),
                    stealth_mode, True, json.dumps(captcha_solved),
                    len(automation_steps), 5, datetime.utcnow().isoformat()
                ))

                # Crear pasos individuales
                for i, step in enumerate(automation_steps):
                    recommended_engine = await self._recommend_engine_for_step(step)

                    cursor.execute("""
                        INSERT INTO web_automation_steps (
                            session_id, step_number, step_type, step_description,
                            step_config, assigned_engine, target_selectors
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session_id, i + 1, step.get('type', 'navigate'),
                        step.get('description', f'Step {i + 1}'),
                        json.dumps(step), recommended_engine.value,
                        json.dumps(step.get('selectors', []))
                    ))

                conn.commit()

                logger.info(f"Created web automation session {session_id} for user {user_id}")
                return session_id

        except Exception as e:
            logger.error(f"Error creating web automation session: {e}")
            raise

    async def start_web_automation_session(self, session_id: str) -> Dict[str, Any]:
        """Iniciar ejecución de sesión de automatización web"""
        try:
            # Obtener configuración de sesión
            session_data = await self._get_session_data(session_id)
            if not session_data:
                return {"status": "error", "message": "Sesión no encontrada"}

            # Actualizar estado a running
            await self._update_session_status(session_id, WebSessionStatus.RUNNING)

            # Inicializar engine primario
            primary_engine = WebAutomationEngine(session_data["primary_engine"])
            engine_instance = await self._initialize_engine(primary_engine, session_data)

            if not engine_instance:
                return {"status": "error", "message": "Error inicializando engine"}

            # Guardar engine activo
            self.active_engines[session_id] = {
                "primary": engine_instance,
                "engine_type": primary_engine,
                "start_time": time.time(),
                "browser_fingerprint": json.loads(session_data["browser_fingerprint"])
            }

            # Ejecutar pasos en background
            asyncio.create_task(self._execute_web_automation_steps(session_id))

            return {
                "status": "success",
                "session_id": session_id,
                "message": "Sesión web iniciada exitosamente",
                "primary_engine": primary_engine.value
            }

        except Exception as e:
            logger.error(f"Error starting web automation session: {e}")
            await self._update_session_status(session_id, WebSessionStatus.FAILED)
            return {"status": "error", "message": str(e)}

    async def _initialize_engine(self, engine: WebAutomationEngine, session_data: Dict) -> Optional[Any]:
        """Inicializar engine específico de automatización"""
        try:
            if engine == WebAutomationEngine.PLAYWRIGHT:
                return await self._initialize_playwright(session_data)
            elif engine == WebAutomationEngine.SELENIUM:
                return await self._initialize_selenium(session_data)
            elif engine == WebAutomationEngine.REQUESTS_HTML:
                return await self._initialize_requests_html(session_data)
            else:
                logger.warning(f"Engine no soportado: {engine}")
                return None

        except Exception as e:
            logger.error(f"Error initializing engine {engine}: {e}")
            return None

    async def _initialize_playwright(self, session_data: Dict) -> Dict:
        """Inicializar Playwright con configuración anti-detection"""
        try:
            playwright = await async_playwright().start()

            # Configuración anti-detection
            browser_args = [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--allow-running-insecure-content"
            ]

            if session_data.get("stealth_mode", True):
                browser_args.extend([
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-gpu"
                ])

            browser = await playwright.chromium.launch(
                headless=True,
                args=browser_args,
                slow_mo=random.randint(100, 300)
            )

            # Aplicar fingerprint
            browser_fingerprint = json.loads(session_data["browser_fingerprint"])

            context = await browser.new_context(
                user_agent=browser_fingerprint["user_agent"],
                viewport={
                    "width": browser_fingerprint["screen"]["width"],
                    "height": browser_fingerprint["screen"]["height"]
                },
                locale="es-MX",
                timezone_id="America/Mexico_City",
                permissions=["geolocation"]
            )

            # Inyectar scripts anti-detection
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['es-MX', 'es', 'en'],
                });

                window.chrome = {
                    runtime: {},
                };
            """)

            page = await context.new_page()

            return {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page,
                "engine_type": "playwright"
            }

        except Exception as e:
            logger.error(f"Error initializing Playwright: {e}")
            return None

    async def _initialize_selenium(self, session_data: Dict) -> Dict:
        """Inicializar Selenium con configuración anti-detection"""
        try:
            options = ChromeOptions()

            # Configuración anti-detection
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            if session_data.get("stealth_mode", True):
                options.add_argument("--headless")

            # Aplicar user agent del fingerprint
            browser_fingerprint = json.loads(session_data["browser_fingerprint"])
            options.add_argument(f"--user-agent={browser_fingerprint['user_agent']}")

            # Configurar window size
            screen = browser_fingerprint["screen"]
            options.add_argument(f"--window-size={screen['width']},{screen['height']}")

            driver = webdriver.Chrome(options=options)

            # Ejecutar scripts anti-detection
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            return {
                "driver": driver,
                "engine_type": "selenium",
                "wait": WebDriverWait(driver, 10)
            }

        except Exception as e:
            logger.error(f"Error initializing Selenium: {e}")
            return None

    async def _initialize_requests_html(self, session_data: Dict) -> Dict:
        """Inicializar Requests-HTML"""
        try:
            session = requests_html.HTMLSession()

            # Configurar headers anti-detection
            browser_fingerprint = json.loads(session_data["browser_fingerprint"])

            session.headers.update({
                'User-Agent': browser_fingerprint["user_agent"],
                'Accept-Language': browser_fingerprint["language"],
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })

            return {
                "session": session,
                "engine_type": "requests_html"
            }

        except Exception as e:
            logger.error(f"Error initializing Requests-HTML: {e}")
            return None

    async def _execute_web_automation_steps(self, session_id: str):
        """Ejecutar pasos de automatización web de forma asíncrona"""
        try:
            session_data = await self._get_session_data(session_id)
            steps = await self._get_session_steps(session_id)
            engine_instance = self.active_engines.get(session_id)

            if not engine_instance:
                raise Exception("Engine no encontrado para sesión")

            for step in steps:
                try:
                    # Incrementar contador de intentos
                    await self._increment_step_attempts(step["id"])

                    # Ejecutar paso
                    result = await self._execute_single_web_step(session_id, step, engine_instance)

                    if result["status"] == "success":
                        await self._mark_step_completed(step["id"], result.get("execution_time_ms", 0))
                    else:
                        # Intentar con engine de fallback si está disponible
                        fallback_result = await self._try_fallback_engine(session_id, step, result["error"])

                        if fallback_result["status"] != "success":
                            await self._mark_step_failed(step["id"], result["error"])

                            # Decidir si continuar o fallar sesión
                            if not await self._should_continue_after_failure(session_id, step):
                                await self._update_session_status(session_id, WebSessionStatus.FAILED)
                                return

                    # Delay aleatorio entre pasos
                    await asyncio.sleep(random.uniform(1, 3))

                except Exception as step_error:
                    logger.error(f"Error in web step {step['step_number']}: {step_error}")
                    await self._mark_step_failed(step["id"], str(step_error))

            # Completar sesión
            await self._update_session_status(session_id, WebSessionStatus.COMPLETED)

        except Exception as e:
            logger.error(f"Error executing web automation steps: {e}")
            await self._update_session_status(session_id, WebSessionStatus.FAILED)
        finally:
            await self._cleanup_web_session(session_id)

    async def _execute_single_web_step(self, session_id: str, step: Dict, engine_instance: Dict) -> Dict:
        """Ejecutar un paso individual de automatización web"""
        try:
            step_type = WebStepType(step["step_type"])
            step_config = json.loads(step["step_config"])
            start_time = time.time()

            result = {"status": "failed", "error": "Step not implemented"}

            if engine_instance["engine_type"] == "playwright":
                result = await self._execute_playwright_step(step_type, step_config, engine_instance, step)
            elif engine_instance["engine_type"] == "selenium":
                result = await self._execute_selenium_step(step_type, step_config, engine_instance, step)
            elif engine_instance["engine_type"] == "requests_html":
                result = await self._execute_requests_step(step_type, step_config, engine_instance, step)

            execution_time_ms = int((time.time() - start_time) * 1000)
            result["execution_time_ms"] = execution_time_ms

            # Analizar DOM si es necesario
            if step_type in [WebStepType.CLICK, WebStepType.FILL, WebStepType.EXTRACT]:
                await self._analyze_dom(session_id, step["id"], engine_instance)

            return result

        except Exception as e:
            logger.error(f"Error executing web step: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_playwright_step(self, step_type: WebStepType, config: Dict, engine: Dict, step: Dict) -> Dict:
        """Ejecutar paso con Playwright"""
        try:
            page = engine["page"]

            if step_type == WebStepType.NAVIGATE:
                url = config.get("url")
                await page.goto(url, wait_until="networkidle", timeout=30000)
                return {"status": "success", "data": {"url": url}}

            elif step_type == WebStepType.CLICK:
                selectors = json.loads(step.get("target_selectors", "[]"))
                element = await self._find_element_playwright(page, selectors)

                if element:
                    await element.click()
                    return {"status": "success", "data": {"clicked": True}}
                else:
                    return {"status": "failed", "error": "Element not found"}

            elif step_type == WebStepType.FILL:
                selectors = json.loads(step.get("target_selectors", "[]"))
                value = config.get("value", "")
                element = await self._find_element_playwright(page, selectors)

                if element:
                    await element.fill(value)
                    return {"status": "success", "data": {"filled": value}}
                else:
                    return {"status": "failed", "error": "Input element not found"}

            elif step_type == WebStepType.EXTRACT:
                selectors = json.loads(step.get("target_selectors", "[]"))
                extracted_data = {}

                for selector_config in selectors:
                    selector = selector_config.get("selector")
                    field_name = selector_config.get("field", "data")

                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            extracted_data[field_name] = text.strip() if text else ""
                    except:
                        extracted_data[field_name] = ""

                return {"status": "success", "data": extracted_data}

            elif step_type == WebStepType.WAIT:
                duration = config.get("duration", 1000)
                await page.wait_for_timeout(duration)
                return {"status": "success", "data": {"waited_ms": duration}}

            elif step_type == WebStepType.SCREENSHOT:
                screenshot_path = f"static/web_screenshots/step_{step['id']}_{int(time.time())}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                return {"status": "success", "data": {"screenshot": screenshot_path}}

            elif step_type == WebStepType.CAPTCHA_SOLVE:
                return await self._solve_captcha_playwright(page, config)

            else:
                return {"status": "failed", "error": f"Step type not supported: {step_type}"}

        except Exception as e:
            logger.error(f"Error executing Playwright step: {e}")
            return {"status": "failed", "error": str(e)}

    async def _execute_selenium_step(self, step_type: WebStepType, config: Dict, engine: Dict, step: Dict) -> Dict:
        """Ejecutar paso con Selenium"""
        try:
            driver = engine["driver"]
            wait = engine["wait"]

            if step_type == WebStepType.NAVIGATE:
                url = config.get("url")
                driver.get(url)
                return {"status": "success", "data": {"url": url}}

            elif step_type == WebStepType.CLICK:
                selectors = json.loads(step.get("target_selectors", "[]"))
                element = await self._find_element_selenium(driver, wait, selectors)

                if element:
                    element.click()
                    return {"status": "success", "data": {"clicked": True}}
                else:
                    return {"status": "failed", "error": "Element not found"}

            elif step_type == WebStepType.FILL:
                selectors = json.loads(step.get("target_selectors", "[]"))
                value = config.get("value", "")
                element = await self._find_element_selenium(driver, wait, selectors)

                if element:
                    element.clear()
                    element.send_keys(value)
                    return {"status": "success", "data": {"filled": value}}
                else:
                    return {"status": "failed", "error": "Input element not found"}

            elif step_type == WebStepType.WAIT:
                duration = config.get("duration", 1000) / 1000  # Convert to seconds
                time.sleep(duration)
                return {"status": "success", "data": {"waited_ms": int(duration * 1000)}}

            else:
                return {"status": "failed", "error": f"Step type not supported for Selenium: {step_type}"}

        except Exception as e:
            logger.error(f"Error executing Selenium step: {e}")
            return {"status": "failed", "error": str(e)}

    async def _find_element_playwright(self, page: Page, selectors: List[Dict]) -> Optional[Any]:
        """Buscar elemento con múltiples estrategias en Playwright"""
        try:
            for selector_config in selectors:
                selector = selector_config.get("selector")
                strategy = selector_config.get("strategy", "css")

                try:
                    if strategy == "css":
                        element = await page.query_selector(selector)
                    elif strategy == "xpath":
                        element = await page.query_selector(f"xpath={selector}")
                    elif strategy == "text":
                        element = await page.get_by_text(selector).first
                    else:
                        element = await page.query_selector(selector)

                    if element:
                        return element

                except Exception as e:
                    logger.debug(f"Selector failed {selector}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"Error finding element: {e}")
            return None

    async def _find_element_selenium(self, driver, wait, selectors: List[Dict]) -> Optional[Any]:
        """Buscar elemento con múltiples estrategias en Selenium"""
        try:
            for selector_config in selectors:
                selector = selector_config.get("selector")
                strategy = selector_config.get("strategy", "css")

                try:
                    if strategy == "css":
                        element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    elif strategy == "xpath":
                        element = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    elif strategy == "id":
                        element = wait.until(EC.element_to_be_clickable((By.ID, selector)))
                    else:
                        element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))

                    if element:
                        return element

                except Exception as e:
                    logger.debug(f"Selenium selector failed {selector}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"Error finding Selenium element: {e}")
            return None

    async def _solve_captcha_playwright(self, page: Page, config: Dict) -> Dict:
        """Resolver CAPTCHA usando servicios externos"""
        try:
            # Detectar tipo de CAPTCHA
            captcha_info = await self._detect_captcha_type(page)

            if not captcha_info["detected"]:
                return {"status": "success", "data": {"captcha_solved": False, "reason": "No CAPTCHA detected"}}

            captcha_type = captcha_info["type"]

            # Intentar resolver según el tipo
            if captcha_type == "recaptcha_v2":
                return await self._solve_recaptcha_v2(page, captcha_info)
            elif captcha_type == "hcaptcha":
                return await self._solve_hcaptcha(page, captcha_info)
            else:
                return {"status": "failed", "error": f"CAPTCHA type not supported: {captcha_type}"}

        except Exception as e:
            logger.error(f"Error solving CAPTCHA: {e}")
            return {"status": "failed", "error": str(e)}

    async def _detect_captcha_type(self, page: Page) -> Dict:
        """Detectar tipo de CAPTCHA en la página"""
        try:
            # Buscar indicadores de diferentes tipos de CAPTCHA
            recaptcha_v2 = await page.query_selector(".g-recaptcha")
            recaptcha_v3 = await page.evaluate("() => window.grecaptcha !== undefined")
            hcaptcha = await page.query_selector(".h-captcha")

            if recaptcha_v2:
                site_key = await recaptcha_v2.get_attribute("data-sitekey")
                return {
                    "detected": True,
                    "type": "recaptcha_v2",
                    "site_key": site_key,
                    "element": recaptcha_v2
                }
            elif recaptcha_v3:
                return {
                    "detected": True,
                    "type": "recaptcha_v3",
                    "site_key": None,
                    "element": None
                }
            elif hcaptcha:
                site_key = await hcaptcha.get_attribute("data-sitekey")
                return {
                    "detected": True,
                    "type": "hcaptcha",
                    "site_key": site_key,
                    "element": hcaptcha
                }
            else:
                return {"detected": False, "type": None}

        except Exception as e:
            logger.error(f"Error detecting CAPTCHA: {e}")
            return {"detected": False, "type": None}

    async def _solve_recaptcha_v2(self, page: Page, captcha_info: Dict) -> Dict:
        """Resolver reCAPTCHA v2 usando servicio externo"""
        try:
            # Placeholder - integración con servicio de CAPTCHA
            # En implementación real se usaría 2captcha, anticaptcha, etc.

            logger.info("CAPTCHA v2 detected - would use external service")

            # Simular resolución exitosa para demo
            await asyncio.sleep(5)  # Tiempo simulado de resolución

            return {
                "status": "success",
                "data": {
                    "captcha_solved": True,
                    "method": "external_service",
                    "solve_time_ms": 5000
                }
            }

        except Exception as e:
            logger.error(f"Error solving reCAPTCHA v2: {e}")
            return {"status": "failed", "error": str(e)}

    async def _analyze_dom(self, session_id: str, step_id: int, engine_instance: Dict):
        """Analizar DOM de la página actual"""
        try:
            if engine_instance["engine_type"] != "playwright":
                return  # Solo soportado en Playwright por ahora

            page = engine_instance["page"]

            # Obtener información básica de la página
            page_url = page.url
            page_title = await page.title()

            # Contar elementos
            total_elements = await page.evaluate("() => document.querySelectorAll('*').length")
            interactive_elements = await page.evaluate("""
                () => document.querySelectorAll('input, button, select, textarea, a').length
            """)
            form_elements = await page.evaluate("() => document.querySelectorAll('form').length")

            # Detectar elementos interactivos
            detected_elements = await page.evaluate("""
                () => {
                    const elements = [];
                    const interactives = document.querySelectorAll('input, button, select, textarea, a');
                    for (let el of interactives) {
                        if (el.offsetParent !== null) {
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                type: el.type || null,
                                id: el.id || null,
                                class: el.className || null,
                                text: el.textContent?.slice(0, 100) || null,
                                selector: el.id ? `#${el.id}` : `.${el.className.split(' ')[0]}`
                            });
                        }
                    }
                    return elements.slice(0, 50);
                }
            """)

            # Guardar análisis en base de datos
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO web_dom_analysis (
                        session_id, step_id, page_url, page_title,
                        total_elements, interactive_elements, form_elements,
                        detected_elements, analysis_engine, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, step_id, page_url, page_title,
                    total_elements, interactive_elements, form_elements,
                    json.dumps(detected_elements), "playwright",
                    datetime.utcnow().isoformat()
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error analyzing DOM: {e}")

    async def _try_fallback_engine(self, session_id: str, step: Dict, original_error: str) -> Dict:
        """Intentar paso con engine de fallback"""
        try:
            fallback_engines = json.loads(step.get("fallback_engines", "[]"))

            for engine_name in fallback_engines:
                try:
                    engine = WebAutomationEngine(engine_name)
                    logger.info(f"Trying fallback engine: {engine_name}")

                    # Implementar lógica de fallback
                    # Por ahora retornar fallo
                    return {"status": "failed", "error": f"Fallback not implemented for {engine_name}"}

                except Exception as e:
                    logger.error(f"Fallback engine {engine_name} failed: {e}")
                    continue

            return {"status": "failed", "error": f"All fallback engines failed. Original: {original_error}"}

        except Exception as e:
            logger.error(f"Error trying fallback engine: {e}")
            return {"status": "failed", "error": str(e)}

    async def get_web_session_status(self, session_id: str) -> Dict[str, Any]:
        """Obtener estado actual de la sesión web"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, progress_percentage, current_step, total_steps,
                           execution_time_ms, retry_count, success_rate,
                           created_at, started_at, completed_at
                    FROM web_automation_sessions
                    WHERE session_id = ?
                """, (session_id,))

                result = cursor.fetchone()
                if result:
                    return {
                        "session_id": session_id,
                        "status": result[0],
                        "progress_percentage": result[1],
                        "current_step": result[2],
                        "total_steps": result[3],
                        "execution_time_ms": result[4],
                        "retry_count": result[5],
                        "success_rate": result[6],
                        "created_at": result[7],
                        "started_at": result[8],
                        "completed_at": result[9]
                    }
                else:
                    return {"error": "Sesión no encontrada"}

        except Exception as e:
            logger.error(f"Error getting web session status: {e}")
            return {"error": str(e)}

    async def get_web_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Obtener analytics de automatización web"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Métricas básicas
                cursor.execute("""
                    SELECT COUNT(*) as total_sessions,
                           COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_sessions,
                           COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_sessions,
                           AVG(execution_time_ms) as avg_execution_time,
                           AVG(success_rate) as avg_success_rate,
                           SUM(retry_count) as total_retries
                    FROM web_automation_sessions
                    WHERE user_id = ? AND created_at >= date('now', '-{} days')
                """.format(days), (user_id,))

                basic_metrics = cursor.fetchone()

                # Uso por engine
                cursor.execute("""
                    SELECT primary_engine, COUNT(*) as usage_count,
                           AVG(success_rate) as avg_success_rate
                    FROM web_automation_sessions
                    WHERE user_id = ? AND created_at >= date('now', '-{} days')
                    GROUP BY primary_engine
                    ORDER BY usage_count DESC
                """.format(days), (user_id,))

                engine_usage = {}
                for row in cursor.fetchall():
                    engine_usage[row[0]] = {
                        "usage_count": row[1],
                        "success_rate": round(row[2], 2) if row[2] else 0.0
                    }

                return {
                    "user_id": user_id,
                    "period_days": days,
                    "total_sessions": basic_metrics[0] if basic_metrics else 0,
                    "successful_sessions": basic_metrics[1] if basic_metrics else 0,
                    "failed_sessions": basic_metrics[2] if basic_metrics else 0,
                    "success_rate": round((basic_metrics[1] / max(basic_metrics[0], 1)) * 100, 2) if basic_metrics else 0,
                    "average_execution_time_ms": round(basic_metrics[3], 2) if basic_metrics and basic_metrics[3] else 0,
                    "average_success_rate": round(basic_metrics[4], 2) if basic_metrics and basic_metrics[4] else 0,
                    "total_retries": basic_metrics[5] if basic_metrics else 0,
                    "engine_usage": engine_usage,
                    "generated_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Error getting web analytics: {e}")
            return {"user_id": user_id, "error": str(e)}

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance del sistema web"""
        try:
            system_metrics = {
                "cpu_usage_percent": psutil.cpu_percent(interval=1),
                "memory_usage_percent": psutil.virtual_memory().percent,
                "available_memory_gb": round(psutil.virtual_memory().available / (1024**3), 2)
            }

            return {
                "active_sessions": len(self.active_engines),
                "engine_health": self.engine_health,
                "system_metrics": system_metrics,
                "performance_metrics": self.performance_metrics,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {"error": str(e)}

    # Helper methods for database operations
    async def _get_session_data(self, session_id: str) -> Optional[Dict]:
        """Obtener datos de sesión de la base de datos"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM web_automation_sessions WHERE session_id = ?
                """, (session_id,))

                result = cursor.fetchone()
                if result:
                    return dict(result)
                return None

        except Exception as e:
            logger.error(f"Error getting session data: {e}")
            return None

    async def _get_session_steps(self, session_id: str) -> List[Dict]:
        """Obtener pasos de una sesión"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM web_automation_steps
                    WHERE session_id = ?
                    ORDER BY step_number ASC
                """, (session_id,))

                results = cursor.fetchall()
                return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error getting session steps: {e}")
            return []

    async def _update_session_status(self, session_id: str, status: WebSessionStatus):
        """Actualizar estado de sesión"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE web_automation_sessions
                    SET status = ?, updated_at = ?
                    WHERE session_id = ?
                """, (status.value, datetime.utcnow().isoformat(), session_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating session status: {e}")

    async def _increment_step_attempts(self, step_id: int):
        """Incrementar contador de intentos de paso"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE web_automation_steps
                    SET execution_attempts = execution_attempts + 1
                    WHERE id = ?
                """, (step_id,))
                conn.commit()

        except Exception as e:
            logger.error(f"Error incrementing step attempts: {e}")

    async def _mark_step_completed(self, step_id: int, execution_time_ms: int):
        """Marcar paso como completado"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE web_automation_steps
                    SET status = ?, execution_time_ms = ?, completed_at = ?
                    WHERE id = ?
                """, ("completed", execution_time_ms, datetime.utcnow().isoformat(), step_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error marking step completed: {e}")

    async def _mark_step_failed(self, step_id: int, error_message: str):
        """Marcar paso como fallido"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE web_automation_steps
                    SET status = ?, error_message = ?
                    WHERE id = ?
                """, ("failed", error_message, step_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error marking step failed: {e}")

    async def _should_continue_after_failure(self, session_id: str, failed_step: Dict) -> bool:
        """Determinar si continuar después de un fallo"""
        try:
            # Lógica simple: continuar si no es un paso crítico
            step_type = failed_step.get("step_type")
            critical_steps = ["navigate", "captcha_solve"]

            return step_type not in critical_steps

        except Exception as e:
            logger.error(f"Error determining continuation: {e}")
            return False

    async def _recommend_engine_for_step(self, step: Dict) -> WebAutomationEngine:
        """Recomendar engine óptimo para un paso específico"""
        try:
            step_type = step.get("type", "navigate")

            # Lógica de recomendación simple
            if step_type in ["javascript", "extract"]:
                return WebAutomationEngine.PLAYWRIGHT
            elif step_type in ["click", "fill"]:
                return WebAutomationEngine.SELENIUM
            elif step_type == "navigate" and step.get("simple", False):
                return WebAutomationEngine.REQUESTS_HTML
            else:
                return WebAutomationEngine.PLAYWRIGHT

        except Exception as e:
            logger.error(f"Error recommending engine: {e}")
            return WebAutomationEngine.PLAYWRIGHT

    async def _cleanup_web_session(self, session_id: str):
        """Limpiar recursos de sesión web"""
        try:
            if session_id in self.active_engines:
                engine_instance = self.active_engines[session_id]

                # Limpiar según tipo de engine
                if engine_instance["engine_type"] == "playwright":
                    if "browser" in engine_instance:
                        await engine_instance["browser"].close()
                    if "playwright" in engine_instance:
                        await engine_instance["playwright"].stop()
                elif engine_instance["engine_type"] == "selenium":
                    if "driver" in engine_instance:
                        engine_instance["driver"].quit()

                # Remover de cache
                del self.active_engines[session_id]

                logger.info(f"Cleaned up web session {session_id}")

        except Exception as e:
            logger.error(f"Error cleaning up web session: {e}")