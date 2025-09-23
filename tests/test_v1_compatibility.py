"""
Test Suite: v1 API Compatibility
Garantiza que NINGÚN endpoint v1 se rompe con la integración v2.
"""

import pytest
import requests
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import original app (pre-integration)
from main import app as original_app

# Import enhanced app (post-integration)
from main_enhanced import app as enhanced_app

class TestV1BackwardCompatibility:
    """Test que v1 API mantiene exacta compatibilidad."""

    def setup_method(self):
        self.original_client = TestClient(original_app)
        self.enhanced_client = TestClient(enhanced_app)

    def test_root_endpoint_unchanged(self):
        """Root endpoint debe funcionar igual."""
        original = self.original_client.get("/")
        enhanced = self.enhanced_client.get("/")

        assert original.status_code == enhanced.status_code
        # Redirect to same location
        assert original.headers.get("location") == enhanced.headers.get("location")

    def test_health_endpoint_compatible(self):
        """Health endpoint debe mantener campos básicos."""
        original = self.original_client.get("/health").json()
        enhanced = self.enhanced_client.get("/health").json()

        # Enhanced puede tener más campos, pero no menos
        assert set(original.keys()).issubset(set(enhanced.keys()))
        assert enhanced["status"] == original["status"]
        assert enhanced["version"] != original["version"]  # Version bump OK

    def test_mcp_endpoint_unchanged(self):
        """MCP endpoint debe mantener mismo contrato."""
        test_data = {"request": "test", "params": {}}

        # Mock MCP handler to avoid actual processing
        with patch('main.handle_mcp_request') as mock_handler:
            mock_handler.return_value = {"result": "test"}

            original = self.original_client.post("/mcp", json=test_data)
            enhanced = self.enhanced_client.post("/mcp", json=test_data)

            assert original.status_code == enhanced.status_code
            assert original.json() == enhanced.json()

    @pytest.mark.skipif(not hasattr(original_app, 'voice_endpoint'), reason="Voice not enabled")
    def test_voice_endpoint_unchanged(self):
        """Voice endpoint debe mantener mismo contrato."""
        # Mock voice file
        test_audio = b"fake_audio_data"

        with patch('main.process_voice_request') as mock_voice:
            mock_voice.return_value = {"success": True, "text": "test"}

            files = {"audio": ("test.wav", test_audio, "audio/wav")}
            data = {"user_id": "test", "language": "es-MX"}

            original = self.original_client.post("/voice", files=files, data=data)
            enhanced = self.enhanced_client.post("/voice", files=files, data=data)

            assert original.status_code == enhanced.status_code
            assert original.json() == enhanced.json()

class TestInvoicingV1Compatibility:
    """Test específicos del módulo de facturación v1."""

    def setup_method(self):
        self.client = TestClient(enhanced_app)

    def test_create_ticket_schema_unchanged(self):
        """POST /invoicing/tickets debe mantener mismo schema de response."""
        # Mock database operations
        with patch('modules.invoicing_agent.models.create_ticket') as mock_create:
            mock_create.return_value = 123

            # Test con archivo
            files = {"file": ("test.jpg", b"fake_image", "image/jpeg")}
            data = {"company_id": "default"}

            response = self.client.post("/invoicing/tickets", files=files, data=data)

            assert response.status_code == 200
            result = response.json()

            # Campos obligatorios v1
            required_fields = {"ticket_id", "status", "message"}
            assert required_fields.issubset(set(result.keys()))

    def test_get_ticket_schema_unchanged(self):
        """GET /invoicing/tickets/{id} debe mantener campos básicos."""
        with patch('modules.invoicing_agent.models.get_ticket') as mock_get:
            mock_get.return_value = {
                "id": 123,
                "user_id": 1,
                "raw_data": "test",
                "tipo": "imagen",
                "estado": "pendiente",
                "created_at": "2024-09-22T00:00:00",
                "updated_at": "2024-09-22T00:00:00",
                "company_id": "default"
            }

            response = self.client.get("/invoicing/tickets/123")

            assert response.status_code == 200
            ticket = response.json()

            # Campos v1 obligatorios
            v1_fields = {"id", "estado", "created_at", "updated_at", "tipo"}
            assert v1_fields.issubset(set(ticket.keys()))

            # Tipos válidos v1
            assert ticket["estado"] in ["pendiente", "procesando", "completado", "fallido"]
            assert ticket["tipo"] in ["imagen", "pdf", "texto", "voz"]

    def test_merchants_endpoints_unchanged(self):
        """Endpoints de merchants deben mantener compatibilidad."""
        # Test GET merchants
        with patch('modules.invoicing_agent.models.list_merchants') as mock_list:
            mock_list.return_value = [
                {"id": 1, "nombre": "Test", "metodo_facturacion": "portal", "is_active": True}
            ]

            response = self.client.get("/invoicing/merchants")
            assert response.status_code == 200

            merchants = response.json()
            assert isinstance(merchants, list)
            if merchants:
                merchant = merchants[0]
                required_fields = {"id", "nombre", "metodo_facturacion", "is_active"}
                assert required_fields.issubset(set(merchant.keys()))

    def test_jobs_endpoint_unchanged(self):
        """GET /invoicing/jobs debe mantener schema básico."""
        with patch('modules.invoicing_agent.models.list_pending_jobs') as mock_jobs:
            mock_jobs.return_value = [
                {
                    "id": 1,
                    "ticket_id": 123,
                    "estado": "pendiente",
                    "created_at": "2024-09-22T00:00:00"
                }
            ]

            response = self.client.get("/invoicing/jobs")
            assert response.status_code == 200

            jobs = response.json()
            assert isinstance(jobs, list)
            if jobs:
                job = jobs[0]
                v1_fields = {"id", "ticket_id", "estado", "created_at"}
                assert v1_fields.issubset(set(job.keys()))

class TestStaticFilesCompatibility:
    """Test que archivos estáticos siguen funcionando."""

    def setup_method(self):
        self.client = TestClient(enhanced_app)

    def test_automation_viewer_accessible(self):
        """automation-viewer.html debe seguir funcionando."""
        response = self.client.get("/static/automation-viewer.html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_advanced_dashboard_accessible(self):
        """advanced-ticket-dashboard.html debe seguir funcionando."""
        response = self.client.get("/static/advanced-ticket-dashboard.html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_js_files_accessible(self):
        """Archivos JS deben seguir siendo servidos."""
        response = self.client.get("/static/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "")

class TestErrorHandlingCompatibility:
    """Test que manejo de errores es compatible."""

    def setup_method(self):
        self.client = TestClient(enhanced_app)

    def test_404_behavior_unchanged(self):
        """404s deben comportarse igual."""
        response = self.client.get("/nonexistent-endpoint")
        assert response.status_code == 404

    def test_500_error_format_unchanged(self):
        """500 errors deben tener mismo formato."""
        # Mock para forzar error interno
        with patch('modules.invoicing_agent.models.get_ticket') as mock_get:
            mock_get.side_effect = Exception("Test error")

            response = self.client.get("/invoicing/tickets/999")
            assert response.status_code == 500

            error = response.json()
            assert "detail" in error  # FastAPI standard error format

    def test_validation_errors_unchanged(self):
        """Errores de validación deben mantener formato."""
        # Enviar datos inválidos
        response = self.client.post("/invoicing/tickets", data={})  # Sin archivo ni texto

        assert response.status_code == 400
        error = response.json()
        assert "detail" in error

class TestPerformanceRegression:
    """Test que performance no se degrada significativamente."""

    def setup_method(self):
        self.client = TestClient(enhanced_app)

    def test_basic_endpoints_response_time(self):
        """Endpoints básicos deben responder rápido."""
        import time

        # Test health endpoint
        start = time.time()
        response = self.client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0  # Should respond within 1 second

    def test_static_file_serving_speed(self):
        """Archivos estáticos deben servirse rápido."""
        import time

        start = time.time()
        response = self.client.get("/static/app.js")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.5  # Static files should be very fast

# Integration test fixture
@pytest.fixture
def test_database():
    """Fixture para database de pruebas."""
    import tempfile
    import sqlite3
    import os

    # Create temporary database
    temp_db = tempfile.mktemp(suffix='.db')

    # Initialize with basic schema
    with sqlite3.connect(temp_db) as conn:
        conn.execute("""
            CREATE TABLE tickets (
                id INTEGER PRIMARY KEY,
                raw_data TEXT,
                tipo TEXT,
                estado TEXT,
                created_at TEXT,
                updated_at TEXT,
                company_id TEXT DEFAULT 'default'
            )
        """)

        # Insert test data
        conn.execute("""
            INSERT INTO tickets (raw_data, tipo, estado, created_at, updated_at)
            VALUES ('test data', 'texto', 'pendiente', '2024-09-22T00:00:00', '2024-09-22T00:00:00')
        """)
        conn.commit()

    yield temp_db

    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)

def test_with_real_database(test_database):
    """Test integración con database real."""
    # Patch database path to use test database
    with patch('core.internal_db._get_db_path') as mock_path:
        mock_path.return_value = test_database

        client = TestClient(enhanced_app)
        response = client.get("/invoicing/tickets/1")

        assert response.status_code == 200
        ticket = response.json()
        assert ticket["id"] == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])