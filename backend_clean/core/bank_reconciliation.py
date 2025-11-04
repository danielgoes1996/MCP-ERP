"""Heuristic bank reconciliation utilities.

This module provides scoring helpers to suggest bank movements that likely
match a given expense. It is intentionally lightweight so we can evolve towards
an AI-powered matcher later while keeping a clear scoring breakdown today.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional, Set

from core.internal_db import list_bank_movements

logger = logging.getLogger(__name__)


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value[: len(fmt)], fmt)
        except ValueError:
            continue
    return None


def _amount_score(expense_amount: float, movement_amount: float) -> float:
    if expense_amount <= 0 or movement_amount <= 0:
        return 0.0

    diff = abs(expense_amount - movement_amount)
    denom = max(expense_amount, movement_amount)
    return max(0.0, 1.0 - (diff / denom))


def _date_score(expense_date: Optional[str], movement_date: Optional[str]) -> float:
    expense_dt = _parse_date(expense_date)
    movement_dt = _parse_date(movement_date)

    if not expense_dt or not movement_dt:
        return 0.5  # neutral if we lack either date

    diff_days = abs((expense_dt.date() - movement_dt.date()).days)
    if diff_days == 0:
        return 1.0
    if diff_days <= 3:
        return 0.9
    if diff_days <= 7:
        return 0.75
    if diff_days <= 15:
        return 0.6
    if diff_days <= 30:
        return 0.4
    if diff_days <= 45:
        return 0.25
    return 0.0


def _text_score(text_a: Optional[str], text_b: Optional[str]) -> float:
    if not text_a or not text_b:
        return 0.4
    ratio = SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
    return ratio


def _payment_mode_score(expense: Dict[str, Any], movement: Dict[str, Any]) -> float:
    paid_by = (expense.get("paid_by") or "").lower()
    tags: Iterable[str] = movement.get("tags", []) or []
    bank = (movement.get("bank") or "").lower()

    if paid_by == "company_account":
        if "tarjeta_empresa" in tags or "corporativa" in bank:
            return 1.0
        return 0.6
    if paid_by == "own_account":
        if "reembolso" in tags:
            return 0.9
        return 0.5
    return 0.4


def _build_reasons(
    *,
    amount_score: float,
    date_score: float,
    text_score: float,
    payment_score: float,
    amount_match: bool,
    diff_days: Optional[int],
) -> List[str]:
    reasons: List[str] = []
    if amount_score >= 0.95 and amount_match:
        reasons.append("Monto exacto")
    elif amount_score >= 0.8:
        reasons.append("Monto muy cercano")

    if diff_days is not None:
        if diff_days == 0:
            reasons.append("Mismo día")
        elif diff_days <= 3:
            reasons.append(f"Fecha cercana ({diff_days} días)")

    if text_score >= 0.7:
        reasons.append("Descripción coincide con proveedor")

    if payment_score >= 0.9:
        reasons.append("Forma de pago coincide")

    if not reasons:
        reasons.append("Coincidencia parcial basada en similitudes de monto/fecha")

    return reasons


def _normalized_movement(movement: Dict[str, Any]) -> Dict[str, Any]:
    # ensures we always have shared keys regardless of DB or UI seed
    normalized = dict(movement)
    normalized.setdefault("movement_id", movement.get("movement_id") or movement.get("id"))
    normalized.setdefault("id", normalized["movement_id"])
    normalized.setdefault("movement_date", movement.get("movement_date") or movement.get("fecha"))
    normalized.setdefault("description", movement.get("description") or movement.get("descripcion", ""))
    normalized.setdefault("amount", float(movement.get("amount") or movement.get("monto") or 0.0))
    normalized.setdefault("currency", movement.get("currency") or "MXN")
    normalized.setdefault("bank", movement.get("bank") or movement.get("banco") or "")
    tags = movement.get("tags")
    if isinstance(tags, str):
        try:
            import json

            tags = json.loads(tags)
        except Exception:  # pragma: no cover - defensive
            tags = []
    normalized["tags"] = tags or []
    return normalized


def _generate_group_id(movements: Iterable[Dict[str, Any]]) -> str:
    identifiers = sorted(
        {
            str(item.get("movement_id") or item.get("id"))
            for item in movements
            if item.get("movement_id") or item.get("id")
        }
    )
    return "+".join(identifiers)


def _extract_linked_ids(expense: Dict[str, Any]) -> Set[str]:
    linked: Set[str] = set()
    for key in ("movimientos_bancarios",):
        items = expense.get(key)
        if isinstance(items, list):
            for entry in items:
                if isinstance(entry, dict):
                    movement_id = entry.get("movement_id") or entry.get("id")
                    if movement_id:
                        linked.add(str(movement_id))
                elif isinstance(entry, str):
                    linked.add(entry)

    metadata = expense.get("metadata")
    if isinstance(metadata, dict):
        items = metadata.get("movimientos_bancarios")
        if isinstance(items, list):
            for entry in items:
                if isinstance(entry, dict):
                    movement_id = entry.get("movement_id") or entry.get("id")
                    if movement_id:
                        linked.add(str(movement_id))
                elif isinstance(entry, str):
                    linked.add(entry)

    return linked


def _select_combination_candidates(
    candidate_movements: List[Dict[str, Any]],
    expense_amount: float,
) -> List[Dict[str, Any]]:
    if not candidate_movements:
        return []

    if expense_amount <= 0:
        return candidate_movements[:12]

    tolerance = max(20.0, expense_amount * 0.03)
    filtered = [
        movement
        for movement in candidate_movements
        if 0 < movement.get("amount", 0.0) <= (expense_amount + tolerance)
    ]

    filtered.sort(key=lambda m: (abs(expense_amount - m["amount"]), m["amount"]))
    return filtered[:15]


def _combine_movements(
    candidate_movements: List[Dict[str, Any]],
    expense_amount: float,
    expense_date: Optional[str],
    expense_text: str,
    expense: Dict[str, Any],
    *,
    linked_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    tolerance = max(10.0, expense_amount * 0.015)
    linked_ids = linked_ids or set()
    seen_group_ids: Set[str] = set()

    combination_candidates = _select_combination_candidates(candidate_movements, expense_amount)

    for size in (2, 3):
        if len(combination_candidates) < size:
            continue
        for combo in combinations(combination_candidates, size):
            combined_amount = sum(item["amount"] for item in combo)
            diff = abs(expense_amount - combined_amount)
            if diff > tolerance:
                continue

            group_id = _generate_group_id(combo)
            if not group_id or group_id in seen_group_ids:
                continue

            amount_score = _amount_score(expense_amount, combined_amount)
            date_score = max(_date_score(expense_date, movement.get("movement_date")) for movement in combo)
            text_score = max(_text_score(expense_text, movement.get("description")) for movement in combo)
            payment_score = max(_payment_mode_score(expense, movement) for movement in combo)

            expense_dt = _parse_date(expense_date)
            combo_dates = [
                _parse_date(movement.get("movement_date"))
                for movement in combo
                if movement.get("movement_date")
            ]
            span_days = None
            if len(combo_dates) >= 2 and all(date is not None for date in combo_dates):
                days = sorted(date.date() for date in combo_dates if date)
                span_days = abs((days[-1] - days[0]).days)
                if span_days > 10:
                    continue

            aggregate = (
                amount_score * 0.55
                + date_score * 0.25
                + text_score * 0.15
                + payment_score * 0.05
            )
            combo_ids: Set[str] = set()
            for movement in combo:
                identifier = movement.get("movement_id") or movement.get("id")
                if identifier:
                    combo_ids.add(str(identifier))

            link_bonus = 0.08 if linked_ids and combo_ids & linked_ids else 0.0
            confidence = round(min(1.0, aggregate + link_bonus) * 100, 2)

            diff_days_values = []
            for movement in combo:
                movement_dt = _parse_date(movement.get("movement_date"))
                if expense_dt and movement_dt:
                    diff_days_values.append(abs((expense_dt.date() - movement_dt.date()).days))

            diff_days = min(diff_days_values) if diff_days_values else None

            reasons = _build_reasons(
                amount_score=amount_score,
                date_score=date_score,
                text_score=text_score,
                payment_score=payment_score,
                amount_match=diff <= (expense_amount * 0.01),
                diff_days=diff_days,
            )
            reasons.insert(0, f"Pago en {size} cargos")
            if linked_ids and combo_ids & linked_ids:
                reasons.append("Coincide con movimientos registrados en el gasto")
            if span_days and span_days > 0:
                reasons.append(f"Cargos repartidos en {span_days} días")

            suggestions.append(
                {
                    "type": "combination",
                    "movements": list(combo),
                    "movement": combo[0],
                    "movement_ids": sorted(combo_ids),
                    "group_id": group_id,
                    "combined_amount": round(combined_amount, 2),
                    "confidence": confidence,
                    "split_payment": True,
                    "linked_match": bool(linked_ids and combo_ids & linked_ids),
                    "reasons": reasons,
                    "score_breakdown": {
                        "amount": round(amount_score, 4),
                        "date": round(date_score, 4),
                        "text": round(text_score, 4),
                        "payment": round(payment_score, 4),
                    },
                }
            )
            seen_group_ids.add(group_id)

    return suggestions


def suggest_bank_matches(
    expense: Dict[str, Any],
    *,
    limit: int = 5,
    movements: Optional[Iterable[Dict[str, Any]]] = None,
    company_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return bank movement suggestions ordered by confidence."""

    normalized_company_id = (
        company_id
        or expense.get("company_id")
        or (expense.get("metadata") or {}).get("company_id")
        or "default"
    )

    candidate_movements = [
        _normalized_movement(item)
        for item in (
            movements
            or list_bank_movements(limit=200, company_id=normalized_company_id)
        )
    ]
    amount = float(expense.get("amount") or expense.get("monto_total") or 0.0)
    expense_description = expense.get("description") or expense.get("descripcion") or ""
    expense_provider = expense.get("provider_name") or expense.get("proveedor") or expense.get("proveedor.nombre") or ""
    text_to_match = f"{expense_description} {expense_provider}".strip()
    expense_date = expense.get("date") or expense.get("fecha_gasto")
    linked_ids = _extract_linked_ids(expense)

    suggestions: List[Dict[str, Any]] = []

    for movement in candidate_movements:
        movement_amount = float(movement.get("amount", 0.0))
        amount_score = _amount_score(amount, movement_amount)

        diff_days = None
        expense_dt = _parse_date(expense_date)
        movement_dt = _parse_date(movement.get("movement_date"))
        if expense_dt and movement_dt:
            diff_days = abs((expense_dt.date() - movement_dt.date()).days)

        date_score = _date_score(expense_date, movement.get("movement_date"))
        text_score = _text_score(text_to_match, movement.get("description"))
        payment_score = _payment_mode_score(expense, movement)

        aggregate = (
            amount_score * 0.5
            + date_score * 0.3
            + text_score * 0.15
            + payment_score * 0.05
        )
        identifier = movement.get("movement_id") or movement.get("id")
        linked_match = bool(identifier and str(identifier) in linked_ids)
        link_bonus = 0.06 if linked_match else 0.0
        confidence = round(min(1.0, aggregate + link_bonus) * 100, 2)

        group_id = _generate_group_id([movement])
        reasons = _build_reasons(
            amount_score=amount_score,
            date_score=date_score,
            text_score=text_score,
            payment_score=payment_score,
            amount_match=math.isclose(amount, movement_amount, rel_tol=0.01),
            diff_days=diff_days,
        )
        if linked_match:
            reasons.append("Movimiento registrado en el gasto")

        suggestions.append(
            {
                "type": "single",
                "movements": [movement],
                "movement": movement,
                "movement_ids": [str(identifier)] if identifier else [],
                "group_id": group_id,
                "combined_amount": round(movement_amount, 2),
                "confidence": confidence,
                "split_payment": False,
                "linked_match": linked_match,
                "score_breakdown": {
                    "amount": round(amount_score, 4),
                    "date": round(date_score, 4),
                    "text": round(text_score, 4),
                    "payment": round(payment_score, 4),
                },
                "reasons": reasons,
            }
        )

    suggestions.extend(
        _combine_movements(
            candidate_movements,
            amount,
            expense_date,
            text_to_match,
            expense,
            linked_ids=linked_ids,
        )
    )

    suggestions.sort(key=lambda item: item["confidence"], reverse=True)
    return suggestions[:limit]


__all__ = ["suggest_bank_matches"]
