"""
Utility helpers for SAT account code handling.
"""

from __future__ import annotations


def extract_family_code(code: str | None) -> str:
    """
    Return the first-level family code (prefix) for a SAT account.

    Examples:
        "603.54" -> "603"
        "602" -> "602"
    """
    if not code:
        return ""
    normalized = code.strip()
    if not normalized:
        return ""
    return normalized.split(".", 1)[0]


def format_family_label(code: str | None) -> str:
    """
    Format a human readable label for a family code.
    """
    family = extract_family_code(code)
    if not family:
        return "sin_familia"
    return f"{family}"

