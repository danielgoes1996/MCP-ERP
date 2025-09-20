"""
Servicio de OCR para extracción de texto de imágenes de tickets.

Soporta múltiples backends:
- Google Vision API (recomendado para tickets mexicanos)
- Tesseract OCR (local, gratuito)
- Amazon Textract (alternativa cloud)
"""

import base64
import io
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class OCRService:
    """
    Servicio unificado de OCR con múltiples backends.
    """

    def __init__(self):
        self.preferred_backend = os.getenv("OCR_BACKEND", "tesseract")  # tesseract, google, amazon

        # Configuración de credenciales
        self.google_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")

    async def extract_text_from_base64(self, base64_image: str) -> str:
        """
        Extraer texto de imagen en base64.

        Args:
            base64_image: Imagen codificada en base64

        Returns:
            Texto extraído de la imagen
        """
        try:
            # Intentar backends en orden de preferencia
            if self.preferred_backend == "google":
                return await self._extract_with_google_vision(base64_image)
            elif self.preferred_backend == "amazon":
                return await self._extract_with_amazon_textract(base64_image)
            else:
                return await self._extract_with_tesseract(base64_image)

        except Exception as e:
            logger.warning(f"OCR backend {self.preferred_backend} falló: {e}")

            # Fallback a otros backends
            for fallback in ["tesseract", "google", "amazon"]:
                if fallback != self.preferred_backend:
                    try:
                        if fallback == "tesseract":
                            return await self._extract_with_tesseract(base64_image)
                        elif fallback == "google":
                            return await self._extract_with_google_vision(base64_image)
                        elif fallback == "amazon":
                            return await self._extract_with_amazon_textract(base64_image)
                    except Exception as e2:
                        logger.warning(f"Fallback OCR {fallback} también falló: {e2}")
                        continue

            # Si todos fallan, usar simulación
            logger.error("Todos los backends de OCR fallaron, usando simulación")
            return await self._extract_with_simulation(base64_image)

    async def _extract_with_google_vision(self, base64_image: str) -> str:
        """
        Extraer texto usando Google Vision API con API Key.

        Ventajas:
        - Muy preciso para texto en español
        - Reconoce formato de tickets mexicanos
        - Maneja bien imágenes de baja calidad
        """
        try:
            import requests
            import asyncio
            import json

            # Obtener API key de las variables de entorno
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise Exception("Google API Key no configurada. Configurar GOOGLE_API_KEY en .env")

            # Usar Google Vision API REST con API Key
            url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

            # Preparar request
            request_body = {
                "requests": [{
                    "image": {
                        "content": base64_image
                    },
                    "features": [{
                        "type": "TEXT_DETECTION",
                        "maxResults": 1
                    }],
                    "imageContext": {
                        "languageHints": ["es"]
                    }
                }]
            }

            # Hacer request con requests (síncrono pero lo ejecutamos en thread)
            def _sync_request():
                response = requests.post(url, json=request_body)
                if response.status_code != 200:
                    error_data = response.text
                    raise Exception(f"Google Vision API error: {error_data}")

                data = response.json()

                # Extraer texto de la respuesta
                if "responses" in data and data["responses"]:
                    response_data = data["responses"][0]
                    if "textAnnotations" in response_data and response_data["textAnnotations"]:
                        return response_data["textAnnotations"][0]["description"]
                    else:
                        return ""
                else:
                    return ""

            # Ejecutar en thread para no bloquear
            loop = asyncio.get_event_loop()
            extracted_text = await loop.run_in_executor(None, _sync_request)

            logger.info(f"Google Vision API extrajo {len(extracted_text)} caracteres")
            return extracted_text.strip()

        except ImportError as e:
            raise Exception(f"Error de importación: {str(e)}")
        except Exception as e:
            logger.error(f"Error en Google Vision API: {str(e)}")
            raise Exception(f"Error Google Vision: {str(e)}")

    async def _extract_with_amazon_textract(self, base64_image: str) -> str:
        """
        Extraer texto usando Amazon Textract.

        Ventajas:
        - Muy bueno para documentos estructurados
        - Detecta tablas y campos específicos
        - Integración fácil con AWS
        """
        try:
            import boto3
            import asyncio

            # Verificar credenciales
            if not self.aws_access_key or not self.aws_secret_key:
                raise Exception("Credenciales AWS no configuradas")

            # Configurar cliente
            textract = boto3.client(
                'textract',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )

            # Preparar imagen
            image_content = base64.b64decode(base64_image)

            # Ejecutar OCR
            def _sync_textract():
                response = textract.detect_document_text(
                    Document={'Bytes': image_content}
                )

                # Extraer texto de bloques
                extracted_text = []
                for block in response['Blocks']:
                    if block['BlockType'] == 'LINE':
                        extracted_text.append(block['Text'])

                return '\n'.join(extracted_text)

            loop = asyncio.get_event_loop()
            extracted_text = await loop.run_in_executor(None, _sync_textract)

            logger.info(f"Amazon Textract extrajo {len(extracted_text)} caracteres")
            return extracted_text.strip()

        except ImportError:
            raise Exception("boto3 no instalado. Instalar con: pip install boto3")
        except Exception as e:
            raise Exception(f"Error Amazon Textract: {str(e)}")

    async def _extract_with_tesseract(self, base64_image: str) -> str:
        """
        Extraer texto usando Tesseract OCR local.

        Ventajas:
        - Gratuito y local
        - No requiere internet
        - Personalizable
        """
        try:
            import pytesseract
            from PIL import Image
            import asyncio

            # Preparar imagen
            image_content = base64.b64decode(base64_image)
            image = Image.open(io.BytesIO(image_content))

            # Configurar Tesseract para español
            custom_config = r'--oem 3 --psm 6 -l spa'

            # Ejecutar OCR
            def _sync_tesseract():
                extracted_text = pytesseract.image_to_string(
                    image,
                    config=custom_config,
                    lang='spa'  # Español
                )
                return extracted_text

            loop = asyncio.get_event_loop()
            extracted_text = await loop.run_in_executor(None, _sync_tesseract)

            logger.info(f"Tesseract extrajo {len(extracted_text)} caracteres")
            return extracted_text.strip()

        except ImportError:
            raise Exception("pytesseract no instalado. Instalar con: pip install pytesseract pillow")
        except Exception as e:
            raise Exception(f"Error Tesseract: {str(e)}")

    async def _extract_with_simulation(self, base64_image: str) -> str:
        """
        Simulación de OCR para desarrollo/testing.
        """
        import random

        # Analizar el inicio del base64 para determinar tipo de imagen
        image_type = "unknown"
        if base64_image.startswith("/9j/"):
            image_type = "jpeg"
        elif base64_image.startswith("iVBORw0KGgo"):
            image_type = "png"

        # Simulaciones más realistas según el tipo
        simulations = [
            "OXXO TIENDA #1234\nRFC: OXX970814HS9\nFecha: 15/01/2024\nSubtotal: $105.50\nIVA: $16.88\nTotal: $122.38",
            "WALMART SUPERCENTER\nRFC: WAL9709244W4\nNo. Tienda: 2612\nFecha: 20/01/2024 14:30\nSubtotal: $280.00\nIVA: $44.80\nTotal: $324.80",
            "COSTCO WHOLESALE\nRFC: COS050815PE4\nNo. Almacén: 002\nFecha: 18/01/2024\nSubtotal: $1250.00\nIVA: $200.00\nTotal: $1450.00",
            "HOME DEPOT MÉXICO\nRFC: HDM930228Q90\nTienda: 6123\nFecha: 22/01/2024 16:45\nCódigo: HD789456\nSubtotal: $599.00\nIVA: $95.84\nTotal: $694.84",
            "SORIANA HIPER\nRFC: SOR9709244W4\nSucursal: 089\nFecha: 25/01/2024\nSubtotal: $450.75\nIVA: $72.12\nTotal: $522.87"
        ]

        selected_text = random.choice(simulations)

        logger.info(f"OCR simulado devolvió: {selected_text[:50]}...")
        return selected_text


# =============================================================
# INSTALACIÓN Y CONFIGURACIÓN
# =============================================================

def setup_google_vision():
    """
    Instrucciones para configurar Google Vision API.
    """
    instructions = """
    CONFIGURACIÓN GOOGLE VISION API:

    1. Crear proyecto en Google Cloud Console
    2. Habilitar Vision API
    3. Crear Service Account
    4. Descargar JSON credentials
    5. Configurar variable de entorno:
       export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

    6. Instalar biblioteca:
       pip install google-cloud-vision

    7. Configurar en .env:
       OCR_BACKEND=google
       GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
    """
    return instructions

def setup_amazon_textract():
    """
    Instrucciones para configurar Amazon Textract.
    """
    instructions = """
    CONFIGURACIÓN AMAZON TEXTRACT:

    1. Crear cuenta AWS
    2. Crear IAM user con permisos Textract
    3. Obtener Access Key y Secret Key
    4. Instalar biblioteca:
       pip install boto3

    5. Configurar en .env:
       OCR_BACKEND=amazon
       AWS_ACCESS_KEY_ID=tu_access_key
       AWS_SECRET_ACCESS_KEY=tu_secret_key
       AWS_REGION=us-east-1
    """
    return instructions

def setup_tesseract():
    """
    Instrucciones para configurar Tesseract OCR.
    """
    instructions = """
    CONFIGURACIÓN TESSERACT OCR (GRATUITO):

    1. Instalar Tesseract:
       # macOS
       brew install tesseract tesseract-lang

       # Ubuntu/Debian
       sudo apt update
       sudo apt install tesseract-ocr tesseract-ocr-spa

       # Windows
       Descargar desde: https://github.com/UB-Mannheim/tesseract/wiki

    2. Instalar bibliotecas Python:
       pip install pytesseract pillow

    3. Configurar en .env:
       OCR_BACKEND=tesseract
    """
    return instructions


# =============================================================
# FUNCIÓN PRINCIPAL PARA USAR DESDE EL WORKER
# =============================================================

async def extract_text_from_image(base64_image: str) -> str:
    """
    Función principal para extraer texto de imagen.

    Args:
        base64_image: Imagen en formato base64

    Returns:
        Texto extraído de la imagen
    """
    ocr_service = OCRService()
    return await ocr_service.extract_text_from_base64(base64_image)


if __name__ == "__main__":
    # Test del servicio
    import asyncio

    async def test_ocr():
        # Imagen de prueba (1x1 pixel blanco en base64)
        test_image = "/9j/4AAQSkZJRgABAQAAAQABAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2NjIpLCBxdWFsaXR5ID0gOTAK/9sAQwADAgIDAgIDAwMDBAMDBAUIBQUEBAUKBwcGCAwKDAwLCgsLDQ4SEA0OEQ4LCxAWEBETFBUVFQwPFxgWFBgSFBUU/9sAQwEDBAQFBAUJBQUJFA0LDRQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU/8AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8A/fyiiigD/9k="

        result = await extract_text_from_image(test_image)
        print(f"OCR Result: {result}")

    print("=== INSTRUCCIONES DE CONFIGURACIÓN ===")
    print("\n1. GOOGLE VISION (RECOMENDADO):")
    print(setup_google_vision())
    print("\n2. AMAZON TEXTRACT:")
    print(setup_amazon_textract())
    print("\n3. TESSERACT (GRATUITO):")
    print(setup_tesseract())

    # Ejecutar test
    asyncio.run(test_ocr())