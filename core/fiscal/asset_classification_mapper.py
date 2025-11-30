"""
Asset Classification Mapper

Maps SAT account codes to asset_class for automatic fixed asset detection.
Provides utility to convert classification results into asset registry data.

Author: System
Date: 2025-11-28
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# SAT Family → Internal Asset Class mapping
SAT_FAMILY_TO_ASSET_CLASS = {
    '151': 'terrenos',
    '152': 'edificios',
    '153': 'maquinaria',
    '154': 'vehiculos',
    '155': 'mobiliario',
    '156': 'equipo_computo',
    '157': 'equipo_comunicacion',
    '158': 'activos_biologicos',
    '118': 'activos_intangibles'
}

# Asset class labels (for UI)
ASSET_CLASS_LABELS = {
    'terrenos': 'Terrenos',
    'edificios': 'Edificios',
    'maquinaria': 'Maquinaria Industrial',
    'vehiculos': 'Vehículos',
    'mobiliario': 'Mobiliario y Equipo de Oficina',
    'equipo_computo': 'Equipo de Cómputo',
    'equipo_comunicacion': 'Equipo de Comunicación',
    'activos_biologicos': 'Activos Biológicos',
    'activos_intangibles': 'Activos Intangibles (Software, Licencias)'
}


def is_fixed_asset(sat_account_code: str) -> bool:
    """
    Determine if SAT account code represents a fixed asset.

    Args:
        sat_account_code: SAT code like "156.01", "154.02", etc.

    Returns:
        True if code belongs to fixed asset families (151-158, 118)

    Example:
        >>> is_fixed_asset("156.01")
        True
        >>> is_fixed_asset("601.48")
        False
    """
    if not sat_account_code:
        return False

    family = sat_account_code.split('.')[0]
    return family in SAT_FAMILY_TO_ASSET_CLASS


def get_asset_class_from_sat(sat_account_code: str) -> Optional[str]:
    """
    Get internal asset_class from SAT account code.

    Args:
        sat_account_code: SAT code like "156.01"

    Returns:
        Asset class string (e.g., "equipo_computo") or None

    Example:
        >>> get_asset_class_from_sat("156.01")
        'equipo_computo'
        >>> get_asset_class_from_sat("154.01")
        'vehiculos'
    """
    if not sat_account_code:
        return None

    family = sat_account_code.split('.')[0]
    return SAT_FAMILY_TO_ASSET_CLASS.get(family)


def get_asset_label(asset_class: str) -> str:
    """
    Get human-readable label for asset class.

    Args:
        asset_class: Internal class like "equipo_computo"

    Returns:
        Display label like "Equipo de Cómputo"
    """
    return ASSET_CLASS_LABELS.get(asset_class, asset_class.replace('_', ' ').title())


def extract_asset_data_from_classification(
    classification_dict: Dict[str, Any],
    parsed_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Extract fixed asset data from invoice classification result.

    Converts classification + parsed CFDI into structured data ready
    for creating a fixed_assets record.

    Args:
        classification_dict: Result from UniversalInvoiceEngineSystem
        parsed_data: Parsed CFDI data

    Returns:
        Dictionary with asset data ready for CreateFixedAssetRequest,
        or None if not a fixed asset

    Example:
        >>> classification = {
        ...     "sat_account_code": "156.01",
        ...     "metadata": {
        ...         "fixed_asset": {
        ...             "is_fixed_asset": True,
        ...             "asset_type": "equipo_computo",
        ...             "depreciation_rate_fiscal_annual": 30.0,
        ...             ...
        ...         }
        ...     }
        ... }
        >>> parsed_data = {
        ...     "uuid": "ABC123",
        ...     "total": 50000,
        ...     "fecha": "2025-11-28",
        ...     "emisor": {"nombre": "Dell", "rfc": "DEL850101ABC"},
        ...     "conceptos": [{"descripcion": "Laptop Dell"}]
        ... }
        >>> asset_data = extract_asset_data_from_classification(classification, parsed_data)
        >>> asset_data['description']
        'Laptop Dell'
        >>> asset_data['asset_class']
        'equipo_computo'
    """
    # Check if classification contains fixed asset metadata
    fixed_asset_meta = classification_dict.get('metadata', {}).get('fixed_asset')

    if not fixed_asset_meta or not fixed_asset_meta.get('is_fixed_asset'):
        return None

    # Extract SAT code and derive asset class
    sat_code = classification_dict.get('sat_account_code')
    asset_class = get_asset_class_from_sat(sat_code)

    if not asset_class:
        logger.warning(f"Could not determine asset_class from SAT code: {sat_code}")
        return None

    # Extract description from first concept
    conceptos = parsed_data.get('conceptos', [])
    description = conceptos[0].get('descripcion', 'Activo fijo') if conceptos else 'Activo fijo'

    # Extract supplier info
    emisor = parsed_data.get('emisor', {})
    supplier_name = emisor.get('nombre')
    supplier_rfc = emisor.get('rfc')

    # Extract financial data
    subtotal = parsed_data.get('subtotal', 0)
    total = parsed_data.get('total', 0)
    purchase_value = float(subtotal) if subtotal else float(total)

    # Extract purchase date
    fecha_str = parsed_data.get('fecha', '')
    try:
        from datetime import datetime
        purchase_date = datetime.fromisoformat(fecha_str.replace('Z', '+00:00')).date()
    except:
        from datetime import date
        purchase_date = date.today()

    # Build asset data
    asset_data = {
        'description': description,
        'asset_class': asset_class,
        'asset_category': sat_code.split('.')[0],  # SAT family

        # Purchase info
        'purchase_date': purchase_date,
        'supplier_name': supplier_name,
        'supplier_rfc': supplier_rfc,
        'purchase_value': purchase_value,
        'invoice_uuid': parsed_data.get('uuid'),

        # Depreciation rates (from RAG service)
        'depreciation_rate_accounting': fixed_asset_meta.get('depreciation_rate_accounting_annual'),
        'depreciation_years_accounting': fixed_asset_meta.get('depreciation_years_accounting'),
        'depreciation_rate_fiscal': fixed_asset_meta.get('depreciation_rate_fiscal_annual'),
        'depreciation_years_fiscal': fixed_asset_meta.get('depreciation_years_fiscal'),

        # Legal basis
        'legal_basis': fixed_asset_meta.get('legal_basis'),

        # Additional costs (empty initially, can be added later)
        'additional_costs': []
    }

    logger.info(
        f"Extracted asset data: {asset_class} - {description} (${purchase_value})"
    )

    return asset_data


def should_auto_create_asset(
    classification_dict: Dict[str, Any],
    min_amount: float = 2000.0,
    auto_create_enabled: bool = False
) -> bool:
    """
    Determine if asset should be auto-created based on business rules.

    Args:
        classification_dict: Classification result
        min_amount: Minimum amount threshold for auto-creation
        auto_create_enabled: Global flag for auto-creation

    Returns:
        True if asset should be automatically registered

    Business rules:
    1. Must be classified as fixed asset
    2. Amount must exceed threshold (default $2,000 MXN per LISR)
    3. Auto-creation must be enabled (default: False, requires user confirmation)
    """
    if not auto_create_enabled:
        return False

    fixed_asset_meta = classification_dict.get('metadata', {}).get('fixed_asset')

    if not fixed_asset_meta or not fixed_asset_meta.get('is_fixed_asset'):
        return False

    # Check amount threshold (from parsed_data if available)
    # This would need to be passed separately or extracted from context

    # For now, return False to require manual confirmation
    # Can be changed to True for fully automatic registration
    return False
