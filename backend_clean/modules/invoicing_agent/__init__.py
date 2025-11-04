"""
Módulo de facturación automática de tickets vía WhatsApp.

Este módulo permite a usuarios en el plan freemium facturar tickets de compra
recibidos por WhatsApp de manera automática, detectando el comercio y utilizando
el método de facturación correspondiente.
"""

from .models import (
    TicketCreate,
    TicketResponse,
    MerchantCreate,
    MerchantResponse,
    InvoicingJobCreate,
    InvoicingJobResponse,
    WhatsAppMessage,
    BulkTicketUpload,
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

__all__ = [
    "TicketCreate",
    "TicketResponse",
    "MerchantCreate",
    "MerchantResponse",
    "InvoicingJobCreate",
    "InvoicingJobResponse",
    "WhatsAppMessage",
    "BulkTicketUpload",
    "create_ticket",
    "get_ticket",
    "list_tickets",
    "update_ticket",
    "create_merchant",
    "get_merchant",
    "list_merchants",
    "find_merchant_by_name",
    "create_invoicing_job",
    "get_invoicing_job",
    "list_pending_jobs",
    "update_invoicing_job",
    "create_expense_from_ticket",
    "link_expense_invoice",
]