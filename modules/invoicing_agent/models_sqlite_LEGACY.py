"""
Modelos Pydantic y helpers SQL para el módulo de facturación automática.

Este módulo define los modelos de datos para:
- Tickets de compra recibidos por WhatsApp
- Merchants y métodos de facturación
- Jobs de procesamiento de facturación
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

from core.internal_db import _get_db_path, _DB_LOCK


# ===================================================================
# MODELOS PYDANTIC
# ===================================================================

class TicketCreate(BaseModel):
    """Modelo para crear un ticket de compra."""
    raw_data: str = Field(..., description="Datos del ticket (imagen base64, texto, etc.)")
    tipo: Literal["imagen", "pdf", "texto", "voz"] = Field(..., description="Tipo de contenido del ticket")
    user_id: Optional[int] = Field(None, description="ID del usuario que envía el ticket")
    whatsapp_message_id: Optional[str] = Field(None, description="ID del mensaje de WhatsApp")
    company_id: str = Field("default", description="ID de la empresa")


class TicketResponse(BaseModel):
    """Modelo de respuesta para tickets."""
    id: int
    user_id: Optional[int]
    raw_data: str
    tipo: str
    estado: str
    whatsapp_message_id: Optional[str]
    merchant_id: Optional[int]
    merchant_name: Optional[str] = None
    invoice_data: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str
    company_id: str


class MerchantCreate(BaseModel):
    """Modelo para crear un merchant."""
    nombre: str = Field(..., description="Nombre del comercio")
    metodo_facturacion: Literal["portal", "email", "api"] = Field(..., description="Método de facturación")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata adicional (credenciales, URLs, etc.)")


class MerchantResponse(BaseModel):
    """Modelo de respuesta para merchants."""
    id: int
    nombre: str
    metodo_facturacion: str
    metadata: Optional[Dict[str, Any]]
    is_active: bool
    created_at: str
    updated_at: str


class InvoicingJobCreate(BaseModel):
    """Modelo para crear un job de facturación."""
    ticket_id: int = Field(..., description="ID del ticket asociado")
    merchant_id: Optional[int] = Field(None, description="ID del merchant identificado")
    scheduled_at: Optional[str] = Field(None, description="Cuándo ejecutar el job")
    company_id: str = Field("default", description="ID de la empresa")


class InvoicingJobResponse(BaseModel):
    """Modelo de respuesta para jobs de facturación."""
    id: int
    ticket_id: int
    merchant_id: Optional[int]
    merchant_name: Optional[str] = None
    estado: str
    resultado: Optional[Dict[str, Any]] = None
    error_message: Optional[str]
    retry_count: int
    scheduled_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    updated_at: str
    company_id: str


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
    company_id: str = Field("default", description="ID de la empresa")


# ===================================================================
# HELPERS SQL PARA TICKETS
# ===================================================================

def create_ticket(
    *,
    raw_data: str,
    tipo: str,
    user_id: Optional[int] = None,
    whatsapp_message_id: Optional[str] = None,
    company_id: str = "default",
    original_image: Optional[str] = None,
) -> int:
    """Crear un nuevo ticket en la base de datos."""
    now = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            cursor = connection.execute(
                """
                INSERT INTO tickets (
                    user_id,
                    raw_data,
                    tipo,
                    estado,
                    whatsapp_message_id,
                    company_id,
                    created_at,
                    updated_at,
                    original_image
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, raw_data, tipo, "pendiente", whatsapp_message_id, company_id, now, now, original_image),
            )
            connection.commit()
            return int(cursor.lastrowid)


def get_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    """Obtener un ticket por ID."""
    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT t.*, m.nombre as merchant_name
            FROM tickets t
            LEFT JOIN merchants m ON t.merchant_id = m.id
            WHERE t.id = ?
            """,
            (ticket_id,)
        ).fetchone()

        if not row:
            return None

        ticket = dict(row)
        if ticket.get("invoice_data"):
            try:
                ticket["invoice_data"] = json.loads(ticket["invoice_data"])
            except json.JSONDecodeError:
                ticket["invoice_data"] = None

        if ticket.get("llm_analysis"):
            try:
                ticket["llm_analysis"] = json.loads(ticket["llm_analysis"])
            except json.JSONDecodeError:
                ticket["llm_analysis"] = None

        return ticket


def list_tickets(
    *,
    company_id: str = "default",
    estado: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Listar tickets con filtros opcionales."""
    conditions = ["t.company_id = ?"]
    params = [company_id]

    if estado:
        conditions.append("t.estado = ?")
        params.append(estado)

    if user_id is not None:
        conditions.append("t.user_id = ?")
        params.append(user_id)

    query = f"""
        SELECT t.*, m.nombre as merchant_name
        FROM tickets t
        LEFT JOIN merchants m ON t.merchant_id = m.id
        WHERE {" AND ".join(conditions)}
        ORDER BY t.created_at DESC
        LIMIT ?
    """
    params.append(limit)

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, params).fetchall()

        tickets = []
        for row in rows:
            ticket = dict(row)
            if ticket.get("invoice_data"):
                try:
                    ticket["invoice_data"] = json.loads(ticket["invoice_data"])
                except json.JSONDecodeError:
                    ticket["invoice_data"] = None

            if ticket.get("llm_analysis"):
                try:
                    ticket["llm_analysis"] = json.loads(ticket["llm_analysis"])
                except json.JSONDecodeError:
                    ticket["llm_analysis"] = None

            # Agregar campo processing para el frontend (SINCRONIZADO)
            ticket["processing"] = _calculate_processing_status(ticket)
            tickets.append(ticket)

        return tickets


def _calculate_processing_status(ticket: Dict[str, Any]) -> bool:
    """
    Función centralizada para calcular el estado de procesamiento.
    SINCRONIZADA entre POST /tickets y GET /tickets.
    """
    if ticket.get("tipo") == "imagen":
        # Para imágenes: está en procesamiento si NO tiene merchant_name válido Y análisis LLM
        merchant_name = ticket.get("merchant_name")
        llm_analysis = ticket.get("llm_analysis")

        # Considerar procesado si tiene merchant_name válido Y análisis LLM
        has_valid_merchant = (
            merchant_name is not None and
            merchant_name != "" and
            merchant_name != "Unknown" and
            merchant_name != "Procesando imagen..."
        )
        has_analysis = llm_analysis is not None

        # Solo está en procesamiento si le falta merchant o análisis
        return not (has_valid_merchant and has_analysis)

    # Para texto: normalmente no está en procesamiento a menos que tenga indicadores específicos
    merchant_name = ticket.get("merchant_name")
    return (
        merchant_name == "Procesando imagen..." or
        merchant_name == "Texto insuficiente"
    )


def update_ticket(
    ticket_id: int,
    *,
    estado: Optional[str] = None,
    merchant_id: Optional[int] = None,
    merchant_name: Optional[str] = None,
    category: Optional[str] = None,
    confidence: Optional[float] = None,
    invoice_data: Optional[Dict[str, Any]] = None,
    llm_analysis: Optional[Dict[str, Any]] = None,
    raw_data: Optional[str] = None,
    extracted_text: Optional[str] = None,
    linked_expense_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Actualizar un ticket."""
    updates = []
    params = []

    if estado is not None:
        updates.append("estado = ?")
        params.append(estado)

    if merchant_id is not None:
        updates.append("merchant_id = ?")
        params.append(merchant_id)

    if merchant_name is not None:
        updates.append("merchant_name = ?")
        params.append(merchant_name)

    if category is not None:
        updates.append("category = ?")
        params.append(category)

    if confidence is not None:
        updates.append("confidence = ?")
        params.append(confidence)

    if invoice_data is not None:
        updates.append("invoice_data = ?")
        params.append(json.dumps(invoice_data))

    if llm_analysis is not None:
        updates.append("llm_analysis = ?")
        params.append(json.dumps(llm_analysis))

    if raw_data is not None:
        updates.append("raw_data = ?")
        params.append(raw_data)

    if extracted_text is not None:
        updates.append("extracted_text = ?")
        params.append(extracted_text)

    if linked_expense_id is not None:
        updates.append("linked_expense_id = ?")
        params.append(linked_expense_id)

    if not updates:
        return get_ticket(ticket_id)

    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(ticket_id)

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.execute(
                f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?",
                params
            )
            connection.commit()

    return get_ticket(ticket_id)


# ===================================================================
# HELPERS SQL PARA MERCHANTS
# ===================================================================

def create_merchant(
    *,
    nombre: str,
    metodo_facturacion: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Crear un nuevo merchant."""
    now = datetime.utcnow().isoformat()
    metadata_json = json.dumps(metadata) if metadata else None

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO merchants (
                    nombre,
                    metodo_facturacion,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (nombre, metodo_facturacion, metadata_json, now, now),
            )
            connection.commit()
            return int(cursor.lastrowid)


def get_merchant(merchant_id: int) -> Optional[Dict[str, Any]]:
    """Obtener un merchant por ID."""
    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM merchants WHERE id = ?",
            (merchant_id,)
        ).fetchone()

        if not row:
            return None

        merchant = dict(row)
        merchant["is_active"] = bool(merchant.get("is_active", 1))
        if merchant.get("metadata"):
            try:
                merchant["metadata"] = json.loads(merchant["metadata"])
            except json.JSONDecodeError:
                merchant["metadata"] = None

        return merchant


def list_merchants(*, is_active: bool = True) -> List[Dict[str, Any]]:
    """Listar merchants activos."""
    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM merchants WHERE is_active = ? ORDER BY nombre",
            (int(is_active),)
        ).fetchall()

        merchants = []
        for row in rows:
            merchant = dict(row)
            merchant["is_active"] = bool(merchant.get("is_active", 1))
            if merchant.get("metadata"):
                try:
                    merchant["metadata"] = json.loads(merchant["metadata"])
                except json.JSONDecodeError:
                    merchant["metadata"] = None
            merchants.append(merchant)

        return merchants


def find_merchant_by_name(nombre: str) -> Optional[Dict[str, Any]]:
    """Buscar merchant por nombre (case insensitive)."""
    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM merchants WHERE LOWER(nombre) LIKE LOWER(?) AND is_active = 1",
            (f"%{nombre}%",)
        ).fetchone()

        if not row:
            return None

        merchant = dict(row)
        merchant["is_active"] = bool(merchant.get("is_active", 1))
        if merchant.get("metadata"):
            try:
                merchant["metadata"] = json.loads(merchant["metadata"])
            except json.JSONDecodeError:
                merchant["metadata"] = None

        return merchant


# ===================================================================
# HELPERS SQL PARA INVOICING JOBS
# ===================================================================

def create_invoicing_job(
    *,
    ticket_id: int,
    merchant_id: Optional[int] = None,
    scheduled_at: Optional[str] = None,
    company_id: str = "default",
) -> int:
    """Crear un nuevo job de facturación."""
    now = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            cursor = connection.execute(
                """
                INSERT INTO invoicing_jobs (
                    ticket_id,
                    merchant_id,
                    estado,
                    scheduled_at,
                    company_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ticket_id, merchant_id, "pendiente", scheduled_at or now, company_id, now, now),
            )
            connection.commit()
            return int(cursor.lastrowid)


def get_invoicing_job(job_id: int) -> Optional[Dict[str, Any]]:
    """Obtener un job por ID."""
    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT j.*, m.nombre as merchant_name
            FROM invoicing_jobs j
            LEFT JOIN merchants m ON j.merchant_id = m.id
            WHERE j.id = ?
            """,
            (job_id,)
        ).fetchone()

        if not row:
            return None

        job = dict(row)
        if job.get("resultado"):
            try:
                job["resultado"] = json.loads(job["resultado"])
            except json.JSONDecodeError:
                job["resultado"] = None

        return job


def list_pending_jobs(company_id: str = "default") -> List[Dict[str, Any]]:
    """Listar jobs pendientes de procesar."""
    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT j.*, m.nombre as merchant_name
            FROM invoicing_jobs j
            LEFT JOIN merchants m ON j.merchant_id = m.id
            WHERE j.estado = 'pendiente'
              AND j.company_id = ?
              AND (j.scheduled_at IS NULL OR j.scheduled_at <= ?)
            ORDER BY j.created_at ASC
            """,
            (company_id, datetime.utcnow().isoformat())
        ).fetchall()

        jobs = []
        for row in rows:
            job = dict(row)
            if job.get("resultado"):
                try:
                    job["resultado"] = json.loads(job["resultado"])
                except json.JSONDecodeError:
                    job["resultado"] = None
            jobs.append(job)

        return jobs


def update_invoicing_job(
    job_id: int,
    *,
    estado: Optional[str] = None,
    merchant_id: Optional[int] = None,
    resultado: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    retry_count: Optional[int] = None,
    completed_at: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Actualizar un job de facturación."""
    updates = []
    params = []

    if estado is not None:
        updates.append("estado = ?")
        params.append(estado)

    if merchant_id is not None:
        updates.append("merchant_id = ?")
        params.append(merchant_id)

    if resultado is not None:
        updates.append("resultado = ?")
        params.append(json.dumps(resultado))

    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)

    if retry_count is not None:
        updates.append("retry_count = ?")
        params.append(retry_count)

    if completed_at is not None:
        updates.append("completed_at = ?")
        params.append(completed_at)

    if not updates:
        return get_invoicing_job(job_id)

    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(job_id)

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.execute(
                f"UPDATE invoicing_jobs SET {', '.join(updates)} WHERE id = ?",
                params
            )
            connection.commit()

    return get_invoicing_job(job_id)


# ===================================================================
# FUNCIONES DE INTEGRACIÓN CON ERP
# ===================================================================

def create_expense_from_ticket(ticket_id: int) -> Optional[int]:
    """Crear un expense_record a partir de un ticket procesado."""
    from core.internal_db import record_internal_expense

    ticket = get_ticket(ticket_id)
    if not ticket or not ticket.get("invoice_data"):
        return None

    invoice_data = ticket["invoice_data"]

    # Mapear datos del ticket a expense record
    expense_id = record_internal_expense(
        description=invoice_data.get("descripcion", f"Gasto desde ticket #{ticket_id}"),
        amount=float(invoice_data.get("total", 0.0)),
        account_code="6180",  # Código por defecto
        expense_date=invoice_data.get("fecha"),
        category=invoice_data.get("categoria"),
        provider_name=invoice_data.get("proveedor"),
        provider_rfc=invoice_data.get("rfc_emisor"),
        workflow_status="facturado",
        invoice_status="facturado",
        invoice_uuid=invoice_data.get("uuid"),
        invoice_folio=invoice_data.get("folio"),
        invoice_url=invoice_data.get("url_pdf"),
        external_reference=f"ticket_{ticket_id}",
        metadata={
            "origen": "invoicing_agent",
            "ticket_id": ticket_id,
            "whatsapp_message_id": ticket.get("whatsapp_message_id"),
        },
        company_id=ticket["company_id"],
    )

    # Actualizar el ticket con el expense_id
    update_ticket(
        ticket_id,
        estado="procesado",
        invoice_data={**invoice_data, "expense_id": expense_id}
    )

    return expense_id


def link_expense_invoice(expense_id: int, ticket_id: int) -> bool:
    """Vincular una factura obtenida con un expense record."""
    from core.internal_db import register_expense_invoice

    ticket = get_ticket(ticket_id)
    if not ticket or not ticket.get("invoice_data"):
        return False

    invoice_data = ticket["invoice_data"]

    try:
        register_expense_invoice(
            expense_id,
            uuid=invoice_data.get("uuid"),
            folio=invoice_data.get("folio"),
            url=invoice_data.get("url_pdf"),
            issued_at=invoice_data.get("fecha"),
            status="registrada",
            raw_xml=invoice_data.get("xml_content"),
            actor="invoicing_agent",
        )
        return True
    except Exception:
        return False
