from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
from datetime import datetime
import logging
from core.expense_completion_system import ExpenseCompletionSystem
from core.api_models import (
    ExpenseCompletionSuggestionRequest,
    ExpenseCompletionSuggestionResponse,
    CompletionInteractionRequest,
    UserPreferencesRequest,
    UserPreferencesResponse,
    CompletionAnalyticsResponse,
    BulkCompletionRequest,
    BulkCompletionResponse,
    CompletionRuleRequest,
    CompletionRuleResponse,
    CompletionPatternResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/expense-completion", tags=["Expense Completion"])
completion_system = ExpenseCompletionSystem()

@router.post("/suggestions", response_model=ExpenseCompletionSuggestionResponse)
async def get_completion_suggestions(request: ExpenseCompletionSuggestionRequest):
    """
    Get field completion suggestions for an expense
    """
    try:
        suggestions = await completion_system.get_field_suggestions(
            user_id=request.user_id,
            expense_data=request.expense_data,
            target_fields=request.target_fields,
            context=request.context
        )

        return ExpenseCompletionSuggestionResponse(
            expense_id=request.expense_id,
            suggestions=suggestions,
            confidence_threshold=0.7,
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting completion suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/interactions")
async def record_completion_interaction(request: CompletionInteractionRequest):
    """
    Record user interaction with completion suggestions for learning
    """
    try:
        await completion_system.record_user_interaction(
            user_id=request.user_id,
            expense_id=request.expense_id,
            field_name=request.field_name,
            suggested_value=request.suggested_value,
            actual_value=request.actual_value,
            action=request.action,
            context=request.context
        )

        return {"status": "success", "message": "Interaction recorded"}

    except Exception as e:
        logger.error(f"Error recording interaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk-complete", response_model=BulkCompletionResponse)
async def bulk_complete_expenses(request: BulkCompletionRequest, background_tasks: BackgroundTasks):
    """
    Perform bulk completion of multiple expenses
    """
    try:
        # Start background task for bulk processing
        background_tasks.add_task(
            _process_bulk_completion,
            request.user_id,
            request.expense_ids,
            request.completion_rules,
            request.auto_apply_threshold
        )

        return BulkCompletionResponse(
            batch_id=f"bulk_{int(datetime.utcnow().timestamp())}",
            total_expenses=len(request.expense_ids),
            status="processing",
            estimated_completion_time=len(request.expense_ids) * 2  # 2 seconds per expense
        )

    except Exception as e:
        logger.error(f"Error starting bulk completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _process_bulk_completion(user_id: str, expense_ids: List[str], completion_rules: Dict, threshold: float):
    """
    Background task for bulk completion processing
    """
    for expense_id in expense_ids:
        try:
            # Get expense data and apply completion
            suggestions = await completion_system.get_field_suggestions(
                user_id=user_id,
                expense_data={"id": expense_id},
                target_fields=None  # All fields
            )

            # Auto-apply suggestions above threshold
            for suggestion in suggestions:
                if suggestion.confidence >= threshold:
                    await completion_system.record_user_interaction(
                        user_id=user_id,
                        expense_id=expense_id,
                        field_name=suggestion.field_name,
                        suggested_value=suggestion.value,
                        actual_value=suggestion.value,
                        action="auto_applied"
                    )

        except Exception as e:
            logger.error(f"Error processing bulk completion for expense {expense_id}: {e}")

@router.get("/preferences/{user_id}", response_model=UserPreferencesResponse)
async def get_user_preferences(user_id: str):
    """
    Get user completion preferences
    """
    try:
        preferences = await completion_system.get_user_preferences(user_id)

        return UserPreferencesResponse(
            user_id=user_id,
            auto_complete_threshold=preferences.get('auto_complete_threshold', 0.8),
            preferred_sources=preferences.get('preferred_sources', ['patterns', 'rules']),
            field_priorities=preferences.get('field_priorities', {}),
            learning_enabled=preferences.get('learning_enabled', True),
            notification_settings=preferences.get('notification_settings', {})
        )

    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/preferences/{user_id}")
async def update_user_preferences(user_id: str, request: UserPreferencesRequest):
    """
    Update user completion preferences
    """
    try:
        await completion_system.update_user_preferences(
            user_id=user_id,
            preferences={
                'auto_complete_threshold': request.auto_complete_threshold,
                'preferred_sources': request.preferred_sources,
                'field_priorities': request.field_priorities,
                'learning_enabled': request.learning_enabled,
                'notification_settings': request.notification_settings
            }
        )

        return {"status": "success", "message": "Preferences updated"}

    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/{user_id}", response_model=CompletionAnalyticsResponse)
async def get_completion_analytics(user_id: str, days: int = 30):
    """
    Get completion analytics for user
    """
    try:
        analytics = await completion_system.get_completion_analytics(user_id, days)

        return CompletionAnalyticsResponse(
            user_id=user_id,
            period_days=days,
            total_suggestions=analytics.get('total_suggestions', 0),
            accepted_suggestions=analytics.get('accepted_suggestions', 0),
            auto_completions=analytics.get('auto_completions', 0),
            accuracy_rate=analytics.get('accuracy_rate', 0.0),
            time_saved_minutes=analytics.get('time_saved_minutes', 0),
            top_completed_fields=analytics.get('top_completed_fields', []),
            completion_trends=analytics.get('completion_trends', {}),
            generated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting completion analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules", response_model=CompletionRuleResponse)
async def create_completion_rule(request: CompletionRuleRequest):
    """
    Create a new completion rule
    """
    try:
        rule_id = await completion_system.create_completion_rule(
            user_id=request.user_id,
            name=request.name,
            conditions=request.conditions,
            actions=request.actions,
            priority=request.priority,
            active=request.active
        )

        return CompletionRuleResponse(
            rule_id=rule_id,
            name=request.name,
            conditions=request.conditions,
            actions=request.actions,
            priority=request.priority,
            active=request.active,
            created_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error creating completion rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rules/{user_id}", response_model=List[CompletionRuleResponse])
async def get_completion_rules(user_id: str):
    """
    Get all completion rules for user
    """
    try:
        rules = await completion_system.get_completion_rules(user_id)
        return [
            CompletionRuleResponse(
                rule_id=rule.get('id'),
                name=rule.get('name'),
                conditions=rule.get('conditions', {}),
                actions=rule.get('actions', {}),
                priority=rule.get('priority', 1),
                active=rule.get('active', True),
                created_at=rule.get('created_at')
            ) for rule in rules
        ]

    except Exception as e:
        logger.error(f"Error getting completion rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/rules/{rule_id}")
async def delete_completion_rule(rule_id: str):
    """
    Delete a completion rule
    """
    try:
        await completion_system.delete_completion_rule(rule_id)
        return {"status": "success", "message": "Rule deleted"}

    except Exception as e:
        logger.error(f"Error deleting completion rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/patterns/{user_id}", response_model=List[CompletionPatternResponse])
async def get_learned_patterns(user_id: str, limit: int = 50):
    """
    Get learned completion patterns for user
    """
    try:
        patterns = await completion_system.get_learned_patterns(user_id, limit)
        return [
            CompletionPatternResponse(
                pattern_id=pattern.get('id'),
                field_name=pattern.get('field_name'),
                conditions=pattern.get('conditions', {}),
                suggested_value=pattern.get('suggested_value'),
                confidence=pattern.get('confidence', 0.0),
                usage_count=pattern.get('usage_count', 0),
                last_used=pattern.get('last_used'),
                created_at=pattern.get('created_at')
            ) for pattern in patterns
        ]

    except Exception as e:
        logger.error(f"Error getting learned patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate-completeness")
async def validate_expense_completeness(expense_data: Dict[str, Any]):
    """
    Validate completeness of expense data
    """
    try:
        validation = await completion_system.validate_completeness(expense_data)

        return {
            "is_complete": validation.get('is_complete', False),
            "missing_fields": validation.get('missing_fields', []),
            "completeness_score": validation.get('completeness_score', 0.0),
            "suggestions": validation.get('suggestions', []),
            "validation_rules": validation.get('validation_rules', {})
        }

    except Exception as e:
        logger.error(f"Error validating completeness: {e}")
        raise HTTPException(status_code=500, detail=str(e))