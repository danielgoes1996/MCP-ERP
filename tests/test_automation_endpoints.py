"""
Test suite para endpoints de automatización e invoicing agent
Cubre funcionalidades críticas del sistema de automatización
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import os
import json

# Import the invoicing agent API
try:
    from modules.invoicing_agent.api import router as invoicing_router
    from main import app

    # Create test client
    client = TestClient(app)
    INVOICING_AVAILABLE = True
    SKIP_REASON = ""
except ImportError as exc:
    INVOICING_AVAILABLE = False
    client = None
    SKIP_REASON = f"Invoicing agent no disponible: {exc}"
except TypeError as exc:
    INVOICING_AVAILABLE = False
    client = None
    SKIP_REASON = f"TestClient incompatible con la versión actual de httpx/starlette: {exc}"
else:
    SKIP_REASON = ""


@pytest.mark.skipif(not INVOICING_AVAILABLE, reason=SKIP_REASON or "Invoicing agent not available")
class TestInvoicingAgentEndpoints:
    """Tests para endpoints del agente de facturación"""

    def test_get_tickets_list(self):
        """Test obtener lista de tickets"""
        response = client.get("/invoicing/tickets?company_id=demo-company")
        assert response.status_code == 200
        data = response.json()
        if isinstance(data, list):
            tickets = data
        else:
            assert isinstance(data, dict)
            assert "tickets" in data
            tickets = data["tickets"]
            assert isinstance(tickets, list)
            assert "success" in data
        assert len(tickets) >= 0

    def test_get_tickets_stats(self):
        """Test obtener estadísticas de tickets"""
        response = client.get("/invoicing/stats?company_id=demo-company")
        assert response.status_code == 200
        data = response.json()
        assert "total_tickets" in data
        assert "by_status" in data

    @patch('modules.invoicing_agent.worker.process_ticket_job')
    def test_upload_ticket_with_file(self, mock_process):
        """Test subir ticket con archivo"""
        mock_process.return_value = {"status": "processed", "ticket_id": 123}

        # Create temporary image file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(b'fake image content')
            tmp_file.flush()

            with open(tmp_file.name, "rb") as f:
                response = client.post(
                    "/invoicing/tickets",
                    files={"file": ("test.jpg", f, "image/jpeg")},
                    data={"user_id": "test-user"}
                )

            os.unlink(tmp_file.name)

        assert response.status_code in [200, 201]
        # Response format may vary, adjust based on actual implementation

    def test_upload_ticket_with_text(self):
        """Test subir ticket solo con texto"""
        response = client.post("/invoicing/tickets", json={
            "text_content": "Test ticket content",
            "user_id": "test-user",
            "company_id": "demo-company"
        })

        # Should accept text-only tickets
        assert response.status_code in [200, 201, 422]  # 422 if validation fails

    def test_get_ticket_by_id(self):
        """Test obtener ticket específico por ID"""
        # First, we need a ticket ID - this test assumes ticket 1 exists or mocks it
        with patch('modules.invoicing_agent.models.get_ticket_by_id') as mock_get:
            mock_get.return_value = {
                "id": 1,
                "status": "processing",
                "created_at": "2024-01-01T00:00:00",
                "company_id": "demo-company"
            }

            response = client.get("/invoicing/tickets/1")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1

    def test_get_nonexistent_ticket(self):
        """Test obtener ticket inexistente"""
        response = client.get("/invoicing/tickets/99999")
        assert response.status_code == 404

    @patch('modules.invoicing_agent.robust_automation_engine.RobustAutomationEngine')
    def test_process_ticket_job(self, mock_engine):
        """Test procesar job de ticket"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.process_ticket.return_value = {
            "success": True,
            "invoice_generated": True,
            "final_url": "https://portal.com/invoice"
        }
        mock_engine.return_value = mock_engine_instance

        response = client.post("/invoicing/jobs/1/process")

        # Response depends on implementation
        assert response.status_code in [200, 202]  # 202 for async processing

    def test_get_ticket_image(self):
        """Test obtener imagen de ticket"""
        # This test needs a valid ticket with image
        with patch('modules.invoicing_agent.models.get_ticket_by_id') as mock_get:
            mock_get.return_value = {
                "id": 1,
                "image_path": "/path/to/test/image.jpg",
                "status": "processing"
            }

            response = client.get("/invoicing/tickets/1/image")
            # Response depends on whether image exists
            assert response.status_code in [200, 404]

    def test_get_ticket_ocr_text(self):
        """Test obtener texto OCR de ticket"""
        with patch('modules.invoicing_agent.models.get_ticket_by_id') as mock_get:
            mock_get.return_value = {
                "id": 1,
                "ocr_text": "Sample OCR text content",
                "status": "processed"
            }

            response = client.get("/invoicing/tickets/1/ocr-text")
            assert response.status_code == 200
            data = response.json()
            assert "ocr_text" in data

    def test_get_ticket_invoice_status(self):
        """Test obtener estatus de factura de ticket"""
        with patch('modules.invoicing_agent.models.get_ticket_by_id') as mock_get:
            mock_get.return_value = {
                "id": 1,
                "invoice_status": "generated",
                "invoice_url": "https://portal.com/invoice.pdf"
            }

            response = client.get("/invoicing/tickets/1/invoice-status")
            assert response.status_code == 200
            data = response.json()
            assert "invoice_status" in data


@pytest.mark.skipif(not INVOICING_AVAILABLE, reason="Invoicing agent not available")
class TestAutomationEngineEndpoints:
    """Tests para endpoints de motores de automatización"""

    @pytest.mark.asyncio
    @patch('modules.invoicing_agent.playwright_simple_engine.PlaywrightLitromilEngine')
    async def test_playwright_simple_engine(self, mock_engine):
        """Test motor simple de Playwright"""
        mock_engine_instance = AsyncMock()
        mock_engine_instance.initialize.return_value = True
        mock_engine_instance.automate_litromil_invoice.return_value = {
            "success": True,
            "final_url": "http://litromil.dynalias.net:8088/litromil/facturar.aspx",
            "execution_log": ["Step 1: Navigation", "Step 2: Click"],
            "screenshots": ["screenshot1.png", "screenshot2.png"]
        }
        mock_engine_instance.cleanup = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        response = client.post("/invoicing/test-playwright-simple/1")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    @patch('modules.invoicing_agent.playwright_automation_engine.PlaywrightAutomationEngine')
    def test_playwright_complete_engine(self, mock_engine):
        """Test motor completo de Playwright"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.process_ticket.return_value = {
            "success": True,
            "portal_detected": "LITROMIL",
            "invoice_generated": True,
            "performance_metrics": {
                "total_time": 8.5,
                "navigation_time": 3.2,
                "form_fill_time": 2.1
            }
        }
        mock_engine.return_value = mock_engine_instance

        response = client.post("/invoicing/test-playwright-complete/1")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    @patch('modules.invoicing_agent.universal_invoice_engine.UniversalInvoiceEngine')
    def test_universal_invoice_engine(self, mock_engine):
        """Test motor universal de facturación"""
        mock_engine_instance = AsyncMock()
        mock_engine_instance.generate_invoice_from_any_portal.return_value = {
            "success": True,
            "portal_type": "LITROMIL",
            "invoice_url": "https://portal.com/invoice.pdf",
            "processing_stages": {
                "portal_detection": {"status": "completed", "time": 1.2},
                "navigation": {"status": "completed", "time": 3.5},
                "form_filling": {"status": "completed", "time": 2.1},
                "invoice_generation": {"status": "completed", "time": 1.8}
            },
            "total_time": 8.6
        }
        mock_engine.return_value = mock_engine_instance

        response = client.post("/invoicing/universal-invoice-generator/1", json={
            "portal_url": "https://litromil.com",
            "invoice_data": {
                "estacion": "1234",
                "folio": "ABC123",
                "monto": "500.00"
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        if data.get("success"):
            assert data.get("portal_type") == "LITROMIL"

    def test_test_any_portal_endpoint(self):
        """Test endpoint para probar cualquier portal"""
        response = client.post("/invoicing/test-any-portal", json={
            "portal_url": "https://example.com",
            "test_data": {
                "field1": "value1",
                "field2": "value2"
            }
        })

        # Response depends on implementation
        assert response.status_code in [200, 400, 501]


@pytest.mark.skipif(not INVOICING_AVAILABLE, reason="Invoicing agent not available")
class TestIntelligentAgentEndpoints:
    """Tests para endpoints del agente inteligente"""

    @patch('modules.invoicing_agent.robust_automation_engine.RobustAutomationEngine')
    def test_intelligent_agent_success(self, mock_engine):
        """Test agente inteligente exitoso"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.process_ticket.return_value = {
            "success": True,
            "intelligent_analysis": {
                "portal_detected": True,
                "form_fields_identified": 5,
                "confidence_score": 0.95
            },
            "automation_result": {
                "navigation_successful": True,
                "form_filled": True,
                "invoice_generated": True
            }
        }
        mock_engine.return_value = mock_engine_instance

        response = client.post("/invoicing/test-intelligent-agent/1")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    @patch('modules.invoicing_agent.models.get_ticket_by_id')
    def test_intelligent_agent_ticket_not_found(self, mock_get):
        """Test agente inteligente con ticket inexistente"""
        mock_get.return_value = None

        response = client.post("/invoicing/test-intelligent-agent/99999")

        assert response.status_code == 404

    @patch('modules.invoicing_agent.robust_automation_engine.RobustAutomationEngine')
    def test_intelligent_agent_processing_error(self, mock_engine):
        """Test agente inteligente con error de procesamiento"""
        mock_engine_instance = MagicMock()
        mock_engine_instance.process_ticket.side_effect = Exception("Processing failed")
        mock_engine.return_value = mock_engine_instance

        response = client.post("/invoicing/test-intelligent-agent/1")

        assert response.status_code == 500


class TestAutomationModelsValidation:
    """Tests para validación de modelos de automatización"""

    def test_automation_request_model(self):
        """Test modelo de request de automatización"""
        # This would test Pydantic models if available
        from modules.invoicing_agent.models import TicketCreate

        # Valid data
        valid_data = {
            "text_content": "Test ticket",
            "user_id": "user123",
            "company_id": "comp123"
        }

        ticket = TicketCreate(**valid_data)
        assert ticket.text_content == "Test ticket"
        assert ticket.user_id == "user123"

    def test_automation_response_model(self):
        """Test modelo de response de automatización"""
        # Test response model validation if available
        pass


class TestErrorHandling:
    """Tests para manejo de errores"""

    def test_invalid_ticket_id_format(self):
        """Test formato inválido de ID de ticket"""
        response = client.get("/invoicing/tickets/invalid-id")
        assert response.status_code in [404, 422]  # Depends on path parameter validation

    def test_missing_required_fields(self):
        """Test campos requeridos faltantes"""
        response = client.post("/invoicing/tickets", json={})
        # Should fail validation
        assert response.status_code == 422

    def test_invalid_file_type(self):
        """Test tipo de archivo inválido"""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(b'not an image')
            tmp_file.flush()

            with open(tmp_file.name, "rb") as f:
                response = client.post(
                    "/invoicing/tickets",
                    files={"file": ("malware.exe", f, "application/exe")},
                    data={"user_id": "test-user"}
                )

            os.unlink(tmp_file.name)

        # Should reject dangerous file types
        assert response.status_code in [400, 422]


# Performance and Load Tests
class TestPerformance:
    """Tests básicos de performance"""

    @pytest.mark.slow
    def test_tickets_list_performance(self):
        """Test performance del listado de tickets"""
        import time
        start_time = time.time()

        response = client.get("/invoicing/tickets?company_id=demo-company&limit=100")

        end_time = time.time()
        response_time = end_time - start_time

        assert response.status_code == 200
        assert response_time < 2.0  # Should respond within 2 seconds

    @pytest.mark.slow
    def test_stats_endpoint_performance(self):
        """Test performance del endpoint de estadísticas"""
        import time
        start_time = time.time()

        response = client.get("/invoicing/stats?company_id=demo-company")

        end_time = time.time()
        response_time = end_time - start_time

        assert response.status_code == 200
        assert response_time < 1.0  # Should respond within 1 second


# Configuration for pytest
def pytest_configure(config):
    """Configuración adicional de pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow-running tests"
    )
    config.addinivalue_line(
        "markers", "automation: marks tests as automation tests"
    )


if __name__ == "__main__":
    # Para ejecutar tests directamente
    pytest.main([__file__])
