"""
API endpoints for Split Reconciliation
🔒 Protected endpoints - Requires JWT authentication

Handles:
- One-to-Many: 1 bank movement → N expenses
- Many-to-One: N bank movements → 1 expense
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import logging

from core.split_reconciliation_models import (
    SplitType,
    SplitOneToManyRequest,
    SplitManyToOneRequest,
    SplitResponse,
    SplitDetailResponse,
    SplitSummary,
)
from core.split_reconciliation_service import (
    create_one_to_many_split,
    create_many_to_one_split,
    get_split_details,
    list_splits,
    undo_split,
    get_split_summary,
)
from core.auth_jwt import User, get_current_user, require_role, enforce_tenant_isolation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bank_reconciliation/split", tags=["Split Reconciliation"])


# =====================================================
# CREATE SPLIT RECONCILIATIONS
# =====================================================

@router.post("/one-to-many", response_model=SplitResponse, status_code=status.HTTP_201_CREATED)
async def create_one_to_many_split_endpoint(
    request: SplitOneToManyRequest,
    current_user: User = Depends(require_role(['accountant', 'admin']))
) -> SplitResponse:
    """
    Create a one-to-many split reconciliation.

    🔒 **Requires:** accountant or admin role

    **Use case:** One bank movement pays for multiple expenses.

    **Example:**
    - Movement: "PAGO A PROVEEDOR XYZ" - $5,000
    - Expenses:
      * Servicio de mantenimiento - $2,500
      * Reparación de equipo - $1,500
      * Material adicional - $1,000

    **Process:**
    1. Validates that allocated amounts match movement total
    2. Creates split records for each expense
    3. Marks movement and all expenses as reconciled with split type
    4. Returns split group ID for tracking

    **Requirements:**
    - At least 2 expenses
    - Sum of expense amounts must equal movement amount (±$0.01 tolerance)
    - Movement must not be already reconciled (simple)
    - Expenses must not be already reconciled (simple)
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        result = create_one_to_many_split(request, user_id=current_user.id, tenant_id=tenant_id)

        logger.info(
            f"✅ User {current_user.username} (tenant={tenant_id}) created one-to-many split {result.split_group_id}: "
            f"movement {request.movement_id} → {len(request.expenses)} expenses"
        )

        return result

    except ValueError as e:
        logger.error(f"Validation error creating one-to-many split: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error creating one-to-many split: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating split reconciliation: {str(e)}"
        )


@router.post("/many-to-one", response_model=SplitResponse, status_code=status.HTTP_201_CREATED)
async def create_many_to_one_split_endpoint(
    request: SplitManyToOneRequest,
    current_user: User = Depends(require_role(['accountant', 'admin']))
) -> SplitResponse:
    """
    Create a many-to-one split reconciliation (partial payments).

    🔒 **Requires:** accountant or admin role

    **Use case:** One expense paid in multiple installments.

    **Example:**
    - Expense: "Equipo de cómputo Dell" - $25,000
    - Payments:
      * Anticipo - $10,000 (10-ene)
      * Segundo pago - $10,000 (20-ene)
      * Finiquito - $5,000 (30-ene)

    **Process:**
    1. Validates that allocated amounts match expense total
    2. Creates split records for each movement
    3. Marks expense and all movements as reconciled with split type
    4. Returns split group ID for tracking

    **Requirements:**
    - At least 2 movements
    - Sum of movement amounts must equal expense amount (±$0.01 tolerance)
    - Expense must not be already reconciled (simple)
    - Movements must not be already reconciled (simple)
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        result = create_many_to_one_split(request, user_id=current_user.id, tenant_id=tenant_id)

        logger.info(
            f"✅ User {current_user.username} (tenant={tenant_id}) created many-to-one split {result.split_group_id}: "
            f"{len(request.movements)} movements → expense {request.expense_id}"
        )

        return result

    except ValueError as e:
        logger.error(f"Validation error creating many-to-one split: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error creating many-to-one split: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating split reconciliation: {str(e)}"
        )


# =====================================================
# QUERY SPLITS
# =====================================================

@router.get("/{split_group_id}", response_model=SplitDetailResponse)
async def get_split_details_endpoint(
    split_group_id: str,
    current_user: User = Depends(get_current_user)
) -> SplitDetailResponse:
    """
    Get detailed information about a specific split reconciliation.

    🔒 **Requires:** Authentication

    Returns:
    - Split type (one-to-many or many-to-one)
    - Status and completion
    - All associated expenses and movements with full details
    - Allocation amounts and percentages
    - Notes and metadata
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        details = get_split_details(split_group_id, tenant_id=tenant_id)

        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Split group {split_group_id} not found"
            )

        return details

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting split details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving split details: {str(e)}"
        )


@router.get("/", response_model=List[SplitDetailResponse])
async def list_splits_endpoint(
    split_type: Optional[SplitType] = None,
    is_complete: Optional[bool] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
) -> List[SplitDetailResponse]:
    """
    List all split reconciliations with optional filters.

    🔒 **Requires:** Authentication

    **Filters:**
    - `split_type`: Filter by type (one_to_many or many_to_one)
    - `is_complete`: Filter by completion status
    - `limit`: Maximum number of results (default 100)

    **Returns:**
    List of split details ordered by creation date (newest first)
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        splits = list_splits(split_type=split_type, is_complete=is_complete, limit=limit, tenant_id=tenant_id)
        return splits

    except Exception as e:
        logger.exception(f"Error listing splits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing splits: {str(e)}"
        )


# =====================================================
# MANAGE SPLITS
# =====================================================

@router.delete("/{split_group_id}", status_code=status.HTTP_200_OK)
async def undo_split_endpoint(
    split_group_id: str,
    current_user: User = Depends(require_role(['accountant', 'admin']))
):
    """
    Undo a split reconciliation (unlink all records).

    🔒 **Requires:** accountant or admin role

    **Warning:** This action:
    - Deletes all split records
    - Resets all expenses to 'pending' status
    - Resets all movements to 'unreconciled' status
    - Cannot be undone

    **Use case:** Correct an incorrect split before creating a new one.

    Returns:
    - success: True if split was undone
    - message: Confirmation message
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        success = undo_split(split_group_id, tenant_id=tenant_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Split group {split_group_id} not found"
            )

        logger.info(f"✅ User {current_user.username} (tenant={tenant_id}) undone split {split_group_id}")

        return {
            "success": True,
            "message": f"Split {split_group_id} has been undone. All linked records have been reset."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error undoing split: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error undoing split: {str(e)}"
        )


# =====================================================
# SUMMARY AND STATS
# =====================================================

@router.get("/summary/stats", response_model=SplitSummary)
async def get_split_summary_endpoint(
    current_user: User = Depends(get_current_user)
) -> SplitSummary:
    """
    Get summary statistics for all split reconciliations.

    🔒 **Requires:** Authentication

    Returns:
    - Total splits created
    - Complete vs incomplete splits
    - Total amount split
    - Breakdown by type (one-to-many vs many-to-one)
    - Recent splits (last 5)

    **Use case:** Dashboard overview of split reconciliation activity
    """
    try:
        # 🔐 Enforce tenant isolation
        tenant_id = enforce_tenant_isolation(current_user)

        summary = get_split_summary(tenant_id=tenant_id)
        return summary

    except Exception as e:
        logger.exception(f"Error getting split summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating split summary: {str(e)}"
        )
