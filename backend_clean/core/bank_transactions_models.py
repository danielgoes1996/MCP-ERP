"""SQLAlchemy models for bank transactions/movements."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from core.database import Base


class BankTransaction(Base):
    """Minimal SQLAlchemy model mapping bank_movements table."""

    __tablename__ = "bank_movements"

    id: int = Column(Integer, primary_key=True, index=True)
    review_status: str = Column(String, nullable=False, default="pending")
    reviewed_by: Optional[int] = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Optional[datetime] = Column(DateTime, nullable=True)


__all__ = ["BankTransaction"]

