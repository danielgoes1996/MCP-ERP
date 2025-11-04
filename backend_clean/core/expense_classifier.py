"""Clasificador de gastos con normalización contable y SAT."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from core.accounting_catalog import normalize_accounting_category
from core.company_settings import CompanySettings


@dataclass
class ClassificationResult:
    slug: str
    nombre: str
    sat_account_code: Optional[str]
    sat_product_service_code: Optional[str]
    confidence: float
    source: str
    matched_by: str
    reasoning: str
    deducible: bool
    warnings: List[str]

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "nombre": self.nombre,
            "sat_account_code": self.sat_account_code,
            "sat_product_service_code": self.sat_product_service_code,
            "confidence": self.confidence,
            "source": self.source,
            "matched_by": self.matched_by,
            "reasoning": self.reasoning,
            "warnings": list(self.warnings),
        }


def _extract_provider_name(expense: Dict[str, Any]) -> Optional[str]:
    provider = expense.get("proveedor") or expense.get("provider")
    if isinstance(provider, dict):
        for key in ("nombre", "name", "razon_social"):
            value = provider.get(key)
            if value:
                return str(value)
    if isinstance(provider, str):
        return provider
    return None


def classify_expense(
    expense: Dict[str, Any],
    company_settings: Optional[CompanySettings] = None,
) -> ClassificationResult:
    """Clasifica un gasto usando el catálogo contable determinista."""

    provided_category: Optional[str] = (
        expense.get("categoria")
        or expense.get("categoria_normalizada")
        or expense.get("category")
    )

    description: str = str(expense.get("descripcion") or expense.get("description") or "")
    provider_name: Optional[str] = _extract_provider_name(expense)

    if provided_category:
        candidate = provided_category
        source = "user_input"
    else:
        candidate_parts = [description]
        if provider_name:
            candidate_parts.append(provider_name)
        candidate = " ".join(part for part in candidate_parts if part)
        if not candidate:
            candidate = "otros gastos"
        source = "rule_based"

    fiscal_regime = company_settings.regimen_fiscal_code if company_settings else None
    normalized = normalize_accounting_category(candidate, fiscal_regime=fiscal_regime)

    reasoning = f"Coincidencia por {normalized.matched_by.replace('_', ' ')}"
    warnings: List[str] = []

    deducible = bool(expense.get("will_have_cfdi", True))
    if not deducible:
        warnings.append("Marcado como no deducible por falta de CFDI")

    if deducible and fiscal_regime:
        if normalized.disallowed_regimes and fiscal_regime in normalized.disallowed_regimes:
            deducible = False
            warnings.append("Categoría no deducible para el régimen fiscal actual")
        if normalized.allowed_regimes and fiscal_regime not in normalized.allowed_regimes:
            deducible = False
            warnings.append("Categoría fuera de los regímenes permitidos")

    return ClassificationResult(
        slug=normalized.slug,
        nombre=normalized.nombre,
        sat_account_code=normalized.sat_account_code,
        sat_product_service_code=normalized.sat_product_service_code,
        confidence=normalized.confianza,
        source=source,
        matched_by=normalized.matched_by,
        reasoning=reasoning,
        deducible=deducible,
        warnings=warnings,
    )
