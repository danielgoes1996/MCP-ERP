"""Seed data and default mappings for SAT catalogs.

Provides a minimal-yet-realistic subset of the official SAT account
and product-service catalogs so that new environments start with
useful defaults without requiring an immediate CSV import.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

# Subset of SAT account catalog (Códigos agrupadores)
# Source: Catálogo de cuentas SAT (versión 2024.1)
# Only the entries required by the default normalization rules are
# included here. The import script can later replace/extend them with
# the full official dataset.
SAT_ACCOUNT_CATALOG_SEED: List[Dict[str, object]] = [
    {
        "code": "601",
        "name": "Gastos de operación",
        "description": "Agrupador para gastos operativos de la entidad",
        "parent_code": None,
        "type": "agrupador",
        "is_active": True,
    },
    {
        "code": "601.32",
        "name": "Servicios administrativos",
        "description": "Servicios administrativos y de soporte",
        "parent_code": "601",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "601.56",
        "name": "Mantenimiento y conservación",
        "description": "Mantenimiento general de activos y vehículos",
        "parent_code": "601",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "601.58",
        "name": "Otros impuestos y derechos",
        "description": "Pagos de impuestos, derechos y contribuciones",
        "parent_code": "601",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "601.6",
        "name": "Cuotas y suscripciones",
        "description": "Cuotas periódicas y suscripciones de servicios",
        "parent_code": "601",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "601.83",
        "name": "Gastos no deducibles (sin requisitos fiscales)",
        "description": "Gastos no deducibles que requieren revisión",
        "parent_code": "601",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "601.84",
        "name": "Otros gastos generales",
        "description": "Gastos generales no clasificados",
        "parent_code": "601",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "607",
        "name": "Gastos de transporte y combustibles",
        "description": "Agrupador para gastos relacionados con movilidad",
        "parent_code": "601",
        "type": "agrupador",
        "is_active": True,
    },
    {
        "code": "607.01",
        "name": "Combustibles y lubricantes",
        "description": "Consumo de gasolina, diésel y lubricantes",
        "parent_code": "607",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "608",
        "name": "Viáticos y gastos de viaje",
        "description": "Agrupador para viáticos, alimentos y hospedaje",
        "parent_code": "601",
        "type": "agrupador",
        "is_active": True,
    },
    {
        "code": "608.01",
        "name": "Viáticos y alimentación",
        "description": "Gastos de alimentos, viáticos y consumos durante viajes",
        "parent_code": "608",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "608.02",
        "name": "Hospedaje y alojamiento",
        "description": "Gastos de hospedaje en hoteles o similares",
        "parent_code": "608",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "610",
        "name": "Servicios profesionales y administrativos",
        "description": "Agrupador para servicios de terceros",
        "parent_code": "601",
        "type": "agrupador",
        "is_active": True,
    },
    {
        "code": "610.01",
        "name": "Servicios profesionales externos",
        "description": "Honorarios y servicios administrativos contratados",
        "parent_code": "610",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "611",
        "name": "Suministros y gastos de oficina",
        "description": "Agrupador para papelería y consumibles",
        "parent_code": "601",
        "type": "agrupador",
        "is_active": True,
    },
    {
        "code": "611.01",
        "name": "Papelería y misceláneos",
        "description": "Material de oficina, papelería y consumibles",
        "parent_code": "611",
        "type": "subcuenta",
        "is_active": True,
    },
    {
        "code": "612",
        "name": "Gastos no deducibles para CUFIN",
        "description": "Agrupador para gastos no deducibles",
        "parent_code": "601",
        "type": "agrupador",
        "is_active": True,
    },
    {
        "code": "612.01",
        "name": "Gastos no deducibles para CUFIN",
        "description": "Cuentas no deducibles que afectan CUFIN",
        "parent_code": "612",
        "type": "subcuenta",
        "is_active": True,
    },
]


# Subset of SAT product/service catalog (ClaveProdServ CFDI)
SAT_PRODUCT_SERVICE_CATALOG_SEED: List[Dict[str, object]] = [
    {
        "code": "15101500",
        "name": "Combustibles para transporte",
        "description": "Gasolina y otros combustibles para vehículos",
        "unit_key": "LTR",
        "is_active": True,
    },
    {
        "code": "90101702",
        "name": "Servicios de alimentos preparados",
        "description": "Servicios de alimentos proporcionados por restaurantes",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "90111502",
        "name": "Servicios de hospedaje",
        "description": "Servicios de hotel y alojamiento temporal",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "43232408",
        "name": "Software como servicio (SaaS)",
        "description": "Licencias y suscripciones de software bajo demanda",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "14111503",
        "name": "Suministros de oficina",
        "description": "Papelería, cuadernos y artículos de escritorio",
        "unit_key": "H87",
        "is_active": True,
    },
    {
        "code": "81141600",
        "name": "Servicios administrativos",
        "description": "Servicios administrativos y de soporte empresarial",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "25172000",
        "name": "Mantenimiento y reparación de vehículos",
        "description": "Servicios de reparación, refacción y mantenimiento vehicular",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "80101500",
        "name": "Servicios profesionales administrativos",
        "description": "Servicios profesionales externos de administración y consultoría",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "90101800",
        "name": "Servicios de organización de eventos y banquetes",
        "description": "Atenciones, eventos y representaciones corporativas",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "93151500",
        "name": "Servicios de gestión y cumplimiento fiscal",
        "description": "Servicios asociados a impuestos, derechos y contribuciones",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "99999998",
        "name": "Servicios no deducibles",
        "description": "Claves genéricas para gastos no deducibles",
        "unit_key": "E48",
        "is_active": True,
    },
    {
        "code": "99999999",
        "name": "Servicios generales no clasificados",
        "description": "Clave genérica para gastos diversos",
        "unit_key": "E48",
        "is_active": True,
    },
]


VALID_FISCAL_REGIME_GROUPS: Set[str] = {
    "PM_GENERAL",
    "PF",
    "RESICO",
}


# Mapping between internal category slugs and their default SAT codes.
CATEGORY_SAT_MAPPING: Dict[str, Dict[str, object]] = {
    # 🚗 Transporte y movilidad
    "transporte_combustible": {
        "sat_account_code": "607.01",
        "sat_product_service_code": "15101500",
        "descripcion": "Combustibles y lubricantes para flotillas o traslados",
    },
    "mantenimiento_vehicular": {
        "sat_account_code": "601.56",
        "sat_product_service_code": "25172000",
        "descripcion": "Reparaciones, refacciones y mantenimiento de vehículos",
        "needs_review": False,
    },

    # ✈️ Viáticos, hospedaje y representación
    "viaticos_alimentos": {
        "sat_account_code": "608.01",
        "sat_product_service_code": "90101702",
        "descripcion": "Viáticos y alimentación del personal en viaje",
    },
    "hospedaje_alojamiento": {
        "sat_account_code": "608.02",
        "sat_product_service_code": "90111502",
        "descripcion": "Hospedajes, hoteles y estancias temporales",
    },
    "gastos_representacion": {
        "sat_account_code": "601.83",
        "sat_product_service_code": "90101800",
        "descripcion": "Atenciones a clientes, eventos o representación",
        "needs_review": True,
        "disallowed_regimes": ["RESICO"],
    },

    # 💼 Administración y oficina
    "gastos_administrativos": {
        "sat_account_code": "611.01",
        "sat_product_service_code": "14111503",
        "descripcion": "Papelería, consumibles y misceláneos administrativos",
    },
    "servicios_administrativos": {
        "sat_account_code": "601.32",
        "sat_product_service_code": "80101500",
        "descripcion": "Servicios administrativos internos o de soporte",
        "allowed_regimes": ["PM_GENERAL"],
        "needs_review": False,
    },
    "tecnologia_software": {
        "sat_account_code": "601.6",
        "sat_product_service_code": "43232408",
        "descripcion": "Suscripciones, SaaS y licencias de software",
        "allowed_regimes": ["PM_GENERAL"],
    },

    # 👔 Servicios profesionales y gastos generales
    "gastos_profesionales": {
        "sat_account_code": "610.01",
        "sat_product_service_code": "80101500",
        "descripcion": "Honorarios y servicios profesionales externos",
    },
    "gastos_generales": {
        "sat_account_code": "601.84",
        "sat_product_service_code": "99999999",
        "descripcion": "Gastos generales no clasificados",
        "needs_review": True,
    },

    # ⚖️ Impuestos y no deducibles
    "gastos_no_deducibles": {
        "sat_account_code": "612.01",
        "sat_product_service_code": "99999998",
        "descripcion": "Gastos no deducibles para CUFIN",
        "disallowed_regimes": ["RESICO"],
    },
    "impuestos_derechos": {
        "sat_account_code": "601.58",
        "sat_product_service_code": "93151500",
        "descripcion": "Impuestos, derechos y contribuciones",
    },
}


def _normalize_iterable(values: Iterable[str]) -> Set[str]:
    return {str(value) for value in values if value}


def validate_category_mapping_integrity(
    *,
    available_account_codes: Iterable[str],
    available_product_service_codes: Iterable[str],
    raise_on_missing: bool = True,
) -> Tuple[Set[str], Set[str]]:
    """Ensure CATEGORY_SAT_MAPPING references valid SAT catalogs and regimes."""

    available_account_codes_set = _normalize_iterable(available_account_codes)
    available_product_codes_set = _normalize_iterable(available_product_service_codes)

    missing_account_codes: Set[str] = set()
    missing_product_codes: Set[str] = set()

    for slug, mapping in CATEGORY_SAT_MAPPING.items():
        allowed = _normalize_iterable(mapping.get("allowed_regimes", []) or [])
        disallowed = _normalize_iterable(mapping.get("disallowed_regimes", []) or [])

        invalid_allowed = allowed - VALID_FISCAL_REGIME_GROUPS
        invalid_disallowed = disallowed - VALID_FISCAL_REGIME_GROUPS
        if invalid_allowed or invalid_disallowed:
            raise ValueError(
                "Regímenes fiscales inválidos en CATEGORY_SAT_MAPPING para"
                f" '{slug}': allowed={sorted(invalid_allowed)},"
                f" disallowed={sorted(invalid_disallowed)}"
            )

        overlap = allowed & disallowed
        if overlap:
            raise ValueError(
                "CATEGORY_SAT_MAPPING contiene regímenes simultáneamente"
                f" permitidos y restringidos para '{slug}': {sorted(overlap)}"
            )

        account_code = mapping.get("sat_account_code")
        if account_code and str(account_code) not in available_account_codes_set:
            missing_account_codes.add(str(account_code))

        product_code = mapping.get("sat_product_service_code")
        if product_code and str(product_code) not in available_product_codes_set:
            missing_product_codes.add(str(product_code))

    if (missing_account_codes or missing_product_codes) and raise_on_missing:
        details = []
        if missing_account_codes:
            details.append(
                f"códigos de cuenta faltantes: {sorted(missing_account_codes)}"
            )
        if missing_product_codes:
            details.append(
                f"códigos producto/servicio faltantes: {sorted(missing_product_codes)}"
            )
        raise ValueError(
            "CATEGORY_SAT_MAPPING hace referencia a códigos SAT ausentes en"
            f" el catálogo importado ({'; '.join(details)})"
        )

    return missing_account_codes, missing_product_codes

__all__ = [
    "SAT_ACCOUNT_CATALOG_SEED",
    "SAT_PRODUCT_SERVICE_CATALOG_SEED",
    "CATEGORY_SAT_MAPPING",
    "VALID_FISCAL_REGIME_GROUPS",
    "validate_category_mapping_integrity",
]
