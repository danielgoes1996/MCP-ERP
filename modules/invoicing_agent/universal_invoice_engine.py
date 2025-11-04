"""
Universal Invoice Engine - Motor Dinámico para Cualquier Portal de Facturación
Sistema inteligente que se adapta automáticamente a cualquier portal y obtiene facturas
"""

import asyncio
import logging
import time
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright

# Verificar disponibilidad de Claude
try:
    from core.claude_dom_analyzer import create_claude_analyzer
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

logger = logging.getLogger(__name__)

class InvoiceStage(Enum):
    """Etapas del proceso de facturación universal"""
    INITIAL_LANDING = "initial_landing"
    PORTAL_DETECTION = "portal_detection"
    NAVIGATION_TO_INVOICE = "navigation_to_invoice"
    FORM_FILLING = "form_filling"
    INVOICE_GENERATION = "invoice_generation"
    INVOICE_DOWNLOAD = "invoice_download"
    COMPLETION = "completion"

class PortalTechnology(Enum):
    """Tecnologías de portal detectadas"""
    ASP_NET = "asp_net"
    REACT = "react"
    ANGULAR = "angular"
    VUE = "vue"
    WORDPRESS = "wordpress"
    SHOPIFY = "shopify"
    CUSTOM_PHP = "custom_php"
    JAVA_JSF = "java_jsf"
    DRUPAL = "drupal"
    UNKNOWN = "unknown"

@dataclass
class InvoiceRequest:
    """Datos necesarios para generar factura"""
    rfc: Optional[str] = None
    email: Optional[str] = None
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    folio: Optional[str] = None
    total: Optional[str] = None
    fecha: Optional[str] = None
    conceptos: Optional[List[str]] = None
    uso_cfdi: Optional[str] = None

class UniversalInvoiceEngine:
    """Motor universal que se adapta a cualquier portal de facturación"""

    def __init__(self, ticket_id: int, invoice_data: Optional[InvoiceRequest] = None):
        self.ticket_id = ticket_id
        self.invoice_data = invoice_data or InvoiceRequest()

        # Playwright components
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Intelligence components
        self.claude_analyzer = None
        if CLAUDE_AVAILABLE:
            try:
                self.claude_analyzer = create_claude_analyzer()
                self._log("🤖 Claude habilitado para análisis inteligente")
            except Exception as e:
                self._log(f"⚠️ Claude no disponible: {e}")

        # State tracking
        self.current_stage = InvoiceStage.INITIAL_LANDING
        self.portal_technology = PortalTechnology.UNKNOWN
        self.discovered_patterns = {}
        self.execution_log = []
        self.start_time = time.time()

        # Screenshots
        self.screenshots_dir = Path("/Users/danielgoes96/Desktop/mcp-server/static/automation_screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)

    def _log(self, message: str, level: str = "INFO"):
        """Logging con timestamp y contexto"""
        timestamp = time.time() - self.start_time
        log_entry = f"[{timestamp:.2f}s] [{self.current_stage.value}] {level}: {message}"
        self.execution_log.append(log_entry)

        if level == "ERROR":
            logger.error(log_entry)
        elif level == "WARNING":
            logger.warning(log_entry)
        else:
            logger.info(log_entry)

    async def initialize(self) -> bool:
        """Inicializar motor universal"""
        try:
            self._log("🚀 Inicializando Universal Invoice Engine...")

            self.playwright = await async_playwright().start()

            # Browser optimizado para máxima compatibilidad
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )

            # Contexto con configuración universal
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                java_script_enabled=True,
                accept_downloads=True  # Para descargar facturas
            )

            self.page = await self.context.new_page()

            # Configurar timeouts dinámicos
            self.page.set_default_timeout(15000)
            self.page.set_default_navigation_timeout(30000)

            # Event listeners universales
            self.page.on("console", lambda msg: self._log(f"Console: {msg.text}"))
            self.page.on("download", self._handle_download)
            self.page.on("dialog", self._handle_dialog)

            self._log("✅ Motor universal inicializado")
            return True

        except Exception as e:
            self._log(f"❌ Error inicializando motor: {e}", "ERROR")
            await self.cleanup()
            return False

    async def generate_invoice_from_any_portal(self, portal_url: str) -> Dict[str, Any]:
        """
        Método principal: Generar factura desde cualquier portal dinámicamente
        """
        result = {
            "success": False,
            "invoice_generated": False,
            "invoice_downloaded": False,
            "portal_detected": False,
            "execution_log": [],
            "discovered_patterns": {},
            "invoice_data": {},
            "final_stage": self.current_stage.value
        }

        try:
            self._log(f"🎯 Iniciando generación universal de factura en: {portal_url}")

            # Etapa 1: Navegar y detectar portal
            self.current_stage = InvoiceStage.PORTAL_DETECTION
            detection_result = await self._detect_portal_technology(portal_url)
            result["portal_detected"] = detection_result["success"]
            result["portal_technology"] = self.portal_technology.value

            if not detection_result["success"]:
                return self._finalize_result(result, "Portal detection failed")

            # Etapa 2: Navegación inteligente a facturación
            self.current_stage = InvoiceStage.NAVIGATION_TO_INVOICE
            nav_result = await self._navigate_to_invoice_section_universal()

            if not nav_result["success"]:
                return self._finalize_result(result, "Navigation to invoice section failed")

            # Etapa 3: Detectar y llenar formularios
            self.current_stage = InvoiceStage.FORM_FILLING
            form_result = await self._fill_invoice_form_universal()

            if not form_result["success"]:
                return self._finalize_result(result, "Form filling failed")

            # Etapa 4: Generar factura
            self.current_stage = InvoiceStage.INVOICE_GENERATION
            generation_result = await self._generate_invoice_universal()
            result["invoice_generated"] = generation_result["success"]

            if not generation_result["success"]:
                return self._finalize_result(result, "Invoice generation failed")

            # Etapa 5: Descargar factura
            self.current_stage = InvoiceStage.INVOICE_DOWNLOAD
            download_result = await self._download_invoice_universal()
            result["invoice_downloaded"] = download_result["success"]

            # Éxito final
            self.current_stage = InvoiceStage.COMPLETION
            success = result["invoice_generated"] and result["invoice_downloaded"]

            message = "Invoice generated and downloaded successfully" if success else "Partial success"
            return self._finalize_result(result, message, success)

        except Exception as e:
            self._log(f"❌ Error en generación universal: {e}", "ERROR")
            return self._finalize_result(result, f"Universal generation error: {str(e)}")

    async def _detect_portal_technology(self, url: str) -> Dict[str, Any]:
        """Detectar tecnología y características del portal dinámicamente"""
        try:
            self._log(f"🔍 Detectando tecnología del portal: {url}")

            # Navegar al portal
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self._take_screenshot("portal_detection")

            # Análisis profundo del portal
            portal_analysis = await self.page.evaluate("""
                () => {
                    const analysis = {
                        title: document.title,
                        url: window.location.href,
                        html: document.documentElement.innerHTML.slice(0, 5000),
                        technologies: [],
                        invoice_indicators: [],
                        forms: [],
                        interactive_elements: []
                    };

                    // Detectar tecnologías
                    const html = analysis.html.toLowerCase();

                    if (html.includes('__dopostback') || html.includes('aspnet') || html.includes('webform')) {
                        analysis.technologies.push('ASP.NET');
                    }
                    if (html.includes('react') || html.includes('_react') || window.React) {
                        analysis.technologies.push('React');
                    }
                    if (html.includes('angular') || html.includes('ng-') || window.angular) {
                        analysis.technologies.push('Angular');
                    }
                    if (html.includes('vue') || window.Vue) {
                        analysis.technologies.push('Vue');
                    }
                    if (html.includes('wp-content') || html.includes('wordpress')) {
                        analysis.technologies.push('WordPress');
                    }
                    if (html.includes('shopify') || html.includes('shop.js')) {
                        analysis.technologies.push('Shopify');
                    }

                    // Buscar indicadores de facturación (multiidioma)
                    const invoiceKeywords = [
                        'factur', 'invoic', 'bill', 'receipt', 'cobr', 'pag',
                        'fiscal', 'tax', 'cfdi', 'sat', 'rfc', 'ticket'
                    ];

                    // Buscar elementos interactivos relacionados con facturación
                    const allElements = document.querySelectorAll('a, button, input[type="button"], input[type="submit"], [onclick], [ng-click]');

                    Array.from(allElements).forEach((el, index) => {
                        const text = (el.textContent || el.value || '').toLowerCase();
                        const href = el.href || '';
                        const onclick = el.onclick?.toString() || '';
                        const id = el.id || '';
                        const className = el.className || '';

                        // Verificar si contiene palabras clave de facturación
                        const hasInvoiceKeyword = invoiceKeywords.some(keyword =>
                            text.includes(keyword) || href.includes(keyword) ||
                            onclick.includes(keyword) || id.includes(keyword) ||
                            className.includes(keyword)
                        );

                        if (hasInvoiceKeyword && el.offsetParent !== null) {
                            analysis.invoice_indicators.push({
                                index: index,
                                tag: el.tagName,
                                text: text.slice(0, 100),
                                href: href,
                                id: id,
                                className: className,
                                onclick: onclick.slice(0, 200),
                                selector: el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}:nth-of-type(${index + 1})`
                            });
                        }

                        // Recopilar elementos interactivos generales
                        if (el.offsetParent !== null && (el.tagName === 'BUTTON' || el.tagName === 'A' || el.type === 'button' || el.type === 'submit')) {
                            analysis.interactive_elements.push({
                                tag: el.tagName,
                                text: text.slice(0, 50),
                                href: href,
                                id: id
                            });
                        }
                    });

                    // Análizar formularios
                    Array.from(document.forms).forEach((form, index) => {
                        const inputs = Array.from(form.elements).map(input => ({
                            type: input.type,
                            name: input.name,
                            id: input.id,
                            placeholder: input.placeholder
                        }));

                        analysis.forms.push({
                            index: index,
                            id: form.id,
                            action: form.action,
                            method: form.method,
                            inputs: inputs
                        });
                    });

                    return analysis;
                }
            """)

            # Procesar análisis
            self.discovered_patterns = {
                "technologies": portal_analysis["technologies"],
                "invoice_elements": len(portal_analysis["invoice_indicators"]),
                "forms_count": len(portal_analysis["forms"]),
                "interactive_elements": len(portal_analysis["interactive_elements"])
            }

            # Determinar tecnología principal
            if "ASP.NET" in portal_analysis["technologies"]:
                self.portal_technology = PortalTechnology.ASP_NET
            elif "React" in portal_analysis["technologies"]:
                self.portal_technology = PortalTechnology.REACT
            elif "WordPress" in portal_analysis["technologies"]:
                self.portal_technology = PortalTechnology.WORDPRESS
            elif "Shopify" in portal_analysis["technologies"]:
                self.portal_technology = PortalTechnology.SHOPIFY
            else:
                self.portal_technology = PortalTechnology.CUSTOM_PHP

            self._log(f"🎯 Portal detectado: {self.portal_technology.value}")
            self._log(f"📊 Elementos de facturación encontrados: {len(portal_analysis['invoice_indicators'])}")

            # Guardar análisis para uso posterior
            self.discovered_patterns["portal_analysis"] = portal_analysis

            return {
                "success": True,
                "technology": self.portal_technology,
                "invoice_elements": portal_analysis["invoice_indicators"],
                "analysis": portal_analysis
            }

        except Exception as e:
            self._log(f"❌ Error detectando portal: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    async def _navigate_to_invoice_section_universal(self) -> Dict[str, Any]:
        """Navegación universal a sección de facturación usando patrones descobertos"""
        try:
            self._log("🧭 Navegando a sección de facturación usando análisis dinámico...")

            # Obtener elementos de facturación descobertos
            invoice_elements = self.discovered_patterns["portal_analysis"]["invoice_indicators"]

            if not invoice_elements:
                self._log("⚠️ No se encontraron elementos de facturación directos")
                # Fallback: buscar patrones comunes
                return await self._fallback_navigation()

            # Ordenar elementos por relevancia
            sorted_elements = sorted(invoice_elements, key=lambda x: self._calculate_element_relevance(x), reverse=True)

            # Intentar navegación con los elementos más relevantes
            for i, element in enumerate(sorted_elements[:5]):  # Top 5 elementos
                try:
                    self._log(f"🔧 Probando elemento {i+1}: '{element['text'][:50]}...'")

                    # Obtener URL antes del click
                    url_before = self.page.url

                    # Intentar click usando diferentes estrategias
                    success = await self._try_click_element(element)

                    if success:
                        # Esperar navegación o cambios
                        await asyncio.sleep(2)

                        url_after = self.page.url

                        # Verificar si hay cambio significativo
                        if url_after != url_before or await self._detect_invoice_forms():
                            await self._take_screenshot("navigation_success")
                            self._log(f"✅ Navegación exitosa con elemento: {element['text'][:30]}")
                            return {"success": True, "method": "element_click", "element_used": element}

                except Exception as e:
                    self._log(f"⚠️ Error con elemento {i+1}: {e}")
                    continue

            # Si llegamos aquí, ningún elemento funcionó
            return await self._fallback_navigation()

        except Exception as e:
            self._log(f"❌ Error navegando universalmente: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    def _calculate_element_relevance(self, element: Dict[str, Any]) -> float:
        """Calcular relevancia de elemento para facturación"""
        score = 0.0
        text = element.get("text", "").lower()

        # Palabras clave de alta prioridad
        high_priority = ["facturar", "invoice", "generar factura", "billing", "cfdi"]
        medium_priority = ["factur", "bill", "cobr", "pag", "fiscal"]
        low_priority = ["ticket", "receipt", "documento"]

        for keyword in high_priority:
            if keyword in text:
                score += 3.0

        for keyword in medium_priority:
            if keyword in text:
                score += 2.0

        for keyword in low_priority:
            if keyword in text:
                score += 1.0

        # Bonus por tipo de elemento
        if element.get("tag") == "BUTTON":
            score += 0.5
        elif element.get("tag") == "A" and element.get("href"):
            score += 0.3

        # Bonus por tener ID relevante
        if element.get("id") and any(kw in element.get("id", "").lower() for kw in ["factur", "invoice", "bill"]):
            score += 1.0

        return score

    async def _try_click_element(self, element: Dict[str, Any]) -> bool:
        """Intentar click en elemento usando múltiples estrategias"""
        strategies = []

        # Estrategia 1: Por ID
        if element.get("id"):
            strategies.append(f"#{element['id']}")

        # Estrategia 2: Por texto exacto
        if element.get("text") and len(element["text"].strip()) > 0:
            strategies.append(f"{element['tag'].lower()}:has-text('{element['text'][:30]}')")

        # Estrategia 3: Por href
        if element.get("href"):
            strategies.append(f"a[href='{element['href']}']")

        # Estrategia 4: Por onclick
        if element.get("onclick"):
            strategies.append(f"[onclick*='{element['onclick'][:20]}']")

        # Probar cada estrategia
        for strategy in strategies:
            try:
                locator = self.page.locator(strategy).first

                if await locator.count() > 0 and await locator.is_visible():
                    await locator.click(timeout=10000)
                    return True

            except Exception as e:
                continue

        return False

    async def _fallback_navigation(self) -> Dict[str, Any]:
        """Navegación de fallback usando patrones universales"""
        self._log("🔧 Ejecutando navegación de fallback...")

        # Patrones universales de navegación
        universal_selectors = [
            # Botones y enlaces comunes
            "button:has-text('Facturar')",
            "a:has-text('Facturación')",
            "button:has-text('Invoice')",
            "a:has-text('Billing')",
            "button:has-text('Generar')",
            "[id*='factur']",
            "[id*='invoice']",
            "[class*='factur']",
            "[class*='invoice']",
            # ASP.NET específico
            "input[value*='Facturar']",
            "button[onclick*='facturar']",
            "[onclick*='invoice']",
            # WordPress/eCommerce
            ".invoice-button",
            ".billing-button",
            "a[href*='invoice']",
            "a[href*='billing']"
        ]

        for selector in universal_selectors:
            try:
                locator = self.page.locator(selector).first

                if await locator.count() > 0 and await locator.is_visible():
                    await locator.click(timeout=10000)
                    await asyncio.sleep(2)

                    # Verificar si llegamos a formularios
                    if await self._detect_invoice_forms():
                        self._log(f"✅ Navegación de fallback exitosa con: {selector}")
                        return {"success": True, "method": "fallback", "selector_used": selector}

            except Exception as e:
                continue

        self._log("❌ Todos los métodos de navegación fallaron")
        return {"success": False, "error": "All navigation methods failed"}

    async def _detect_invoice_forms(self) -> bool:
        """Detectar si estamos en una página con formularios de facturación"""
        try:
            form_detected = await self.page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    const inputs = document.querySelectorAll('input, select, textarea');

                    // Palabras clave que indican formularios de facturación
                    const invoiceKeywords = [
                        'rfc', 'folio', 'total', 'subtotal', 'fecha', 'cliente',
                        'nombre', 'direccion', 'email', 'telefono', 'cfdi',
                        'estacion', 'webid', 'web id', 'factura', 'invoice'
                    ];

                    let keywordMatches = 0;

                    // Verificar formularios
                    for (let form of forms) {
                        const formText = form.textContent?.toLowerCase() || '';
                        for (let keyword of invoiceKeywords) {
                            if (formText.includes(keyword)) {
                                keywordMatches++;
                            }
                        }
                    }

                    // Verificar inputs específicos
                    for (let input of inputs) {
                        const name = (input.name || '').toLowerCase();
                        const id = (input.id || '').toLowerCase();
                        const placeholder = (input.placeholder || '').toLowerCase();

                        for (let keyword of invoiceKeywords) {
                            if (name.includes(keyword) || id.includes(keyword) || placeholder.includes(keyword)) {
                                keywordMatches++;
                            }
                        }
                    }

                    // Si tenemos más de 2 coincidencias, probablemente es un formulario de facturación
                    return keywordMatches >= 2;
                }
            """)

            return form_detected

        except Exception as e:
            self._log(f"⚠️ Error detectando formularios: {e}")
            return False

    async def _fill_invoice_form_universal(self) -> Dict[str, Any]:
        """Llenar formulario de facturación de manera universal"""
        try:
            self._log("📝 Llenando formulario de facturación universalmente...")

            # Tomar screenshot del formulario
            await self._take_screenshot("form_filling_start")

            # Mapeo universal de campos
            field_mappings = {
                "rfc": ["rfc", "tax_id", "taxid", "fiscal", "identificador"],
                "email": ["email", "correo", "e-mail", "mail"],
                "nombre": ["nombre", "name", "cliente", "customer", "razon"],
                "folio": ["folio", "number", "ticket", "reference"],
                "total": ["total", "amount", "monto", "importe"],
                "fecha": ["fecha", "date", "day"],
                "uso_cfdi": ["uso", "cfdi", "usage"]
            }

            filled_fields = []

            for field_key, field_variations in field_mappings.items():
                field_value = getattr(self.invoice_data, field_key, None)

                if not field_value:
                    continue

                # Buscar campo en el formulario
                field_filled = await self._fill_field_by_variations(field_variations, field_value)

                if field_filled:
                    filled_fields.append(field_key)
                    self._log(f"✅ Campo llenado: {field_key} = {field_value}")

            await self._take_screenshot("form_filling_complete")

            self._log(f"📊 Campos llenados: {len(filled_fields)}/{len(field_mappings)}")

            return {
                "success": len(filled_fields) > 0,
                "filled_fields": filled_fields,
                "total_fields": len(field_mappings)
            }

        except Exception as e:
            self._log(f"❌ Error llenando formulario: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    async def _fill_field_by_variations(self, field_variations: List[str], value: str) -> bool:
        """Llenar campo usando múltiples variaciones de nombre"""
        for variation in field_variations:
            try:
                # Intentar diferentes selectores
                selectors = [
                    f"input[name*='{variation}']",
                    f"input[id*='{variation}']",
                    f"select[name*='{variation}']",
                    f"select[id*='{variation}']",
                    f"textarea[name*='{variation}']",
                    f"textarea[id*='{variation}']",
                    f"input[placeholder*='{variation}']"
                ]

                for selector in selectors:
                    try:
                        locator = self.page.locator(selector).first

                        if await locator.count() > 0 and await locator.is_visible():
                            await locator.fill(value)
                            return True

                    except Exception:
                        continue

            except Exception:
                continue

        return False

    async def _generate_invoice_universal(self) -> Dict[str, Any]:
        """Generar factura usando patrones universales"""
        try:
            self._log("⚡ Generando factura...")

            # Tomar screenshot antes de generar
            await self._take_screenshot("before_generation")

            # Buscar botón de generar/enviar
            generation_selectors = [
                "button:has-text('Generar')",
                "button:has-text('Generate')",
                "button:has-text('Enviar')",
                "button:has-text('Submit')",
                "input[type='submit']",
                "button:has-text('Crear Factura')",
                "button:has-text('Create Invoice')",
                "button[id*='generar']",
                "button[id*='generate']",
                "button[id*='submit']"
            ]

            for selector in generation_selectors:
                try:
                    locator = self.page.locator(selector).first

                    if await locator.count() > 0 and await locator.is_visible():
                        await locator.click(timeout=15000)

                        # Esperar procesamiento
                        await asyncio.sleep(3)

                        # Verificar si se generó la factura
                        if await self._verify_invoice_generation():
                            await self._take_screenshot("generation_success")
                            self._log(f"✅ Factura generada exitosamente")
                            return {"success": True, "method": selector}

                except Exception as e:
                    continue

            self._log("⚠️ No se pudo generar la factura automáticamente")
            return {"success": False, "error": "No generation button found"}

        except Exception as e:
            self._log(f"❌ Error generando factura: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    async def _verify_invoice_generation(self) -> bool:
        """Verificar si la factura se generó exitosamente"""
        try:
            # Buscar indicadores de éxito
            success_indicators = await self.page.evaluate("""
                () => {
                    const text = document.body.textContent?.toLowerCase() || '';
                    const successKeywords = [
                        'factura generada', 'invoice generated', 'exitosamente', 'successfully',
                        'pdf', 'descargar', 'download', 'ver factura', 'view invoice',
                        'folio fiscal', 'uuid', 'timbrado'
                    ];

                    return successKeywords.some(keyword => text.includes(keyword));
                }
            """)

            return success_indicators

        except Exception as e:
            return False

    async def _download_invoice_universal(self) -> Dict[str, Any]:
        """Descargar factura usando patrones universales"""
        try:
            self._log("📥 Intentando descargar factura...")

            # Buscar enlaces de descarga
            download_selectors = [
                "a:has-text('Descargar')",
                "a:has-text('Download')",
                "a:has-text('PDF')",
                "button:has-text('Descargar')",
                "button:has-text('Download')",
                "a[href*='.pdf']",
                "a[download]",
                "[onclick*='download']",
                "[href*='factura']",
                "[href*='invoice']"
            ]

            for selector in download_selectors:
                try:
                    locator = self.page.locator(selector).first

                    if await locator.count() > 0 and await locator.is_visible():
                        # Configurar listener para descarga
                        download_info = None

                        async with self.page.expect_download() as download_promise:
                            await locator.click(timeout=15000)
                            download = await download_promise

                        # Guardar descarga
                        download_path = self.screenshots_dir / f"invoice_{self.ticket_id}_{int(time.time())}.pdf"
                        await download.save_as(str(download_path))

                        self._log(f"✅ Factura descargada: {download_path.name}")

                        return {
                            "success": True,
                            "download_path": str(download_path),
                            "filename": download_path.name
                        }

                except Exception as e:
                    continue

            self._log("⚠️ No se encontró enlace de descarga")
            return {"success": False, "error": "No download link found"}

        except Exception as e:
            self._log(f"❌ Error descargando factura: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    async def _handle_download(self, download):
        """Manejar descarga automática"""
        self._log(f"📥 Descarga detectada: {download.suggested_filename}")

    async def _handle_dialog(self, dialog):
        """Manejar diálogos automáticamente"""
        self._log(f"💬 Dialog detectado: {dialog.message}")
        await dialog.accept()

    async def _take_screenshot(self, name: str) -> str:
        """Tomar screenshot con nombre descriptivo"""
        try:
            timestamp = int(time.time())
            screenshot_name = f"universal_{name}_{timestamp}.png"
            screenshot_path = self.screenshots_dir / screenshot_name

            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            self._log(f"📸 Screenshot: {screenshot_name}")

            return screenshot_name

        except Exception as e:
            self._log(f"⚠️ Error screenshot: {e}", "WARNING")
            return ""

    def _finalize_result(self, result: Dict[str, Any], message: str, success: bool = None) -> Dict[str, Any]:
        """Finalizar resultado con información completa"""
        if success is not None:
            result["success"] = success

        result.update({
            "message": message,
            "execution_log": self.execution_log,
            "discovered_patterns": self.discovered_patterns,
            "final_stage": self.current_stage.value,
            "portal_technology": self.portal_technology.value,
            "total_time": time.time() - self.start_time,
            "final_url": self.page.url if self.page else "unknown"
        })

        return result

    async def cleanup(self):
        """Limpiar recursos"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self._log("🧹 Recursos liberados")
        except Exception as e:
            self._log(f"⚠️ Error limpiando: {e}", "WARNING")