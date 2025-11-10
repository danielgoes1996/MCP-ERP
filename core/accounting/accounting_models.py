"""SQLAlchemy models for accounting entries and journal polizas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from core.database import Base


class PolizaContable(Base):
    """Accounting journal entry generated from bank reconciliation."""

    __tablename__ = "polizas_contables"

    id = Column(Integer, primary_key=True, index=True)
    bank_movement_id = Column(Integer, ForeignKey("bank_movements.id", ondelete="SET NULL"))
    expense_record_id = Column(Integer, ForeignKey("expense_records.id", ondelete="SET NULL"))
    cfdi_uuid = Column(String, index=True)
    tipo = Column(String, nullable=False, default="Egreso")
    descripcion = Column(Text)
    monto_total = Column(Float, default=0.0)
    iva_total = Column(Float, default=0.0)
    estatus = Column(String, nullable=False, default="generada")
    periodo = Column(String)
    company_id = Column(Integer)
    tenant_id = Column(Integer)
    ai_source = Column(String)
    ai_confidence = Column(Float)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow)

    detalles = relationship("PolizaDetalle", back_populates="poliza", cascade="all, delete-orphan")


class PolizaDetalle(Base):
    """Detail line (debit/credit) inside a journal entry."""

    __tablename__ = "polizas_detalle"

    id = Column(Integer, primary_key=True, index=True)
    poliza_id = Column(Integer, ForeignKey("polizas_contables.id", ondelete="CASCADE"), nullable=False, index=True)
    cuenta_contable = Column(String, nullable=False)
    descripcion = Column(Text)
    debe = Column(Float, default=0.0)
    haber = Column(Float, default=0.0)
    impuesto_tipo = Column(String)
    impuesto_monto = Column(Float, default=0.0)
    orden = Column(Integer, default=0)

    poliza = relationship("PolizaContable", back_populates="detalles")


__all__ = ["PolizaContable", "PolizaDetalle"]

