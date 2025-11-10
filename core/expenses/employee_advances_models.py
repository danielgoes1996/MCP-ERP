"""
Models for Employee Advances (Anticipos/Préstamos)

Handles expenses paid with personal funds that need reimbursement.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class AdvanceStatus(str, Enum):
    """Status of employee advance"""
    PENDING = "pending"           # Waiting for reimbursement
    PARTIAL = "partial"           # Partially reimbursed
    COMPLETED = "completed"       # Fully reimbursed
    CANCELLED = "cancelled"       # Advance cancelled


class ReimbursementType(str, Enum):
    """Type of reimbursement"""
    PENDING = "pending"           # Not yet decided
    CASH = "cash"                 # Cash payment
    TRANSFER = "transfer"         # Bank transfer
    PAYROLL = "payroll"          # Via payroll deduction
    CREDIT = "credit"            # Credit note


# =====================================================
# REQUEST MODELS
# =====================================================

class CreateAdvanceRequest(BaseModel):
    """Request to create an employee advance"""
    employee_id: int = Field(..., description="ID of employee")
    employee_name: str = Field(..., description="Name of employee")
    expense_id: int = Field(..., description="ID of the expense paid with personal funds")
    advance_amount: float = Field(..., gt=0, description="Amount advanced by employee")
    advance_date: datetime = Field(default_factory=datetime.utcnow, description="Date of advance")
    payment_method: Optional[str] = Field(None, description="How employee paid (cash, personal card, etc.)")
    notes: Optional[str] = Field(None, description="Additional notes")

    @field_validator('advance_amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Advance amount must be positive")
        return round(v, 2)


class ReimburseAdvanceRequest(BaseModel):
    """Request to reimburse (partially or fully) an advance"""
    advance_id: int = Field(..., description="ID of the advance to reimburse")
    reimbursement_amount: float = Field(..., gt=0, description="Amount being reimbursed")
    reimbursement_type: ReimbursementType = Field(..., description="Method of reimbursement")
    reimbursement_date: datetime = Field(default_factory=datetime.utcnow, description="Date of reimbursement")
    reimbursement_movement_id: Optional[int] = Field(None, description="Bank movement ID if via transfer")
    notes: Optional[str] = Field(None, description="Notes about this reimbursement")

    @field_validator('reimbursement_amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Reimbursement amount must be positive")
        return round(v, 2)

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


class UpdateAdvanceRequest(BaseModel):
    """Request to update an advance"""
    employee_name: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[AdvanceStatus] = None

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


# =====================================================
# RESPONSE MODELS
# =====================================================

class AdvanceResponse(BaseModel):
    """Response for a single advance"""
    id: int
    employee_id: int
    employee_name: str
    expense_id: int
    advance_amount: float
    reimbursed_amount: float
    pending_amount: float
    reimbursement_type: str
    advance_date: str  # Changed to str to handle date formats
    reimbursement_date: Optional[str] = None
    status: str
    reimbursement_movement_id: Optional[int]
    notes: Optional[str]
    payment_method: Optional[str]
    created_at: str  # Changed to str
    updated_at: Optional[str] = None

    # Related data
    expense_description: Optional[str] = None
    expense_category: Optional[str] = None
    expense_date: Optional[str] = None  # Changed to str

    model_config = ConfigDict(from_attributes=True, use_enum_values=True, protected_namespaces=())


class AdvanceSummary(BaseModel):
    """Summary of employee advances"""
    total_advances: int
    total_amount_advanced: float
    total_reimbursed: float
    total_pending: float

    pending_count: int
    partial_count: int
    completed_count: int

    by_employee: List[dict] = Field(default_factory=list)
    recent_advances: List[AdvanceResponse] = Field(default_factory=list)


class ReimbursementHistoryItem(BaseModel):
    """Single reimbursement entry in history"""
    advance_id: int
    employee_name: str
    expense_description: str
    reimbursement_amount: float
    reimbursement_type: str
    reimbursement_date: datetime
    notes: Optional[str]


class EmployeeAdvancesSummary(BaseModel):
    """Summary for a specific employee"""
    employee_id: int
    employee_name: str
    total_advances: int
    total_amount_advanced: float
    total_reimbursed: float
    total_pending: float
    advances: List[AdvanceResponse] = Field(default_factory=list)


# =====================================================
# VALIDATION MODELS
# =====================================================

class AdvanceValidation(BaseModel):
    """Validation result for an advance"""
    is_valid: bool
    can_reimburse: bool
    max_reimbursement_amount: float
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


def validate_reimbursement(
    advance: AdvanceResponse,
    reimbursement_amount: float
) -> AdvanceValidation:
    """
    Validate a reimbursement request

    Args:
        advance: The advance being reimbursed
        reimbursement_amount: Amount to reimburse

    Returns:
        AdvanceValidation with results
    """
    warnings = []
    errors = []
    is_valid = True
    can_reimburse = True

    # Check if already fully reimbursed
    if advance.status == AdvanceStatus.COMPLETED:
        errors.append("Advance is already fully reimbursed")
        is_valid = False
        can_reimburse = False

    # Check if cancelled
    if advance.status == AdvanceStatus.CANCELLED:
        errors.append("Advance is cancelled")
        is_valid = False
        can_reimburse = False

    # Check reimbursement amount
    pending = advance.pending_amount
    if reimbursement_amount > pending:
        errors.append(
            f"Reimbursement amount (${reimbursement_amount:.2f}) exceeds pending amount (${pending:.2f})"
        )
        is_valid = False

    if reimbursement_amount <= 0:
        errors.append("Reimbursement amount must be positive")
        is_valid = False

    # Warnings
    if reimbursement_amount < pending:
        warnings.append(
            f"Partial reimbursement: ${reimbursement_amount:.2f} of ${pending:.2f} pending"
        )

    return AdvanceValidation(
        is_valid=is_valid,
        can_reimburse=can_reimburse,
        max_reimbursement_amount=pending,
        warnings=warnings,
        errors=errors
    )
