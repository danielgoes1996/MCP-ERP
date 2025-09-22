"""Tests for bank reconciliation heuristics."""

import asyncio
from typing import Dict

import pytest
from httpx import ASGITransport, AsyncClient

from core.internal_db import initialize_internal_database, record_bank_movement
from main import app


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_internal.db"
    monkeypatch.setenv("INTERNAL_DB_PATH", str(test_db))
    initialize_internal_database()
    yield
    if test_db.exists():
        test_db.unlink()


@pytest.fixture()
def client():
    transport = ASGITransport(app=app)
    client_instance = AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield client_instance
    finally:
        asyncio.get_event_loop().run_until_complete(client_instance.aclose())


def _create_expense(client: AsyncClient, payload: Dict) -> Dict:
    resp = asyncio.get_event_loop().run_until_complete(client.post('/expenses', json=payload))
    assert resp.status_code == 200
    return resp.json()


def test_split_payment_suggestion_includes_combination(client):
    expense_payload = {
        "descripcion": "Servicio consultoría",
        "monto_total": 375.0,
        "fecha_gasto": "2025-01-07",
        "categoria": "servicios",
        "workflow_status": "capturado",
        "estado_factura": "pendiente",
        "estado_conciliacion": "pendiente",
        "company_id": "acme-inc",
        "movimientos_bancarios": [
            {"movement_id": "SPLIT-001"},
            {"movement_id": "SPLIT-002"},
        ],
    }
    expense = _create_expense(client, expense_payload)

    record_bank_movement(
        movement_id="SPLIT-001",
        movement_date="2025-01-05",
        description="Cargo parcial Proveedor X",
        amount=250.0,
        currency="MXN",
        bank="BBVA",
        tags=["tarjeta_empresa"],
        company_id="acme-inc",
    )
    record_bank_movement(
        movement_id="SPLIT-002",
        movement_date="2025-01-06",
        description="Cargo parcial Proveedor X",
        amount=125.0,
        currency="MXN",
        bank="BBVA",
        tags=["tarjeta_empresa"],
        company_id="acme-inc",
    )

    suggestion_payload = {
        "expense_id": str(expense['id']),
        "amount": expense_payload['monto_total'],
        "currency": "MXN",
        "description": expense_payload['descripcion'],
        "date": expense_payload['fecha_gasto'],
        "provider_name": "Proveedor X",
        "paid_by": "company_account",
        "company_id": "acme-inc",
        "metadata": {
            "movimientos_bancarios": [
                {"movement_id": "SPLIT-001"},
                {"movement_id": "SPLIT-002"},
            ]
        },
    }
    resp = asyncio.get_event_loop().run_until_complete(
        client.post('/bank_reconciliation/suggestions', json=suggestion_payload)
    )
    assert resp.status_code == 200
    suggestions = resp.json()['suggestions']
    assert suggestions, "Expected at least one suggestion"

    combo = next((item for item in suggestions if item['type'] == 'combination'), None)
    assert combo is not None, "Expected split-payment combination suggestion"
    assert set(combo['movement_ids']) == {"SPLIT-001", "SPLIT-002"}
    assert combo['split_payment'] is True
    assert combo['linked_match'] is True
    assert combo['group_id'] == "SPLIT-001+SPLIT-002"
    assert any("Pago en 2 cargos" in reason for reason in combo['reasons'])
