"""
Purchase Orders API
Endpoints for creating, managing, and tracking purchase orders with budget control
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
import logging

from core.auth.jwt import get_current_user, User
from core.shared.unified_db_adapter import get_unified_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase_orders"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

# ========== LINE ITEMS ==========
class POLineItem(BaseModel):
    """Purchase Order Line Item for detailed product/service tracking"""
    line_number: int = Field(..., ge=1, description="Sequential line number (1, 2, 3...)")
    sku: Optional[str] = Field(None, max_length=100, description="SKU/Part Number")
    description: str = Field(..., min_length=1, description="Line item description")
    unit_of_measure: str = Field("PZA", max_length=20, description="Unit (PZA, KG, M, HR, etc.)")
    quantity: float = Field(..., gt=0, description="Quantity ordered")
    unit_price: float = Field(..., ge=0, description="Price per unit")
    clave_prod_serv: Optional[str] = Field(None, max_length=20, description="SAT product/service code")
    notes: Optional[str] = None


class POLineItemResponse(POLineItem):
    """PO Line Item with tracking quantities"""
    id: int
    line_total: float
    quantity_received: float = 0
    quantity_invoiced: float = 0
    created_at: datetime
    updated_at: datetime


# ========== INVOICE LINKING (MANY-TO-MANY) ==========
class POInvoiceLinkRequest(BaseModel):
    """Link a SAT invoice to a PO with B2B partial invoicing support"""
    sat_invoice_id: str = Field(..., description="SAT invoice UUID to link")
    invoice_type: str = Field(..., pattern="^(anticipo|parcial|finiquito|total)$",
                              description="anticipo=advance, parcial=partial, finiquito=final, total=full")
    invoice_amount: float = Field(..., gt=0, description="Amount from this invoice allocated to PO")
    covered_lines: Optional[dict] = Field(None, description="Optional: Which PO lines this invoice covers")
    notes: Optional[str] = None


class POInvoiceResponse(BaseModel):
    """Linked invoice information"""
    id: int
    sat_invoice_id: str
    invoice_type: str
    invoice_amount: float
    covered_lines: Optional[dict]
    linked_by: Optional[int]
    linked_at: datetime
    notes: Optional[str]


# ========== PURCHASE ORDER CREATE/UPDATE ==========
class PurchaseOrderCreate(BaseModel):
    project_id: Optional[int] = Field(None, description="Link to project for budget tracking")
    department_id: Optional[int] = Field(None, description="Department making the purchase")
    vendor_name: str = Field(..., min_length=1, max_length=255, description="Vendor/supplier name")
    vendor_rfc: Optional[str] = Field(None, max_length=13, description="Vendor RFC (tax ID)")
    vendor_email: Optional[str] = Field(None, max_length=255, description="Vendor email")
    vendor_phone: Optional[str] = Field(None, max_length=20, description="Vendor phone")
    description: str = Field(..., min_length=1, description="Purchase order description")
    total_amount: float = Field(..., gt=0, description="Total amount in MXN")
    currency: str = Field("MXN", pattern="^(MXN|USD|EUR)$", description="Currency code")
    notes: Optional[str] = None

    # B2B Enhancement: Optional line items
    lines: Optional[List[POLineItem]] = Field(None, description="Optional: Detailed line items for this PO")


class PurchaseOrderUpdate(BaseModel):
    project_id: Optional[int] = None
    department_id: Optional[int] = None
    vendor_name: Optional[str] = Field(None, min_length=1, max_length=255)
    vendor_rfc: Optional[str] = Field(None, max_length=13)
    vendor_email: Optional[str] = Field(None, max_length=255)
    vendor_phone: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = Field(None, min_length=1)
    total_amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, pattern="^(MXN|USD|EUR)$")
    notes: Optional[str] = None

    # Line items can be updated via separate endpoint
    lines: Optional[List[POLineItem]] = None


class PurchaseOrderApprove(BaseModel):
    notes: Optional[str] = None


class PurchaseOrderReject(BaseModel):
    rejection_reason: str = Field(..., min_length=1, description="Reason for rejection")


# DEPRECATED: Use POInvoiceLinkRequest for new multi-invoice pattern
class PurchaseOrderLinkInvoice(BaseModel):
    """DEPRECATED: Legacy single-invoice linking. Use POST /{po_id}/invoices instead."""
    sat_invoice_id: str = Field(..., description="SAT invoice UUID to link")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _convert_row_to_dict(row):
    """Convert psycopg2 RealDictRow to regular dict"""
    if row is None:
        return None
    return dict(row)


def _get_po_by_id(po_id: int, tenant_id: int):
    """Get purchase order by ID with tenant check"""
    db = get_unified_adapter()
    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT po.*,
                   u1.full_name as requester_name,
                   u2.full_name as approver_name,
                   p.name as project_name,
                   d.name as department_name
            FROM purchase_orders po
            LEFT JOIN users u1 ON po.requester_user_id = u1.id
            LEFT JOIN users u2 ON po.approver_user_id = u2.id
            LEFT JOIN projects p ON po.project_id = p.id
            LEFT JOIN departments d ON po.department_id = d.id
            WHERE po.id = %s AND po.tenant_id = %s
        """, (po_id, tenant_id))

        po = cursor.fetchone()
        if not po:
            return None

        po_dict = _convert_row_to_dict(po)

        # Fetch linked invoices (B2B multi-invoice pattern)
        cursor.execute("""
            SELECT poi.id, poi.sat_invoice_id, poi.invoice_type, poi.invoice_amount,
                   poi.covered_lines, poi.linked_by, poi.linked_at, poi.notes
            FROM po_invoices poi
            WHERE poi.po_id = %s
            ORDER BY poi.linked_at DESC
        """, (po_id,))

        invoices = cursor.fetchall()
        po_dict['linked_invoices'] = [_convert_row_to_dict(inv) for inv in invoices]
        po_dict['invoiced_count'] = len(po_dict['linked_invoices'])

        return po_dict


def _generate_po_number(tenant_id: int) -> str:
    """Generate unique PO number: PO-YYYY-NNN"""
    from datetime import datetime

    db = get_unified_adapter()
    with db.get_connection() as conn:
        cursor = conn.cursor()

        year = datetime.now().year

        # Get the latest PO number for this year
        cursor.execute("""
            SELECT po_number FROM purchase_orders
            WHERE tenant_id = %s
              AND po_number LIKE %s
            ORDER BY id DESC
            LIMIT 1
        """, (tenant_id, f"PO-{year}-%"))

        result = cursor.fetchone()

        if result:
            result_dict = _convert_row_to_dict(result)
            last_number = int(result_dict['po_number'].split('-')[-1])
            next_number = last_number + 1
        else:
            next_number = 1

        return f"PO-{year}-{next_number:03d}"


def _check_budget_availability(project_id: int, amount: float, po_id_to_exclude: Optional[int] = None):
    """
    Check if project has enough budget available for this PO
    Returns (available, remaining_budget, budget_info)

    Note: Budget check uses the corrected project_budget_summary view which accounts for:
    - committed: Approved POs not yet fully invoiced (total_amount - invoiced_amount)
    - spent: Invoiced amounts from POs (invoiced_amount) + manual expenses
    """
    db = get_unified_adapter()
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get project budget summary using the CORRECTED view
        cursor.execute("""
            SELECT budget_total, committed_mxn, spent_total_mxn, remaining_mxn
            FROM project_budget_summary
            WHERE project_id = %s
        """, (project_id,))

        budget = cursor.fetchone()

        if not budget:
            return False, 0, {"error": "Project not found"}

        budget_dict = _convert_row_to_dict(budget)

        # If updating an existing PO, add back its uncommitted amount to available budget
        # (The view already excludes invoiced portions, so we add back total_amount - invoiced_amount)
        if po_id_to_exclude:
            cursor.execute("""
                SELECT total_amount, invoiced_amount
                FROM purchase_orders
                WHERE id = %s AND status IN ('approved', 'partially_invoiced')
            """, (po_id_to_exclude,))

            existing_po = cursor.fetchone()
            if existing_po:
                existing_po_dict = _convert_row_to_dict(existing_po)
                uncommitted_amount = float(existing_po_dict['total_amount']) - float(existing_po_dict.get('invoiced_amount') or 0)
                budget_dict['remaining_mxn'] += uncommitted_amount

        remaining = float(budget_dict['remaining_mxn'] or 0)
        has_budget = remaining >= amount

        return has_budget, remaining, budget_dict


# ============================================================================
# PURCHASE ORDERS CRUD ENDPOINTS
# ============================================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    po: PurchaseOrderCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new Purchase Order in draft status.

    **Permission**: All authenticated users

    **Workflow**: draft → pending_approval → approved → invoiced

    **Response**: Created PO object with auto-generated PO number
    """
    try:
        logger.info(f"Creating PO for {po.vendor_name}, user={current_user.id}")

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Generate PO number
            po_number = _generate_po_number(current_user.tenant_id)

            # Insert PO
            cursor.execute("""
                INSERT INTO purchase_orders (
                    tenant_id, po_number, project_id, department_id,
                    requester_user_id, vendor_name, vendor_rfc, vendor_email, vendor_phone,
                    description, total_amount, currency, notes, status,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (
                current_user.tenant_id,
                po_number,
                po.project_id,
                po.department_id,
                current_user.id,
                po.vendor_name.strip(),
                po.vendor_rfc.strip() if po.vendor_rfc else None,
                po.vendor_email,
                po.vendor_phone,
                po.description,
                po.total_amount,
                po.currency,
                po.notes,
                'draft'
            ))

            result = cursor.fetchone()
            po_id = _convert_row_to_dict(result)['id']

            conn.commit()

            # Fetch created PO
            created_po = _get_po_by_id(po_id, current_user.tenant_id)

            logger.info(f"PO created: id={po_id}, po_number={po_number}")

            return created_po

    except Exception as e:
        logger.error(f"Error creating PO: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating purchase order: {str(e)}"
        )


@router.get("/")
async def list_purchase_orders(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    department_id: Optional[int] = Query(None, description="Filter by department"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """
    List all purchase orders for the current tenant.

    **Filters:**
    - status_filter: draft, pending_approval, approved, rejected, sent_to_vendor, received, invoiced, cancelled
    - project_id: Filter by project
    - department_id: Filter by department

    **Response**: Array of purchase orders
    """
    try:
        logger.info(f"Listing POs, user={current_user.id}, filters: status={status_filter}")

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT po.*,
                       u1.full_name as requester_name,
                       u2.full_name as approver_name,
                       p.name as project_name,
                       d.name as department_name
                FROM purchase_orders po
                LEFT JOIN users u1 ON po.requester_user_id = u1.id
                LEFT JOIN users u2 ON po.approver_user_id = u2.id
                LEFT JOIN projects p ON po.project_id = p.id
                LEFT JOIN departments d ON po.department_id = d.id
                WHERE po.tenant_id = %s
            """

            params = [current_user.tenant_id]

            # Apply filters
            if status_filter:
                query += " AND po.status = %s"
                params.append(status_filter)

            if project_id:
                query += " AND po.project_id = %s"
                params.append(project_id)

            if department_id:
                query += " AND po.department_id = %s"
                params.append(department_id)

            # Order and pagination
            query += " ORDER BY po.created_at DESC"
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cursor.execute(query, params)
            pos = cursor.fetchall()

            result = []
            for po in pos:
                po_dict = _convert_row_to_dict(po)
                result.append(po_dict)

            logger.info(f"Found {len(result)} purchase orders")

            return result

    except Exception as e:
        logger.error(f"Error listing POs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing purchase orders: {str(e)}"
        )


@router.get("/{po_id}")
async def get_purchase_order(
    po_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific purchase order by ID.

    **Response**: PO object with linked project/department/invoice info
    """
    try:
        logger.info(f"Getting PO {po_id}, user={current_user.id}")

        po = _get_po_by_id(po_id, current_user.tenant_id)

        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found"
            )

        # If linked to project, get budget info
        if po.get('project_id'):
            db = get_unified_adapter()
            with db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT budget_total, committed_mxn, spent_total_mxn, remaining_mxn
                    FROM project_budget_summary
                    WHERE project_id = %s
                """, (po['project_id'],))

                budget = cursor.fetchone()
                if budget:
                    po['project_budget'] = _convert_row_to_dict(budget)

        return po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PO {po_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting purchase order: {str(e)}"
        )


@router.put("/{po_id}")
async def update_purchase_order(
    po_id: int,
    po_update: PurchaseOrderUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a purchase order (only in draft status).

    **Permission**: Only the requester can update draft POs

    **Response**: Updated PO object
    """
    try:
        logger.info(f"Updating PO {po_id}, user={current_user.id}")

        existing_po = _get_po_by_id(po_id, current_user.tenant_id)

        if not existing_po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found"
            )

        # Only draft POs can be edited
        if existing_po['status'] != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update PO in status: {existing_po['status']}. Only draft POs can be edited."
            )

        # Permission check: only requester can edit
        if existing_po['requester_user_id'] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the requester can update this purchase order"
            )

        # Build update query
        update_fields = []
        params = []

        update_data = po_update.model_dump(exclude_unset=True)

        if not update_data:
            return existing_po

        for field, value in update_data.items():
            if field == 'vendor_name' and value:
                update_fields.append("vendor_name = %s")
                params.append(value.strip())
            elif field == 'vendor_rfc' and value:
                update_fields.append("vendor_rfc = %s")
                params.append(value.strip())
            elif field in ['vendor_email', 'vendor_phone', 'description', 'total_amount', 'currency', 'notes', 'project_id', 'department_id']:
                update_fields.append(f"{field} = %s")
                params.append(value)

        if not update_fields:
            return existing_po

        update_fields.append("updated_at = NOW()")

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            query = f"""
                UPDATE purchase_orders
                SET {', '.join(update_fields)}
                WHERE id = %s AND tenant_id = %s
            """
            params.extend([po_id, current_user.tenant_id])

            cursor.execute(query, params)
            conn.commit()

        updated_po = _get_po_by_id(po_id, current_user.tenant_id)

        logger.info(f"PO {po_id} updated successfully")

        return updated_po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating PO {po_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating purchase order: {str(e)}"
        )


@router.post("/{po_id}/submit")
async def submit_purchase_order(
    po_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Submit a draft PO for approval.

    **Permission**: Only the requester

    **Workflow**: draft → pending_approval

    **Response**: Updated PO object
    """
    try:
        logger.info(f"Submitting PO {po_id} for approval, user={current_user.id}")

        existing_po = _get_po_by_id(po_id, current_user.tenant_id)

        if not existing_po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found"
            )

        # Only draft POs can be submitted
        if existing_po['status'] != 'draft':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot submit PO in status: {existing_po['status']}. Only draft POs can be submitted."
            )

        # Permission check
        if existing_po['requester_user_id'] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the requester can submit this purchase order"
            )

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE purchase_orders
                SET status = 'pending_approval', updated_at = NOW()
                WHERE id = %s AND tenant_id = %s
            """, (po_id, current_user.tenant_id))

            conn.commit()

        updated_po = _get_po_by_id(po_id, current_user.tenant_id)

        logger.info(f"PO {po_id} submitted for approval")

        return updated_po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting PO {po_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting purchase order: {str(e)}"
        )


@router.post("/{po_id}/approve")
async def approve_purchase_order(
    po_id: int,
    approval: PurchaseOrderApprove,
    current_user: User = Depends(get_current_user)
):
    """
    Approve a PO (commits budget if linked to project).

    **Permission**: Manager, Admin, or Department Manager

    **Workflow**: pending_approval → approved

    **Budget Check**: Validates project has sufficient remaining budget

    **Response**: Approved PO object
    """
    try:
        logger.info(f"Approving PO {po_id}, user={current_user.id}")

        existing_po = _get_po_by_id(po_id, current_user.tenant_id)

        if not existing_po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found"
            )

        # Only pending POs can be approved
        if existing_po['status'] != 'pending_approval':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve PO in status: {existing_po['status']}. Only pending_approval POs can be approved."
            )

        # Permission check: manager or admin
        is_admin = 'admin' in (current_user.roles or [])
        is_manager = 'manager' in (current_user.roles or []) or 'contador' in (current_user.roles or [])

        if not (is_admin or is_manager):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only managers or admins can approve purchase orders"
            )

        # Budget check if linked to project
        if existing_po.get('project_id'):
            has_budget, remaining, budget_info = _check_budget_availability(
                existing_po['project_id'],
                float(existing_po['total_amount'])
            )

            if not has_budget:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient budget. Remaining: ${remaining:,.2f} MXN, Required: ${float(existing_po['total_amount']):,.2f} MXN"
                )

            logger.info(f"Budget check passed. Remaining after approval: ${remaining - float(existing_po['total_amount']):,.2f} MXN")

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Update notes if provided
            notes_update = ""
            notes_param = []
            if approval.notes:
                notes_update = ", notes = %s"
                notes_param = [approval.notes]

            cursor.execute(f"""
                UPDATE purchase_orders
                SET status = 'approved',
                    approver_user_id = %s,
                    approved_at = NOW(),
                    updated_at = NOW()
                    {notes_update}
                WHERE id = %s AND tenant_id = %s
            """, [current_user.id] + notes_param + [po_id, current_user.tenant_id])

            conn.commit()

        updated_po = _get_po_by_id(po_id, current_user.tenant_id)

        logger.info(f"PO {po_id} approved successfully")

        return updated_po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving PO {po_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving purchase order: {str(e)}"
        )


@router.post("/{po_id}/reject")
async def reject_purchase_order(
    po_id: int,
    rejection: PurchaseOrderReject,
    current_user: User = Depends(get_current_user)
):
    """
    Reject a PO.

    **Permission**: Manager, Admin, or Department Manager

    **Workflow**: pending_approval → rejected

    **Response**: Rejected PO object
    """
    try:
        logger.info(f"Rejecting PO {po_id}, user={current_user.id}")

        existing_po = _get_po_by_id(po_id, current_user.tenant_id)

        if not existing_po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found"
            )

        # Only pending POs can be rejected
        if existing_po['status'] != 'pending_approval':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject PO in status: {existing_po['status']}. Only pending_approval POs can be rejected."
            )

        # Permission check
        is_admin = 'admin' in (current_user.roles or [])
        is_manager = 'manager' in (current_user.roles or []) or 'contador' in (current_user.roles or [])

        if not (is_admin or is_manager):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only managers or admins can reject purchase orders"
            )

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE purchase_orders
                SET status = 'rejected',
                    approver_user_id = %s,
                    rejection_reason = %s,
                    rejected_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s AND tenant_id = %s
            """, (current_user.id, rejection.rejection_reason, po_id, current_user.tenant_id))

            conn.commit()

        updated_po = _get_po_by_id(po_id, current_user.tenant_id)

        logger.info(f"PO {po_id} rejected")

        return updated_po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting PO {po_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting purchase order: {str(e)}"
        )


@router.post("/{po_id}/invoices")
async def link_invoice_to_po(
    po_id: int,
    link_data: POInvoiceLinkRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Link a SAT invoice to an approved PO (B2B multi-invoice pattern).

    Supports multiple invoices per PO:
    - anticipo: 30-80% of PO total (initial payment)
    - parcial: partial payment during execution
    - finiquito: final settlement payment
    - total: single full payment (>95% of PO)

    **Permission**: Accountant, Manager, Admin

    **Response**: Updated PO object with all linked invoices
    """
    try:
        logger.info(f"Linking invoice {link_data.sat_invoice_id} (type: {link_data.invoice_type}) to PO {po_id}, user={current_user.id}")

        # 🔒 SECURITY: Fetch PO and verify ownership
        # First, get PO without tenant filter to check if it exists
        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, tenant_id
                FROM purchase_orders
                WHERE id = %s
            """, (po_id,))

            po_check = cursor.fetchone()

            if not po_check:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Purchase order {po_id} not found"
                )

            po_dict = _convert_row_to_dict(po_check)

            # 🔒 SECURITY: Validate user has access to this PO's tenant
            if po_dict['tenant_id'] != current_user.tenant_id:
                logger.warning(
                    f"SECURITY: User {current_user.email} (tenant_id={current_user.tenant_id}) "
                    f"attempted to link invoice to PO {po_id} (tenant_id={po_dict['tenant_id']})"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this purchase order"
                )

        # Now get full PO details
        existing_po = _get_po_by_id(po_id, current_user.tenant_id)

        if not existing_po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found"
            )

        # Only approved POs can have invoices linked
        if existing_po['status'] not in ('approved', 'partially_invoiced'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot link invoice to PO in status: {existing_po['status']}. Only approved or partially invoiced POs can receive invoices."
            )

        # Permission check
        is_admin = 'admin' in (current_user.roles or [])
        is_accountant = 'contador' in (current_user.roles or []) or 'accountant' in (current_user.roles or [])

        if not (is_admin or is_accountant):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only accountants or admins can link invoices to purchase orders"
            )

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Verify invoice exists and get details
            cursor.execute("""
                SELECT id, emisor_rfc, receptor_rfc, total
                FROM sat_invoices
                WHERE id = %s AND tenant_id = %s
            """, (link_data.sat_invoice_id, current_user.tenant_id))

            invoice = cursor.fetchone()

            if not invoice:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"SAT invoice {link_data.sat_invoice_id} not found"
                )

            invoice_dict = _convert_row_to_dict(invoice)

            # Validate invoice amount doesn't exceed PO total
            current_invoiced = existing_po.get('invoiced_amount', 0) or 0
            new_total_invoiced = current_invoiced + link_data.invoice_amount

            if new_total_invoiced > existing_po['total_amount'] * 1.05:  # Allow 5% tolerance
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invoice amount ${link_data.invoice_amount:,.2f} would exceed PO total ${existing_po['total_amount']:,.2f}. Already invoiced: ${current_invoiced:,.2f}"
                )

            # Check if invoice is already linked to this PO
            cursor.execute("""
                SELECT id FROM po_invoices
                WHERE po_id = %s AND sat_invoice_id = %s AND tenant_id = %s
            """, (po_id, link_data.sat_invoice_id, current_user.tenant_id))

            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invoice {link_data.sat_invoice_id} is already linked to this PO"
                )

            # Insert into po_invoices table
            cursor.execute("""
                INSERT INTO po_invoices (
                    po_id,
                    sat_invoice_id,
                    tenant_id,
                    invoice_type,
                    invoice_amount,
                    covered_lines,
                    notes,
                    linked_by,
                    linked_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
            """, (
                po_id,
                link_data.sat_invoice_id,
                current_user.tenant_id,
                link_data.invoice_type,
                link_data.invoice_amount,
                json.dumps(link_data.covered_lines) if link_data.covered_lines else None,
                link_data.notes,
                current_user.id
            ))

            link_id = cursor.fetchone()[0]

            conn.commit()

            logger.info(f"Created invoice link {link_id}: PO {po_id} ← Invoice {link_data.sat_invoice_id} (${link_data.invoice_amount:,.2f})")

        # Return updated PO with all linked invoices
        updated_po = _get_po_by_id(po_id, current_user.tenant_id)

        return updated_po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking invoice to PO {po_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error linking invoice: {str(e)}"
        )


@router.delete("/{po_id}/invoices/{invoice_link_id}")
async def unlink_invoice_from_po(
    po_id: int,
    invoice_link_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Unlink a SAT invoice from a PO.

    **Permission**: Accountant, Admin only

    **Response**: Updated PO object
    """
    try:
        logger.info(f"Unlinking invoice link {invoice_link_id} from PO {po_id}, user={current_user.id}")

        # Permission check (stricter than linking)
        is_admin = 'admin' in (current_user.roles or [])
        is_accountant = 'contador' in (current_user.roles or []) or 'accountant' in (current_user.roles or [])

        if not (is_admin or is_accountant):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only accountants or admins can unlink invoices"
            )

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Verify link exists and belongs to this PO
            cursor.execute("""
                SELECT sat_invoice_id
                FROM po_invoices
                WHERE id = %s AND po_id = %s AND tenant_id = %s
            """, (invoice_link_id, po_id, current_user.tenant_id))

            link = cursor.fetchone()

            if not link:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Invoice link {invoice_link_id} not found for PO {po_id}"
                )

            invoice_id = link[0]

            # Delete the link
            cursor.execute("""
                DELETE FROM po_invoices
                WHERE id = %s AND po_id = %s AND tenant_id = %s
            """, (invoice_link_id, po_id, current_user.tenant_id))

            conn.commit()

            logger.info(f"Unlinked invoice {invoice_id} from PO {po_id}")

        # Return updated PO
        updated_po = _get_po_by_id(po_id, current_user.tenant_id)

        return updated_po

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlinking invoice from PO {po_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error unlinking invoice: {str(e)}"
        )


@router.get("/invoices/unlinked")
async def get_unlinked_invoices(
    vendor_rfc: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get SAT invoices that are not yet linked to any PO for a specific vendor.

    Used by InvoiceLinkingPanel to suggest invoices for linking.

    **Query Parameters:**
    - vendor_rfc: RFC of the vendor to filter invoices

    **Response**: List of unlinked SAT invoices
    """
    try:
        logger.info(f"Getting unlinked invoices for vendor {vendor_rfc}, user={current_user.id}")

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get invoices from this vendor that are not yet linked to any PO
            cursor.execute("""
                SELECT
                    si.id,
                    si.emisor_nombre,
                    si.emisor_rfc,
                    si.receptor_nombre,
                    si.receptor_rfc,
                    si.total,
                    si.fecha,
                    si.folio,
                    si.serie,
                    si.tipo_comprobante,
                    si.uso_cfdi,
                    si.metodo_pago,
                    si.forma_pago
                FROM sat_invoices si
                WHERE si.tenant_id = %s
                    AND si.emisor_rfc = %s
                    AND si.tipo_comprobante = 'I'  -- Only Ingreso (income for vendor = expense for us)
                    AND NOT EXISTS (
                        SELECT 1
                        FROM po_invoices poi
                        WHERE poi.sat_invoice_id = si.id
                    )
                ORDER BY si.fecha DESC
                LIMIT 50
            """, (current_user.tenant_id, vendor_rfc))

            invoices = cursor.fetchall()

            invoices_list = [_convert_row_to_dict(inv) for inv in invoices]

            logger.info(f"Found {len(invoices_list)} unlinked invoices for vendor {vendor_rfc}")

            return {
                "vendor_rfc": vendor_rfc,
                "count": len(invoices_list),
                "invoices": invoices_list
            }

    except Exception as e:
        logger.error(f"Error getting unlinked invoices for vendor {vendor_rfc}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting unlinked invoices: {str(e)}"
        )


@router.post("/{po_id}/link-invoice")
async def link_sat_invoice_deprecated(
    po_id: int,
    link_data: PurchaseOrderLinkInvoice,
    current_user: User = Depends(get_current_user)
):
    """
    DEPRECATED: Use POST /{po_id}/invoices instead.

    This endpoint uses the old single-invoice pattern and will be removed in a future version.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use POST /api/purchase-orders/{po_id}/invoices instead with the new multi-invoice pattern."
    )


@router.get("/projects/{project_id}/budget-summary")
async def get_project_budget_summary(
    project_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get budget summary for a project including committed and spent amounts.

    **Response**: Budget breakdown with available funds
    """
    try:
        logger.info(f"Getting budget summary for project {project_id}, user={current_user.id}")

        db = get_unified_adapter()
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Verify project exists and belongs to tenant
            cursor.execute("""
                SELECT id, name, budget_mxn
                FROM projects
                WHERE id = %s AND tenant_id = %s
            """, (project_id, current_user.tenant_id))

            project = cursor.fetchone()

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project {project_id} not found"
                )

            project_dict = _convert_row_to_dict(project)

            # Get budget summary from view
            cursor.execute("""
                SELECT *
                FROM project_budget_summary
                WHERE project_id = %s
            """, (project_id,))

            summary = cursor.fetchone()
            summary_dict = _convert_row_to_dict(summary) if summary else {}

            return {
                "project": project_dict,
                "budget_summary": summary_dict
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting budget summary for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting budget summary: {str(e)}"
        )
