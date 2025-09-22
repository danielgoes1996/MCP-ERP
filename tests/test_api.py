"""
Basic API tests for MCP Server
Tests core endpoints and functionality
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import status


class TestHealthEndpoints:
    """Test health and status endpoints"""

    def test_health_check(self, client: TestClient):
        """Test /health endpoint"""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_status(self, client: TestClient):
        """Test /api/status endpoint"""
        response = client.get("/api/status")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "version" in data
        assert "status" in data


class TestExpenseEndpoints:
    """Test expense-related endpoints"""

    def test_list_expenses(self, client: TestClient):
        """Test GET /expenses"""
        response = client.get("/expenses")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_create_expense(self, client: TestClient, sample_expense_data):
        """Test POST /expenses"""
        response = client.post("/expenses", json=sample_expense_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "expense_id" in data

    def test_create_expense_invalid_data(self, client: TestClient):
        """Test POST /expenses with invalid data"""
        invalid_data = {
            "description": "",  # Empty description
            "amount": -100,  # Negative amount
        }
        response = client.post("/expenses", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_predict_category(self, client: TestClient):
        """Test POST /expenses/predict-category"""
        response = client.post(
            "/expenses/predict-category",
            json={"description": "Uber ride to airport"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "predicted_category" in data
        assert "confidence" in data

    def test_check_duplicates(self, client: TestClient):
        """Test POST /expenses/check-duplicates"""
        response = client.post(
            "/expenses/check-duplicates",
            json={
                "description": "Lunch at Restaurant ABC",
                "amount": 250.00,
                "date": "2024-01-15"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "is_duplicate" in data
        assert "similar_expenses" in data


class TestInvoiceEndpoints:
    """Test invoice-related endpoints"""

    def test_parse_invoice(self, client: TestClient, sample_invoice_xml, temp_file):
        """Test POST /invoices/parse"""
        with open(temp_file, "wb") as f:
            f.write(sample_invoice_xml.encode())

        with open(temp_file, "rb") as f:
            response = client.post(
                "/invoices/parse",
                files={"file": ("invoice.xml", f, "application/xml")}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "invoice_data" in data


class TestAuthEndpoints:
    """Test authentication endpoints"""

    @pytest.mark.skipif(True, reason="Auth endpoint not implemented in main.py yet")
    def test_login(self, client: TestClient):
        """Test POST /auth/token"""
        response = client.post(
            "/auth/token",
            data={
                "username": "admin@mcp.com",
                "password": "admin123"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.skipif(True, reason="Auth endpoint not implemented in main.py yet")
    def test_login_invalid_credentials(self, client: TestClient):
        """Test login with invalid credentials"""
        response = client.post(
            "/auth/token",
            data={
                "username": "invalid@mcp.com",
                "password": "wrongpass"
            }
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMCPEndpoints:
    """Test MCP protocol endpoints"""

    def test_mcp_request(self, client: TestClient):
        """Test POST /mcp"""
        response = client.post(
            "/mcp",
            json={
                "method": "tools/list",
                "params": {}
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "result" in data

    def test_mcp_invalid_method(self, client: TestClient):
        """Test MCP with invalid method"""
        response = client.post(
            "/mcp",
            json={
                "method": "invalid/method",
                "params": {}
            }
        )
        # Should still return 200 but with error in result
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "error" in data["result"] or data["result"] is None


class TestVoiceEndpoints:
    """Test voice-related endpoints"""

    @pytest.mark.skipif(True, reason="Requires OpenAI API key")
    def test_voice_mcp(self, client: TestClient, mock_openai_response):
        """Test POST /voice_mcp"""
        response = client.post(
            "/voice_mcp",
            json={
                "audio": "base64_encoded_audio_here",
                "format": "webm"
            }
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]


class TestStaticPages:
    """Test static HTML pages"""

    def test_index_page(self, client: TestClient):
        """Test / endpoint"""
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK

    def test_onboarding_page(self, client: TestClient):
        """Test /onboarding endpoint"""
        response = client.get("/onboarding")
        assert response.status_code == status.HTTP_200_OK

    def test_voice_expenses_page(self, client: TestClient):
        """Test /voice-expenses endpoint"""
        response = client.get("/voice-expenses")
        assert response.status_code == status.HTTP_200_OK


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])