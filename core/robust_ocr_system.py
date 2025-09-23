"""
Sistema robusto de OCR con fallbacks inteligentes
Implementa los principios de la documentación oficial
"""
import logging
import base64
import os
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class OCRBackend(Enum):
    GOOGLE_VISION = "google_vision"
    AWS_TEXTRACT = "aws_textract"
    TESSERACT = "tesseract"

@dataclass
class OCRResult:
    text: str
    confidence: float
    backend: OCRBackend
    processing_time: float
    error: Optional[str] = None

class RobustOCRSystem:
    """
    Sistema de OCR robusto con fallbacks automáticos
    Principios:
    1. Si confidence < 70%, reintentar con otro backend
    2. Validar merchant_name contra catálogo interno
    3. Guardar texto crudo, validado y confianza
    """

    def __init__(self):
        self.backends = self._initialize_backends()
        self.min_confidence = 70.0
        self.max_retries = 3

    def _initialize_backends(self) -> List[OCRBackend]:
        """Inicializa backends disponibles según variables de entorno"""
        available_backends = []

        # Google Vision (principal)
        if os.getenv("GOOGLE_API_KEY"):
            available_backends.append(OCRBackend.GOOGLE_VISION)

        # AWS Textract (fallback)
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            available_backends.append(OCRBackend.AWS_TEXTRACT)

        # Tesseract (último recurso)
        available_backends.append(OCRBackend.TESSERACT)

        logger.info(f"🔍 OCR backends disponibles: {[b.value for b in available_backends]}")
        return available_backends

    def extract_text_with_fallback(self, image_data: bytes) -> OCRResult:
        """
        Extrae texto con sistema de fallback inteligente

        Args:
            image_data: Datos binarios de la imagen

        Returns:
            OCRResult con el mejor resultado obtenido
        """
        best_result = None

        for backend in self.backends:
            try:
                logger.info(f"🔍 Intentando OCR con {backend.value}")
                start_time = time.time()

                result = self._process_with_backend(image_data, backend)
                processing_time = time.time() - start_time

                ocr_result = OCRResult(
                    text=result["text"],
                    confidence=result["confidence"],
                    backend=backend,
                    processing_time=processing_time
                )

                logger.info(f"✅ {backend.value}: {ocr_result.confidence:.1f}% confianza")

                # Si es suficientemente bueno, lo usamos
                if ocr_result.confidence >= self.min_confidence:
                    logger.info(f"🎯 Resultado aceptable con {backend.value}")
                    return ocr_result

                # Guardar el mejor hasta ahora
                if best_result is None or ocr_result.confidence > best_result.confidence:
                    best_result = ocr_result

            except Exception as e:
                logger.error(f"❌ Error en {backend.value}: {e}")
                continue

        # Si llegamos aquí, no tuvimos un resultado perfecto
        if best_result:
            logger.warning(f"⚠️ Usando mejor resultado disponible: {best_result.backend.value} ({best_result.confidence:.1f}%)")
            return best_result
        else:
            # Último recurso: resultado vacío con error
            return OCRResult(
                text="",
                confidence=0.0,
                backend=OCRBackend.TESSERACT,
                processing_time=0.0,
                error="Todos los backends de OCR fallaron"
            )

    def _process_with_backend(self, image_data: bytes, backend: OCRBackend) -> Dict:
        """Procesa imagen con un backend específico"""

        if backend == OCRBackend.GOOGLE_VISION:
            return self._google_vision_ocr(image_data)
        elif backend == OCRBackend.AWS_TEXTRACT:
            return self._aws_textract_ocr(image_data)
        elif backend == OCRBackend.TESSERACT:
            return self._tesseract_ocr(image_data)
        else:
            raise ValueError(f"Backend no soportado: {backend}")

    def _google_vision_ocr(self, image_data: bytes) -> Dict:
        """OCR con Google Vision API"""
        try:
            from google.cloud import vision

            client = vision.ImageAnnotatorClient()
            image = vision.Image(content=image_data)

            response = client.text_detection(image=image)

            if response.error.message:
                raise Exception(response.error.message)

            if response.text_annotations:
                text = response.text_annotations[0].description
                # Google Vision no da confidence directo, estimamos
                confidence = 85.0 if len(text.strip()) > 10 else 60.0

                return {
                    "text": text.strip(),
                    "confidence": confidence
                }
            else:
                return {"text": "", "confidence": 0.0}

        except ImportError:
            raise Exception("google-cloud-vision no está instalado")
        except Exception as e:
            raise Exception(f"Error en Google Vision: {e}")

    def _aws_textract_ocr(self, image_data: bytes) -> Dict:
        """OCR con AWS Textract"""
        try:
            import boto3

            textract = boto3.client('textract')

            response = textract.detect_document_text(
                Document={'Bytes': image_data}
            )

            text_blocks = []
            confidence_scores = []

            for item in response['Blocks']:
                if item['BlockType'] == 'LINE':
                    text_blocks.append(item['Text'])
                    confidence_scores.append(item['Confidence'])

            text = '\n'.join(text_blocks)
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

            return {
                "text": text.strip(),
                "confidence": avg_confidence
            }

        except ImportError:
            raise Exception("boto3 no está instalado")
        except Exception as e:
            raise Exception(f"Error en AWS Textract: {e}")

    def _tesseract_ocr(self, image_data: bytes) -> Dict:
        """OCR con Tesseract (último recurso)"""
        try:
            import pytesseract
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image, lang='spa')

            # Tesseract no da confidence, estimamos basado en longitud
            confidence = min(50.0 + len(text.strip()) * 0.5, 80.0)

            return {
                "text": text.strip(),
                "confidence": confidence
            }

        except ImportError:
            raise Exception("pytesseract no está instalado")
        except Exception as e:
            raise Exception(f"Error en Tesseract: {e}")

    def validate_merchant(self, text: str) -> Dict:
        """
        Valida merchant_name contra catálogo interno

        Args:
            text: Texto extraído por OCR

        Returns:
            Dict con merchant validado y confianza
        """
        # Catálogo de merchants conocidos
        known_merchants = {
            "oxxo": ["oxxo", "tiendas oxxo"],
            "walmart": ["walmart", "wal mart", "walmex"],
            "soriana": ["soriana", "tiendas soriana"],
            "coppel": ["coppel", "tiendas coppel"],
            "seven_eleven": ["seven eleven", "7 eleven", "7-eleven"],
            "gasolinera_litro_mil": ["gasolinera litro mil", "litro mil", "glm"]
        }

        text_lower = text.lower()

        for merchant_id, variations in known_merchants.items():
            for variation in variations:
                if variation in text_lower:
                    confidence = len(variation) / len(text_lower) * 100
                    return {
                        "merchant_id": merchant_id,
                        "merchant_name": variation.title(),
                        "confidence": min(confidence, 95.0),
                        "validated": True
                    }

        # Si no se encontró, extraer posible nombre
        lines = text.split('\n')
        possible_name = ""
        for line in lines[:3]:  # Primeras 3 líneas
            if len(line.strip()) > 5:  # Línea con contenido
                possible_name = line.strip()
                break

        return {
            "merchant_id": "unknown",
            "merchant_name": possible_name,
            "confidence": 30.0,
            "validated": False
        }