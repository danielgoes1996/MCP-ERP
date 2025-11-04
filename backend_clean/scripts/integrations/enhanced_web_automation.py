"""
Sistema de automatización web mejorado que integra el manejador de páginas dinámicas
para resolver el problema de elementos que cambian después de cargar.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from modules.invoicing_agent.web_automation import WebAutomationWorker
from dynamic_page_handler import DynamicPageHandler

logger = logging.getLogger(__name__)


class EnhancedWebAutomationWorker(WebAutomationWorker):
    """
    Worker de automatización web mejorado que maneja páginas dinámicas.

    Resuelve problemas como:
    - Elementos que aparecen después de cargar
    - Botones que cambian de posición (header vs hero)
    - Contenido que se actualiza cada X segundos
    """

    def __init__(self):
        super().__init__()
        self.dynamic_handler = None

    async def navigate_to_portal_enhanced(
        self,
        url: str,
        merchant_name: str = None,
        take_screenshot: bool = True,
        auto_fill: bool = False,
        ticket_text: str = None,
        handle_dynamic_content: bool = True,
        capture_intervals: List[int] = [0, 3, 6, 10]
    ) -> Dict[str, Any]:
        """
        Navegación mejorada que maneja contenido dinámico.

        Args:
            url: URL del portal
            merchant_name: Nombre del merchant
            take_screenshot: Si tomar screenshots
            auto_fill: Si llenar automáticamente
            ticket_text: Texto del ticket
            handle_dynamic_content: Si usar captura dinámica
            capture_intervals: Momentos para capturar (en segundos)

        Returns:
            Resultado de navegación con análisis dinámico
        """
        start_time = time.time()

        try:
            logger.info(f"🚀 Navegación mejorada a: {url}")

            # Configurar driver
            self.driver = self.setup_driver(headless=True)
            self.dynamic_handler = DynamicPageHandler(self.driver)

            result = {
                "success": False,
                "url": url,
                "merchant": merchant_name,
                "loading_time": 0,
                "page_title": "",
                "accessibility": "unknown",
                "form_detected": False,
                "form_fields": [],
                "screenshots": [],
                "dynamic_analysis": None,
                "auto_filled": False,
                "filled_fields": {},
                "submission_result": None,
                "error": None,
                "multiple_selectors_tried": [],
                "best_interaction_moment": None
            }

            if handle_dynamic_content:
                # Usar análisis dinámico
                logger.info("🔄 Usando análisis dinámico de página...")

                dynamic_result = await self.dynamic_handler.capture_dynamic_page(
                    url=url,
                    capture_intervals=capture_intervals,
                    element_selectors=[
                        "button:contains('factura')",
                        "a:contains('factura')",
                        "button:contains('solicitar')",
                        ".btn-factura",
                        ".facturacion",
                        "#factura",
                        "input[type='submit']",
                        "button[type='submit']"
                    ]
                )

                result["dynamic_analysis"] = dynamic_result

                if dynamic_result["success"]:
                    result["success"] = True
                    result["page_title"] = dynamic_result["page_title"]
                    result["accessibility"] = "accessible"
                    result["screenshots"] = [c["screenshot_path"] for c in dynamic_result["captures"] if c["screenshot_path"]]
                    result["best_interaction_moment"] = dynamic_result["captures"][dynamic_result["best_capture_index"]]["interval"]

                    # Usar la mejor captura para detectar formularios
                    best_capture = dynamic_result["captures"][dynamic_result["best_capture_index"]]
                    result["form_detected"] = best_capture["forms_found"] > 0
                    result["form_fields"] = best_capture["forms"] if best_capture["forms_found"] > 0 else []

                    logger.info(f"✅ Análisis dinámico completado. Mejor momento: {result['best_interaction_moment']}s")

                    # Si hay auto_fill, usar múltiples estrategias
                    if auto_fill and ticket_text:
                        fill_result = await self._enhanced_auto_fill(
                            dynamic_result,
                            ticket_text,
                            merchant_name
                        )
                        result.update(fill_result)

                else:
                    result["error"] = dynamic_result.get("error", "Error en análisis dinámico")
                    logger.error(f"❌ Error en análisis dinámico: {result['error']}")

            else:
                # Navegación tradicional
                logger.info("🔄 Usando navegación tradicional...")
                traditional_result = await super().navigate_to_portal(
                    url=url,
                    merchant_name=merchant_name,
                    take_screenshot=take_screenshot,
                    auto_fill=auto_fill,
                    ticket_text=ticket_text
                )
                result.update(traditional_result)

            result["loading_time"] = time.time() - start_time
            return result

        except Exception as e:
            logger.error(f"❌ Error en navegación mejorada: {e}")
            result["error"] = str(e)
            result["loading_time"] = time.time() - start_time
            return result

        finally:
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except:
                    pass

    async def _enhanced_auto_fill(
        self,
        dynamic_result: Dict[str, Any],
        ticket_text: str,
        merchant_name: str
    ) -> Dict[str, Any]:
        """
        Auto-fill mejorado que usa múltiples estrategias y momentos.

        Args:
            dynamic_result: Resultado del análisis dinámico
            ticket_text: Texto del ticket
            merchant_name: Nombre del merchant

        Returns:
            Resultado del auto-fill
        """
        fill_result = {
            "auto_filled": False,
            "filled_fields": {},
            "multiple_selectors_tried": [],
            "submission_result": None,
            "fill_strategies_used": []
        }

        try:
            # Usar la mejor captura
            best_capture = dynamic_result["captures"][dynamic_result["best_capture_index"]]

            logger.info(f"🎯 Iniciando auto-fill en momento óptimo: {best_capture['interval']}s")

            # Esperar al momento óptimo si es necesario
            current_time = time.time()
            target_time = best_capture["timestamp"]
            wait_time = max(0, target_time - current_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Estrategia 1: Buscar botones de facturación específicos
            factura_buttons = await self._try_factura_buttons(best_capture)
            if factura_buttons["success"]:
                fill_result["auto_filled"] = True
                fill_result["fill_strategies_used"].append("factura_buttons")
                fill_result["filled_fields"]["factura_button"] = factura_buttons["button_clicked"]

            # Estrategia 2: Llenar formularios detectados
            if best_capture["forms_found"] > 0:
                form_fill = await self._try_form_filling(best_capture, ticket_text, merchant_name)
                if form_fill["success"]:
                    fill_result["auto_filled"] = True
                    fill_result["fill_strategies_used"].append("form_filling")
                    fill_result["filled_fields"].update(form_fill["fields"])

            # Estrategia 3: Buscar enlaces de facturación
            factura_links = await self._try_factura_links(best_capture)
            if factura_links["success"]:
                fill_result["auto_filled"] = True
                fill_result["fill_strategies_used"].append("factura_links")
                fill_result["filled_fields"]["factura_link"] = factura_links["link_clicked"]

            # Registro de selectores probados
            fill_result["multiple_selectors_tried"] = [
                "button:contains('factura')",
                "a:contains('factura')",
                "button:contains('solicitar')",
                ".btn-factura",
                ".facturacion",
                "form input[name*='rfc']",
                "form input[name*='email']"
            ]

            logger.info(f"✅ Auto-fill completado. Estrategias usadas: {fill_result['fill_strategies_used']}")

        except Exception as e:
            logger.error(f"❌ Error en auto-fill mejorado: {e}")
            fill_result["error"] = str(e)

        return fill_result

    async def _try_factura_buttons(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        """Intentar hacer clic en botones de facturación detectados"""
        try:
            from selenium.webdriver.common.by import By

            # Buscar elementos que contengan "factura"
            factura_elements = [
                elem for elem in capture["elements"]
                if "factura" in elem["text"].lower() and elem["visible"] and elem["enabled"]
            ]

            if not factura_elements:
                return {"success": False, "reason": "No se encontraron botones de facturación"}

            # Intentar hacer clic en el primer botón disponible
            for element_info in factura_elements:
                try:
                    if element_info["attributes"]["id"]:
                        element = self.driver.find_element(By.ID, element_info["attributes"]["id"])
                    elif element_info["attributes"]["class"]:
                        element = self.driver.find_element(By.CLASS_NAME, element_info["attributes"]["class"].split()[0])
                    else:
                        # Usar XPath basado en texto
                        element = self.driver.find_element(By.XPATH, f"//{element_info['tag']}[contains(text(), 'factura')]")

                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        await asyncio.sleep(2)  # Esperar respuesta
                        return {
                            "success": True,
                            "button_clicked": element_info["text"][:50],
                            "element_info": element_info
                        }

                except Exception as e:
                    logger.warning(f"Error haciendo clic en botón: {e}")
                    continue

            return {"success": False, "reason": "No se pudo hacer clic en ningún botón"}

        except Exception as e:
            logger.error(f"Error en _try_factura_buttons: {e}")
            return {"success": False, "error": str(e)}

    async def _try_form_filling(self, capture: Dict[str, Any], ticket_text: str, merchant_name: str) -> Dict[str, Any]:
        """Intentar llenar formularios detectados"""
        try:
            from selenium.webdriver.common.by import By

            filled_fields = {}

            for form_info in capture["forms"]:
                if not form_info["visible"]:
                    continue

                # Buscar el formulario en la página
                forms = self.driver.find_elements(By.TAG_NAME, "form")
                if len(forms) <= form_info["index"]:
                    continue

                form_element = forms[form_info["index"]]

                # Llenar campos básicos
                for field in form_info["fields"]:
                    try:
                        if field["type"] == "input":
                            input_element = None

                            # Buscar por name
                            if field["name"]:
                                input_element = form_element.find_element(By.NAME, field["name"])
                            # Buscar por id
                            elif field["id"]:
                                input_element = form_element.find_element(By.ID, field["id"])

                            if input_element and input_element.is_displayed() and input_element.is_enabled():
                                # Determinar qué valor llenar
                                value = self._determine_field_value(field, ticket_text, merchant_name)
                                if value:
                                    input_element.clear()
                                    input_element.send_keys(value)
                                    filled_fields[field["name"] or field["id"]] = value

                    except Exception as e:
                        logger.warning(f"Error llenando campo {field}: {e}")
                        continue

            return {
                "success": len(filled_fields) > 0,
                "fields": filled_fields,
                "fields_filled_count": len(filled_fields)
            }

        except Exception as e:
            logger.error(f"Error en _try_form_filling: {e}")
            return {"success": False, "error": str(e)}

    async def _try_factura_links(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        """Intentar hacer clic en enlaces de facturación"""
        try:
            from selenium.webdriver.common.by import By

            # Buscar enlaces que contengan "factura"
            factura_links = [
                elem for elem in capture["elements"]
                if elem["tag"] == "a" and "factura" in elem["text"].lower() and elem["visible"]
            ]

            if not factura_links:
                return {"success": False, "reason": "No se encontraron enlaces de facturación"}

            # Intentar hacer clic en el primer enlace
            for link_info in factura_links:
                try:
                    if link_info["attributes"]["href"]:
                        link = self.driver.find_element(By.XPATH, f"//a[@href='{link_info['attributes']['href']}']")
                        if link.is_displayed():
                            link.click()
                            await asyncio.sleep(2)
                            return {
                                "success": True,
                                "link_clicked": link_info["text"][:50],
                                "href": link_info["attributes"]["href"]
                            }

                except Exception as e:
                    logger.warning(f"Error haciendo clic en enlace: {e}")
                    continue

            return {"success": False, "reason": "No se pudo hacer clic en ningún enlace"}

        except Exception as e:
            logger.error(f"Error en _try_factura_links: {e}")
            return {"success": False, "error": str(e)}

    def _determine_field_value(self, field: Dict[str, Any], ticket_text: str, merchant_name: str) -> Optional[str]:
        """Determinar qué valor llenar en un campo específico"""
        field_name = (field.get("name") or field.get("id") or "").lower()
        (field.get("placeholder") or "").lower()

        # RFC
        if any(keyword in field_name for keyword in ["rfc"]):
            return self.company_credentials["rfc"]

        # Email
        if any(keyword in field_name for keyword in ["email", "correo", "mail"]):
            return self.company_credentials["email"]

        # Teléfono
        if any(keyword in field_name for keyword in ["telefono", "phone", "tel"]):
            return self.company_credentials["telefono"]

        # Código postal
        if any(keyword in field_name for keyword in ["postal", "zip", "cp"]):
            return self.company_credentials["codigo_postal"]

        # Total (extraer del ticket)
        if any(keyword in field_name for keyword in ["total", "monto", "amount", "importe"]):
            return self._extract_total_from_ticket({"raw_data": ticket_text})

        # Fecha (extraer del ticket)
        if any(keyword in field_name for keyword in ["fecha", "date"]):
            return self._extract_date_from_ticket({"raw_data": ticket_text})

        return None


async def test_enhanced_navigation():
    """Función de prueba para la navegación mejorada"""
    logger.info("🧪 Probando navegación mejorada con Litro Mil")

    worker = EnhancedWebAutomationWorker()

    test_ticket = """
    LITRO MIL ESTACION #5678
    RFC: LIT123456789
    MAGNA $350.00
    Total: $350.00
    Fecha: 2024-01-15
    """

    try:
        result = await worker.navigate_to_portal_enhanced(
            url="https://litromil.com",
            merchant_name="Litro Mil",
            auto_fill=True,
            ticket_text=test_ticket,
            handle_dynamic_content=True,
            capture_intervals=[0, 3, 6, 10]
        )

        print("🎯 Resultado de navegación mejorada:")
        print(f"✅ Éxito: {result['success']}")
        print(f"⏱️ Tiempo de carga: {result['loading_time']:.2f}s")
        print(f"📸 Screenshots tomados: {len(result['screenshots'])}")

        if result.get('best_interaction_moment'):
            print(f"🎯 Mejor momento para interactuar: {result['best_interaction_moment']}s")

        if result.get('auto_filled'):
            print(f"📝 Auto-fill exitoso: {result['fill_strategies_used']}")
            print(f"📋 Campos llenados: {list(result['filled_fields'].keys())}")

        if result.get('dynamic_analysis'):
            da = result['dynamic_analysis']
            print(f"🔄 Análisis dinámico: {len(da['captures'])} capturas")
            if da.get('changes_detected', {}).get('significant_changes'):
                print("⚠️ Se detectaron cambios significativos en la página")

    except Exception as e:
        print(f"❌ Error en prueba: {e}")

    finally:
        await worker.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_enhanced_navigation())