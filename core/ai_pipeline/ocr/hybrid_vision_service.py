#!/usr/bin/env python3
"""
Servicio híbrido que combina Google Cloud Vision con GPT Vision
para máxima precisión en extracción de campos críticos
"""

import os
import json
import base64
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ExtractionMethod(Enum):
    GOOGLE_VISION = "google_vision"
    GPT_VISION = "gpt_vision"
    HYBRID = "hybrid"

@dataclass
class FieldExtractionResult:
    value: str
    confidence: float
    method: ExtractionMethod
    context: Dict[str, Any]
    alternative_values: List[str] = None
    reasoning: str = ""

class HybridVisionService:
    """
    Servicio que combina Google Cloud Vision con GPT Vision para
    extracciones más precisas y recuperación inteligente de errores
    """

    def __init__(self):
        self.google_api_key = os.getenv('GOOGLE_CLOUD_VISION_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Configuraciones de confianza
        self.google_confidence_threshold = 0.8
        self.retry_threshold = 0.6

    def extract_field_intelligently(
        self,
        image_data: str,
        field_name: str,
        web_error: str = None,
        force_gpt: bool = False
    ) -> FieldExtractionResult:
        """
        Extrae un campo usando el método más apropiado basado en:
        - Confianza del resultado inicial
        - Errores reportados por formularios web
        - Tipo de campo (algunos son más difíciles para OCR)
        """

        # Campos que típicamente requieren GPT Vision
        gpt_preferred_fields = ['folio', 'web_id', 'reference', 'codigo']

        try:
            # 1. Intento inicial con Google Cloud Vision (más rápido)
            if not force_gpt and not web_error:
                google_result = self._extract_with_google_vision(image_data, field_name)

                # Si confianza es alta y no es campo problemático, usar resultado
                if (google_result.confidence >= self.google_confidence_threshold and
                    field_name.lower() not in gpt_preferred_fields):
                    return google_result

                # Si confianza es media, guardar como contexto para GPT
                google_context = google_result if google_result.confidence >= self.retry_threshold else None
            else:
                google_context = None

            # 2. Usar GPT Vision para casos complejos
            gpt_result = self._extract_with_gpt_vision(
                image_data,
                field_name,
                google_context=google_context,
                web_error=web_error
            )

            return gpt_result

        except Exception as e:
            logger.error(f"Error en extracción híbrida para {field_name}: {e}")
            return FieldExtractionResult(
                value="",
                confidence=0.0,
                method=ExtractionMethod.HYBRID,
                context={"error": str(e)},
                reasoning=f"Error durante extracción: {e}"
            )

    def _extract_with_google_vision(self, image_data: str, field_name: str) -> FieldExtractionResult:
        """
        Extrae campo usando Google Cloud Vision OCR
        """
        try:
            # Importar OCR service existente
            from core.ai_pipeline.ocr.advanced_ocr_service import AdvancedOCRService

            ocr_service = AdvancedOCRService()

            # Extraer texto completo
            extracted_text = ocr_service._extract_google_vision(image_data, context_hint="")

            # Extraer campos específicos usando patrones existentes
            fields = ocr_service.extract_fields_from_lines(extracted_text.split('\n'))

            # Buscar el campo específico
            field_value = fields.get(field_name.lower(), "")

            # Calcular confianza basada en patrones y contexto
            confidence = self._calculate_google_confidence(field_value, field_name, extracted_text)

            return FieldExtractionResult(
                value=field_value,
                confidence=confidence,
                method=ExtractionMethod.GOOGLE_VISION,
                context={
                    "full_text": extracted_text,
                    "all_fields": fields
                },
                reasoning=f"Extraído via Google Cloud Vision OCR con confianza {confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"Error en Google Vision para {field_name}: {e}")
            return FieldExtractionResult(
                value="",
                confidence=0.0,
                method=ExtractionMethod.GOOGLE_VISION,
                context={"error": str(e)},
                reasoning=f"Error en Google Vision: {e}"
            )

    def _extract_with_gpt_vision(
        self,
        image_data: str,
        field_name: str,
        google_context: FieldExtractionResult = None,
        web_error: str = None
    ) -> FieldExtractionResult:
        """
        Extrae campo usando GPT Vision para casos complejos
        """
        try:
            import openai

            # Preparar contexto adicional
            context_info = ""
            if google_context:
                context_info += f"\n\nGoogle OCR extrajo: '{google_context.value}' con confianza {google_context.confidence:.2f}"
                if google_context.context.get("full_text"):
                    context_info += f"\n\nTexto OCR completo:\n{google_context.context['full_text'][:500]}..."

            if web_error:
                context_info += f"\n\nERROR DEL FORMULARIO WEB: {web_error}"
                context_info += "\nPor favor, reanaliza la imagen y encuentra el valor correcto."

            # Prompt especializado según el campo
            field_prompts = {
                'folio': "Busca números que parezcan ser un folio, número de ticket, o identificador de transacción. Puede estar etiquetado como 'FOLIO:', 'NO.', 'TICKET:', '#', etc.",
                'web_id': "Busca un número que parezca ser un ID web, código de autorización, o identificador de sistema. Suele ser un número largo (6-10 dígitos).",
                'reference': "Busca números de referencia, códigos de autorización, o identificadores de transacción.",
                'total': "Busca el monto total de la transacción, incluyendo moneda ($).",
                'merchant': "Busca el nombre del comercio, empresa, o establecimiento."
            }

            prompt = f"""
Eres un experto en lectura de tickets y recibos mexicanos. Analiza esta imagen y extrae ÚNICAMENTE el campo: {field_name.upper()}

INSTRUCCIONES ESPECÍFICAS:
{field_prompts.get(field_name.lower(), f"Busca el campo {field_name} en la imagen.")}

{context_info}

FORMATO DE RESPUESTA (JSON):
{{
    "value": "valor_extraído",
    "confidence": 0.95,
    "alternatives": ["valor1", "valor2"],
    "reasoning": "explicación de por qué elegiste este valor"
}}

REGLAS IMPORTANTES:
1. Si hay múltiples candidatos, elige el que sea más probable basado en contexto
2. Incluye solo el VALOR, sin etiquetas (ej: "123456", no "FOLIO: 123456")
3. Si no encuentras el campo, responde value: ""
4. Confidence debe ser 0.0-1.0 basado en qué tan seguro estás
5. En alternatives incluye otros valores que consideraste
"""

            # Preparar imagen para GPT Vision
            if not image_data.startswith('data:image'):
                image_data = f"data:image/jpeg;base64,{image_data}"

            client = openai.OpenAI(api_key=self.openai_api_key)

            response = client.chat.completions.create(
                model="gpt-4o",  # Modelo con capacidades de visión
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_data}
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )

            # Parsear respuesta JSON
            response_text = response.choices[0].message.content.strip()

            # Limpiar respuesta si viene con ```json
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()

            result_data = json.loads(response_text)

            return FieldExtractionResult(
                value=result_data.get("value", ""),
                confidence=float(result_data.get("confidence", 0.0)),
                method=ExtractionMethod.GPT_VISION,
                context={
                    "gpt_response": result_data,
                    "google_context": google_context.context if google_context else None,
                    "web_error": web_error
                },
                alternative_values=result_data.get("alternatives", []),
                reasoning=result_data.get("reasoning", "")
            )

        except Exception as e:
            logger.error(f"Error en GPT Vision para {field_name}: {e}")
            return FieldExtractionResult(
                value="",
                confidence=0.0,
                method=ExtractionMethod.GPT_VISION,
                context={"error": str(e)},
                reasoning=f"Error en GPT Vision: {e}"
            )

    def _calculate_google_confidence(self, field_value: str, field_name: str, full_text: str) -> float:
        """
        Calcula confianza del resultado de Google Vision basado en varios factores
        """
        if not field_value:
            return 0.0

        confidence = 0.5  # Base

        # Factores que aumentan confianza
        if len(field_value) >= 4:  # Longitud razonable
            confidence += 0.2

        if field_value.isdigit():  # Es numérico (bueno para folios, web_ids)
            if field_name.lower() in ['folio', 'web_id', 'reference']:
                confidence += 0.2

        # Verificar si hay etiquetas cercanas en el texto
        field_labels = {
            'folio': ['folio', 'no.', 'ticket', '#'],
            'web_id': ['web', 'id', 'codigo', 'auth'],
            'total': ['total', 'importe', '$']
        }

        labels = field_labels.get(field_name.lower(), [])
        for label in labels:
            if label.lower() in full_text.lower():
                confidence += 0.1
                break

        return min(confidence, 1.0)

    async def validate_field_with_candidates(
        self,
        image_data: str,
        field_name: str,
        candidates: List[str],
        portal_error: str = None,
        ocr_full_text: str = None
    ) -> FieldExtractionResult:
        """
        GPT Vision analiza imagen original y candidatos para seleccionar el valor correcto.

        Args:
            image_data: Imagen original del ticket en base64
            field_name: Campo que se está validando (folio, rfc_emisor, monto_total, etc.)
            candidates: Lista de valores candidatos detectados por OCR
            portal_error: Error específico del portal web (opcional)
            ocr_full_text: Texto completo extraído por OCR (opcional)

        Returns:
            FieldExtractionResult con el valor más probable
        """
        try:
            import openai

            # Construir contexto detallado
            context_info = f"\nCANDIDATOS DETECTADOS POR OCR:"
            for i, candidate in enumerate(candidates, 1):
                context_info += f"\n{i}. '{candidate}'"

            if portal_error:
                context_info += f"\n\nERROR DEL PORTAL WEB: {portal_error}"
                context_info += "\nEste error indica que el valor seleccionado por OCR no es correcto."

            if ocr_full_text:
                context_info += f"\n\nTEXTO COMPLETO EXTRAÍDO POR OCR:\n{ocr_full_text[:800]}..."

            # Prompts específicos por campo
            field_instructions = {
                'folio': """
BUSCA EL FOLIO/NÚMERO DE TICKET:
- Usualmente está en la parte superior del ticket
- Puede estar etiquetado como: "FOLIO:", "NO:", "TICKET:", "#", "REF:"
- Es un número único de la transacción
- Suele tener entre 4-12 dígitos
- NO confundir con códigos de autorización o números de tarjeta""",

                'rfc_emisor': """
BUSCA EL RFC DEL EMISOR (quien emite el ticket):
- Formato: 3-4 letras + 6 números + 2-3 caracteres (ej: ABC123456XY1)
- Usualmente cerca del nombre de la empresa
- NO confundir con RFC del receptor
- Debe tener exactamente 12 o 13 caracteres""",

                'monto_total': """
BUSCA EL MONTO TOTAL A PAGAR:
- Etiquetado como: "TOTAL:", "IMPORTE:", "TOTAL A PAGAR:"
- Incluye símbolo $ o mención de moneda
- Es el monto final después de impuestos
- NO confundir con subtotales o montos parciales""",

                'fecha': """
BUSCA LA FECHA DE LA TRANSACCIÓN:
- Formato: DD/MM/YYYY o DD-MM-YYYY
- Puede incluir hora: DD/MM/YYYY HH:MM
- Usualmente en la parte superior del ticket""",

                'web_id': """
BUSCA CÓDIGO/ID WEB O DE AUTORIZACIÓN:
- Número largo (6-15 dígitos)
- Puede estar etiquetado como: "WEB ID:", "AUTH:", "CODIGO:", "REF:"
- NO confundir con folio normal"""
            }

            instruction = field_instructions.get(field_name.lower(), f"Busca el campo {field_name} en el ticket")

            prompt = f"""
Eres un experto en análisis de tickets mexicanos. Analiza esta imagen de ticket y ayuda a seleccionar el valor CORRECTO para el campo: {field_name.upper()}

{instruction}

{context_info}

INSTRUCCIONES:
1. Mira cuidadosamente la imagen del ticket
2. Identifica visualmente dónde está el {field_name} real en el ticket
3. Compara con los candidatos detectados por OCR
4. Si ningún candidato es correcto, extrae el valor correcto de la imagen

RESPONDE EN JSON:
{{
    "selected_candidate": "número_del_candidato_correcto_o_nuevo_valor",
    "confidence": 0.95,
    "reasoning": "explicación detallada de por qué elegiste este valor",
    "visual_location": "descripción de dónde está ubicado en el ticket",
    "is_new_value": false,
    "alternatives": ["otros_valores_considerados"]
}}

REGLAS IMPORTANTES:
- Si uno de los candidatos es correcto, usa "selected_candidate": "1" (por ejemplo, para el primer candidato)
- Si ningún candidato es correcto, pon el valor real en "selected_candidate" y marca "is_new_value": true
- Confidence debe ser 0.0-1.0 basado en qué tan seguro estás
- Sé muy específico en tu razonamiento sobre la ubicación visual"""

            # Preparar imagen para GPT Vision
            if not image_data.startswith('data:image'):
                image_data = f"data:image/jpeg;base64,{image_data}"

            client = openai.OpenAI(api_key=self.openai_api_key)

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_data}
                            }
                        ]
                    }
                ],
                max_tokens=800,
                temperature=0.1
            )

            # Parsear respuesta
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()

            result_data = json.loads(response_text)

            # Determinar el valor final
            selected = result_data.get("selected_candidate", "")
            is_new = result_data.get("is_new_value", False)

            if is_new:
                final_value = selected
            else:
                # Es un índice de candidato
                try:
                    candidate_index = int(selected) - 1  # Convertir a índice base-0
                    if 0 <= candidate_index < len(candidates):
                        final_value = candidates[candidate_index]
                    else:
                        final_value = selected  # Usar como valor directo si índice inválido
                except (ValueError, TypeError):
                    final_value = selected  # Usar como valor directo

            return FieldExtractionResult(
                value=final_value,
                confidence=float(result_data.get("confidence", 0.0)),
                method=ExtractionMethod.GPT_VISION,
                context={
                    "gpt_analysis": result_data,
                    "candidates": candidates,
                    "portal_error": portal_error,
                    "selected_candidate_index": selected if not is_new else None,
                    "is_new_value": is_new
                },
                alternative_values=result_data.get("alternatives", []),
                reasoning=f"GPT Vision: {result_data.get('reasoning', '')} | Ubicación: {result_data.get('visual_location', '')}"
            )

        except Exception as e:
            logger.error(f"Error en validación con candidatos para {field_name}: {e}")
            # Fallback: retornar primer candidato si existe
            fallback_value = candidates[0] if candidates else ""
            return FieldExtractionResult(
                value=fallback_value,
                confidence=0.1,
                method=ExtractionMethod.GPT_VISION,
                context={"error": str(e), "candidates": candidates},
                reasoning=f"Error en GPT Vision, usando primer candidato: {e}"
            )

    def validate_field_against_web_error(
        self,
        field_value: str,
        field_name: str,
        web_error: str
    ) -> bool:
        """
        Analiza si un valor de campo podría estar causando el error web
        """
        error_lower = web_error.lower()

        # Patrones de errores comunes
        error_patterns = {
            'invalid_format': ['formato', 'inválido', 'format', 'invalid'],
            'too_short': ['corto', 'short', 'mínimo', 'minimum'],
            'too_long': ['largo', 'long', 'máximo', 'maximum'],
            'not_found': ['encontrado', 'found', 'existe', 'exist'],
            'numeric_only': ['número', 'numeric', 'dígito', 'digit']
        }

        # Analizar tipo de error
        for error_type, keywords in error_patterns.items():
            if any(keyword in error_lower for keyword in keywords):
                return self._validate_against_error_type(field_value, field_name, error_type)

        # Si no reconocemos el error, asumir que el campo necesita revisión
        return False

    def _validate_against_error_type(self, value: str, field_name: str, error_type: str) -> bool:
        """
        Valida un valor contra un tipo específico de error
        """
        if error_type == 'numeric_only':
            return value.isdigit()

        if error_type == 'too_short':
            # Longitudes mínimas típicas por campo
            min_lengths = {'folio': 4, 'web_id': 6, 'reference': 4}
            return len(value) >= min_lengths.get(field_name, 3)

        if error_type == 'too_long':
            # Longitudes máximas típicas por campo
            max_lengths = {'folio': 12, 'web_id': 15, 'reference': 20}
            return len(value) <= max_lengths.get(field_name, 50)

        return True

# Instancia global
hybrid_vision_service = HybridVisionService()