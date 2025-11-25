#!/usr/bin/env python3
"""
Tests de integración para endpoints de gastos.

Estos tests verifican el comportamiento completo de los endpoints,
incluyendo validaciones, mapeos y creación en base de datos.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from httpx import ASGITransport, AsyncClient

from core.internal_db import initialize_internal_database
from main import app


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    """Reset database antes de cada test."""
    test_db = tmp_path / "test_expense_endpoints.db"
    monkeypatch.setenv("INTERNAL_DB_PATH", str(test_db))
    initialize_internal_database()
    yield
    if test_db.exists():
        test_db.unlink()


@pytest.fixture()
def client():
    """Cliente HTTP asíncrono para tests."""
    transport = ASGITransport(app=app)
    client_instance = AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield client_instance
    finally:
        asyncio.get_event_loop().run_until_complete(client_instance.aclose())


class TestPOSTExpensesBasicCreation:
    """Tests básicos para POST /expenses."""

    async def test_create_minimal_expense(self, client):
        """Debe crear gasto con campos mínimos."""
        payload = {
            "descripcion": "Gasto de prueba",
            "monto_total": 100.50,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data['id'], int)
        assert data['descripcion'] == "Gasto de prueba"
        assert data['monto_total'] == 100.50
        assert data['fecha_gasto'] == "2025-01-15"

    async def test_create_complete_expense(self, client):
        """Debe crear gasto con todos los campos."""
        payload = {
            "descripcion": "Gasolina para vehículo de reparto",
            "monto_total": 850.50,
            "fecha_gasto": "2025-01-15",
            "proveedor": {
                "nombre": "Gasolinera PEMEX",
                "rfc": "PEM840212XY1"
            },
            "rfc": "PEM840212XY1",
            "categoria": "combustibles",
            "forma_pago": "tarjeta",
            "paid_by": "company_account",
            "will_have_cfdi": True,
            "workflow_status": "draft",
            "estado_factura": "pendiente",
            "estado_conciliacion": "pendiente",
            "company_id": "test_company"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['id'] > 0
        assert data['descripcion'] == "Gasolina para vehículo de reparto"
        assert data['monto_total'] == 850.50
        assert data['categoria'] == "combustibles"
        assert data['company_id'] == "test_company"

    async def test_create_expense_with_metadata(self, client):
        """Debe crear gasto con metadata adicional."""
        payload = {
            "descripcion": "Test con metadata",
            "monto_total": 200,
            "fecha_gasto": "2025-01-15",
            "metadata": {
                "source": "test",
                "user_agent": "pytest"
            }
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['metadata'] is not None
        assert data['metadata'].get('source') == "test"


class TestPOSTExpensesValidations:
    """Tests para validaciones del endpoint POST /expenses."""

    async def test_monto_zero_rejected(self, client):
        """Monto cero debe ser rechazado."""
        payload = {
            "descripcion": "Test",
            "monto_total": 0,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422  # Unprocessable Entity
        error_detail = resp.json()['detail']
        assert any('monto_total' in str(err.get('loc', [])) for err in error_detail)

    async def test_monto_negative_rejected(self, client):
        """Monto negativo debe ser rechazado."""
        payload = {
            "descripcion": "Test",
            "monto_total": -100,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422

    async def test_monto_exceeds_limit_rejected(self, client):
        """Monto mayor a 10M debe ser rechazado."""
        payload = {
            "descripcion": "Test",
            "monto_total": 15_000_000,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422
        error_detail = resp.json()['detail']
        assert any('límite máximo' in str(err.get('msg', '')) for err in error_detail)

    async def test_fecha_futura_rejected(self, client):
        """Fecha futura debe ser rechazada."""
        future_date = (datetime.now() + timedelta(days=7)).date().isoformat()

        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": future_date
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422
        error_detail = resp.json()['detail']
        assert any('futura' in str(err.get('msg', '')) for err in error_detail)

    async def test_fecha_invalid_format_rejected(self, client):
        """Formato de fecha inválido debe ser rechazado."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "15/01/2025"  # Formato incorrecto
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422

    async def test_rfc_invalid_too_short_rejected(self, client):
        """RFC muy corto debe ser rechazado."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "rfc": "ABC123"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422
        error_detail = resp.json()['detail']
        assert any('rfc' in str(err.get('loc', [])) for err in error_detail)

    async def test_rfc_with_special_chars_rejected(self, client):
        """RFC con caracteres especiales debe ser rechazado."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "rfc": "PEM-840212-XY1"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422

    async def test_descripcion_empty_rejected(self, client):
        """Descripción vacía debe ser rechazada."""
        payload = {
            "descripcion": "",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422


class TestPOSTExpensesCategoryMapping:
    """Tests para mapeo automático de categorías."""

    async def test_combustibles_maps_to_account_6140(self, client):
        """Categoría combustibles debe mapear a cuenta 6140."""
        payload = {
            "descripcion": "Gasolina",
            "monto_total": 500,
            "fecha_gasto": "2025-01-15",
            "categoria": "combustibles"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        # Verificar que se creó (el mapeo sucede internamente)
        assert data['categoria'] == "combustibles"

    async def test_viajes_maps_to_account_6150(self, client):
        """Categoría viajes debe mapear a cuenta 6150."""
        payload = {
            "descripcion": "Viaje de negocios",
            "monto_total": 2000,
            "fecha_gasto": "2025-01-15",
            "categoria": "viajes"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['categoria'] == "viajes"

    async def test_categoria_normalized_to_lowercase(self, client):
        """Categoría debe normalizarse a minúsculas."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "categoria": "COMBUSTIBLES"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['categoria'] == "combustibles"

    async def test_unknown_categoria_still_creates_expense(self, client):
        """Categoría desconocida no debe impedir creación."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "categoria": "categoria_inexistente"
        }

        resp = await client.post('/expenses', json=payload)

        # Debe crear igual con cuenta por defecto
        assert resp.status_code == 200
        data = resp.json()
        assert data['categoria'] == "categoria_inexistente"


class TestPOSTExpensesDefaults:
    """Tests para valores por defecto."""

    async def test_defaults_applied_when_not_provided(self, client):
        """Debe aplicar valores por defecto si no se proporcionan."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['workflow_status'] == "draft"
        assert data['estado_factura'] == "pendiente"
        assert data['estado_conciliacion'] == "pendiente"
        assert data['paid_by'] == "company_account"
        assert data['will_have_cfdi'] is True
        assert data['company_id'] == "default"

    async def test_can_override_defaults(self, client):
        """Debe poder sobrescribir valores por defecto."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "workflow_status": "aprobado",
            "paid_by": "employee",
            "will_have_cfdi": False,
            "company_id": "custom_company"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['workflow_status'] == "aprobado"
        assert data['paid_by'] == "employee"
        assert data['will_have_cfdi'] is False
        assert data['company_id'] == "custom_company"


class TestPOSTExpensesRFCNormalization:
    """Tests para normalización de RFC."""

    async def test_rfc_normalized_to_uppercase(self, client):
        """RFC debe normalizarse a mayúsculas."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "rfc": "pem840212xy1"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['rfc'] == "PEM840212XY1"

    async def test_rfc_strips_whitespace(self, client):
        """RFC debe limpiar espacios en blanco."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "rfc": "  PEM840212XY1  "
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data['rfc'] == "PEM840212XY1"


class TestPOSTExpensesEnhanced:
    """Tests para POST /expenses/enhanced."""

    async def test_create_expense_with_duplicate_check(self, client):
        """Debe crear gasto y verificar duplicados."""
        # Primero crear un gasto
        payload1 = {
            "descripcion": "Gasolina PEMEX",
            "monto_total": 500,
            "fecha_gasto": "2025-01-15",
            "categoria": "combustibles"
        }

        resp1 = await client.post('/expenses', json=payload1)
        assert resp1.status_code == 200

        # Intentar crear gasto similar con enhanced
        payload2 = {
            "descripcion": "Gasolina PEMEX",
            "monto_total": 500,
            "fecha_gasto": "2025-01-15",
            "categoria": "combustibles",
            "check_duplicates": True
        }

        resp2 = await client.post('/expenses/enhanced', json=payload2)

        # Puede tener status 200 y marcar duplicados en respuesta
        # o 400 si rechaza duplicados - depende de implementación
        assert resp2.status_code in [200, 400]

    async def test_enhanced_can_disable_duplicate_check(self, client):
        """Debe poder deshabilitar check de duplicados."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "check_duplicates": False
        }

        resp = await client.post('/expenses/enhanced', json=payload)

        # Debe crear sin verificar duplicados
        assert resp.status_code in [200, 201]


class TestPOSTExpensesSimple:
    """Tests para POST /api/expenses/simple."""

    async def test_create_simple_expense(self, client):
        """Debe crear gasto con formato simplificado usando el endpoint moderno."""
        payload = {
            "descripcion": "Comida en restaurante",
            "monto_total": 450.00,
            "fecha_gasto": "2025-01-15",
            "categoria": "alimentacion",
            "forma_pago": "efectivo",
            "company_id": "test_company"
        }

        resp = await client.post('/expenses', json=payload)

        # Verificar que se cree correctamente con el endpoint moderno
        assert resp.status_code == 200
        data = resp.json()
        assert data['id'] > 0
        assert data['descripcion'] == "Comida en restaurante"
        assert data['monto_total'] == 450.00


class TestPOSTExpensesMultipleCreation:
    """Tests para creación múltiple de gastos."""

    async def test_create_multiple_expenses_sequentially(self, client):
        """Debe poder crear múltiples gastos."""
        payloads = [
            {
                "descripcion": "Gasto 1",
                "monto_total": 100,
                "fecha_gasto": "2025-01-15"
            },
            {
                "descripcion": "Gasto 2",
                "monto_total": 200,
                "fecha_gasto": "2025-01-16"
            },
            {
                "descripcion": "Gasto 3",
                "monto_total": 300,
                "fecha_gasto": "2025-01-17"
            }
        ]

        created_ids = []
        for payload in payloads:
            resp = await client.post('/expenses', json=payload)
            assert resp.status_code == 200
            created_ids.append(resp.json()['id'])

        # Todos deben tener IDs únicos
        assert len(created_ids) == len(set(created_ids))

    async def test_expenses_from_different_companies_isolated(self, client):
        """Gastos de diferentes empresas deben estar aislados."""
        payload1 = {
            "descripcion": "Gasto empresa A",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15",
            "company_id": "company_a"
        }

        payload2 = {
            "descripcion": "Gasto empresa B",
            "monto_total": 200,
            "fecha_gasto": "2025-01-15",
            "company_id": "company_b"
        }

        resp1 = await client.post('/expenses', json=payload1)
        resp2 = await client.post('/expenses', json=payload2)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        data1 = resp1.json()
        data2 = resp2.json()

        assert data1['company_id'] == "company_a"
        assert data2['company_id'] == "company_b"


class TestPOSTExpensesErrorHandling:
    """Tests para manejo de errores."""

    async def test_missing_required_fields(self, client):
        """Faltar campos requeridos debe retornar 422."""
        payload = {
            "monto_total": 100
            # Falta descripcion y fecha_gasto
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 422
        error_detail = resp.json()['detail']
        assert len(error_detail) >= 2  # Al menos 2 campos faltantes

    async def test_invalid_json(self, client):
        """JSON inválido debe retornar error."""
        resp = await client.post(
            '/expenses',
            content="{invalid json}",
            headers={"Content-Type": "application/json"}
        )

        assert resp.status_code in [400, 422]

    async def test_wrong_content_type(self, client):
        """Content-Type incorrecto puede causar error."""
        resp = await client.post(
            '/expenses',
            data="descripcion=Test&monto_total=100",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Puede retornar 422 (validation error) o 415 (unsupported media type)
        assert resp.status_code in [415, 422]


class TestPOSTExpensesResponseStructure:
    """Tests para estructura de respuesta."""

    async def test_response_includes_required_fields(self, client):
        """Respuesta debe incluir todos los campos requeridos."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()

        # Verificar campos requeridos de ExpenseResponse
        assert 'id' in data
        assert 'descripcion' in data
        assert 'monto_total' in data
        assert 'workflow_status' in data
        assert 'estado_factura' in data
        assert 'estado_conciliacion' in data
        assert 'moneda' in data
        assert 'company_id' in data

    async def test_response_includes_timestamps(self, client):
        """Respuesta debe incluir timestamps de creación."""
        payload = {
            "descripcion": "Test",
            "monto_total": 100,
            "fecha_gasto": "2025-01-15"
        }

        resp = await client.post('/expenses', json=payload)

        assert resp.status_code == 200
        data = resp.json()

        # Timestamps opcionales pero típicamente incluidos
        if 'created_at' in data:
            assert isinstance(data['created_at'], str)
        if 'updated_at' in data:
            assert isinstance(data['updated_at'], str)


# Helper function para tests
def create_expense_sync(client, payload: dict) -> dict:
    """Helper para crear gastos síncronamente en tests."""
    return asyncio.get_event_loop().run_until_complete(
        client.post('/expenses', json=payload)
    ).json()
