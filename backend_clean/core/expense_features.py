"""Helpers to build normalized feature snapshots for expenses."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from core.text_normalizer import normalize_expense_text


AMOUNT_BUCKETS = [
    (0, 100),
    (100, 250),
    (250, 500),
    (500, 1000),
    (1000, 2500),
    (2500, 5000),
    (5000, 10000),
]


def _amount_bucket(amount: Optional[float]) -> str:
    if amount is None or math.isnan(amount):
        return "unknown"
    abs_amount = abs(amount)
    for low, high in AMOUNT_BUCKETS:
        if low <= abs_amount < high:
            return f"{low}-{high}"
    if abs_amount >= AMOUNT_BUCKETS[-1][1]:
        return f"{AMOUNT_BUCKETS[-1][1]}+"
    return "unknown"


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def build_expense_feature_snapshot(expense_row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized dictionary with the most relevant expense features."""

    descripcion = _safe_str(
        expense_row.get("descripcion_contable")
        or expense_row.get("descripcion")
        or expense_row.get("description")
    )
    categoria_slug = _safe_str(expense_row.get("categoria_slug"))
    categoria_usuario = _safe_str(expense_row.get("categoria"))
    categoria_contable = _safe_str(expense_row.get("categoria_contable"))
    provider_name = _safe_str(
        (expense_row.get("proveedor") or {}).get("nombre")
        if isinstance(expense_row.get("proveedor"), dict)
        else expense_row.get("proveedor_nombre")
        or expense_row.get("provider_name")
    )
    provider_rfc = _safe_str(
        (expense_row.get("proveedor") or {}).get("rfc")
        if isinstance(expense_row.get("proveedor"), dict)
        else expense_row.get("rfc_proveedor")
        or expense_row.get("provider_rfc")
        or expense_row.get("rfc")
    )
    amount = expense_row.get("monto_total") or expense_row.get("amount")
    try:
        amount_value = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount_value = None

    snapshot = {
        "descripcion_original": descripcion,
        "descripcion_normalizada": normalize_expense_text(descripcion or ""),
        "categoria_slug": categoria_slug,
        "categoria_usuario": categoria_usuario,
        "categoria_contable": categoria_contable,
        "provider_name": provider_name,
        "provider_rfc": provider_rfc,
        "payment_method": _safe_str(expense_row.get("forma_pago") or expense_row.get("metodo_pago") or expense_row.get("payment_method")),
        "bank_status": _safe_str(expense_row.get("estado_conciliacion") or expense_row.get("bank_status")),
        "invoice_status": _safe_str(expense_row.get("estado_factura") or expense_row.get("invoice_status")),
        "tenant_id": expense_row.get("tenant_id"),
        "company_id": expense_row.get("company_id"),
        "amount": amount_value,
        "amount_bucket": _amount_bucket(amount_value),
        "existing_sat_account_code": _safe_str(expense_row.get("sat_account_code")),
        "metadata": expense_row.get("metadata") if isinstance(expense_row.get("metadata"), dict) else None,
    }

    keywords = snapshot["descripcion_normalizada"].split()
    if provider_name:
        keywords.extend(normalize_expense_text(provider_name).split())
    if categoria_usuario:
        keywords.extend(normalize_expense_text(categoria_usuario).split())
    snapshot["keywords"] = sorted(set(filter(None, keywords)))

    return snapshot

