"""
Framework de Automatización Robusta para Portales de Facturación

Implementa el checklist técnico de 10 puntos para navegación inteligente,
con fallbacks, logs detallados y integración LLM.

Sigue los principios:
- Detectar múltiples rutas (header, hero, footer)
- Validar visibilidad antes de click
- Manejar pestañas y redirecciones
- Política de fallback ordenada
- Logs y screenshots paso a paso
- Integración LLM para decisiones
- Manejo robusto de errores
- Extensibilidad modular
- Seguridad anti-loops
- Feedback visual completo
"""

import logging
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementNotInteractableException,
    StaleElementReferenceException
)

# Verificar disponibilidad de Claude
try:
    from core.claude_dom_analyzer import create_claude_analyzer
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

# Importar persistencia
try:
    from .automation_persistence import AutomationPersistence
    PERSISTENCE_AVAILABLE = True
except ImportError:
    PERSISTENCE_AVAILABLE = False

logger = logging.getLogger(__name__)

class ActionType(Enum):
    """Tipos de acciones de automatización"""
    SEARCH_ELEMENTS = "search_elements"
    CLICK_HEADER = "click_header"
    CLICK_HERO = "click_hero"
    CLICK_FOOTER = "click_footer"
    VALIDATE_VISIBILITY = "validate_visibility"
    HANDLE_TAB = "handle_tab"
    WAIT_DYNAMIC = "wait_dynamic"
    LLM_DECISION = "llm_decision"
    FALLBACK = "fallback"
    SCREENSHOT = "screenshot"

class ResultStatus(Enum):
    """Estados de resultado de acciones"""
    SUCCESS = "success"
    FAILED = "failed"
    NOT_VISIBLE = "not_visible"
    NOT_FOUND = "not_found"
    ERROR = "error"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    REQUIRES_INTERVENTION = "requires_intervention"

@dataclass
class AutomationStep:
    """Registro de un paso de automatización"""
    step_number: int
    action_type: ActionType
    selector: str
    description: str
    result: ResultStatus
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    timing_ms: int = 0
    llm_reasoning: Optional[str] = None
    fallback_used: bool = False
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class ElementRoute:
    """Definición de una ruta para encontrar elementos"""
    name: str
    priority: int
    selectors: List[str]
    description: str
    is_dynamic: bool = False
    requires_scroll: bool = False

class RobustAutomationEngine:
    """
    Motor de automatización robusta siguiendo el checklist técnico
    """

    def __init__(self, driver: webdriver.Chrome, ticket_id: int):
        self.driver = driver
        self.ticket_id = ticket_id
        self.wait = WebDriverWait(driver, 30)
        self.short_wait = WebDriverWait(driver, 5)

        # Configuración
        self.max_retries = 3
        self.retry_delay_base = 2  # segundos
        self.screenshot_dir = "static/automation_screenshots"

        # Estado de la sesión
        self.steps: List[AutomationStep] = []
        self.current_step = 0
        self.original_window = None
        self.start_time = time.time()

        # Persistencia
        self.persistence = AutomationPersistence() if PERSISTENCE_AVAILABLE else None
        self.session_id = f"session_{ticket_id}_{int(time.time())}"
        self.job_id = None

        # Rutas de búsqueda ordenadas por prioridad
        self.element_routes = [
            ElementRoute(
                name="header",
                priority=1,
                selectors=[
                    "nav a[href*='factura']",
                    "header a[href*='factura']",
                    ".navbar a[href*='factura']",
                    "nav a[href*='billing']",
                    ".menu a[contains(text(), 'Factura')]"
                ],
                description="Enlaces en navegación principal"
            ),
            ElementRoute(
                name="hero",
                priority=2,
                selectors=[
                    ".hero a.btn",
                    ".banner a[href*='factura']",
                    "//a[contains(text(),'Click Aquí')]",
                    ".carousel a.btn",
                    ".hero-section a"
                ],
                description="Botones en área hero/banner",
                is_dynamic=True
            ),
            ElementRoute(
                name="footer",
                priority=3,
                selectors=[
                    "footer a[href*='factura']",
                    ".footer a[href*='billing']",
                    "footer a[contains(text(), 'Factura')]"
                ],
                description="Enlaces en footer"
            )
        ]

        # Crear directorio de screenshots
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.original_window = self.driver.current_window_handle

    def _serialize_steps_for_json(self) -> List[Dict[str, Any]]:
        """Convertir steps a formato JSON serializable"""
        serialized_steps = []
        for step in self.steps:
            step_dict = asdict(step)
            # Convertir enums a strings
            step_dict['action_type'] = step_dict['action_type'].value if hasattr(step_dict['action_type'], 'value') else str(step_dict['action_type'])
            step_dict['result'] = step_dict['result'].value if hasattr(step_dict['result'], 'value') else str(step_dict['result'])
            serialized_steps.append(step_dict)
        return serialized_steps

    def log_step(self, action_type: ActionType, selector: str, description: str,
                result: ResultStatus, **kwargs) -> AutomationStep:
        """Registrar paso de automatización con evidencia"""

        self.current_step += 1

        # Tomar screenshot
        screenshot_path = None
        try:
            screenshot_filename = f"step_{self.current_step}_{action_type.value}_{int(time.time())}.png"
            screenshot_path = os.path.join(self.screenshot_dir, screenshot_filename)
            self.driver.save_screenshot(screenshot_path)
        except Exception as e:
            logger.warning(f"No se pudo tomar screenshot: {e}")

        step = AutomationStep(
            step_number=self.current_step,
            action_type=action_type,
            selector=selector,
            description=description,
            result=result,
            screenshot_path=screenshot_path,
            timing_ms=int((time.time() - self.start_time) * 1000),
            **kwargs
        )

        self.steps.append(step)

        # Persistir en DB si está disponible
        if self.persistence and self.job_id:
            try:
                step_dict = asdict(step)
                # Convertir enums a strings para JSON serialization
                step_dict['action_type'] = step_dict['action_type'].value if hasattr(step_dict['action_type'], 'value') else str(step_dict['action_type'])
                step_dict['result'] = step_dict['result'].value if hasattr(step_dict['result'], 'value') else str(step_dict['result'])
                step_dict['url'] = self.driver.current_url
                self.persistence.save_automation_step(self.job_id, self.session_id, step_dict)

                # Guardar screenshot si existe
                if step.screenshot_path:
                    screenshot_data = {
                        'step_number': self.current_step,
                        'screenshot_path': step.screenshot_path,
                        'step_result': result.value,
                        'step_name': f"{action_type.value}_{self.current_step}",
                        'url': self.driver.current_url,
                        'window_title': self.driver.title,
                        'company_id': 'default'
                    }
                    self.persistence.save_screenshot(self.job_id, self.session_id, screenshot_data)

            except Exception as e:
                logger.warning(f"Error persistiendo step en DB: {e}")

        # Log para debugging
        logger.info(f"Step {self.current_step}: {action_type.value} - {result.value}")
        logger.info(f"  Selector: {selector}")
        logger.info(f"  Description: {description}")
        if step.error_message:
            logger.error(f"  Error: {step.error_message}")
        if step.llm_reasoning:
            logger.info(f"  LLM Reasoning: {step.llm_reasoning}")

        return step

    def find_elements_with_validation(self, route: ElementRoute) -> List[Any]:
        """
        Checklist 1: Búsqueda de Elementos
        - Buscar en orden de prioridad
        - Validar existencia en DOM
        - Confirmar visibilidad y clickeabilidad
        """
        found_elements = []

        for selector in route.selectors:
            try:
                # Buscar elementos
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                # Validar cada elemento encontrado
                for element in elements:
                    if self.validate_element_interactability(element, selector):
                        found_elements.append((element, selector))

            except Exception as e:
                logger.debug(f"Error buscando selector {selector}: {e}")
                continue

        return found_elements

    def validate_element_interactability(self, element, selector: str) -> bool:
        """
        Checklist 2: Visibilidad y Condiciones
        - Elemento visible, interactuable y no bloqueado
        - Validaciones Selenium antes de click
        """
        try:
            # Validar que existe y está en DOM
            if not element:
                return False

            # Validar visibilidad
            if not element.is_displayed():
                self.log_step(
                    ActionType.VALIDATE_VISIBILITY,
                    selector,
                    "Elemento no visible",
                    ResultStatus.NOT_VISIBLE
                )
                return False

            # Validar que es clickeable
            try:
                self.short_wait.until(EC.element_to_be_clickable(element))
            except TimeoutException:
                self.log_step(
                    ActionType.VALIDATE_VISIBILITY,
                    selector,
                    "Elemento no clickeable",
                    ResultStatus.NOT_VISIBLE
                )
                return False

            # Validaciones adicionales para elementos dinámicos
            if self.is_element_in_active_slide(element):
                return True
            elif self.is_element_blocked_by_modal(element):
                return False

            return True

        except StaleElementReferenceException:
            return False
        except Exception as e:
            logger.debug(f"Error validando elemento: {e}")
            return False

    def is_element_in_active_slide(self, element) -> bool:
        """Verificar si elemento está en slide activo de carousel"""
        try:
            # Buscar carousel parent
            carousel_parent = element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'carousel') or contains(@class, 'slider')]")
            if carousel_parent:
                # Verificar si está en slide activo
                active_slide = carousel_parent.find_element(By.CSS_SELECTOR, ".active, .current, .selected")
                return element in active_slide.find_elements(By.XPATH, ".//*")
            return True
        except:
            return True  # Si no es carousel, asumir que está activo

    def is_element_blocked_by_modal(self, element) -> bool:
        """Verificar si elemento está bloqueado por modal"""
        try:
            modals = self.driver.find_elements(By.CSS_SELECTOR, ".modal, .overlay, .popup")
            for modal in modals:
                if modal.is_displayed():
                    return True
            return False
        except:
            return False

    def handle_new_tab_if_needed(self, element, selector: str) -> bool:
        """
        Checklist 3: Manejo de Pestañas
        - Detectar target="_blank"
        - Cambiar a nueva ventana
        - Validar URL destino
        """
        try:
            # Verificar si abre nueva pestaña
            element.get_attribute("target")
            initial_handles = len(self.driver.window_handles)

            # Hacer click
            element.click()

            # Esperar un momento para que se abra la pestaña
            time.sleep(2)

            current_handles = len(self.driver.window_handles)

            if current_handles > initial_handles:
                # Nueva pestaña detectada
                new_window = self.driver.window_handles[-1]
                self.driver.switch_to.window(new_window)

                # Validar URL destino
                current_url = self.driver.current_url
                if self.validate_destination_url(current_url):
                    self.log_step(
                        ActionType.HANDLE_TAB,
                        selector,
                        f"Cambiado a nueva pestaña: {current_url}",
                        ResultStatus.SUCCESS
                    )
                    return True
                else:
                    # URL no válida, volver a ventana original
                    self.driver.close()
                    self.driver.switch_to.window(self.original_window)
                    self.log_step(
                        ActionType.HANDLE_TAB,
                        selector,
                        f"URL destino no válida: {current_url}",
                        ResultStatus.FAILED
                    )
                    return False
            else:
                # No hubo nueva pestaña, validar URL actual
                current_url = self.driver.current_url
                return self.validate_destination_url(current_url)

        except Exception as e:
            self.log_step(
                ActionType.HANDLE_TAB,
                selector,
                f"Error manejando pestaña: {str(e)}",
                ResultStatus.ERROR,
                error_message=str(e)
            )
            return False

    def validate_destination_url(self, url: str) -> bool:
        """Validar que la URL contiene palabras clave de facturación"""
        keywords = ["factura", "billing", "invoice", "litromil", "cfdi"]
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in keywords)

    def attempt_click_with_fallback(self, route: ElementRoute) -> bool:
        """
        Checklist 4: Política de Fallback
        - Intentos ordenados por prioridad
        - Máximo 3 reintentos por ruta
        - Escalación a intervención manual
        """

        self.log_step(
            ActionType.SEARCH_ELEMENTS,
            f"route:{route.name}",
            f"Buscando elementos en {route.description}",
            ResultStatus.SUCCESS
        )

        # Buscar elementos válidos en esta ruta
        valid_elements = self.find_elements_with_validation(route)

        if not valid_elements:
            self.log_step(
                ActionType.SEARCH_ELEMENTS,
                f"route:{route.name}",
                f"No se encontraron elementos válidos en {route.name}",
                ResultStatus.NOT_FOUND
            )
            return False

        # Intentar click en cada elemento válido
        for element, selector in valid_elements:
            success = self.retry_click_with_backoff(element, selector, route)
            if success:
                return True

        return False

    def retry_click_with_backoff(self, element, selector: str, route: ElementRoute) -> bool:
        """
        Checklist 6: Manejo de Errores
        - Reintentar máx. 3 veces
        - Backoff exponencial entre intentos
        - Cambiar de ruta si falla
        """

        for attempt in range(self.max_retries):
            try:
                # Re-validar elemento antes de click (puede haber cambiado)
                if not self.validate_element_interactability(element, selector):
                    break

                action_type = getattr(ActionType, f"CLICK_{route.name.upper()}")

                # Intentar click
                success = self.handle_new_tab_if_needed(element, selector)

                if success:
                    self.log_step(
                        action_type,
                        selector,
                        f"Click exitoso en {route.name} (intento {attempt + 1})",
                        ResultStatus.SUCCESS,
                        fallback_used=(attempt > 0)
                    )
                    return True
                else:
                    raise Exception("Click falló - URL destino no válida")

            except ElementNotInteractableException:
                self.log_step(
                    action_type,
                    selector,
                    f"Elemento no interactuable (intento {attempt + 1})",
                    ResultStatus.NOT_VISIBLE
                )
                break  # No tiene sentido reintentar si no es interactuable

            except Exception as e:
                wait_time = self.retry_delay_base * (2 ** attempt)

                self.log_step(
                    action_type,
                    selector,
                    f"Error en click (intento {attempt + 1}): {str(e)}",
                    ResultStatus.ERROR,
                    error_message=str(e)
                )

                if attempt < self.max_retries - 1:
                    # Esperar antes del siguiente intento
                    self.log_step(
                        ActionType.WAIT_DYNAMIC,
                        "",
                        f"Esperando {wait_time}s antes del siguiente intento",
                        ResultStatus.SUCCESS
                    )
                    time.sleep(wait_time)

                    # Re-encontrar elemento (puede haber cambiado por dinámico)
                    try:
                        if selector.startswith("//"):
                            element = self.driver.find_element(By.XPATH, selector)
                        else:
                            element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    except:
                        break  # Elemento desapareció

        return False

    async def get_llm_recommendation(self, page_source: str) -> Dict[str, Any]:
        """
        Checklist 7: Integración con LLM REAL
        - Analizar DOM completo de forma agnóstica
        - Detectar CTAs e inputs automáticamente
        - Navegar sin conocer el portal específico
        """

        try:
            # Obtener snippet relevante del DOM (elementos interactivos)
            dom_snippet = self._extract_relevant_dom_elements()

            prompt = self._build_intelligent_navigation_prompt(dom_snippet, page_source)

            # Llamada REAL al LLM
            if CLAUDE_AVAILABLE:
                llm_response = await self._call_claude_for_navigation(prompt)
            else:
                # Fallback a análisis heurístico inteligente
                llm_response = self._analyze_dom_heuristically(dom_snippet)

            self.log_step(
                ActionType.LLM_DECISION,
                llm_response.get("suggested_selector", ""),
                f"LLM análisis: {llm_response.get('intent_detected', 'unknown')}",
                ResultStatus.SUCCESS,
                llm_reasoning=llm_response.get("reasoning", "")
            )

            return llm_response

        except Exception as e:
            self.log_step(
                ActionType.LLM_DECISION,
                "",
                f"Error en análisis LLM: {str(e)}",
                ResultStatus.ERROR,
                error_message=str(e)
            )
            return None

    def _extract_relevant_dom_elements(self) -> Dict[str, List[Dict]]:
        """Extraer solo elementos relevantes para facturación/billing"""

        relevant_elements = {
            "potential_ctas": [],
            "forms": [],
            "inputs": [],
            "navigation": [],
            "text_content": []
        }

        try:
            # 1. Buscar CTAs (botones, enlaces) relacionados con facturación
            factura_keywords = [
                "factura", "billing", "invoice", "cfdi", "solicitar",
                "generar", "descargar", "click aquí", "obtener", "emitir"
            ]

            # Buscar enlaces con texto relevante
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links[:20]:  # Limitar a primeros 20
                try:
                    text = link.get_attribute("textContent").strip().lower()
                    href = link.get_attribute("href") or ""

                    if any(keyword in text or keyword in href.lower() for keyword in factura_keywords):
                        relevant_elements["potential_ctas"].append({
                            "tag": "a",
                            "text": text[:100],
                            "href": href,
                            "selector": self._generate_smart_selector(link),
                            "visible": link.is_displayed(),
                            "confidence": self._calculate_relevance_score(text, href)
                        })
                except:
                    continue

            # Buscar botones con texto relevante
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in buttons[:15]:  # Limitar a primeros 15
                try:
                    text = button.get_attribute("textContent").strip().lower()

                    if any(keyword in text for keyword in factura_keywords):
                        relevant_elements["potential_ctas"].append({
                            "tag": "button",
                            "text": text[:100],
                            "selector": self._generate_smart_selector(button),
                            "visible": button.is_displayed(),
                            "confidence": self._calculate_relevance_score(text, "")
                        })
                except:
                    continue

            # 2. Detectar formularios
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            for i, form in enumerate(forms[:5]):  # Máximo 5 formularios
                try:
                    inputs = form.find_elements(By.TAG_NAME, "input")
                    relevant_elements["forms"].append({
                        "index": i,
                        "action": form.get_attribute("action") or "",
                        "method": form.get_attribute("method") or "get",
                        "inputs_count": len(inputs),
                        "selector": f"form:nth-of-type({i+1})"
                    })
                except:
                    continue

            # 3. Inputs independientes (fuera de formularios)
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for input_elem in inputs[:10]:  # Máximo 10 inputs
                try:
                    input_type = input_elem.get_attribute("type") or "text"
                    placeholder = input_elem.get_attribute("placeholder") or ""
                    name = input_elem.get_attribute("name") or ""

                    relevant_elements["inputs"].append({
                        "type": input_type,
                        "placeholder": placeholder[:50],
                        "name": name,
                        "selector": self._generate_smart_selector(input_elem),
                        "visible": input_elem.is_displayed()
                    })
                except:
                    continue

            # 4. Navegación principal
            nav_elements = self.driver.find_elements(By.CSS_SELECTOR, "nav, header, .navbar, .menu")
            for nav in nav_elements[:3]:
                try:
                    text_content = nav.get_attribute("textContent")[:200]
                    relevant_elements["navigation"].append({
                        "text": text_content,
                        "tag": nav.tag_name,
                        "selector": self._generate_smart_selector(nav)
                    })
                except:
                    continue

        except Exception as e:
            logger.error(f"Error extrayendo elementos DOM: {e}")

        return relevant_elements

    def _generate_smart_selector(self, element) -> str:
        """Generar selector inteligente para un elemento"""
        try:
            # Prioridad: id > class única > xpath relativo
            element_id = element.get_attribute("id")
            if element_id:
                return f"#{element_id}"

            class_name = element.get_attribute("class")
            if class_name and len(class_name.split()) == 1:
                return f".{class_name}"

            # Fallback a XPath relativo simple
            tag = element.tag_name
            parent = element.find_element(By.XPATH, "..")
            siblings = parent.find_elements(By.TAG_NAME, tag)
            index = siblings.index(element) + 1

            return f"{tag}:nth-of-type({index})"

        except:
            return f"{element.tag_name}"

    def _calculate_relevance_score(self, text: str, href: str) -> float:
        """Calcular score de relevancia para facturación"""
        score = 0.0

        # Palabras clave principales
        primary_keywords = ["factura", "cfdi", "billing", "invoice"]
        secondary_keywords = ["solicitar", "generar", "descargar", "obtener", "emitir"]

        text_lower = text.lower()
        href_lower = href.lower()

        # Score por palabras clave primarias
        for keyword in primary_keywords:
            if keyword in text_lower:
                score += 0.4
            if keyword in href_lower:
                score += 0.3

        # Score por palabras clave secundarias
        for keyword in secondary_keywords:
            if keyword in text_lower:
                score += 0.2

        # Bonificación por posición/contexto
        if "click" in text_lower and ("aquí" in text_lower or "here" in text_lower):
            score += 0.3

        return min(score, 1.0)

    def _build_intelligent_navigation_prompt(self, dom_elements: Dict, page_source: str) -> str:
        """Construir prompt inteligente para LLM"""

        current_url = self.driver.current_url
        page_title = self.driver.title

        return f"""
Eres un experto en automatización web. Analiza este portal web para encontrar cómo acceder a facturación/billing.

CONTEXTO:
- URL: {current_url}
- Título: {page_title}
- Objetivo: Encontrar ruta para solicitar/generar facturas

ELEMENTOS DETECTADOS:
CTAs Potenciales: {dom_elements.get('potential_ctas', [])}
Formularios: {dom_elements.get('forms', [])}
Inputs: {dom_elements.get('inputs', [])}
Navegación: {dom_elements.get('navigation', [])}

INSTRUCCIONES:
1. Identifica la MEJOR estrategia para llegar a facturación
2. Considera elementos visibles y accesibles
3. Prioriza elementos estables (no dinámicos)
4. Detecta si hay formularios de facturación en la página actual

Responde en JSON:
{{
    "intent_detected": "navigation_needed|form_present|unclear",
    "best_strategy": "click_cta|fill_form|navigate_menu",
    "recommended_selector": "selector CSS más confiable",
    "confidence": 0.0-1.0,
    "reasoning": "explicación detallada",
    "alternative_selectors": ["backup1", "backup2"],
    "form_detected": true/false,
    "risks": ["carousel", "modal", "dynamic_content"],
    "next_steps": ["paso1", "paso2", "paso3"]
}}
"""

    async def _call_claude_for_navigation(self, prompt: str) -> Dict[str, Any]:
        """Llamada a Claude para análisis de navegación"""

        try:
            analyzer = create_claude_analyzer()

            if not analyzer.is_available():
                logger.warning("⚠️ Claude no disponible, usando análisis heurístico")
                return self._analyze_dom_heuristically({})

            # Claude espera prompts más específicos, adaptamos
            claude_prompt = f"""
{prompt}

Por favor responde SOLO en JSON válido. Si no puedes generar JSON válido, responde con análisis heurístico.
"""

            response = await analyzer._call_claude_api(claude_prompt)

            try:
                import json
                llm_result = json.loads(response)
                return llm_result
            except json.JSONDecodeError as e:
                logger.warning(f"Claude response no es JSON válido: {response[:200]}")
                return self._analyze_dom_heuristically({})

        except Exception as e:
            logger.error(f"Error en llamada Claude: {e}")
            return self._analyze_dom_heuristically({})

    def _analyze_dom_heuristically(self, dom_elements: Dict) -> Dict[str, Any]:
        """Análisis heurístico del DOM como fallback cuando LLM no está disponible"""

        try:
            # Análisis básico usando las reglas del checklist
            ctas = dom_elements.get('potential_ctas', [])
            forms = dom_elements.get('forms', [])

            if ctas:
                # Ordenar por score de relevancia
                best_cta = max(ctas, key=lambda x: x.get('confidence', 0))

                return {
                    "intent_detected": "navigation_needed",
                    "best_strategy": "click_cta",
                    "recommended_selector": best_cta['selector'],
                    "confidence": best_cta.get('confidence', 0.5),
                    "reasoning": f"Análisis heurístico: CTA con mayor relevancia '{best_cta['text'][:50]}'",
                    "alternative_selectors": [cta['selector'] for cta in ctas[1:3]],
                    "form_detected": len(forms) > 0,
                    "risks": [],
                    "next_steps": ["click_element", "wait_for_page_load", "analyze_new_content"]
                }

            elif forms:
                # Si hay formularios pero no CTAs, podríamos estar en página de facturación
                return {
                    "intent_detected": "form_present",
                    "best_strategy": "fill_form",
                    "recommended_selector": forms[0]['selector'],
                    "confidence": 0.7,
                    "reasoning": "Análisis heurístico: Formulario detectado, posible página de facturación",
                    "alternative_selectors": [],
                    "form_detected": True,
                    "risks": [],
                    "next_steps": ["analyze_form_fields", "extract_ticket_data", "fill_and_submit"]
                }

            else:
                return {
                    "intent_detected": "unclear",
                    "best_strategy": "navigate_menu",
                    "recommended_selector": "",
                    "confidence": 0.2,
                    "reasoning": "Análisis heurístico: No se encontraron elementos obvios de facturación",
                    "alternative_selectors": [],
                    "form_detected": False,
                    "risks": ["unclear_navigation"],
                    "next_steps": ["search_in_menu", "look_for_hidden_elements", "try_common_paths"]
                }

        except Exception as e:
            logger.error(f"Error en análisis heurístico: {e}")
            return {
                "intent_detected": "unclear",
                "best_strategy": "navigate_menu",
                "recommended_selector": "",
                "confidence": 0.1,
                "reasoning": f"Error en análisis: {str(e)}",
                "alternative_selectors": [],
                "form_detected": False,
                "risks": ["analysis_failed"],
                "next_steps": ["manual_intervention_required"]
            }

            return llm_response

        except Exception as e:
            self.log_step(
                ActionType.LLM_DECISION,
                "",
                f"Error en consulta LLM: {str(e)}",
                ResultStatus.ERROR,
                error_message=str(e)
            )
            return None

    async def classify_urls_with_llm(self, urls: List[str]) -> Dict[str, Any]:
        """Clasificar URLs por probabilidad de ser portal de facturación usando LLM"""

        if len(urls) <= 1:
            return {"primary_url": urls[0] if urls else None, "alternatives": [], "reasoning": "Solo una URL disponible"}

        try:
            prompt = f"""
Analiza estas URLs y clasifícalas por probabilidad de ser un portal de facturación/CFDI:

URLs encontradas:
{chr(10).join([f"- {url}" for url in urls])}

Responde en JSON con este formato:
{{
    "primary_url": "la URL más probable para facturación",
    "alternatives": ["otras URLs en orden de probabilidad"],
    "reasoning": "explicación corta de por qué elegiste la principal",
    "confidence": 0.85
}}

Considera: palabras como 'factura', 'cfdi', 'billing', 'invoice', 'portal', dominios principales vs subdomains, paths que sugieren funcionalidad.
"""

            llm_response = await self._call_claude_for_navigation(prompt)

            if llm_response and "primary_url" in llm_response:
                return llm_response
            else:
                # Fallback heurístico
                return self._classify_urls_heuristically(urls)

        except Exception as e:
            logger.warning(f"Error en clasificación LLM de URLs: {e}")
            return self._classify_urls_heuristically(urls)

    def _classify_urls_heuristically(self, urls: List[str]) -> Dict[str, Any]:
        """Clasificación heurística como fallback"""

        # Scoring heurístico
        scored_urls = []
        for url in urls:
            score = 0
            url_lower = url.lower()

            # Palabras clave positivas
            positive_keywords = ['factura', 'cfdi', 'billing', 'invoice', 'portal', 'facturacion']
            for keyword in positive_keywords:
                if keyword in url_lower:
                    score += 2

            # Palabras clave negativas
            negative_keywords = ['app-descarga', 'download', 'mobile', 'app', 'about', 'contact']
            for keyword in negative_keywords:
                if keyword in url_lower:
                    score -= 3

            # Preferir HTTPS
            if url.startswith('https'):
                score += 1

            # Preferir dominios principales vs puertos raros
            if ':8088' in url or ':8080' in url:
                score -= 1

            scored_urls.append((url, score))

        # Ordenar por score
        scored_urls.sort(key=lambda x: x[1], reverse=True)

        primary = scored_urls[0][0]
        alternatives = [url for url, _ in scored_urls[1:]]

        return {
            "primary_url": primary,
            "alternatives": alternatives,
            "reasoning": f"Análisis heurístico: {primary} tiene mayor score de facturación",
            "confidence": 0.7
        }

    async def _attempt_single_url_navigation(self, url: str) -> Dict[str, Any]:
        """Intentar navegación en una sola URL y determinar si es exitosa"""

        attempt_result = {
            "url": url,
            "success": False,
            "reason": "",
            "has_form_fields": False,
            "has_invoicing_elements": False,
            "error": None
        }

        try:
            # Navegar a URL
            self.driver.get(url)
            self.log_step(
                ActionType.SEARCH_ELEMENTS,
                url,
                f"Navegando a portal: {url}",
                ResultStatus.SUCCESS
            )

            # Esperar carga inicial
            time.sleep(3)

            # Detectar elementos de facturación
            form_elements = self.driver.find_elements(By.TAG_NAME, "form")
            rfc_fields = self.driver.find_elements(By.XPATH, "//*[contains(@placeholder, 'RFC') or contains(@name, 'rfc') or contains(@id, 'rfc')]")
            invoice_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'factura') or contains(text(), 'CFDI') or contains(text(), 'billing')]")

            attempt_result["has_form_fields"] = len(form_elements) > 0
            attempt_result["has_invoicing_elements"] = len(rfc_fields) > 0 or len(invoice_buttons) > 0

            if attempt_result["has_invoicing_elements"]:
                # Parece ser un portal de facturación, intentar navegación completa
                navigation_result = await self._perform_full_navigation()
                if navigation_result["success"]:
                    attempt_result["success"] = True
                    attempt_result["reason"] = f"Navegación exitosa: {navigation_result.get('route_used', 'unknown')}"
                    attempt_result["navigation_details"] = navigation_result
                else:
                    attempt_result["reason"] = f"Portal de facturación detectado pero falló: {navigation_result.get('error', 'unknown')}"
            else:
                attempt_result["reason"] = "No se detectaron elementos de facturación (RFC, formularios, botones CFDI)"

        except Exception as e:
            attempt_result["error"] = str(e)
            attempt_result["reason"] = f"Error técnico: {str(e)}"

        return attempt_result

    async def _perform_full_navigation(self) -> Dict[str, Any]:
        """Realizar navegación completa usando las rutas del checklist"""

        try:
            # Intentar rutas en orden de prioridad (Checklist 4)
            for route in sorted(self.element_routes, key=lambda r: r.priority):

                success = self.attempt_click_with_fallback(route)

                if success:
                    result = {
                        "success": True,
                        "route_used": route.name,
                        "steps": self._serialize_steps_for_json(),
                        "total_time_ms": int((time.time() - self.start_time) * 1000),
                        "final_url": self.driver.current_url
                    }
                    return result

            # Si todas las rutas fallaron, consultar LLM
            llm_recommendation = await self.get_llm_recommendation(self.driver.page_source)

            if llm_recommendation and llm_recommendation.get("suggested_selector"):
                # Intentar sugerencia del LLM
                success = self.try_llm_suggestion(llm_recommendation)
                if success:
                    result = {
                        "success": True,
                        "route_used": "llm_suggestion",
                        "llm_recommendation": llm_recommendation,
                        "steps": self._serialize_steps_for_json(),
                        "total_time_ms": int((time.time() - self.start_time) * 1000),
                        "final_url": self.driver.current_url
                    }
                    return result

            # Todas las rutas fallaron
            return {
                "success": False,
                "error": "No se pudo encontrar ruta de facturación",
                "requires_human_intervention": True,
                "steps": self._serialize_steps_for_json(),
                "total_time_ms": int((time.time() - self.start_time) * 1000),
                "final_url": self.driver.current_url
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "steps": self._serialize_steps_for_json(),
                "total_time_ms": int((time.time() - self.start_time) * 1000)
            }

    async def navigate_to_invoicing_portal(self, url: str, alternative_urls: List[str] = None) -> Dict[str, Any]:
        """
        Método principal que implementa todo el checklist técnico + manejo múltiples URLs
        """

        # Tracking de intentos para reportes (inicializar primero)
        attempt_reports = []

        # Lista de URLs para intentar
        all_urls = [url]
        if alternative_urls:
            all_urls.extend(alternative_urls)

        # Clasificar URLs si hay múltiples
        url_classification = None
        if len(all_urls) > 1:
            url_classification = await self.classify_urls_with_llm(all_urls)
            # Reordenar URLs según clasificación LLM
            primary_url = url_classification.get("primary_url", url)
            alternatives = url_classification.get("alternatives", [])
            all_urls = [primary_url] + [u for u in alternatives if u != primary_url]

        try:
            # Crear job de automatización si persistencia está disponible
            if self.persistence:
                try:
                    job_data = {
                        'config': {
                            'urls': all_urls,
                            'classification': url_classification,
                            'session_id': self.session_id
                        },
                        'company_id': 'default'
                    }
                    self.job_id = self.persistence.create_automation_job(self.ticket_id, job_data)
                    logger.info(f"💾 Automation job {self.job_id} creado para ticket {self.ticket_id}")
                except Exception as e:
                    logger.warning(f"No se pudo crear job de automatización: {e}")

            # Intentar con cada URL en orden de prioridad
            for attempt_num, current_url in enumerate(all_urls, 1):
                logger.info(f"🌐 Intento {attempt_num}/{len(all_urls)}: {current_url}")

                # Intentar navegación en URL actual
                attempt_result = await self._attempt_single_url_navigation(current_url)
                attempt_reports.append(attempt_result)

                if attempt_result["success"]:
                    # Éxito en esta URL
                    final_result = attempt_result["navigation_details"]
                    final_result["url_attempts"] = attempt_reports
                    final_result["url_classification"] = url_classification

                    # Actualizar job como exitoso
                    if self.persistence and self.job_id:
                        self.persistence.update_automation_job_status(self.job_id, 'success', final_result)

                    return final_result

                logger.warning(f"❌ Intento {attempt_num} falló: {attempt_result['reason']}")

            # Todos los intentos fallaron - generar reporte detallado
            error_report = await self._generate_detailed_error_report(attempt_reports, url_classification)

            # Actualizar job como fallido
            if self.persistence and self.job_id:
                self.persistence.update_automation_job_status(self.job_id, 'requires_intervention', error_report)

            return error_report

        except Exception as e:
            # Error crítico en el proceso general
            self.log_step(
                ActionType.FALLBACK,
                "",
                f"Error crítico en sistema de múltiples URLs: {str(e)}",
                ResultStatus.ERROR,
                error_message=str(e)
            )

            error_result = {
                "success": False,
                "error": str(e),
                "steps": self._serialize_steps_for_json(),
                "total_time_ms": int((time.time() - self.start_time) * 1000),
                "url_attempts": attempt_reports
            }

            # Actualizar job como error
            if self.persistence and self.job_id:
                self.persistence.update_automation_job_status(self.job_id, 'error', error_result)

            return error_result

    async def _generate_detailed_error_report(self, attempt_reports: List[Dict], url_classification: Dict = None) -> Dict[str, Any]:
        """Generar reporte detallado de errores con explicación humana usando LLM"""

        try:
            # Preparar datos para el LLM
            attempts_summary = []
            for i, attempt in enumerate(attempt_reports, 1):
                attempts_summary.append({
                    "attempt": i,
                    "url": attempt["url"],
                    "reason": attempt["reason"],
                    "has_forms": attempt["has_form_fields"],
                    "has_invoice_elements": attempt["has_invoicing_elements"],
                    "error": attempt.get("error")
                })

            # Solicitar al LLM una explicación humana
            llm_prompt = f"""
Analiza estos intentos fallidos de automatización de facturación y genera una explicación clara para el usuario:

Clasificación inicial de URLs:
{url_classification.get('reasoning', 'No disponible') if url_classification else 'Solo una URL'}

Intentos realizados:
{chr(10).join([f"- Intento {a['attempt']}: {a['url']} → {a['reason']}" for a in attempts_summary])}

Responde en JSON con este formato:
{{
    "status": "error",
    "llm_summary": "Explicación clara y concisa de por qué falló el proceso",
    "recommended_action": "Qué debe hacer el usuario para resolver esto",
    "technical_details": "Detalles técnicos para el equipo de soporte"
}}

La explicación debe ser comprensible para un usuario no técnico.
"""

            llm_explanation = await self._call_claude_for_navigation(llm_prompt)

            if not llm_explanation:
                # Fallback heurístico
                llm_explanation = {
                    "llm_summary": "No se encontraron elementos de facturación en ninguna de las URLs probadas",
                    "recommended_action": "Verificar que las URLs del merchant sean correctas y contengan portales de facturación",
                    "technical_details": f"Se probaron {len(attempt_reports)} URLs sin encontrar formularios CFDI"
                }

        except Exception as e:
            # Si falla el LLM, generar explicación básica
            llm_explanation = {
                "llm_summary": f"Error en análisis automático. Se probaron {len(attempt_reports)} URLs sin éxito",
                "recommended_action": "Revisar manualmente las URLs del merchant",
                "technical_details": f"LLM error: {str(e)}"
            }

        # Construir reporte final
        error_report = {
            "success": False,
            "status": "error",
            "merchant": "Portal desconocido",
            "total_attempts": len(attempt_reports),
            "attempts": attempt_reports,
            "url_classification": url_classification,
            "llm_summary": llm_explanation.get("llm_summary", "Error desconocido"),
            "recommended_action": llm_explanation.get("recommended_action", "Contactar soporte"),
            "technical_details": llm_explanation.get("technical_details", "Sin detalles técnicos"),
            "steps": self._serialize_steps_for_json(),
            "total_time_ms": int((time.time() - self.start_time) * 1000),
            "requires_human_intervention": True,
            "timestamp": time.time()
        }

        return error_report

    def try_llm_suggestion(self, llm_recommendation: Dict[str, Any]) -> bool:
        """Intentar sugerencia del LLM inteligente con múltiples estrategias"""

        strategy = llm_recommendation.get("best_strategy", "click_cta")
        recommended_selector = llm_recommendation.get("recommended_selector", "")

        if strategy == "fill_form" and llm_recommendation.get("form_detected"):
            # Si el LLM detectó un formulario, intentar llenarlo directamente
            return self._try_form_filling_strategy(llm_recommendation)

        elif strategy == "click_cta" and recommended_selector:
            # Estrategia de click en CTA
            return self._try_cta_click_strategy(llm_recommendation)

        elif strategy == "navigate_menu":
            # Estrategia de navegación por menú
            return self._try_menu_navigation_strategy(llm_recommendation)

        else:
            self.log_step(
                ActionType.LLM_DECISION,
                recommended_selector,
                f"Estrategia desconocida: {strategy}",
                ResultStatus.FAILED
            )
            return False

    def _try_cta_click_strategy(self, llm_recommendation: Dict[str, Any]) -> bool:
        """Intentar click en CTA recomendado por LLM"""

        selector = llm_recommendation.get("recommended_selector", "")
        alternative_selectors = llm_recommendation.get("alternative_selectors", [])

        # Intentar selector principal
        for attempt_selector in [selector] + alternative_selectors:
            if not attempt_selector:
                continue

            try:
                if attempt_selector.startswith("//"):
                    element = self.driver.find_element(By.XPATH, attempt_selector)
                else:
                    element = self.driver.find_element(By.CSS_SELECTOR, attempt_selector)

                if self.validate_element_interactability(element, attempt_selector):
                    success = self.handle_new_tab_if_needed(element, attempt_selector)
                    if success:
                        self.log_step(
                            ActionType.LLM_DECISION,
                            attempt_selector,
                            f"LLM CTA exitoso: {llm_recommendation.get('reasoning', '')}",
                            ResultStatus.SUCCESS,
                            llm_reasoning=llm_recommendation.get("reasoning", "")
                        )
                        return True

            except Exception as e:
                self.log_step(
                    ActionType.LLM_DECISION,
                    attempt_selector,
                    f"CTA falló: {str(e)}",
                    ResultStatus.FAILED,
                    error_message=str(e)
                )

        return False

    def _try_form_filling_strategy(self, llm_recommendation: Dict[str, Any]) -> bool:
        """Estrategia para llenar formulario directamente"""

        try:
            # Si ya estamos en una página con formulario de facturación
            forms = self.driver.find_elements(By.TAG_NAME, "form")

            if forms:
                self.log_step(
                    ActionType.LLM_DECISION,
                    "form",
                    f"LLM detectó formulario presente: {llm_recommendation.get('reasoning', '')}",
                    ResultStatus.SUCCESS,
                    llm_reasoning=llm_recommendation.get("reasoning", "")
                )

                # TODO: Integrar aquí el llenado automático de formularios
                # Por ahora, marcar como éxito si encontramos formulario
                return True

            return False

        except Exception as e:
            self.log_step(
                ActionType.LLM_DECISION,
                "form",
                f"Error en estrategia de formulario: {str(e)}",
                ResultStatus.ERROR,
                error_message=str(e)
            )
            return False

    def _try_menu_navigation_strategy(self, llm_recommendation: Dict[str, Any]) -> bool:
        """Estrategia de navegación por menú cuando no hay CTAs obvios"""

        try:
            # Buscar elementos de navegación comunes
            nav_selectors = [
                "nav a", "header a", ".menu a", ".navbar a",
                "[role='navigation'] a", ".navigation a"
            ]

            for nav_selector in nav_selectors:
                try:
                    nav_links = self.driver.find_elements(By.CSS_SELECTOR, nav_selector)

                    for link in nav_links[:10]:  # Máximo 10 enlaces por selector
                        text = link.get_attribute("textContent").strip().lower()
                        link.get_attribute("href") or ""

                        # Buscar texto relevante
                        if any(keyword in text for keyword in ["factura", "billing", "servicio", "cliente"]):
                            if self.validate_element_interactability(link, nav_selector):
                                success = self.handle_new_tab_if_needed(link, nav_selector)
                                if success:
                                    self.log_step(
                                        ActionType.LLM_DECISION,
                                        nav_selector,
                                        f"Navegación por menú exitosa: {text[:50]}",
                                        ResultStatus.SUCCESS,
                                        llm_reasoning=f"Encontrado en navegación: {text}"
                                    )
                                    return True

                except Exception:
                    continue

            return False

        except Exception as e:
            self.log_step(
                ActionType.LLM_DECISION,
                "menu",
                f"Error en navegación por menú: {str(e)}",
                ResultStatus.ERROR,
                error_message=str(e)
            )
            return False

    def get_automation_summary(self) -> Dict[str, Any]:
        """
        Checklist 10: Viewer (Feedback al usuario)
        - Screenshots paso a paso
        - Logs de decisiones
        - Estado actual
        """

        total_steps = len(self.steps)
        successful_steps = len([s for s in self.steps if s.result == ResultStatus.SUCCESS])
        failed_steps = len([s for s in self.steps if s.result in [ResultStatus.FAILED, ResultStatus.ERROR]])

        return {
            "ticket_id": self.ticket_id,
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "success_rate": successful_steps / total_steps if total_steps > 0 else 0,
            "total_time_ms": int((time.time() - self.start_time) * 1000),
            "steps": [asdict(step) for step in self.steps],
            "routes_attempted": list(set(step.selector.split(":")[1] if ":" in step.selector else "unknown"
                                      for step in self.steps if step.action_type == ActionType.SEARCH_ELEMENTS)),
            "llm_decisions": [asdict(step) for step in self.steps if step.action_type == ActionType.LLM_DECISION],
            "screenshots": [step.screenshot_path for step in self.steps if step.screenshot_path],
            "final_status": self.steps[-1].result.value if self.steps else "not_started"
        }