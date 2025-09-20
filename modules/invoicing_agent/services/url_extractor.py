"""
URL Extractor - Extracción de URLs de facturación desde tickets.

Paradigma URL-driven para México/LATAM:
En lugar de identificar merchants, extraer directamente las URLs de facturación
que aparecen impresas en los tickets.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class URLType(Enum):
    """Tipos de URLs encontradas."""
    FACTURACION = "facturacion"
    PORTAL_FISCAL = "portal_fiscal"
    CFDI = "cfdi"
    GENERIC_WEB = "generic_web"
    UNKNOWN = "unknown"


@dataclass
class ExtractedURL:
    """URL extraída de un ticket."""
    url: str
    url_type: URLType
    confidence: float
    context: str  # Texto alrededor de la URL
    merchant_hint: Optional[str] = None  # Nombre del merchant si se puede inferir
    extracted_method: str = "regex"
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "url_type": self.url_type.value,
            "confidence": self.confidence,
            "context": self.context,
            "merchant_hint": self.merchant_hint,
            "extracted_method": self.extracted_method,
            "metadata": self.metadata or {}
        }


class URLExtractor:
    """
    Extractor de URLs de facturación desde texto de tickets.

    Enfoque URL-driven para México/LATAM donde cada merchant
    imprime su propia URL de facturación en el ticket.
    """

    def __init__(self):
        # Patrones para identificar URLs de facturación
        self.facturacion_patterns = [
            # Patrones específicos de facturación
            r'https?://[^\s]*factura[^\s]*',
            r'https?://[^\s]*billing[^\s]*',
            r'https?://[^\s]*invoice[^\s]*',
            r'https?://[^\s]*cfdi[^\s]*',
            r'https?://[^\s]*fiscal[^\s]*',

            # Patrones de dominios conocidos
            r'https?://factura\.[a-zA-Z0-9\-\.]+',
            r'https?://[a-zA-Z0-9\-]+\.factura\.[a-zA-Z0-9\-\.]+',

            # Patrones con palabras clave en español
            r'https?://[^\s]*facturacion[^\s]*',
            r'https?://[^\s]*facturaci[oó]n[^\s]*',
        ]

        # Patrones de contexto que indican URLs de facturación
        self.context_patterns = [
            r'(?:para\s+)?facturar\s+(?:en|visita|visite?)?:?\s*(https?://[^\s]+)',
            r'facturaci[oó]n\s+(?:en|web)?:?\s*(https?://[^\s]+)',
            r'(?:portal\s+)?(?:de\s+)?facturaci[oó]n:?\s*(https?://[^\s]+)',
            r'solicita\s+tu\s+factura\s+en:?\s*(https?://[^\s]+)',
            r'(?:para\s+)?(?:tu\s+)?(?:cfdi|factura)\s+(?:en|web)?:?\s*(https?://[^\s]+)',
        ]

        # Dominios conocidos de facturación México
        self.known_domains = {
            'factura.pemex.com': 'PEMEX',
            'factura.oxxo.com': 'OXXO',
            'factura.walmart.com.mx': 'WALMART',
            'facturaelectronica.costco.com.mx': 'COSTCO',
            'facturacion.soriana.com': 'SORIANA',
            'homedepot.com.mx/facturacion': 'HOME_DEPOT',
            'factura.chedraui.com.mx': 'CHEDRAUI',
            'facturacion.7-eleven.com.mx': '7_ELEVEN',
            'facturacion.fahorro.com.mx': 'FARMACIA_DEL_AHORRO'
        }

    def extract_urls(self, text: str) -> List[ExtractedURL]:
        """
        Extraer todas las URLs de facturación de un texto.

        Args:
            text: Texto extraído del ticket por OCR

        Returns:
            Lista de URLs extraídas con metadatos
        """
        extracted_urls = []
        text_lines = text.split('\n')
        full_text = ' '.join(text_lines)

        # Método 1: Buscar URLs con contexto específico
        context_urls = self._extract_with_context(full_text)
        extracted_urls.extend(context_urls)

        # Método 2: Buscar URLs con patrones de facturación
        pattern_urls = self._extract_with_patterns(full_text)
        extracted_urls.extend(pattern_urls)

        # Método 3: Buscar URLs que pueden estar separadas por saltos de línea
        multiline_urls = self._extract_multiline_urls(text_lines, full_text)
        extracted_urls.extend(multiline_urls)

        # Método 4: Buscar cualquier URL y clasificar
        generic_urls = self._extract_generic_urls(full_text)
        classified_urls = self._classify_urls(generic_urls, full_text)
        extracted_urls.extend(classified_urls)

        # Eliminar duplicados y ordenar por confianza
        unique_urls = self._deduplicate_urls(extracted_urls)
        return sorted(unique_urls, key=lambda x: x.confidence, reverse=True)

    def _extract_with_context(self, text: str) -> List[ExtractedURL]:
        """Extraer URLs usando patrones de contexto."""
        urls = []

        for pattern in self.context_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.group(1)
                context = match.group(0)

                # Limpiar URL
                url = self._clean_url(url)
                if url:
                    extracted_url = ExtractedURL(
                        url=url,
                        url_type=URLType.FACTURACION,
                        confidence=0.95,  # Alta confianza por contexto
                        context=context,
                        merchant_hint=self._get_merchant_hint(url),
                        extracted_method="context_pattern"
                    )
                    urls.append(extracted_url)

        return urls

    def _extract_with_patterns(self, text: str) -> List[ExtractedURL]:
        """Extraer URLs usando patrones específicos de facturación."""
        urls = []

        for pattern in self.facturacion_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.group(0)
                url = self._clean_url(url)

                if url:
                    # Buscar contexto alrededor
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()

                    extracted_url = ExtractedURL(
                        url=url,
                        url_type=URLType.FACTURACION,
                        confidence=0.85,  # Buena confianza por patrón
                        context=context,
                        merchant_hint=self._get_merchant_hint(url),
                        extracted_method="facturacion_pattern"
                    )
                    urls.append(extracted_url)

        return urls

    def _extract_multiline_urls(self, text_lines: List[str], full_text: str) -> List[ExtractedURL]:
        """Extraer URLs que pueden estar separadas por saltos de línea."""
        urls = []

        for i, line in enumerate(text_lines):
            line = line.strip()

            # Buscar líneas que sugieren URLs de facturación pero sin el protocolo
            if any(keyword in line.lower() for keyword in ['facture en', 'facturación:', 'portal:']):
                # Buscar en las siguientes líneas por URLs o dominios
                for j in range(i + 1, min(i + 4, len(text_lines))):  # Buscar en las próximas 3 líneas
                    next_line = text_lines[j].strip()

                    # Buscar dominios que parecen URLs de facturación
                    domain_patterns = [
                        r'[a-zA-Z0-9\-]+\.(?:com|mx|net|org)(?:\.[a-zA-Z]{2,3})?',  # dominios básicos
                        r'factura[a-zA-Z0-9\-]*\.[a-zA-Z0-9\-\.]+',  # dominios con factura
                        r'[a-zA-Z0-9\-]+\.info[a-zA-Z0-9\-]*\.[a-zA-Z0-9\-\.]+',  # dominios con info
                    ]

                    for pattern in domain_patterns:
                        matches = re.finditer(pattern, next_line, re.IGNORECASE)
                        for match in matches:
                            domain = match.group(0)

                            # Reconstruir URL completa
                            if not domain.startswith('http'):
                                reconstructed_url = f"https://{domain}"
                            else:
                                reconstructed_url = domain

                            # Limpiar URL
                            clean_url = self._clean_url(reconstructed_url)
                            if clean_url:
                                # Crear contexto combinando las líneas
                                context_lines = text_lines[max(0, i-1):min(len(text_lines), j+2)]
                                context = ' '.join(line.strip() for line in context_lines if line.strip())

                                extracted_url = ExtractedURL(
                                    url=clean_url,
                                    url_type=URLType.FACTURACION,
                                    confidence=0.90,  # Alta confianza por contexto específico
                                    context=context,
                                    merchant_hint=self._get_merchant_hint(clean_url),
                                    extracted_method="multiline_reconstruction"
                                )
                                urls.append(extracted_url)

        return urls

    def _extract_generic_urls(self, text: str) -> List[str]:
        """Extraer todas las URLs genéricas del texto."""
        # Patrón para URLs completas
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:]'

        urls = []
        matches = re.finditer(url_pattern, text, re.IGNORECASE)
        for match in matches:
            url = self._clean_url(match.group(0))
            if url:
                urls.append(url)

        return list(set(urls))  # Eliminar duplicados

    def _classify_urls(self, urls: List[str], text: str) -> List[ExtractedURL]:
        """Clasificar URLs genéricas para determinar si son de facturación."""
        classified = []

        for url in urls:
            url_type, confidence = self._classify_single_url(url)

            if url_type != URLType.UNKNOWN:
                # Buscar contexto de la URL en el texto
                url_pos = text.find(url)
                if url_pos != -1:
                    start = max(0, url_pos - 30)
                    end = min(len(text), url_pos + len(url) + 30)
                    context = text[start:end].strip()
                else:
                    context = url

                extracted_url = ExtractedURL(
                    url=url,
                    url_type=url_type,
                    confidence=confidence,
                    context=context,
                    merchant_hint=self._get_merchant_hint(url),
                    extracted_method="classification"
                )
                classified.append(extracted_url)

        return classified

    def _classify_single_url(self, url: str) -> tuple[URLType, float]:
        """Clasificar una URL individual."""
        url_lower = url.lower()

        # Verificar dominios conocidos
        for domain, merchant in self.known_domains.items():
            if domain in url_lower:
                return URLType.FACTURACION, 0.95

        # Verificar palabras clave en la URL
        facturacion_keywords = [
            'factura', 'billing', 'invoice', 'cfdi', 'fiscal',
            'facturacion', 'facturación'
        ]

        for keyword in facturacion_keywords:
            if keyword in url_lower:
                return URLType.FACTURACION, 0.75

        # Verificar patrones de subdominios
        if re.search(r'factura\.|\.factura', url_lower):
            return URLType.PORTAL_FISCAL, 0.70

        # URL genérica
        return URLType.GENERIC_WEB, 0.30

    def _get_merchant_hint(self, url: str) -> Optional[str]:
        """Obtener pista del merchant desde la URL."""
        url_lower = url.lower()

        # Verificar dominios conocidos
        for domain, merchant in self.known_domains.items():
            if domain in url_lower:
                return merchant

        # Extraer posible nombre del dominio
        try:
            # Extraer dominio principal
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            domain_parts = parsed.netloc.split('.')

            # Buscar parte principal del dominio
            for part in domain_parts:
                if part not in ['www', 'factura', 'facturacion', 'com', 'mx', 'net', 'org']:
                    return part.upper()
        except:
            pass

        return None

    def _clean_url(self, url: str) -> Optional[str]:
        """Limpiar y validar URL."""
        if not url:
            return None

        # Eliminar caracteres de cierre comunes
        url = re.sub(r'[.,;:)\]}]+$', '', url.strip())

        # Verificar que sea una URL válida
        if not re.match(r'https?://', url, re.IGNORECASE):
            return None

        # Verificar longitud mínima
        if len(url) < 10:
            return None

        return url

    def _deduplicate_urls(self, urls: List[ExtractedURL]) -> List[ExtractedURL]:
        """Eliminar URLs duplicadas, manteniendo la de mayor confianza."""
        seen_urls = {}

        for extracted_url in urls:
            url = extracted_url.url
            if url not in seen_urls or extracted_url.confidence > seen_urls[url].confidence:
                seen_urls[url] = extracted_url

        return list(seen_urls.values())

    def get_best_facturacion_url(self, text: str) -> Optional[ExtractedURL]:
        """
        Obtener la mejor URL de facturación de un ticket.

        Args:
            text: Texto del ticket

        Returns:
            La URL de facturación más probable o None
        """
        urls = self.extract_urls(text)

        # Filtrar solo URLs de facturación
        facturacion_urls = [
            url for url in urls
            if url.url_type in [URLType.FACTURACION, URLType.PORTAL_FISCAL]
            and url.confidence >= 0.7
        ]

        if facturacion_urls:
            return facturacion_urls[0]  # Ya están ordenadas por confianza

        return None


# Instancia global
url_extractor = URLExtractor()


# Función de conveniencia
def extract_facturacion_url(text: str) -> Optional[str]:
    """
    Función simple para extraer URL de facturación.

    Args:
        text: Texto del ticket

    Returns:
        URL de facturación o None
    """
    best_url = url_extractor.get_best_facturacion_url(text)
    return best_url.url if best_url else None


if __name__ == "__main__":
    # Test del extractor
    test_tickets = [
        """
        ABARROTES LUPITA
        RFC: ALU123456789
        Total: $45.50
        Para facturar visita: https://factura.lupita.mx
        """,
        """
        GASOLINERIA LITRO MIL S.A. DE C.V.
        RFC: GLM090710TVO
        CLAVE CLIENTE PEMEX: 0000115287
        Portal de facturación: https://factura.litromil.com.mx
        """,
        """
        OXXO TIENDA #1234
        RFC: OXX970814HS9
        Solicita tu factura en: https://factura.oxxo.com
        """,
        """
        TIENDA LOCAL SIN URL
        RFC: TLS123456789
        Solo efectivo
        """
    ]

    extractor = URLExtractor()

    print("=== Test URL Extractor ===")
    for i, ticket_text in enumerate(test_tickets, 1):
        print(f"\n--- Ticket {i} ---")

        urls = extractor.extract_urls(ticket_text)

        if urls:
            for url in urls:
                print(f"URL: {url.url}")
                print(f"Tipo: {url.url_type.value}")
                print(f"Confianza: {url.confidence:.3f}")
                print(f"Merchant: {url.merchant_hint or 'N/A'}")
        else:
            print("No se encontraron URLs de facturación")

    print(f"\n=== Mejor URL por ticket ===")
    for i, ticket_text in enumerate(test_tickets, 1):
        best_url = extractor.get_best_facturacion_url(ticket_text)
        if best_url:
            print(f"Ticket {i}: {best_url.url} ({best_url.merchant_hint})")
        else:
            print(f"Ticket {i}: Sin URL de facturación")