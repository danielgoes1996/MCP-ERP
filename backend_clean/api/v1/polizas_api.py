"""API endpoints for accounting polizas generated from bank reconciliation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from core.database import SessionLocal
from core.accounting_models import PolizaContable
from core.polizas_service import generate_poliza_from_movement
from core.unified_auth import get_current_active_user, UserInDB


router = APIRouter(prefix="/api/v1/polizas", tags=["Polizas Contables"])


class PolizaRequest(BaseModel):
    bank_movement_id: int
    ai_source: Optional[str] = None
    ai_confidence: Optional[float] = None


def _get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/generar_desde_conciliacion")
async def generar_poliza_desde_conciliacion(
    request: PolizaRequest,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        result = generate_poliza_from_movement(
            movement_id=request.bank_movement_id,
            current_user_id=current_user.id,
            ai_source=request.ai_source,
            ai_confidence=request.ai_confidence,
        )
        return {"status": "ok", **result}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/")
async def listar_polizas(limit: int = 100):
    db = SessionLocal()
    try:
        polizas = (
            db.query(PolizaContable)
            .order_by(PolizaContable.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": poliza.id,
                "bank_movement_id": poliza.bank_movement_id,
                "cfdi_uuid": poliza.cfdi_uuid,
                "tipo": poliza.tipo,
                "descripcion": poliza.descripcion,
                "monto_total": poliza.monto_total,
                "iva_total": poliza.iva_total,
                "estatus": poliza.estatus,
                "created_at": poliza.created_at.isoformat() if poliza.created_at else None,
            }
            for poliza in polizas
        ]
    finally:
        db.close()


@router.get("/{poliza_id}")
async def obtener_poliza(poliza_id: int):
    db = SessionLocal()
    try:
        poliza = db.query(PolizaContable).filter(PolizaContable.id == poliza_id).first()
        if not poliza:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Póliza no encontrada")

        detalles = [
            {
                "id": detalle.id,
                "cuenta_contable": detalle.cuenta_contable,
                "descripcion": detalle.descripcion,
                "debe": detalle.debe,
                "haber": detalle.haber,
                "impuesto_tipo": detalle.impuesto_tipo,
                "impuesto_monto": detalle.impuesto_monto,
                "orden": detalle.orden,
            }
            for detalle in poliza.detalles
        ]

        return {
            "id": poliza.id,
            "bank_movement_id": poliza.bank_movement_id,
            "expense_record_id": poliza.expense_record_id,
            "cfdi_uuid": poliza.cfdi_uuid,
            "tipo": poliza.tipo,
            "descripcion": poliza.descripcion,
            "monto_total": poliza.monto_total,
            "iva_total": poliza.iva_total,
            "estatus": poliza.estatus,
            "periodo": poliza.periodo,
            "company_id": poliza.company_id,
            "tenant_id": poliza.tenant_id,
            "ai_source": poliza.ai_source,
            "ai_confidence": poliza.ai_confidence,
            "created_by": poliza.created_by,
            "created_at": poliza.created_at.isoformat() if poliza.created_at else None,
            "detalles": detalles,
        }
    finally:
        db.close()


@router.get("/por-movimiento/{movement_id}")
async def obtener_poliza_por_movimiento(movement_id: int):
    db = SessionLocal()
    try:
        poliza = (
            db.query(PolizaContable)
            .filter(PolizaContable.bank_movement_id == movement_id)
            .order_by(PolizaContable.created_at.desc())
            .first()
        )
        if not poliza:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Póliza no encontrada")
        return {"poliza_id": poliza.id}
    finally:
        db.close()
