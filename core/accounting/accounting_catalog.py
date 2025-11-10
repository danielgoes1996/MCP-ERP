"""Catálogo contable y normalizador determinista.

Provee una lista pequeña pero extensible de categorías contables
estandarizadas y utilidades para normalizar textos ruidosos que
vienen de la captura de gastos.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Dict, Iterable, List, Optional

from core.sat_catalog_seed import (
    CATEGORY_SAT_MAPPING,
    SAT_ACCOUNT_CATALOG_SEED,
    SAT_PRODUCT_SERVICE_CATALOG_SEED,
    validate_category_mapping_integrity,
)


def _category_kwargs(slug: str) -> Dict[str, object]:
    mapping = CATEGORY_SAT_MAPPING.get(slug, {})
    if not mapping:
        return {}
    return {key: value for key, value in mapping.items() if key != "descripcion"}


@dataclass(frozen=True)
class AccountingCategory:
    slug: str
    nombre: str
    descripcion: str
    sinonimos: List[str]
    sat_account_code: Optional[str] = None
    sat_product_service_code: Optional[str] = None
    needs_review: bool = False
    allowed_regimes: Optional[List[str]] = None
    disallowed_regimes: Optional[List[str]] = None


@dataclass(frozen=True)
class CategoryNormalizationResult:
    slug: str
    nombre: str
    confianza: float
    fuente: str
    matched_by: str
    sat_account_code: Optional[str] = None
    sat_product_service_code: Optional[str] = None
    needs_review: bool = False
    allowed_regimes: Optional[List[str]] = None
    disallowed_regimes: Optional[List[str]] = None


ACCOUNTING_CATEGORY_CATALOG: List[AccountingCategory] = [
    AccountingCategory(
        slug="transporte_combustible",
        nombre="Transporte y Combustible",
        descripcion=CATEGORY_SAT_MAPPING.get("transporte_combustible", {}).get(
            "descripcion", "Gastos relacionados con traslados y combustibles"
        ),
        sinonimos=[
            "transporte",
            "combustible",
            "gasolina",
            "gas",
            "uber",
            "cabify",
            "taxi",
            "pemex",
            "gasolinera",
            "peaje",
        ],
        **_category_kwargs("transporte_combustible"),
    ),
    AccountingCategory(
        slug="mantenimiento_vehicular",
        nombre="Mantenimiento Vehicular",
        descripcion=CATEGORY_SAT_MAPPING.get("mantenimiento_vehicular", {}).get(
            "descripcion", "Reparaciones y refacciones de vehículos"
        ),
        sinonimos=[
            "mantenimiento vehicular",
            "servicio vehicular",
            "refacciones",
            "taller",
            "llantas",
            "mantenimiento camioneta",
            "mantenimiento auto",
            "mantenimiento coche",
        ],
        **_category_kwargs("mantenimiento_vehicular"),
    ),
    AccountingCategory(
        slug="viaticos_alimentos",
        nombre="Alimentos y Viáticos",
        descripcion=CATEGORY_SAT_MAPPING.get("viaticos_alimentos", {}).get(
            "descripcion", "Viáticos y alimentación del personal"
        ),
        sinonimos=[
            "alimentos",
            "viaticos",
            "viáticos",
            "viatico comida",
            "viatico",
            "alimentacion viaje",
            "desayuno",
            "almuerzo",
            "cena",
            "viatico alimentos",
        ],
        **_category_kwargs("viaticos_alimentos"),
    ),
    AccountingCategory(
        slug="hospedaje_alojamiento",
        nombre="Hospedaje y Alojamiento",
        descripcion=CATEGORY_SAT_MAPPING.get("hospedaje_alojamiento", {}).get(
            "descripcion", "Hospedaje y alojamiento en viajes"
        ),
        sinonimos=[
            "hotel",
            "hospedaje",
            "alojamiento",
            "airbnb",
            "motel",
            "hostal",
        ],
        **_category_kwargs("hospedaje_alojamiento"),
    ),
    AccountingCategory(
        slug="gastos_representacion",
        nombre="Gastos de Representación",
        descripcion=CATEGORY_SAT_MAPPING.get("gastos_representacion", {}).get(
            "descripcion", "Atenciones y representación con clientes"
        ),
        sinonimos=[
            "representacion",
            "gastos representacion",
            "comida clientes",
            "atencion clientes",
            "eventos",
            "restaurante",
            "comida",
            "atencion",
        ],
        **_category_kwargs("gastos_representacion"),
    ),
    AccountingCategory(
        slug="tecnologia_software",
        nombre="Tecnología y Software",
        descripcion=CATEGORY_SAT_MAPPING.get("tecnologia_software", {}).get(
            "descripcion", "Suscripciones y servicios de software"
        ),
        sinonimos=[
            "software",
            "suscripcion",
            "suscripción",
            "licencia",
            "tecnologia",
            "tecnología",
            "hosting",
            "cloud",
            "saas",
            "microsoft",
            "google",
            "aws",
            "azure",
        ],
        **_category_kwargs("tecnologia_software"),
    ),
    AccountingCategory(
        slug="servicios_administrativos",
        nombre="Servicios Administrativos",
        descripcion=CATEGORY_SAT_MAPPING.get("servicios_administrativos", {}).get(
            "descripcion", "Servicios administrativos y de soporte"
        ),
        sinonimos=[
            "servicio administrativo",
            "servicios administrativos",
            "administracion",
            "administración",
            "backoffice",
        ],
        **_category_kwargs("servicios_administrativos"),
    ),
    AccountingCategory(
        slug="gastos_administrativos",
        nombre="Gastos Administrativos",
        descripcion=CATEGORY_SAT_MAPPING.get("gastos_administrativos", {}).get(
            "descripcion", "Papelería y consumibles administrativos"
        ),
        sinonimos=[
            "oficina",
            "papeleria",
            "papelería",
            "material",
            "impresion",
            "impresión",
            "consumible",
            "boligrafo",
            "pluma",
            "toner",
        ],
        **_category_kwargs("gastos_administrativos"),
    ),
    AccountingCategory(
        slug="gastos_profesionales",
        nombre="Gastos Profesionales",
        descripcion=CATEGORY_SAT_MAPPING.get("gastos_profesionales", {}).get(
            "descripcion", "Honorarios y servicios profesionales"
        ),
        sinonimos=[
            "honorarios",
            "consultoria",
            "consultoría",
            "asesoria",
            "servicio profesional",
        ],
        **_category_kwargs("gastos_profesionales"),
    ),
    AccountingCategory(
        slug="gastos_generales",
        nombre="Gastos Generales",
        descripcion=CATEGORY_SAT_MAPPING.get("gastos_generales", {}).get(
            "descripcion", "Otros gastos operativos no clasificados"
        ),
        sinonimos=[
            "otros",
            "general",
            "miscelaneo",
            "misceláneo",
            "varios",
        ],
        **_category_kwargs("gastos_generales"),
    ),
    AccountingCategory(
        slug="gastos_no_deducibles",
        nombre="Gastos no deducibles",
        descripcion=CATEGORY_SAT_MAPPING.get("gastos_no_deducibles", {}).get(
            "descripcion", "Gastos no deducibles para CUFIN"
        ),
        sinonimos=[
            "gasto no deducible",
            "gastos no deducibles",
            "cufin",
            "no deducible",
        ],
        **_category_kwargs("gastos_no_deducibles"),
    ),
    AccountingCategory(
        slug="impuestos_derechos",
        nombre="Impuestos y Derechos",
        descripcion=CATEGORY_SAT_MAPPING.get("impuestos_derechos", {}).get(
            "descripcion", "Pagos de impuestos, derechos y contribuciones"
        ),
        sinonimos=[
            "impuesto",
            "impuestos",
            "derechos",
            "predial",
            "contribucion",
        ],
        **_category_kwargs("impuestos_derechos"),
    ),
]


validate_category_mapping_integrity(
    available_account_codes=(entry["code"] for entry in SAT_ACCOUNT_CATALOG_SEED),
    available_product_service_codes=(
        entry["code"] for entry in SAT_PRODUCT_SERVICE_CATALOG_SEED
    ),
)


ACCOUNTING_CATEGORY_DEFAULT_SLUG = "gastos_generales"


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower().strip()


_SLUG_MAP: Dict[str, AccountingCategory] = {
    cat.slug: cat for cat in ACCOUNTING_CATEGORY_CATALOG
}

_NOMBRE_MAP: Dict[str, AccountingCategory] = {
    _normalize_text(cat.nombre): cat for cat in ACCOUNTING_CATEGORY_CATALOG
}

_SINONIMO_MAP: Dict[str, AccountingCategory] = {}
for cat in ACCOUNTING_CATEGORY_CATALOG:
    for alias in cat.sinonimos:
        key = _normalize_text(alias)
        if key:
            _SINONIMO_MAP[key] = cat


def list_accounting_categories() -> List[Dict[str, str]]:
    """Devuelve el catálogo en formato serializable."""

    return [
        {
            "slug": cat.slug,
            "nombre": cat.nombre,
            "descripcion": cat.descripcion,
            "sinonimos": list(cat.sinonimos),
            "sat_account_code": cat.sat_account_code,
            "sat_product_service_code": cat.sat_product_service_code,
            "needs_review": cat.needs_review,
            "allowed_regimes": list(cat.allowed_regimes) if cat.allowed_regimes else [],
            "disallowed_regimes": list(cat.disallowed_regimes) if cat.disallowed_regimes else [],
        }
        for cat in ACCOUNTING_CATEGORY_CATALOG
    ]


def _create_result(
    category: AccountingCategory,
    *,
    confidence: float,
    matched_by: str,
    fiscal_regime: Optional[str],
) -> CategoryNormalizationResult:
    allowed = list(category.allowed_regimes) if category.allowed_regimes else None
    disallowed = list(category.disallowed_regimes) if category.disallowed_regimes else None

    needs_review = category.needs_review
    if fiscal_regime:
        normalized_regime = fiscal_regime.upper()
        if allowed and normalized_regime not in allowed:
            needs_review = True
        if disallowed and normalized_regime in disallowed:
            needs_review = True

    return CategoryNormalizationResult(
        slug=category.slug,
        nombre=category.nombre,
        confianza=confidence,
        fuente="rule_based",
        matched_by=matched_by,
        sat_account_code=category.sat_account_code,
        sat_product_service_code=category.sat_product_service_code,
        needs_review=needs_review,
        allowed_regimes=allowed,
        disallowed_regimes=disallowed,
    )


def normalize_accounting_category(
    raw_value: Optional[str],
    *,
    fiscal_regime: Optional[str] = None,
) -> CategoryNormalizationResult:
    """Normaliza un texto libre a una categoría contable estándar.

    La estrategia es determinista:
        1. Si ya viene el slug válido → confianza 1.0
        2. Si coincide exactamente con el nombre canónico → 0.95
        3. Si coincide con algún sinónimo → 0.8
        4. En cualquier otro caso → regresa la categoría default con 0.4
    """

    if raw_value is None:
        raw_value = ""

    normalized = _normalize_text(raw_value)

    # 1) Slug válido
    if normalized in _SLUG_MAP:
        cat = _SLUG_MAP[normalized]
        return _create_result(
            cat,
            confidence=1.0,
            matched_by="slug",
            fiscal_regime=fiscal_regime,
        )

    # 2) Coincidencia exacta con el nombre
    if normalized in _NOMBRE_MAP:
        cat = _NOMBRE_MAP[normalized]
        return _create_result(
            cat,
            confidence=0.95,
            matched_by="nombre",
            fiscal_regime=fiscal_regime,
        )

    # 3) Sinónimos
    if normalized in _SINONIMO_MAP:
        cat = _SINONIMO_MAP[normalized]
        return _create_result(
            cat,
            confidence=0.8,
            matched_by="sinonimo",
            fiscal_regime=fiscal_regime,
        )

    # 4) Búsqueda parcial en sinónimos (palabra dentro del texto)
    for key, cat in _SINONIMO_MAP.items():
        if key and key in normalized:
            return _create_result(
                cat,
                confidence=0.7,
                matched_by="sinonimo_parcial",
                fiscal_regime=fiscal_regime,
            )

    # 5) Fallback a categoría default
    default_category = _SLUG_MAP[ACCOUNTING_CATEGORY_DEFAULT_SLUG]
    return _create_result(
        default_category,
        confidence=0.4,
        matched_by="default",
        fiscal_regime=fiscal_regime,
    )


def iter_accounting_categories() -> Iterable[AccountingCategory]:
    return tuple(ACCOUNTING_CATEGORY_CATALOG)
