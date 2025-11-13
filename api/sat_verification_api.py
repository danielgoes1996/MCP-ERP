"""
SAT Verification API
====================
API endpoints for validating CFDIs against SAT web services

Endpoints:
- POST /api/sat/validate/{session_id} - Validate a single invoice
- POST /api/sat/batch-validate - Batch validate pending invoices
- GET /api/sat/validation-stats - Get validation statistics
- POST /api/sat/revalidate - Re-validate old validations
- GET /api/sat/verification-history/{session_id} - Get verification history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from core.db_postgresql import get_db
from core.auth.jwt import get_current_user_email
from core.sat.sat_validation_service import (
    SATValidationService,
    validate_single_invoice,
    batch_validate_company_invoices
)
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sat", tags=["SAT Verification"])


# ========================================
# Request/Response Models
# ========================================

class ValidationRequest(BaseModel):
    """Request to validate a single invoice"""
    session_id: str = Field(..., description="Universal invoice session ID")
    force_refresh: bool = Field(False, description="Force re-validation even if already validated")


class BatchValidationRequest(BaseModel):
    """Request to batch validate invoices"""
    company_id: str = Field(..., description="Company ID")
    limit: int = Field(100, ge=1, le=500, description="Maximum number of invoices to validate")
    max_age_hours: int = Field(24, ge=1, le=720, description="Only validate invoices newer than this many hours")
    use_mock: bool = Field(False, description="Use mock SAT responses for testing")


class RevalidationRequest(BaseModel):
    """Request to re-validate old validations"""
    company_id: str = Field(..., description="Company ID")
    days_old: int = Field(30, ge=1, le=365, description="Re-validate if last check was this many days ago")
    limit: int = Field(50, ge=1, le=200, description="Maximum number to re-validate")


class ValidationResponse(BaseModel):
    """Response for validation request"""
    success: bool
    session_id: str
    validation_info: Optional[Dict] = None
    error: Optional[str] = None


class BatchValidationResponse(BaseModel):
    """Response for batch validation"""
    success: bool
    summary: Dict
    message: str


class ValidationStatsResponse(BaseModel):
    """Response for validation statistics"""
    company_id: str
    stats: Dict
    timestamp: datetime


class VerificationHistoryResponse(BaseModel):
    """Response for verification history"""
    session_id: str
    history: List[Dict]
    total_verifications: int


# ========================================
# Endpoints
# ========================================

@router.post("/validate/{session_id}", response_model=ValidationResponse)
async def validate_invoice(
    session_id: str,
    force_refresh: bool = False,
    use_mock: bool = False,
    current_user: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """
    Validate a single invoice against SAT

    This endpoint:
    1. Fetches invoice data from universal_invoice_sessions
    2. Extracts UUID, RFCs, and total from extracted_data
    3. Calls SAT web service to verify status
    4. Updates session with SAT validation results
    5. Records verification in history table

    Args:
        session_id: Universal invoice session ID
        force_refresh: If True, re-validate even if already validated
        use_mock: If True, use mock SAT responses for testing
    """
    try:
        logger.info(f"User {current_user} validating invoice {session_id}")

        # Validate invoice
        success, validation_info, error = validate_single_invoice(
            db=db,
            session_id=session_id,
            use_mock=use_mock,
            force_refresh=force_refresh
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error or "Validation failed"
            )

        return ValidationResponse(
            success=True,
            session_id=session_id,
            validation_info=validation_info,
            error=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in validate_invoice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/batch-validate", response_model=BatchValidationResponse)
async def batch_validate(
    request: BatchValidationRequest,
    current_user: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """
    Batch validate pending invoices for a company

    This endpoint:
    1. Finds all pending validations for the company
    2. Validates each one sequentially
    3. Returns summary of results

    Useful for:
    - Initial setup (validate all existing invoices)
    - Periodic validation jobs
    - Catching up after downtime

    Args:
        request: Batch validation request with company_id, limit, and options
    """
    try:
        logger.info(f"User {current_user} batch validating for company {request.company_id}")

        # Create service
        service = SATValidationService(db, use_mock=request.use_mock)

        # Batch validate
        summary = service.batch_validate_pending(
            company_id=request.company_id,
            limit=request.limit,
            max_age_hours=request.max_age_hours
        )

        message = f"Validated {summary['successful']}/{summary['total']} invoices"

        return BatchValidationResponse(
            success=True,
            summary=summary,
            message=message
        )

    except Exception as e:
        logger.error(f"Error in batch_validate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/validation-stats/{company_id}", response_model=ValidationStatsResponse)
async def get_validation_stats(
    company_id: str,
    current_user: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """
    Get SAT validation statistics for a company

    Returns breakdown by status:
    - total: Total invoices with extraction completed
    - pending: Not yet validated
    - vigente: SAT confirmed vigente
    - cancelado: SAT confirmed cancelado
    - sustituido: SAT confirmed sustituido
    - por_cancelar: SAT confirmed por_cancelar
    - no_encontrado: SAT says not found
    - error: Error during verification

    Args:
        company_id: Company ID
    """
    try:
        service = SATValidationService(db)
        stats = service.get_validation_stats(company_id)

        return ValidationStatsResponse(
            company_id=company_id,
            stats=stats,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error in get_validation_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/revalidate", response_model=BatchValidationResponse)
async def revalidate_old(
    request: RevalidationRequest,
    current_user: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """
    Re-validate invoices that were validated long ago

    This is useful for:
    - Checking if vigente invoices have been canceled
    - Verifying por_cancelar invoices have been fully canceled
    - Periodic auditing of SAT status

    Only re-validates invoices with status 'vigente' or 'por_cancelar'
    that were last validated more than X days ago.

    Args:
        request: Re-validation request with company_id, days_old, limit
    """
    try:
        logger.info(f"User {current_user} re-validating old invoices for company {request.company_id}")

        service = SATValidationService(db)
        summary = service.revalidate_old_validations(
            company_id=request.company_id,
            days_old=request.days_old,
            limit=request.limit
        )

        if summary['changed'] > 0:
            message = f"Re-validated {summary['total']} invoices: {summary['changed']} changed, {summary['unchanged']} unchanged"
        else:
            message = f"Re-validated {summary['total']} invoices: all statuses unchanged"

        return BatchValidationResponse(
            success=True,
            summary=summary,
            message=message
        )

    except Exception as e:
        logger.error(f"Error in revalidate_old: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/verification-history/{session_id}", response_model=VerificationHistoryResponse)
async def get_verification_history(
    session_id: str,
    current_user: str = Depends(get_current_user_email),
    db: Session = Depends(get_db)
):
    """
    Get verification history for an invoice session

    Shows all SAT verification attempts for this invoice,
    including status changes over time.

    Useful for:
    - Auditing status changes
    - Debugging validation issues
    - Compliance reporting

    Args:
        session_id: Universal invoice session ID
    """
    try:
        query = text("""
            SELECT
                id,
                uuid,
                rfc_emisor,
                rfc_receptor,
                total,
                status,
                codigo_estatus,
                es_cancelable,
                estado,
                validacion_efos,
                verification_url,
                error_message,
                is_retry,
                retry_count,
                verified_at
            FROM sat_verification_history
            WHERE session_id = :session_id
            ORDER BY verified_at DESC
        """)

        results = db.execute(query, {"session_id": session_id}).fetchall()

        history = []
        for row in results:
            history.append({
                'id': row[0],
                'uuid': row[1],
                'rfc_emisor': row[2],
                'rfc_receptor': row[3],
                'total': float(row[4]) if row[4] else None,
                'status': row[5],
                'codigo_estatus': row[6],
                'es_cancelable': row[7],
                'estado': row[8],
                'validacion_efos': row[9],
                'verification_url': row[10],
                'error_message': row[11],
                'is_retry': row[12],
                'retry_count': row[13],
                'verified_at': row[14].isoformat() if row[14] else None
            })

        return VerificationHistoryResponse(
            session_id=session_id,
            history=history,
            total_verifications=len(history)
        )

    except Exception as e:
        logger.error(f"Error in get_verification_history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
