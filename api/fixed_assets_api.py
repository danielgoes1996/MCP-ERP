"""
Fixed Assets API - CRUD and management endpoints

Provides endpoints for:
- Creating fixed assets from invoices
- Listing assets with filters
- Getting asset details with depreciation history
- Adding additional costs (freight, installation)
- Updating asset information
- Disposing/retiring assets
- Generating depreciation reports

Author: System
Date: 2025-11-28
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

from core.shared.db_config import POSTGRES_CONFIG
from core.auth.unified import get_tenancy_context, TenancyContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixed-assets", tags=["Fixed Assets"])


# ============================================================================
# Pydantic Models
# ============================================================================

class AdditionalCost(BaseModel):
    """Additional cost associated with asset (freight, installation, etc.)"""
    concept: str = Field(..., description="Cost concept: flete, instalación, etc.")
    amount: Decimal = Field(..., gt=0, description="Cost amount")
    expense_id: Optional[int] = Field(None, description="Related expense ID")
    invoice_uuid: Optional[str] = None
    date: Optional[date] = None
    notes: Optional[str] = None


class CreateFixedAssetRequest(BaseModel):
    """Request to create new fixed asset from invoice"""
    # Link to invoice/expense
    invoice_session_id: Optional[str] = Field(None, description="Invoice classification session")
    purchase_expense_id: Optional[int] = Field(None, description="Manual expense ID")
    invoice_uuid: Optional[str] = None

    # Asset info
    description: str = Field(..., min_length=3, max_length=500)
    asset_class: str = Field(..., description="equipo_computo, vehiculos, mobiliario, etc.")
    asset_category: str = Field(..., description="SAT family: 156, 154, 155, etc.")

    # Purchase details
    purchase_date: date
    supplier_name: Optional[str] = None
    supplier_rfc: Optional[str] = None
    purchase_value: Decimal = Field(..., gt=0)
    additional_costs: List[AdditionalCost] = Field(default_factory=list)

    # Depreciation (from RAG service or manual)
    depreciation_rate_accounting: Decimal = Field(..., gt=0, le=100)
    depreciation_years_accounting: Decimal = Field(..., gt=0)
    depreciation_rate_fiscal: Decimal = Field(..., gt=0, le=100)
    depreciation_years_fiscal: Decimal = Field(..., gt=0)
    legal_basis: Optional[Dict[str, Any]] = None

    # Operational
    department: Optional[str] = None
    location: Optional[str] = None
    responsible_user_id: Optional[int] = None
    physical_tag: Optional[str] = None
    notes: Optional[str] = None


class UpdateFixedAssetRequest(BaseModel):
    """Request to update asset information"""
    description: Optional[str] = Field(None, min_length=3, max_length=500)
    department: Optional[str] = None
    location: Optional[str] = None
    responsible_user_id: Optional[int] = None
    physical_tag: Optional[str] = None
    notes: Optional[str] = None


class AddAdditionalCostRequest(BaseModel):
    """Request to add additional cost to existing asset"""
    concept: str
    amount: Decimal = Field(..., gt=0)
    expense_id: Optional[int] = None
    invoice_uuid: Optional[str] = None
    date: Optional[date] = None
    notes: Optional[str] = None


class DisposeAssetRequest(BaseModel):
    """Request to dispose/retire asset"""
    disposal_date: date
    disposal_method: str = Field(..., description="sale, donation, scrap, loss")
    disposal_value: Optional[Decimal] = Field(None, ge=0)
    disposal_reason: Optional[str] = None

    @validator('disposal_method')
    def validate_disposal_method(cls, v):
        valid_methods = ['sale', 'donation', 'scrap', 'loss', 'retirement']
        if v not in valid_methods:
            raise ValueError(f'disposal_method must be one of: {valid_methods}')
        return v


class FixedAssetResponse(BaseModel):
    """Fixed asset details"""
    id: int
    company_id: int
    tenant_id: int
    asset_code: str
    description: str
    asset_class: str
    asset_category: str

    # Purchase
    purchase_date: date
    supplier_name: Optional[str]
    supplier_rfc: Optional[str]
    invoice_uuid: Optional[str]

    # Financial
    purchase_value: Decimal
    total_cost: Decimal
    residual_value: Decimal

    # Depreciation accounting
    depreciation_rate_accounting: Decimal
    depreciation_years_accounting: Decimal
    depreciation_months_accounting: int
    accumulated_depreciation_accounting: Decimal
    months_depreciated_accounting: int
    book_value_accounting: Decimal

    # Depreciation fiscal
    depreciation_rate_fiscal: Decimal
    depreciation_years_fiscal: Decimal
    depreciation_months_fiscal: int
    accumulated_depreciation_fiscal: Decimal
    months_depreciated_fiscal: int
    book_value_fiscal: Decimal

    # Operational
    department: Optional[str]
    location: Optional[str]
    responsible_user_id: Optional[int]
    physical_tag: Optional[str]
    status: str

    # Metadata
    additional_costs: List[Dict[str, Any]]
    legal_basis: Optional[Dict[str, Any]]
    notes: Optional[str]

    # Audit
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=FixedAssetResponse, status_code=201)
async def create_fixed_asset(
    request: CreateFixedAssetRequest,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Create new fixed asset from invoice.

    Automatically:
    - Generates asset code (AF-YYYY-NNN)
    - Calculates total cost (purchase + additional costs)
    - Initializes depreciation tracking
    - Links to original invoice/expense
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # 1. Generate asset code
        cursor.execute(
            "SELECT generate_next_asset_code(%s, %s)",
            (tenancy_context.tenant_id, datetime.now().year)
        )
        asset_code = cursor.fetchone()['generate_next_asset_code']

        # 2. Calculate total cost
        additional_costs_total = sum(cost.amount for cost in request.additional_costs)
        total_cost = request.purchase_value + additional_costs_total

        # 3. Calculate depreciation months
        depreciation_months_accounting = int(request.depreciation_years_accounting * 12)
        depreciation_months_fiscal = int(request.depreciation_years_fiscal * 12)

        # 4. Prepare additional costs JSONB
        additional_costs_json = [
            {
                "id": idx + 1,
                "concept": cost.concept,
                "amount": float(cost.amount),
                "expense_id": cost.expense_id,
                "invoice_uuid": cost.invoice_uuid,
                "date": cost.date.isoformat() if cost.date else None,
                "notes": cost.notes
            }
            for idx, cost in enumerate(request.additional_costs)
        ]

        # 5. Insert asset
        cursor.execute("""
            INSERT INTO fixed_assets (
                company_id, tenant_id, asset_code, description,
                asset_class, asset_category,
                purchase_expense_id, invoice_uuid, purchase_date,
                supplier_name, supplier_rfc,
                purchase_value, additional_costs, total_cost, residual_value,
                depreciation_rate_accounting, depreciation_years_accounting,
                depreciation_months_accounting, accumulated_depreciation_accounting,
                months_depreciated_accounting,
                depreciation_rate_fiscal, depreciation_years_fiscal,
                depreciation_months_fiscal, accumulated_depreciation_fiscal,
                months_depreciated_fiscal,
                legal_basis,
                department, location, responsible_user_id, physical_tag,
                notes, created_by, status
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s,
                %s, %s, %s, %s,
                %s, %s, %s
            )
            RETURNING *
        """, (
            tenancy_context.tenant_id, tenancy_context.tenant_id, asset_code, request.description,
            request.asset_class, request.asset_category,
            request.purchase_expense_id, request.invoice_uuid, request.purchase_date,
            request.supplier_name, request.supplier_rfc,
            request.purchase_value, additional_costs_json, total_cost, 0,
            request.depreciation_rate_accounting, request.depreciation_years_accounting,
            depreciation_months_accounting, 0, 0,
            request.depreciation_rate_fiscal, request.depreciation_years_fiscal,
            depreciation_months_fiscal, 0, 0,
            request.legal_basis,
            request.department, request.location, request.responsible_user_id, request.physical_tag,
            request.notes, tenancy_context.user_id, 'active'
        ))

        asset_row = cursor.fetchone()
        conn.commit()

        # 6. Build response
        response = FixedAssetResponse(
            **asset_row,
            book_value_accounting=total_cost,  # Initial book value
            book_value_fiscal=total_cost
        )

        logger.info(
            f"Created fixed asset {asset_code} for tenant {tenancy_context.tenant_id}: "
            f"{request.description} (${total_cost})"
        )

        return response

    except Exception as e:
        logger.error(f"Error creating fixed asset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("", response_model=List[FixedAssetResponse])
async def list_fixed_assets(
    asset_class: Optional[str] = Query(None, description="Filter by asset class"),
    department: Optional[str] = Query(None, description="Filter by department"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in description"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    List fixed assets with filters.

    Returns assets with current book values calculated.
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # Build WHERE clause
        where_clauses = ["company_id = %s"]
        params = [tenancy_context.tenant_id]

        if asset_class:
            where_clauses.append("asset_class = %s")
            params.append(asset_class)

        if department:
            where_clauses.append("department = %s")
            params.append(department)

        if status:
            where_clauses.append("status = %s")
            params.append(status)

        if search:
            where_clauses.append("description ILIKE %s")
            params.append(f"%{search}%")

        where_sql = " AND ".join(where_clauses)

        # Query with calculated book values
        params.extend([limit, offset])
        cursor.execute(f"""
            SELECT
                *,
                (total_cost - accumulated_depreciation_accounting) as book_value_accounting,
                (total_cost - accumulated_depreciation_fiscal) as book_value_fiscal
            FROM fixed_assets
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, params)

        assets = cursor.fetchall()

        return [FixedAssetResponse(**asset) for asset in assets]

    except Exception as e:
        logger.error(f"Error listing fixed assets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/{asset_id}", response_model=FixedAssetResponse)
async def get_fixed_asset(
    asset_id: int,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """Get fixed asset details by ID"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                *,
                (total_cost - accumulated_depreciation_accounting) as book_value_accounting,
                (total_cost - accumulated_depreciation_fiscal) as book_value_fiscal
            FROM fixed_assets
            WHERE id = %s AND company_id = %s
        """, (asset_id, tenancy_context.tenant_id))

        asset = cursor.fetchone()

        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        return FixedAssetResponse(**asset)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fixed asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.post("/{asset_id}/additional-costs", response_model=FixedAssetResponse)
async def add_additional_cost(
    asset_id: int,
    request: AddAdditionalCostRequest,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Add additional cost to existing asset (freight, installation, etc.).

    Automatically recalculates total_cost and adjusts depreciation if asset
    hasn't been fully depreciated yet.
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # 1. Get current asset
        cursor.execute("""
            SELECT * FROM fixed_assets
            WHERE id = %s AND company_id = %s
        """, (asset_id, tenancy_context.tenant_id))

        asset = cursor.fetchone()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # 2. Prepare new cost
        additional_costs = asset['additional_costs'] or []
        new_cost_id = len(additional_costs) + 1

        new_cost = {
            "id": new_cost_id,
            "concept": request.concept,
            "amount": float(request.amount),
            "expense_id": request.expense_id,
            "invoice_uuid": request.invoice_uuid,
            "date": request.date.isoformat() if request.date else datetime.now().date().isoformat(),
            "notes": request.notes,
            "added_at": datetime.now().isoformat()
        }

        additional_costs.append(new_cost)

        # 3. Recalculate total cost
        new_total_cost = asset['purchase_value'] + sum(c['amount'] for c in additional_costs)

        # 4. Update asset
        cursor.execute("""
            UPDATE fixed_assets
            SET additional_costs = %s,
                total_cost = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *,
                (total_cost - accumulated_depreciation_accounting) as book_value_accounting,
                (total_cost - accumulated_depreciation_fiscal) as book_value_fiscal
        """, (additional_costs, new_total_cost, asset_id))

        updated_asset = cursor.fetchone()
        conn.commit()

        logger.info(
            f"Added additional cost to asset {asset['asset_code']}: "
            f"{request.concept} ${request.amount}"
        )

        return FixedAssetResponse(**updated_asset)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding additional cost: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.put("/{asset_id}", response_model=FixedAssetResponse)
async def update_fixed_asset(
    asset_id: int,
    request: UpdateFixedAssetRequest,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """Update asset information (location, department, responsible, etc.)"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # Build SET clause dynamically
        updates = []
        params = []

        if request.description is not None:
            updates.append("description = %s")
            params.append(request.description)

        if request.department is not None:
            updates.append("department = %s")
            params.append(request.department)

        if request.location is not None:
            updates.append("location = %s")
            params.append(request.location)

        if request.responsible_user_id is not None:
            updates.append("responsible_user_id = %s")
            params.append(request.responsible_user_id)

        if request.physical_tag is not None:
            updates.append("physical_tag = %s")
            params.append(request.physical_tag)

        if request.notes is not None:
            updates.append("notes = %s")
            params.append(request.notes)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clause = ", ".join(updates)
        params.extend([asset_id, tenancy_context.tenant_id])

        cursor.execute(f"""
            UPDATE fixed_assets
            SET {set_clause}, updated_at = NOW()
            WHERE id = %s AND company_id = %s
            RETURNING *,
                (total_cost - accumulated_depreciation_accounting) as book_value_accounting,
                (total_cost - accumulated_depreciation_fiscal) as book_value_fiscal
        """, params)

        updated_asset = cursor.fetchone()

        if not updated_asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        conn.commit()

        return FixedAssetResponse(**updated_asset)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.post("/{asset_id}/dispose", response_model=FixedAssetResponse)
async def dispose_asset(
    asset_id: int,
    request: DisposeAssetRequest,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Dispose or retire asset.

    Sets status to 'disposed' and records disposal details.
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE fixed_assets
            SET status = 'disposed',
                disposal_date = %s,
                disposal_method = %s,
                disposal_value = %s,
                disposal_reason = %s,
                updated_at = NOW()
            WHERE id = %s AND company_id = %s
            RETURNING *,
                (total_cost - accumulated_depreciation_accounting) as book_value_accounting,
                (total_cost - accumulated_depreciation_fiscal) as book_value_fiscal
        """, (
            request.disposal_date,
            request.disposal_method,
            request.disposal_value,
            request.disposal_reason,
            asset_id,
            tenancy_context.tenant_id
        ))

        disposed_asset = cursor.fetchone()

        if not disposed_asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        conn.commit()

        logger.info(
            f"Disposed asset {disposed_asset['asset_code']}: "
            f"{request.disposal_method} on {request.disposal_date}"
        )

        return FixedAssetResponse(**disposed_asset)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disposing asset {asset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()


@router.get("/{asset_id}/depreciation-history")
async def get_depreciation_history(
    asset_id: int,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """Get monthly depreciation history for asset"""
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # Verify asset belongs to tenant
        cursor.execute("""
            SELECT id FROM fixed_assets
            WHERE id = %s AND company_id = %s
        """, (asset_id, tenancy_context.tenant_id))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Asset not found")

        # Get history
        cursor.execute("""
            SELECT *
            FROM asset_depreciation_history
            WHERE asset_id = %s
            ORDER BY period_year DESC, period_month DESC
        """, (asset_id,))

        history = cursor.fetchall()

        return {
            "asset_id": asset_id,
            "history": history,
            "total_records": len(history)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting depreciation history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()
