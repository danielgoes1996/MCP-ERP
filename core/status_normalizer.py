"""Helpers to keep status fields consistent between backend and frontend."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, Optional


def _ensure_dict(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _has_ticket(expense: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    return any(
        filter(
            None,
            [
                expense.get("ticket_image_url"),
                expense.get("ticket_folio"),
                expense.get("ticket_file"),
                metadata.get("ticket_file"),
                metadata.get("ticket_url"),
                metadata.get("ticket_folio"),
                metadata.get("has_ticket"),
            ],
        )
    )


def _has_cfdi(expense: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    tax_info = _ensure_dict(expense.get("tax_info")) or _ensure_dict(metadata.get("tax_info"))
    return any(
        filter(
            None,
            [
                expense.get("cfdi_uuid"),
                expense.get("factura_uuid"),
                tax_info.get("uuid"),
                metadata.get("cfdi_uuid"),
                metadata.get("factura_uuid"),
            ],
        )
    )


def _is_closed_without_invoice(expense: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    candidate_values = [
        expense.get("closed_without_invoice"),
        metadata.get("closed_without_invoice"),
        expense.get("workflow_status"),
        expense.get("estado_factura"),
        expense.get("invoice_status"),
    ]
    for value in candidate_values:
        if isinstance(value, str) and value.strip().lower() == "sin_factura":
            return True
        if value is True:
            return True
    return False


# Backend canonicalizes invoice_status here so the UI only maps Spanish labels.
# Backend canonicalizes invoice_status here so the UI only maps Spanish labels.
def normalize_invoice_status(expense: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Normalizes invoice_status for consistency between backend and UI.
    Ensures that the state reflects real document availability.
    """
    meta = _ensure_dict(metadata or expense.get("metadata") or {})

    if _is_closed_without_invoice(expense, meta):
        return "sin_factura"

    if _has_cfdi(expense, meta):
        return "ready_invoice"

    if _has_ticket(expense, meta):
        return "waiting_cfdi_match"

    return "pending_invoice"


def update_invoice_status(
    expense_payload: Dict[str, Any],
    metadata: Optional[Dict[str, Any]],
    new_status: str,
) -> Dict[str, Any]:
    """Persist invoice_status transitions for auditability."""

    meta = dict(metadata or {})
    log = list(meta.get("status_change_log") or [])

    old_status = expense_payload.get("invoice_status") or meta.get("last_invoice_status")
    if old_status != new_status:
        log.append(
            {
                "from": old_status,
                "to": new_status,
                "at": datetime.utcnow().isoformat(),
            }
        )

    meta["status_change_log"] = log
    meta["last_invoice_status"] = new_status
    return meta
