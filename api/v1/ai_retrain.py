"""AI retraining endpoints for local feedback and correction memory."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator

from config.config import config
from core.unified_auth import User, get_current_active_user
from core.ai.correction_learning_service import (
    store_correction_feedback,
    aggregate_correction_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Retraining"])


class CorrectionItem(BaseModel):
    description: str = Field(..., min_length=3, description="Original transaction description")
    corrected_category: str = Field(..., min_length=2, description="Desired category after manual correction")
    ai_category: Optional[str] = Field(None, description="Category previously suggested by the AI")
    movement_kind: Optional[str] = Field(None, description="Optional movement kind override")
    amount: Optional[float] = Field(None, description="Amount of the transaction")
    notes: Optional[str] = Field(None, description="Additional feedback from the user")
    model_used: Optional[str] = Field(None, description="Model that generated the original suggestion")
    raw_transaction: Optional[Dict[str, Any]] = Field(None, description="Raw transaction payload for auditing")

    @validator("description")
    def _ensure_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description cannot be empty")
        return value

    @validator("corrected_category")
    def _ensure_category(cls, value: str) -> str:
        return value.strip()


class RetrainRequest(BaseModel):
    company_id: int = Field(..., gt=0, description="Company receiving the correction")
    corrections: List[CorrectionItem] = Field(..., min_items=1, description="List of corrections to ingest")


class RetrainResponse(BaseModel):
    status: str
    stored_examples: int
    stats: Dict[str, Any]


def _get_company_tenant(company_id: int) -> Optional[int]:
    db_path = Path(config.UNIFIED_DB_PATH)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT tenant_id FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
    return int(row["tenant_id"]) if row else None


def _validate_company_access(company_id: int, current_user: User) -> None:
    if getattr(current_user, "is_superuser", False):
        return

    company_tenant = _get_company_tenant(company_id)
    if company_tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if company_tenant != getattr(current_user, "tenant_id", None):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to requested company")


@router.post("/retrain", response_model=RetrainResponse)
async def retrain_from_corrections(
    payload: RetrainRequest,
    current_user: User = Depends(get_current_active_user),
) -> RetrainResponse:
    """Persist manual corrections so future parses reuse the feedback."""

    if not payload.corrections:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No corrections provided")

    _validate_company_access(payload.company_id, current_user)

    stored = 0
    for correction in payload.corrections:
        try:
            store_correction_feedback(
                company_id=payload.company_id,
                tenant_id=getattr(current_user, "tenant_id", None),
                user_id=getattr(current_user, "id", None),
                description=correction.description,
                ai_category=correction.ai_category,
                corrected_category=correction.corrected_category,
                movement_kind=correction.movement_kind,
                amount=correction.amount,
                model_used=correction.model_used,
                notes=correction.notes,
                raw_transaction=correction.raw_transaction,
            )
            stored += 1
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unable to store correction: %s", exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store correction") from exc

    stats = aggregate_correction_stats(payload.company_id)
    logger.info(
        "Retrain feedback ingested for company=%s by user=%s (examples=%s)",
        payload.company_id,
        getattr(current_user, "id", None),
        stored,
    )

    return RetrainResponse(status="success", stored_examples=stored, stats=stats)
