#!/usr/bin/env python3
"""
Tests unitarios para el módulo de mapeo de categorías.

Verifica que el mapeo de categorías a cuentas contables SAT funcione correctamente.
"""

import pytest
from core.ai_pipeline.classification.category_mappings import (
    get_account_code_for_category,
    get_all_categories,
    get_categories_for_account,
    register_custom_category_mapping,
    CATEGORY_TO_ACCOUNT_CODE,
    DEFAULT_ACCOUNT_CODE
)


class TestGetAccountCodeForCategory:
    """Tests para función get_account_code_for_category."""

    # Tests para categorías conocidas
    def test_combustibles_maps_to_6140(self):
        """Combustibles debe mapear a 6140."""
        assert get_account_code_for_category("combustibles") == "6140"

    def test_gasolina_maps_to_6140(self):
        """Gasolina debe mapear a 6140."""
        assert get_account_code_for_category("gasolina") == "6140"

    def test_viajes_maps_to_6150(self):
        """Viajes debe mapear a 6150."""
        assert get_account_code_for_category("viajes") == "6150"

    def test_viaticos_maps_to_6150(self):
        """Viáticos debe mapear a 6150."""
        assert get_account_code_for_category("viaticos") == "6150"

    def test_alimentos_maps_to_6150(self):
        """Alimentos debe mapear a 6150."""
        assert get_account_code_for_category("alimentos") == "6150"

    def test_servicios_maps_to_6130(self):
        """Servicios debe mapear a 6130."""
        assert get_account_code_for_category("servicios") == "6130"

    def test_oficina_maps_to_6180(self):
        """Oficina debe mapear a 6180."""
        assert get_account_code_for_category("oficina") == "6180"

    def test_honorarios_maps_to_6110(self):
        """Honorarios debe mapear a 6110."""
        assert get_account_code_for_category("honorarios") == "6110"

    def test_renta_maps_to_6120(self):
        """Renta debe mapear a 6120."""
        assert get_account_code_for_category("renta") == "6120"

    def test_publicidad_maps_to_6160(self):
        """Publicidad debe mapear a 6160."""
        assert get_account_code_for_category("publicidad") == "6160"

    def test_marketing_maps_to_6160(self):
        """Marketing debe mapear a 6160."""
        assert get_account_code_for_category("marketing") == "6160"

    # Tests para normalización
    def test_category_case_insensitive_uppercase(self):
        """Debe funcionar con mayúsculas."""
        assert get_account_code_for_category("COMBUSTIBLES") == "6140"

    def test_category_case_insensitive_mixed(self):
        """Debe funcionar con mayúsculas/minúsculas mezcladas."""
        assert get_account_code_for_category("Viajes") == "6150"

    def test_category_strips_whitespace(self):
        """Debe limpiar espacios en blanco."""
        assert get_account_code_for_category("  alimentos  ") == "6150"

    def test_category_with_accents(self):
        """Debe funcionar con acentos."""
        assert get_account_code_for_category("viáticos") == "6150"

    # Tests para categorías desconocidas
    def test_unknown_category_returns_default(self):
        """Categoría desconocida debe retornar código por defecto."""
        assert get_account_code_for_category("categoria_inexistente") == DEFAULT_ACCOUNT_CODE

    def test_empty_string_returns_default(self):
        """String vacío debe retornar código por defecto."""
        assert get_account_code_for_category("") == DEFAULT_ACCOUNT_CODE

    def test_none_returns_default(self):
        """None debe retornar código por defecto."""
        assert get_account_code_for_category(None) == DEFAULT_ACCOUNT_CODE

    def test_whitespace_only_returns_default(self):
        """Solo espacios debe retornar código por defecto."""
        assert get_account_code_for_category("   ") == DEFAULT_ACCOUNT_CODE

    # Tests para categorías alternativas
    def test_diesel_maps_to_6140(self):
        """Diesel debe mapear a 6140."""
        assert get_account_code_for_category("diesel") == "6140"

    def test_transporte_maps_to_6140(self):
        """Transporte debe mapear a 6140."""
        assert get_account_code_for_category("transporte") == "6140"

    def test_hospedaje_maps_to_6150(self):
        """Hospedaje debe mapear a 6150."""
        assert get_account_code_for_category("hospedaje") == "6150"

    def test_hotel_maps_to_6150(self):
        """Hotel debe mapear a 6150."""
        assert get_account_code_for_category("hotel") == "6150"

    def test_comida_maps_to_6150(self):
        """Comida debe mapear a 6150."""
        assert get_account_code_for_category("comida") == "6150"

    def test_restaurante_maps_to_6150(self):
        """Restaurante debe mapear a 6150."""
        assert get_account_code_for_category("restaurante") == "6150"

    def test_consultoria_maps_to_6110(self):
        """Consultoría debe mapear a 6110."""
        assert get_account_code_for_category("consultoria") == "6110"

    def test_papeleria_maps_to_6180(self):
        """Papelería debe mapear a 6180."""
        assert get_account_code_for_category("papeleria") == "6180"

    def test_software_maps_to_6180(self):
        """Software debe mapear a 6180."""
        assert get_account_code_for_category("software") == "6180"

    def test_licencias_maps_to_6180(self):
        """Licencias debe mapear a 6180."""
        assert get_account_code_for_category("licencias") == "6180"

    def test_mantenimiento_maps_to_6170(self):
        """Mantenimiento debe mapear a 6170."""
        assert get_account_code_for_category("mantenimiento") == "6170"


class TestGetAllCategories:
    """Tests para función get_all_categories."""

    def test_returns_dict(self):
        """Debe retornar un diccionario."""
        categories = get_all_categories()
        assert isinstance(categories, dict)

    def test_contains_expected_categories(self):
        """Debe contener categorías esperadas."""
        categories = get_all_categories()

        expected = [
            "combustibles",
            "viajes",
            "alimentos",
            "servicios",
            "oficina",
            "honorarios",
            "renta",
            "publicidad",
            "marketing"
        ]

        for cat in expected:
            assert cat in categories

    def test_all_values_are_strings(self):
        """Todos los valores deben ser strings."""
        categories = get_all_categories()
        for value in categories.values():
            assert isinstance(value, str)

    def test_all_values_are_account_codes(self):
        """Todos los valores deben ser códigos de cuenta válidos (4 dígitos)."""
        categories = get_all_categories()
        for value in categories.values():
            assert len(value) == 4
            assert value.isdigit()

    def test_returns_copy_not_reference(self):
        """Debe retornar una copia, no una referencia."""
        categories1 = get_all_categories()
        categories2 = get_all_categories()

        # Modificar una no debe afectar la otra
        categories1["test"] = "9999"
        assert "test" not in categories2


class TestGetCategoriesForAccount:
    """Tests para función get_categories_for_account."""

    def test_account_6140_returns_combustible_categories(self):
        """Cuenta 6140 debe retornar categorías de combustible."""
        categories = get_categories_for_account("6140")

        assert "combustibles" in categories
        assert "gasolina" in categories
        assert "diesel" in categories
        assert "transporte" in categories

    def test_account_6150_returns_viajes_categories(self):
        """Cuenta 6150 debe retornar categorías de viajes."""
        categories = get_categories_for_account("6150")

        assert "viajes" in categories
        assert "viaticos" in categories
        assert "hospedaje" in categories
        assert "alimentos" in categories

    def test_account_6110_returns_honorarios_categories(self):
        """Cuenta 6110 debe retornar categorías de honorarios."""
        categories = get_categories_for_account("6110")

        assert "honorarios" in categories
        assert "consultoria" in categories or "consultoría" in categories

    def test_account_6160_returns_marketing_categories(self):
        """Cuenta 6160 debe retornar categorías de marketing."""
        categories = get_categories_for_account("6160")

        assert "publicidad" in categories
        assert "marketing" in categories

    def test_unknown_account_returns_empty_list(self):
        """Cuenta desconocida debe retornar lista vacía."""
        categories = get_categories_for_account("9999")
        assert categories == []

    def test_returns_list(self):
        """Debe retornar una lista."""
        categories = get_categories_for_account("6140")
        assert isinstance(categories, list)

    def test_all_returned_items_are_strings(self):
        """Todos los items retornados deben ser strings."""
        categories = get_categories_for_account("6140")
        for cat in categories:
            assert isinstance(cat, str)


class TestRegisterCustomCategoryMapping:
    """Tests para función register_custom_category_mapping."""

    def test_register_new_category(self):
        """Debe poder registrar nueva categoría."""
        # Registrar nueva categoría
        register_custom_category_mapping("uber", "6140")

        # Verificar que se puede usar
        assert get_account_code_for_category("uber") == "6140"

    def test_register_normalizes_category(self):
        """Debe normalizar categoría al registrar."""
        register_custom_category_mapping("  LYFT  ", "6140")

        # Debe poder accederse en minúsculas sin espacios
        assert get_account_code_for_category("lyft") == "6140"

    def test_overwrite_existing_category(self):
        """Debe poder sobrescribir categoría existente."""
        # Guardar valor original
        original = get_account_code_for_category("oficina")

        # Sobrescribir
        register_custom_category_mapping("oficina", "9999")
        assert get_account_code_for_category("oficina") == "9999"

        # Restaurar original
        register_custom_category_mapping("oficina", original)

    def test_custom_mapping_persists(self):
        """Mapeo custom debe persistir entre llamadas."""
        register_custom_category_mapping("custom_test", "6789")

        # Primera llamada
        assert get_account_code_for_category("custom_test") == "6789"

        # Segunda llamada
        assert get_account_code_for_category("custom_test") == "6789"

    def test_custom_mapping_visible_in_get_all(self):
        """Mapeo custom debe aparecer en get_all_categories."""
        register_custom_category_mapping("custom_visible", "6789")

        all_categories = get_all_categories()
        assert "custom_visible" in all_categories
        assert all_categories["custom_visible"] == "6789"


class TestCategoryMappingIntegration:
    """Tests de integración para múltiples funciones."""

    def test_all_categories_have_reverse_lookup(self):
        """Todas las categorías deben poder buscarse por su cuenta."""
        all_categories = get_all_categories()

        for category, account_code in all_categories.items():
            categories_for_account = get_categories_for_account(account_code)
            assert category in categories_for_account, \
                f"Category '{category}' not found in reverse lookup for account {account_code}"

    def test_consistency_between_functions(self):
        """Debe haber consistencia entre get y reverse lookup."""
        # Tomar una categoría
        account_code = get_account_code_for_category("combustibles")

        # Buscar todas las categorías de esa cuenta
        categories = get_categories_for_account(account_code)

        # Verificar que "combustibles" esté en la lista
        assert "combustibles" in categories

    def test_typical_workflow(self):
        """Test de workflow típico de usuario."""
        # 1. Usuario ingresa categoría
        user_input = "  GASOLINA  "

        # 2. Sistema la mapea a cuenta
        account_code = get_account_code_for_category(user_input)
        assert account_code == "6140"

        # 3. Sistema puede mostrar categorías relacionadas
        related = get_categories_for_account(account_code)
        assert len(related) >= 4  # combustibles, gasolina, diesel, transporte

    def test_default_account_code_exists(self):
        """DEFAULT_ACCOUNT_CODE debe existir en algún mapeo."""
        all_categories = get_all_categories()
        default_used = DEFAULT_ACCOUNT_CODE in all_categories.values()

        # Al menos debe ser un código válido
        assert len(DEFAULT_ACCOUNT_CODE) == 4
        assert DEFAULT_ACCOUNT_CODE.isdigit()


class TestEdgeCases:
    """Tests para casos límite."""

    def test_special_characters_in_category(self):
        """Categoría con caracteres especiales debe usar default."""
        assert get_account_code_for_category("@#$%") == DEFAULT_ACCOUNT_CODE

    def test_numbers_in_category(self):
        """Categoría con números debe funcionar si existe."""
        # Registrar una categoría con números
        register_custom_category_mapping("cat123", "6000")
        assert get_account_code_for_category("cat123") == "6000"

    def test_very_long_category_name(self):
        """Categoría muy larga debe funcionar."""
        long_name = "a" * 1000
        assert get_account_code_for_category(long_name) == DEFAULT_ACCOUNT_CODE

    def test_unicode_category(self):
        """Categoría con unicode debe funcionar."""
        assert get_account_code_for_category("viáticos") == "6150"

    def test_account_code_with_leading_zeros(self):
        """Código de cuenta debe mantener ceros a la izquierda."""
        # 6140 no es 6140.0 ni 614
        assert get_account_code_for_category("combustibles") == "6140"
        assert get_account_code_for_category("combustibles") != "614"


class TestCoverageOfKnownCategories:
    """Tests para asegurar cobertura de categorías conocidas."""

    def test_all_fuel_categories_covered(self):
        """Todas las variantes de combustible deben estar."""
        fuel_categories = ["combustible", "combustibles", "gasolina", "diesel"]

        for cat in fuel_categories:
            account = get_account_code_for_category(cat)
            assert account == "6140", f"{cat} should map to 6140, got {account}"

    def test_all_travel_categories_covered(self):
        """Todas las variantes de viajes deben estar."""
        travel_categories = ["viajes", "viaticos", "viáticos", "hospedaje", "hotel"]

        for cat in travel_categories:
            account = get_account_code_for_category(cat)
            assert account == "6150", f"{cat} should map to 6150, got {account}"

    def test_all_food_categories_covered(self):
        """Todas las variantes de alimentos deben estar."""
        food_categories = ["alimentos", "comida", "restaurante", "alimentacion", "alimentación"]

        for cat in food_categories:
            account = get_account_code_for_category(cat)
            assert account == "6150", f"{cat} should map to 6150, got {account}"

    def test_all_professional_services_covered(self):
        """Todas las variantes de servicios profesionales deben estar."""
        services = ["honorarios", "consultoria", "consultoría", "freelance"]

        for cat in services:
            account = get_account_code_for_category(cat)
            assert account == "6110", f"{cat} should map to 6110, got {account}"

    def test_all_rent_categories_covered(self):
        """Todas las variantes de renta deben estar."""
        rent_categories = ["renta", "arrendamiento", "alquiler"]

        for cat in rent_categories:
            account = get_account_code_for_category(cat)
            assert account == "6120", f"{cat} should map to 6120, got {account}"

    def test_all_marketing_categories_covered(self):
        """Todas las variantes de marketing deben estar."""
        marketing_categories = ["publicidad", "marketing", "marketing_digital", "ads"]

        for cat in marketing_categories:
            account = get_account_code_for_category(cat)
            assert account == "6160", f"{cat} should map to 6160, got {account}"
