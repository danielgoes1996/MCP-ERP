#!/usr/bin/env python3
"""
Validador Inteligente de Campos con GPT Vision
Integra OCR + GPT Vision para máxima precisión en extracción de campos de tickets
"""

import asyncio
import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationRequest:
    """Solicitud de validación de campo"""
    image_data: str          # Imagen original del ticket en base64
    field_name: str          # Campo a validar (folio, rfc_emisor, monto_total)
    portal_error: str = None # Error específico del portal web
    force_gpt: bool = False  # Forzar uso de GPT Vision


@dataclass
class ValidationResult:
    """Resultado de validación con contexto completo"""
    final_value: str
    confidence: float
    method_used: str
    all_candidates: List[str]
    gpt_reasoning: str = ""
    validation_context: Dict[str, Any] = None
    error: str = None


class IntelligentFieldValidator:
    """
    Validador que combina OCR tradicional con GPT Vision para casos complejos.

    Flujo de trabajo:
    1. Extrae texto completo con Google Cloud Vision
    2. Genera múltiples candidatos para el campo solicitado
    3. Si hay error del portal, usa GPT Vision como árbitro
    4. GPT Vision analiza imagen + candidatos y selecciona el correcto
    """

    def __init__(self):
        # Importar servicios existentes
        from core.advanced_ocr_service import AdvancedOCRService
        from core.hybrid_vision_service import hybrid_vision_service

        self.ocr_service = AdvancedOCRService()
        self.hybrid_service = hybrid_vision_service

    async def validate_field(self, request: ValidationRequest) -> ValidationResult:
        """
        Validar un campo específico con estrategia cost-optimized.

        GPT Vision se usa SOLO cuando:
        1. Portal web rechaza con error específico (caso real de fallo)
        2. OCR tiene confianza muy baja Y múltiples candidatos ambiguos
        3. Usuario fuerza explícitamente (force_gpt=True)

        Args:
            request: Solicitud de validación con imagen y contexto

        Returns:
            ValidationResult con valor más probable y contexto
        """
        try:
            logger.info(f"🔍 Validando campo: {request.field_name}")

            # PASO 1: OCR tradicional (siempre primero, es barato)
            ocr_result = await self.ocr_service.extract_text_intelligent(
                request.image_data,
                context_hint="ticket"
            )

            if not ocr_result or not ocr_result.text:
                return ValidationResult(
                    final_value="",
                    confidence=0.0,
                    method_used="ocr_failed",
                    all_candidates=[],
                    error="OCR no pudo extraer texto de la imagen"
                )

            # PASO 2: Extraer candidatos con regex mejorados
            ocr_lines = self.ocr_service.extract_lines_from_ocr(ocr_result.raw_response)
            if not ocr_lines:
                ocr_lines = ocr_result.text.split('\n')

            candidates = self.ocr_service.extract_field_candidates(ocr_lines, request.field_name)
            logger.info(f"📋 Candidatos OCR: {candidates}")

            # PASO 3: DECISIÓN INTELIGENTE DE COSTOS
            should_use_gpt = self._should_use_expensive_gpt_vision(
                request=request,
                ocr_result=ocr_result,
                candidates=candidates
            )

            # PASO 4A: RUTA BARATA - Usar solo OCR si es suficiente
            if not should_use_gpt:
                return self._resolve_with_cheap_methods(
                    candidates=candidates,
                    field_name=request.field_name,
                    ocr_result=ocr_result
                )

            # PASO 4B: RUTA COSTOSA - GPT Vision solo para casos críticos
            logger.warning(f"💰 Usando GPT Vision (COSTOSO) para {request.field_name}")
            logger.warning(f"📊 Razón: {self._get_gpt_usage_reason(request, ocr_result, candidates)}")

            gpt_result = await self.hybrid_service.validate_field_with_candidates(
                image_data=request.image_data,
                field_name=request.field_name,
                candidates=candidates,
                portal_error=request.portal_error,
                ocr_full_text=ocr_result.text
            )

            # Tracking de costos DESPUÉS de obtener resultado
            usage_reason = self._get_gpt_usage_reason(request, ocr_result, candidates)
            self._track_gpt_usage(
                field_name=request.field_name,
                reason=usage_reason,
                confidence_before=ocr_result.confidence,
                confidence_after=gpt_result.confidence,
                success=bool(gpt_result.value and gpt_result.confidence >= 0.5),
                ticket_id=getattr(request, 'ticket_id', ''),
                error_message=request.portal_error or ''
            )

            return ValidationResult(
                final_value=gpt_result.value,
                confidence=gpt_result.confidence,
                method_used="gpt_vision_expensive",
                all_candidates=candidates,
                gpt_reasoning=gpt_result.reasoning,
                validation_context={
                    "gpt_analysis": gpt_result.context,
                    "ocr_confidence": ocr_result.confidence,
                    "ocr_backend": ocr_result.backend.value,
                    "cost_reason": usage_reason,
                    "cost_justified": True
                }
            )

        except Exception as e:
            logger.error(f"❌ Error en validación: {e}")
            return ValidationResult(
                final_value="",
                confidence=0.0,
                method_used="error",
                all_candidates=[],
                error=str(e)
            )

    def _should_use_expensive_gpt_vision(
        self,
        request: ValidationRequest,
        ocr_result: Any,
        candidates: List[str]
    ) -> bool:
        """
        Decisión crítica: ¿vale la pena gastar tokens en GPT Vision?

        SOLO usar GPT Vision si:
        1. 🚨 PORTAL RECHAZÓ (error real confirmado)
        2. 🤷 OCR muy incierto Y múltiples candidatos confusos
        3. 💪 Usuario fuerza explícitamente
        """

        # CASO 1: Portal web rechazó - USAR GPT (justificado)
        if request.portal_error:
            logger.info("✅ GPT Vision justificado: Portal rechazó con error específico")
            return True

        # CASO 2: Usuario fuerza - USAR GPT (responsabilidad del usuario)
        if request.force_gpt:
            logger.info("✅ GPT Vision justificado: Forzado por usuario")
            return True

        # CASO 3: Múltiples candidatos ambiguos Y confianza baja
        confidence_threshold = 0.6
        ambiguous_threshold = 2

        if (len(candidates) >= ambiguous_threshold and
            ocr_result.confidence < confidence_threshold):
            logger.info(f"✅ GPT Vision justificado: {len(candidates)} candidatos ambiguos + confianza baja ({ocr_result.confidence:.2f})")
            return True

        # CASO 4: No hay candidatos Y campo crítico
        critical_fields = ['folio', 'rfc_emisor']
        if (len(candidates) == 0 and
            request.field_name.lower() in critical_fields):
            logger.info(f"✅ GPT Vision justificado: Campo crítico '{request.field_name}' sin candidatos")
            return True

        # TODOS LOS DEMÁS CASOS: NO usar GPT (ahorrar dinero)
        logger.info(f"💰 Ahorrando dinero: OCR suficiente para '{request.field_name}'")
        return False

    def _resolve_with_cheap_methods(
        self,
        candidates: List[str],
        field_name: str,
        ocr_result: Any
    ) -> ValidationResult:
        """
        Resolver usando solo métodos baratos (OCR + heurísticas)
        """

        if len(candidates) == 1:
            # Un solo candidato confiable
            return ValidationResult(
                final_value=candidates[0],
                confidence=0.85,
                method_used="ocr_single_confident",
                all_candidates=candidates,
                validation_context={
                    "cost_saved": "gpt_vision_avoided",
                    "ocr_confidence": ocr_result.confidence
                }
            )

        elif len(candidates) > 1:
            # Múltiples candidatos - usar heurísticas para elegir el mejor
            best_candidate = self._select_best_candidate_heuristic(candidates, field_name)
            return ValidationResult(
                final_value=best_candidate,
                confidence=0.75,
                method_used="ocr_heuristic_selection",
                all_candidates=candidates,
                validation_context={
                    "cost_saved": "gpt_vision_avoided",
                    "selection_method": "heuristic",
                    "ocr_confidence": ocr_result.confidence
                }
            )

        else:
            # Sin candidatos - fallback a extracción básica
            basic_fields = self.ocr_service.extract_fields_from_lines(ocr_result.text.split('\n'))
            fallback_value = basic_fields.get(field_name.lower(), "")

            return ValidationResult(
                final_value=fallback_value,
                confidence=0.5,
                method_used="ocr_basic_fallback",
                all_candidates=[],
                validation_context={
                    "cost_saved": "gpt_vision_avoided",
                    "fallback_used": True
                }
            )

    def _select_best_candidate_heuristic(self, candidates: List[str], field_name: str) -> str:
        """
        Heurísticas baratas para seleccionar el mejor candidato sin GPT Vision
        """

        if field_name.lower() == 'folio':
            # Para folios: preferir más largo, menos ceros, formato alfanumérico
            return max(candidates, key=lambda x: (
                len(x),                    # Más largo
                -x.count('0'),            # Menos ceros
                any(c.isalpha() for c in x) # Tiene letras (ej: A-123456)
            ))

        elif field_name.lower() == 'rfc_emisor':
            # Para RFC: preferir 13 caracteres, formato estándar
            rfc_candidates = [c for c in candidates if len(c) in [12, 13]]
            if rfc_candidates:
                return max(rfc_candidates, key=len)  # 13 chars mejor que 12
            return candidates[0]

        elif field_name.lower() == 'monto_total':
            # Para montos: preferir formato decimal correcto
            decimal_candidates = [c for c in candidates if '.' in c and len(c.split('.')[-1]) == 2]
            if decimal_candidates:
                return max(decimal_candidates, key=lambda x: float(x) if x.replace('.', '').isdigit() else 0)
            return candidates[0]

        # Default: primer candidato
        return candidates[0]

    def _get_gpt_usage_reason(self, request: ValidationRequest, ocr_result: Any, candidates: List[str]) -> str:
        """Explicar por qué se usó GPT Vision (para auditoría de costos)"""

        if request.portal_error:
            return f"Portal rechazó: '{request.portal_error[:50]}...'"
        elif request.force_gpt:
            return "Forzado por usuario"
        elif len(candidates) >= 2 and ocr_result.confidence < 0.6:
            return f"{len(candidates)} candidatos ambiguos + baja confianza ({ocr_result.confidence:.2f})"
        elif len(candidates) == 0:
            return f"Campo crítico '{request.field_name}' sin candidatos"
        else:
            return "Razón desconocida"

    def _track_gpt_usage(self, field_name: str, reason: str, **kwargs):
        """Tracking avanzado de uso de GPT para análisis de costos"""

        try:
            from core.cost_analytics import cost_analytics

            # Tracking completo con analytics
            cost_analytics.track_gpt_usage(
                field_name=field_name,
                reason=reason,
                confidence_before=kwargs.get('confidence_before', 0.0),
                confidence_after=kwargs.get('confidence_after', 0.0),
                success=kwargs.get('success', True),
                merchant_type=kwargs.get('merchant_type', 'unknown'),
                ticket_id=kwargs.get('ticket_id', ''),
                error_message=kwargs.get('error_message', '')
            )

        except Exception as e:
            # Fallback a logging simple si analytics falla
            logger.warning(f"Analytics falló, usando logging simple: {e}")
            logger.info(f"💰 GPT_USAGE_TRACKING: campo={field_name}, razón={reason}")

        # Contador en memoria para estadísticas rápidas
        if not hasattr(self, '_gpt_usage_stats'):
            self._gpt_usage_stats = {}

        self._gpt_usage_stats[field_name] = self._gpt_usage_stats.get(field_name, 0) + 1

    async def validate_multiple_fields(
        self,
        image_data: str,
        required_fields: List[str],
        portal_errors: Dict[str, str] = None
    ) -> Dict[str, ValidationResult]:
        """
        Validar múltiples campos del mismo ticket de forma eficiente.

        Args:
            image_data: Imagen del ticket en base64
            required_fields: Lista de campos requeridos
            portal_errors: Errores específicos por campo (opcional)

        Returns:
            Diccionario con resultados por campo
        """
        results = {}
        portal_errors = portal_errors or {}

        # Procesar campos en paralelo para eficiencia
        tasks = []
        for field_name in required_fields:
            request = ValidationRequest(
                image_data=image_data,
                field_name=field_name,
                portal_error=portal_errors.get(field_name)
            )
            tasks.append(self.validate_field(request))

        # Ejecutar todas las validaciones en paralelo
        validation_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados
        for i, result in enumerate(validation_results):
            field_name = required_fields[i]
            if isinstance(result, Exception):
                results[field_name] = ValidationResult(
                    final_value="",
                    confidence=0.0,
                    method_used="error",
                    all_candidates=[],
                    error=str(result)
                )
            else:
                results[field_name] = result

        return results

    def get_summary_report(self, results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """
        Generar reporte resumen de validación para debugging/logging.

        Args:
            results: Resultados de validación por campo

        Returns:
            Reporte estructurado
        """
        report = {
            "total_fields": len(results),
            "successful_extractions": 0,
            "gpt_vision_used": 0,
            "average_confidence": 0.0,
            "fields_with_errors": [],
            "method_distribution": {},
            "field_details": {}
        }

        total_confidence = 0
        for field_name, result in results.items():
            # Contar éxitos
            if result.final_value and not result.error:
                report["successful_extractions"] += 1

            # Contar uso de GPT Vision
            if "gpt_vision" in result.method_used:
                report["gpt_vision_used"] += 1

            # Acumular confianza
            total_confidence += result.confidence

            # Errores
            if result.error:
                report["fields_with_errors"].append(field_name)

            # Distribución de métodos
            method = result.method_used
            report["method_distribution"][method] = report["method_distribution"].get(method, 0) + 1

            # Detalles por campo
            report["field_details"][field_name] = {
                "value": result.final_value,
                "confidence": result.confidence,
                "method": result.method_used,
                "candidates_found": len(result.all_candidates),
                "gpt_reasoning": result.gpt_reasoning[:100] if result.gpt_reasoning else None
            }

        # Calcular promedio de confianza
        if results:
            report["average_confidence"] = total_confidence / len(results)

        return report


# Instancia global para uso fácil
intelligent_validator = IntelligentFieldValidator()


# Funciones de conveniencia
async def validate_single_field(
    image_data: str,
    field_name: str,
    portal_error: str = None
) -> ValidationResult:
    """
    Función simple para validar un solo campo.

    Args:
        image_data: Imagen del ticket en base64
        field_name: Campo a validar (folio, rfc_emisor, monto_total)
        portal_error: Error del portal web (opcional)

    Returns:
        ValidationResult con el valor más probable
    """
    request = ValidationRequest(
        image_data=image_data,
        field_name=field_name,
        portal_error=portal_error
    )
    return await intelligent_validator.validate_field(request)


async def validate_ticket_fields(
    image_data: str,
    required_fields: List[str] = None,
    portal_errors: Dict[str, str] = None
) -> Dict[str, str]:
    """
    Función simple que retorna solo los valores finales.

    Args:
        image_data: Imagen del ticket en base64
        required_fields: Campos requeridos (default: folio, rfc_emisor, monto_total)
        portal_errors: Errores por campo (opcional)

    Returns:
        Diccionario simple {campo: valor}
    """
    if required_fields is None:
        required_fields = ['folio', 'rfc_emisor', 'monto_total']

    results = await intelligent_validator.validate_multiple_fields(
        image_data, required_fields, portal_errors
    )

    # Retornar solo valores finales
    return {
        field_name: result.final_value
        for field_name, result in results.items()
    }


if __name__ == "__main__":
    # Test del validador inteligente
    async def test_intelligent_validation():
        """Test del sistema de validación inteligente"""
        print("=== TEST VALIDADOR INTELIGENTE ===")

        # Imagen de prueba mínima
        test_image = "/9j/4AAQSkZJRgABAQAAAQABAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2NjIpLCBxdWFsaXR5ID0gOTAK/9sAQwADAgIDAgIDAwMDBAMDBAUIBQUEBAUKBwcGCAwKDAwLCgsLDQ4SEA0OEQ4LCxAWEBETFBUVFQwPFxgWFBgSFBUU/9sAQwEDBAQFBAUJBQUJFA0LDRQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU/8AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8A/fyiiigD/9k="

        # Test 1: Validación simple
        print("\n1. Validación de campo único:")
        result = await validate_single_field(test_image, "folio")
        print(f"   Folio: '{result.final_value}' (confianza: {result.confidence:.2f})")
        print(f"   Método: {result.method_used}")
        print(f"   Candidatos: {result.all_candidates}")

        # Test 2: Validación múltiple
        print("\n2. Validación múltiple:")
        fields = await validate_ticket_fields(test_image)
        for field, value in fields.items():
            print(f"   {field}: '{value}'")

        # Test 3: Con error de portal
        print("\n3. Validación con error de portal:")
        result_with_error = await validate_single_field(
            test_image,
            "folio",
            portal_error="El folio ingresado no es válido"
        )
        print(f"   Folio corregido: '{result_with_error.final_value}'")
        print(f"   Razonamiento GPT: {result_with_error.gpt_reasoning[:150]}...")

    # Ejecutar test
    asyncio.run(test_intelligent_validation())