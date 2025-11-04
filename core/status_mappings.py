"""Utilities to normalize expense status values between legacy Spanish and new English naming."""

from __future__ import annotations

from typing import Optional


def _normalize(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


_INVOICE_STATUS_TO_PUBLIC = {
    "pendiente": "pending_invoice",
    "pending": "pending_invoice",
    "pendiente_factura": "pending_invoice",
    "pending_invoice": "pending_invoice",
    "waiting_cfdi_match": "waiting_cfdi_match",
    "esperando_cfdi": "waiting_cfdi_match",
    "registrada": "registered",
    "registrado": "registered",
    "registered": "registered",
    "facturado": "ready_invoice",
    "facturada": "ready_invoice",
    "invoiced": "ready_invoice",
    "ready_invoice": "ready_invoice",
    "sin_factura": "no_invoice",
    "no_factura": "no_invoice",
    "no_requiere": "no_invoice",
    "no_invoice": "no_invoice",
    "procesado": "processed",
    "processed": "processed",
    "procesando": "processing",
    "processing": "processing",
    "en_revision": "under_review",
    "under_review": "under_review",
    "manual_review": "manual_review",
    "needs_review": "manual_review",
    "no_aplica": "not_applicable",
    "not_applicable": "not_applicable",
}

_INVOICE_STATUS_TO_INTERNAL = {
    "pending": "pendiente",
    "pending_invoice": "pendiente_factura",
    "waiting_cfdi_match": "esperando_cfdi",
    "ready_invoice": "facturado",
    "registered": "registrada",
    "invoiced": "facturado",
    "no_invoice": "sin_factura",
    "processed": "procesado",
    "processing": "procesando",
    "under_review": "en_revision",
    "manual_review": "manual_review",
    "not_applicable": "no_aplica",
}

_BANK_STATUS_TO_PUBLIC = {
    "pendiente": "pending",
    "pending": "pending",
    "pendiente_bancaria": "pending",
    "pendiente_factura": "pending",
    "pendiente_pago": "pending",
    "pendiente_banco": "pending",
    "por_conciliar": "pending",
    "conciliado_banco": "bank_reconciled",
    "conciliado": "bank_reconciled",
    "reconciliado": "bank_reconciled",
    "bank_reconciled": "bank_reconciled",
    "reconciled": "reconciled",
    "matched": "reconciled",
    "sin_factura": "no_invoice",
    "no_factura": "no_invoice",
    "no_invoice": "no_invoice",
    "pagado": "paid",
    "paid": "paid",
    "advance": "advance",
    "non_reconcilable": "non_reconcilable",
    "manual_review": "manual_review",
}

_BANK_STATUS_TO_INTERNAL = {
    "pending": "pendiente",
    "bank_reconciled": "conciliado_banco",
    "reconciled": "conciliado_banco",
    "no_invoice": "sin_factura",
    "paid": "pagado",
    "advance": "advance",
    "non_reconcilable": "non_reconcilable",
    "manual_review": "manual_review",
}


def to_public_invoice_status(value: Optional[str]) -> Optional[str]:
    normalized = _normalize(value)
    if normalized is None:
        return None
    return _INVOICE_STATUS_TO_PUBLIC.get(normalized, normalized)


def to_internal_invoice_status(value: Optional[str]) -> Optional[str]:
    normalized = _normalize(value)
    if normalized is None:
        return None
    return _INVOICE_STATUS_TO_INTERNAL.get(normalized, normalized)


def to_public_bank_status(value: Optional[str]) -> Optional[str]:
    normalized = _normalize(value)
    if normalized is None:
        return None
    return _BANK_STATUS_TO_PUBLIC.get(normalized, normalized)


def to_internal_bank_status(value: Optional[str]) -> Optional[str]:
    normalized = _normalize(value)
    if normalized is None:
        return None
    return _BANK_STATUS_TO_INTERNAL.get(normalized, normalized)
