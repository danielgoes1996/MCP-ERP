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
from core.internal_db import initialize_internal_database


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Configurar base de datos de pruebas."""
    initialize_internal_database()


@pytest.fixture
def sample_ticket_data():
    """Datos de muestra para tickets."""
    return {
        "raw_data": "OXXO TIENDA #1234 RFC: OXX9999999XXX TOTAL: $125.50 FECHA: 2024-01-15",
        "tipo": "texto",
        "user_id": 1,
        "company_id": "test_company",
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
        assert isinstance(ticket_id, int)
        assert ticket_id > 0

    def test_get_ticket(self, sample_ticket_data):
        """Test de obtención de ticket."""
        # Crear ticket
        ticket_id = create_ticket(**sample_ticket_data)

        # Obtener ticket
        ticket = get_ticket(ticket_id)

        assert ticket is not None
        assert ticket["id"] == ticket_id
        assert ticket["raw_data"] == sample_ticket_data["raw_data"]
        assert ticket["tipo"] == sample_ticket_data["tipo"]
        assert ticket["estado"] == "pendiente"

    def test_list_tickets(self, sample_ticket_data):
        """Test de listado de tickets."""
        company_id = "test_list_company"
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
        assert updated_ticket["estado"] == "procesando"
        assert updated_ticket["invoice_data"]["test"] == "data"

    def test_ticket_with_image_data(self):
        """Test de ticket con imagen."""
        # Crear imagen falsa en base64
        fake_image = base64.b64encode(b"fake image data").decode('utf-8')

        ticket_id = create_ticket(
            raw_data=fake_image,
            tipo="imagen",
            company_id="test_image_company"
        )

        ticket = get_ticket(ticket_id)
        assert ticket["tipo"] == "imagen"
        assert ticket["raw_data"] == fake_image


class TestMerchantManagement:
    """Pruebas para gestión de merchants."""

    def test_create_merchant(self, sample_merchant_data):
        """Test de creación de merchant."""
        merchant_id = create_merchant(**sample_merchant_data)

        assert merchant_id is not None
        assert isinstance(merchant_id, int)
        assert merchant_id > 0

    def test_get_merchant(self, sample_merchant_data):
        """Test de obtención de merchant."""
        # Crear merchant
        merchant_id = create_merchant(**sample_merchant_data)

        # Obtener merchant
        merchant = get_merchant(merchant_id)

        assert merchant is not None
        assert merchant["id"] == merchant_id
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
        assert isinstance(job_id, int)
        assert job_id > 0

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
        assert job["id"] == job_id
        assert job["ticket_id"] == ticket_id
        assert job["estado"] == "pendiente"

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
        assert updated_job["estado"] == "completado"
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
            "company_id": "test_company"
        }

        result = await worker._detect_merchant(ticket)

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
            "company_id": "test_company"
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
            "company_id": "test_company"
        }

        result = await worker._process_portal_invoicing(ticket, merchant)

        assert result["success"] is True
        assert "invoice_data" in result
        assert result["processing_method"] == "portal"

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
            "company_id": "test_company"
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
            "company_id": "test_company"
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

        # Crear expense desde ticket
        expense_id = create_expense_from_ticket(ticket_id)

        assert expense_id is not None
        assert isinstance(expense_id, int)

        # Verificar que el ticket fue actualizado
        updated_ticket = get_ticket(ticket_id)
        assert updated_ticket["invoice_data"]["expense_id"] == expense_id

    def test_link_expense_invoice_success(self, sample_ticket_data):
        """Test de vinculación exitosa de factura con gasto."""
        from core.internal_db import record_internal_expense

        # Crear gasto manualmente
        expense_id = record_internal_expense(
            description="Test expense",
            amount=100.0,
            company_id="test_company"
        )

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
        from core.internal_db import record_internal_expense

        # Crear gasto manualmente
        expense_id = record_internal_expense(
            description="Test expense",
            amount=100.0,
            company_id="test_company"
        )

        # Crear ticket sin datos de factura
        ticket_id = create_ticket(
            raw_data="ticket sin procesar",
            tipo="texto",
            company_id="test_company"
        )

        # Intentar vincular (debería fallar)
        result = link_expense_invoice(expense_id, ticket_id)

        assert result is False


class TestEdgeCases:
    """Pruebas para casos edge y errores."""

    def test_get_nonexistent_ticket(self):
        """Test de obtención de ticket inexistente."""
        ticket = get_ticket(99999)
        assert ticket is None

    def test_get_nonexistent_merchant(self):
        """Test de obtención de merchant inexistente."""
        merchant = get_merchant(99999)
        assert merchant is None

    def test_get_nonexistent_job(self):
        """Test de obtención de job inexistente."""
        job = get_invoicing_job(99999)
        assert job is None

    def test_update_nonexistent_ticket(self):
        """Test de actualización de ticket inexistente."""
        result = update_ticket(99999, estado="test")
        assert result is None

    def test_create_expense_from_unprocessed_ticket(self, sample_ticket_data):
        """Test de creación de gasto desde ticket no procesado."""
        # Crear ticket sin procesar
        ticket_id = create_ticket(**sample_ticket_data)

        # Intentar crear gasto (debería fallar)
        expense_id = create_expense_from_ticket(ticket_id)

        assert expense_id is None

    def test_find_merchant_no_match(self):
        """Test de búsqueda de merchant sin coincidencias."""
        merchant = find_merchant_by_name("NonexistentMerchant12345")
        assert merchant is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])