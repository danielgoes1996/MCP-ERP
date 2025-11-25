"""
Manejador mejorado para páginas dinámicas que cambian después de cargar.
Implementa capturas múltiples y detección de elementos que aparecen/desaparecen.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class DynamicPageHandler:
    """
    Maneja páginas web que cambian dinámicamente después de cargar.

    Especialmente útil para páginas con:
    - Elementos que aparecen después de cargar (JavaScript)
    - Botones que cambian de posición
    - Content que se actualiza cada X segundos
    """

    def __init__(self, driver, wait_timeout: int = 30):
        self.driver = driver
        self.wait_timeout = wait_timeout
        self.screenshots = []
        self.detected_elements = []

    async def capture_dynamic_page(
        self,
        url: str,
        capture_intervals: List[int] = [0, 3, 6, 10],
        element_selectors: List[str] = None
    ) -> Dict[str, Any]:
        """
        Capturar una página dinámica en múltiples momentos.

        Args:
            url: URL a capturar
            capture_intervals: Momentos en segundos para tomar screenshots
            element_selectors: Selectores de elementos a monitorear

        Returns:
            Dict con información de todas las capturas
        """
        try:
            logger.info(f"🌐 Navegando a página dinámica: {url}")

            # Navegar a la página
            self.driver.get(url)

            # Obtener título inicial
            page_title = self.driver.title
            logger.info(f"📄 Título de página: {page_title}")

            # Realizar capturas en intervalos
            capture_results = []

            for i, interval in enumerate(capture_intervals):
                if i > 0:  # No esperar en la primera captura
                    logger.info(f"⏰ Esperando {interval} segundos para captura {i+1}...")
                    await asyncio.sleep(interval - (capture_intervals[i-1] if i > 0 else 0))

                # Tomar screenshot
                screenshot_path = f"screenshots/dynamic_capture_{int(time.time())}_{i}.png"
                success = self._take_screenshot(screenshot_path)

                # Detectar elementos disponibles
                elements = self._detect_page_elements(element_selectors)

                # Detectar formularios
                forms = self._detect_forms()

                capture_result = {
                    "interval": interval,
                    "timestamp": time.time(),
                    "screenshot_path": screenshot_path if success else None,
                    "elements_found": len(elements),
                    "elements": elements,
                    "forms_found": len(forms),
                    "forms": forms,
                    "page_source_length": len(self.driver.page_source),
                    "current_url": self.driver.current_url
                }

                capture_results.append(capture_result)
                logger.info(f"✅ Captura {i+1}: {len(elements)} elementos, {len(forms)} formularios")

            # Analizar cambios entre capturas
            changes = self._analyze_changes_between_captures(capture_results)

            # Encontrar el mejor momento para interactuar
            best_capture = self._find_best_interaction_moment(capture_results)

            return {
                "success": True,
                "url": url,
                "page_title": page_title,
                "captures": capture_results,
                "changes_detected": changes,
                "best_capture_index": best_capture,
                "recommendation": self._get_interaction_recommendation(capture_results, best_capture),
                "total_screenshots": len([c for c in capture_results if c["screenshot_path"]])
            }

        except Exception as e:
            logger.error(f"❌ Error capturando página dinámica: {e}")
            return {
                "success": False,
                "error": str(e),
                "captures": capture_results if 'capture_results' in locals() else []
            }

    def _take_screenshot(self, path: str) -> bool:
        """Tomar screenshot de la página actual"""
        try:
            import os
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.driver.save_screenshot(path)
            return True
        except Exception as e:
            logger.error(f"Error tomando screenshot: {e}")
            return False

    def _detect_page_elements(self, custom_selectors: List[str] = None) -> List[Dict[str, Any]]:
        """Detectar elementos importantes en la página"""
        elements = []

        # Selectores comunes para facturación
        common_selectors = [
            "button:contains('factura')",
            "a:contains('factura')",
            "button:contains('solicitar')",
            "a:contains('solicitar')",
            ".btn-factura",
            ".facturacion",
            "#factura",
            "input[type='submit']",
            "button[type='submit']",
            ".submit-btn",
            ".btn-primary",
            ".btn-success"
        ]

        # Combinar con selectores personalizados
        all_selectors = common_selectors + (custom_selectors or [])

        for selector in all_selectors:
            try:
                # Adaptar selectores CSS que contengan :contains
                if ":contains(" in selector:
                    # Convertir a XPath para Selenium
                    text = selector.split(":contains('")[1].split("')")[0]
                    tag = selector.split(":contains(")[0]
                    xpath = f"//{tag}[contains(text(), '{text}')]"
                    found_elements = self.driver.find_elements(By.XPATH, xpath)
                else:
                    found_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                for i, element in enumerate(found_elements):
                    if element.is_displayed():
                        try:
                            elements.append({
                                "selector": selector,
                                "index": i,
                                "tag": element.tag_name,
                                "text": element.text[:100],  # Primeros 100 caracteres
                                "visible": element.is_displayed(),
                                "enabled": element.is_enabled(),
                                "location": element.location,
                                "size": element.size,
                                "attributes": {
                                    "id": element.get_attribute("id"),
                                    "class": element.get_attribute("class"),
                                    "type": element.get_attribute("type"),
                                    "href": element.get_attribute("href")
                                }
                            })
                        except Exception as e:
                            # Element could be stale, skip it
                            continue

            except Exception as e:
                # Selector failed, continue with next
                continue

        return elements

    def _detect_forms(self) -> List[Dict[str, Any]]:
        """Detectar formularios en la página"""
        forms = []

        try:
            form_elements = self.driver.find_elements(By.TAG_NAME, "form")

            for i, form in enumerate(form_elements):
                if form.is_displayed():
                    # Detectar campos del formulario
                    inputs = form.find_elements(By.TAG_NAME, "input")
                    textareas = form.find_elements(By.TAG_NAME, "textarea")
                    selects = form.find_elements(By.TAG_NAME, "select")

                    fields = []
                    for input_elem in inputs:
                        if input_elem.is_displayed():
                            fields.append({
                                "type": "input",
                                "input_type": input_elem.get_attribute("type"),
                                "name": input_elem.get_attribute("name"),
                                "id": input_elem.get_attribute("id"),
                                "placeholder": input_elem.get_attribute("placeholder"),
                                "required": input_elem.get_attribute("required") is not None
                            })

                    for textarea in textareas:
                        if textarea.is_displayed():
                            fields.append({
                                "type": "textarea",
                                "name": textarea.get_attribute("name"),
                                "id": textarea.get_attribute("id"),
                                "placeholder": textarea.get_attribute("placeholder")
                            })

                    for select in selects:
                        if select.is_displayed():
                            fields.append({
                                "type": "select",
                                "name": select.get_attribute("name"),
                                "id": select.get_attribute("id")
                            })

                    forms.append({
                        "index": i,
                        "action": form.get_attribute("action"),
                        "method": form.get_attribute("method"),
                        "fields_count": len(fields),
                        "fields": fields,
                        "visible": form.is_displayed()
                    })

        except Exception as e:
            logger.error(f"Error detectando formularios: {e}")

        return forms

    def _analyze_changes_between_captures(self, captures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analizar cambios entre capturas consecutivas"""
        changes = {
            "elements_appeared": [],
            "elements_disappeared": [],
            "forms_appeared": [],
            "forms_disappeared": [],
            "significant_changes": False
        }

        if len(captures) < 2:
            return changes

        try:
            for i in range(1, len(captures)):
                prev_capture = captures[i-1]
                curr_capture = captures[i]

                # Comparar número de elementos
                prev_elements = prev_capture["elements_found"]
                curr_elements = curr_capture["elements_found"]

                # Comparar número de formularios
                prev_forms = prev_capture["forms_found"]
                curr_forms = curr_capture["forms_found"]

                if curr_elements > prev_elements:
                    changes["elements_appeared"].append({
                        "interval": curr_capture["interval"],
                        "new_elements": curr_elements - prev_elements
                    })
                    changes["significant_changes"] = True

                if curr_elements < prev_elements:
                    changes["elements_disappeared"].append({
                        "interval": curr_capture["interval"],
                        "lost_elements": prev_elements - curr_elements
                    })
                    changes["significant_changes"] = True

                if curr_forms > prev_forms:
                    changes["forms_appeared"].append({
                        "interval": curr_capture["interval"],
                        "new_forms": curr_forms - prev_forms
                    })
                    changes["significant_changes"] = True

                if curr_forms < prev_forms:
                    changes["forms_disappeared"].append({
                        "interval": curr_capture["interval"],
                        "lost_forms": prev_forms - curr_forms
                    })
                    changes["significant_changes"] = True

        except Exception as e:
            logger.error(f"Error analizando cambios: {e}")

        return changes

    def _find_best_interaction_moment(self, captures: List[Dict[str, Any]]) -> int:
        """Encontrar el mejor momento para interactuar con la página"""
        best_index = 0
        best_score = 0

        for i, capture in enumerate(captures):
            score = 0

            # Más elementos = mejor
            score += capture["elements_found"] * 2

            # Más formularios = mejor
            score += capture["forms_found"] * 5

            # Penalizar capturas muy tempranas (pueden estar cargando)
            if capture["interval"] >= 3:
                score += 10

            # Bonificar si hay elementos interactivos
            for element in capture["elements"]:
                if element["enabled"] and element["visible"]:
                    if any(keyword in element["text"].lower() for keyword in ["factura", "solicitar", "enviar"]):
                        score += 15

            if score > best_score:
                best_score = score
                best_index = i

        return best_index

    def _get_interaction_recommendation(self, captures: List[Dict[str, Any]], best_index: int) -> str:
        """Generar recomendación de interacción"""
        if not captures:
            return "No se pudieron realizar capturas"

        best_capture = captures[best_index]

        recommendations = []

        if best_capture["forms_found"] > 0:
            recommendations.append(f"Se detectaron {best_capture['forms_found']} formularios en el segundo {best_capture['interval']}")

        if best_capture["elements_found"] > 0:
            recommendations.append(f"Se encontraron {best_capture['elements_found']} elementos interactivos")

        # Buscar botones específicos de facturación
        factura_buttons = [
            elem for elem in best_capture["elements"]
            if "factura" in elem["text"].lower() or "solicitar" in elem["text"].lower()
        ]

        if factura_buttons:
            recommendations.append(f"Se detectaron {len(factura_buttons)} botones de facturación")

        if not recommendations:
            recommendations.append("No se detectaron elementos de facturación claros")

        return f"Mejor momento para interactuar: segundo {best_capture['interval']}. " + ". ".join(recommendations)


async def test_dynamic_page_handler():
    """Función de prueba para el manejador de páginas dinámicas"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        handler = DynamicPageHandler(driver)

        # Probar con una página conocida
        result = await handler.capture_dynamic_page(
            url="https://litromil.com",
            capture_intervals=[0, 2, 5, 8],
            element_selectors=[
                "button:contains('factura')",
                ".btn-factura",
                "#factura-btn"
            ]
        )

        print("🧪 Resultado de prueba:")
        print(f"✅ Éxito: {result['success']}")
        if result['success']:
            print(f"📊 Capturas realizadas: {len(result['captures'])}")
            print(f"🎯 Mejor momento: segundo {result['captures'][result['best_capture_index']]['interval']}")
            print(f"💡 Recomendación: {result['recommendation']}")
        else:
            print(f"❌ Error: {result['error']}")

    finally:
        driver.quit()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_dynamic_page_handler())