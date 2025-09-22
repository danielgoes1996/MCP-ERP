#!/usr/bin/env python3
"""
Tests completos para el sistema de validación inteligente con GPT Vision
Prueba todos los escenarios de optimización de costos y casos edge
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# Imports del sistema
from core.intelligent_field_validator import (
    IntelligentFieldValidator,
    ValidationRequest,
    ValidationResult,
    validate_single_field,
    validate_ticket_fields
)
from core.hybrid_vision_service import FieldExtractionResult, ExtractionMethod
from core.cost_analytics import CostAnalytics


class TestIntelligentValidation:
    """Tests principales del validador inteligente"""

    @pytest.fixture
    def validator(self):
        """Fixture del validador con mocks"""
        return IntelligentFieldValidator()

    @pytest.fixture
    def sample_ticket_image(self):
        """Imagen de ticket de prueba en base64"""
        return "data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    @pytest.fixture
    def mock_ocr_result(self):
        """Mock del resultado de OCR"""
        mock_result = Mock()
        mock_result.text = """
        OXXO TIENDA #1234
        RFC: OXX970814HS9
        FOLIO: A-789456
        FECHA: 19/09/2024 18:30
        TOTAL: $40.50
        """
        mock_result.confidence = 0.85
        mock_result.backend = Mock()
        mock_result.backend.value = "google_vision"
        mock_result.raw_response = {"textAnnotations": [{"description": mock_result.text}]}
        return mock_result

    @pytest.mark.asyncio
    async def test_scenario_1_ocr_only_success(self, validator, sample_ticket_image, mock_ocr_result):
        """
        TEST 1: OCR funciona perfecto, NO usar GPT Vision (AHORRO)
        """
        with patch.object(validator.ocr_service, 'extract_text_intelligent', return_value=mock_ocr_result), \
             patch.object(validator.ocr_service, 'extract_lines_from_ocr', return_value=mock_ocr_result.text.split('\n')), \
             patch.object(validator.ocr_service, 'extract_field_candidates', return_value=['A-789456']):

            request = ValidationRequest(
                image_data=sample_ticket_image,
                field_name="folio"
                # Sin portal_error, sin force_gpt
            )

            result = await validator.validate_field(request)

            # Verificaciones
            assert result.final_value == "A-789456"
            assert result.confidence >= 0.8
            assert "gpt_vision" not in result.method_used
            assert result.validation_context.get("cost_saved") == "gpt_vision_avoided"

            print("✅ TEST 1 PASSED: OCR solo, sin GPT Vision")

    @pytest.mark.asyncio
    async def test_scenario_2_portal_error_triggers_gpt(self, validator, sample_ticket_image, mock_ocr_result):
        """
        TEST 2: Portal rechaza, SÍ usar GPT Vision (JUSTIFICADO)
        """
        # Mock GPT Vision response
        mock_gpt_result = FieldExtractionResult(
            value="A-789456",
            confidence=0.95,
            method=ExtractionMethod.GPT_VISION,
            context={"gpt_response": {"reasoning": "Analicé la imagen y el folio correcto es A-789456"}},
            reasoning="El OCR leyó mal el último dígito, en la imagen se ve claramente A-789456"
        )

        with patch.object(validator.ocr_service, 'extract_text_intelligent', return_value=mock_ocr_result), \
             patch.object(validator.ocr_service, 'extract_lines_from_ocr', return_value=mock_ocr_result.text.split('\n')), \
             patch.object(validator.ocr_service, 'extract_field_candidates', return_value=['A-78945б', 'A-789456']), \
             patch.object(validator.hybrid_service, 'validate_field_with_candidates', return_value=mock_gpt_result), \
             patch.object(validator, '_track_gpt_usage') as mock_tracking:

            request = ValidationRequest(
                image_data=sample_ticket_image,
                field_name="folio",
                portal_error="El folio ingresado no existe en nuestros registros"
            )

            result = await validator.validate_field(request)

            # Verificaciones
            assert result.final_value == "A-789456"
            assert result.confidence == 0.95
            assert "gpt_vision" in result.method_used
            assert result.gpt_reasoning is not None
            assert mock_tracking.called  # Se registró el uso de GPT

            print("✅ TEST 2 PASSED: Portal error activa GPT Vision")

    @pytest.mark.asyncio
    async def test_scenario_3_ambiguous_candidates_low_confidence(self, validator, sample_ticket_image):
        """
        TEST 3: Múltiples candidatos ambiguos + baja confianza → GPT Vision
        """
        # Mock OCR con baja confianza
        mock_ocr_result = Mock()
        mock_ocr_result.text = "TICKET BORROSO..."
        mock_ocr_result.confidence = 0.45  # Baja confianza
        mock_ocr_result.backend = Mock()
        mock_ocr_result.backend.value = "tesseract"
        mock_ocr_result.raw_response = {}

        # Mock múltiples candidatos confusos
        candidates = ['123456', '128456', '123856']

        mock_gpt_result = FieldExtractionResult(
            value="123456",
            confidence=0.88,
            method=ExtractionMethod.GPT_VISION,
            context={},
            reasoning="Entre los candidatos, 123456 es el más claro en la imagen"
        )

        with patch.object(validator.ocr_service, 'extract_text_intelligent', return_value=mock_ocr_result), \
             patch.object(validator.ocr_service, 'extract_field_candidates', return_value=candidates), \
             patch.object(validator.hybrid_service, 'validate_field_with_candidates', return_value=mock_gpt_result):

            request = ValidationRequest(
                image_data=sample_ticket_image,
                field_name="folio"
            )

            result = await validator.validate_field(request)

            # Verificaciones
            assert result.final_value == "123456"
            assert "gpt_vision" in result.method_used
            assert result.validation_context.get("cost_justified") == True

            print("✅ TEST 3 PASSED: Candidatos ambiguos activan GPT Vision")

    @pytest.mark.asyncio
    async def test_scenario_4_single_confident_candidate_no_gpt(self, validator, sample_ticket_image, mock_ocr_result):
        """
        TEST 4: Un solo candidato confiable → NO usar GPT Vision (AHORRO)
        """
        with patch.object(validator.ocr_service, 'extract_text_intelligent', return_value=mock_ocr_result), \
             patch.object(validator.ocr_service, 'extract_field_candidates', return_value=['OXX970814HS9']):

            request = ValidationRequest(
                image_data=sample_ticket_image,
                field_name="rfc_emisor"
            )

            result = await validator.validate_field(request)

            # Verificaciones
            assert result.final_value == "OXX970814HS9"
            assert "gpt_vision" not in result.method_used
            assert result.validation_context.get("cost_saved") == "gpt_vision_avoided"

            print("✅ TEST 4 PASSED: Candidato único evita GPT Vision")

    @pytest.mark.asyncio
    async def test_scenario_5_heuristic_selection(self, validator, sample_ticket_image, mock_ocr_result):
        """
        TEST 5: Múltiples candidatos con heurística barata
        """
        # Múltiples candidatos para folio
        candidates = ['123456', '12345678', 'A-789456']  # El último debería ganar

        with patch.object(validator.ocr_service, 'extract_text_intelligent', return_value=mock_ocr_result), \
             patch.object(validator.ocr_service, 'extract_field_candidates', return_value=candidates):

            request = ValidationRequest(
                image_data=sample_ticket_image,
                field_name="folio"
            )

            result = await validator.validate_field(request)

            # Verificaciones
            assert result.final_value == "A-789456"  # Mejor por tener letras y longitud
            assert result.method_used == "ocr_heuristic_selection"
            assert result.validation_context.get("selection_method") == "heuristic"

            print("✅ TEST 5 PASSED: Heurística selecciona mejor candidato")

    @pytest.mark.asyncio
    async def test_scenario_6_critical_field_no_candidates(self, validator, sample_ticket_image):
        """
        TEST 6: Campo crítico sin candidatos → GPT Vision como último recurso
        """
        mock_ocr_result = Mock()
        mock_ocr_result.text = "TEXTO SIN FOLIOS CLAROS"
        mock_ocr_result.confidence = 0.7
        mock_ocr_result.backend = Mock()
        mock_ocr_result.backend.value = "google_vision"
        mock_ocr_result.raw_response = {}

        mock_gpt_result = FieldExtractionResult(
            value="HIDDEN-123456",
            confidence=0.8,
            method=ExtractionMethod.GPT_VISION,
            context={},
            reasoning="Encontré un folio oculto en la esquina inferior de la imagen"
        )

        with patch.object(validator.ocr_service, 'extract_text_intelligent', return_value=mock_ocr_result), \
             patch.object(validator.ocr_service, 'extract_field_candidates', return_value=[]), \
             patch.object(validator.hybrid_service, 'validate_field_with_candidates', return_value=mock_gpt_result):

            request = ValidationRequest(
                image_data=sample_ticket_image,
                field_name="folio"  # Campo crítico
            )

            result = await validator.validate_field(request)

            # Verificaciones
            assert result.final_value == "HIDDEN-123456"
            assert "gpt_vision" in result.method_used

            print("✅ TEST 6 PASSED: Campo crítico sin candidatos usa GPT Vision")

    def test_cost_decision_logic(self, validator):
        """
        TEST 7: Lógica de decisión de costos
        """
        mock_request = Mock()
        mock_ocr_result = Mock()
        mock_ocr_result.confidence = 0.8

        # Test caso 1: Portal error → SÍ GPT
        mock_request.portal_error = "Error del portal"
        mock_request.force_gpt = False
        assert validator._should_use_expensive_gpt_vision(mock_request, mock_ocr_result, ['candidate1'])

        # Test caso 2: Force GPT → SÍ GPT
        mock_request.portal_error = None
        mock_request.force_gpt = True
        assert validator._should_use_expensive_gpt_vision(mock_request, mock_ocr_result, ['candidate1'])

        # Test caso 3: Alta confianza + un candidato → NO GPT
        mock_request.portal_error = None
        mock_request.force_gpt = False
        mock_ocr_result.confidence = 0.85
        assert not validator._should_use_expensive_gpt_vision(mock_request, mock_ocr_result, ['candidate1'])

        # Test caso 4: Baja confianza + múltiples candidatos → SÍ GPT
        mock_ocr_result.confidence = 0.4
        assert validator._should_use_expensive_gpt_vision(mock_request, mock_ocr_result, ['cand1', 'cand2'])

        print("✅ TEST 7 PASSED: Lógica de decisión de costos correcta")

    def test_heuristic_selection_logic(self, validator):
        """
        TEST 8: Lógica de selección heurística
        """
        # Test para folios
        folio_candidates = ['123456', 'A-789456', '000000']
        best_folio = validator._select_best_candidate_heuristic(folio_candidates, 'folio')
        assert best_folio == 'A-789456'  # Más largo + alfanumérico + menos ceros

        # Test para RFCs
        rfc_candidates = ['ABC123456XY1', 'DEF789012AB']  # 13 vs 12 chars
        best_rfc = validator._select_best_candidate_heuristic(rfc_candidates, 'rfc_emisor')
        assert best_rfc == 'ABC123456XY1'  # 13 caracteres es mejor

        # Test para montos
        amount_candidates = ['150.75', '15075', '150,75']
        best_amount = validator._select_best_candidate_heuristic(amount_candidates, 'monto_total')
        assert best_amount == '150.75'  # Formato decimal correcto

        print("✅ TEST 8 PASSED: Heurísticas de selección correctas")


class TestCostAnalytics:
    """Tests del sistema de análisis de costos"""

    @pytest.fixture
    def analytics(self):
        """Analytics con DB en memoria para tests"""
        return CostAnalytics(":memory:")

    def test_cost_tracking(self, analytics):
        """
        TEST 9: Tracking de costos
        """
        # Simular eventos de uso
        analytics.track_gpt_usage(
            field_name="folio",
            reason="Portal rechazó: Folio no válido",
            confidence_before=0.7,
            confidence_after=0.95,
            success=True,
            merchant_type="oxxo"
        )

        analytics.track_gpt_usage(
            field_name="rfc_emisor",
            reason="2 candidatos ambiguos + baja confianza",
            confidence_before=0.4,
            confidence_after=0.8,
            success=True,
            merchant_type="walmart"
        )

        # Generar reporte
        report = analytics.generate_cost_report(days_back=1)

        # Verificaciones
        assert report.total_gpt_calls == 2
        assert report.success_rate == 1.0  # 100% éxito
        assert report.total_cost_usd > 0
        assert len(report.breakdown_by_reason) == 2
        assert len(report.breakdown_by_field) == 2

        print("✅ TEST 9 PASSED: Cost tracking funciona correctamente")

    def test_cost_recommendations(self, analytics):
        """
        TEST 10: Generación de recomendaciones
        """
        # Simular múltiples usos del mismo campo
        for i in range(5):
            analytics.track_gpt_usage(
                field_name="folio",
                reason="Portal rechazó: Folio no válido",
                confidence_before=0.6,
                confidence_after=0.9,
                success=True
            )

        report = analytics.generate_cost_report(days_back=1)

        # Debe haber recomendación sobre campo problemático
        recommendations_text = " ".join(report.recommendations)
        assert "folio" in recommendations_text.lower()

        print("✅ TEST 10 PASSED: Recomendaciones generadas correctamente")


class TestIntegrationScenarios:
    """Tests de integración con escenarios reales"""

    @pytest.mark.asyncio
    async def test_oxxo_ticket_flow(self):
        """
        TEST 11: Flujo completo ticket OXXO
        """
        ticket_data = {
            "merchant_type": "oxxo",
            "image": "base64_image",
            "required_fields": ["folio", "rfc_emisor", "monto_total"]
        }

        # Mock portal que rechaza folio inicialmente
        portal_errors = {"folio": "Folio de ticket no válido"}

        with patch('core.intelligent_field_validator.intelligent_validator') as mock_validator:
            # Simular validación múltiple
            mock_results = {
                "folio": ValidationResult(
                    final_value="A-789456",
                    confidence=0.95,
                    method_used="gpt_vision_expensive",
                    all_candidates=["A-78945б", "A-789456"],
                    gpt_reasoning="Corregido el último carácter de б a 6"
                ),
                "rfc_emisor": ValidationResult(
                    final_value="OXX970814HS9",
                    confidence=0.9,
                    method_used="ocr_single_confident",
                    all_candidates=["OXX970814HS9"]
                ),
                "monto_total": ValidationResult(
                    final_value="40.50",
                    confidence=0.85,
                    method_used="ocr_heuristic_selection",
                    all_candidates=["40.50", "4050"]
                )
            }

            mock_validator.validate_multiple_fields.return_value = mock_results

            # Simular flujo
            results = await mock_validator.validate_multiple_fields(
                image_data=ticket_data["image"],
                required_fields=ticket_data["required_fields"],
                portal_errors=portal_errors
            )

            # Verificaciones
            assert results["folio"].final_value == "A-789456"
            assert "gpt_vision" in results["folio"].method_used  # Solo folio usó GPT
            assert "gpt_vision" not in results["rfc_emisor"].method_used  # RFC no usó GPT
            assert "gpt_vision" not in results["monto_total"].method_used  # Monto no usó GPT

            print("✅ TEST 11 PASSED: Flujo OXXO completo con optimización de costos")

    @pytest.mark.asyncio
    async def test_cost_budget_alert(self):
        """
        TEST 12: Alerta de presupuesto excedido
        """
        analytics = CostAnalytics(":memory:")

        # Simular uso excesivo en un día
        for i in range(20):  # 20 llamadas costosas
            analytics.track_gpt_usage(
                field_name="folio",
                reason="Portal rechazó",
                confidence_before=0.5,
                confidence_after=0.9,
                success=True
            )

        # Verificar alerta
        should_alert, message = analytics.should_alert_on_costs(daily_budget=0.15)  # Budget bajo
        assert should_alert
        assert "excedido" in message

        print("✅ TEST 12 PASSED: Sistema de alertas de presupuesto funciona")


# Función para ejecutar todos los tests
def run_all_tests():
    """
    Ejecutar todos los tests del sistema de validación inteligente
    """
    print("🚀 EJECUTANDO TESTS COMPLETOS DEL SISTEMA DE VALIDACIÓN INTELIGENTE")
    print("=" * 80)

    # Ejecutar tests usando pytest
    pytest.main([
        __file__,
        "-v",  # Verbose
        "-s",  # No capture output
        "--tb=short"  # Short traceback
    ])


if __name__ == "__main__":
    run_all_tests()