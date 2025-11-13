"""
API endpoints for invoice accounting classification
Provides endpoints for confirming, correcting, and querying AI-generated classifications
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import json

from core.error_handler import handle_error, log_endpoint_entry, log_endpoint_success, log_endpoint_error

router = APIRouter(prefix="/invoice-classification", tags=["Invoice Classification"])
logger = logging.getLogger(__name__)


def _get_db_connection():
    """Get PostgreSQL connection using environment variables"""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import os

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
        port=int(os.getenv('POSTGRES_PORT', '5433')),
        database=os.getenv('POSTGRES_DB', 'mcp_system'),
        user=os.getenv('POSTGRES_USER', 'mcp_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'changeme')
    )
    conn.cursor_factory = RealDictCursor
    return conn


@router.post("/confirm/{session_id}")
async def confirm_classification(
    session_id: str,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Confirm an AI-generated classification as correct

    This marks the classification as 'confirmed' and the accountant accepts it.
    The confirmation is stored for future learning.
    """
    log_endpoint_entry(f"/invoice-classification/confirm/{session_id}", method="POST", user_id=user_id)

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # 1. Get current classification
        cursor.execute("""
            SELECT id, accounting_classification
            FROM universal_invoice_sessions
            WHERE id = %s
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Invoice session {session_id} not found")

        classification = row['accounting_classification']

        if not classification:
            raise HTTPException(status_code=400, detail="No classification found for this invoice")

        if classification.get('status') not in ['pending_confirmation', 'corrected']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot confirm classification with status: {classification.get('status')}"
            )

        # 2. Update status to 'confirmed'
        classification['status'] = 'confirmed'
        classification['confirmed_at'] = datetime.utcnow().isoformat()
        classification['confirmed_by'] = user_id or 'unknown'

        cursor.execute("""
            UPDATE universal_invoice_sessions
            SET accounting_classification = %s
            WHERE id = %s
        """, (json.dumps(classification), session_id))

        conn.commit()

        logger.info(f"Session {session_id}: Classification confirmed by {user_id or 'unknown'}")

        response = {
            "session_id": session_id,
            "status": "confirmed",
            "sat_account_code": classification.get('sat_account_code'),
            "confirmed_at": classification['confirmed_at'],
            "confirmed_by": classification['confirmed_by']
        }

        log_endpoint_success(f"/invoice-classification/confirm/{session_id}", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error confirming classification: {str(e)}"
        log_endpoint_error(f"/invoice-classification/confirm/{session_id}", error_msg)
        logger.error(f"Session {session_id}: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if 'conn' in locals():
            conn.close()


@router.post("/correct/{session_id}")
async def correct_classification(
    session_id: str,
    corrected_sat_code: str,
    correction_notes: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Correct an AI-generated classification

    This allows the accountant to override the AI's suggestion with the correct
    SAT account code. The correction is stored for future learning.
    """
    log_endpoint_entry(
        f"/invoice-classification/correct/{session_id}",
        method="POST",
        corrected_sat_code=corrected_sat_code,
        user_id=user_id
    )

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # 1. Get current classification and parsed_data
        cursor.execute("""
            SELECT id, accounting_classification, parsed_data, company_id
            FROM universal_invoice_sessions
            WHERE id = %s
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Invoice session {session_id} not found")

        classification = row['accounting_classification'] or {}
        parsed_data = row['parsed_data'] or {}
        company_id = row['company_id']

        # 2. Store original classification if this is first correction
        if 'original_sat_code' not in classification:
            classification['original_sat_code'] = classification.get('sat_account_code')
            classification['original_confidence'] = classification.get('confidence_sat')

        # 3. Update classification with correction
        classification['status'] = 'corrected'
        classification['corrected_at'] = datetime.utcnow().isoformat()
        classification['corrected_by'] = user_id or 'unknown'
        classification['corrected_sat_code'] = corrected_sat_code
        classification['correction_notes'] = correction_notes

        cursor.execute("""
            UPDATE universal_invoice_sessions
            SET accounting_classification = %s
            WHERE id = %s
        """, (json.dumps(classification), session_id))

        # 4. TODO (v2): Save to ai_correction_memory for learning
        # This will be implemented when we add the learning loop
        # For now, just log the correction

        conn.commit()

        logger.info(
            f"Session {session_id}: Classification corrected from "
            f"{classification.get('sat_account_code')} to {corrected_sat_code} by {user_id or 'unknown'}"
        )

        response = {
            "session_id": session_id,
            "status": "corrected",
            "original_sat_code": classification.get('original_sat_code'),
            "corrected_sat_code": corrected_sat_code,
            "corrected_at": classification['corrected_at'],
            "corrected_by": classification['corrected_by'],
            "correction_notes": correction_notes
        }

        log_endpoint_success(f"/invoice-classification/correct/{session_id}", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error correcting classification: {str(e)}"
        log_endpoint_error(f"/invoice-classification/correct/{session_id}", error_msg)
        logger.error(f"Session {session_id}: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/pending")
async def get_pending_classifications(
    company_id: str,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Get list of invoices with pending classifications for a company

    Returns invoices that need accountant review (status = 'pending_confirmation')
    """
    log_endpoint_entry(
        "/invoice-classification/pending",
        method="GET",
        company_id=company_id,
        limit=limit,
        offset=offset
    )

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Get total count
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM universal_invoice_sessions
            WHERE company_id = %s
            AND accounting_classification->>'status' = 'pending_confirmation'
        """, (company_id,))

        total = cursor.fetchone()['total']

        # Get paginated results
        cursor.execute("""
            SELECT
                id,
                original_filename,
                created_at,
                accounting_classification->>'sat_account_code' as sat_code,
                accounting_classification->>'family_code' as family_code,
                accounting_classification->>'confidence_sat' as confidence,
                accounting_classification->>'explanation_short' as explanation,
                parsed_data->>'total' as invoice_total,
                parsed_data->>'emisor' as emisor,
                parsed_data->'conceptos'->0->>'descripcion' as first_concept_description
            FROM universal_invoice_sessions
            WHERE company_id = %s
            AND accounting_classification->>'status' = 'pending_confirmation'
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (company_id, limit, offset))

        invoices = []
        for row in cursor.fetchall():
            invoices.append({
                "session_id": row['id'],
                "filename": row['original_filename'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "sat_code": row['sat_code'],
                "family_code": row['family_code'],
                "confidence": float(row['confidence']) if row['confidence'] else None,
                "explanation": row['explanation'],
                "invoice_total": float(row['invoice_total']) if row['invoice_total'] else None,
                "provider": json.loads(row['emisor']) if row['emisor'] else {},
                "description": row['first_concept_description']
            })

        response = {
            "company_id": company_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "invoices": invoices
        }

        log_endpoint_success("/invoice-classification/pending", response)
        return response

    except Exception as e:
        error_msg = f"Error fetching pending classifications: {str(e)}"
        log_endpoint_error("/invoice-classification/pending", error_msg)
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/stats/{company_id}")
async def get_classification_stats(
    company_id: str,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get classification statistics for a company

    Returns metrics about AI classification performance
    """
    log_endpoint_entry(
        f"/invoice-classification/stats/{company_id}",
        method="GET",
        days=days
    )

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Get stats for last N days
        cursor.execute("""
            SELECT
                COUNT(*) as total_invoices,
                COUNT(*) FILTER (WHERE accounting_classification IS NOT NULL) as classified,
                COUNT(*) FILTER (WHERE accounting_classification->>'status' = 'pending_confirmation') as pending,
                COUNT(*) FILTER (WHERE accounting_classification->>'status' = 'confirmed') as confirmed,
                COUNT(*) FILTER (WHERE accounting_classification->>'status' = 'corrected') as corrected,
                COUNT(*) FILTER (WHERE accounting_classification->>'status' = 'not_classified') as not_classified,
                AVG((accounting_classification->>'confidence_sat')::float) as avg_confidence,
                AVG((processing_metrics->'accounting_classification'->>'classification_duration_ms')::float) as avg_duration_ms
            FROM universal_invoice_sessions
            WHERE company_id = %s
            AND created_at >= NOW() - INTERVAL '%s days'
        """, (company_id, days))

        stats = cursor.fetchone()

        # Calculate percentages
        total = stats['total_invoices'] or 0
        classified = stats['classified'] or 0

        response = {
            "company_id": company_id,
            "period_days": days,
            "total_invoices": total,
            "classified": classified,
            "pending_confirmation": stats['pending'] or 0,
            "confirmed": stats['confirmed'] or 0,
            "corrected": stats['corrected'] or 0,
            "not_classified": stats['not_classified'] or 0,
            "classification_rate": round((classified / total * 100) if total > 0 else 0, 2),
            "confirmation_rate": round((stats['confirmed'] / classified * 100) if classified > 0 else 0, 2),
            "correction_rate": round((stats['corrected'] / classified * 100) if classified > 0 else 0, 2),
            "avg_confidence": round(float(stats['avg_confidence']), 3) if stats['avg_confidence'] else None,
            "avg_duration_seconds": round(float(stats['avg_duration_ms']) / 1000, 2) if stats['avg_duration_ms'] else None
        }

        log_endpoint_success(f"/invoice-classification/stats/{company_id}", response)
        return response

    except Exception as e:
        error_msg = f"Error fetching classification stats: {str(e)}"
        log_endpoint_error(f"/invoice-classification/stats/{company_id}", error_msg)
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/detail/{session_id}")
async def get_classification_detail(
    session_id: str
) -> Dict[str, Any]:
    """
    Get detailed classification information for a specific invoice

    Returns full classification data including parsed invoice info
    """
    log_endpoint_entry(
        f"/invoice-classification/detail/{session_id}",
        method="GET"
    )

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                company_id,
                original_filename,
                created_at,
                accounting_classification,
                parsed_data,
                processing_metrics
            FROM universal_invoice_sessions
            WHERE id = %s
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Invoice session {session_id} not found")

        classification = row['accounting_classification'] or {}
        parsed_data = row['parsed_data'] or {}
        metrics = row['processing_metrics'] or {}

        response = {
            "session_id": row['id'],
            "company_id": row['company_id'],
            "filename": row['original_filename'],
            "created_at": row['created_at'].isoformat() if row['created_at'] else None,
            "classification": classification,
            "invoice_data": {
                "tipo_comprobante": parsed_data.get('tipo_comprobante'),
                "total": parsed_data.get('total'),
                "fecha_emision": parsed_data.get('fecha_emision'),
                "emisor": parsed_data.get('emisor'),
                "receptor": parsed_data.get('receptor'),
                "conceptos": parsed_data.get('conceptos', [])
            },
            "metrics": metrics.get('accounting_classification', {})
        }

        log_endpoint_success(f"/invoice-classification/detail/{session_id}", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error fetching classification detail: {str(e)}"
        log_endpoint_error(f"/invoice-classification/detail/{session_id}", error_msg)
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        if 'conn' in locals():
            conn.close()
