"""
Hybrid Processor - Paradigma URL-driven para México/LATAM con fallback a merchant.

Flujo principal:
1. Extraer URL de facturación del ticket
2. Validar legibilidad y calidad de la URL
3. Si URL no está clara → solicitar nueva foto
4. Si no hay URL → fallback a detección de merchant
5. Si ambos fallan → intervención humana
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .url_extractor import URLExtractor, ExtractedURL, URLType
from .merchant_classifier import classify_merchant
from .ocr_service import OCRService

logger = logging.getLogger(__name__)


class ProcessingResult(Enum):
    """Resultados posibles del procesamiento."""
    SUCCESS_URL = "success_url"
    SUCCESS_MERCHANT = "success_merchant"
    RETAKE_PHOTO = "retake_photo"
    HUMAN_INTERVENTION = "human_intervention"
    ERROR = "error"


class InterventionReason(Enum):
    """Razones para intervención humana."""
    ILLEGIBLE_TICKET = "illegible_ticket"
    NO_URL_FOUND = "no_url_found"
    NO_MERCHANT_FOUND = "no_merchant_found"
    UNKNOWN_BUSINESS = "unknown_business"
    OCR_FAILED = "ocr_failed"


@dataclass
class ProcessingOutput:
    """Resultado del procesamiento híbrido."""
    result: ProcessingResult
    facturacion_url: Optional[str] = None
    merchant_name: Optional[str] = None
    confidence: float = 0.0
    intervention_reason: Optional[InterventionReason] = None
    message: str = ""
    extracted_text: str = ""
    extracted_urls: List[ExtractedURL] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "facturacion_url": self.facturacion_url,
            "merchant_name": self.merchant_name,
            "confidence": self.confidence,
            "intervention_reason": self.intervention_reason.value if self.intervention_reason else None,
            "message": self.message,
            "extracted_text": self.extracted_text,
            "extracted_urls": [url.to_dict() for url in self.extracted_urls] if self.extracted_urls else [],
            "retry_count": self.retry_count
        }


class HybridProcessor:
    """
    Procesador híbrido URL-driven con fallback a merchant.

    Implementa el paradigma LATAM donde cada negocio imprime
    su propia URL de facturación en el ticket.
    """

    def __init__(self):
        self.url_extractor = URLExtractor()
        # No necesitamos instanciar el classifier, usamos la función global
        self.ocr_service = OCRService()

        # Configuración de calidad mínima
        self.min_url_confidence = 0.7
        self.min_merchant_confidence = 0.8
        self.min_text_quality = 0.6

        # Límites de reintento
        self.max_retries = 2

    async def process_ticket(self, image_path: str, retry_count: int = 0) -> ProcessingOutput:
        """
        Procesar ticket con enfoque URL-driven.

        Args:
            image_path: Ruta a la imagen del ticket
            retry_count: Número de reintentos previos

        Returns:
            Resultado del procesamiento
        """
        logger.info(f"Procesando ticket: {image_path} (intento {retry_count + 1})")

        try:
            # Paso 1: Extraer texto con OCR o leer archivo directo si es .txt
            if image_path.endswith('.txt'):
                # Para pruebas: leer directamente el archivo de texto
                with open(image_path, 'r', encoding='utf-8') as f:
                    extracted_text = f.read()
                text_confidence = 1.0  # Texto directo, alta confianza
            else:
                # Usar OCR para imágenes reales
                ocr_result = await self.ocr_service.extract_text(image_path)

                if ocr_result.error:
                    return ProcessingOutput(
                        result=ProcessingResult.ERROR,
                        intervention_reason=InterventionReason.OCR_FAILED,
                        message=f"Error en OCR: {ocr_result.error}",
                        retry_count=retry_count
                    )

                extracted_text = ocr_result.text
                text_confidence = ocr_result.confidence

            # Paso 2: Validar calidad del texto extraído
            if text_confidence < self.min_text_quality:
                if retry_count < self.max_retries:
                    return ProcessingOutput(
                        result=ProcessingResult.RETAKE_PHOTO,
                        message=f"Calidad del texto muy baja ({text_confidence:.2f}). Por favor tome otra foto más clara.",
                        extracted_text=extracted_text,
                        retry_count=retry_count
                    )
                else:
                    return ProcessingOutput(
                        result=ProcessingResult.HUMAN_INTERVENTION,
                        intervention_reason=InterventionReason.ILLEGIBLE_TICKET,
                        message="El ticket no es legible después de varios intentos. Requiere intervención humana.",
                        extracted_text=extracted_text,
                        retry_count=retry_count
                    )

            # Paso 3: Extraer URLs de facturación (enfoque principal)
            url_result = self._process_with_urls(extracted_text)
            if url_result.result == ProcessingResult.SUCCESS_URL:
                url_result.extracted_text = extracted_text
                url_result.retry_count = retry_count
                return url_result

            # Paso 4: Si URL no es clara, solicitar nueva foto
            if url_result.result == ProcessingResult.RETAKE_PHOTO and retry_count < self.max_retries:
                return ProcessingOutput(
                    result=ProcessingResult.RETAKE_PHOTO,
                    message="La URL de facturación no está clara. Por favor tome otra foto enfocando la URL.",
                    extracted_text=extracted_text,
                    retry_count=retry_count
                )

            # Paso 5: Fallback a detección de merchant
            logger.info("URL no encontrada o no clara, intentando detección de merchant")
            merchant_result = await self._process_with_merchant(extracted_text)
            if merchant_result.result == ProcessingResult.SUCCESS_MERCHANT:
                merchant_result.extracted_text = extracted_text
                merchant_result.retry_count = retry_count
                return merchant_result

            # Paso 6: Intervención humana
            return ProcessingOutput(
                result=ProcessingResult.HUMAN_INTERVENTION,
                intervention_reason=InterventionReason.UNKNOWN_BUSINESS,
                message="No se pudo extraer URL ni identificar el merchant. Requiere intervención humana.",
                extracted_text=extracted_text,
                retry_count=retry_count
            )

        except Exception as e:
            logger.error(f"Error procesando ticket: {e}")
            return ProcessingOutput(
                result=ProcessingResult.ERROR,
                message=f"Error interno: {str(e)}",
                retry_count=retry_count
            )

    def _process_with_urls(self, text: str) -> ProcessingOutput:
        """Procesar usando extracción de URLs."""
        try:
            # Extraer URLs
            extracted_urls = self.url_extractor.extract_urls(text)
            best_url = self.url_extractor.get_best_facturacion_url(text)

            if best_url and best_url.confidence >= self.min_url_confidence:
                logger.info(f"URL encontrada: {best_url.url} (confianza: {best_url.confidence:.3f})")

                return ProcessingOutput(
                    result=ProcessingResult.SUCCESS_URL,
                    facturacion_url=best_url.url,
                    merchant_name=best_url.merchant_hint,
                    confidence=best_url.confidence,
                    message=f"URL de facturación extraída: {best_url.url}",
                    extracted_urls=extracted_urls
                )

            # URL encontrada pero con baja confianza
            if best_url and best_url.confidence < self.min_url_confidence:
                logger.warning(f"URL encontrada pero con baja confianza: {best_url.confidence:.3f}")
                return ProcessingOutput(
                    result=ProcessingResult.RETAKE_PHOTO,
                    message=f"URL detectada pero poco clara (confianza: {best_url.confidence:.2f}). Enfoque mejor la URL.",
                    extracted_urls=extracted_urls
                )

            # No se encontró URL
            logger.info("No se encontró URL de facturación en el ticket")
            return ProcessingOutput(
                result=ProcessingResult.HUMAN_INTERVENTION,
                intervention_reason=InterventionReason.NO_URL_FOUND,
                message="No se encontró URL de facturación en el ticket.",
                extracted_urls=extracted_urls
            )

        except Exception as e:
            logger.error(f"Error en extracción de URL: {e}")
            return ProcessingOutput(
                result=ProcessingResult.ERROR,
                message=f"Error extrayendo URL: {str(e)}"
            )

    async def _process_with_merchant(self, text: str) -> ProcessingOutput:
        """Procesar usando clasificación de merchant (fallback)."""
        try:
            # Clasificar merchant
            classification = await classify_merchant(text)

            if classification.confidence >= self.min_merchant_confidence:
                logger.info(f"Merchant identificado: {classification.merchant_name} (confianza: {classification.confidence:.3f})")

                # Buscar URL conocida para este merchant
                known_url = self._get_known_merchant_url(classification.merchant_name)

                return ProcessingOutput(
                    result=ProcessingResult.SUCCESS_MERCHANT,
                    facturacion_url=known_url,
                    merchant_name=classification.merchant_name,
                    confidence=classification.confidence,
                    message=f"Merchant identificado: {classification.merchant_name}"
                )

            # Merchant no identificado con suficiente confianza
            logger.warning(f"Merchant con baja confianza: {classification.confidence:.3f}")
            return ProcessingOutput(
                result=ProcessingResult.HUMAN_INTERVENTION,
                intervention_reason=InterventionReason.NO_MERCHANT_FOUND,
                message=f"Merchant no identificado claramente (confianza: {classification.confidence:.2f})"
            )

        except Exception as e:
            logger.error(f"Error en clasificación de merchant: {e}")
            return ProcessingOutput(
                result=ProcessingResult.ERROR,
                message=f"Error clasificando merchant: {str(e)}"
            )

    def _get_known_merchant_url(self, merchant_name: str) -> Optional[str]:
        """Obtener URL conocida para merchants identificados."""
        # URLs conocidas para merchants grandes
        known_urls = {
            'OXXO': 'https://factura.oxxo.com',
            'WALMART': 'https://factura.walmart.com.mx',
            'SORIANA': 'https://facturacion.soriana.com',
            'COSTCO': 'https://facturaelectronica.costco.com.mx',
            'HOME_DEPOT': 'https://homedepot.com.mx/facturacion',
            'CHEDRAUI': 'https://factura.chedraui.com.mx',
            '7_ELEVEN': 'https://facturacion.7-eleven.com.mx',
            'FARMACIA_DEL_AHORRO': 'https://facturacion.fahorro.com.mx',
            'PEMEX': 'https://factura.pemex.com'
        }

        return known_urls.get(merchant_name.upper())

    def get_processing_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del procesador."""
        return {
            "url_extractor_stats": {
                "min_confidence": self.min_url_confidence,
                "known_domains_count": len(self.url_extractor.known_domains)
            },
            "merchant_classifier_stats": {
                "min_confidence": self.min_merchant_confidence,
                "pattern_count": len(self.merchant_classifier.patterns)
            },
            "quality_thresholds": {
                "min_text_quality": self.min_text_quality,
                "max_retries": self.max_retries
            }
        }


# Instancia global
hybrid_processor = HybridProcessor()


# Función de conveniencia
async def process_ticket_image(image_path: str, retry_count: int = 0) -> Dict[str, Any]:
    """
    Función simple para procesar imagen de ticket.

    Args:
        image_path: Ruta a la imagen
        retry_count: Número de reintento

    Returns:
        Resultado del procesamiento como diccionario
    """
    result = await hybrid_processor.process_ticket(image_path, retry_count)
    return result.to_dict()


async def test_main():
    # Test del procesador híbrido
    test_cases = [
        "test_tickets/gas_station_clear.jpg",
        "test_tickets/oxxo_blurry.jpg",
        "test_tickets/local_store_no_url.jpg",
        "test_tickets/unreadable.jpg"
    ]

    processor = HybridProcessor()

    print("=== Test Hybrid Processor ===")
    for image_path in test_cases:
        print(f"\n--- Procesando: {image_path} ---")

        result = await processor.process_ticket(image_path)

        print(f"Resultado: {result.result.value}")
        print(f"URL: {result.facturacion_url or 'N/A'}")
        print(f"Merchant: {result.merchant_name or 'N/A'}")
        print(f"Confianza: {result.confidence:.3f}")
        print(f"Mensaje: {result.message}")

        if result.intervention_reason:
            print(f"Razón intervención: {result.intervention_reason.value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_main())