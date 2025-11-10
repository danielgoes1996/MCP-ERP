"""
Utility helpers to normalize expense descriptions before feeding them to
the embedding pipeline or search components.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Minimal Spanish stopword list focused on expense descriptions.
_STOPWORDS = {
    "a",
    "al",
    "de",
    "del",
    "el",
    "la",
    "los",
    "las",
    "en",
    "para",
    "por",
    "un",
    "una",
    "unos",
    "unas",
    "y",
    "con",
    "sin",
    "sobre",
    "compra",
    "pago",
    "servicio",
    "servicios",
    "gasto",
    "gastos",
    "factura",
    "ticket",
    "cliente",
    "proveedor",
    "deuda",
    "abono",
    "cargo",
    "registro",
    "concepto",
    "por",
    "mes",
    "anio",
    "año",
    "semana",
    "dia",
    "día",
}

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ASCII", "ignore").decode("ASCII")


def _simple_stem(token: str) -> str:
    """
    Apply a light stemming heuristic that removes plural suffixes common in Spanish.
    Keeps the implementation lightweight while improving recall for embeddings.
    """
    if len(token) <= 4:
        return token

    for suffix in ("es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def _filter_tokens(tokens: Iterable[str]) -> Iterable[str]:
    for token in tokens:
        if not token or token in _STOPWORDS:
            continue
        yield _simple_stem(token)


def normalize_expense_text(text: str) -> str:
    """
    Normalize raw expense text by lowercasing, stripping accents, removing punctuation,
    dropping common stopwords, and applying a lightweight stemming heuristic.
    """
    if not text:
        return ""

    lowered = text.lower()
    ascii_text = _strip_accents(lowered)
    cleaned = _NON_ALNUM_RE.sub(" ", ascii_text)
    tokens = cleaned.split()
    normalized_tokens = list(_filter_tokens(tokens))
    return " ".join(normalized_tokens)

