"""
Mapeos centralizados de categorías a cuentas contables.

Este módulo centraliza la lógica de mapeo de categorías de gastos
a cuentas contables SAT para evitar duplicación de código.
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Mapeo de categorías a códigos de cuenta contable SAT
CATEGORY_TO_ACCOUNT_CODE: Dict[str, str] = {
    # Combustibles y transporte
    'combustible': '6140',
    'combustibles': '6140',
    'gasolina': '6140',
    'diesel': '6140',
    'transporte': '6140',

    # Viajes y viáticos
    'viajes': '6150',
    'viaticos': '6150',
    'viáticos': '6150',
    'hospedaje': '6150',
    'hotel': '6150',
    'vuelos': '6150',
    'avion': '6150',

    # Alimentación
    'alimentos': '6150',
    'comida': '6150',
    'restaurante': '6150',
    'alimentacion': '6150',
    'alimentación': '6150',

    # Servicios
    'servicios': '6130',
    'servicios_profesionales': '6110',
    'consultoría': '6110',
    'consultoria': '6110',
    'asesoría': '6110',
    'asesoria': '6110',

    # Oficina y papelería
    'oficina': '6180',
    'papeleria': '6180',
    'papelería': '6180',
    'suministros': '6180',
    'material_oficina': '6180',

    # Honorarios
    'honorarios': '6110',
    'freelance': '6110',

    # Renta
    'renta': '6120',
    'arrendamiento': '6120',
    'alquiler': '6120',

    # Publicidad y marketing
    'publicidad': '6160',
    'marketing': '6160',
    'marketing_digital': '6160',
    'ads': '6160',
    'publicidad_digital': '6160',

    # Tecnología
    'software': '6180',
    'licencias': '6180',
    'suscripciones': '6180',
    'saas': '6180',
    'tecnologia': '6180',
    'tecnología': '6180',

    # Mantenimiento
    'mantenimiento': '6170',
    'reparaciones': '6170',
    'limpieza': '6170',

    # Servicios públicos
    'luz': '6130',
    'agua': '6130',
    'internet': '6130',
    'telefono': '6130',
    'teléfono': '6130',
    'servicios_publicos': '6130',
}

# Cuenta por defecto si no se encuentra mapeo
DEFAULT_ACCOUNT_CODE = '6180'  # Otros gastos


def get_account_code_for_category(categoria: Optional[str]) -> str:
    """
    Obtiene el código de cuenta contable para una categoría dada.

    Args:
        categoria: Nombre de la categoría (ej: "combustibles", "viajes")

    Returns:
        Código de cuenta contable (ej: "6140", "6150")

    Examples:
        >>> get_account_code_for_category("combustibles")
        "6140"
        >>> get_account_code_for_category("viajes")
        "6150"
        >>> get_account_code_for_category("categoria_desconocida")
        "6180"
    """
    if not categoria:
        logger.debug(f"No category provided, using default account: {DEFAULT_ACCOUNT_CODE}")
        return DEFAULT_ACCOUNT_CODE

    # Normalizar categoría (minúsculas, sin espacios extra)
    categoria_normalizada = categoria.strip().lower()

    # Buscar mapeo
    account_code = CATEGORY_TO_ACCOUNT_CODE.get(categoria_normalizada)

    if account_code:
        logger.debug(f"Mapped category '{categoria}' to account {account_code}")
        return account_code

    # Si no se encuentra, usar cuenta por defecto
    logger.warning(
        f"No mapping found for category '{categoria}', using default account {DEFAULT_ACCOUNT_CODE}"
    )
    return DEFAULT_ACCOUNT_CODE


def get_all_categories() -> Dict[str, str]:
    """
    Retorna todos los mapeos de categorías disponibles.

    Returns:
        Diccionario con categorías como keys y códigos de cuenta como values
    """
    return CATEGORY_TO_ACCOUNT_CODE.copy()


def get_categories_for_account(account_code: str) -> list[str]:
    """
    Obtiene todas las categorías que mapean a un código de cuenta dado.

    Args:
        account_code: Código de cuenta contable (ej: "6140")

    Returns:
        Lista de categorías que mapean a esa cuenta

    Examples:
        >>> get_categories_for_account("6140")
        ["combustible", "combustibles", "gasolina", "diesel", "transporte"]
    """
    return [
        categoria
        for categoria, codigo in CATEGORY_TO_ACCOUNT_CODE.items()
        if codigo == account_code
    ]


def register_custom_category_mapping(categoria: str, account_code: str) -> None:
    """
    Registra un mapeo personalizado de categoría a cuenta.

    Args:
        categoria: Nombre de la categoría
        account_code: Código de cuenta contable

    Note:
        Los mapeos personalizados tienen prioridad sobre los predefinidos.
    """
    categoria_normalizada = categoria.strip().lower()

    if categoria_normalizada in CATEGORY_TO_ACCOUNT_CODE:
        logger.warning(
            f"Overwriting existing mapping for '{categoria}': "
            f"{CATEGORY_TO_ACCOUNT_CODE[categoria_normalizada]} -> {account_code}"
        )

    CATEGORY_TO_ACCOUNT_CODE[categoria_normalizada] = account_code
    logger.info(f"Registered custom mapping: '{categoria}' -> {account_code}")
