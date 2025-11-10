"""Service layer for generating accounting polizas from bank reconciliation."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import text

from core.accounting.accounting_models import PolizaContable, PolizaDetalle
from core.accounting.accounting_rules import generate_accounting_entries
from core.database import SessionLocal
from core.internal_db import get_sqlite_connection


def _fetch_bank_movement(movement_id: int) -> Optional[Dict[str, Any]]:
    with get_sqlite_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM bank_movements WHERE id = ?",
            (movement_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def _fetch_expense(expense_id: int) -> Optional[Dict[str, Any]]:
    with get_sqlite_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM expense_records WHERE id = ?",
            (expense_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        record = dict(row)
        metadata_raw = record.get("metadata")
        if metadata_raw:
            try:
                record["metadata_dict"] = json.loads(metadata_raw)
            except json.JSONDecodeError:
                record["metadata_dict"] = {}
        else:
            record["metadata_dict"] = {}
        return record


def _fetch_invoice_by_uuid(cfdi_uuid: str) -> Optional[Dict[str, Any]]:
    if not cfdi_uuid:
        return None
    with get_sqlite_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM expense_invoices WHERE uuid = ?",
            (cfdi_uuid,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def _fetch_match_links(movement_id: int) -> List[Dict[str, Any]]:
    with get_sqlite_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, bank_movement_id, expense_id, cfdi_uuid, monto_asignado, score, source, explanation, created_at
              FROM bank_match_links
             WHERE bank_movement_id = ?
             ORDER BY datetime(created_at) ASC
            """,
            (movement_id,),
        )
        rows = cursor.fetchall() or []
        return [dict(row) for row in rows]


def _ensure_session(db: Optional[Session] = None) -> Session:
    return db or SessionLocal()


def generate_poliza_from_movement(
    movement_id: int,
    *,
    current_user_id: Optional[int] = None,
    ai_source: Optional[str] = None,
    ai_confidence: Optional[float] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Generate a poliza for a reconciled bank movement."""

    movement = _fetch_bank_movement(movement_id)
    if not movement:
        raise ValueError("Movimiento bancario no encontrado")

    match_links = _fetch_match_links(movement_id)
    linked_expense_ids = [link.get("expense_id") for link in match_links if link.get("expense_id")]
    expense_id = (linked_expense_ids[0] if linked_expense_ids else None) or movement.get("matched_expense_id") or movement.get("expense_record_id")
    expense = _fetch_expense(expense_id) if expense_id else None

    raw_amount = movement.get("amount")
    try:
        movement_amount = float(raw_amount) if raw_amount is not None else 0.0
    except (TypeError, ValueError):
        movement_amount = 0.0

    if match_links:
        try:
            allocated_total = sum(float(link.get("monto_asignado") or 0.0) for link in match_links)
            if allocated_total > 0:
                movement_amount = allocated_total
        except (TypeError, ValueError):
            pass

    cfdi_uuid = None
    for link in match_links:
        if link.get("cfdi_uuid"):
            cfdi_uuid = link["cfdi_uuid"]
            break
    if not cfdi_uuid:
        cfdi_uuid = movement.get("cfdi_uuid") or (expense.get("cfdi_uuid") if expense else None)

    invoice = _fetch_invoice_by_uuid(cfdi_uuid)

    if not expense:
        # Construir gasto sintético basado en movimiento si no hay expense_record vinculado
        expense = {
            "id": None,
            "description": movement.get("description"),
            "amount": movement_amount,
            "expense_date": movement.get("date") or movement.get("created_at"),
            "tax_metadata": {},
            "metadata_dict": {},
            "category": movement.get("category_manual") or movement.get("category_auto") or "otros",
            "paid_by": "company_account",
            "will_have_cfdi": bool(cfdi_uuid),
            "bank_status": movement.get("processing_status"),
            "invoice_status": "registrada" if cfdi_uuid else None,
            "total_paid": abs(movement_amount),
        }

    if invoice:
        expense.setdefault("metadata_dict", {})
        expense["metadata_dict"]["invoice"] = invoice
        expense["cfdi_uuid"] = invoice.get("uuid")
        expense["subtotal"] = invoice.get("subtotal")
        expense["iva"] = invoice.get("iva_amount")
        expense["total"] = invoice.get("total")

    if match_links:
        expense.setdefault("metadata_dict", {})
        expense["metadata_dict"]["bank_match_links"] = match_links

    session = _ensure_session(db)

    existing = (
        session.query(PolizaContable)
        .filter(PolizaContable.bank_movement_id == movement_id)
        .order_by(PolizaContable.created_at.desc())
        .first()
    )
    if existing:
        result = {
            "poliza_id": existing.id,
            "bank_movement_id": movement_id,
            "cfdi_uuid": existing.cfdi_uuid,
            "tipo": existing.tipo,
            "descripcion": existing.descripcion,
            "monto_total": existing.monto_total,
            "iva_total": existing.iva_total,
            "estatus": existing.estatus,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
            "movimientos": [
                {
                    "cuenta_contable": detalle.cuenta_contable,
                    "descripcion": detalle.descripcion,
                    "debe": detalle.debe,
                    "haber": detalle.haber,
                    "orden": detalle.orden,
                }
                for detalle in existing.detalles
            ],
        }
        if db is None:
            session.close()
        return result

    if match_links:
        payments = [
            {
                "amount": abs(float(link.get("monto_asignado") or 0.0)),
                "payment_date": movement.get("date"),
                "payment_method": movement.get("payment_method") or link.get("source"),
            }
            for link in match_links
            if (link.get("monto_asignado") is not None)
        ]
        if not payments:
            payments = [
                {
                    "amount": abs(movement_amount),
                    "payment_date": movement.get("date"),
                    "payment_method": movement.get("payment_method"),
                }
            ]
    else:
        payments = [
            {
                "amount": abs(movement_amount),
                "payment_date": movement.get("date"),
                "payment_method": movement.get("payment_method"),
            }
        ]

    poliza_payload = generate_accounting_entries(expense, payments)

    try:
        poliza = PolizaContable(
            bank_movement_id=movement_id,
            expense_record_id=expense.get("id"),
            cfdi_uuid=cfdi_uuid,
            tipo=poliza_payload.get("tipo_poliza") or "Egreso",
            descripcion=poliza_payload.get("concepto"),
            monto_total=float(poliza_payload.get("total_debe") or 0),
            iva_total=float(expense.get("iva") or 0),
            estatus="generada",
            periodo=poliza_payload.get("fecha_asiento"),
            company_id=movement.get("company_id"),
            tenant_id=movement.get("tenant_id"),
            ai_source=ai_source,
            ai_confidence=ai_confidence,
            created_by=current_user_id,
            created_at=datetime.utcnow(),
        )

        for idx, detalle in enumerate(poliza_payload.get("movimientos", []), start=1):
            detalle_poliza = PolizaDetalle(
                cuenta_contable=detalle.get("cuenta"),
                descripcion=detalle.get("descripcion"),
                debe=float(detalle.get("debe") or 0),
                haber=float(detalle.get("haber") or 0),
                impuesto_tipo=None,
                impuesto_monto=0,
                orden=idx,
            )
            poliza.detalles.append(detalle_poliza)

        session.add(poliza)
        session.flush()

        # update bank movement linking
        session.execute(
            text("UPDATE bank_movements SET generated_poliza_id = :poliza_id, cfdi_uuid = COALESCE(cfdi_uuid, :cfdi_uuid) WHERE id = :movement_id"),
            {"poliza_id": poliza.id, "cfdi_uuid": cfdi_uuid, "movement_id": movement_id},
        )

        session.commit()

        response = {
            "poliza_id": poliza.id,
            "bank_movement_id": movement_id,
            "cfdi_uuid": cfdi_uuid,
            "tipo": poliza.tipo,
            "descripcion": poliza.descripcion,
            "monto_total": poliza.monto_total,
            "iva_total": poliza.iva_total,
            "estatus": poliza.estatus,
            "created_at": poliza.created_at.isoformat(),
            "movimientos": [
                {
                    "cuenta_contable": detalle.cuenta_contable,
                    "descripcion": detalle.descripcion,
                    "debe": detalle.debe,
                    "haber": detalle.haber,
                    "orden": detalle.orden,
                }
                for detalle in poliza.detalles
            ],
        }
        return response
    except Exception:
        session.rollback()
        raise
    finally:
        if db is None:
            session.close()
