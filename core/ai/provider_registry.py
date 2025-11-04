"""
Registry utilities for AI provider stack configuration.
"""

from __future__ import annotations

import os
from typing import Dict, Any, Optional

DEFAULT_STACK = {
    "categorization_model": {
        "provider": "openai",
        "model": "gpt-4o-mini",
    },
    "invoice_parser": {
        "provider": "claude",
        "model": "claude-3-haiku-20240307",
    },
    "bank_matcher": {
        "provider": "local",
        "model": "vector-similarity-v1",
    },
}


def get_ai_provider_stack(company_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Returns the configured AI stack for a company.

    Currently reads from environment variables, falling back to defaults.
    """
    stack = {
        "categorization_model": {
            "provider": os.getenv("AI_CATEGORIZATION_PROVIDER", DEFAULT_STACK["categorization_model"]["provider"]),
            "model": os.getenv("AI_CATEGORIZATION_MODEL", DEFAULT_STACK["categorization_model"]["model"]),
        },
        "invoice_parser": {
            "provider": os.getenv("AI_INVOICE_PROVIDER", DEFAULT_STACK["invoice_parser"]["provider"]),
            "model": os.getenv("AI_INVOICE_MODEL", DEFAULT_STACK["invoice_parser"]["model"]),
        },
        "bank_matcher": {
            "provider": os.getenv("AI_BANK_MATCHER_PROVIDER", DEFAULT_STACK["bank_matcher"]["provider"]),
            "model": os.getenv("AI_BANK_MATCHER_MODEL", DEFAULT_STACK["bank_matcher"]["model"]),
        },
    }

    stack["company_id"] = company_id
    return stack
