"""Endpoints for marking bank transactions as reviewed."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.bank_transactions_models import BankTransaction
from core.unified_auth import get_current_active_user, UserInDB


router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions Review"])


def _get_session() -> Session:
    """Helper to obtain a database session."""
    return SessionLocal()


@router.post("/{transaction_id}/mark_reviewed")
async def mark_transaction_reviewed(
    transaction_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
):
    """Mark a bank transaction as reviewed by the current user."""

    db = _get_session()
    try:
        transaction = db.query(BankTransaction).filter(BankTransaction.id == transaction_id).first()
        if not transaction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

        transaction.review_status = "reviewed"
        transaction.reviewed_by = current_user.id
        transaction.reviewed_at = datetime.utcnow()

        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return {
            "status": "ok",
            "transaction_id": transaction_id,
            "reviewed_by_id": current_user.id,
            "reviewed_by": current_user.email,
            "reviewed_at": transaction.reviewed_at.isoformat() if transaction.reviewed_at else None,
        }
    finally:
        db.close()
