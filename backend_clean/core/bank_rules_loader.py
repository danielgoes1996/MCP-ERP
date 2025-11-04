"""Utility helpers to load bank-specific parsing rules."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

RULES_DIR = (Path(__file__).resolve().parent.parent / "rules" / "banks").resolve()


def _normalise_bank_name(bank_name: str | None) -> str | None:
    if not bank_name:
        return None
    normalised = bank_name.strip().lower().replace(" ", "_")
    return normalised or None


@lru_cache(maxsize=32)
def load_bank_rules(bank_name: str | None) -> Dict[str, Any]:
    """Load rules for the given bank.

    Parameters
    ----------
    bank_name:
        Identifier returned by :class:`BankDetector`. Case and whitespace are
        ignored.

    Returns
    -------
    dict
        Dictionary with optional keys such as ``credit_keywords``,
        ``debit_keywords``, ``amount_patterns`` and ``skip_patterns``.
    """

    normalised = _normalise_bank_name(bank_name)
    if not normalised:
        return {}

    if not RULES_DIR.exists():
        logger.debug("Bank rules directory %s does not exist", RULES_DIR)
        return {}

    candidate = RULES_DIR / f"{normalised}.json"
    if not candidate.exists():
        logger.debug("No bank rules file found for %s", bank_name)
        return {}

    try:
        with candidate.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("rules file must contain a JSON object")
            logger.info("Loaded bank-specific rules for %s from %s", bank_name, candidate)
            return data
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to load bank rules for %s: %s", bank_name, exc)
        return {}


def merge_unique(target: List[str], additions: List[str]) -> None:
    """Append entries from *additions* into *target* avoiding duplicates."""
    existing = {item.lower() for item in target}
    for item in additions:
        value = item.strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered not in existing:
            target.append(value)
            existing.add(lowered)

