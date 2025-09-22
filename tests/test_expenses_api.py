#!/usr/bin/env python3
"""Smoke tests for expense endpoints using FastAPI TestClient."""

from datetime import datetime
from typing import Dict

import asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from core.internal_db import initialize_internal_database
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


async def create_demo_expense_async(client, company_id: str = "default") -> Dict:
    payload = {
        "descripcion": "Taxi aeropuerto",
        "monto_total": 350,
        "fecha_gasto": "2025-09-18",
        "categoria": "transporte",
        "workflow_status": "capturado",
        "estado_factura": "pendiente",
        "estado_conciliacion": "pendiente",
        "company_id": company_id,
    }
    resp = await client.post('/expenses', json=payload)
    assert resp.status_code == 200
    return resp.json()


def create_demo_expense(client, company_id: str = "default") -> Dict:
    return asyncio.get_event_loop().run_until_complete(create_demo_expense_async(client, company_id))


def test_create_expense_generates_id(client):
    data = create_demo_expense(client)
    assert isinstance(data['id'], int)
    assert data['descripcion'] == 'Taxi aeropuerto'
    assert data['company_id'] == 'default'


def test_register_invoice_and_mark_invoiced_flow(client):
    expense = create_demo_expense(client)
    expense_id = expense['id']

    resp = asyncio.get_event_loop().run_until_complete(
        client.post(f'/expenses/{expense_id}/invoice', json={'uuid': 'ABC123', 'folio': 'F123', 'url': 'https://example'})
    )
    assert resp.status_code == 200
    assert resp.json()['estado_factura'] == 'registrada'

    resp = asyncio.get_event_loop().run_until_complete(
        client.post(f'/expenses/{expense_id}/mark-invoiced', json={'actor': 'pytest'})
    )
    assert resp.status_code == 200
    assert resp.json()['estado_factura'] == 'facturado'


def test_bulk_invoice_match_auto_links(client):
    unique_payload = {
        "descripcion": "Gasto único",
        "monto_total": 432.17,
        "fecha_gasto": "2025-10-05",
        "categoria": "transporte",
        "workflow_status": "capturado",
        "estado_factura": "pendiente",
        "estado_conciliacion": "pendiente",
        "company_id": "default",
    }
    expense = asyncio.get_event_loop().run_until_complete(
        client.post('/expenses', json=unique_payload)
    )
    assert expense.status_code == 200
    expense = expense.json()
    expense_id = expense['id']

    bulk_payload = {
        'company_id': 'default',
        'invoices': [
            {
                'filename': 'invoice.xml',
                'uuid': 'UUID-123',
                'total': expense['monto_total'],
                'issued_at': expense['fecha_gasto'],
                'rfc_emisor': 'ABC123456789',
                'raw_xml': '<cfdi:Comprobante Total="{0}" />'.format(expense['monto_total'])
            }
        ],
        'auto_mark_invoiced': True,
    }

    resp = asyncio.get_event_loop().run_until_complete(
        client.post('/invoices/bulk-match', json=bulk_payload)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['processed'] == 1
    result = data['results'][0]
    assert result['status'] == 'linked'
    assert result['expense']['id'] == expense_id
    assert result['expense']['estado_factura'] == 'facturado'


def test_bulk_invoice_match_no_match(client):
    create_demo_expense(client)

    bulk_payload = {
        'company_id': 'default',
        'invoices': [
            {
                'filename': 'other.xml',
                'uuid': 'UUID-999',
                'total': 9999.99,
                'issued_at': '2025-01-01',
                'rfc_emisor': 'XYZ999999999',
                'raw_xml': '<cfdi:Comprobante Total="9999.99" />'
            }
        ],
        'auto_mark_invoiced': True,
    }

    resp = asyncio.get_event_loop().run_until_complete(
        client.post('/invoices/bulk-match', json=bulk_payload)
    )
    assert resp.status_code == 200
    data = resp.json()
    result = data['results'][0]
    assert result['status'] in {'no_match', 'needs_review'}
def test_close_expense_without_invoice(client):
    expense = create_demo_expense(client)
    expense_id = expense['id']

    resp = asyncio.get_event_loop().run_until_complete(
        client.post(f'/expenses/{expense_id}/close-no-invoice', json={'actor': 'pytest'})
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['estado_factura'] == 'sin_factura'
    assert data['will_have_cfdi'] is False


def test_list_expenses_filters(client):
    create_demo_expense(client)
    resp = asyncio.get_event_loop().run_until_complete(
        client.get('/expenses', params={'mes': '2025-09', 'categoria': 'transporte', 'estatus': 'pendiente'})
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data and data[0]['categoria'] == 'transporte'
    assert data[0]['company_id'] == 'default'


def test_list_expenses_scoped_by_company(client):
    default_expense = create_demo_expense(client)
    other_expense = create_demo_expense(client, company_id="acme-inc")

    resp_default = asyncio.get_event_loop().run_until_complete(
        client.get('/expenses', params={'company_id': 'default'})
    )
    assert resp_default.status_code == 200
    default_items = resp_default.json()
    ids_default = {item['id'] for item in default_items}
    assert default_expense['id'] in ids_default
    assert other_expense['id'] not in ids_default

    resp_acme = asyncio.get_event_loop().run_until_complete(
        client.get('/expenses', params={'company_id': 'acme-inc'})
    )
    assert resp_acme.status_code == 200
    acme_items = resp_acme.json()
    ids_acme = {item['id'] for item in acme_items}
    assert other_expense['id'] in ids_acme
    assert default_expense['id'] not in ids_acme
    assert all(item['company_id'] == 'acme-inc' for item in acme_items)
