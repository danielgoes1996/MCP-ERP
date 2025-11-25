"""
API endpoints for Non-Reconciliation Management
🔒 Protected endpoints - Requires JWT authentication
Implementing Point 13 improvements for expense non-reconciliation workflow
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from core.api_models import (
    NonReconciliationRequest, NonReconciliationResponse, NonReconciliationUpdate,
    NonReconciliationEscalationRequest, NonReconciliationBulkAction,
    NonReconciliationStats, EscalationRuleCreate, EscalationRuleResponse,
    NonReconciliationNotificationRequest, NonReconciliationHistoryResponse,
    NonReconciliationAnalyticsRequest, NonReconciliationAnalyticsResponse,
    NonReconciliationReason, ReconciliationStatus, BusinessImpactLevel
)
from core.non_reconciliation_system import non_reconciliation_system
from core.shared.unified_db_adapter import get_db_adapter
from core.auth.jwt import User, get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/non-reconciliation", tags=["non-reconciliation"])

# =========================================================
# CORE NON-RECONCILIATION ENDPOINTS
# =========================================================

@router.post("/mark-non-reconcilable", response_model=NonReconciliationResponse)
async def mark_expense_non_reconcilable(
    request: NonReconciliationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(['accountant', 'admin']))
):
    """
    Mark an expense as non-reconcilable with specified reason

    🔒 **Requires:** accountant or admin role
    """
    try:
        db = get_db_adapter()

        # Create non-reconciliation record
        record = await non_reconciliation_system.mark_non_reconcilable(
            expense_id=request.expense_id,
            reason_code=request.reason_code,
            reason_description=request.reason_description,
            notes=request.notes,
            estimated_resolution_date=request.estimated_resolution_date,
            resolution_priority=request.resolution_priority,
            business_impact=request.business_impact,
            context_data=request.context_data,
            supporting_documents=request.supporting_documents,
            tags=request.tags,
            escalation_rules=request.escalation_rules,
            created_by=current_user.id
        )

        # Schedule background tasks
        background_tasks.add_task(
            _schedule_initial_notifications,
            record.id
        )

        # Update expense status
        await db.execute(
            "UPDATE manual_expenses SET bank_status = 'non_reconcilable' WHERE id = ?",
            (request.expense_id,)
        )

        return NonReconciliationResponse(
            id=record.id,
            expense_id=record.expense_id,
            reason_code=record.reason_code.value,
            reason_description=record.reason_description,
            status=record.status,
            escalation_level=record.escalation_level,
            estimated_resolution_date=record.estimated_resolution_date,
            resolution_priority=record.resolution_priority,
            business_impact=record.business_impact.value,
            workflow_state=record.workflow_state,
            created_by=record.created_by,
            created_at=record.created_at,
            context_data=record.context_data,
            tags=record.tags
        )

    except Exception as e:
        logger.error(f"Error marking expense as non-reconcilable: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records", response_model=List[NonReconciliationResponse])
async def get_non_reconciliation_records(
    company_id: str = "default",
    status: Optional[ReconciliationStatus] = None,
    reason_code: Optional[NonReconciliationReason] = None,
    escalation_level: Optional[int] = None,
    business_impact: Optional[BusinessImpactLevel] = None,
    overdue_only: bool = False,
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve non-reconciliation records with filtering
    """
    try:
        filters = {
            'company_id': company_id,
            'status': status.value if status else None,
            'reason_code': reason_code.value if reason_code else None,
            'escalation_level': escalation_level,
            'business_impact': business_impact.value if business_impact else None,
            'overdue_only': overdue_only,
            'limit': limit,
            'offset': offset
        }

        records = await non_reconciliation_system.get_records(**filters)

        return [
            NonReconciliationResponse(
                id=r.id,
                expense_id=r.expense_id,
                reason_code=r.reason_code.value,
                reason_description=r.reason_description,
                status=r.status,
                escalation_level=r.escalation_level,
                estimated_resolution_date=r.estimated_resolution_date,
                actual_resolution_date=r.actual_resolution_date,
                resolution_priority=r.resolution_priority,
                business_impact=r.business_impact.value,
                workflow_state=r.workflow_state,
                created_by=r.created_by,
                created_at=r.created_at,
                updated_at=r.updated_at,
                next_escalation_date=r.next_escalation_date,
                context_data=r.context_data,
                tags=r.tags
            ) for r in records
        ]

    except Exception as e:
        logger.error(f"Error retrieving non-reconciliation records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records/{record_id}", response_model=NonReconciliationResponse)
async def get_non_reconciliation_record(record_id: int):
    """
    Get specific non-reconciliation record by ID
    """
    try:
        record = await non_reconciliation_system.get_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Non-reconciliation record not found")

        return NonReconciliationResponse(
            id=record.id,
            expense_id=record.expense_id,
            reason_code=record.reason_code.value,
            reason_description=record.reason_description,
            status=record.status,
            escalation_level=record.escalation_level,
            estimated_resolution_date=record.estimated_resolution_date,
            actual_resolution_date=record.actual_resolution_date,
            resolution_priority=record.resolution_priority,
            business_impact=record.business_impact.value,
            workflow_state=record.workflow_state,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
            next_escalation_date=record.next_escalation_date,
            context_data=record.context_data,
            tags=record.tags
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving non-reconciliation record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/records/{record_id}", response_model=NonReconciliationResponse)
async def update_non_reconciliation_record(
    record_id: int,
    request: NonReconciliationUpdate,
    background_tasks: BackgroundTasks
):
    """
    Update non-reconciliation record
    """
    try:
        record = await non_reconciliation_system.update_record(
            record_id=record_id,
            status=request.status,
            resolution_notes=request.resolution_notes,
            estimated_resolution_date=request.estimated_resolution_date,
            actual_resolution_date=request.actual_resolution_date,
            resolution_priority=request.resolution_priority,
            business_impact=request.business_impact,
            escalation_level=request.escalation_level,
            escalated_to_user_id=request.escalated_to_user_id,
            workflow_state=request.workflow_state,
            context_data=request.context_data,
            tags=request.tags,
            supporting_documents=request.supporting_documents,
            updated_by=1  # TODO: Get from authentication context
        )

        if not record:
            raise HTTPException(status_code=404, detail="Non-reconciliation record not found")

        # Schedule notifications for status changes
        if request.status:
            background_tasks.add_task(
                _notify_status_change,
                record.id,
                request.status.value
            )

        return NonReconciliationResponse(
            id=record.id,
            expense_id=record.expense_id,
            reason_code=record.reason_code.value,
            reason_description=record.reason_description,
            status=record.status,
            escalation_level=record.escalation_level,
            estimated_resolution_date=record.estimated_resolution_date,
            actual_resolution_date=record.actual_resolution_date,
            resolution_priority=record.resolution_priority,
            business_impact=record.business_impact.value,
            workflow_state=record.workflow_state,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
            next_escalation_date=record.next_escalation_date,
            context_data=record.context_data,
            tags=record.tags
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating non-reconciliation record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# ESCALATION MANAGEMENT ENDPOINTS
# =========================================================

@router.post("/escalate", response_model=NonReconciliationResponse)
async def escalate_non_reconciliation(
    request: NonReconciliationEscalationRequest,
    background_tasks: BackgroundTasks
):
    """
    Escalate a non-reconciliation record to higher level
    """
    try:
        record = await non_reconciliation_system.escalate_record(
            record_id=request.non_reconciliation_id,
            escalation_level=request.escalation_level,
            escalated_to_user_id=request.escalated_to_user_id,
            escalation_reason=request.escalation_reason,
            notes=request.notes,
            escalated_by=1  # TODO: Get from authentication context
        )

        if not record:
            raise HTTPException(status_code=404, detail="Non-reconciliation record not found")

        # Schedule escalation notifications
        background_tasks.add_task(
            _notify_escalation,
            record.id,
            request.escalation_level
        )

        return NonReconciliationResponse(
            id=record.id,
            expense_id=record.expense_id,
            reason_code=record.reason_code.value,
            status=record.status,
            escalation_level=record.escalation_level,
            estimated_resolution_date=record.estimated_resolution_date,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
            message=f"Record escalated to level {request.escalation_level}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error escalating non-reconciliation record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-actions")
async def bulk_non_reconciliation_actions(
    request: NonReconciliationBulkAction,
    background_tasks: BackgroundTasks
):
    """
    Perform bulk actions on multiple non-reconciliation records
    """
    try:
        results = await non_reconciliation_system.bulk_action(
            record_ids=request.record_ids,
            action=request.action,
            parameters=request.parameters,
            notes=request.notes,
            performed_by=1  # TODO: Get from authentication context
        )

        # Schedule bulk notifications
        background_tasks.add_task(
            _notify_bulk_action,
            request.record_ids,
            request.action,
            results
        )

        return {
            "success": True,
            "processed": len(results),
            "results": results,
            "message": f"Bulk action '{request.action}' completed on {len(results)} records"
        }

    except Exception as e:
        logger.error(f"Error performing bulk action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# ESCALATION RULES ENDPOINTS
# =========================================================

@router.post("/escalation-rules", response_model=EscalationRuleResponse)
async def create_escalation_rule(request: EscalationRuleCreate):
    """
    Create new escalation rule
    """
    try:
        rule = await non_reconciliation_system.create_escalation_rule(
            company_id="default",  # TODO: Get from context
            rule_name=request.rule_name,
            rule_code=request.rule_code,
            applies_to_reason_codes=request.applies_to_reason_codes,
            applies_to_categories=request.applies_to_categories,
            minimum_amount=request.minimum_amount,
            maximum_amount=request.maximum_amount,
            escalation_after_days=request.escalation_after_days,
            escalation_levels=request.escalation_levels,
            notification_settings=request.notification_settings,
            is_active=request.is_active,
            created_by=1  # TODO: Get from authentication context
        )

        return EscalationRuleResponse(
            id=rule.id,
            company_id=rule.company_id,
            rule_name=rule.rule_name,
            rule_code=rule.rule_code,
            applies_to_reason_codes=rule.applies_to_reason_codes,
            applies_to_categories=rule.applies_to_categories,
            minimum_amount=rule.minimum_amount,
            maximum_amount=rule.maximum_amount,
            escalation_after_days=rule.escalation_after_days,
            escalation_levels=rule.escalation_levels,
            notification_settings=rule.notification_settings,
            is_active=rule.is_active,
            created_by=rule.created_by,
            created_at=rule.created_at,
            updated_at=rule.updated_at
        )

    except Exception as e:
        logger.error(f"Error creating escalation rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/escalation-rules", response_model=List[EscalationRuleResponse])
async def get_escalation_rules(
    company_id: str = "default",
    active_only: bool = True,
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get escalation rules for company
    """
    try:
        rules = await non_reconciliation_system.get_escalation_rules(
            company_id=company_id,
            active_only=active_only,
            limit=limit,
            offset=offset
        )

        return [
            EscalationRuleResponse(
                id=rule.id,
                company_id=rule.company_id,
                rule_name=rule.rule_name,
                rule_code=rule.rule_code,
                applies_to_reason_codes=rule.applies_to_reason_codes,
                applies_to_categories=rule.applies_to_categories,
                minimum_amount=rule.minimum_amount,
                maximum_amount=rule.maximum_amount,
                escalation_after_days=rule.escalation_after_days,
                escalation_levels=rule.escalation_levels,
                notification_settings=rule.notification_settings,
                is_active=rule.is_active,
                created_by=rule.created_by,
                created_at=rule.created_at,
                updated_at=rule.updated_at
            ) for rule in rules
        ]

    except Exception as e:
        logger.error(f"Error retrieving escalation rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# ANALYTICS AND REPORTING ENDPOINTS
# =========================================================

@router.get("/stats", response_model=NonReconciliationStats)
async def get_non_reconciliation_stats(
    company_id: str = "default",
    period_days: int = Query(30, ge=1, le=365)
):
    """
    Get non-reconciliation statistics for company
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)

        stats = await non_reconciliation_system.get_statistics(
            company_id=company_id,
            start_date=start_date,
            end_date=end_date
        )

        return stats

    except Exception as e:
        logger.error(f"Error retrieving non-reconciliation stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics", response_model=NonReconciliationAnalyticsResponse)
async def get_non_reconciliation_analytics(request: NonReconciliationAnalyticsRequest):
    """
    Get detailed analytics for non-reconciliation data
    """
    try:
        analytics = await non_reconciliation_system.get_analytics(
            company_id=request.company_id,
            period_start=request.period_start,
            period_end=request.period_end,
            group_by=request.group_by,
            include_trends=request.include_trends,
            include_forecasts=request.include_forecasts
        )

        return analytics

    except Exception as e:
        logger.error(f"Error generating non-reconciliation analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records/{record_id}/history", response_model=List[NonReconciliationHistoryResponse])
async def get_record_history(record_id: int):
    """
    Get history of actions for a non-reconciliation record
    """
    try:
        history = await non_reconciliation_system.get_record_history(record_id)

        return [
            NonReconciliationHistoryResponse(
                id=h.id,
                non_reconciliation_id=h.non_reconciliation_id,
                action_type=h.action_type,
                action_description=h.action_description,
                previous_status=h.previous_status,
                new_status=h.new_status,
                performed_by=h.performed_by,
                performed_at=h.performed_at,
                field_changes=h.field_changes,
                notes=h.notes,
                system_generated=h.system_generated,
                correlation_id=h.correlation_id
            ) for h in history
        ]

    except Exception as e:
        logger.error(f"Error retrieving record history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# NOTIFICATION ENDPOINTS
# =========================================================

@router.post("/notifications/schedule")
async def schedule_notification(request: NonReconciliationNotificationRequest):
    """
    Schedule a notification for a non-reconciliation record
    """
    try:
        notification = await non_reconciliation_system.schedule_notification(
            non_reconciliation_id=request.non_reconciliation_id,
            notification_type=request.notification_type,
            recipient_type=request.recipient_type,
            recipient_identifier=request.recipient_identifier,
            message_template=request.message_template,
            message_data=request.message_data,
            scheduled_for=request.scheduled_for
        )

        return {
            "success": True,
            "notification_id": notification.id,
            "message": "Notification scheduled successfully"
        }

    except Exception as e:
        logger.error(f"Error scheduling notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# UTILITY ENDPOINTS
# =========================================================

@router.get("/reason-codes")
async def get_reason_codes():
    """
    Get available non-reconciliation reason codes
    """
    try:
        codes = await non_reconciliation_system.get_reason_codes()
        return {
            "reason_codes": [
                {
                    "code": code.code,
                    "name": code.name,
                    "description": code.description,
                    "category": code.category,
                    "typical_resolution_days": code.typical_resolution_days,
                    "auto_resolution_possible": code.auto_resolution_possible
                } for code in codes
            ]
        }
    except Exception as e:
        logger.error(f"Error retrieving reason codes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard-summary")
async def get_dashboard_summary(company_id: str = "default"):
    """
    Get dashboard summary data for non-reconciliation management
    """
    try:
        summary = await non_reconciliation_system.get_dashboard_summary(company_id)
        return summary
    except Exception as e:
        logger.error(f"Error retrieving dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# BACKGROUND TASK FUNCTIONS
# =========================================================

async def _schedule_initial_notifications(record_id: int):
    """Schedule initial notifications for new non-reconciliation record"""
    try:
        await non_reconciliation_system.schedule_initial_notifications(record_id)
    except Exception as e:
        logger.error(f"Error scheduling initial notifications for record {record_id}: {e}")


async def _notify_status_change(record_id: int, new_status: str):
    """Notify about status change"""
    try:
        await non_reconciliation_system.notify_status_change(record_id, new_status)
    except Exception as e:
        logger.error(f"Error notifying status change for record {record_id}: {e}")


async def _notify_escalation(record_id: int, escalation_level: int):
    """Notify about escalation"""
    try:
        await non_reconciliation_system.notify_escalation(record_id, escalation_level)
    except Exception as e:
        logger.error(f"Error notifying escalation for record {record_id}: {e}")


async def _notify_bulk_action(record_ids: List[int], action: str, results: List[Dict[str, Any]]):
    """Notify about bulk action completion"""
    try:
        await non_reconciliation_system.notify_bulk_action(record_ids, action, results)
    except Exception as e:
        logger.error(f"Error notifying bulk action for records {record_ids}: {e}")


# =========================================================
# HEALTH CHECK
# =========================================================

@router.get("/health")
async def health_check():
    """Health check endpoint for non-reconciliation system"""
    try:
        # Test system components
        db_status = await non_reconciliation_system.health_check()

        return {
            "status": "healthy" if db_status else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy" if db_status else "unhealthy",
                "non_reconciliation_system": "healthy"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )