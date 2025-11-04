"""
API endpoints for completing expense placeholders created from bulk invoices.

This handles the popup flow when invoices create incomplete expense placeholders
that require user input to complete missing required fields.
"""
from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import json
import sqlite3
import time

from core.expense_validation import expense_validator
from core.structured_logger import (
    get_structured_logger,
    set_request_context,
    log_expense_action,
    log_validation_error,
    log_api_request
)

logger = get_structured_logger(__name__)
router = APIRouter(prefix="/api/expenses/placeholder-completion", tags=["Expense Placeholder Completion"])


class PendingExpenseResponse(BaseModel):
    """Response model for pending expense placeholders."""
    expense_id: int
    description: str
    amount: float
    expense_date: str
    provider_name: Optional[str]
    missing_fields_count: int
    invoice_uuid: Optional[str]
    created_at: str


class CompletionPromptResponse(BaseModel):
    """Response model for completion prompt data."""
    expense_id: int
    needs_completion: bool
    missing_fields: List[Dict[str, Any]]
    prefilled_data: Dict[str, Any]
    invoice_reference: Optional[Dict[str, Any]]


class UpdateExpenseRequest(BaseModel):
    """Request to update an expense with completed fields."""
    expense_id: int = Field(..., description="ID of the expense to update")
    completed_fields: Dict[str, Any] = Field(..., description="Fields with completed values")
    company_id: str = Field(default="default", description="Company ID")


class CompletionStatsResponse(BaseModel):
    """Statistics about incomplete expenses."""
    total_pending: int
    total_amount_pending: float
    oldest_pending_date: Optional[str]
    by_category: Dict[str, int]


class DetailedStatsResponse(BaseModel):
    """Detailed KPIs for expense placeholder completion system."""
    # Overview metrics
    total_pending: int
    total_amount_pending: float
    total_completed_today: int
    total_completed_this_week: int

    # Completion rate KPI
    completion_rate: float  # Percentage of placeholders completed within 24h
    average_time_to_complete_hours: Optional[float]  # Average hours from creation to completion

    # Missing fields analysis
    top_missing_fields: List[Dict[str, Any]]  # [{field: str, count: int, percentage: float}]

    # Time-based breakdown
    pending_by_age: Dict[str, int]  # {"<24h": X, "24-48h": Y, "48h-7d": Z, ">7d": W}

    # Category breakdown
    pending_by_category: Dict[str, int]

    # Health metrics
    oldest_pending_hours: Optional[float]
    at_risk_count: int  # Placeholders older than 48 hours


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect('data/mcp_internal.db')


@router.get("/pending", response_model=List[PendingExpenseResponse])
async def get_pending_expenses(
    company_id: str = "default",
    limit: int = 100
):
    """
    Get list of expense placeholders that require completion.

    Returns expenses with workflow_status='requiere_completar'.
    """
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
        SELECT
            id, description, amount, expense_date,
            provider_name, invoice_uuid, metadata, created_at
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """

        cursor.execute(query, (company_id, limit))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            # Parse metadata to get missing fields count
            metadata = {}
            missing_count = 0

            if row['metadata']:
                try:
                    metadata = json.loads(row['metadata'])
                    missing_count = len(metadata.get('missing_fields', []))
                except:
                    pass

            results.append(PendingExpenseResponse(
                expense_id=row['id'],
                description=row['description'] or '',
                amount=row['amount'] or 0.0,
                expense_date=row['expense_date'] or '',
                provider_name=row['provider_name'],
                missing_fields_count=missing_count,
                invoice_uuid=row['invoice_uuid'],
                created_at=row['created_at'] or ''
            ))

        conn.close()
        return results

    except Exception as e:
        logger.error(f"Error getting pending expenses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompt/{expense_id}", response_model=CompletionPromptResponse)
async def get_completion_prompt(expense_id: int):
    """
    Get completion prompt data for a specific expense.

    This returns the data structure needed to show the completion popup,
    including missing fields, prefilled data, and invoice reference.
    """
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get expense record
        query = """
        SELECT
            id, description, amount, expense_date, category,
            provider_name, provider_rfc, payment_account_id,
            invoice_uuid, metadata, workflow_status
        FROM expense_records
        WHERE id = ?
        """

        cursor.execute(query, (expense_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")

        # Parse metadata to get completion_prompt
        metadata = {}
        completion_prompt = None

        if row['metadata']:
            try:
                metadata = json.loads(row['metadata'])
                completion_prompt = metadata.get('completion_prompt')
            except Exception as e:
                logger.warning(f"Failed to parse metadata: {e}")

        # If no completion_prompt in metadata, generate it now
        if not completion_prompt:
            expense_data = {
                'id': row['id'],
                'description': row['description'],
                'amount': row['amount'],
                'expense_date': row['expense_date'],
                'category': row['category'],
                'payment_account_id': row['payment_account_id'],
                'provider_name': row['provider_name'],
                'provider_rfc': row['provider_rfc'],
            }

            invoice_data = None
            if row['invoice_uuid']:
                invoice_data = {
                    'uuid': row['invoice_uuid'],
                    'provider_name': row['provider_name'],
                    'provider_rfc': row['provider_rfc'],
                    'total_amount': row['amount'],
                    'issued_date': row['expense_date'],
                }

            completion_prompt = expense_validator.get_completion_prompt_data(
                expense_data,
                invoice_data
            )

        conn.close()

        return CompletionPromptResponse(
            expense_id=expense_id,
            needs_completion=completion_prompt.get('needs_completion', True),
            missing_fields=completion_prompt.get('missing_fields', []),
            prefilled_data=completion_prompt.get('prefilled_data', {}),
            invoice_reference=completion_prompt.get('invoice_reference')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting completion prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def update_expense_with_completed_fields(request: UpdateExpenseRequest):
    """
    Update an expense with completed fields from the popup.

    This endpoint receives the filled-in fields from the user and:
    1. Updates the expense record with the new values
    2. Re-validates to ensure all required fields are present
    3. Updates workflow_status to 'draft' if complete
    4. Updates metadata to reflect completion
    """
    start_time = time.time()

    # Set request context for structured logging
    set_request_context(
        tenant_id=request.company_id,
        expense_id=request.expense_id,
        action="update_placeholder"
    )

    logger.info(
        "Starting expense placeholder update",
        expense_id=request.expense_id,
        fields_count=len(request.completed_fields)
    )

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current expense
        cursor.execute("""
        SELECT id, metadata, workflow_status
        FROM expense_records
        WHERE id = ?
        """, (request.expense_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Expense {request.expense_id} not found")

        # IDEMPOTENCY CHECK: Prevent duplicate updates within short timeframe (5 minutes)
        existing_metadata = {}
        if row[1]:  # metadata column
            try:
                existing_metadata = json.loads(row[1])
            except:
                pass

        # Check if there was a recent update
        last_update_time = existing_metadata.get('last_update_timestamp')
        if last_update_time:
            try:
                last_update = datetime.fromisoformat(last_update_time.replace('Z', '+00:00'))
                seconds_since_last_update = (datetime.utcnow() - last_update.replace(tzinfo=None)).total_seconds()

                # If updated within last 5 minutes (300 seconds), check if it's the same update
                if seconds_since_last_update < 300:
                    # Compare completed_fields with last_updated_fields
                    last_fields = existing_metadata.get('last_updated_fields', {})

                    # If same fields with same values, this is a duplicate request
                    if last_fields == request.completed_fields:
                        conn.close()
                        logger.warning(
                            "Duplicate update request detected (idempotency check)",
                            extra={
                                'expense_id': request.expense_id,
                                'seconds_since_last_update': round(seconds_since_last_update, 2)
                            }
                        )
                        raise HTTPException(
                            status_code=429,  # Too Many Requests
                            detail=f"Update already processed {int(seconds_since_last_update)} seconds ago. Please wait before retrying."
                        )
            except (ValueError, AttributeError) as e:
                # Invalid timestamp format, proceed with update
                logger.debug(f"Could not parse last_update_timestamp: {e}")

        # Build UPDATE statement dynamically based on completed_fields
        update_fields = []
        update_values = []

        # Map of allowed fields to update
        allowed_fields = {
            'description', 'category', 'payment_account_id',
            'provider_name', 'provider_rfc', 'forma_pago',
            'amount', 'expense_date', 'cfdi_uuid'
        }

        for field, value in request.completed_fields.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = ?")
                update_values.append(value)

        if not update_fields:
            conn.close()
            raise HTTPException(status_code=400, detail="No valid fields to update")

        # VALIDATION: Check for duplicate RFC
        if 'provider_rfc' in request.completed_fields:
            rfc_value = request.completed_fields['provider_rfc']
            if rfc_value:
                cursor.execute("""
                SELECT id FROM expense_records
                WHERE provider_rfc = ? AND id != ? AND company_id = ?
                LIMIT 1
                """, (rfc_value, request.expense_id, request.company_id))

                duplicate_row = cursor.fetchone()
                if duplicate_row:
                    conn.close()
                    log_validation_error(
                        logger,
                        "duplicate_rfc",
                        {
                            "rfc": rfc_value,
                            "existing_expense_id": duplicate_row[0],
                            "attempted_expense_id": request.expense_id
                        }
                    )
                    raise HTTPException(
                        status_code=409,
                        detail=f"Ya existe un gasto con RFC '{rfc_value}' (ID: {duplicate_row[0]})"
                    )

        # VALIDATION: Check for duplicate invoice UUID
        if 'cfdi_uuid' in request.completed_fields:
            uuid_value = request.completed_fields['cfdi_uuid']
            if uuid_value:
                cursor.execute("""
                SELECT id FROM expense_records
                WHERE cfdi_uuid = ? AND id != ? AND company_id = ?
                LIMIT 1
                """, (uuid_value, request.expense_id, request.company_id))

                duplicate_row = cursor.fetchone()
                if duplicate_row:
                    conn.close()
                    log_validation_error(
                        logger,
                        "duplicate_uuid",
                        {
                            "uuid": uuid_value,
                            "existing_expense_id": duplicate_row[0],
                            "attempted_expense_id": request.expense_id
                        }
                    )
                    raise HTTPException(
                        status_code=409,
                        detail=f"Ya existe una factura con UUID '{uuid_value}' (ID: {duplicate_row[0]})"
                    )

        # Get updated expense data for validation
        cursor.execute(f"""
        SELECT
            description, amount, expense_date, category,
            payment_account_id, provider_name, provider_rfc
        FROM expense_records
        WHERE id = ?
        """, (request.expense_id,))

        current_data = cursor.fetchone()

        # Merge with completed fields
        expense_data = {
            'description': request.completed_fields.get('description', current_data[0]),
            'amount': request.completed_fields.get('amount', current_data[1]),
            'expense_date': request.completed_fields.get('expense_date', current_data[2]),
            'category': request.completed_fields.get('category', current_data[3]),
            'payment_account_id': request.completed_fields.get('payment_account_id', current_data[4]),
            'provider_name': request.completed_fields.get('provider_name', current_data[5]),
            'provider_rfc': request.completed_fields.get('provider_rfc', current_data[6]),
        }

        # Re-validate
        validation_result = expense_validator.validate_expense_data(expense_data, context="bulk_invoice")

        # Update workflow_status based on validation
        new_workflow_status = "draft" if validation_result.is_complete else "requiere_completar"
        update_fields.append("workflow_status = ?")
        update_values.append(new_workflow_status)

        # Update metadata (reuse existing_metadata from idempotency check)
        existing_metadata['completed_at'] = datetime.utcnow().isoformat()
        existing_metadata['completed_by_user'] = True
        existing_metadata['validation_status'] = 'complete' if validation_result.is_complete else 'incomplete'
        existing_metadata['missing_fields'] = validation_result.missing_fields

        # Store for idempotency check on next request
        existing_metadata['last_update_timestamp'] = datetime.utcnow().isoformat() + 'Z'
        existing_metadata['last_updated_fields'] = request.completed_fields

        if not validation_result.is_complete:
            # Still missing fields, update completion_prompt
            completion_prompt = expense_validator.get_completion_prompt_data(expense_data, None)
            existing_metadata['completion_prompt'] = completion_prompt
        else:
            # Complete, remove completion flags
            existing_metadata.pop('completion_prompt', None)
            existing_metadata['placeholder_needs_review'] = False

        update_fields.append("metadata = ?")
        update_values.append(json.dumps(existing_metadata))

        update_fields.append("updated_at = ?")
        update_values.append(datetime.utcnow().isoformat())

        # Execute update
        update_values.append(request.expense_id)
        update_query = f"""
        UPDATE expense_records
        SET {', '.join(update_fields)}
        WHERE id = ?
        """

        cursor.execute(update_query, update_values)
        conn.commit()
        conn.close()

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log successful update
        log_expense_action(
            logger,
            action="updated",
            expense_id=request.expense_id,
            level="INFO",
            new_workflow_status=new_workflow_status,
            is_complete=validation_result.is_complete,
            duration_ms=duration_ms
        )

        return {
            "status": "success",
            "expense_id": request.expense_id,
            "workflow_status": new_workflow_status,
            "is_complete": validation_result.is_complete,
            "remaining_missing_fields": validation_result.missing_fields,
            "message": "Expense actualizado correctamente" if validation_result.is_complete else "Expense actualizado pero aún requiere campos adicionales"
        }

    except HTTPException:
        # Log HTTP exceptions (validation errors)
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            "HTTP exception in placeholder update",
            expense_id=request.expense_id,
            status_code=400,
            duration_ms=duration_ms
        )
        raise
    except Exception as e:
        # Log unexpected errors
        duration_ms = (time.time() - start_time) * 1000
        logger.exception(
            "Error updating expense placeholder",
            expense_id=request.expense_id,
            duration_ms=duration_ms
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=CompletionStatsResponse)
async def get_completion_stats(company_id: str = "default"):
    """
    Get statistics about incomplete expense placeholders.
    """
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Total pending
        cursor.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total_amount
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        """, (company_id,))

        row = cursor.fetchone()
        total_pending = row['count'] or 0
        total_amount = row['total_amount'] or 0.0

        # Oldest pending
        cursor.execute("""
        SELECT MIN(created_at) as oldest
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        """, (company_id,))

        row = cursor.fetchone()
        oldest = row['oldest']

        # By category
        cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        GROUP BY category
        """, (company_id,))

        by_category = {}
        for row in cursor.fetchall():
            category = row['category'] or 'sin_clasificar'
            by_category[category] = row['count']

        conn.close()

        return CompletionStatsResponse(
            total_pending=total_pending,
            total_amount_pending=total_amount,
            oldest_pending_date=oldest,
            by_category=by_category
        )

    except Exception as e:
        logger.error(f"Error getting completion stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/detailed", response_model=DetailedStatsResponse)
async def get_detailed_stats(company_id: str = "default"):
    """
    Get detailed KPIs and analytics for expense placeholder completion system.

    Returns comprehensive metrics including:
    - Completion rates and time-to-complete
    - Top missing fields analysis
    - Age-based breakdown of pending placeholders
    - At-risk placeholder count
    """
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Total pending and amount
        cursor.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total_amount
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        """, (company_id,))

        row = cursor.fetchone()
        total_pending = row['count'] or 0
        total_amount_pending = row['total_amount'] or 0.0

        # 2. Completed today and this week
        cursor.execute("""
        SELECT COUNT(*) as today_count
        FROM expense_records
        WHERE company_id = ?
        AND metadata LIKE '%"completed_by_user": true%'
        AND DATE(json_extract(metadata, '$.completed_at')) = DATE('now')
        """, (company_id,))

        completed_today = cursor.fetchone()['today_count'] or 0

        cursor.execute("""
        SELECT COUNT(*) as week_count
        FROM expense_records
        WHERE company_id = ?
        AND metadata LIKE '%"completed_by_user": true%'
        AND DATE(json_extract(metadata, '$.completed_at')) >= DATE('now', '-7 days')
        """, (company_id,))

        completed_this_week = cursor.fetchone()['week_count'] or 0

        # 3. Completion rate (completed within 24h)
        cursor.execute("""
        SELECT COUNT(*) as fast_completed
        FROM expense_records
        WHERE company_id = ?
        AND metadata LIKE '%"completed_by_user": true%'
        AND (
            julianday(json_extract(metadata, '$.completed_at')) - julianday(created_at)
        ) * 24 <= 24
        AND created_at >= datetime('now', '-30 days')
        """, (company_id,))

        fast_completed = cursor.fetchone()['fast_completed'] or 0

        cursor.execute("""
        SELECT COUNT(*) as total_completed_last_month
        FROM expense_records
        WHERE company_id = ?
        AND metadata LIKE '%"completed_by_user": true%'
        AND created_at >= datetime('now', '-30 days')
        """, (company_id,))

        total_completed_last_month = cursor.fetchone()['total_completed_last_month'] or 0
        completion_rate = (fast_completed / total_completed_last_month * 100) if total_completed_last_month > 0 else 0.0

        # 4. Average time to complete (in hours)
        cursor.execute("""
        SELECT AVG(
            (julianday(json_extract(metadata, '$.completed_at')) - julianday(created_at)) * 24
        ) as avg_hours
        FROM expense_records
        WHERE company_id = ?
        AND metadata LIKE '%"completed_by_user": true%'
        AND created_at >= datetime('now', '-30 days')
        """, (company_id,))

        avg_hours_row = cursor.fetchone()
        average_time_to_complete_hours = avg_hours_row['avg_hours'] if avg_hours_row['avg_hours'] else None

        # 5. Top missing fields analysis
        cursor.execute("""
        SELECT metadata
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        AND metadata IS NOT NULL
        """, (company_id,))

        missing_fields_counter = {}
        for row in cursor.fetchall():
            try:
                metadata = json.loads(row['metadata'])
                missing_fields = metadata.get('missing_fields', [])
                for field in missing_fields:
                    missing_fields_counter[field] = missing_fields_counter.get(field, 0) + 1
            except:
                pass

        top_missing_fields = []
        for field, count in sorted(missing_fields_counter.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_pending * 100) if total_pending > 0 else 0
            top_missing_fields.append({
                "field": field,
                "count": count,
                "percentage": round(percentage, 2)
            })

        # 6. Pending by age
        cursor.execute("""
        SELECT
            CASE
                WHEN (julianday('now') - julianday(created_at)) * 24 < 24 THEN '<24h'
                WHEN (julianday('now') - julianday(created_at)) * 24 < 48 THEN '24-48h'
                WHEN (julianday('now') - julianday(created_at)) * 24 < 168 THEN '48h-7d'
                ELSE '>7d'
            END as age_bucket,
            COUNT(*) as count
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        GROUP BY age_bucket
        """, (company_id,))

        pending_by_age = {"<24h": 0, "24-48h": 0, "48h-7d": 0, ">7d": 0}
        for row in cursor.fetchall():
            pending_by_age[row['age_bucket']] = row['count']

        # 7. Pending by category
        cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        GROUP BY category
        """, (company_id,))

        pending_by_category = {}
        for row in cursor.fetchall():
            category = row['category'] or 'sin_clasificar'
            pending_by_category[category] = row['count']

        # 8. Oldest pending hours
        cursor.execute("""
        SELECT MIN(created_at) as oldest
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        """, (company_id,))

        oldest_row = cursor.fetchone()
        oldest_pending_hours = None
        if oldest_row['oldest']:
            cursor.execute("""
            SELECT (julianday('now') - julianday(?)) * 24 as hours
            """, (oldest_row['oldest'],))
            oldest_pending_hours = cursor.fetchone()['hours']

        # 9. At-risk count (older than 48 hours)
        cursor.execute("""
        SELECT COUNT(*) as at_risk
        FROM expense_records
        WHERE workflow_status = 'requiere_completar'
        AND company_id = ?
        AND (julianday('now') - julianday(created_at)) * 24 > 48
        """, (company_id,))

        at_risk_count = cursor.fetchone()['at_risk'] or 0

        conn.close()

        return DetailedStatsResponse(
            total_pending=total_pending,
            total_amount_pending=total_amount_pending,
            total_completed_today=completed_today,
            total_completed_this_week=completed_this_week,
            completion_rate=round(completion_rate, 2),
            average_time_to_complete_hours=round(average_time_to_complete_hours, 2) if average_time_to_complete_hours else None,
            top_missing_fields=top_missing_fields,
            pending_by_age=pending_by_age,
            pending_by_category=pending_by_category,
            oldest_pending_hours=round(oldest_pending_hours, 2) if oldest_pending_hours else None,
            at_risk_count=at_risk_count
        )

    except Exception as e:
        logger.exception("Error getting detailed stats", extra={'company_id': company_id})
        raise HTTPException(status_code=500, detail=str(e))
