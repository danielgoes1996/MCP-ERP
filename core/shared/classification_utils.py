"""Canonical classification merge utilities.

This module enforces the SINGLE SOURCE OF TRUTH rules for accounting classifications:

GOLDEN RULES:
1. expense_invoices.accounting_classification = SINGLE SOURCE OF TRUTH
2. sat_invoices.accounting_classification = AUDIT TRAIL (historical snapshot)
3. In conflicts: ALWAYS expense_invoices wins
4. Status priority: corrected > confirmed > pending > None

Created: 2025-01-13
Purpose: Centralize classification merge logic to prevent inconsistencies
"""

from typing import Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ClassificationStatus:
    """Classification status constants"""
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CORRECTED = 'corrected'


# Status priority from highest to lowest
STATUS_PRIORITY = {
    ClassificationStatus.CORRECTED: 3,
    ClassificationStatus.CONFIRMED: 2,
    ClassificationStatus.PENDING: 1,
    None: 0
}


def should_update_classification(
    existing: Optional[Dict],
    new: Dict
) -> bool:
    """
    Determine if a new classification should replace an existing one.

    This enforces the priority rule: corrected > confirmed > pending

    Args:
        existing: Current classification (or None if no classification exists)
        new: New classification to potentially apply

    Returns:
        True if new classification should replace existing, False otherwise

    Examples:
        >>> should_update_classification(None, {'status': 'pending'})
        True  # No existing, always allow

        >>> should_update_classification(
        ...     {'status': 'confirmed'},
        ...     {'status': 'pending'}
        ... )
        False  # Don't downgrade from confirmed to pending

        >>> should_update_classification(
        ...     {'status': 'pending'},
        ...     {'status': 'confirmed'}
        ... )
        True  # Upgrade from pending to confirmed OK
    """
    if not existing:
        # No existing classification → always allow new one
        return True

    existing_status = existing.get('status')
    new_status = new.get('status')

    existing_priority = STATUS_PRIORITY.get(existing_status, 0)
    new_priority = STATUS_PRIORITY.get(new_status, 0)

    # Only allow if new has equal or higher priority
    should_update = new_priority >= existing_priority

    if not should_update:
        logger.warning(
            f"Attempted to downgrade classification from '{existing_status}' to '{new_status}' - blocked"
        )

    return should_update


def merge_classification(
    existing: Optional[Dict],
    new: Optional[Dict],
    override: bool = False
) -> Optional[Dict]:
    """
    Merge new classification with existing one following priority rules.

    This is the CANONICAL function for combining classifications.
    Use this before any UPDATE to expense_invoices.accounting_classification.

    Args:
        existing: Current classification (or None)
        new: New classification to apply (or None)
        override: If True, ignore priority rules and force update (USE WITH CAUTION)

    Returns:
        The classification that should be stored (either existing or new), or None

    Examples:
        >>> merge_classification(
        ...     {'status': 'confirmed', 'sat_account_code': '601.84'},
        ...     {'status': 'pending', 'sat_account_code': '603.12'}
        ... )
        {'status': 'confirmed', 'sat_account_code': '601.84'}  # Keeps confirmed

        >>> merge_classification(
        ...     {'status': 'pending', 'sat_account_code': '601.84'},
        ...     {'status': 'confirmed', 'sat_account_code': '601.84'}
        ... )
        {'status': 'confirmed', ...}  # Upgrades to confirmed
    """
    # Handle None cases
    if not new:
        return existing

    if not existing:
        return new

    if override:
        logger.warning("merge_classification called with override=True - bypassing priority rules")
        return new

    if should_update_classification(existing, new):
        # Preserve metadata from existing if not in new
        merged = {**existing, **new}

        # Add merge metadata (with underscore prefix for internal tracking)
        merged['merged_at'] = datetime.utcnow().isoformat()
        merged['previous_code'] = existing.get('sat_account_code')
        merged['previous_status'] = existing.get('status')

        return merged
    else:
        # Keep existing (higher priority)
        return existing


def validate_classification(classification: Dict) -> bool:
    """
    Validate that a classification dict has required fields.

    Args:
        classification: Classification dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ['sat_account_code', 'status']

    for field in required_fields:
        if field not in classification:
            logger.error(f"Invalid classification: missing '{field}' field")
            return False

    valid_statuses = [
        ClassificationStatus.PENDING,
        ClassificationStatus.CONFIRMED,
        ClassificationStatus.CORRECTED
    ]

    if classification['status'] not in valid_statuses:
        logger.error(f"Invalid classification status: '{classification['status']}'")
        return False

    return True


def format_classification_for_audit(
    classification: Dict,
    session_id: Optional[str] = None,
    invoice_id: Optional[int] = None
) -> str:
    """
    Format classification for audit logging.

    Args:
        classification: Classification dict
        session_id: Optional session ID
        invoice_id: Optional invoice ID

    Returns:
        Human-readable string for logging
    """
    sat_code = classification.get('sat_account_code', 'UNKNOWN')
    status = classification.get('status', 'UNKNOWN')
    confidence = classification.get('confidence_sat', 0)

    base = f"SAT={sat_code}, status={status}, confidence={confidence:.2%}"

    if session_id:
        base += f", session={session_id}"

    if invoice_id:
        base += f", invoice_id={invoice_id}"

    return base
