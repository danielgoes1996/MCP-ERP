"""
Pruebas unitarias para el módulo de facturación automática de tickets.

Cubre:
- Creación y gestión de tickets
- Gestión de merchants
- Procesamiento de jobs
- Integración con ERP interno
"""

import pytest
import json
import base64
from datetime import datetime
from typing import Dict, Any
from uuid import UUID
import psycopg2

# Importar módulos a testear
from modules.invoicing_agent.models import (
    create_ticket,
    get_ticket,
    list_tickets,
    update_ticket,
    create_merchant,
    get_merchant,
    list_merchants,
    find_merchant_by_name,
    create_invoicing_job,
    get_invoicing_job,
    list_pending_jobs,
    update_invoicing_job,
    create_expense_from_ticket,
    link_expense_invoice,
)
from modules.invoicing_agent.worker import InvoicingWorker
from core.shared.db_config import get_connection


# Test tenant ID
TEST_TENANT_ID = 3
TEST_COMPANY_ID = 999  # Company for tests


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Configurar base de datos PostgreSQL de pruebas."""
    # Verify PostgreSQL connection
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ensure test tenant exists
        cursor.execute("""
            INSERT INTO tenants (id, name, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
        """, (TEST_TENANT_ID, "Test Tenant"))

        # Ensure test company exists
        cursor.execute("""
            INSERT INTO companies (id, tenant_id, name, rfc, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
        """, (TEST_COMPANY_ID, TEST_TENANT_ID, "Test Company", "TST000000XXX"))

        # Ensure test user exists (password_hash is required but not important for tests)
        cursor.execute("""
            INSERT INTO users (id, tenant_id, company_id, email, password_hash, name, created_at)
            VALUES (1, %s, %s, 'testuser@example.com', 'test_hash', 'Test User', NOW())
            ON CONFLICT (id) DO NOTHING
        """, (TEST_TENANT_ID, TEST_COMPANY_ID))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Warning: Could not set up test database: {e}")


@pytest.fixture(scope="function", autouse=False)
def cleanup_test_data():
    """Clean up test data after each test function."""
    yield
    # Cleanup is done after the test
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Delete test data (keep in dependency order)
        cursor.execute("DELETE FROM invoice_automation_jobs WHERE tenant_id = %s", (TEST_TENANT_ID,))
        cursor.execute("DELETE FROM tickets WHERE tenant_id = %s AND company_id = %s", (TEST_TENANT_ID, TEST_COMPANY_ID))
        cursor.execute("DELETE FROM merchants WHERE tenant_id = %s AND name LIKE 'Test%' OR name LIKE 'OXXO Test%'", (TEST_TENANT_ID,))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Warning: Could not clean up test data: {e}")


@pytest.fixture
def sample_ticket_data():
    """Datos de muestra para tickets."""
    return {
        "raw_data": "OXXO TIENDA #1234 RFC: OXX9999999XXX TOTAL: $125.50 FECHA: 2024-01-15",
        "tipo": "texto",
        "user_id": 1,
        "company_id": TEST_COMPANY_ID,
        "tenant_id": TEST_TENANT_ID,
    }


@pytest.fixture
def sample_merchant_data():
    """Datos de muestra para merchants."""
    return {
        "nombre": "OXXO Test",
        "metodo_facturacion": "portal",
        "metadata": {
            "url": "https://facturacion.oxxo.com",
            "requires_login": True,
            "rfc": "OXX9999999XXX",
        }
    }


@pytest.fixture
def sample_whatsapp_message():
    """Mensaje de WhatsApp de muestra."""
    return {
        "message_id": "wa_msg_123456",
        "from_number": "+525512345678",
        "message_type": "text",
        "content": "Compré en Walmart por $250.00 el día de hoy, necesito factura",
        "timestamp": datetime.now().isoformat(),
    }


class TestTicketManagement:
    """Pruebas para gestión de tickets."""

    def test_create_ticket(self, sample_ticket_data):
        """Test de creación de ticket."""
        ticket_id = create_ticket(**sample_ticket_data)

        assert ticket_id is not None
        assert isinstance(ticket_id, str)  # UUID string
        assert len(ticket_id) > 0  # UUID non-empty

    def test_get_ticket(self, sample_ticket_data):
        """Test de obtención de ticket."""
        # Crear ticket
        ticket_id = create_ticket(**sample_ticket_data)

        # Obtener ticket
        ticket = get_ticket(ticket_id)

        assert ticket is not None
        assert ticket["id"] == ticket_id  # UUID match
        assert ticket["raw_data"] == sample_ticket_data["raw_data"]
        # tipo "texto" se mapea a source_type "whatsapp" internamente
        assert ticket["tipo"] in ["texto", "whatsapp"]
        assert ticket["estado"] in ["pendiente", "pending"]  # estado maps to status

    def test_list_tickets(self, sample_ticket_data):
        """Test de listado de tickets."""
        company_id = TEST_COMPANY_ID
        sample_ticket_data["company_id"] = company_id

        # Crear varios tickets
        ticket_ids = []
        for i in range(3):
            ticket_data = sample_ticket_data.copy()
            ticket_data["raw_data"] = f"Ticket #{i+1} content"
            ticket_id = create_ticket(**ticket_data)
            ticket_ids.append(ticket_id)

        # Listar tickets
        tickets = list_tickets(company_id=company_id)

        assert len(tickets) >= 3
        ticket_ids_found = [t["id"] for t in tickets]
        for ticket_id in ticket_ids:
            assert ticket_id in ticket_ids_found

    def test_update_ticket(self, sample_ticket_data):
        """Test de actualización de ticket."""
        # Crear ticket
        ticket_id = create_ticket(**sample_ticket_data)

        # Actualizar estado
        updated_ticket = update_ticket(
            ticket_id,
            estado="procesando",
            invoice_data={"test": "data"}
        )

        assert updated_ticket is not None
        # estado "procesando" se mapea a status "processing" en PostgreSQL
        assert updated_ticket["estado"] in ["procesando", "processing"]
        assert updated_ticket["invoice_data"]["test"] == "data"

    def test_ticket_with_image_data(self):
        """Test de ticket con imagen."""
        # Crear imagen falsa en base64
        fake_image = base64.b64encode(b"fake image data").decode('utf-8')

        ticket_id = create_ticket(
            raw_data=fake_image,
            tipo="imagen",
            company_id=TEST_COMPANY_ID,
            user_id=1
        )

        ticket = get_ticket(ticket_id)
        assert ticket["tipo"] in ["imagen", "upload"]  # tipo maps to source_type
        assert ticket["raw_data"] == fake_image


class TestMerchantManagement:
    """Pruebas para gestión de merchants."""

    def test_create_merchant(self, sample_merchant_data):
        """Test de creación de merchant."""
        merchant_id = create_merchant(**sample_merchant_data)

        assert merchant_id is not None
        assert isinstance(merchant_id, str)  # UUID string
        assert len(merchant_id) > 0  # UUID non-empty

    def test_get_merchant(self, sample_merchant_data):
        """Test de obtención de merchant."""
        # Crear merchant
        merchant_id = create_merchant(**sample_merchant_data)

        # Obtener merchant
        merchant = get_merchant(merchant_id)

        assert merchant is not None
        assert merchant["id"] == merchant_id  # UUID match
        assert merchant["nombre"] == sample_merchant_data["nombre"]
        assert merchant["metodo_facturacion"] == sample_merchant_data["metodo_facturacion"]
        assert merchant["is_active"] is True

    def test_list_merchants(self, sample_merchant_data):
        """Test de listado de merchants."""
        # Crear merchant
        merchant_id = create_merchant(**sample_merchant_data)

        # Listar merchants
        merchants = list_merchants(is_active=True)

        assert len(merchants) >= 1
        merchant_ids = [m["id"] for m in merchants]
        assert merchant_id in merchant_ids

    def test_find_merchant_by_name(self, sample_merchant_data):
        """Test de búsqueda de merchant por nombre."""
        # Crear merchant
        create_merchant(**sample_merchant_data)

        # Buscar por nombre
        merchant = find_merchant_by_name("oxxo")  # Case insensitive

        assert merchant is not None
        assert "oxxo" in merchant["nombre"].lower()

    def test_merchant_different_methods(self):
        """Test de merchants con diferentes métodos."""
        methods = ["portal", "email", "api"]

        for method in methods:
            merchant_id = create_merchant(
                nombre=f"Test {method} Merchant",
                metodo_facturacion=method,
                metadata={"test_method": method}
            )

            merchant = get_merchant(merchant_id)
            assert merchant["metodo_facturacion"] == method


class TestInvoicingJobs:
    """Pruebas para jobs de facturación."""

    def test_create_invoicing_job(self, sample_ticket_data, sample_merchant_data):
        """Test de creación de job."""
        # Crear ticket y merchant
        ticket_id = create_ticket(**sample_ticket_data)
        merchant_id = create_merchant(**sample_merchant_data)

        # Crear job
        job_id = create_invoicing_job(
            ticket_id=ticket_id,
            merchant_id=merchant_id,
            company_id=sample_ticket_data["company_id"]
        )

        assert job_id is not None
        assert isinstance(job_id, str)  # UUID string
        assert len(job_id) > 0  # UUID non-empty

    def test_get_invoicing_job(self, sample_ticket_data):
        """Test de obtención de job."""
        # Crear ticket y job
        ticket_id = create_ticket(**sample_ticket_data)
        job_id = create_invoicing_job(
            ticket_id=ticket_id,
            company_id=sample_ticket_data["company_id"]
        )

        # Obtener job
        job = get_invoicing_job(job_id)

        assert job is not None
        assert job["id"] == job_id  # UUID match
        assert job["ticket_id"] == ticket_id
        assert job["estado"] in ["pendiente", "pending"]  # estado maps to status in PostgreSQL

    def test_list_pending_jobs(self, sample_ticket_data):
        """Test de listado de jobs pendientes."""
        company_id = sample_ticket_data["company_id"]

        # Crear ticket y job
        ticket_id = create_ticket(**sample_ticket_data)
        job_id = create_invoicing_job(
            ticket_id=ticket_id,
            company_id=company_id
        )

        # Listar jobs pendientes
        jobs = list_pending_jobs(company_id)

        assert len(jobs) >= 1
        job_ids = [j["id"] for j in jobs]
        assert job_id in job_ids

    def test_update_invoicing_job(self, sample_ticket_data):
        """Test de actualización de job."""
        # Crear ticket y job
        ticket_id = create_ticket(**sample_ticket_data)
        job_id = create_invoicing_job(
            ticket_id=ticket_id,
            company_id=sample_ticket_data["company_id"]
        )

        # Actualizar job
        result_data = {"test": "result", "status": "completed"}
        updated_job = update_invoicing_job(
            job_id,
            estado="completado",
            resultado=result_data,
            completed_at=datetime.now().isoformat()
        )

        assert updated_job is not None
        assert updated_job["estado"] in ["completado", "completed"]  # estado maps to status in PostgreSQL
        assert updated_job["resultado"]["test"] == "result"
        assert updated_job["completed_at"] is not None


class TestWorkerProcessing:
    """Pruebas para el worker de procesamiento."""

    @pytest.fixture
    def worker(self):
        """Instancia del worker."""
        return InvoicingWorker()

    @pytest.mark.asyncio
    async def test_detect_merchant_from_text(self, worker):
        """Test de detección de merchant desde texto."""
        ticket = {
            "id": 1,
            "raw_data": "OXXO TIENDA #1234 TOTAL: $125.50",
            "tipo": "texto",
            "company_id": TEST_COMPANY_ID
        }

        result = await worker._detect_merchant_legacy(ticket)

        # Como es una simulación, debería detectar algo
        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_extract_text_from_image(self, worker):
        """Test de extracción de texto desde imagen."""
        fake_image = base64.b64encode(b"fake image").decode('utf-8')

        text = await worker._extract_text_from_image(fake_image)

        assert isinstance(text, str)
        assert len(text) > 0

    @pytest.mark.asyncio
    async def test_extract_invoice_data(self, worker):
        """Test de extracción de datos de factura."""
        ticket = {
            "raw_data": "WALMART TOTAL: $250.00 FECHA: 2024-01-15",
            "company_id": TEST_COMPANY_ID
        }

        invoice_data = await worker._extract_invoice_data_from_ticket(ticket)

        assert invoice_data["total"] == 250.0
        assert "2024" in invoice_data["fecha"]

    @pytest.mark.asyncio
    async def test_process_portal_invoicing(self, worker, sample_merchant_data):
        """Test de procesamiento por portal."""
        # Crear merchant
        merchant_id = create_merchant(**sample_merchant_data)
        merchant = get_merchant(merchant_id)

        ticket = {
            "id": 1,
            "raw_data": "OXXO TOTAL: $125.50",
            "company_id": TEST_COMPANY_ID
        }

        result = await worker._process_portal_invoicing(ticket, merchant)

        assert result["success"] is True
        assert "invoice_data" in result
        assert result["processing_method"] == "portal_simulation"  # Returns portal_simulation when portal_url not defined

    @pytest.mark.asyncio
    async def test_process_email_invoicing(self, worker):
        """Test de procesamiento por email."""
        merchant = {
            "id": 1,
            "nombre": "Test Email Merchant",
            "metodo_facturacion": "email",
            "metadata": {
                "email": "test@merchant.com",
                "subject_format": "Factura {rfc}"
            }
        }

        ticket = {
            "id": 1,
            "raw_data": "Test Merchant TOTAL: $100.00",
            "company_id": TEST_COMPANY_ID
        }

        result = await worker._process_email_invoicing(ticket, merchant)

        assert result["success"] is True
        assert result["processing_method"] == "email"

    @pytest.mark.asyncio
    async def test_process_api_invoicing(self, worker):
        """Test de procesamiento por API."""
        merchant = {
            "id": 1,
            "nombre": "Test API Merchant",
            "metodo_facturacion": "api",
            "metadata": {
                "api_url": "https://api.merchant.com/invoices",
                "auth_type": "api_key"
            }
        }

        ticket = {
            "id": 1,
            "raw_data": "API Merchant TOTAL: $75.00",
            "company_id": TEST_COMPANY_ID
        }

        result = await worker._process_api_invoicing(ticket, merchant)

        assert result["success"] is True
        assert result["processing_method"] == "api"


class TestERPIntegration:
    """Pruebas para integración con ERP interno."""

    def test_create_expense_from_ticket(self, sample_ticket_data, sample_merchant_data):
        """Test de creación de gasto desde ticket."""
        # Crear ticket con datos de factura
        ticket_id = create_ticket(**sample_ticket_data)

        # Simular que el ticket fue procesado
        invoice_data = {
            "descripcion": "Compra en OXXO",
            "total": 125.50,
            "fecha": "2024-01-15",
            "proveedor": "OXXO",
            "rfc": "OXX9999999XXX",
            "uuid": "TEST-UUID-123",
            "folio": "F123456",
            "url_pdf": "https://test.com/invoice.pdf"
        }

        update_ticket(
            ticket_id,
            estado="procesado",
            invoice_data=invoice_data
        )

        # Crear expense desde ticket (PostgreSQL requires created_by parameter)
        expense_id = create_expense_from_ticket(ticket_id, created_by=1)

        assert expense_id is not None
        assert isinstance(expense_id, int)

        # Verificar que el ticket fue actualizado (expense_id is at root level, not in invoice_data)
        updated_ticket = get_ticket(ticket_id)
        assert updated_ticket.get("expense_id") == expense_id

    def test_link_expense_invoice_success(self, sample_ticket_data):
        """Test de vinculación exitosa de factura con gasto."""
        # Crear gasto manualmente en PostgreSQL
        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO manual_expenses (tenant_id, company_id, amount, description, expense_date, created_by, status)
            VALUES (%s, %s, %s, %s, CURRENT_DATE, 1, 'draft')
            RETURNING id
        """, (TEST_TENANT_ID, TEST_COMPANY_ID, 100.0, "Test expense"))
        expense_id = cursor.fetchone()["id"]
        conn.commit()
        cursor.close()
        conn.close()

        # Crear ticket con datos de factura
        ticket_id = create_ticket(**sample_ticket_data)
        invoice_data = {
            "uuid": "TEST-UUID-LINK",
            "folio": "F789",
            "url_pdf": "https://test.com/link.pdf",
            "fecha": "2024-01-15",
            "xml_content": "<xml>test</xml>"
        }

        update_ticket(
            ticket_id,
            estado="procesado",
            invoice_data=invoice_data
        )

        # Vincular factura con gasto
        result = link_expense_invoice(expense_id, ticket_id)

        assert result is True

    def test_link_expense_invoice_failure(self):
        """Test de vinculación fallida por ticket sin datos."""
        # Crear gasto manualmente en PostgreSQL
        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO manual_expenses (tenant_id, company_id, amount, description, expense_date, created_by, status)
            VALUES (%s, %s, %s, %s, CURRENT_DATE, 1, 'draft')
            RETURNING id
        """, (TEST_TENANT_ID, TEST_COMPANY_ID, 100.0, "Test expense"))
        expense_id = cursor.fetchone()["id"]
        conn.commit()
        cursor.close()
        conn.close()

        # Crear ticket sin datos de factura
        ticket_id = create_ticket(
            raw_data="ticket sin procesar",
            tipo="texto",
            company_id=TEST_COMPANY_ID,
            user_id=1
        )

        # Intentar vincular (debería fallar)
        result = link_expense_invoice(expense_id, ticket_id)

        assert result is False


class TestEdgeCases:
    """Pruebas para casos edge y errores."""

    def test_get_nonexistent_ticket(self):
        """Test de obtención de ticket inexistente."""
        # Use a fake UUID for PostgreSQL
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        ticket = get_ticket(fake_uuid)
        assert ticket is None

    def test_get_nonexistent_merchant(self):
        """Test de obtención de merchant inexistente."""
        # Use a fake UUID for PostgreSQL
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        merchant = get_merchant(fake_uuid)
        assert merchant is None

    def test_get_nonexistent_job(self):
        """Test de obtención de job inexistente."""
        # Use a fake UUID for PostgreSQL
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        job = get_invoicing_job(fake_uuid)
        assert job is None

    def test_update_nonexistent_ticket(self):
        """Test de actualización de ticket inexistente."""
        # Use a fake UUID for PostgreSQL
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        result = update_ticket(fake_uuid, estado="test")
        assert result is None

    def test_create_expense_from_unprocessed_ticket(self, sample_ticket_data):
        """Test de creación de gasto desde ticket no procesado."""
        # Crear ticket sin procesar
        ticket_id = create_ticket(**sample_ticket_data)

        # Intentar crear gasto (debería fallar - PostgreSQL requires created_by)
        expense_id = create_expense_from_ticket(ticket_id, created_by=1)

        assert expense_id is None

    def test_find_merchant_no_match(self):
        """Test de búsqueda de merchant sin coincidencias."""
        merchant = find_merchant_by_name("NonexistentMerchant12345")
        assert merchant is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])