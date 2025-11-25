"""
Global classification guardrails and validation rules.

These rules enforce data integrity and business logic for invoice classifications.
They are applied before saving classifications to the database.
"""

from typing import Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)


def validate_classification_before_save(
    classification: Dict[str, Any],
    invoice: Optional[Dict[str, Any]] = None,
    existing: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Global validation rules for classifications.

    Args:
        classification: The new classification to validate
        invoice: Invoice data (optional, for additional validation)
        existing: Existing classification (optional, for priority checking)

    Returns:
        (is_valid, error_message): True if valid, False with error message otherwise
    """

    # Rule 1: Only classify CFDI invoices (must have UUID)
    if invoice:
        if not invoice.get('cfdi_uuid'):
            return False, "Cannot classify non-CFDI expenses (missing cfdi_uuid)"

    # Rule 2: SAT code must be present and valid format
    sat_code = classification.get('sat_account_code')
    if not sat_code:
        return False, "sat_account_code is required"

    # Basic format validation (SAT codes are like "601", "613.01", "614.02.01")
    if not isinstance(sat_code, str) or not sat_code.replace('.', '').isdigit():
        return False, f"Invalid SAT code format: {sat_code}"

    # Rule 3: Never override 'corrected' status with lower priority
    if existing and existing.get('status') == 'corrected':
        new_status = classification.get('status')
        if new_status not in ['corrected', None]:
            # Allow None to preserve existing status during merge
            logger.warning(
                f"Attempted to override corrected classification with status={new_status}. "
                "This is not allowed unless explicitly correcting again."
            )
            return False, "Cannot override corrected classification with lower priority status"

    # Rule 4: Low confidence should trigger review flag
    confidence = classification.get('confidence_sat', 0)
    if isinstance(confidence, (int, float)) and confidence < 0.30:
        if 'needs_review' not in classification:
            classification['needs_review'] = True
        if 'review_reason' not in classification:
            classification['review_reason'] = "Low confidence classification"
        logger.info(f"Flagged classification for review (confidence={confidence:.2f})")

    # Rule 5: Confidence must be between 0 and 1
    if confidence is not None:
        try:
            conf_float = float(confidence)
            if not (0.0 <= conf_float <= 1.0):
                return False, f"Confidence must be between 0.0 and 1.0, got {conf_float}"
        except (ValueError, TypeError):
            return False, f"Invalid confidence value: {confidence}"

    # Rule 6: Status must be one of the allowed values
    allowed_statuses = ['pending', 'pending_confirmation', 'confirmed', 'corrected', 'not_classified']
    status = classification.get('status')
    if status and status not in allowed_statuses:
        return False, f"Invalid status: {status}. Must be one of {allowed_statuses}"

    return True, None


def merge_classification(
    existing: Optional[Dict[str, Any]],
    new: Dict[str, Any],
    override: bool = False
) -> Dict[str, Any]:
    """
    Merge new classification with existing, respecting priority rules.

    Priority hierarchy (highest to lowest):
    1. corrected (accountant corrections always win)
    2. confirmed (accountant confirmations)
    3. pending_confirmation (AI suggestions awaiting review)
    4. pending (initial state)
    5. not_classified (fallback)

    Args:
        existing: Existing classification dict (or None)
        new: New classification dict to merge
        override: If True, bypass priority rules and force override

    Returns:
        Merged classification dict
    """
    if not existing or override:
        return new.copy()

    # Priority mapping
    priority = {
        'corrected': 5,
        'confirmed': 4,
        'pending_confirmation': 3,
        'pending': 2,
        'not_classified': 1,
        None: 0
    }

    existing_status = existing.get('status')
    new_status = new.get('status')

    existing_priority = priority.get(existing_status, 0)
    new_priority = priority.get(new_status, 0)

    # If new has higher priority, use new
    if new_priority > existing_priority:
        logger.info(
            f"Applying new classification (priority {new_priority} > {existing_priority})"
        )
        return new.copy()

    # If same priority or lower, keep existing but merge non-conflicting fields
    logger.info(
        f"Keeping existing classification (priority {existing_priority} >= {new_priority})"
    )
    merged = existing.copy()

    # Merge metadata fields that don't conflict with priority
    for key in ['explanation_short', 'explanation_detail', 'model_version', 'prompt_version']:
        if key in new and key not in merged:
            merged[key] = new[key]

    return merged


def is_valid_sat_code(sat_code: str) -> bool:
    """
    Basic validation for SAT account codes.

    SAT codes follow pattern: XXX or XXX.XX or XXX.XX.XX
    where XXX are digits.

    Args:
        sat_code: SAT account code to validate

    Returns:
        True if valid format, False otherwise
    """
    if not isinstance(sat_code, str):
        return False

    # Remove dots and check if all digits
    if not sat_code.replace('.', '').isdigit():
        return False

    # Check structure: must be 3, 6, or 9 digits (plus dots)
    parts = sat_code.split('.')
    if len(parts) > 3:
        return False

    for part in parts:
        if not part.isdigit():
            return False
        if len(part) < 1 or len(part) > 3:
            return False

    return True


def should_auto_approve(classification: Dict[str, Any], company_settings: Optional[Dict[str, Any]] = None) -> bool:
    """
    Determine if classification should be auto-approved based on confidence and company settings.

    Args:
        classification: Classification dict with confidence_sat
        company_settings: Company settings with auto_approve_threshold (optional)

    Returns:
        True if should auto-approve, False otherwise
    """
    confidence = classification.get('confidence_sat', 0.0)

    # Default threshold is 0.90
    threshold = 0.90

    if company_settings:
        preferences = company_settings.get('preferences', {})
        threshold = preferences.get('auto_approve_threshold', 0.90)

    return confidence >= threshold
