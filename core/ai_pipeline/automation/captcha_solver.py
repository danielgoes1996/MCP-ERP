"""
2Captcha Service Integration

Servicio para resolver captchas automáticamente usando 2Captcha API.
Reemplaza la necesidad de GPT-4 Vision para captchas visuales.
"""

import os
import time
import logging
import base64
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

@dataclass
class CaptchaResult:
    """Resultado de resolución de captcha"""
    solution: str
    confidence: float
    solving_time_ms: int
    captcha_type: str
    cost_credits: float
    service_id: str

@dataclass
class CaptchaTask:
    """Tarea de captcha para resolver"""
    captcha_type: str  # recaptcha_v2, recaptcha_v3, hcaptcha, image
    site_key: Optional[str] = None
    page_url: Optional[str] = None
    image_path: Optional[str] = None
    image_base64: Optional[str] = None
    action: Optional[str] = None  # Para reCAPTCHA v3
    min_score: Optional[float] = None  # Para reCAPTCHA v3

class TwoCaptchaSolver:
    """Cliente para 2Captcha API"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TWOCAPTCHA_API_KEY")
        self.base_url = "http://2captcha.com"
        self.session = requests.Session()

        if not self.api_key:
            logger.warning("⚠️ 2Captcha API key no configurada")

    def is_available(self) -> bool:
        """Verificar si el servicio está disponible"""
        return bool(self.api_key)

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> CaptchaResult:
        """Resolver reCAPTCHA v2"""

        start_time = datetime.now()

        try:
            # Enviar tarea
            submit_data = {
                'key': self.api_key,
                'method': 'userrecaptcha',
                'googlekey': site_key,
                'pageurl': page_url,
                'json': 1
            }

            submit_response = self.session.post(f"{self.base_url}/in.php", data=submit_data)
            submit_result = submit_response.json()

            if submit_result['status'] != 1:
                raise Exception(f"Error enviando captcha: {submit_result.get('error_text', 'Unknown error')}")

            captcha_id = submit_result['request']
            logger.info(f"🔄 reCAPTCHA v2 enviado: ID {captcha_id}")

            # Esperar resultado
            solution = await self._wait_for_solution(captcha_id)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return CaptchaResult(
                solution=solution,
                confidence=0.95,  # 2Captcha típicamente tiene alta confianza
                solving_time_ms=int(processing_time),
                captcha_type="recaptcha_v2",
                cost_credits=0.001,  # Costo típico
                service_id=captcha_id
            )

        except Exception as e:
            logger.error(f"❌ Error resolviendo reCAPTCHA v2: {e}")
            raise

    async def solve_recaptcha_v3(self, site_key: str, page_url: str, action: str = "submit", min_score: float = 0.3) -> CaptchaResult:
        """Resolver reCAPTCHA v3"""

        start_time = datetime.now()

        try:
            submit_data = {
                'key': self.api_key,
                'method': 'userrecaptcha',
                'version': 'v3',
                'googlekey': site_key,
                'pageurl': page_url,
                'action': action,
                'min_score': min_score,
                'json': 1
            }

            submit_response = self.session.post(f"{self.base_url}/in.php", data=submit_data)
            submit_result = submit_response.json()

            if submit_result['status'] != 1:
                raise Exception(f"Error enviando reCAPTCHA v3: {submit_result.get('error_text', 'Unknown error')}")

            captcha_id = submit_result['request']
            logger.info(f"🔄 reCAPTCHA v3 enviado: ID {captcha_id}")

            solution = await self._wait_for_solution(captcha_id)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return CaptchaResult(
                solution=solution,
                confidence=0.9,
                solving_time_ms=int(processing_time),
                captcha_type="recaptcha_v3",
                cost_credits=0.002,
                service_id=captcha_id
            )

        except Exception as e:
            logger.error(f"❌ Error resolviendo reCAPTCHA v3: {e}")
            raise

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> CaptchaResult:
        """Resolver hCaptcha"""

        start_time = datetime.now()

        try:
            submit_data = {
                'key': self.api_key,
                'method': 'hcaptcha',
                'sitekey': site_key,
                'pageurl': page_url,
                'json': 1
            }

            submit_response = self.session.post(f"{self.base_url}/in.php", data=submit_data)
            submit_result = submit_response.json()

            if submit_result['status'] != 1:
                raise Exception(f"Error enviando hCaptcha: {submit_result.get('error_text', 'Unknown error')}")

            captcha_id = submit_result['request']
            logger.info(f"🔄 hCaptcha enviado: ID {captcha_id}")

            solution = await self._wait_for_solution(captcha_id)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return CaptchaResult(
                solution=solution,
                confidence=0.93,
                solving_time_ms=int(processing_time),
                captcha_type="hcaptcha",
                cost_credits=0.001,
                service_id=captcha_id
            )

        except Exception as e:
            logger.error(f"❌ Error resolviendo hCaptcha: {e}")
            raise

    async def solve_image_captcha(self, image_path: str = None, image_base64: str = None) -> CaptchaResult:
        """Resolver captcha de imagen"""

        start_time = datetime.now()

        try:
            # Preparar imagen
            if image_path and os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
            elif image_base64:
                image_data = image_base64
            else:
                raise Exception("Se requiere image_path o image_base64")

            submit_data = {
                'key': self.api_key,
                'method': 'base64',
                'body': image_data,
                'json': 1
            }

            submit_response = self.session.post(f"{self.base_url}/in.php", data=submit_data)
            submit_result = submit_response.json()

            if submit_result['status'] != 1:
                raise Exception(f"Error enviando image captcha: {submit_result.get('error_text', 'Unknown error')}")

            captcha_id = submit_result['request']
            logger.info(f"🔄 Image captcha enviado: ID {captcha_id}")

            solution = await self._wait_for_solution(captcha_id)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return CaptchaResult(
                solution=solution,
                confidence=0.85,  # Image captchas suelen tener menor confianza
                solving_time_ms=int(processing_time),
                captcha_type="image",
                cost_credits=0.0005,
                service_id=captcha_id
            )

        except Exception as e:
            logger.error(f"❌ Error resolviendo image captcha: {e}")
            raise

    async def _wait_for_solution(self, captcha_id: str, max_wait_time: int = 120) -> str:
        """Esperar a que se resuelva el captcha"""

        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                result_response = self.session.get(
                    f"{self.base_url}/res.php",
                    params={
                        'key': self.api_key,
                        'action': 'get',
                        'id': captcha_id,
                        'json': 1
                    }
                )

                result_data = result_response.json()

                if result_data['status'] == 1:
                    # Captcha resuelto
                    solution = result_data['request']
                    logger.info(f"✅ Captcha {captcha_id} resuelto")
                    return solution

                elif result_data['error_text'] == 'CAPCHA_NOT_READY':
                    # Aún procesando
                    await asyncio.sleep(3)
                    continue

                else:
                    # Error
                    raise Exception(f"Error obteniendo solución: {result_data.get('error_text', 'Unknown error')}")

            except Exception as e:
                logger.warning(f"⚠️ Error esperando solución: {e}")
                await asyncio.sleep(3)

        raise Exception(f"Timeout esperando solución del captcha {captcha_id}")

    def get_balance(self) -> float:
        """Obtener balance de la cuenta"""

        try:
            response = self.session.get(
                f"{self.base_url}/res.php",
                params={
                    'key': self.api_key,
                    'action': 'getbalance'
                }
            )

            balance = float(response.text)
            return balance

        except Exception as e:
            logger.error(f"❌ Error obteniendo balance: {e}")
            return 0.0

    async def solve_captcha_auto(self, task: CaptchaTask) -> CaptchaResult:
        """Resolver captcha automáticamente según el tipo"""

        if not self.is_available():
            raise Exception("2Captcha API key no configurada")

        if task.captcha_type == "recaptcha_v2":
            return await self.solve_recaptcha_v2(task.site_key, task.page_url)

        elif task.captcha_type == "recaptcha_v3":
            return await self.solve_recaptcha_v3(
                task.site_key,
                task.page_url,
                task.action or "submit",
                task.min_score or 0.3
            )

        elif task.captcha_type == "hcaptcha":
            return await self.solve_hcaptcha(task.site_key, task.page_url)

        elif task.captcha_type == "image":
            return await self.solve_image_captcha(task.image_path, task.image_base64)

        else:
            raise Exception(f"Tipo de captcha no soportado: {task.captcha_type}")

class CaptchaDetector:
    """Detector automático de captchas en páginas web"""

    def __init__(self):
        self.selectors = {
            'recaptcha_v2': [
                'iframe[src*="recaptcha"]',
                '.g-recaptcha',
                '#recaptcha',
                '[data-sitekey]'
            ],
            'recaptcha_v3': [
                'script[src*="recaptcha/api.js"]',
                'script:contains("grecaptcha.execute")'
            ],
            'hcaptcha': [
                'iframe[src*="hcaptcha"]',
                '.h-captcha',
                '[data-sitekey][data-theme]'
            ],
            'image': [
                'img[src*="captcha"]',
                '.captcha-image',
                'input[name*="captcha"]'
            ]
        }

    def detect_captcha_in_page(self, driver) -> Optional[CaptchaTask]:
        """Detectar captcha en la página actual"""

        try:
            from selenium.webdriver.common.by import By
            from selenium.common.exceptions import NoSuchElementException

            current_url = driver.current_url

            # Detectar reCAPTCHA v2
            for selector in self.selectors['recaptcha_v2']:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    site_key = element.get_attribute('data-sitekey')
                    if site_key:
                        logger.info(f"🔍 reCAPTCHA v2 detectado: {site_key}")
                        return CaptchaTask(
                            captcha_type="recaptcha_v2",
                            site_key=site_key,
                            page_url=current_url
                        )
                except NoSuchElementException:
                    continue

            # Detectar hCaptcha
            for selector in self.selectors['hcaptcha']:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    site_key = element.get_attribute('data-sitekey')
                    if site_key:
                        logger.info(f"🔍 hCaptcha detectado: {site_key}")
                        return CaptchaTask(
                            captcha_type="hcaptcha",
                            site_key=site_key,
                            page_url=current_url
                        )
                except NoSuchElementException:
                    continue

            # Detectar reCAPTCHA v3 (más complejo, revisar scripts)
            try:
                scripts = driver.find_elements(By.TAG_NAME, 'script')
                for script in scripts:
                    src = script.get_attribute('src') or ""
                    if 'recaptcha/api.js' in src:
                        # Buscar site key en el DOM
                        page_source = driver.page_source
                        import re
                        site_key_match = re.search(r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)', page_source)
                        if site_key_match:
                            site_key = site_key_match.group(1)
                            logger.info(f"🔍 reCAPTCHA v3 detectado: {site_key}")
                            return CaptchaTask(
                                captcha_type="recaptcha_v3",
                                site_key=site_key,
                                page_url=current_url
                            )
            except Exception:
                pass

            # Detectar image captcha
            for selector in self.selectors['image']:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        logger.info(f"🔍 Image captcha detectado")
                        return CaptchaTask(captcha_type="image")
                except NoSuchElementException:
                    continue

            return None

        except Exception as e:
            logger.error(f"❌ Error detectando captcha: {e}")
            return None

# Funciones de conveniencia
def create_captcha_solver(api_key: str = None) -> TwoCaptchaSolver:
    """Factory para crear solver de captcha"""
    return TwoCaptchaSolver(api_key)

def create_captcha_detector() -> CaptchaDetector:
    """Factory para crear detector de captcha"""
    return CaptchaDetector()

async def auto_solve_page_captcha(driver, solver: TwoCaptchaSolver = None) -> Optional[CaptchaResult]:
    """Resolver automáticamente cualquier captcha en la página"""

    if not solver:
        solver = create_captcha_solver()

    if not solver.is_available():
        logger.warning("⚠️ 2Captcha no disponible")
        return None

    detector = create_captcha_detector()
    captcha_task = detector.detect_captcha_in_page(driver)

    if not captcha_task:
        return None

    try:
        result = await solver.solve_captcha_auto(captcha_task)
        logger.info(f"✅ Captcha resuelto automáticamente: {result.captcha_type}")
        return result

    except Exception as e:
        logger.error(f"❌ Error resolviendo captcha automáticamente: {e}")
        return None