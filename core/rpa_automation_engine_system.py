import asyncio
import json
import logging
import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
import sqlite3
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import aiofiles
from pathlib import Path
import base64
from cryptography.fernet import Fernet
import psutil

logger = logging.getLogger(__name__)

class RPASessionStatus(Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RPAStepType(Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    VALIDATE = "validate"
    CUSTOM = "custom"

class RPAStepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class SelectorStrategy(Enum):
    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"
    ROLE = "role"
    AUTO = "auto"

class RPAAutomationEngineSystem:
    """
    Sistema de Motor de Automatización RPA con Playwright

    Características:
    - Gestión de sesiones persistentes con estado
    - Screenshots automáticos con metadata completa
    - Sistema de error recovery robusto
    - Plantillas de portales reutilizables
    - Seguridad avanzada para credenciales
    - Monitoreo de performance en tiempo real
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

        # Configuración de directorios
        self.screenshots_dir = Path("static/automation_screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Configuración de seguridad
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)

        # Cache de sesiones activas
        self.active_sessions = {}
        self.browser_instances = {}

        # Configuración de Playwright
        self.playwright_config = {
            "headless": True,
            "slow_mo": 100,  # ms entre acciones
            "timeout": 30000,
            "viewport": {"width": 1920, "height": 1080}
        }

        # Plantillas de portales cargadas
        self.portal_templates = {}

    def _get_or_create_encryption_key(self) -> bytes:
        """Obtener o crear clave de encriptación para credenciales"""
        key_file = Path(".rpa_encryption_key")

        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            # Cambiar permisos para solo el propietario
            os.chmod(key_file, 0o600)
            return key

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

    async def create_rpa_session(self, user_id: str, company_id: str,
                                portal_name: str, portal_url: str,
                                automation_steps: List[Dict],
                                credentials: Dict = None,
                                browser_config: Dict = None) -> str:
        """Crear nueva sesión de automatización RPA"""
        try:
            session_id = f"rpa_{int(time.time())}_{user_id[:8]}"

            # Encriptar credenciales si se proporcionan
            credentials_encrypted = None
            if credentials:
                credentials_json = json.dumps(credentials)
                credentials_encrypted = self.cipher.encrypt(credentials_json.encode()).decode()

            # Configuración por defecto del navegador
            final_browser_config = {**self.playwright_config, **(browser_config or {})}

            # Estado inicial de sesión
            initial_session_state = {
                "browser_launched": False,
                "context_created": False,
                "page_loaded": False,
                "current_url": None,
                "cookies": [],
                "local_storage": {},
                "session_storage": {},
                "last_screenshot": None,
                "performance_metrics": {
                    "start_time": time.time(),
                    "memory_usage_mb": 0.0,
                    "cpu_usage_percent": 0.0
                }
            }

            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO rpa_automation_sessions (
                        session_id, user_id, company_id, portal_name, portal_url,
                        portal_config, session_state, credentials_encrypted,
                        automation_steps, browser_config, total_steps,
                        error_recovery, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, user_id, company_id, portal_name, portal_url,
                    json.dumps({}), json.dumps(initial_session_state),
                    credentials_encrypted, json.dumps(automation_steps),
                    json.dumps(final_browser_config), len(automation_steps),
                    json.dumps({"enabled": True, "max_retries": 3, "strategies": []}),
                    datetime.utcnow().isoformat()
                ))

                # Crear pasos individuales
                for i, step in enumerate(automation_steps):
                    cursor.execute("""
                        INSERT INTO rpa_automation_steps (
                            session_id, step_number, step_type, step_name,
                            step_config, primary_selector, execution_order
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session_id, i + 1, step.get('type', 'custom'),
                        step.get('name', f'Step {i + 1}'),
                        json.dumps(step), step.get('selector'),
                        i + 1
                    ))

                conn.commit()

                logger.info(f"Created RPA session {session_id} for user {user_id}")
                return session_id

        except Exception as e:
            logger.error(f"Error creating RPA session: {e}")
            raise

    async def start_rpa_session(self, session_id: str) -> Dict[str, Any]:
        """Iniciar ejecución de sesión RPA"""
        try:
            # Obtener configuración de sesión
            session_data = await self._get_session_data(session_id)
            if not session_data:
                return {"status": "error", "message": "Sesión no encontrada"}

            # Actualizar estado a running
            await self._update_session_status(session_id, RPASessionStatus.RUNNING)

            # Inicializar Playwright
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=session_data["browser_config"].get("headless", True),
                slow_mo=session_data["browser_config"].get("slow_mo", 100)
            )

            # Crear contexto
            context = await browser.new_context(
                viewport=session_data["browser_config"].get("viewport"),
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            page = await context.new_page()

            # Guardar instancias activas
            self.active_sessions[session_id] = {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page,
                "start_time": time.time()
            }

            # Actualizar estado de sesión
            session_state = json.loads(session_data["session_state"])
            session_state.update({
                "browser_launched": True,
                "context_created": True,
                "page_loaded": True,
                "start_time": time.time()
            })

            await self._update_session_state(session_id, session_state)

            # Ejecutar pasos en background
            asyncio.create_task(self._execute_automation_steps(session_id))

            return {
                "status": "success",
                "session_id": session_id,
                "message": "Sesión RPA iniciada exitosamente"
            }

        except Exception as e:
            logger.error(f"Error starting RPA session: {e}")
            await self._update_session_status(session_id, RPASessionStatus.FAILED)
            return {"status": "error", "message": str(e)}

    async def _execute_automation_steps(self, session_id: str):
        """Ejecutar pasos de automatización de forma asíncrona"""
        try:
            session_data = await self._get_session_data(session_id)
            steps = await self._get_session_steps(session_id)
            session_instances = self.active_sessions.get(session_id)

            if not session_instances:
                raise Exception("Instancias de navegador no encontradas")

            page = session_instances["page"]

            # Screenshot inicial
            await self._capture_screenshot(session_id, None, "initial")

            for step in steps:
                try:
                    await self._execute_single_step(session_id, step, page)
                    await asyncio.sleep(0.5)  # Pausa entre pasos
                except Exception as step_error:
                    logger.error(f"Error in step {step['step_number']}: {step_error}")

                    # Intentar recuperación de error
                    recovered = await self._attempt_error_recovery(session_id, step, step_error)
                    if not recovered:
                        await self._update_session_status(session_id, RPASessionStatus.FAILED)
                        return

            # Screenshot final
            await self._capture_screenshot(session_id, None, "final")

            # Completar sesión
            await self._update_session_status(session_id, RPASessionStatus.COMPLETED)
            await self._cleanup_session(session_id)

        except Exception as e:
            logger.error(f"Error executing automation steps: {e}")
            await self._update_session_status(session_id, RPASessionStatus.FAILED)
        finally:
            await self._cleanup_session(session_id)

    async def _execute_single_step(self, session_id: str, step: Dict, page: Page):
        """Ejecutar un paso individual de automatización"""
        try:
            step_id = step["id"]
            step_type = RPAStepType(step["step_type"])
            step_config = json.loads(step["step_config"])

            # Actualizar estado del paso
            await self._update_step_status(step_id, RPAStepStatus.RUNNING)

            # Screenshot antes de la acción
            await self._capture_screenshot(session_id, step_id, "before_action")

            start_time = time.time()

            if step_type == RPAStepType.NAVIGATE:
                url = step_config.get("url")
                await page.goto(url, wait_until="networkidle")

            elif step_type == RPAStepType.CLICK:
                selector = step["primary_selector"]
                element = await self._find_element_with_fallback(page, step)
                if element:
                    await element.click()
                else:
                    raise Exception(f"Elemento no encontrado: {selector}")

            elif step_type == RPAStepType.FILL:
                selector = step["primary_selector"]
                value = step_config.get("value", "")
                element = await self._find_element_with_fallback(page, step)
                if element:
                    await element.fill(value)
                else:
                    raise Exception(f"Campo no encontrado: {selector}")

            elif step_type == RPAStepType.WAIT:
                wait_time = step_config.get("duration", 1000)
                await page.wait_for_timeout(wait_time)

            elif step_type == RPAStepType.SCREENSHOT:
                await self._capture_screenshot(session_id, step_id, "custom")

            elif step_type == RPAStepType.EXTRACT:
                data = await self._extract_data_from_page(page, step_config)
                await self._save_step_result(step_id, data)

            elif step_type == RPAStepType.VALIDATE:
                validation_result = await self._validate_page_state(page, step_config)
                if not validation_result["valid"]:
                    raise Exception(f"Validación falló: {validation_result['message']}")

            # Screenshot después de la acción
            await self._capture_screenshot(session_id, step_id, "after_action")

            execution_time = int((time.time() - start_time) * 1000)

            # Actualizar paso como completado
            await self._update_step_completion(step_id, execution_time)

        except Exception as e:
            logger.error(f"Error executing step {step.get('step_number')}: {e}")
            await self._update_step_status(step["id"], RPAStepStatus.FAILED)
            await self._capture_screenshot(session_id, step["id"], "error")
            raise

    async def _find_element_with_fallback(self, page: Page, step: Dict):
        """Buscar elemento con estrategias de fallback"""
        try:
            primary_selector = step["primary_selector"]
            fallback_selectors = json.loads(step.get("fallback_selectors", "[]"))

            # Intentar selector principal
            try:
                element = await page.wait_for_selector(primary_selector, timeout=5000)
                if element:
                    return element
            except:
                pass

            # Intentar selectores de fallback
            for fallback in fallback_selectors:
                try:
                    element = await page.wait_for_selector(fallback, timeout=3000)
                    if element:
                        logger.info(f"Usado selector fallback: {fallback}")
                        return element
                except:
                    continue

            # Estrategia de último recurso: buscar por texto
            if "text" in step.get("step_config", {}):
                text = json.loads(step["step_config"])["text"]
                try:
                    element = await page.get_by_text(text).first
                    if element:
                        logger.info(f"Encontrado por texto: {text}")
                        return element
                except:
                    pass

            return None

        except Exception as e:
            logger.error(f"Error finding element: {e}")
            return None

    async def _capture_screenshot(self, session_id: str, step_id: Optional[int],
                                screenshot_type: str) -> str:
        """Capturar screenshot con metadata completa"""
        try:
            session_instances = self.active_sessions.get(session_id)
            if not session_instances:
                return None

            page = session_instances["page"]

            # Generar nombre de archivo
            timestamp = int(time.time())
            filename = f"{screenshot_type}_{session_id}_{timestamp}.png"
            filepath = self.screenshots_dir / filename

            # Capturar screenshot
            await page.screenshot(path=str(filepath), full_page=True)

            # Obtener información de la página
            page_url = page.url
            page_title = await page.title()
            viewport = await page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")

            # Contar elementos DOM
            dom_elements_count = await page.evaluate("() => document.querySelectorAll('*').length")

            # Obtener elementos interactivos
            interactive_elements = await page.evaluate("""
                () => {
                    const elements = [];
                    const interactives = document.querySelectorAll('input, button, select, textarea, a');
                    for (let el of interactives) {
                        if (el.offsetParent !== null) { // Visible
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                type: el.type || null,
                                id: el.id || null,
                                class: el.className || null,
                                text: el.textContent?.slice(0, 50) || null
                            });
                        }
                    }
                    return elements.slice(0, 50); // Límite para no sobrecargar
                }
            """)

            # Metadata completa del screenshot
            screenshot_metadata = {
                "capture_method": "playwright",
                "page_load_state": await page.evaluate("() => document.readyState"),
                "scroll_position": await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })"),
                "network_activity": len(await page.evaluate("() => performance.getEntriesByType('navigation')")),
                "timestamp": datetime.utcnow().isoformat(),
                "file_size_bytes": filepath.stat().st_size if filepath.exists() else 0,
                "browser_info": {
                    "user_agent": await page.evaluate("() => navigator.userAgent"),
                    "viewport_size": viewport,
                    "screen_resolution": f"{viewport['width']}x{viewport['height']}"
                },
                "page_performance": {
                    "dom_elements": dom_elements_count,
                    "interactive_elements": len(interactive_elements),
                    "load_time": await page.evaluate("() => performance.timing.loadEventEnd - performance.timing.navigationStart")
                }
            }

            # Guardar en base de datos
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO rpa_screenshots (
                        session_id, step_id, screenshot_type, file_path,
                        file_size_bytes, screenshot_metadata, screen_resolution,
                        viewport_size, page_url, page_title, dom_elements_count,
                        interactive_elements, captured_at, is_error_screenshot
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, step_id, screenshot_type, str(filepath),
                    screenshot_metadata["file_size_bytes"],
                    json.dumps(screenshot_metadata),
                    f"{viewport['width']}x{viewport['height']}",
                    f"{viewport['width']}x{viewport['height']}",
                    page_url, page_title, dom_elements_count,
                    json.dumps(interactive_elements),
                    datetime.utcnow().isoformat(),
                    screenshot_type == "error"
                ))
                conn.commit()

            logger.info(f"Screenshot captured: {filename}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            return None

    async def _attempt_error_recovery(self, session_id: str, step: Dict, error: Exception) -> bool:
        """Intentar recuperación de error"""
        try:
            session_data = await self._get_session_data(session_id)
            error_recovery_config = json.loads(session_data.get("error_recovery", "{}"))

            if not error_recovery_config.get("enabled", True):
                return False

            max_retries = error_recovery_config.get("max_retries", 3)
            current_retries = step.get("retry_count", 0)

            if current_retries >= max_retries:
                logger.warning(f"Max retries reached for step {step['step_number']}")
                return False

            # Incrementar contador de reintentos
            await self._increment_step_retry_count(step["id"])

            # Estrategias de recuperación
            recovery_strategies = error_recovery_config.get("strategies", [])

            for strategy in recovery_strategies:
                if strategy == "refresh_page":
                    await self._refresh_page_recovery(session_id)
                elif strategy == "wait_and_retry":
                    await asyncio.sleep(2)
                elif strategy == "clear_cookies":
                    await self._clear_cookies_recovery(session_id)

            # Log de recuperación
            await self._log_error_recovery(session_id, step["id"], error, "attempted")

            return True

        except Exception as e:
            logger.error(f"Error in recovery attempt: {e}")
            return False

    async def _refresh_page_recovery(self, session_id: str):
        """Estrategia de recuperación: refrescar página"""
        try:
            session_instances = self.active_sessions.get(session_id)
            if session_instances:
                await session_instances["page"].reload(wait_until="networkidle")
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in page refresh recovery: {e}")

    async def _clear_cookies_recovery(self, session_id: str):
        """Estrategia de recuperación: limpiar cookies"""
        try:
            session_instances = self.active_sessions.get(session_id)
            if session_instances:
                await session_instances["context"].clear_cookies()
        except Exception as e:
            logger.error(f"Error in clear cookies recovery: {e}")

    async def _extract_data_from_page(self, page: Page, config: Dict) -> Dict:
        """Extraer datos de la página según configuración"""
        try:
            extraction_rules = config.get("extraction_rules", {})
            extracted_data = {}

            for field_name, rule in extraction_rules.items():
                selector = rule.get("selector")
                attribute = rule.get("attribute", "textContent")

                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        if attribute == "textContent":
                            value = await element.text_content()
                        else:
                            value = await element.get_attribute(attribute)

                        extracted_data[field_name] = value

            return extracted_data

        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            return {}

    async def _validate_page_state(self, page: Page, config: Dict) -> Dict:
        """Validar estado de la página"""
        try:
            validations = config.get("validations", [])

            for validation in validations:
                rule_type = validation.get("type")

                if rule_type == "element_exists":
                    selector = validation.get("selector")
                    element = await page.query_selector(selector)
                    if not element:
                        return {"valid": False, "message": f"Elemento no encontrado: {selector}"}

                elif rule_type == "url_contains":
                    expected_text = validation.get("text")
                    if expected_text not in page.url:
                        return {"valid": False, "message": f"URL no contiene: {expected_text}"}

                elif rule_type == "title_contains":
                    expected_text = validation.get("text")
                    title = await page.title()
                    if expected_text not in title:
                        return {"valid": False, "message": f"Título no contiene: {expected_text}"}

            return {"valid": True, "message": "Todas las validaciones pasaron"}

        except Exception as e:
            logger.error(f"Error validating page state: {e}")
            return {"valid": False, "message": f"Error en validación: {str(e)}"}

    async def pause_rpa_session(self, session_id: str) -> Dict[str, Any]:
        """Pausar sesión RPA"""
        try:
            await self._update_session_status(session_id, RPASessionStatus.PAUSED)
            return {"status": "success", "message": "Sesión pausada"}
        except Exception as e:
            logger.error(f"Error pausing session: {e}")
            return {"status": "error", "message": str(e)}

    async def resume_rpa_session(self, session_id: str) -> Dict[str, Any]:
        """Reanudar sesión RPA pausada"""
        try:
            await self._update_session_status(session_id, RPASessionStatus.RUNNING)
            return {"status": "success", "message": "Sesión reanudada"}
        except Exception as e:
            logger.error(f"Error resuming session: {e}")
            return {"status": "error", "message": str(e)}

    async def cancel_rpa_session(self, session_id: str) -> Dict[str, Any]:
        """Cancelar sesión RPA"""
        try:
            await self._update_session_status(session_id, RPASessionStatus.CANCELLED)
            await self._cleanup_session(session_id)
            return {"status": "success", "message": "Sesión cancelada"}
        except Exception as e:
            logger.error(f"Error cancelling session: {e}")
            return {"status": "error", "message": str(e)}

    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Obtener estado actual de la sesión"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT status, progress_percentage, current_step, total_steps,
                           execution_time_ms, created_at, started_at, completed_at
                    FROM rpa_automation_sessions
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
                        "created_at": result[5],
                        "started_at": result[6],
                        "completed_at": result[7]
                    }
                else:
                    return {"error": "Sesión no encontrada"}

        except Exception as e:
            logger.error(f"Error getting session status: {e}")
            return {"error": str(e)}

    async def get_session_screenshots(self, session_id: str, screenshot_type: str = None) -> List[Dict]:
        """Obtener screenshots de una sesión"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, screenshot_type, file_path, file_size_bytes,
                           screenshot_metadata, page_url, page_title, captured_at
                    FROM rpa_screenshots
                    WHERE session_id = ?
                """
                params = [session_id]

                if screenshot_type:
                    query += " AND screenshot_type = ?"
                    params.append(screenshot_type)

                query += " ORDER BY captured_at ASC"

                cursor.execute(query, params)
                results = cursor.fetchall()

                screenshots = []
                for row in results:
                    screenshots.append({
                        "id": row[0],
                        "screenshot_type": row[1],
                        "file_path": row[2],
                        "file_size_bytes": row[3],
                        "screenshot_metadata": json.loads(row[4]) if row[4] else {},
                        "page_url": row[5],
                        "page_title": row[6],
                        "captured_at": row[7]
                    })

                return screenshots

        except Exception as e:
            logger.error(f"Error getting session screenshots: {e}")
            return []

    async def get_rpa_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Obtener analytics de RPA para usuario"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Métricas básicas
                cursor.execute("""
                    SELECT COUNT(*) as total_sessions,
                           COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_sessions,
                           COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_sessions,
                           AVG(execution_time_ms) as avg_execution_time,
                           AVG(progress_percentage) as avg_progress
                    FROM rpa_automation_sessions
                    WHERE user_id = ? AND created_at >= date('now', '-{} days')
                """.format(days), (user_id,))

                basic_metrics = cursor.fetchone()

                # Portales más usados
                cursor.execute("""
                    SELECT portal_name, COUNT(*) as usage_count
                    FROM rpa_automation_sessions
                    WHERE user_id = ? AND created_at >= date('now', '-{} days')
                    GROUP BY portal_name
                    ORDER BY usage_count DESC
                    LIMIT 10
                """.format(days), (user_id,))

                portal_usage = dict(cursor.fetchall())

                return {
                    "user_id": user_id,
                    "period_days": days,
                    "total_sessions": basic_metrics[0] if basic_metrics else 0,
                    "successful_sessions": basic_metrics[1] if basic_metrics else 0,
                    "failed_sessions": basic_metrics[2] if basic_metrics else 0,
                    "success_rate": round((basic_metrics[1] / max(basic_metrics[0], 1)) * 100, 2) if basic_metrics else 0,
                    "average_execution_time_ms": round(basic_metrics[3], 2) if basic_metrics and basic_metrics[3] else 0,
                    "average_progress": round(basic_metrics[4], 2) if basic_metrics and basic_metrics[4] else 0,
                    "portal_usage": portal_usage,
                    "generated_at": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Error getting RPA analytics: {e}")
            return {"user_id": user_id, "error": str(e)}

    async def _get_session_data(self, session_id: str) -> Optional[Dict]:
        """Obtener datos de sesión de la base de datos"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM rpa_automation_sessions WHERE session_id = ?
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
                    SELECT * FROM rpa_automation_steps
                    WHERE session_id = ?
                    ORDER BY execution_order ASC
                """, (session_id,))

                results = cursor.fetchall()
                return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error getting session steps: {e}")
            return []

    async def _update_session_status(self, session_id: str, status: RPASessionStatus):
        """Actualizar estado de sesión"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rpa_automation_sessions
                    SET status = ?, updated_at = ?
                    WHERE session_id = ?
                """, (status.value, datetime.utcnow().isoformat(), session_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating session status: {e}")

    async def _update_session_state(self, session_id: str, session_state: Dict):
        """Actualizar estado de sesión en BD"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rpa_automation_sessions
                    SET session_state = ?, updated_at = ?
                    WHERE session_id = ?
                """, (json.dumps(session_state), datetime.utcnow().isoformat(), session_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating session state: {e}")

    async def _update_step_status(self, step_id: int, status: RPAStepStatus):
        """Actualizar estado de paso"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rpa_automation_steps
                    SET status = ?
                    WHERE id = ?
                """, (status.value, step_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating step status: {e}")

    async def _update_step_completion(self, step_id: int, execution_time_ms: int):
        """Actualizar paso como completado"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rpa_automation_steps
                    SET status = ?, execution_time_ms = ?, completed_at = ?
                    WHERE id = ?
                """, (RPAStepStatus.COMPLETED.value, execution_time_ms,
                      datetime.utcnow().isoformat(), step_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error updating step completion: {e}")

    async def _increment_step_retry_count(self, step_id: int):
        """Incrementar contador de reintentos de paso"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rpa_automation_steps
                    SET retry_count = retry_count + 1
                    WHERE id = ?
                """, (step_id,))
                conn.commit()

        except Exception as e:
            logger.error(f"Error incrementing step retry count: {e}")

    async def _save_step_result(self, step_id: int, result_data: Dict):
        """Guardar resultado de paso"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rpa_automation_steps
                    SET result_data = ?
                    WHERE id = ?
                """, (json.dumps(result_data), step_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Error saving step result: {e}")

    async def _log_error_recovery(self, session_id: str, step_id: int, error: Exception, action: str):
        """Log de recuperación de error"""
        try:
            async with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO rpa_execution_logs (
                        session_id, step_id, log_level, log_category,
                        log_message, error_type, error_recovery_attempted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, step_id, "WARN", "error_recovery",
                    f"Error recovery {action}: {str(error)}",
                    type(error).__name__, True
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error logging error recovery: {e}")

    async def _cleanup_session(self, session_id: str):
        """Limpiar recursos de sesión"""
        try:
            if session_id in self.active_sessions:
                instances = self.active_sessions[session_id]

                # Cerrar navegador
                if "browser" in instances:
                    await instances["browser"].close()

                # Cerrar Playwright
                if "playwright" in instances:
                    await instances["playwright"].stop()

                # Remover de cache
                del self.active_sessions[session_id]

                logger.info(f"Cleaned up session {session_id}")

        except Exception as e:
            logger.error(f"Error cleaning up session: {e}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance del sistema"""
        try:
            # Métricas del sistema
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            return {
                "active_sessions": len(self.active_sessions),
                "system_metrics": {
                    "cpu_usage_percent": cpu_percent,
                    "memory_usage_percent": memory.percent,
                    "available_memory_gb": round(memory.available / (1024**3), 2)
                },
                "browser_instances": len(self.browser_instances),
                "screenshots_directory_size_mb": self._get_directory_size_mb(self.screenshots_dir),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {"error": str(e)}

    def _get_directory_size_mb(self, directory: Path) -> float:
        """Obtener tamaño de directorio en MB"""
        try:
            total_size = sum(f.stat().st_size for f in directory.glob('**/*') if f.is_file())
            return round(total_size / (1024 * 1024), 2)
        except:
            return 0.0