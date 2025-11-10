"""
Gemini Vision OCR Service
Extrae texto de PDFs usando Gemini 2.5 Flash Vision API
"""

import logging
import base64
import os
import time
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass
import json

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OCRPage:
    """Resultado de OCR para una página"""
    page_number: int
    text: str
    confidence: float
    processing_time_ms: int
    structured_data: Optional[Dict] = None


@dataclass
class OCRDocument:
    """Resultado completo de OCR"""
    total_pages: int
    pages: List[OCRPage]
    full_text: str
    total_processing_time_ms: int
    metadata: Dict[str, Any]


class GeminiVisionOCR:
    """
    Servicio OCR usando Gemini Vision API
    Extrae texto de PDFs con alta precisión
    """

    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai no está instalado. Ejecuta: pip install google-generativeai")

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no configurada")

        # Configurar Gemini
        genai.configure(api_key=self.api_key)

        # Modelo optimizado para OCR
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        logger.info("✅ Gemini Vision OCR initialized")

    def extract_text_from_pdf(
        self,
        pdf_path: str,
        max_pages: Optional[int] = None,
        extract_structured: bool = False
    ) -> OCRDocument:
        """
        Extrae texto de un PDF usando Gemini Vision

        Args:
            pdf_path: Ruta al archivo PDF
            max_pages: Máximo de páginas a procesar (None = todas)
            extract_structured: Si True, intenta extraer datos estructurados

        Returns:
            OCRDocument con texto extraído
        """
        start_time = time.time()

        logger.info(f"🔍 Extracting text from PDF: {pdf_path}")

        # Validar archivo
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        # Leer PDF como bytes
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        # Convertir a base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # Crear prompt para OCR
        prompt = self._create_ocr_prompt(extract_structured)

        try:
            # Enviar a Gemini Vision
            response = self.model.generate_content([
                {
                    "mime_type": "application/pdf",
                    "data": pdf_base64
                },
                prompt
            ])

            # Extraer texto
            extracted_text = response.text

            processing_time = int((time.time() - start_time) * 1000)

            # Parsear respuesta si es estructurada
            structured_data = None
            if extract_structured:
                structured_data = self._parse_structured_response(extracted_text)

            # Crear resultado
            ocr_page = OCRPage(
                page_number=1,
                text=extracted_text,
                confidence=0.95,  # Gemini es muy preciso
                processing_time_ms=processing_time,
                structured_data=structured_data
            )

            result = OCRDocument(
                total_pages=1,  # Gemini procesa todo el PDF de una vez
                pages=[ocr_page],
                full_text=extracted_text,
                total_processing_time_ms=processing_time,
                metadata={
                    "model": "gemini-2.0-flash-exp",
                    "file_name": Path(pdf_path).name,
                    "file_size_bytes": len(pdf_bytes),
                    "extract_structured": extract_structured
                }
            )

            logger.info(f"✅ OCR completed in {processing_time}ms - {len(extracted_text)} chars")

            return result

        except Exception as e:
            logger.error(f"❌ Error extracting text from PDF: {e}")
            raise

    def _create_ocr_prompt(self, extract_structured: bool) -> str:
        """Crea prompt optimizado para OCR"""
        if extract_structured:
            return """
Extrae TODO el texto de este estado de cuenta bancario en formato JSON estructurado.

Incluye:
1. Información del banco (nombre, tipo de cuenta, número de cuenta)
2. Período del estado (fecha inicio y fin)
3. Resumen (saldo inicial, saldo final, total créditos, total débitos)
4. TODAS las transacciones con:
   - Fecha
   - Descripción completa
   - Monto (positivo para créditos, negativo para débitos)
   - Tipo (débito/crédito)
   - Saldo después de la transacción (si está disponible)
   - Referencia (si está disponible)

Responde SOLO con JSON válido, sin explicaciones adicionales.

Formato esperado:
{
  "bank_info": {
    "bank_name": "...",
    "account_type": "credit_card|debit_card|checking|savings",
    "account_number": "****1234",
    "period_start": "2024-01-01",
    "period_end": "2024-01-31"
  },
  "summary": {
    "opening_balance": 0.00,
    "closing_balance": 0.00,
    "total_credits": 0.00,
    "total_debits": 0.00
  },
  "transactions": [
    {
      "date": "2024-01-05",
      "description": "...",
      "amount": -1500.00,
      "type": "debit",
      "balance": 8500.00,
      "reference": "REF123456"
    }
  ]
}
"""
        else:
            return """
Extrae TODO el texto de este documento PDF exactamente como aparece.

Preserva:
- Fechas
- Montos
- Descripciones completas
- Estructura de tabla (si hay)
- Números de referencia

Responde con el texto extraído sin modificaciones.
"""

    def _parse_structured_response(self, response_text: str) -> Optional[Dict]:
        """Parsea respuesta estructurada de Gemini"""
        try:
            # Limpiar respuesta (remover markdown si existe)
            cleaned = response_text.strip()

            # Buscar JSON en la respuesta
            if "```json" in cleaned:
                # Extraer JSON de markdown
                start = cleaned.find("```json") + 7
                end = cleaned.find("```", start)
                cleaned = cleaned[start:end].strip()
            elif "```" in cleaned:
                start = cleaned.find("```") + 3
                end = cleaned.find("```", start)
                cleaned = cleaned[start:end].strip()

            # Parsear JSON
            data = json.loads(cleaned)
            return data

        except Exception as e:
            logger.warning(f"⚠️ Could not parse structured response: {e}")
            return None

    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extrae texto de una imagen usando Gemini Vision

        Args:
            image_path: Ruta a la imagen

        Returns:
            Texto extraído
        """
        logger.info(f"🔍 Extracting text from image: {image_path}")

        # Leer imagen
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        # Convertir a base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Detectar tipo MIME
        ext = Path(image_path).suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')

        try:
            # Enviar a Gemini Vision
            response = self.model.generate_content([
                {
                    "mime_type": mime_type,
                    "data": image_base64
                },
                "Extrae TODO el texto de esta imagen exactamente como aparece."
            ])

            extracted_text = response.text
            logger.info(f"✅ Extracted {len(extracted_text)} chars from image")

            return extracted_text

        except Exception as e:
            logger.error(f"❌ Error extracting text from image: {e}")
            raise


# Singleton instance
_gemini_ocr_instance: Optional[GeminiVisionOCR] = None


def get_gemini_ocr() -> GeminiVisionOCR:
    """Obtiene instancia singleton de GeminiVisionOCR"""
    global _gemini_ocr_instance

    if _gemini_ocr_instance is None:
        _gemini_ocr_instance = GeminiVisionOCR()

    return _gemini_ocr_instance
