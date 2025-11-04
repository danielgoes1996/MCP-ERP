"""
Sistema de Planificación IA para RPA - Cerebro Inteligente
Convierte análisis del DOM en planes de automatización ejecutables con Playwright.
Usa LLM para generar planes deterministas y seguros.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
import hashlib

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Tipos de acciones RPA disponibles"""
    NAVIGATE = "navigate"
    WAIT_FOR_ELEMENT = "wait_for_element"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    UPLOAD_FILE = "upload_file"
    WAIT_FOR_NAVIGATION = "wait_for_navigation"
    WAIT_TIME = "wait_time"
    SCROLL = "scroll"
    TAKE_SCREENSHOT = "take_screenshot"
    EXTRACT_TEXT = "extract_text"
    VALIDATE = "validate"
    CONDITIONAL = "conditional"


@dataclass
class RPAAction:
    """Acción individual de RPA"""
    action_type: ActionType
    selector: Optional[str] = None
    value: Optional[str] = None
    timeout: int = 30000  # ms
    description: str = ""

    # Parámetros específicos
    options: Dict[str, Any] = None

    # Validaciones
    expected_result: Optional[str] = None
    retry_count: int = 3

    def __post_init__(self):
        if self.options is None:
            self.options = {}


@dataclass
class RPAPlan:
    """Plan completo de automatización RPA"""
    plan_id: str
    merchant_name: str
    portal_url: str

    # Configuración del browser
    browser_config: Dict[str, Any]

    # Secuencia de acciones
    actions: List[RPAAction]

    # Datos de entrada esperados
    input_schema: Dict[str, str]

    # Validaciones finales
    success_validations: List[Dict[str, Any]]

    # Metadatos
    created_at: str
    confidence_score: float
    estimated_duration_seconds: int


class AIRPAPlanner:
    """
    Planificador IA que analiza portales web y genera planes de automatización.
    """

    def __init__(self):
        # Configuración de LLM
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = "gpt-4o-mini"  # Modelo para planificación

        # Templates de prompts
        self.system_prompt = self._load_system_prompt()

        # Cache de análisis de portales
        self._portal_cache = {}

        # Configuraciones de browser comunes
        self.browser_configs = {
            "default": {
                "headless": False,
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "timeout": 30000,
                "wait_for_load_state": "networkidle"
            },
            "mobile": {
                "headless": False,
                "viewport": {"width": 375, "height": 667},
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
                "timeout": 30000
            }
        }

    async def analyze_portal_and_create_plan(
        self,
        merchant_name: str,
        portal_url: str,
        ticket_data: Dict[str, Any],
        credentials: Dict[str, str],
        context: Optional[str] = None
    ) -> RPAPlan:
        """
        Analiza un portal de facturación y crea un plan de automatización.

        Args:
            merchant_name: Nombre del merchant
            portal_url: URL del portal
            ticket_data: Datos del ticket extraídos
            credentials: Credenciales para el portal
            context: Contexto adicional o instrucciones especiales

        Returns:
            Plan de automatización completo
        """

        logger.info(f"Creando plan RPA para {merchant_name} - {portal_url}")

        start_time = time.time()

        try:
            # 1. Analizar el portal (usar cache si existe)
            portal_analysis = await self._analyze_portal_structure(portal_url, merchant_name)

            # 2. Generar plan con IA
            plan = await self._generate_plan_with_ai(
                merchant_name=merchant_name,
                portal_url=portal_url,
                portal_analysis=portal_analysis,
                ticket_data=ticket_data,
                credentials=credentials,
                context=context
            )

            # 3. Validar y optimizar plan
            validated_plan = await self._validate_and_optimize_plan(plan)

            processing_time = time.time() - start_time
            logger.info(f"Plan RPA creado en {processing_time:.2f}s con {len(validated_plan.actions)} acciones")

            return validated_plan

        except Exception as e:
            logger.error(f"Error creando plan RPA: {e}")
            # Retornar plan de fallback
            return await self._create_fallback_plan(merchant_name, portal_url, ticket_data)

    async def _analyze_portal_structure(
        self,
        portal_url: str,
        merchant_name: str
    ) -> Dict[str, Any]:
        """
        Analiza la estructura del portal para entender el flujo de facturación.
        """

        # Verificar cache
        cache_key = hashlib.md5(f"{portal_url}-{merchant_name}".encode()).hexdigest()
        if cache_key in self._portal_cache:
            logger.info(f"Usando análisis cached para {merchant_name}")
            return self._portal_cache[cache_key]

        try:
            # Usar Playwright para análisis inicial
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Navegar al portal
                await page.goto(portal_url, wait_until="networkidle")

                # Extraer estructura básica
                analysis = {
                    "url": portal_url,
                    "title": await page.title(),
                    "forms": await self._extract_forms_info(page),
                    "inputs": await self._extract_inputs_info(page),
                    "buttons": await self._extract_buttons_info(page),
                    "navigation": await self._extract_navigation_info(page),
                    "meta_info": await self._extract_meta_info(page),
                    "screenshot_b64": await page.screenshot(type="png", encoding="base64")
                }

                await browser.close()

        except Exception as e:
            logger.warning(f"Error analizando portal con Playwright: {e}")

            # Fallback: análisis básico con requests
            analysis = await self._basic_portal_analysis(portal_url)

        # Guardar en cache
        self._portal_cache[cache_key] = analysis

        return analysis

    async def _extract_forms_info(self, page) -> List[Dict[str, Any]]:
        """Extraer información de formularios en la página"""

        forms = await page.query_selector_all("form")
        forms_info = []

        for i, form in enumerate(forms):
            form_info = {
                "index": i,
                "action": await form.get_attribute("action"),
                "method": await form.get_attribute("method") or "GET",
                "id": await form.get_attribute("id"),
                "class": await form.get_attribute("class"),
                "inputs": []
            }

            # Extraer inputs del formulario
            inputs = await form.query_selector_all("input, select, textarea")
            for input_el in inputs:
                input_info = {
                    "type": await input_el.get_attribute("type") or "text",
                    "name": await input_el.get_attribute("name"),
                    "id": await input_el.get_attribute("id"),
                    "placeholder": await input_el.get_attribute("placeholder"),
                    "required": await input_el.get_attribute("required") is not None,
                    "selector": await self._generate_selector_for_element(input_el)
                }
                form_info["inputs"].append(input_info)

            forms_info.append(form_info)

        return forms_info

    async def _extract_inputs_info(self, page) -> List[Dict[str, Any]]:
        """Extraer información de todos los inputs"""

        inputs = await page.query_selector_all("input, select, textarea")
        inputs_info = []

        for input_el in inputs:
            input_info = {
                "type": await input_el.get_attribute("type") or "text",
                "name": await input_el.get_attribute("name"),
                "id": await input_el.get_attribute("id"),
                "placeholder": await input_el.get_attribute("placeholder"),
                "label": await self._find_input_label(page, input_el),
                "selector": await self._generate_selector_for_element(input_el)
            }
            inputs_info.append(input_info)

        return inputs_info

    async def _extract_buttons_info(self, page) -> List[Dict[str, Any]]:
        """Extraer información de botones"""

        buttons = await page.query_selector_all("button, input[type='submit'], input[type='button'], a.btn")
        buttons_info = []

        for button in buttons:
            button_info = {
                "tag": await button.evaluate("el => el.tagName.toLowerCase()"),
                "text": await button.inner_text(),
                "type": await button.get_attribute("type"),
                "id": await button.get_attribute("id"),
                "class": await button.get_attribute("class"),
                "selector": await self._generate_selector_for_element(button)
            }
            buttons_info.append(button_info)

        return buttons_info

    async def _extract_navigation_info(self, page) -> Dict[str, Any]:
        """Extraer información de navegación"""

        return {
            "current_url": page.url,
            "links": await page.evaluate("""
                () => Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.innerText.trim(),
                    href: a.href,
                    id: a.id,
                    class: a.className
                })).slice(0, 20)
            """)
        }

    async def _extract_meta_info(self, page) -> Dict[str, Any]:
        """Extraer metadatos de la página"""

        return await page.evaluate("""
            () => ({
                title: document.title,
                description: document.querySelector('meta[name="description"]')?.content || '',
                keywords: document.querySelector('meta[name="keywords"]')?.content || '',
                viewport: document.querySelector('meta[name="viewport"]')?.content || '',
                charset: document.characterSet,
                lang: document.documentElement.lang || '',
                scripts_count: document.querySelectorAll('script').length,
                styles_count: document.querySelectorAll('link[rel="stylesheet"], style').length
            })
        """)

    async def _generate_selector_for_element(self, element) -> str:
        """Generar selector único para un elemento"""

        # Intentar diferentes estrategias para el selector
        element_id = await element.get_attribute("id")
        if element_id:
            return f"#{element_id}"

        element_name = await element.get_attribute("name")
        if element_name:
            return f"[name='{element_name}']"

        # Usar selector CSS más específico
        selector = await element.evaluate("""
            el => {
                if (el.id) return '#' + el.id;
                if (el.name) return '[name="' + el.name + '"]';
                if (el.className) {
                    const classes = el.className.split(' ').filter(c => c).slice(0, 2).join('.');
                    if (classes) return '.' + classes;
                }
                return el.tagName.toLowerCase();
            }
        """)

        return selector

    async def _find_input_label(self, page, input_el) -> Optional[str]:
        """Encontrar el label asociado a un input"""

        try:
            input_id = await input_el.get_attribute("id")
            if input_id:
                label = await page.query_selector(f"label[for='{input_id}']")
                if label:
                    return await label.inner_text()

            # Buscar label padre
            parent_label = await input_el.evaluate("""
                el => {
                    let parent = el.parentElement;
                    while (parent && parent.tagName.toLowerCase() !== 'label') {
                        parent = parent.parentElement;
                    }
                    return parent ? parent.innerText.trim() : null;
                }
            """)

            return parent_label

        except:
            return None

    async def _basic_portal_analysis(self, portal_url: str) -> Dict[str, Any]:
        """Análisis básico con requests como fallback"""

        try:
            import requests
            from bs4 import BeautifulSoup

            response = requests.get(portal_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')

            return {
                "url": portal_url,
                "title": soup.title.string if soup.title else "",
                "forms": len(soup.find_all("form")),
                "inputs": len(soup.find_all(["input", "select", "textarea"])),
                "buttons": len(soup.find_all(["button", "input[type='submit']"])),
                "analysis_method": "basic_requests"
            }

        except Exception as e:
            logger.error(f"Error en análisis básico: {e}")
            return {
                "url": portal_url,
                "error": str(e),
                "analysis_method": "failed"
            }

    async def _generate_plan_with_ai(
        self,
        merchant_name: str,
        portal_url: str,
        portal_analysis: Dict[str, Any],
        ticket_data: Dict[str, Any],
        credentials: Dict[str, str],
        context: Optional[str]
    ) -> RPAPlan:
        """
        Generar plan de automatización usando IA.
        """

        # Preparar prompt para el LLM
        user_prompt = self._build_planning_prompt(
            merchant_name=merchant_name,
            portal_url=portal_url,
            portal_analysis=portal_analysis,
            ticket_data=ticket_data,
            context=context
        )

        # Llamar al LLM
        if self.openai_api_key:
            ai_response = await self._call_openai_for_planning(user_prompt)
        else:
            # Fallback: usar plantilla predefinida
            ai_response = await self._generate_template_plan(merchant_name, portal_url, ticket_data)

        # Parsear respuesta del AI y crear plan
        plan = await self._parse_ai_response_to_plan(
            ai_response=ai_response,
            merchant_name=merchant_name,
            portal_url=portal_url,
            ticket_data=ticket_data
        )

        return plan

    def _build_planning_prompt(
        self,
        merchant_name: str,
        portal_url: str,
        portal_analysis: Dict[str, Any],
        ticket_data: Dict[str, Any],
        context: Optional[str]
    ) -> str:
        """Construir prompt para planificación con IA"""

        prompt = f"""
Eres un experto en automatización RPA para portales de facturación mexicanos.

TAREA: Crear un plan de automatización para facturar un ticket en el portal de {merchant_name}.

INFORMACIÓN DEL PORTAL:
- URL: {portal_url}
- Merchant: {merchant_name}
- Análisis del portal: {json.dumps(portal_analysis, indent=2)}

DATOS DEL TICKET:
{json.dumps(ticket_data, indent=2)}

CONTEXTO ADICIONAL:
{context or "Facturación estándar"}

INSTRUCCIONES:
1. Analiza la estructura del portal identificada
2. Crea una secuencia de acciones para:
   - Acceder al portal
   - Hacer login si es necesario
   - Navegar a la sección de facturación
   - Llenar el formulario con los datos del ticket
   - Completar el proceso de facturación
   - Descargar o capturar los archivos CFDI (XML/PDF)

3. Usa SOLO estos tipos de acciones: {[action.value for action in ActionType]}

4. Para cada acción especifica:
   - Selector CSS específico
   - Valor a ingresar (si aplica)
   - Timeout apropiado
   - Descripción clara

5. Incluye validaciones para verificar el éxito

RESPONDE EN FORMATO JSON con esta estructura:
{{
    "browser_config": {{"headless": false, "viewport": {{"width": 1920, "height": 1080}}}},
    "actions": [
        {{
            "action_type": "navigate",
            "value": "{portal_url}",
            "timeout": 30000,
            "description": "Navegar al portal de facturación"
        }},
        {{
            "action_type": "wait_for_element",
            "selector": "#username",
            "timeout": 10000,
            "description": "Esperar a que aparezca el campo de usuario"
        }}
        // ... más acciones
    ],
    "input_schema": {{
        "rfc": "RFC del receptor",
        "folio": "Folio del ticket",
        "fecha": "Fecha de compra",
        "total": "Total del ticket"
    }},
    "success_validations": [
        {{
            "type": "element_present",
            "selector": ".success-message",
            "description": "Verificar mensaje de éxito"
        }}
    ],
    "estimated_duration_seconds": 60,
    "confidence_score": 0.85
}}

IMPORTANTE:
- Usa selectores CSS específicos y únicos
- Incluye esperas apropiadas entre acciones
- Maneja posibles modals o popups
- Considera diferentes tipos de portales (SPA, tradicionales)
- Incluye capturas de pantalla en puntos clave
"""

        return prompt.strip()

    async def _call_openai_for_planning(self, user_prompt: str) -> Dict[str, Any]:
        """Llamar a OpenAI para generar plan"""

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.openai_api_key)

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Muy determinista para RPA
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            response_text = response.choices[0].message.content
            return json.loads(response_text)

        except Exception as e:
            logger.error(f"Error llamando OpenAI: {e}")
            raise

    async def _generate_template_plan(
        self,
        merchant_name: str,
        portal_url: str,
        ticket_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generar plan usando plantilla como fallback"""

        logger.info(f"Generando plan template para {merchant_name}")

        return {
            "browser_config": self.browser_configs["default"],
            "actions": [
                {
                    "action_type": "navigate",
                    "value": portal_url,
                    "timeout": 30000,
                    "description": f"Navegar al portal de {merchant_name}"
                },
                {
                    "action_type": "wait_time",
                    "value": "3000",
                    "description": "Esperar carga de página"
                },
                {
                    "action_type": "take_screenshot",
                    "description": "Capturar estado inicial"
                },
                {
                    "action_type": "wait_for_element",
                    "selector": "input[type='text'], input[name*='rfc'], input[id*='rfc']",
                    "timeout": 15000,
                    "description": "Buscar campo RFC"
                },
                {
                    "action_type": "type",
                    "selector": "input[type='text'], input[name*='rfc'], input[id*='rfc']",
                    "value": "${rfc}",
                    "description": "Ingresar RFC"
                }
            ],
            "input_schema": {
                "rfc": "RFC del receptor",
                "folio": "Folio del ticket",
                "fecha": "Fecha de compra",
                "total": "Total del ticket"
            },
            "success_validations": [
                {
                    "type": "url_contains",
                    "value": "success",
                    "description": "Verificar URL de éxito"
                }
            ],
            "estimated_duration_seconds": 120,
            "confidence_score": 0.6
        }

    async def _parse_ai_response_to_plan(
        self,
        ai_response: Dict[str, Any],
        merchant_name: str,
        portal_url: str,
        ticket_data: Dict[str, Any]
    ) -> RPAPlan:
        """Parsear respuesta del AI a plan estructurado"""

        # Convertir acciones del AI a objetos RPAAction
        actions = []
        for action_data in ai_response.get("actions", []):
            action = RPAAction(
                action_type=ActionType(action_data["action_type"]),
                selector=action_data.get("selector"),
                value=action_data.get("value"),
                timeout=action_data.get("timeout", 30000),
                description=action_data.get("description", ""),
                options=action_data.get("options", {}),
                expected_result=action_data.get("expected_result"),
                retry_count=action_data.get("retry_count", 3)
            )
            actions.append(action)

        # Crear plan completo
        plan = RPAPlan(
            plan_id=self._generate_plan_id(merchant_name, portal_url),
            merchant_name=merchant_name,
            portal_url=portal_url,
            browser_config=ai_response.get("browser_config", self.browser_configs["default"]),
            actions=actions,
            input_schema=ai_response.get("input_schema", {}),
            success_validations=ai_response.get("success_validations", []),
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            confidence_score=ai_response.get("confidence_score", 0.7),
            estimated_duration_seconds=ai_response.get("estimated_duration_seconds", 90)
        )

        return plan

    async def _validate_and_optimize_plan(self, plan: RPAPlan) -> RPAPlan:
        """Validar y optimizar plan generado"""

        # Validaciones básicas
        if not plan.actions:
            raise ValueError("Plan sin acciones")

        # Optimizaciones
        optimized_actions = []

        for i, action in enumerate(plan.actions):
            # Validar selectores
            if action.selector and not self._is_valid_css_selector(action.selector):
                logger.warning(f"Selector potencialmente inválido: {action.selector}")

            # Agregar screenshots en puntos clave
            if action.action_type in [ActionType.CLICK, ActionType.TYPE] and i % 3 == 0:
                screenshot_action = RPAAction(
                    action_type=ActionType.TAKE_SCREENSHOT,
                    description=f"Captura después de {action.description}"
                )
                optimized_actions.append(screenshot_action)

            optimized_actions.append(action)

        # Agregar screenshot final
        final_screenshot = RPAAction(
            action_type=ActionType.TAKE_SCREENSHOT,
            description="Captura final del proceso"
        )
        optimized_actions.append(final_screenshot)

        plan.actions = optimized_actions

        return plan

    async def _create_fallback_plan(
        self,
        merchant_name: str,
        portal_url: str,
        ticket_data: Dict[str, Any]
    ) -> RPAPlan:
        """Crear plan de fallback cuando falla la generación con IA"""

        actions = [
            RPAAction(
                action_type=ActionType.NAVIGATE,
                value=portal_url,
                description=f"Navegar a {merchant_name}",
                timeout=30000
            ),
            RPAAction(
                action_type=ActionType.TAKE_SCREENSHOT,
                description="Capturar página inicial"
            ),
            RPAAction(
                action_type=ActionType.WAIT_TIME,
                value="5000",
                description="Esperar carga completa"
            )
        ]

        return RPAPlan(
            plan_id=self._generate_plan_id(merchant_name, portal_url),
            merchant_name=merchant_name,
            portal_url=portal_url,
            browser_config=self.browser_configs["default"],
            actions=actions,
            input_schema={},
            success_validations=[],
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            confidence_score=0.3,
            estimated_duration_seconds=30
        )

    def _generate_plan_id(self, merchant_name: str, portal_url: str) -> str:
        """Generar ID único para el plan"""

        content = f"{merchant_name}-{portal_url}-{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _is_valid_css_selector(self, selector: str) -> bool:
        """Validar si un selector CSS es válido"""

        try:
            import re

            # Patrones básicos de selectores válidos
            valid_patterns = [
                r'^#[\w-]+$',  # ID
                r'^\.[\w-]+$',  # Class
                r'^\w+$',  # Tag
                r'^\[[\w-]+.*\]$',  # Attribute
                r'^[\w\s\.\#\[\],:>+~-]+$'  # Combinación compleja
            ]

            return any(re.match(pattern, selector) for pattern in valid_patterns)

        except:
            return False

    def _load_system_prompt(self) -> str:
        """Cargar prompt del sistema para el LLM"""

        return """
Eres un experto en automatización RPA especializado en portales de facturación mexicanos.

Tu tarea es analizar portales web y generar planes de automatización seguros y deterministas.

PRINCIPIOS:
1. SEGURIDAD: No ejecutes acciones destructivas o no autorizadas
2. DETERMINISMO: Cada plan debe ser reproducible
3. ROBUSTEZ: Incluye validaciones y manejo de errores
4. EFICIENCIA: Minimiza el número de acciones

CONOCIMIENTO ESPECÍFICO:
- Portales mexicanos comunes: OXXO, Walmart, Costco, Home Depot, etc.
- Campos típicos: RFC, folio, fecha, total, uso de CFDI
- Patrones UI comunes en sitios de facturación
- Validaciones de formato de datos mexicanos

RESPONDE SIEMPRE EN JSON VÁLIDO.
        """.strip()


# Función de conveniencia
async def create_rpa_plan(
    merchant_name: str,
    portal_url: str,
    ticket_data: Dict[str, Any],
    credentials: Dict[str, str],
    context: Optional[str] = None
) -> RPAPlan:
    """
    Crear plan RPA para automatización de facturación.

    Args:
        merchant_name: Nombre del merchant
        portal_url: URL del portal
        ticket_data: Datos extraídos del ticket
        credentials: Credenciales para acceso
        context: Contexto adicional

    Returns:
        Plan de automatización listo para ejecutar
    """

    planner = AIRPAPlanner()
    return await planner.analyze_portal_and_create_plan(
        merchant_name=merchant_name,
        portal_url=portal_url,
        ticket_data=ticket_data,
        credentials=credentials,
        context=context
    )


if __name__ == "__main__":
    # Test del planificador
    import asyncio

    async def test_ai_planner():
        """Test del planificador RPA con IA"""

        print("=== TEST DEL PLANIFICADOR RPA CON IA ===")

        # Datos de prueba
        ticket_data = {
            "merchant_rfc": "MFU761216I40",
            "folio": "318534",
            "fecha": "18/08/2025",
            "total": 359.00,
            "merchant_name": "Mejor Futuro"
        }

        credentials = {
            "username": "test@empresa.com",
            "password": "password123"
        }

        try:
            plan = await create_rpa_plan(
                merchant_name="Mejor Futuro",
                portal_url="https://facturacion.inforest.com.mx",
                ticket_data=ticket_data,
                credentials=credentials,
                context="Portal de restaurante con formulario simple"
            )

            print(f"✅ Plan creado exitosamente:")
            print(f"ID: {plan.plan_id}")
            print(f"Acciones: {len(plan.actions)}")
            print(f"Confianza: {plan.confidence_score:.2%}")
            print(f"Duración estimada: {plan.estimated_duration_seconds}s")

            print("\nPrimeras acciones:")
            for i, action in enumerate(plan.actions[:5]):
                print(f"{i+1}. {action.action_type.value}: {action.description}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Ejecutar test
    asyncio.run(test_ai_planner())