"""
Autopilot configuration and decision logic for classification.

This module centralizes all autopilot rules and provides a single
auditable function for auto-approval decisions.

Created: 2025-11-13
"""

from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Autopilot levels with clear conditions
AUTOPILOT_LEVELS = {
    "L0": {
        "name": "Solo sugerir",
        "auto_approve": False,
        "description": "Siempre requiere revisión humana",
        "conditions": {}
    },
    "L3": {
        "name": "Auto-aprobar bajo riesgo",
        "auto_approve": True,
        "description": "Proveedores conocidos, montos bajos, alta confianza",
        "conditions": {
            "confidence_min": 0.85,
            "amount_max": 25000,
            "known_provider": True,
            "not_sensitive": True,
            "provider_min_docs": 3
        }
    },
    "L4": {
        "name": "Auto-aprobar medio riesgo",
        "auto_approve": True,
        "description": "Proveedores con historial sólido, confianza muy alta",
        "conditions": {
            "confidence_min": 0.90,
            "amount_max": 100000,
            "corrections_count_min": 3,
            "provider_min_docs": 5,
            "zero_recent_errors": True
        }
    },
    "L5": {
        "name": "Straight-through processing",
        "auto_approve": True,
        "description": "Patrones muy fuertes, sin errores recientes",
        "conditions": {
            "confidence_min": 0.95,
            "corrections_count_min": 10,
            "provider_min_docs": 10,
            "zero_recent_errors": True,
            "consistent_pattern": True
        }
    }
}

# Sensitive categories that always require review (L0)
SENSITIVE_CATEGORIES = {
    "payroll": {
        "autopilot_level": "L0",
        "reason": "Nómina requiere revisión contable/fiscal"
    },
    "taxes": {
        "autopilot_level": "L0",
        "reason": "Impuestos requieren validación fiscal"
    },
    "leases_ifrs16": {
        "autopilot_level": "L0",
        "reason": "Arrendamientos IFRS-16 requieren análisis"
    },
    "capex": {
        "autopilot_level": "L0",
        "reason": "Inversiones de capital requieren aprobación"
    },
    "financial_expenses": {
        "autopilot_level": "L0",
        "reason": "Gastos financieros requieren revisión"
    }
}

# Risk gates by invoice characteristics
RISK_GATES = {
    "new_provider": {
        "min_days_since_first": 30,
        "min_invoice_count": 3,
        "reason": "Proveedor nuevo requiere patrón establecido"
    },
    "high_amount": {
        "threshold_mxn": 100000,
        "reason": "Monto alto requiere revisión"
    },
    "complemento_pago": {
        "always_review": True,
        "reason": "Complementos de pago no se clasifican"
    },
    "nota_credito": {
        "always_review": True,
        "reason": "Notas de crédito requieren análisis especial"
    }
}


def can_auto_approve(
    snapshot: Dict[str, Any],
    autopilot_level: str,
    memory_stats: Optional[Dict[str, Any]] = None,
    classification: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """
    Centralized autopilot decision logic.

    Args:
        snapshot: Invoice snapshot with amount, provider, category, etc.
        autopilot_level: Target level (L0, L3, L4, L5)
        memory_stats: Provider memory statistics (corrections, doc count, etc.)
        classification: Classification result with confidence

    Returns:
        (can_approve, reason_code)

    Reason codes:
        - approved_l3/l4/l5: Auto-approved at level
        - blocked_l0: Always review
        - blocked_sensitive: Sensitive category
        - blocked_new_provider: New provider
        - blocked_amount: Amount too high
        - blocked_confidence: Confidence too low
        - blocked_no_pattern: Insufficient corrections
        - blocked_recent_errors: Recent corrections indicate issues
    """

    if not autopilot_level or autopilot_level not in AUTOPILOT_LEVELS:
        return False, "blocked_unknown_level"

    level_config = AUTOPILOT_LEVELS[autopilot_level]

    # L0 = always review
    if not level_config["auto_approve"]:
        return False, "blocked_l0"

    # Check sensitive categories
    category = snapshot.get("category") or snapshot.get("expense_type")
    if category and category in SENSITIVE_CATEGORIES:
        return False, f"blocked_sensitive_{category}"

    # Check CFDI type gates
    cfdi_type = snapshot.get("cfdi_tipo_comprobante", "I")
    if cfdi_type == "P":  # Complemento de pago
        return False, "blocked_complemento_pago"
    if cfdi_type == "E":  # Nota de crédito
        return False, "blocked_nota_credito"

    # Get amount in base currency (assume MXN for now)
    amount = snapshot.get("total") or snapshot.get("amount", 0)

    # Check amount gate
    if amount > RISK_GATES["high_amount"]["threshold_mxn"]:
        return False, "blocked_high_amount"

    # Initialize memory stats if not provided
    if memory_stats is None:
        memory_stats = {
            "doc_count": 0,
            "corrections_count": 0,
            "first_seen_days": 0,
            "recent_errors": 0
        }

    # Check new provider gate
    is_new_provider = (
        memory_stats.get("first_seen_days", 0) < RISK_GATES["new_provider"]["min_days_since_first"] or
        memory_stats.get("doc_count", 0) < RISK_GATES["new_provider"]["min_invoice_count"]
    )

    if is_new_provider:
        return False, "blocked_new_provider"

    # Get classification confidence
    confidence = 0.0
    if classification:
        confidence = classification.get("confidence_sat") or classification.get("confidence", 0.0)

    # Evaluate level-specific conditions
    conditions = level_config["conditions"]

    # L3: Basic autopilot
    if autopilot_level == "L3":
        if confidence < conditions["confidence_min"]:
            return False, "blocked_confidence_l3"
        if amount > conditions["amount_max"]:
            return False, "blocked_amount_l3"
        if memory_stats.get("doc_count", 0) < conditions["provider_min_docs"]:
            return False, "blocked_pattern_l3"

        return True, "approved_l3"

    # L4: Requires correction history
    if autopilot_level == "L4":
        if confidence < conditions["confidence_min"]:
            return False, "blocked_confidence_l4"
        if amount > conditions["amount_max"]:
            return False, "blocked_amount_l4"
        if memory_stats.get("corrections_count", 0) < conditions["corrections_count_min"]:
            return False, "blocked_no_corrections_l4"
        if memory_stats.get("doc_count", 0) < conditions["provider_min_docs"]:
            return False, "blocked_pattern_l4"
        if conditions.get("zero_recent_errors") and memory_stats.get("recent_errors", 0) > 0:
            return False, "blocked_recent_errors_l4"

        return True, "approved_l4"

    # L5: Straight-through processing
    if autopilot_level == "L5":
        if confidence < conditions["confidence_min"]:
            return False, "blocked_confidence_l5"
        if memory_stats.get("corrections_count", 0) < conditions["corrections_count_min"]:
            return False, "blocked_no_corrections_l5"
        if memory_stats.get("doc_count", 0) < conditions["provider_min_docs"]:
            return False, "blocked_pattern_l5"
        if conditions.get("zero_recent_errors") and memory_stats.get("recent_errors", 0) > 0:
            return False, "blocked_recent_errors_l5"

        # Check consistent pattern (low variance in recent classifications)
        if conditions.get("consistent_pattern"):
            pattern_variance = memory_stats.get("pattern_variance", 1.0)
            if pattern_variance > 0.1:  # More than 10% variance
                return False, "blocked_inconsistent_pattern_l5"

        return True, "approved_l5"

    return False, "blocked_unknown"


def get_provider_memory_stats(company_id: int, provider_rfc: str) -> Dict[str, Any]:
    """
    Get provider memory statistics for autopilot decision.

    Args:
        company_id: Company ID
        provider_rfc: Provider RFC

    Returns:
        Stats dict with:
        - doc_count: Total invoices from provider
        - corrections_count: Times corrected
        - first_seen_days: Days since first invoice
        - recent_errors: Corrections in last 30 days
        - pattern_variance: Variance in recent classifications
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from core.shared.db_config import POSTGRES_CONFIG
    from datetime import datetime

    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # Get document count and first seen
        cursor.execute("""
            SELECT
                COUNT(*) as doc_count,
                EXTRACT(DAYS FROM (NOW() - MIN(created_at))) as first_seen_days
            FROM expense_invoices ei
            WHERE company_id = %s
              AND (parsed_data->>'emisor'->>'rfc' = %s OR provider_rfc = %s)
        """, (company_id, provider_rfc, provider_rfc))

        doc_stats = cursor.fetchone()

        # Get corrections count
        cursor.execute("""
            SELECT
                COUNT(*) as corrections_count,
                COUNT(*) FILTER (WHERE corrected_at > NOW() - INTERVAL '30 days') as recent_errors
            FROM ai_correction_memory
            WHERE company_id = %s
              AND provider_rfc = %s
        """, (company_id, provider_rfc))

        correction_stats = cursor.fetchone()

        conn.close()

        return {
            "doc_count": doc_stats["doc_count"] if doc_stats else 0,
            "first_seen_days": doc_stats["first_seen_days"] if doc_stats else 0,
            "corrections_count": correction_stats["corrections_count"] if correction_stats else 0,
            "recent_errors": correction_stats["recent_errors"] if correction_stats else 0,
            "pattern_variance": 0.0  # TODO: Calculate from recent classifications
        }

    except Exception as e:
        logger.error(f"Error getting provider memory stats: {e}")
        return {
            "doc_count": 0,
            "corrections_count": 0,
            "first_seen_days": 0,
            "recent_errors": 0,
            "pattern_variance": 0.0
        }


def format_autopilot_decision(can_approve: bool, reason_code: str, level: str) -> Dict[str, Any]:
    """
    Format autopilot decision for storage in classification.

    Returns dict to merge into accounting_classification JSONB.
    """
    return {
        "autopilot_level": level,
        "autopilot_approved": can_approve,
        "autopilot_reason": reason_code,
        "autopilot_evaluated_at": datetime.now().isoformat()
    }
