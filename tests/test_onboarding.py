"""Tests for onboarding registration and demo seeding."""

import asyncio
from typing import Dict

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


async def _register_user_async(client: AsyncClient, payload: Dict) -> Dict:
    response = await client.post('/onboarding/register', json=payload)
    assert response.status_code == 200
    return response.json()


def register_user(client: AsyncClient, payload: Dict) -> Dict:
    return asyncio.get_event_loop().run_until_complete(_register_user_async(client, payload))


def test_register_user_via_email(client):
    result = register_user(client, {"method": "email", "identifier": "demo.user@gmail.com"})
    assert result['company_id'].startswith('cmp_')
    assert result['demo_snapshot']['total_expenses'] > 0
    assert len(result['demo_expenses']) > 0
    # Fetch expenses scoped by company to ensure seeding
    expenses_resp = asyncio.get_event_loop().run_until_complete(
        client.get('/expenses', params={'company_id': result['company_id']})
    )
    assert expenses_resp.status_code == 200
    expenses = expenses_resp.json()
    assert expenses, "Expected demo expenses for new workspace"


def test_register_user_twice_returns_same_company(client):
    first = register_user(client, {"method": "whatsapp", "identifier": "+52 555 123 4567"})
    second = register_user(client, {"method": "whatsapp", "identifier": "+52 555 123 4567"})
    assert first['company_id'] == second['company_id']
    assert second['already_exists'] is True


def test_invalid_email_domain_rejected(client):
    response = asyncio.get_event_loop().run_until_complete(
        client.post('/onboarding/register', json={"method": "email", "identifier": "persona@empresa.com"})
    )
    assert response.status_code == 400
    assert 'gmail' in response.json()['detail'].lower()


def test_invalid_whatsapp_number_rejected(client):
    response = asyncio.get_event_loop().run_until_complete(
        client.post('/onboarding/register', json={"method": "whatsapp", "identifier": "12345"})
    )
    assert response.status_code == 400
    assert 'WhatsApp' in response.json()['detail']
