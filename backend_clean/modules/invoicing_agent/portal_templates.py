"""
Sistema de Templates para Portales de Facturación
Configuraciones predefinidas para diferentes tipos de portales
"""

from typing import Dict, List
from .playwright_automation_engine import PortalConfig, PortalType

class PortalTemplates:
    """Factory para configuraciones de portales específicos"""

    @staticmethod
    def get_litromil_config() -> PortalConfig:
        """Configuración específica para Litromil"""
        return PortalConfig(
            portal_type=PortalType.LITROMIL,
            base_urls=[
                "https://litromil.com",
                "http://litromil.dynalias.net:8088/litromil/"
            ],
            invoice_indicators=["factur", "invoic", "bill"],
            form_indicators=["estacion", "folio", "webid", "web id", "rfc"],
            success_indicators=["estación", "folio", "web id", "bienvenido", "¿cómo facturar?"],
            navigation_strategies=[
                {"name": "FACTURACIÓN nav link", "selector": "a:has-text('FACTURACIÓN')", "priority": 1},
                {"name": "Litromil portal direct", "selector": "a[href*='litromil.dynalias.net']", "priority": 2},
                {"name": "Click Aquí button", "selector": "a:has-text('Click Aquí!')", "priority": 3},
                {"name": "Facturar button", "selector": "#facturar", "priority": 4},
                {"name": "Any Facturación link", "selector": "a:has-text('Facturación')", "priority": 5}
            ],
            timeouts={
                "navigation": 30000,
                "element": 10000,
                "page_load": 30000
            }
        )

    @staticmethod
    def get_asp_net_generic_config() -> PortalConfig:
        """Configuración genérica para portales ASP.NET"""
        return PortalConfig(
            portal_type=PortalType.ASP_NET,
            base_urls=[],  # Se define por portal específico
            invoice_indicators=["factur", "invoic", "bill", "cobr"],
            form_indicators=["rfc", "folio", "total", "fecha", "cliente"],
            success_indicators=["generar factura", "datos fiscales", "información fiscal"],
            navigation_strategies=[
                {"name": "Facturar button", "selector": "#facturar, button[onclick*='facturar']", "priority": 1},
                {"name": "Facturación link", "selector": "a:has-text('Facturación')", "priority": 2},
                {"name": "Invoice menu", "selector": ".nav a:has-text('Factura')", "priority": 3},
                {"name": "PostBack facturar", "selector": "[onclick*=\"__doPostBack('facturar'\"]", "priority": 4}
            ],
            timeouts={
                "navigation": 25000,
                "element": 8000,
                "page_load": 25000
            }
        )

    @staticmethod
    def get_react_spa_config() -> PortalConfig:
        """Configuración para SPAs React"""
        return PortalConfig(
            portal_type=PortalType.REACT_SPA,
            base_urls=[],
            invoice_indicators=["invoice", "billing", "factur"],
            form_indicators=["taxId", "rfc", "amount", "date", "customer"],
            success_indicators=["invoice form", "billing information", "tax details"],
            navigation_strategies=[
                {"name": "Invoice button", "selector": "button:has-text('Invoice')", "priority": 1},
                {"name": "Billing link", "selector": "a[href*='billing'], a[href*='invoice']", "priority": 2},
                {"name": "Menu invoice", "selector": "[role='menuitem']:has-text('Invoice')", "priority": 3},
                {"name": "Nav invoice", "selector": "nav a:has-text('Invoice')", "priority": 4}
            ],
            timeouts={
                "navigation": 20000,
                "element": 10000,
                "page_load": 20000
            }
        )

    @staticmethod
    def get_wordpress_config() -> PortalConfig:
        """Configuración para sitios WordPress con plugins de facturación"""
        return PortalConfig(
            portal_type=PortalType.WORDPRESS,
            base_urls=[],
            invoice_indicators=["factur", "invoic", "bill", "woocommerce"],
            form_indicators=["billing_", "wc-", "customer", "order"],
            success_indicators=["checkout", "billing details", "order summary"],
            navigation_strategies=[
                {"name": "Checkout link", "selector": "a:has-text('Checkout')", "priority": 1},
                {"name": "Invoice link", "selector": "a:has-text('Invoice')", "priority": 2},
                {"name": "WooCommerce invoice", "selector": ".woocommerce a:has-text('Invoice')", "priority": 3},
                {"name": "My account invoice", "selector": ".my-account a:has-text('Invoice')", "priority": 4}
            ],
            timeouts={
                "navigation": 30000,
                "element": 12000,
                "page_load": 30000
            }
        )

    @staticmethod
    def detect_portal_type(url: str, page_content: str = "") -> PortalType:
        """Detectar tipo de portal basado en URL y contenido"""
        url_lower = url.lower()
        content_lower = page_content.lower()

        # Detección específica
        if "litromil" in url_lower:
            return PortalType.LITROMIL

        # Detección por tecnología
        if "__dopostback" in content_lower or "aspnet" in content_lower:
            return PortalType.ASP_NET

        if "react" in content_lower or "jsx" in content_lower or "_next" in url_lower:
            return PortalType.REACT_SPA

        if "wp-content" in url_lower or "wordpress" in content_lower:
            return PortalType.WORDPRESS

        # Por defecto
        return PortalType.CUSTOM

    @staticmethod
    def get_config_for_portal(portal_type: PortalType, custom_urls: List[str] = None) -> PortalConfig:
        """Obtener configuración para un tipo de portal específico"""
        config_map = {
            PortalType.LITROMIL: PortalTemplates.get_litromil_config,
            PortalType.ASP_NET: PortalTemplates.get_asp_net_generic_config,
            PortalType.REACT_SPA: PortalTemplates.get_react_spa_config,
            PortalType.WORDPRESS: PortalTemplates.get_wordpress_config
        }

        if portal_type in config_map:
            config = config_map[portal_type]()
            if custom_urls:
                config.base_urls = custom_urls + config.base_urls
            return config

        # Config por defecto para CUSTOM
        return PortalConfig(
            portal_type=PortalType.CUSTOM,
            base_urls=custom_urls or [],
            invoice_indicators=["factur", "invoic", "bill", "cobr"],
            form_indicators=["rfc", "folio", "total", "cliente"],
            success_indicators=["factur", "invoic"],
            navigation_strategies=[
                {"name": "Generic facturar", "selector": "button:has-text('Facturar'), a:has-text('Facturar')", "priority": 1},
                {"name": "Generic invoice", "selector": "button:has-text('Invoice'), a:has-text('Invoice')", "priority": 2}
            ],
            timeouts={
                "navigation": 30000,
                "element": 10000,
                "page_load": 30000
            }
        )

# Ejemplos de uso y configuraciones adicionales

class PortalConfigBuilder:
    """Builder para crear configuraciones personalizadas"""

    def __init__(self, portal_type: PortalType):
        self.config = PortalTemplates.get_config_for_portal(portal_type)

    def with_urls(self, urls: List[str]):
        self.config.base_urls = urls
        return self

    def with_indicators(self, invoice: List[str], form: List[str], success: List[str]):
        self.config.invoice_indicators = invoice
        self.config.form_indicators = form
        self.config.success_indicators = success
        return self

    def with_strategies(self, strategies: List[Dict[str, str]]):
        self.config.navigation_strategies = strategies
        return self

    def with_timeouts(self, timeouts: Dict[str, int]):
        self.config.timeouts = timeouts
        return self

    def build(self) -> PortalConfig:
        return self.config

# Registro de portales conocidos
KNOWN_PORTALS = {
    "litromil.com": {
        "type": PortalType.LITROMIL,
        "config_factory": PortalTemplates.get_litromil_config
    },
    "litromil.dynalias.net": {
        "type": PortalType.LITROMIL,
        "config_factory": PortalTemplates.get_litromil_config
    }
    # Agregar más portales según se vayan descubriendo
}

def get_config_for_url(url: str) -> PortalConfig:
    """Obtener configuración óptima para una URL específica"""

    # Verificar portales conocidos
    for domain, info in KNOWN_PORTALS.items():
        if domain in url.lower():
            return info["config_factory"]()

    # Detectar por patrones
    portal_type = PortalTemplates.detect_portal_type(url)
    return PortalTemplates.get_config_for_portal(portal_type, [url])