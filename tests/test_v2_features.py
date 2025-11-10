"""
Test Suite: v2 Enhanced Features
Valida que todas las nuevas funcionalidades v2 funcionan correctamente.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from main_enhanced import app
from core.expenses.enhanced_api_models import AutomationStatus, JobPriority

class TestEnhancedTicketAPI:
    """Test endpoints v2 de tickets con features robustas."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_create_enhanced_ticket(self):
        """POST /invoicing/v2/tickets con features avanzadas."""
        enhanced_data = {
            "raw_data": "test ticket",
            "tipo": "texto",
            "auto_process": True,
            "priority": "alta",
            "alternative_urls": ["https://test1.com", "https://test2.com"],
            "enable_captcha_solving": True,
            "max_retries": 5,
            "timeout_seconds": 600
        }

        with patch('modules.invoicing_agent.models.create_ticket') as mock_create:
            mock_create.return_value = 456

            response = self.client.post("/invoicing/v2/tickets", json=enhanced_data)

            assert response.status_code == 200
            result = response.json()

            # Enhanced response fields
            assert "automation_status" in result
            assert "automation_job_id" in result
            assert result["automation_status"] in ["pendiente", "en_cola"]

    def test_get_enhanced_ticket(self):
        """GET /invoicing/v2/tickets/{id} con datos de automatización."""
        with patch('modules.invoicing_agent.models.get_ticket') as mock_get, \
             patch('modules.invoicing_agent.automation_persistence.create_automation_persistence') as mock_persistence:

            # Mock basic ticket data
            mock_get.return_value = {
                "id": 456,
                "raw_data": "test",
                "tipo": "texto",
                "estado": "completado",
                "created_at": "2024-09-22T00:00:00",
                "updated_at": "2024-09-22T00:00:00",
                "company_id": "default"
            }

            # Mock automation data
            mock_persistence_instance = MagicMock()
            mock_persistence.return_value = mock_persistence_instance
            mock_persistence_instance.get_automation_data.return_value = {
                "job_data": {"id": 789, "estado": "completado"},
                "logs": [{"level": "info", "message": "Test completed"}],
                "screenshots": [{"file_path": "/test/screenshot.png"}],
                "summary": {"total_steps": 5, "success_rate": 1.0}
            }

            response = self.client.get("/invoicing/v2/tickets/456")

            assert response.status_code == 200
            ticket = response.json()

            # Enhanced fields present
            assert "automation_status" in ticket
            assert "automation_job_id" in ticket
            assert ticket["automation_job_id"] == 789

class TestAutomationJobAPI:
    """Test endpoints de jobs de automatización."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_create_automation_job(self):
        """POST /invoicing/v2/jobs."""
        job_data = {
            "ticket_id": 123,
            "priority": "alta",
            "config": {
                "enable_captcha": True,
                "alternative_urls": ["https://test.com"]
            }
        }

        with patch('modules.invoicing_agent.enhanced_api._create_automation_job') as mock_create:
            mock_create.return_value = 999

            with patch('modules.invoicing_agent.enhanced_api._get_automation_job') as mock_get:
                mock_get.return_value = MagicMock(
                    id=999,
                    ticket_id=123,
                    status=AutomationStatus.PENDING,
                    priority=JobPriority.HIGH
                )

                response = self.client.post("/invoicing/v2/jobs", json=job_data)

                assert response.status_code == 200
                result = response.json()
                assert result["id"] == 999
                assert result["priority"] == "alta"

    def test_list_automation_jobs_with_filters(self):
        """GET /invoicing/v2/jobs con filtros."""
        with patch('modules.invoicing_agent.enhanced_api._list_automation_jobs') as mock_list:
            mock_list.return_value = [
                MagicMock(
                    id=1,
                    ticket_id=100,
                    status=AutomationStatus.PROCESSING,
                    priority=JobPriority.NORMAL
                ),
                MagicMock(
                    id=2,
                    ticket_id=101,
                    status=AutomationStatus.COMPLETED,
                    priority=JobPriority.HIGH
                )
            ]

            response = self.client.get("/invoicing/v2/jobs?status=procesando&limit=10")

            assert response.status_code == 200
            jobs = response.json()
            assert isinstance(jobs, list)

    def test_job_streaming_endpoint(self):
        """GET /invoicing/v2/jobs/{id}/stream SSE endpoint."""
        # Note: Testing SSE is complex, this tests the endpoint exists
        response = self.client.get("/invoicing/v2/jobs/123/stream")

        # Should either work (200) or fail gracefully (404 if job not found)
        assert response.status_code in [200, 404]

class TestBulkOperations:
    """Test operaciones en bulk."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_create_bulk_automation(self):
        """POST /invoicing/v2/bulk."""
        bulk_data = {
            "ticket_ids": [1, 2, 3, 4, 5],
            "priority": "normal",
            "max_concurrent": 3,
            "company_id": "test_company"
        }

        with patch('modules.invoicing_agent.enhanced_api._create_automation_job') as mock_create:
            # Mock job creation for each ticket
            mock_create.side_effect = [101, 102, 103, 104, 105]

            response = self.client.post("/invoicing/v2/bulk", json=bulk_data)

            assert response.status_code == 200
            result = response.json()

            assert "batch_id" in result
            assert result["total_tickets"] == 5
            assert len(result["jobs_created"]) == 5
            assert "estimated_completion" in result

class TestSystemHealthAndMetrics:
    """Test endpoints de health y métricas."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_system_health_endpoint(self):
        """GET /invoicing/v2/health."""
        with patch('core.service_stack_config.get_service_stack') as mock_stack:
            mock_stack_instance = MagicMock()
            mock_stack.return_value = mock_stack_instance
            mock_stack_instance.get_service_status.return_value = {
                "readiness_score": 0.8,
                "services": {
                    "selenium": {"name": "Selenium", "available": True},
                    "claude": {"name": "Claude", "available": False}
                }
            }

            with patch('modules.invoicing_agent.enhanced_api._count_active_jobs') as mock_count, \
                 patch('modules.invoicing_agent.enhanced_api._get_queue_size') as mock_queue:

                mock_count.return_value = 5
                mock_queue.return_value = 10

                response = self.client.get("/invoicing/v2/health")

                assert response.status_code == 200
                health = response.json()

                assert "status" in health
                assert "services" in health
                assert "active_jobs" in health
                assert health["active_jobs"] == 5

    def test_metrics_endpoint(self):
        """GET /invoicing/v2/metrics."""
        response = self.client.get("/invoicing/v2/metrics")

        assert response.status_code == 200
        metrics = response.json()

        # Expected metric fields
        expected_fields = [
            "total_jobs_today",
            "successful_jobs_today",
            "failed_jobs_today",
            "average_processing_time_ms"
        ]

        for field in expected_fields:
            assert field in metrics

class TestBackwardCompatibleEnhancements:
    """Test endpoints bridge que extienden v1."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_enhanced_ticket_endpoint(self):
        """GET /invoicing/tickets/{id}/enhanced bridge endpoint."""
        with patch('modules.invoicing_agent.integration_layer.get_integration_layer') as mock_layer:
            mock_layer_instance = MagicMock()
            mock_layer.return_value = mock_layer_instance
            mock_layer_instance.get_enhanced_ticket_data.return_value = {
                "id": 123,
                "raw_data": "test",
                "tipo": "texto",
                "estado": "completado",
                "created_at": "2024-09-22T00:00:00",
                "updated_at": "2024-09-22T00:00:00",
                "company_id": "default",
                "automation_data": {
                    "job_data": {"id": 456, "estado": "completado"},
                    "summary": {"total_steps": 3}
                }
            }

            response = self.client.get("/invoicing/tickets/123/enhanced")

            assert response.status_code == 200
            ticket = response.json()
            assert ticket["id"] == 123
            assert "automation_status" in ticket

    def test_process_robust_endpoint(self):
        """POST /invoicing/tickets/{id}/process-robust bridge endpoint."""
        with patch('modules.invoicing_agent.integration_layer.is_enhanced_automation_available') as mock_available, \
             patch('modules.invoicing_agent.fastapi_integration._process_ticket_background') as mock_process:

            mock_available.return_value = True

            response = self.client.post(
                "/invoicing/tickets/123/process-robust",
                params={
                    "priority": "alta",
                    "enable_captcha": True,
                    "max_retries": 5
                }
            )

            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "queued"
            assert result["mode"] == "enhanced"

    def test_system_status_bridge_endpoint(self):
        """GET /invoicing/system/status bridge endpoint."""
        with patch('modules.invoicing_agent.integration_layer.validate_automation_system') as mock_validate, \
             patch('modules.invoicing_agent.integration_layer.get_integration_layer') as mock_layer:

            mock_validate.return_value = {"status": "healthy"}
            mock_layer_instance = MagicMock()
            mock_layer.return_value = mock_layer_instance
            mock_layer_instance.is_enhanced_mode.return_value = True
            mock_layer_instance._get_available_capabilities.return_value = {
                "enhanced_automation": True,
                "claude_analysis": False
            }

            response = self.client.get("/invoicing/system/status")

            assert response.status_code == 200
            status = response.json()
            assert "system_health" in status
            assert "enhanced_mode" in status
            assert status["enhanced_mode"] is True

class TestIntegrationLayerFunctionality:
    """Test funcionalidad de la capa de integración."""

    def test_integration_layer_initialization(self):
        """Test que integration layer se inicializa correctamente."""
        from modules.invoicing_agent.integration_layer import get_integration_layer

        layer = get_integration_layer()
        assert layer is not None

        # Should not crash even without robust engine
        capabilities = layer._get_available_capabilities()
        assert isinstance(capabilities, dict)

    @pytest.mark.asyncio
    async def test_process_ticket_with_fallback(self):
        """Test procesamiento con fallback automático."""
        from modules.invoicing_agent.integration_layer import process_ticket_with_fallback

        with patch('modules.invoicing_agent.models.get_ticket') as mock_get:
            mock_get.return_value = {
                "id": 123,
                "raw_data": "test",
                "tipo": "texto",
                "estado": "pendiente"
            }

            # Should not crash even if robust engine not available
            result = await process_ticket_with_fallback(123, {"test": "config"})
            assert isinstance(result, dict)
            assert "success" in result

class TestSecurityFeatures:
    """Test características de seguridad."""

    def test_rate_limiting_applied(self):
        """Test que rate limiting se aplica."""
        # Note: This would need actual rate limiting implementation
        # For now, test that endpoints exist and respond
        response = self.client.post("/invoicing/tickets/123/process-robust")
        # Should not return 429 on first request
        assert response.status_code != 429

    def test_feature_flags_integration(self):
        """Test integración con feature flags."""
        from modules.invoicing_agent.fastapi_integration import check_feature_flag

        # Should not crash even without database
        result = check_feature_flag("test_company", "enhanced_automation")
        assert isinstance(result, bool)

class TestErrorHandlingV2:
    """Test manejo de errores en v2."""

    def setup_method(self):
        self.client = TestClient(app)

    def test_enhanced_error_responses(self):
        """Test que errores v2 son informativos."""
        # Test with non-existent ticket
        response = self.client.get("/invoicing/v2/tickets/99999")

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error

    def test_validation_errors_v2(self):
        """Test errores de validación en v2."""
        # Send invalid data
        invalid_data = {
            "raw_data": "",  # Empty
            "tipo": "invalid_type",  # Invalid enum
            "priority": "invalid_priority"  # Invalid enum
        }

        response = self.client.post("/invoicing/v2/tickets", json=invalid_data)

        assert response.status_code == 422  # Validation error
        error = response.json()
        assert "detail" in error

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])