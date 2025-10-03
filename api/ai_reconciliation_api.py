"""
API endpoints for AI-powered reconciliation suggestions
🔒 Protected endpoints - Requires JWT authentication
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any
import logging

from core.ai_reconciliation_service import get_ai_reconciliation_service
from core.auth_jwt import User, get_current_user, require_role, enforce_tenant_isolation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bank_reconciliation/ai", tags=["AI Reconciliation"])


# =====================================================
# SUGGESTIONS ENDPOINTS
# =====================================================

@router.get("/suggestions", response_model=List[Dict[str, Any]])
async def get_reconciliation_suggestions(
    limit: int = 20,
    min_confidence: float = 60.0,
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get AI-powered reconciliation suggestions

    🔒 **Requires:** Authentication (accountants/admins can see all, employees filtered)

    **Features:**
    - Hybrid approach: Rule-based + text similarity
    - Confidence scoring (0-100%)
    - Both one-to-many and many-to-one suggestions

    **Query Parameters:**
    - `limit`: Maximum number of suggestions (default 20)
    - `min_confidence`: Minimum confidence threshold (default 60%)

    **Returns:**
    List of suggestions sorted by confidence (highest first)

    **Example Response:**
    ```json
    [
      {
        "type": "one_to_many",
        "confidence_score": 95.5,
        "confidence_level": "high",
        "movement": {
          "id": 8181,
          "description": "PAGO PROVEEDOR XYZ",
          "amount": 2551.25,
          "date": "2025-01-16"
        },
        "expenses": [
          {
            "id": 10244,
            "description": "Gasolina",
            "amount": 850.50,
            "allocated_amount": 850.50
          },
          ...
        ],
        "breakdown": {
          "amount_match": 100.0,
          "date_proximity": 85.0,
          "description_similarity": 72.5
        },
        "total_allocated": 2551.25,
        "difference": 0.0
      }
    ]
    ```
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        ai_service = get_ai_reconciliation_service()
        suggestions = ai_service.get_all_suggestions(limit=limit, tenant_id=tenant_id)

        # Filter by minimum confidence
        filtered = [s for s in suggestions if s['confidence_score'] >= min_confidence]

        logger.info(f"User {current_user.username} (tenant={tenant_id}) generated {len(filtered)} AI suggestions (min_confidence={min_confidence})")

        return filtered

    except Exception as e:
        logger.exception(f"Error generating AI suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating suggestions: {str(e)}"
        )


@router.get("/suggestions/one-to-many", response_model=List[Dict[str, Any]])
async def get_one_to_many_suggestions(
    limit: int = 10,
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get one-to-many split suggestions (1 movement → N expenses)

    🔒 **Requires:** Authentication

    **Use case:** Find cases where a single bank payment covers multiple expenses
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        ai_service = get_ai_reconciliation_service()
        suggestions = ai_service.suggest_one_to_many_splits(limit=limit, tenant_id=tenant_id)

        logger.info(f"User {current_user.username} (tenant={tenant_id}) viewed {len(suggestions)} one-to-many suggestions")

        return suggestions

    except Exception as e:
        logger.exception(f"Error generating one-to-many suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating suggestions: {str(e)}"
        )


@router.get("/suggestions/many-to-one", response_model=List[Dict[str, Any]])
async def get_many_to_one_suggestions(
    limit: int = 10,
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get many-to-one split suggestions (N movements → 1 expense)

    🔒 **Requires:** Authentication

    **Use case:** Find cases where multiple payments (installments) pay for one expense
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        ai_service = get_ai_reconciliation_service()
        suggestions = ai_service.suggest_many_to_one_splits(limit=limit, tenant_id=tenant_id)

        logger.info(f"User {current_user.username} (tenant={tenant_id}) viewed {len(suggestions)} many-to-one suggestions")

        return suggestions

    except Exception as e:
        logger.exception(f"Error generating many-to-one suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating suggestions: {str(e)}"
        )


# =====================================================
# AUTO-APPLY ENDPOINTS
# =====================================================

@router.post("/auto-apply/{suggestion_index}", status_code=status.HTTP_201_CREATED)
async def auto_apply_suggestion(
    suggestion_index: int,
    min_confidence: float = 85.0,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, Any]:
    """
    Automatically apply a suggestion if confidence is high enough

    🔒 **Requires:** admin role ONLY (high-risk operation)

    **Safety:**
    - Only applies if confidence >= min_confidence (default 85%)
    - Creates actual split reconciliation via existing endpoints

    **Returns:**
    - split_group_id: ID of created split
    - success: True/False
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        ai_service = get_ai_reconciliation_service()
        suggestions = ai_service.get_all_suggestions(limit=50, tenant_id=tenant_id)

        if suggestion_index >= len(suggestions):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Suggestion index {suggestion_index} not found"
            )

        suggestion = suggestions[suggestion_index]

        # Safety check
        if suggestion['confidence_score'] < min_confidence:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Confidence too low ({suggestion['confidence_score']}% < {min_confidence}%). "
                       "Use manual review instead."
            )

        # Import here to avoid circular dependency
        from core.split_reconciliation_service import (
            create_one_to_many_split,
            create_many_to_one_split
        )
        from core.split_reconciliation_models import (
            SplitOneToManyRequest,
            SplitManyToOneRequest,
            SplitExpenseItem,
            SplitMovementItem
        )

        # Apply based on type
        if suggestion['type'] == 'one_to_many':
            request = SplitOneToManyRequest(
                movement_id=suggestion['movement']['id'],
                movement_amount=suggestion['movement']['amount'],
                expenses=[
                    SplitExpenseItem(
                        expense_id=e['id'],
                        amount=e['allocated_amount'],
                        notes=f"Auto-matched by AI ({suggestion['confidence_score']}%)"
                    )
                    for e in suggestion['expenses']
                ],
                notes=f"Auto-applied AI suggestion (confidence: {suggestion['confidence_score']}%)"
            )
            result = create_one_to_many_split(request, user_id=current_user.id, tenant_id=tenant_id)

        else:  # many_to_one
            request = SplitManyToOneRequest(
                expense_id=suggestion['expense']['id'],
                expense_amount=suggestion['expense']['amount'],
                movements=[
                    SplitMovementItem(
                        movement_id=m['id'],
                        amount=m['allocated_amount'],
                        payment_number=m.get('payment_number'),
                        notes=f"Auto-matched by AI ({suggestion['confidence_score']}%)"
                    )
                    for m in suggestion['movements']
                ],
                notes=f"Auto-applied AI suggestion (confidence: {suggestion['confidence_score']}%)"
            )
            result = create_many_to_one_split(request, user_id=current_user.id, tenant_id=tenant_id)

        logger.info(f"✅ Admin {current_user.username} (tenant={tenant_id}) auto-applied suggestion {suggestion_index}: {result.split_group_id}")

        return {
            "success": True,
            "split_group_id": result.split_group_id,
            "confidence_score": suggestion['confidence_score'],
            "type": suggestion['type'],
            "message": "Suggestion applied successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error auto-applying suggestion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying suggestion: {str(e)}"
        )


@router.post("/auto-apply-batch", status_code=status.HTTP_201_CREATED)
async def auto_apply_batch(
    min_confidence: float = 90.0,
    max_suggestions: int = 10
) -> Dict[str, Any]:
    """
    Auto-apply multiple high-confidence suggestions in batch

    **Safety:**
    - Only applies suggestions with confidence >= min_confidence (default 90%)
    - Maximum number of suggestions to apply: max_suggestions (default 10)

    **Returns:**
    - applied_count: Number of suggestions successfully applied
    - failed_count: Number of suggestions that failed
    - results: List of results per suggestion
    """
    try:
        ai_service = get_ai_reconciliation_service()
        suggestions = ai_service.get_all_suggestions(limit=50)

        # Filter high confidence
        high_confidence = [
            s for s in suggestions
            if s['confidence_score'] >= min_confidence
        ][:max_suggestions]

        results = []
        applied_count = 0
        failed_count = 0

        for idx, suggestion in enumerate(high_confidence):
            try:
                # Use the single auto-apply endpoint
                result = await auto_apply_suggestion(idx, min_confidence=min_confidence)
                results.append({
                    "index": idx,
                    "success": True,
                    "split_group_id": result['split_group_id'],
                    "confidence": suggestion['confidence_score']
                })
                applied_count += 1

            except Exception as e:
                results.append({
                    "index": idx,
                    "success": False,
                    "error": str(e),
                    "confidence": suggestion['confidence_score']
                })
                failed_count += 1

        logger.info(f"Batch auto-apply: {applied_count} applied, {failed_count} failed")

        return {
            "applied_count": applied_count,
            "failed_count": failed_count,
            "total_processed": len(high_confidence),
            "results": results
        }

    except Exception as e:
        logger.exception(f"Error in batch auto-apply: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in batch processing: {str(e)}"
        )


# =====================================================
# STATISTICS
# =====================================================

@router.get("/stats")
async def get_ai_stats() -> Dict[str, Any]:
    """
    Get statistics about AI suggestions

    **Returns:**
    - total_suggestions: Total number of suggestions available
    - high_confidence_count: Suggestions with confidence >= 85%
    - medium_confidence_count: Suggestions with 60% <= confidence < 85%
    - average_confidence: Average confidence score
    - by_type: Breakdown by suggestion type
    """
    try:
        ai_service = get_ai_reconciliation_service()
        suggestions = ai_service.get_all_suggestions(limit=100)

        high_conf = [s for s in suggestions if s['confidence_score'] >= 85]
        medium_conf = [s for s in suggestions if 60 <= s['confidence_score'] < 85]

        one_to_many = [s for s in suggestions if s['type'] == 'one_to_many']
        many_to_one = [s for s in suggestions if s['type'] == 'many_to_one']

        avg_confidence = (
            sum(s['confidence_score'] for s in suggestions) / len(suggestions)
            if suggestions else 0.0
        )

        return {
            "total_suggestions": len(suggestions),
            "high_confidence_count": len(high_conf),
            "medium_confidence_count": len(medium_conf),
            "average_confidence": round(avg_confidence, 2),
            "by_type": {
                "one_to_many": len(one_to_many),
                "many_to_one": len(many_to_one)
            }
        }

    except Exception as e:
        logger.exception(f"Error getting AI stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting statistics: {str(e)}"
        )
