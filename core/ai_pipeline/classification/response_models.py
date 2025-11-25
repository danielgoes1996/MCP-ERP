"""
Pydantic models for LLM response validation.

This module provides strict validation schemas for AI classification responses,
preventing invalid outputs and ensuring data integrity.

Created: 2025-11-15
Purpose: Hardened validation for production scalability
"""

from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Optional


class FamilyCode(str, Enum):
    """Valid SAT family codes (100-800)."""
    ACTIVO = "100"
    PASIVO = "200"
    CAPITAL = "300"
    INGRESOS = "400"
    COSTO_VENTAS = "500"
    GASTOS_OPERACION = "600"
    GASTOS_FINANCIEROS = "700"
    OTROS = "800"


class FamilyClassificationResponse(BaseModel):
    """
    Strict validation model for Phase 1 (family-level) classification.

    Ensures LLM responses conform to expected schema and prevents:
    - Invalid family codes (must be 100-800)
    - Out-of-range confidence scores
    - Missing required fields
    - Type mismatches

    Example:
        >>> response = FamilyClassificationResponse(
        ...     familia_codigo="600",
        ...     familia_nombre="GASTOS DE OPERACIÓN",
        ...     confianza=0.92,
        ...     razonamiento="Gasto operativo mensual"
        ... )
    """

    familia_codigo: FamilyCode = Field(
        ...,
        description="SAT family code (100-800)"
    )

    familia_nombre: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Family name in Spanish"
    )

    confianza: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )

    razonamiento: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Brief explanation for the classification"
    )

    @validator('familia_codigo', pre=True)
    def validate_family_code(cls, v):
        """Ensure family code is valid string format."""
        if isinstance(v, str):
            # Remove any whitespace
            v = v.strip()
            # Ensure it's a valid enum value
            if v not in [e.value for e in FamilyCode]:
                raise ValueError(f"Invalid family code: {v}. Must be one of {[e.value for e in FamilyCode]}")
        return v

    @validator('familia_nombre')
    def validate_family_name_uppercase(cls, v):
        """Ensure family name is uppercase (SAT convention)."""
        return v.upper()

    @validator('confianza')
    def validate_confidence_precision(cls, v):
        """Round confidence to 2 decimal places."""
        return round(v, 2)

    class Config:
        use_enum_values = True  # Store enum values as strings in dict


class SATClassificationResponse(BaseModel):
    """
    Strict validation model for Phase 2-3 (detailed SAT code) classification.

    Ensures LLM responses conform to expected schema for detailed classification.

    Example:
        >>> response = SATClassificationResponse(
        ...     family_code="600",
        ...     sat_account_code="601.48",
        ...     confidence_family=0.95,
        ...     confidence_sat=0.92,
        ...     explanation_short="Combustible para vehículos",
        ...     explanation_detail="Clasificado como gasto de operación..."
        ... )
    """

    family_code: str = Field(
        ...,
        pattern=r'^\d{3}$',
        description="3-digit family code (e.g., 600)"
    )

    sat_account_code: str = Field(
        ...,
        pattern=r'^\d{3}\.\d{2}$',
        description="SAT account code with decimal (e.g., 601.48)"
    )

    confidence_family: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for family classification"
    )

    confidence_sat: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for detailed SAT code"
    )

    explanation_short: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Brief explanation (1-2 sentences)"
    )

    explanation_detail: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Detailed explanation with reasoning"
    )

    @validator('sat_account_code')
    def validate_sat_code_has_decimal(cls, v):
        """Ensure SAT code has decimal point."""
        if '.' not in v:
            raise ValueError(f'SAT code must have decimal point (e.g., 601.48, not 601): {v}')
        return v

    @validator('sat_account_code')
    def validate_family_matches_sat(cls, v, values):
        """Ensure family code matches the SAT code prefix."""
        if 'family_code' in values:
            sat_prefix = v.split('.')[0]
            family_code = values['family_code']

            # Family code should match first digit (e.g., 600 and 601.48 both start with 6)
            # Or for exact match validation: sat_prefix should be within the family's range
            # E.g., 600-699 all belong to family 600
            if sat_prefix[0] != family_code[0]:
                raise ValueError(
                    f"Family code mismatch: family_code={family_code} "
                    f"but sat_account_code={v} (first digit doesn't match)"
                )
        return v

    @validator('confidence_family', 'confidence_sat')
    def validate_confidence_precision(cls, v):
        """Round confidence to 2 decimal places."""
        return round(v, 2)

    @validator('confidence_sat')
    def validate_sat_confidence_lower_or_equal(cls, v, values):
        """SAT confidence should typically be <= family confidence."""
        if 'confidence_family' in values:
            # Allow some tolerance (SAT can be slightly higher in some cases)
            if v > values['confidence_family'] + 0.05:
                # Log warning but don't fail
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"SAT confidence ({v}) is significantly higher than family confidence "
                    f"({values['confidence_family']}). This is unusual."
                )
        return v


class ClassificationError(BaseModel):
    """
    Model for classification errors.

    Used when LLM fails to provide valid classification.
    """

    error_type: str = Field(
        ...,
        description="Type of error (e.g., 'validation_error', 'parsing_error')"
    )

    error_message: str = Field(
        ...,
        description="Human-readable error message"
    )

    raw_response: Optional[str] = Field(
        None,
        description="Raw LLM response that failed validation"
    )

    retry_recommended: bool = Field(
        default=True,
        description="Whether retrying the classification is recommended"
    )


# Export all models
__all__ = [
    'FamilyCode',
    'FamilyClassificationResponse',
    'SATClassificationResponse',
    'ClassificationError'
]
