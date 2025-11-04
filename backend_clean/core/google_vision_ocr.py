"""
Google Cloud Vision OCR Integration

Integración principal para extracción de texto de tickets usando Google Cloud Vision API.
Reemplaza la dependencia de OpenAI/GPT-4 Vision para OCR.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Google Cloud Vision
try:
    from google.cloud import vision
    from google.oauth2 import service_account
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    vision = None

logger = logging.getLogger(__name__)

@dataclass
class OCRResult:
    """Resultado de extracción OCR"""
    text: str
    confidence: float
    bounding_boxes: List[Dict]
    detected_language: str
    processing_time_ms: int
    raw_response: Dict[str, Any]

@dataclass
class ExtractedData:
    """Datos estructurados extraídos del ticket"""
    rfc: Optional[str] = None
    total: Optional[str] = None
    fecha: Optional[str] = None
    folio: Optional[str] = None
    merchant_name: Optional[str] = None
    items: List[Dict] = None
    confidence_score: float = 0.0

class GoogleVisionOCR:
    """Clase principal para OCR con Google Cloud Vision"""

    def __init__(self, credentials_path: str = None):
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Inicializar cliente de Google Vision"""

        if not VISION_AVAILABLE:
            logger.warning("⚠️ Google Cloud Vision no disponible. Instalar: pip install google-cloud-vision")
            return False

        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                # Usar archivo de credenciales
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                self.client = vision.ImageAnnotatorClient(credentials=credentials)
                logger.info("✅ Google Vision client inicializado con credenciales")

            elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                # Usar variable de entorno
                self.client = vision.ImageAnnotatorClient()
                logger.info("✅ Google Vision client inicializado con env vars")

            else:
                logger.warning("⚠️ Credenciales de Google Cloud no encontradas")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Error inicializando Google Vision: {e}")
            return False

    def is_available(self) -> bool:
        """Verificar si el servicio está disponible"""
        return self.client is not None

    async def extract_text_from_image(self, image_path: str) -> OCRResult:
        """Extraer texto de imagen usando Google Vision"""

        if not self.is_available():
            raise Exception("Google Vision client no disponible")

        start_time = datetime.now()

        try:
            # Leer imagen
            with open(image_path, 'rb') as image_file:
                content = image_file.read()

            # Crear objeto imagen para Vision API
            image = vision.Image(content=content)

            # Configurar features para OCR completo
            features = [
                vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION),
                vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            ]

            # Configurar contexto de imagen
            image_context = vision.ImageContext(
                language_hints=['es', 'en']  # Español e inglés
            )

            # Realizar OCR
            request = vision.AnnotateImageRequest(
                image=image,
                features=features,
                image_context=image_context
            )

            response = self.client.annotate_image(request=request)

            if response.error.message:
                raise Exception(f"Google Vision error: {response.error.message}")

            # Procesar resultados
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Obtener texto completo
            full_text = ""
            confidence = 0.0
            bounding_boxes = []

            if response.full_text_annotation:
                full_text = response.full_text_annotation.text

                # Calcular confianza promedio
                confidences = []
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        confidences.append(block.confidence)

                        # Extraer bounding boxes
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = ''.join([symbol.text for symbol in word.symbols])
                                bounding_boxes.append({
                                    'text': word_text,
                                    'confidence': word.confidence,
                                    'bounding_box': self._extract_bounding_box(word.bounding_box)
                                })

                confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Detectar idioma
            detected_language = 'es'  # Default español
            if response.text_annotations:
                # Simple heurística para detectar idioma
                text_sample = full_text[:200].lower()
                english_words = ['total', 'date', 'invoice', 'receipt', 'tax']
                spanish_words = ['total', 'fecha', 'factura', 'recibo', 'iva']

                english_count = sum(1 for word in english_words if word in text_sample)
                spanish_count = sum(1 for word in spanish_words if word in text_sample)

                if english_count > spanish_count:
                    detected_language = 'en'

            result = OCRResult(
                text=full_text,
                confidence=confidence,
                bounding_boxes=bounding_boxes,
                detected_language=detected_language,
                processing_time_ms=int(processing_time),
                raw_response=self._serialize_response(response)
            )

            logger.info(f"✅ OCR completado: {len(full_text)} chars, confianza: {confidence:.2%}")
            return result

        except Exception as e:
            logger.error(f"❌ Error en Google Vision OCR: {e}")
            raise

    def _extract_bounding_box(self, bounding_box) -> Dict:
        """Extraer coordenadas de bounding box"""
        vertices = []
        for vertex in bounding_box.vertices:
            vertices.append({'x': vertex.x, 'y': vertex.y})
        return {'vertices': vertices}

    def _serialize_response(self, response) -> Dict:
        """Serializar respuesta de Vision API para persistencia"""
        try:
            # Convertir protobuf a dict básico
            return {
                'text_annotations_count': len(response.text_annotations),
                'has_full_text_annotation': bool(response.full_text_annotation),
                'timestamp': datetime.now().isoformat()
            }
        except Exception:
            return {'error': 'Could not serialize response'}

    def extract_structured_data(self, ocr_result: OCRResult) -> ExtractedData:
        """Extraer datos estructurados del texto OCR"""

        text = ocr_result.text.upper()
        lines = text.split('\n')

        extracted = ExtractedData()

        # Patrones de extracción
        import re

        # RFC Pattern
        rfc_pattern = r'RFC[:\s]*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})'
        rfc_match = re.search(rfc_pattern, text)
        if rfc_match:
            extracted.rfc = rfc_match.group(1)

        # Total Pattern
        total_patterns = [
            r'TOTAL[:\s]*\$?(\d+[.,]\d{2})',
            r'IMPORTE[:\s]*\$?(\d+[.,]\d{2})',
            r'AMOUNT[:\s]*\$?(\d+[.,]\d{2})'
        ]

        for pattern in total_patterns:
            total_match = re.search(pattern, text)
            if total_match:
                extracted.total = total_match.group(1)
                break

        # Fecha Pattern
        fecha_patterns = [
            r'FECHA[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'DATE[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        ]

        for pattern in fecha_patterns:
            fecha_match = re.search(pattern, text)
            if fecha_match:
                extracted.fecha = fecha_match.group(1)
                break

        # Folio Pattern
        folio_patterns = [
            r'FOLIO[:\s]*([A-Z0-9]+)',
            r'TICKET[:\s]*([A-Z0-9]+)',
            r'NO[.:\s]*([A-Z0-9]+)'
        ]

        for pattern in folio_patterns:
            folio_match = re.search(pattern, text)
            if folio_match:
                extracted.folio = folio_match.group(1)
                break

        # Merchant name (primera línea que no sea número)
        for line in lines[:5]:  # Revisar primeras 5 líneas
            clean_line = line.strip()
            if clean_line and not re.match(r'^\d+$', clean_line) and len(clean_line) > 3:
                extracted.merchant_name = clean_line
                break

        # Calcular confidence score
        found_fields = sum([
            1 if extracted.rfc else 0,
            1 if extracted.total else 0,
            1 if extracted.fecha else 0,
            1 if extracted.folio else 0,
            1 if extracted.merchant_name else 0
        ])

        extracted.confidence_score = (found_fields / 5.0) * ocr_result.confidence

        logger.info(f"📊 Datos extraídos: RFC={bool(extracted.rfc)}, Total={bool(extracted.total)}, Fecha={bool(extracted.fecha)}")

        return extracted

# Función de conveniencia
def create_vision_ocr(credentials_path: str = None) -> GoogleVisionOCR:
    """Factory para crear instancia de Google Vision OCR"""
    return GoogleVisionOCR(credentials_path)

# Función para migrar desde OCR legacy
async def migrate_from_legacy_ocr(image_path: str) -> Dict[str, Any]:
    """Migrar desde sistema OCR legacy usando Google Vision"""

    try:
        ocr = create_vision_ocr()

        if not ocr.is_available():
            # Fallback a sistema legacy si está disponible
            logger.warning("⚠️ Google Vision no disponible, usando fallback")
            return {
                "success": False,
                "error": "Google Vision not available",
                "fallback_needed": True
            }

        # Procesar con Google Vision
        ocr_result = await ocr.extract_text_from_image(image_path)
        extracted_data = ocr.extract_structured_data(ocr_result)

        # Formato compatible con sistema legacy
        return {
            "success": True,
            "extracted_text": ocr_result.text,
            "structured_data": {
                "rfc": extracted_data.rfc,
                "total": extracted_data.total,
                "fecha": extracted_data.fecha,
                "folio": extracted_data.folio,
                "merchant_name": extracted_data.merchant_name
            },
            "confidence": extracted_data.confidence_score,
            "processing_time_ms": ocr_result.processing_time_ms,
            "detected_language": ocr_result.detected_language,
            "service": "google_vision"
        }

    except Exception as e:
        logger.error(f"❌ Error en migración OCR: {e}")
        return {
            "success": False,
            "error": str(e),
            "fallback_needed": True
        }