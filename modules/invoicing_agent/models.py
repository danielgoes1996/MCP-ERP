"""
Modelos y helpers SQL para facturación automática (PostgreSQL).
Migrado de SQLite a PostgreSQL con soporte para UUIDs.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Literal
from uuid import UUID
from pydantic import BaseModel, Field
from core.shared.db_config import get_connection

# ===================================================================
# MODELOS PYDANTIC
# ===================================================================

class TicketCreate(BaseModel):
    """Modelo para crear un ticket de compra."""
    raw_data: str = Field(..., description="Datos del ticket (imagen base64, texto, etc.)")
    tipo: Literal["imagen", "pdf", "texto", "voz"] = Field(..., description="Tipo de contenido del ticket")
    user_id: Optional[int] = Field(None, description="ID del usuario que envía el ticket")
    whatsapp_message_id: Optional[str] = Field(None, description="ID del mensaje de WhatsApp")
    company_id: Optional[int] = Field(None, description="ID de la empresa")
    tenant_id: int = Field(1, description="ID del tenant (multi-tenancy)")


class TicketResponse(BaseModel):
    """Modelo de respuesta para tickets."""
    id: str  # UUID as string
    user_id: Optional[int]
    raw_data: str
    tipo: str
    estado: str
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None
    created_at: str
    updated_at: str


class MerchantCreate(BaseModel):
    """Modelo para crear un merchant."""
    nombre: str
    metodo_facturacion: Literal["portal", "email", "api"]
    rfc: Optional[str] = None
    portal_url: Optional[str] = None
    tenant_id: int = Field(1, description="ID del tenant")


class MerchantResponse(BaseModel):
    """Modelo de respuesta para merchants."""
    id: str  # UUID as string
    nombre: str
    metodo_facturacion: str
    is_active: bool
    created_at: str


class InvoicingJobCreate(BaseModel):
    """Modelo para crear un job de facturación."""
    ticket_id: str = Field(..., description="UUID del ticket asociado")
    merchant_id: Optional[str] = Field(None, description="UUID del merchant identificado")
    scheduled_at: Optional[str] = Field(None, description="Cuándo ejecutar el job")
    tenant_id: int = Field(1, description="ID del tenant")


class InvoicingJobResponse(BaseModel):
    """Modelo de respuesta para jobs de facturación."""
    id: str  # UUID as string
    ticket_id: str
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None
    estado: str
    created_at: str


class WhatsAppMessage(BaseModel):
    """Modelo para mensajes entrantes de WhatsApp."""
    message_id: str = Field(..., description="ID único del mensaje")
    from_number: str = Field(..., description="Número del remitente")
    message_type: Literal["text", "image", "document", "audio"] = Field(..., description="Tipo de mensaje")
    content: str = Field(..., description="Contenido del mensaje")
    timestamp: Optional[str] = Field(None, description="Timestamp del mensaje")
    media_url: Optional[str] = Field(None, description="URL del archivo multimedia")


class BulkTicketUpload(BaseModel):
    """Modelo para carga masiva de tickets."""
    tickets: List[Dict[str, Any]] = Field(..., description="Lista de tickets a procesar")
    auto_process: bool = Field(True, description="Procesar automáticamente")
    tenant_id: int = Field(1, description="ID del tenant")


# ===================================================================
# TICKETS
# ===================================================================

def create_ticket(*, raw_data: str, tipo: str, user_id: Optional[int] = None,
                  whatsapp_message_id: Optional[str] = None, company_id: Optional[int] = None,
                  original_image: Optional[str] = None, tenant_id: int = 3) -> str:
    """Crear ticket. Returns UUID string."""
    source_map = {"imagen": "upload", "pdf": "upload", "texto": "whatsapp", "voz": "voice"}
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO tickets (tenant_id, company_id, user_id, source_type, raw_data, 
               raw_file_url, status, processing_status, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'pending', %s) RETURNING id""",
            (tenant_id, company_id, user_id, source_map.get(tipo, "upload"), raw_data, original_image,
             json.dumps({"tipo_original": tipo, "whatsapp_message_id": whatsapp_message_id}))
        )
        result = cursor.fetchone()
        conn.commit()
        return str(result["id"])
    finally:
        cursor.close()
        conn.close()

def get_ticket(ticket_id: Union[str, UUID]) -> Optional[Dict[str, Any]]:
    """Obtener ticket por UUID."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT t.*, m.name as merchant_name FROM tickets t
               LEFT JOIN merchants m ON t.merchant_id = m.id WHERE t.id = %s""",
            (str(ticket_id),)
        )
        row = cursor.fetchone()
        if not row:
            return None
        ticket = dict(row)
        ticket["id"] = str(ticket["id"])
        if ticket.get("merchant_id"):
            ticket["merchant_id"] = str(ticket["merchant_id"])
        ticket["tipo"] = ticket.get("source_type", "upload")
        ticket["estado"] = ticket.get("status", "pending")
        metadata = ticket.get("metadata", {})
        if metadata:
            ticket["whatsapp_message_id"] = metadata.get("whatsapp_message_id")
        if ticket.get("extracted_data"):
            ticket["invoice_data"] = ticket["extracted_data"]
        if ticket.get("ocr_data"):
            ticket["llm_analysis"] = ticket["ocr_data"]
        return ticket
    finally:
        cursor.close()
        conn.close()

def list_tickets(*, company_id: Optional[int] = None, estado: Optional[str] = None,
                 user_id: Optional[int] = None, tenant_id: int = 3, limit: int = 100) -> List[Dict[str, Any]]:
    """Listar tickets."""
    conditions, params = ["t.tenant_id = %s"], [tenant_id]
    if company_id is not None:
        conditions.append("t.company_id = %s")
        params.append(company_id)
    if estado:
        status_map = {"pendiente": "pending", "procesado": "processed", "procesando": "processing"}
        conditions.append("t.status = %s")
        params.append(status_map.get(estado, estado))
    if user_id is not None:
        conditions.append("t.user_id = %s")
        params.append(user_id)
    
    query = f"""SELECT t.*, m.name as merchant_name FROM tickets t
                LEFT JOIN merchants m ON t.merchant_id = m.id
                WHERE {" AND ".join(conditions)} ORDER BY t.created_at DESC LIMIT %s"""
    params.append(limit)
    
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        tickets = []
        for row in cursor.fetchall():
            ticket = dict(row)
            ticket["id"] = str(ticket["id"])
            if ticket.get("merchant_id"):
                ticket["merchant_id"] = str(ticket["merchant_id"])
            ticket["tipo"] = ticket.get("source_type", "upload")
            ticket["estado"] = ticket.get("status", "pending")
            metadata = ticket.get("metadata", {})
            if metadata:
                ticket["whatsapp_message_id"] = metadata.get("whatsapp_message_id")
            if ticket.get("extracted_data"):
                ticket["invoice_data"] = ticket["extracted_data"]
            if ticket.get("ocr_data"):
                ticket["llm_analysis"] = ticket["ocr_data"]
            ticket["processing"] = _calculate_processing_status(ticket)
            tickets.append(ticket)
        return tickets
    finally:
        cursor.close()
        conn.close()

def _calculate_processing_status(ticket: Dict[str, Any]) -> bool:
    """Calcular si está en procesamiento."""
    if ticket.get("tipo") == "imagen" or ticket.get("source_type") == "upload":
        merchant_name = ticket.get("merchant_name")
        llm_analysis = ticket.get("llm_analysis") or ticket.get("ocr_data")
        has_valid_merchant = merchant_name and merchant_name not in ["", "Unknown", "Procesando imagen..."]
        return not (has_valid_merchant and llm_analysis)
    return ticket.get("merchant_name") in ["Procesando imagen...", "Texto insuficiente"]

def update_ticket(ticket_id: Union[str, UUID], *, estado: Optional[str] = None,
                  merchant_id: Optional[Union[str, UUID]] = None, merchant_name: Optional[str] = None,
                  confidence: Optional[float] = None, invoice_data: Optional[Dict[str, Any]] = None,
                  llm_analysis: Optional[Dict[str, Any]] = None, raw_data: Optional[str] = None,
                  linked_expense_id: Optional[int] = None, **kwargs) -> Optional[Dict[str, Any]]:
    """Actualizar ticket."""
    updates, params = [], []
    if estado:
        status_map = {"pendiente": "pending", "procesado": "processed", "procesando": "processing", "fallido": "failed"}
        updates.append("status = %s")
        params.append(status_map.get(estado, estado))
    if merchant_id:
        updates.append("merchant_id = %s")
        params.append(str(merchant_id))
    if merchant_name:
        updates.append("merchant_name = %s")
        params.append(merchant_name)
    if confidence is not None:
        updates.append("merchant_confidence = %s")
        params.append(confidence)
    if invoice_data:
        updates.append("extracted_data = %s")
        params.append(json.dumps(invoice_data))
    if llm_analysis:
        updates.append("ocr_data = %s")
        params.append(json.dumps(llm_analysis))
    if raw_data:
        updates.append("raw_data = %s")
        params.append(raw_data)
    if linked_expense_id:
        updates.append("expense_id = %s")
        params.append(linked_expense_id)
    
    if not updates:
        return get_ticket(ticket_id)
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(ticket_id))
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE tickets SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return get_ticket(ticket_id)

# ===================================================================
# MERCHANTS
# ===================================================================

def create_merchant(*, nombre: str, metodo_facturacion: str, rfc: Optional[str] = None,
                    portal_url: Optional[str] = None, metadata: Optional[Dict] = None,
                    tenant_id: int = 3, **kwargs) -> str:
    """Crear merchant. Returns UUID string."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO merchants (tenant_id, name, rfc, invoicing_method, portal_url, metadata)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (tenant_id, nombre, rfc, metodo_facturacion, portal_url, json.dumps(metadata) if metadata else None)
        )
        result = cursor.fetchone()
        conn.commit()
        return str(result["id"])
    finally:
        cursor.close()
        conn.close()

def get_merchant(merchant_id: Union[str, UUID]) -> Optional[Dict[str, Any]]:
    """Obtener merchant por UUID."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM merchants WHERE id = %s", (str(merchant_id),))
        row = cursor.fetchone()
        if not row:
            return None
        merchant = dict(row)
        merchant["id"] = str(merchant["id"])
        merchant["nombre"] = merchant.get("name")
        merchant["metodo_facturacion"] = merchant.get("invoicing_method")
        return merchant
    finally:
        cursor.close()
        conn.close()

def list_merchants(*, is_active: bool = True, tenant_id: int = 3) -> List[Dict[str, Any]]:
    """Listar merchants."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM merchants WHERE tenant_id = %s AND is_active = %s ORDER BY name",
            (tenant_id, is_active)
        )
        merchants = []
        for row in cursor.fetchall():
            merchant = dict(row)
            merchant["id"] = str(merchant["id"])
            merchant["nombre"] = merchant.get("name")
            merchant["metodo_facturacion"] = merchant.get("invoicing_method")
            merchants.append(merchant)
        return merchants
    finally:
        cursor.close()
        conn.close()

def find_merchant_by_name(nombre: str, tenant_id: int = 3) -> Optional[Dict[str, Any]]:
    """Buscar merchant por nombre."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM merchants WHERE tenant_id = %s AND LOWER(name) LIKE LOWER(%s)
               AND is_active = true LIMIT 1""",
            (tenant_id, f"%{nombre}%")
        )
        row = cursor.fetchone()
        if not row:
            return None
        merchant = dict(row)
        merchant["id"] = str(merchant["id"])
        merchant["nombre"] = merchant.get("name")
        merchant["metodo_facturacion"] = merchant.get("invoicing_method")
        return merchant
    finally:
        cursor.close()
        conn.close()

# ===================================================================
# INVOICING JOBS
# ===================================================================

def create_invoicing_job(*, ticket_id: Union[str, UUID], merchant_id: Optional[Union[str, UUID]] = None,
                         scheduled_at: Optional[str] = None, tenant_id: int = 3, **kwargs) -> str:
    """Crear job. Returns UUID string."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO invoice_automation_jobs (tenant_id, ticket_id, merchant_id, status, scheduled_at)
               VALUES (%s, %s, %s, 'pending', %s) RETURNING id""",
            (tenant_id, str(ticket_id), str(merchant_id) if merchant_id else None,
             scheduled_at or datetime.utcnow().isoformat())
        )
        result = cursor.fetchone()
        conn.commit()
        return str(result["id"])
    finally:
        cursor.close()
        conn.close()

def get_invoicing_job(job_id: Union[str, UUID]) -> Optional[Dict[str, Any]]:
    """Obtener job por UUID."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT j.*, m.name as merchant_name FROM invoice_automation_jobs j
               LEFT JOIN merchants m ON j.merchant_id = m.id WHERE j.id = %s""",
            (str(job_id),)
        )
        row = cursor.fetchone()
        if not row:
            return None
        job = dict(row)
        job["id"] = str(job["id"])
        if job.get("ticket_id"):
            job["ticket_id"] = str(job["ticket_id"])
        if job.get("merchant_id"):
            job["merchant_id"] = str(job["merchant_id"])
        job["estado"] = job.get("status", "pending")
        job["resultado"] = job.get("execution_result")
        return job
    finally:
        cursor.close()
        conn.close()

def list_pending_jobs(company_id: str = "default", tenant_id: int = 3) -> List[Dict[str, Any]]:
    """Listar jobs pendientes."""
    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT j.*, m.name as merchant_name FROM invoice_automation_jobs j
               LEFT JOIN merchants m ON j.merchant_id = m.id
               WHERE j.tenant_id = %s AND j.status = 'pending'
               AND (j.scheduled_at IS NULL OR j.scheduled_at <= %s)
               ORDER BY j.created_at ASC""",
            (tenant_id, datetime.utcnow().isoformat())
        )
        jobs = []
        for row in cursor.fetchall():
            job = dict(row)
            job["id"] = str(job["id"])
            if job.get("ticket_id"):
                job["ticket_id"] = str(job["ticket_id"])
            if job.get("merchant_id"):
                job["merchant_id"] = str(job["merchant_id"])
            job["estado"] = job.get("status")
            job["resultado"] = job.get("execution_result")
            jobs.append(job)
        return jobs
    finally:
        cursor.close()
        conn.close()

def update_invoicing_job(job_id: Union[str, UUID], *, estado: Optional[str] = None,
                         merchant_id: Optional[Union[str, UUID]] = None,
                         resultado: Optional[Dict[str, Any]] = None,
                         error_message: Optional[str] = None, retry_count: Optional[int] = None,
                         completed_at: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
    """Actualizar job."""
    updates, params = [], []
    if estado:
        status_map = {"pendiente": "pending", "procesando": "running", "completado": "completed", "fallido": "failed"}
        updates.append("status = %s")
        params.append(status_map.get(estado, estado))
    if merchant_id:
        updates.append("merchant_id = %s")
        params.append(str(merchant_id))
    if resultado:
        updates.append("execution_result = %s")
        params.append(json.dumps(resultado))
    if error_message:
        updates.append("error_details = %s")
        params.append(json.dumps({"message": error_message}))
    if retry_count is not None:
        updates.append("retry_count = %s")
        params.append(retry_count)
    if completed_at:
        updates.append("completed_at = %s")
        params.append(completed_at)
    
    if not updates:
        return get_invoicing_job(job_id)
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(job_id))
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE invoice_automation_jobs SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return get_invoicing_job(job_id)

# ===================================================================
# INTEGRACIÓN
# ===================================================================

def link_expense_invoice(expense_id: int, ticket_id: Union[str, UUID]) -> bool:
    """Vincular expense con ticket (bidireccional). Only links if ticket has invoice_data."""
    # First, validate that ticket has invoice_data
    ticket = get_ticket(ticket_id)
    if not ticket:
        return False

    # Check if ticket has invoice_data
    invoice_data = ticket.get("invoice_data") or ticket.get("extracted_data")
    if not invoice_data or not isinstance(invoice_data, dict) or len(invoice_data) == 0:
        return False

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE manual_expenses SET ticket_id = %s WHERE id = %s", (str(ticket_id), expense_id))
        cursor.execute("UPDATE tickets SET expense_id = %s WHERE id = %s", (expense_id, str(ticket_id)))
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def create_expense_from_ticket(ticket_id: Union[str, UUID], created_by: int) -> Optional[int]:
    """
    Crear manual_expense desde un ticket procesado.

    Crea la relación bidireccional:
    - manual_expenses.ticket_id → tickets.id (UUID)
    - tickets.expense_id → manual_expenses.id (INTEGER)

    Args:
        ticket_id: UUID del ticket
        created_by: ID del usuario que crea el expense

    Returns:
        ID del expense creado (INTEGER) o None si falla
    """
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None

    # Extraer datos del ticket
    extracted_data = ticket.get("extracted_data") or ticket.get("invoice_data") or {}

    # Valores por defecto
    amount = extracted_data.get("total", 0.0)
    if not amount or amount <= 0:
        # Intentar con subtotal + IVA
        subtotal = ticket.get("subtotal", 0.0)
        iva = ticket.get("iva", 0.0)
        amount = subtotal + iva if subtotal else 0.0

    if not amount or amount <= 0:
        return None  # No se puede crear expense sin monto

    # Preparar datos del expense
    expense_date = ticket.get("ticket_date") or extracted_data.get("fecha")
    merchant_name = ticket.get("merchant_name") or extracted_data.get("proveedor", "Proveedor desconocido")
    description = extracted_data.get("descripcion") or f"Gasto desde ticket {str(ticket_id)[:8]}"

    conn = get_connection(dict_cursor=True)
    try:
        cursor = conn.cursor()

        # Crear el expense
        cursor.execute(
            """
            INSERT INTO manual_expenses (
                tenant_id,
                company_id,
                amount,
                currency,
                description,
                expense_date,
                category,
                provider_name,
                provider_rfc,
                iva_amount,
                status,
                invoice_required,
                invoice_uploaded,
                created_by,
                ticket_id,
                notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                ticket.get("tenant_id", 3),
                ticket.get("company_id"),
                amount,
                ticket.get("currency", "MXN"),
                description,
                expense_date,
                extracted_data.get("categoria"),
                merchant_name,
                extracted_data.get("rfc_emisor"),
                ticket.get("iva", 0.0),
                "pending_invoice" if ticket.get("will_have_cfdi") else "draft",
                ticket.get("will_have_cfdi", True),
                bool(ticket.get("cfdi_uuid")),
                created_by,
                str(ticket_id),
                f"Creado automáticamente desde ticket. Merchant: {merchant_name}"
            )
        )

        result = cursor.fetchone()
        expense_id = result["id"]

        # Actualizar el ticket con el expense_id (relación bidireccional)
        cursor.execute(
            "UPDATE tickets SET expense_id = %s WHERE id = %s",
            (expense_id, str(ticket_id))
        )

        conn.commit()
        return expense_id

    except Exception as e:
        conn.rollback()
        print(f"Error creating expense from ticket: {e}")
        return None
    finally:
        cursor.close()
        conn.close()
