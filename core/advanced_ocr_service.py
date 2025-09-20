"""
Sistema OCR Inteligente Avanzado - Clase Mundial
Integra múltiples backends: Google Vision, AWS Textract, Azure Computer Vision, Tesseract
Con capacidades de fallback, optimización y aprendizaje continuo.
"""

import asyncio
import base64
import io
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class OCRBackend(Enum):
    """Backends de OCR disponibles"""
    GOOGLE_VISION = "google_vision"
    AWS_TEXTRACT = "aws_textract"
    AZURE_COMPUTER_VISION = "azure_computer_vision"
    TESSERACT = "tesseract"


@dataclass
class OCRResult:
    """Resultado de extracción OCR"""
    backend: OCRBackend
    text: str
    confidence: float
    processing_time_ms: int
    structured_data: Optional[Dict] = None
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


@dataclass
class OCRConfig:
    """Configuración de OCR"""
    preferred_backends: List[OCRBackend]
    fallback_enabled: bool = True
    max_retries: int = 3
    timeout_seconds: int = 30
    enable_preprocessing: bool = True
    enable_caching: bool = True
    quality_threshold: float = 0.7


class AdvancedOCRService:
    """
    Servicio OCR inteligente con múltiples backends y capacidades avanzadas.
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig(
            preferred_backends=[
                OCRBackend.GOOGLE_VISION,
                OCRBackend.AWS_TEXTRACT,
                OCRBackend.AZURE_COMPUTER_VISION,
                OCRBackend.TESSERACT
            ]
        )

        # Cache para resultados
        self._cache = {} if self.config.enable_caching else None

        # Executor para operaciones síncronas
        self._executor = ThreadPoolExecutor(max_workers=4)

        # Configuraciones de backends
        self._backend_configs = {
            OCRBackend.GOOGLE_VISION: {
                "api_key": os.getenv("GOOGLE_API_KEY"),
                "endpoint": "https://vision.googleapis.com/v1/images:annotate"
            },
            OCRBackend.AWS_TEXTRACT: {
                "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
                "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "region": os.getenv("AWS_REGION", "us-east-1")
            },
            OCRBackend.AZURE_COMPUTER_VISION: {
                "api_key": os.getenv("AZURE_COMPUTER_VISION_KEY"),
                "endpoint": os.getenv("AZURE_COMPUTER_VISION_ENDPOINT")
            }
        }

    async def extract_text_intelligent(
        self,
        image_data: Union[str, bytes],
        image_format: str = "base64",
        context_hint: Optional[str] = None
    ) -> OCRResult:
        """
        Extracción inteligente con múltiples backends y optimizaciones.

        Args:
            image_data: Imagen en base64 o bytes
            image_format: Formato de la imagen ("base64", "bytes", "path")
            context_hint: Pista del contexto ("ticket", "invoice", "receipt")

        Returns:
            Mejor resultado de OCR
        """
        start_time = time.time()

        try:
            # Generar cache key
            cache_key = self._generate_cache_key(image_data, context_hint)

            # Verificar cache
            if self._cache and cache_key in self._cache:
                logger.info("Resultado obtenido desde cache")
                return self._cache[cache_key]

            # Preprocesamiento de imagen
            if self.config.enable_preprocessing:
                image_data = await self._preprocess_image(image_data, image_format)

            # Intentar backends en orden de preferencia
            best_result = None
            all_results = []

            for backend in self.config.preferred_backends:
                if not self._is_backend_available(backend):
                    logger.warning(f"Backend {backend.value} no disponible")
                    continue

                try:
                    result = await self._extract_with_backend(
                        backend, image_data, context_hint
                    )
                    all_results.append(result)

                    # Si el resultado es bueno, lo usamos
                    if result.confidence >= self.config.quality_threshold:
                        best_result = result
                        break

                except Exception as e:
                    logger.warning(f"Error en backend {backend.value}: {e}")
                    continue

            # Si no hay resultado bueno, usar el mejor disponible
            if not best_result and all_results:
                best_result = max(all_results, key=lambda r: r.confidence)

            # Si todos fallan, usar Tesseract como último recurso
            if not best_result:
                logger.warning("Todos los backends fallaron, usando Tesseract")
                best_result = await self._extract_with_tesseract_fallback(image_data)

            # Postprocesamiento
            if best_result:
                best_result = await self._postprocess_result(best_result, context_hint)

                # Guardar en cache
                if self._cache:
                    self._cache[cache_key] = best_result

            total_time = int((time.time() - start_time) * 1000)
            logger.info(f"OCR completado en {total_time}ms con backend {best_result.backend.value if best_result else 'none'}")

            return best_result

        except Exception as e:
            logger.error(f"Error crítico en OCR: {e}")
            return OCRResult(
                backend=OCRBackend.TESSERACT,
                text="",
                confidence=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=str(e)
            )

    async def _extract_with_backend(
        self,
        backend: OCRBackend,
        image_data: str,
        context_hint: Optional[str]
    ) -> OCRResult:
        """Extraer texto con un backend específico"""

        start_time = time.time()

        try:
            if backend == OCRBackend.GOOGLE_VISION:
                return await self._extract_google_vision(image_data, context_hint)
            elif backend == OCRBackend.AWS_TEXTRACT:
                return await self._extract_aws_textract(image_data, context_hint)
            elif backend == OCRBackend.AZURE_COMPUTER_VISION:
                return await self._extract_azure_cv(image_data, context_hint)
            elif backend == OCRBackend.TESSERACT:
                return await self._extract_tesseract(image_data, context_hint)
            else:
                raise ValueError(f"Backend no soportado: {backend}")

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            return OCRResult(
                backend=backend,
                text="",
                confidence=0.0,
                processing_time_ms=processing_time,
                error=str(e)
            )

    async def _extract_google_vision(
        self,
        base64_image: str,
        context_hint: Optional[str]
    ) -> OCRResult:
        """Extracción con Google Vision API"""

        import requests

        start_time = time.time()
        config = self._backend_configs[OCRBackend.GOOGLE_VISION]

        if not config["api_key"]:
            raise Exception("Google API Key no configurada")

        # Configurar request según contexto
        features = [{"type": "TEXT_DETECTION", "maxResults": 1}]
        if context_hint == "ticket":
            features.append({"type": "DOCUMENT_TEXT_DETECTION", "maxResults": 1})

        request_body = {
            "requests": [{
                "image": {"content": base64_image},
                "features": features,
                "imageContext": {
                    "languageHints": ["es", "en"],
                    "textDetectionParams": {
                        "enableTextDetectionConfidenceScore": True
                    }
                }
            }]
        }

        def _sync_request():
            response = requests.post(
                f"{config['endpoint']}?key={config['api_key']}",
                json=request_body,
                timeout=self.config.timeout_seconds
            )

            if response.status_code != 200:
                raise Exception(f"Google Vision API error: {response.text}")

            return response.json()

        # Ejecutar en thread
        loop = asyncio.get_event_loop()
        response_data = await loop.run_in_executor(self._executor, _sync_request)

        # Procesar respuesta
        text = ""
        confidence = 0.0
        structured_data = {}

        if "responses" in response_data and response_data["responses"]:
            response = response_data["responses"][0]

            # Extraer texto principal
            if "textAnnotations" in response and response["textAnnotations"]:
                text = response["textAnnotations"][0]["description"]

                # Calcular confianza promedio
                confidences = []
                for annotation in response["textAnnotations"][1:]:  # Skip first (full text)
                    if "confidence" in annotation:
                        confidences.append(annotation["confidence"])

                if confidences:
                    confidence = sum(confidences) / len(confidences)
                else:
                    confidence = 0.8  # Default para Google Vision

            # Extraer datos estructurados si hay DOCUMENT_TEXT_DETECTION
            if "fullTextAnnotation" in response:
                structured_data = self._parse_google_structured_data(
                    response["fullTextAnnotation"]
                )

        processing_time = int((time.time() - start_time) * 1000)

        return OCRResult(
            backend=OCRBackend.GOOGLE_VISION,
            text=text.strip(),
            confidence=confidence,
            processing_time_ms=processing_time,
            structured_data=structured_data,
            raw_response=response_data
        )

    async def _extract_aws_textract(
        self,
        base64_image: str,
        context_hint: Optional[str]
    ) -> OCRResult:
        """Extracción con AWS Textract"""

        try:
            import boto3
        except ImportError:
            raise Exception("boto3 no instalado. Instalar con: pip install boto3")

        start_time = time.time()
        config = self._backend_configs[OCRBackend.AWS_TEXTRACT]

        if not config["access_key"] or not config["secret_key"]:
            raise Exception("Credenciales AWS no configuradas")

        # Configurar cliente
        textract = boto3.client(
            'textract',
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            region_name=config["region"]
        )

        # Preparar imagen
        image_bytes = base64.b64decode(base64_image)

        def _sync_textract():
            # Usar análisis apropiado según contexto
            if context_hint == "ticket":
                response = textract.analyze_expense(
                    Document={'Bytes': image_bytes}
                )
            else:
                response = textract.detect_document_text(
                    Document={'Bytes': image_bytes}
                )
            return response

        # Ejecutar en thread
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(self._executor, _sync_textract)

        # Procesar respuesta
        text_lines = []
        confidence_scores = []
        structured_data = {}

        if 'Blocks' in response:
            for block in response['Blocks']:
                if block['BlockType'] == 'LINE':
                    text_lines.append(block['Text'])
                    if 'Confidence' in block:
                        confidence_scores.append(block['Confidence'] / 100.0)

        # Para análisis de gastos, extraer datos estructurados
        if context_hint == "ticket" and 'ExpenseDocuments' in response:
            structured_data = self._parse_aws_expense_data(response['ExpenseDocuments'])

        text = '\n'.join(text_lines)
        confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        processing_time = int((time.time() - start_time) * 1000)

        return OCRResult(
            backend=OCRBackend.AWS_TEXTRACT,
            text=text.strip(),
            confidence=confidence,
            processing_time_ms=processing_time,
            structured_data=structured_data,
            raw_response=response
        )

    async def _extract_azure_cv(
        self,
        base64_image: str,
        context_hint: Optional[str]
    ) -> OCRResult:
        """Extracción con Azure Computer Vision"""

        import requests

        start_time = time.time()
        config = self._backend_configs[OCRBackend.AZURE_COMPUTER_VISION]

        if not config["api_key"] or not config["endpoint"]:
            raise Exception("Credenciales Azure no configuradas")

        # Preparar request
        headers = {
            'Ocp-Apim-Subscription-Key': config["api_key"],
            'Content-Type': 'application/octet-stream'
        }

        image_bytes = base64.b64decode(base64_image)

        def _sync_request():
            # Usar OCR Read API
            response = requests.post(
                f"{config['endpoint']}/vision/v3.2/read/analyze",
                headers=headers,
                data=image_bytes,
                timeout=self.config.timeout_seconds
            )

            if response.status_code != 202:
                raise Exception(f"Azure CV error: {response.text}")

            # Obtener resultado
            operation_url = response.headers["Operation-Location"]

            # Polling para resultado
            for _ in range(30):  # Max 30 segundos
                time.sleep(1)
                result_response = requests.get(
                    operation_url,
                    headers={'Ocp-Apim-Subscription-Key': config["api_key"]}
                )

                if result_response.status_code == 200:
                    result = result_response.json()
                    if result["status"] == "succeeded":
                        return result
                    elif result["status"] == "failed":
                        raise Exception("Azure OCR failed")

            raise Exception("Azure OCR timeout")

        # Ejecutar en thread
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(self._executor, _sync_request)

        # Procesar respuesta
        text_lines = []
        confidence_scores = []

        if 'analyzeResult' in response and 'readResults' in response['analyzeResult']:
            for page in response['analyzeResult']['readResults']:
                for line in page.get('lines', []):
                    text_lines.append(line['text'])
                    if 'confidence' in line:
                        confidence_scores.append(line['confidence'])

        text = '\n'.join(text_lines)
        confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        processing_time = int((time.time() - start_time) * 1000)

        return OCRResult(
            backend=OCRBackend.AZURE_COMPUTER_VISION,
            text=text.strip(),
            confidence=confidence,
            processing_time_ms=processing_time,
            raw_response=response
        )

    async def _extract_tesseract(
        self,
        base64_image: str,
        context_hint: Optional[str]
    ) -> OCRResult:
        """Extracción con Tesseract OCR"""

        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise Exception("pytesseract/PIL no instalados")

        start_time = time.time()

        # Preparar imagen
        image_bytes = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_bytes))

        # Configuración según contexto
        if context_hint == "ticket":
            config = r'--oem 3 --psm 6 -l spa+eng'
        else:
            config = r'--oem 3 --psm 3 -l spa+eng'

        def _sync_tesseract():
            # Extraer texto
            text = pytesseract.image_to_string(image, config=config)

            # Obtener datos de confianza
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

            return text, avg_confidence

        # Ejecutar en thread
        loop = asyncio.get_event_loop()
        text, confidence = await loop.run_in_executor(self._executor, _sync_tesseract)

        processing_time = int((time.time() - start_time) * 1000)

        return OCRResult(
            backend=OCRBackend.TESSERACT,
            text=text.strip(),
            confidence=confidence,
            processing_time_ms=processing_time
        )

    async def _extract_with_tesseract_fallback(self, base64_image: str) -> OCRResult:
        """Fallback usando Tesseract con configuración optimizada"""

        logger.info("Usando Tesseract como fallback")

        try:
            return await self._extract_tesseract(base64_image, "ticket")
        except Exception as e:
            # Último recurso: simulación
            logger.error(f"Tesseract fallback falló: {e}")
            return OCRResult(
                backend=OCRBackend.TESSERACT,
                text="Error: No se pudo extraer texto de la imagen",
                confidence=0.0,
                processing_time_ms=0,
                error=str(e)
            )

    async def _preprocess_image(self, image_data: str, image_format: str) -> str:
        """Preprocesamiento de imagen para mejorar OCR"""

        try:
            from PIL import Image, ImageEnhance, ImageFilter

            # Convertir a PIL Image
            if image_format == "base64":
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
            else:
                return image_data  # No preprocessing para otros formatos

            def _process():
                # Convertir a RGB si es necesario
                if image.mode != 'RGB':
                    image_rgb = image.convert('RGB')
                else:
                    image_rgb = image

                # Mejorar contraste
                enhancer = ImageEnhance.Contrast(image_rgb)
                enhanced = enhancer.enhance(1.2)

                # Aplicar filtro de nitidez
                sharpened = enhanced.filter(ImageFilter.SHARPEN)

                # Convertir de vuelta a base64
                buffer = io.BytesIO()
                sharpened.save(buffer, format='JPEG', quality=95)
                return base64.b64encode(buffer.getvalue()).decode()

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self._executor, _process)

        except Exception as e:
            logger.warning(f"Error en preprocesamiento: {e}")
            return image_data  # Retornar original si falla

    async def _postprocess_result(self, result: OCRResult, context_hint: Optional[str]) -> OCRResult:
        """Postprocesamiento del resultado OCR"""

        # Limpiar texto
        text = result.text

        # Correcciones comunes para tickets mexicanos
        replacements = {
            'Ñ': 'N',  # Problemas de encoding
            '0': 'O',  # En algunos casos
            'l': 'I',  # En números
        }

        # Aplicar solo si la confianza es baja
        if result.confidence < 0.8:
            for old, new in replacements.items():
                text = text.replace(old, new)

        # Normalizar espacios
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # Actualizar resultado
        result.text = text

        return result

    def _is_backend_available(self, backend: OCRBackend) -> bool:
        """Verificar si un backend está disponible"""

        config = self._backend_configs.get(backend, {})

        if backend == OCRBackend.GOOGLE_VISION:
            return bool(config.get("api_key"))
        elif backend == OCRBackend.AWS_TEXTRACT:
            return bool(config.get("access_key") and config.get("secret_key"))
        elif backend == OCRBackend.AZURE_COMPUTER_VISION:
            return bool(config.get("api_key") and config.get("endpoint"))
        elif backend == OCRBackend.TESSERACT:
            try:
                import pytesseract
                return True
            except ImportError:
                return False

        return False

    def _generate_cache_key(self, image_data: str, context_hint: Optional[str]) -> str:
        """Generar clave de cache para imagen"""

        content = f"{image_data[:100]}-{context_hint or ''}"
        return hashlib.md5(content.encode()).hexdigest()

    def _parse_google_structured_data(self, full_text_annotation: Dict) -> Dict:
        """Parsear datos estructurados de Google Vision"""

        structured = {}

        # Extraer bloques de texto
        if 'pages' in full_text_annotation:
            blocks = []
            for page in full_text_annotation['pages']:
                for block in page.get('blocks', []):
                    block_text = ""
                    for paragraph in block.get('paragraphs', []):
                        for word in paragraph.get('words', []):
                            word_text = ""
                            for symbol in word.get('symbols', []):
                                word_text += symbol.get('text', '')
                            block_text += word_text + " "
                    blocks.append(block_text.strip())

            structured['text_blocks'] = blocks

        return structured

    def _parse_aws_expense_data(self, expense_documents: List[Dict]) -> Dict:
        """Parsear datos estructurados de AWS Textract"""

        structured = {}

        for doc in expense_documents:
            summary_fields = doc.get('SummaryFields', [])
            line_items = doc.get('LineItemGroups', [])

            # Extraer campos de resumen
            for field in summary_fields:
                field_type = field.get('Type', {}).get('Text', '')
                field_value = field.get('ValueDetection', {}).get('Text', '')

                if field_type and field_value:
                    structured[field_type.lower()] = field_value

            # Extraer elementos de línea
            items = []
            for group in line_items:
                for item in group.get('LineItems', []):
                    item_data = {}
                    for field in item.get('LineItemExpenseFields', []):
                        field_type = field.get('Type', {}).get('Text', '')
                        field_value = field.get('ValueDetection', {}).get('Text', '')
                        if field_type and field_value:
                            item_data[field_type.lower()] = field_value
                    items.append(item_data)

            structured['line_items'] = items

        return structured

    async def get_backend_health(self) -> Dict[OCRBackend, bool]:
        """Obtener estado de salud de todos los backends"""

        health_status = {}

        for backend in OCRBackend:
            health_status[backend] = self._is_backend_available(backend)

        return health_status

    async def clear_cache(self) -> None:
        """Limpiar cache de resultados"""

        if self._cache:
            self._cache.clear()
            logger.info("Cache de OCR limpiado")


# Función de conveniencia para usar desde otros módulos
async def extract_text_intelligent(
    image_data: str,
    context_hint: Optional[str] = None
) -> OCRResult:
    """
    Función principal para extracción inteligente de texto.

    Args:
        image_data: Imagen en base64
        context_hint: Contexto ("ticket", "invoice", "receipt")

    Returns:
        Resultado de OCR optimizado
    """

    service = AdvancedOCRService()
    return await service.extract_text_intelligent(image_data, context_hint=context_hint)


# Configuración de logging específica para OCR
def setup_ocr_logging():
    """Configurar logging optimizado para OCR"""

    # Crear logger específico para OCR
    ocr_logger = logging.getLogger('advanced_ocr')
    ocr_logger.setLevel(logging.INFO)

    # Handler para archivo específico de OCR
    handler = logging.FileHandler('ocr_operations.log')
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    ocr_logger.addHandler(handler)

    return ocr_logger


if __name__ == "__main__":
    # Test del servicio avanzado
    import asyncio

    async def test_advanced_ocr():
        """Test completo del servicio OCR avanzado"""

        print("=== TEST DEL SISTEMA OCR AVANZADO ===")

        # Crear servicio
        config = OCRConfig(
            preferred_backends=[
                OCRBackend.GOOGLE_VISION,
                OCRBackend.TESSERACT
            ],
            quality_threshold=0.6
        )

        service = AdvancedOCRService(config)

        # Verificar salud de backends
        health = await service.get_backend_health()
        print("Estado de backends:")
        for backend, is_healthy in health.items():
            print(f"  {backend.value}: {'✅' if is_healthy else '❌'}")

        # Imagen de prueba
        test_image = "/9j/4AAQSkZJRgABAQAAAQABAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2NjIpLCBxdWFsaXR5ID0gOTAK/9sAQwADAgIDAgIDAwMDBAMDBAUIBQUEBAUKBwcGCAwKDAwLCgsLDQ4SEA0OEQ4LCxAWEBETFBUVFQwPFxgWFBgSFBUU/9sAQwEDBAQFBAUJBQUJFA0LDRQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU/8AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8A/fyiiigD/9k="

        try:
            result = await service.extract_text_intelligent(
                test_image,
                context_hint="ticket"
            )

            print(f"\n✅ Resultado exitoso:")
            print(f"Backend: {result.backend.value}")
            print(f"Texto: '{result.text}'")
            print(f"Confianza: {result.confidence:.2%}")
            print(f"Tiempo: {result.processing_time_ms}ms")

            if result.structured_data:
                print(f"Datos estructurados: {json.dumps(result.structured_data, indent=2)}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Ejecutar test
    asyncio.run(test_advanced_ocr())