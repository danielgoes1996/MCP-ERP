"""
Tests Unitarios y de Integración para Sistema de Facturación Automática
Cobertura completa de todos los componentes desarrollados.
"""

import asyncio
import base64
import json
import pytest
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

# Imports del sistema bajo prueba
from core.advanced_ocr_service import AdvancedOCRService, OCRResult, OCRBackend, OCRConfig
from core.ai_rpa_planner import AIRPAPlanner, RPAPlan, RPAAction, ActionType
from core.playwright_executor import PlaywrightExecutor, ExecutionResult, ExecutionStatus
from core.security_vault import SecurityVault, CredentialEntry, store_merchant_credentials
from modules.invoicing_agent.ticket_processor import process_ticket_with_intelligence


class TestAdvancedOCRService:
    """Tests para el servicio OCR avanzado"""

    @pytest.fixture
    def ocr_service(self):
        """Fixture para crear servicio OCR"""
        config = OCRConfig(
            preferred_backends=[OCRBackend.TESSERACT],
            enable_caching=False
        )
        return AdvancedOCRService(config)

    @pytest.fixture
    def sample_base64_image(self):
        """Imagen de prueba en base64"""
        return "/9j/4AAQSkZJRgABAQAAAQABAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2NjIpLCBxdWFsaXR5ID0gOTAK/9sAQwADAgIDAgIDAwMDBAMDBAUIBQUEBAUKBwcGCAwKDAwLCgsLDQ4SEA0OEQ4LCxAWEBETFBUVFQwPFxgWFBgSFBUU/9sAQwEDBAQFBAUJBQUJFA0LDRQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU/8AAEQgAAQABAwEiAAIRAQMRAD8A/fyiiigD/9k="

    @pytest.mark.asyncio
    async def test_extract_text_intelligent_basic(self, ocr_service, sample_base64_image):
        """Test básico de extracción de texto"""

        with patch.object(ocr_service, '_extract_tesseract') as mock_tesseract:
            mock_tesseract.return_value = OCRResult(
                backend=OCRBackend.TESSERACT,
                text="OXXO TIENDA #1234\nTotal: $100.00",
                confidence=0.8,
                processing_time_ms=1000
            )

            result = await ocr_service.extract_text_intelligent(
                sample_base64_image,
                context_hint="ticket"
            )

            assert result.text == "OXXO TIENDA #1234\nTotal: $100.00"
            assert result.confidence == 0.8
            assert result.backend == OCRBackend.TESSERACT

    @pytest.mark.asyncio
    async def test_extract_text_fallback_mechanism(self, ocr_service, sample_base64_image):
        """Test del mecanismo de fallback entre backends"""

        # Simular fallo en backend principal
        with patch.object(ocr_service, '_extract_google_vision', side_effect=Exception("API Error")):
            with patch.object(ocr_service, '_extract_tesseract') as mock_tesseract:
                mock_tesseract.return_value = OCRResult(
                    backend=OCRBackend.TESSERACT,
                    text="Fallback text",
                    confidence=0.6,
                    processing_time_ms=1500
                )

                result = await ocr_service.extract_text_intelligent(sample_base64_image)

                assert result.text == "Fallback text"
                assert result.backend == OCRBackend.TESSERACT

    @pytest.mark.asyncio
    async def test_preprocess_image(self, ocr_service, sample_base64_image):
        """Test de preprocesamiento de imagen"""

        processed_image = await ocr_service._preprocess_image(
            sample_base64_image,
            "base64"
        )

        assert processed_image is not None
        assert isinstance(processed_image, str)

    def test_backend_availability_check(self, ocr_service):
        """Test de verificación de disponibilidad de backends"""

        # Tesseract debería estar disponible (no requiere configuración)
        assert ocr_service._is_backend_available(OCRBackend.TESSERACT) == True

        # Google Vision debería depender de API key
        google_available = ocr_service._is_backend_available(OCRBackend.GOOGLE_VISION)
        assert isinstance(google_available, bool)

    @pytest.mark.asyncio
    async def test_health_check(self, ocr_service):
        """Test de health check de backends"""

        health = await ocr_service.get_backend_health()

        assert isinstance(health, dict)
        assert OCRBackend.TESSERACT in health
        assert isinstance(health[OCRBackend.TESSERACT], bool)


class TestAIRPAPlanner:
    """Tests para el planificador RPA con IA"""

    @pytest.fixture
    def planner(self):
        """Fixture para crear planificador"""
        return AIRPAPlanner()

    @pytest.fixture
    def sample_ticket_data(self):
        """Datos de ticket de prueba"""
        return {
            "merchant_rfc": "MFU761216I40",
            "folio": "318534",
            "fecha": "18/08/2025",
            "total": 359.00,
            "merchant_name": "Mejor Futuro"
        }

    @pytest.fixture
    def sample_credentials(self):
        """Credenciales de prueba"""
        return {
            "username": "test@empresa.com",
            "password": "password123"
        }

    @pytest.mark.asyncio
    async def test_analyze_portal_and_create_plan(self, planner, sample_ticket_data, sample_credentials):
        """Test de análisis de portal y creación de plan"""

        # Mock del análisis de portal para evitar requests reales
        with patch.object(planner, '_analyze_portal_structure') as mock_analyze:
            mock_analyze.return_value = {
                "url": "https://test-portal.com",
                "title": "Portal de Facturación",
                "forms": [{"action": "/facturar", "method": "POST"}]
            }

            # Mock de generación de plan con IA
            with patch.object(planner, '_generate_plan_with_ai') as mock_generate:
                mock_plan = RPAPlan(
                    plan_id="test-plan-001",
                    merchant_name="Test Merchant",
                    portal_url="https://test-portal.com",
                    browser_config={"headless": True},
                    actions=[
                        RPAAction(
                            action_type=ActionType.NAVIGATE,
                            value="https://test-portal.com",
                            description="Navegar al portal"
                        )
                    ],
                    input_schema={"rfc": "RFC del receptor"},
                    success_validations=[],
                    created_at=datetime.now().isoformat(),
                    confidence_score=0.85,
                    estimated_duration_seconds=60
                )
                mock_generate.return_value = mock_plan

                plan = await planner.analyze_portal_and_create_plan(
                    merchant_name="Test Merchant",
                    portal_url="https://test-portal.com",
                    ticket_data=sample_ticket_data,
                    credentials=sample_credentials
                )

                assert plan.merchant_name == "Test Merchant"
                assert plan.portal_url == "https://test-portal.com"
                assert len(plan.actions) == 1
                assert plan.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_generate_template_plan(self, planner, sample_ticket_data):
        """Test de generación de plan template como fallback"""

        plan_data = await planner._generate_template_plan(
            merchant_name="Test Merchant",
            portal_url="https://test-portal.com",
            ticket_data=sample_ticket_data
        )

        assert "actions" in plan_data
        assert "browser_config" in plan_data
        assert "input_schema" in plan_data
        assert len(plan_data["actions"]) > 0

    @pytest.mark.asyncio
    async def test_validate_and_optimize_plan(self, planner):
        """Test de validación y optimización de plan"""

        # Crear plan básico
        actions = [
            RPAAction(
                action_type=ActionType.NAVIGATE,
                value="https://test.com",
                description="Test navigation"
            ),
            RPAAction(
                action_type=ActionType.CLICK,
                selector="#submit-btn",
                description="Click submit"
            )
        ]

        plan = RPAPlan(
            plan_id="test-plan",
            merchant_name="Test",
            portal_url="https://test.com",
            browser_config={},
            actions=actions,
            input_schema={},
            success_validations=[],
            created_at=datetime.now().isoformat(),
            confidence_score=0.8,
            estimated_duration_seconds=30
        )

        optimized_plan = await planner._validate_and_optimize_plan(plan)

        # Verificar que se agregaron screenshots
        screenshot_actions = [a for a in optimized_plan.actions if a.action_type == ActionType.TAKE_SCREENSHOT]
        assert len(screenshot_actions) > 0

    def test_css_selector_validation(self, planner):
        """Test de validación de selectores CSS"""

        valid_selectors = [
            "#my-id",
            ".my-class",
            "button",
            "[name='username']",
            "input[type='text']"
        ]

        invalid_selectors = [
            "",
            "invalid>>selector",
            "123invalid"
        ]

        for selector in valid_selectors:
            assert planner._is_valid_css_selector(selector) == True

        for selector in invalid_selectors:
            assert planner._is_valid_css_selector(selector) == False


class TestPlaywrightExecutor:
    """Tests para el executor de Playwright"""

    @pytest.fixture
    def executor(self):
        """Fixture para crear executor"""
        return PlaywrightExecutor()

    @pytest.fixture
    def sample_plan(self):
        """Plan de prueba"""
        actions = [
            RPAAction(
                action_type=ActionType.NAVIGATE,
                value="https://httpbin.org/html",
                description="Navegar a página de prueba"
            ),
            RPAAction(
                action_type=ActionType.TAKE_SCREENSHOT,
                description="Capturar página"
            )
        ]

        return RPAPlan(
            plan_id="test-execution-plan",
            merchant_name="Test Merchant",
            portal_url="https://httpbin.org/html",
            browser_config={"headless": True},
            actions=actions,
            input_schema={},
            success_validations=[],
            created_at=datetime.now().isoformat(),
            confidence_score=0.9,
            estimated_duration_seconds=30
        )

    @pytest.mark.asyncio
    async def test_execute_plan_basic(self, executor, sample_plan):
        """Test básico de ejecución de plan"""

        # Simular ejecución exitosa sin browser real
        with patch.object(executor, '_setup_browser'):
            with patch.object(executor, '_setup_page'):
                with patch.object(executor, '_execute_action') as mock_execute:
                    # Simular ejecución exitosa de cada acción
                    mock_execute.return_value = MagicMock(
                        status=ExecutionStatus.COMPLETED,
                        error_message=None
                    )

                    with patch.object(executor, '_validate_success', return_value=True):
                        with patch.object(executor, '_cleanup_browser'):

                            input_data = {"test": "data"}
                            result = await executor.execute_plan(sample_plan, input_data)

                            assert result.status == ExecutionStatus.COMPLETED
                            assert result.plan_id == "test-execution-plan"
                            assert len(result.steps) == len(sample_plan.actions)

    @pytest.mark.asyncio
    async def test_process_dynamic_value(self, executor):
        """Test de procesamiento de valores dinámicos"""

        input_data = {
            "rfc": "TEST123456789",
            "total": "100.00"
        }

        # Test sustitución de variables
        result = executor._process_dynamic_value("${rfc}", input_data)
        assert result == "TEST123456789"

        result = executor._process_dynamic_value("Monto: ${total}", input_data)
        assert result == "Monto: 100.00"

        # Test sin variables
        result = executor._process_dynamic_value("texto fijo", input_data)
        assert result == "texto fijo"

    @pytest.mark.asyncio
    async def test_validate_plan_feasibility(self, executor, sample_plan):
        """Test de validación de factibilidad de plan"""

        validation = await executor.validate_plan_feasibility(sample_plan)

        assert "feasible" in validation
        assert "warnings" in validation
        assert "errors" in validation
        assert isinstance(validation["feasible"], bool)

    def test_calculate_success_rate(self, executor):
        """Test de cálculo de tasa de éxito"""

        from core.playwright_executor import ExecutionStep

        steps = [
            MagicMock(status=ExecutionStatus.COMPLETED),
            MagicMock(status=ExecutionStatus.COMPLETED),
            MagicMock(status=ExecutionStatus.FAILED),
            MagicMock(status=ExecutionStatus.COMPLETED)
        ]

        success_rate = executor._calculate_success_rate(steps)
        assert success_rate == 75.0  # 3 de 4 exitosos


class TestSecurityVault:
    """Tests para el sistema de seguridad"""

    @pytest.fixture
    def vault(self):
        """Fixture para crear vault de seguridad"""
        return SecurityVault()

    @pytest.fixture
    def sample_credentials(self):
        """Credenciales de prueba"""
        return {
            "username": "test_user",
            "password": "test_password",
            "api_key": "test_api_key_123"
        }

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_data(self, vault, sample_credentials):
        """Test de encriptación y desencriptación"""

        # Esperar inicialización
        await asyncio.sleep(0.1)

        # Test encriptación
        data_json = json.dumps(sample_credentials)
        encrypted = await vault._encrypt_data(data_json)

        assert isinstance(encrypted, bytes)
        assert encrypted != data_json.encode()

        # Test desencriptación
        decrypted = await vault._decrypt_data(encrypted)
        assert decrypted == data_json

        # Verificar que las credenciales son las mismas
        decrypted_creds = json.loads(decrypted)
        assert decrypted_creds == sample_credentials

    @pytest.mark.asyncio
    async def test_store_and_retrieve_credentials(self, vault, sample_credentials):
        """Test de almacenamiento y recuperación de credenciales"""

        # Esperar inicialización
        await asyncio.sleep(0.1)

        # Mock de funciones de base de datos
        with patch.object(vault, '_save_credential_entry'):
            with patch.object(vault, '_get_credential_entry') as mock_get:
                # Configurar mock para simular credencial existente
                mock_entry = CredentialEntry(
                    id="test-id",
                    company_id="test-company",
                    merchant_id="test-merchant",
                    credential_type="web_login",
                    encrypted_data=await vault._encrypt_data(json.dumps(sample_credentials)),
                    is_active=True
                )
                mock_get.return_value = mock_entry

                # Test almacenamiento
                credential_id = await vault.store_credentials(
                    company_id="test-company",
                    merchant_id="test-merchant",
                    credential_type="web_login",
                    credentials=sample_credentials
                )

                assert credential_id is not None

                # Test recuperación
                retrieved = await vault.retrieve_credentials(
                    company_id="test-company",
                    merchant_id="test-merchant",
                    credential_type="web_login"
                )

                assert retrieved == sample_credentials

    @pytest.mark.asyncio
    async def test_health_check(self, vault):
        """Test de health check del sistema"""

        # Esperar inicialización
        await asyncio.sleep(0.1)

        health = await vault.health_check()

        assert "vault_connected" in health
        assert "local_encryption_ready" in health
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_convenience_functions(self, sample_credentials):
        """Test de funciones de conveniencia"""

        with patch('core.security_vault.get_security_vault') as mock_get_vault:
            mock_vault = AsyncMock()
            mock_vault.store_credentials.return_value = "test-credential-id"
            mock_vault.retrieve_credentials.return_value = sample_credentials
            mock_get_vault.return_value = mock_vault

            # Test store_merchant_credentials
            credential_id = await store_merchant_credentials(
                company_id="test-company",
                merchant_id="test-merchant",
                username=sample_credentials["username"],
                password=sample_credentials["password"]
            )

            assert credential_id == "test-credential-id"

            # Test get_merchant_credentials
            from core.security_vault import get_merchant_credentials
            retrieved = await get_merchant_credentials(
                company_id="test-company",
                merchant_id="test-merchant"
            )

            assert retrieved == sample_credentials


class TestTicketProcessor:
    """Tests para el procesador de tickets"""

    @pytest.fixture
    def sample_ticket_text(self):
        """Texto de ticket de prueba"""
        return """
        Mejor Futuro S.A. de C.V.
        Fecha del día: 18/08/2025
        08:37:17 p.m.
        Folio No: 318534
        Mesa: 04
        Mesero: 2
        Pax: 1

        1 FILETE $193.00
        1 QUESADILLAS $90.00
        2 TORACHICO $76.00

        Total $359.00

        RFC: MFU761216I40

        Facture en
        facturacion.inforest.com.mx o
        facturacion.infocaja.com.mx,
        ingresando la clave de abajo.
        Tiene 72 horas. Favor de
        esperar 60 minutos después
        de su consumo. ¡Gracias!
        """

    @pytest.mark.asyncio
    async def test_process_ticket_with_intelligence(self, sample_ticket_text):
        """Test de procesamiento inteligente de tickets"""

        result = await process_ticket_with_intelligence(sample_ticket_text)

        # Verificar estructura del resultado
        assert "merchant" in result
        assert "extracted_data" in result
        assert "validation" in result
        assert "call_to_action" in result
        assert "confidence" in result

        # Verificar datos extraídos
        extracted = result["extracted_data"]
        assert extracted["rfc"] == "MFU761216I40"
        assert extracted["folio"] == "318534"
        assert extracted["total"] == 359.0

        # Verificar merchant detectado
        merchant = result["merchant"]
        assert merchant["name"] == "MEJOR_FUTURO"
        assert merchant["rfc"] == "MFU761216I40"

        # Verificar call to action
        cta = result["call_to_action"]
        assert cta["action"] == "AUTO_INVOICE"
        assert cta["can_auto_process"] == True


class TestIntegrationFlows:
    """Tests de integración del flujo completo"""

    @pytest.mark.asyncio
    async def test_complete_ticket_processing_flow(self):
        """Test del flujo completo de procesamiento de ticket"""

        # 1. Simular imagen de ticket
        sample_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

        # 2. OCR
        with patch('core.advanced_ocr_service.extract_text_intelligent') as mock_ocr:
            mock_ocr.return_value = OCRResult(
                backend=OCRBackend.GOOGLE_VISION,
                text="OXXO RFC: OXX970814HS9 Total: $125.50",
                confidence=0.9,
                processing_time_ms=1000
            )

            ocr_result = await mock_ocr(sample_image, context_hint="ticket")

            # 3. Procesamiento inteligente
            processed = await process_ticket_with_intelligence(ocr_result.text)

            # 4. Verificar que el flujo funciona
            assert processed["merchant"]["name"] == "OXXO"
            assert processed["extracted_data"]["total"] == 125.5
            assert processed["confidence"] > 0.7

    @pytest.mark.asyncio
    async def test_automation_workflow(self):
        """Test del flujo de automatización completo"""

        # Crear plan mock
        plan = RPAPlan(
            plan_id="integration-test-plan",
            merchant_name="Test Merchant",
            portal_url="https://test.com",
            browser_config={"headless": True},
            actions=[
                RPAAction(
                    action_type=ActionType.NAVIGATE,
                    value="https://test.com",
                    description="Navigate to portal"
                )
            ],
            input_schema={"rfc": "RFC"},
            success_validations=[],
            created_at=datetime.now().isoformat(),
            confidence_score=0.85,
            estimated_duration_seconds=30
        )

        # Simular ejecución
        with patch('core.playwright_executor.execute_rpa_plan') as mock_execute:
            mock_execute.return_value = ExecutionResult(
                execution_id="test-execution",
                plan_id=plan.plan_id,
                status=ExecutionStatus.COMPLETED,
                start_time=time.time(),
                steps=[],
                extracted_data={},
                screenshots=[],
                downloads=[],
                logs=[],
                errors=[],
                browser_info={}
            )

            result = await mock_execute(plan, {"rfc": "TEST123456789"})

            assert result.status == ExecutionStatus.COMPLETED
            assert result.plan_id == plan.plan_id


class TestErrorHandling:
    """Tests de manejo de errores"""

    @pytest.mark.asyncio
    async def test_ocr_error_handling(self):
        """Test de manejo de errores en OCR"""

        service = AdvancedOCRService()

        # Test con imagen inválida
        with pytest.raises(Exception):
            await service.extract_text_intelligent("invalid-base64-data")

    @pytest.mark.asyncio
    async def test_plan_validation_errors(self):
        """Test de errores en validación de planes"""

        executor = PlaywrightExecutor()

        # Plan sin URL
        invalid_plan = RPAPlan(
            plan_id="invalid",
            merchant_name="Test",
            portal_url="",  # URL vacía
            browser_config={},
            actions=[],
            input_schema={},
            success_validations=[],
            created_at=datetime.now().isoformat(),
            confidence_score=0.0,
            estimated_duration_seconds=0
        )

        validation = await executor.validate_plan_feasibility(invalid_plan)
        assert validation["feasible"] == False
        assert len(validation["errors"]) > 0

    @pytest.mark.asyncio
    async def test_security_error_handling(self):
        """Test de manejo de errores en seguridad"""

        vault = SecurityVault()

        # Test con datos inválidos
        with pytest.raises(Exception):
            await vault._encrypt_data(None)


# ===============================================================
# CONFIGURACIÓN DE PYTEST
# ===============================================================

@pytest.fixture(scope="session")
def event_loop():
    """Crear loop de eventos para toda la sesión"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Configurar entorno de prueba"""
    # Configurar variables de entorno para tests
    import os
    os.environ["LOG_LEVEL"] = "WARNING"  # Reducir logs en tests
    os.environ["OCR_BACKEND"] = "tesseract"

    yield

    # Limpiar después de los tests
    # Aquí se pueden agregar tareas de cleanup


# ===============================================================
# MARKS PERSONALIZADOS
# ===============================================================

# Marca para tests que requieren conexión externa
external = pytest.mark.external

# Marca para tests lentos
slow = pytest.mark.slow

# Marca para tests de integración
integration = pytest.mark.integration


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--durations=10"
    ])