"""
Models for Split Reconciliation (Multiple Matching)

Handles:
- One-to-Many: 1 bank movement → N expenses
- Many-to-One: N bank movements → 1 expense
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class SplitType(str, Enum):
    """Types of split reconciliation"""
    ONE_TO_MANY = "one_to_many"  # 1 movement → many expenses
    MANY_TO_ONE = "many_to_one"  # many movements → 1 expense


class SplitStatus(str, Enum):
    """Status of split reconciliation"""
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


# =====================================================
# REQUEST MODELS
# =====================================================

class SplitExpenseItem(BaseModel):
    """Single expense item in a split reconciliation"""
    expense_id: int = Field(..., description="ID of the expense")
    amount: float = Field(..., gt=0, description="Amount to allocate to this expense")
    notes: Optional[str] = Field(None, description="Optional notes for this allocation")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        # Round to 2 decimals
        return round(v, 2)


class SplitMovementItem(BaseModel):
    """Single movement item in a split reconciliation"""
    movement_id: int = Field(..., description="ID of the bank movement")
    amount: float = Field(..., gt=0, description="Amount to allocate from this movement")
    payment_number: Optional[int] = Field(None, description="Payment sequence number (e.g., 1, 2, 3)")
    notes: Optional[str] = Field(None, description="Optional notes for this payment")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return round(v, 2)


class SplitOneToManyRequest(BaseModel):
    """Request to create a one-to-many split reconciliation"""
    movement_id: int = Field(..., description="ID of the bank movement to split")
    movement_amount: float = Field(..., description="Total amount of the movement")
    expenses: List[SplitExpenseItem] = Field(..., min_length=2, description="List of expenses to allocate")
    notes: Optional[str] = Field(None, description="General notes for this split")
    company_id: str = Field(default="default", description="Company ID")

    @field_validator('expenses')
    @classmethod
    def validate_expenses(cls, v):
        if len(v) < 2:
            raise ValueError("At least 2 expenses required for split")

        # Check for duplicate expense IDs
        expense_ids = [e.expense_id for e in v]
        if len(expense_ids) != len(set(expense_ids)):
            raise ValueError("Duplicate expense IDs found")

        return v

    @field_validator('movement_amount')
    @classmethod
    def validate_movement_amount(cls, v):
        if v <= 0:
            raise ValueError("Movement amount must be positive")
        return round(v, 2)


class SplitManyToOneRequest(BaseModel):
    """Request to create a many-to-one split reconciliation"""
    expense_id: int = Field(..., description="ID of the expense")
    expense_amount: float = Field(..., description="Total amount of the expense")
    movements: List[SplitMovementItem] = Field(..., min_length=2, description="List of movements to allocate")
    notes: Optional[str] = Field(None, description="General notes for this split")
    company_id: str = Field(default="default", description="Company ID")

    @field_validator('movements')
    @classmethod
    def validate_movements(cls, v):
        if len(v) < 2:
            raise ValueError("At least 2 movements required for split")

        # Check for duplicate movement IDs
        movement_ids = [m.movement_id for m in v]
        if len(movement_ids) != len(set(movement_ids)):
            raise ValueError("Duplicate movement IDs found")

        return v

    @field_validator('expense_amount')
    @classmethod
    def validate_expense_amount(cls, v):
        if v <= 0:
            raise ValueError("Expense amount must be positive")
        return round(v, 2)


# =====================================================
# RESPONSE MODELS
# =====================================================

class SplitValidation(BaseModel):
    """Validation result for a split"""
    amounts_match: bool = Field(..., description="Whether allocated amounts match total")
    difference: float = Field(..., description="Difference between total and allocated (should be 0)")
    is_complete: bool = Field(..., description="Whether split is complete and valid")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    errors: List[str] = Field(default_factory=list, description="Error messages")


class SplitItemResponse(BaseModel):
    """Response for a single item in a split"""
    id: int
    expense_id: Optional[int] = None
    movement_id: Optional[int] = None
    allocated_amount: float
    percentage: float
    payment_number: Optional[int] = None
    notes: Optional[str] = None


class SplitResponse(BaseModel):
    """Response for a split reconciliation operation"""
    success: bool
    split_group_id: str
    reconciliation_type: SplitType
    created_at: datetime

    # Totals
    total_amount: float
    total_allocated: float

    # Counts
    expenses_count: Optional[int] = None
    movements_count: Optional[int] = None

    # Validation
    validation: SplitValidation

    # Details
    splits: List[SplitItemResponse]

    # Metadata
    notes: Optional[str] = None


class SplitDetailResponse(BaseModel):
    """Detailed response for a split group"""
    split_group_id: str
    split_type: SplitType
    status: SplitStatus
    created_at: datetime
    created_by: Optional[int] = None
    verified_at: Optional[datetime] = None

    # Total
    total_amount: float
    is_complete: bool

    # Items
    items: List[Dict[str, Any]]

    # Metadata
    notes: Optional[str] = None


class SplitSummary(BaseModel):
    """Summary of splits"""
    total_splits: int
    complete_splits: int
    incomplete_splits: int
    total_amount_split: float

    splits_by_type: Dict[str, int]
    recent_splits: List[SplitDetailResponse]


# =====================================================
# DATABASE MODELS (for internal use)
# =====================================================

class SplitRecord(BaseModel):
    """Database record for a split"""
    id: int
    split_group_id: str
    split_type: SplitType
    expense_id: Optional[int] = None
    movement_id: Optional[int] = None
    allocated_amount: float
    percentage: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    created_by: Optional[int] = None
    is_complete: bool = False
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


# =====================================================
# VALIDATION FUNCTIONS
# =====================================================

def validate_split_amounts(
    total_amount: float,
    allocated_items: Union[List[SplitExpenseItem], List[SplitMovementItem]],
    tolerance: float = 0.01
) -> SplitValidation:
    """
    Validate that allocated amounts match the total.

    Args:
        total_amount: Total amount to allocate
        allocated_items: List of items with amounts
        tolerance: Acceptable difference (default 0.01 = 1 cent)

    Returns:
        SplitValidation with results
    """
    total_allocated = sum(item.amount for item in allocated_items)
    difference = round(abs(total_amount - total_allocated), 2)

    amounts_match = difference <= tolerance
    is_complete = amounts_match

    warnings = []
    errors = []

    if difference > tolerance:
        if difference > 0:
            errors.append(
                f"Allocated amount (${total_allocated:.2f}) exceeds total (${total_amount:.2f}) by ${difference:.2f}"
            )
        else:
            errors.append(
                f"Allocated amount (${total_allocated:.2f}) is less than total (${total_amount:.2f}) by ${difference:.2f}"
            )

    # Check for zero allocations
    zero_allocations = [i for i, item in enumerate(allocated_items) if item.amount == 0]
    if zero_allocations:
        warnings.append(f"Found {len(zero_allocations)} items with zero allocation")

    # Check for very small allocations (< $1)
    small_allocations = [i for i, item in enumerate(allocated_items) if 0 < item.amount < 1]
    if small_allocations:
        warnings.append(f"Found {len(small_allocations)} items with allocation less than $1")

    return SplitValidation(
        amounts_match=amounts_match,
        difference=difference,
        is_complete=is_complete,
        warnings=warnings,
        errors=errors
    )


def calculate_percentages(
    items: Union[List[SplitExpenseItem], List[SplitMovementItem]],
    total_amount: float
) -> List[float]:
    """
    Calculate percentage allocation for each item.

    Args:
        items: List of items with amounts
        total_amount: Total amount

    Returns:
        List of percentages
    """
    if total_amount == 0:
        return [0.0] * len(items)

    return [round((item.amount / total_amount) * 100, 2) for item in items]


# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def generate_split_group_id(split_type: SplitType) -> str:
    """Generate unique split group ID"""
    from datetime import datetime
    import uuid

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]

    return f"split_{split_type.value}_{timestamp}_{unique_id}"
