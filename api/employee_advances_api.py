"""
API endpoints for Employee Advances (Anticipos/Préstamos)
🔒 Protected endpoints - Requires JWT authentication
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
import logging

from core.employee_advances_models import (
    CreateAdvanceRequest,
    ReimburseAdvanceRequest,
    UpdateAdvanceRequest,
    AdvanceResponse,
    AdvanceSummary,
    EmployeeAdvancesSummary,
    AdvanceStatus
)
from core.employee_advances_service import get_employee_advances_service
from core.auth_jwt import User, get_current_user, require_role, filter_by_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employee_advances", tags=["Employee Advances"])


# =====================================================
# CREATE ADVANCE
# =====================================================

@router.post("/", response_model=AdvanceResponse, status_code=status.HTTP_201_CREATED)
async def create_advance(
    request: CreateAdvanceRequest,
    current_user: User = Depends(get_current_user)
) -> AdvanceResponse:
    """
    Create a new employee advance

    **Use case:** Employee paid for a business expense with personal funds

    **Process:**
    1. Links expense to employee advance
    2. Marks expense as 'advance' (not reconcilable with bank)
    3. Tracks pending reimbursement amount

    **Example:**
    ```json
    {
      "employee_id": 123,
      "employee_name": "Juan Pérez",
      "expense_id": 10244,
      "advance_amount": 850.50,
      "payment_method": "Tarjeta personal BBVA",
      "notes": "Gasolina pagada con tarjeta personal"
    }
    ```
    """
    try:
        # 🔒 Authorization: Employees can only create advances for themselves
        if current_user.role == 'employee':
            if request.employee_id != current_user.employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Employees can only create advances for themselves"
                )

        service = get_employee_advances_service()
        result = service.create_advance(request)

        logger.info(f"✅ User {current_user.username} created advance {result.id} for employee {request.employee_name}")

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error creating advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error creating advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating advance: {str(e)}"
        )


# =====================================================
# REIMBURSE ADVANCE
# =====================================================

@router.post("/reimburse", response_model=AdvanceResponse)
async def reimburse_advance(
    request: ReimburseAdvanceRequest,
    current_user: User = Depends(require_role(['accountant', 'admin']))
) -> AdvanceResponse:
    """
    Reimburse an employee advance (partial or full)

    🔒 **Requires:** accountant or admin role

    **Use case:** Company reimburses employee for advance

    **Reimbursement types:**
    - `cash`: Cash payment
    - `transfer`: Bank transfer
    - `payroll`: Via payroll
    - `credit`: Credit note

    **Example:**
    ```json
    {
      "advance_id": 1,
      "reimbursement_amount": 850.50,
      "reimbursement_type": "transfer",
      "reimbursement_movement_id": 8181,
      "notes": "Transferencia SPEI realizada"
    }
    ```

    **Status after reimbursement:**
    - If full amount: status = `completed`
    - If partial: status = `partial`
    """
    try:
        service = get_employee_advances_service()
        result = service.reimburse_advance(request)

        logger.info(
            f"✅ User {current_user.username} reimbursed ${request.reimbursement_amount:.2f} "
            f"for advance {request.advance_id}. New status: {result.status}"
        )

        return result

    except ValueError as e:
        logger.error(f"Validation error reimbursing advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error reimbursing advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reimbursing advance: {str(e)}"
        )


# =====================================================
# QUERY ADVANCES
# =====================================================

@router.get("/{advance_id}", response_model=AdvanceResponse)
async def get_advance(
    advance_id: int,
    current_user: User = Depends(get_current_user)
) -> AdvanceResponse:
    """
    Get advance by ID

    🔒 **Authorization:**
    - Employees can only view their own advances
    - Accountants/Admins can view any advance
    """
    try:
        service = get_employee_advances_service()
        result = service.get_advance_by_id(advance_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Advance {advance_id} not found"
            )

        # 🔒 Employees can only view their own advances
        if current_user.role == 'employee':
            if result.employee_id != current_user.employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own advances"
                )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting advance: {str(e)}"
        )


@router.get("/", response_model=List[AdvanceResponse])
async def list_advances(
    status: Optional[AdvanceStatus] = None,
    employee_id: Optional[int] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
) -> List[AdvanceResponse]:
    """
    List employee advances with optional filters

    🔒 **Scope filtering:**
    - **Employees:** Can only see their own advances
    - **Accountants/Admins:** Can see all advances

    **Query parameters:**
    - `status`: Filter by status (pending, partial, completed, cancelled)
    - `employee_id`: Filter by employee
    - `limit`: Maximum results (default 100)

    **Returns:**
    List of advances ordered by creation date (newest first)
    """
    try:
        # 🔒 Apply scope filtering
        if current_user.role == 'employee':
            # Force filter to current user's employee_id
            employee_id = current_user.employee_id
            logger.info(f"Employee {current_user.username} viewing own advances (employee_id={employee_id})")

        service = get_employee_advances_service()
        results = service.list_advances(status=status, employee_id=employee_id, limit=limit)

        return results

    except Exception as e:
        logger.exception(f"Error listing advances: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing advances: {str(e)}"
        )


@router.get("/employee/{employee_id}/summary", response_model=EmployeeAdvancesSummary)
async def get_employee_summary(
    employee_id: int,
    current_user: User = Depends(get_current_user)
) -> EmployeeAdvancesSummary:
    """
    Get summary of advances for a specific employee

    🔒 **Authorization:**
    - Employees can only view their own summary
    - Accountants/Admins can view any employee's summary

    **Returns:**
    - Total advances count
    - Total amount advanced
    - Total reimbursed
    - Total pending
    - List of all advances
    """
    try:
        # 🔒 Employees can only view their own summary
        if current_user.role == 'employee':
            if employee_id != current_user.employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own summary"
                )

        service = get_employee_advances_service()
        result = service.get_advances_by_employee(employee_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting employee summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting employee summary: {str(e)}"
        )


@router.get("/summary/all", response_model=AdvanceSummary)
async def get_advances_summary(
    current_user: User = Depends(require_role(['accountant', 'admin']))
) -> AdvanceSummary:
    """
    Get summary of all employee advances

    🔒 **Requires:** accountant or admin role

    **Returns:**
    - Total advances count
    - Total amounts (advanced, reimbursed, pending)
    - Counts by status
    - Breakdown by employee
    - Recent advances (last 5)

    **Use case:** Dashboard overview
    """
    try:
        service = get_employee_advances_service()
        result = service.get_summary()

        logger.info(f"User {current_user.username} viewed advances summary")

        return result

    except Exception as e:
        logger.exception(f"Error getting advances summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting summary: {str(e)}"
        )


# =====================================================
# UPDATE/DELETE ADVANCES
# =====================================================

@router.patch("/{advance_id}", response_model=AdvanceResponse)
async def update_advance(
    advance_id: int,
    request: UpdateAdvanceRequest,
    current_user: User = Depends(require_role(['accountant', 'admin']))
) -> AdvanceResponse:
    """
    Update an advance

    🔒 **Requires:** accountant or admin role

    **Updatable fields:**
    - employee_name
    - payment_method
    - notes
    - status (use with caution)
    """
    try:
        service = get_employee_advances_service()
        result = service.update_advance(advance_id, request)

        logger.info(f"User {current_user.username} updated advance {advance_id}")

        return result

    except ValueError as e:
        logger.error(f"Validation error updating advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error updating advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating advance: {str(e)}"
        )


@router.delete("/{advance_id}", response_model=AdvanceResponse)
async def cancel_advance(
    advance_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(require_role(['accountant', 'admin']))
) -> AdvanceResponse:
    """
    Cancel an advance

    🔒 **Requires:** accountant or admin role

    **Restrictions:**
    - Can only cancel if not yet reimbursed
    - Resets expense bank_status to 'pending'

    **Query parameters:**
    - `reason`: Reason for cancellation (optional)
    """
    try:
        service = get_employee_advances_service()
        result = service.cancel_advance(advance_id, reason)

        logger.info(f"User {current_user.username} cancelled advance {advance_id}")

        return result

    except ValueError as e:
        logger.error(f"Validation error cancelling advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error cancelling advance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling advance: {str(e)}"
        )


# =====================================================
# PENDING REIMBURSEMENTS
# =====================================================

@router.get("/pending/all", response_model=List[AdvanceResponse])
async def get_pending_reimbursements(
    current_user: User = Depends(require_role(['accountant', 'admin']))
) -> List[AdvanceResponse]:
    """
    Get all pending reimbursements (status = pending or partial)

    🔒 **Requires:** accountant or admin role

    **Use case:** Accounts payable - see what needs to be reimbursed

    **Returns:**
    List of advances that have pending amounts to reimburse
    """
    try:
        service = get_employee_advances_service()

        # Get pending and partial advances
        pending = service.list_advances(status=AdvanceStatus.PENDING, limit=1000)
        partial = service.list_advances(status=AdvanceStatus.PARTIAL, limit=1000)

        results = pending + partial

        # Sort by pending amount (highest first)
        results.sort(key=lambda x: x.pending_amount, reverse=True)

        logger.info(f"User {current_user.username} viewed {len(results)} pending reimbursements")

        return results

    except Exception as e:
        logger.exception(f"Error getting pending reimbursements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting pending reimbursements: {str(e)}"
        )
