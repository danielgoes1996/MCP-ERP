"""
Sistema de Validación de Expenses con Campos Faltantes.

Este módulo define qué campos son obligatorios para un expense completo
y proporciona funcionalidad para detectar campos faltantes que requieren
entrada del usuario.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de validación de un expense."""
    is_complete: bool
    missing_fields: List[str]
    missing_field_labels: Dict[str, str]
    warnings: List[str]


class ExpenseValidator:
    """Validador de campos obligatorios para expenses."""

    # Campos críticos que DEBEN estar presentes
    # Map to actual DB column names
    REQUIRED_FIELDS = {
        "description": "Descripción del gasto",
        "amount": "Monto total",
        "date": "Fecha del gasto",
        "category": "Categoría",
        "payment_account_id": "Cuenta de pago",
    }

    # Campos importantes pero opcionales (generan warnings)
    RECOMMENDED_FIELDS = {
        "proveedor_nombre": "Nombre del proveedor",
        "rfc_proveedor": "RFC del proveedor",
        "metodo_pago": "Forma de pago",
    }

    @classmethod
    def validate_expense_data(
        cls,
        expense_data: Dict[str, Any],
        context: str = "general"
    ) -> ValidationResult:
        """
        Valida si un expense tiene todos los campos necesarios.

        Args:
            expense_data: Datos del expense a validar
            context: Contexto de validación ("bulk_invoice", "manual", "general")

        Returns:
            ValidationResult con campos faltantes y warnings
        """
        missing = []
        missing_labels = {}
        warnings = []

        # Verificar campos requeridos
        for field, label in cls.REQUIRED_FIELDS.items():
            value = expense_data.get(field)

            # Considerar None, "", 0, [] como valores faltantes
            if value is None or value == "" or (isinstance(value, (list, dict)) and not value):
                missing.append(field)
                missing_labels[field] = label

        # Verificar campos recomendados (solo warnings)
        for field, label in cls.RECOMMENDED_FIELDS.items():
            value = expense_data.get(field)
            if value is None or value == "":
                warnings.append(f"Campo recomendado faltante: {label}")

        # Validaciones específicas por contexto
        if context == "bulk_invoice":
            # Para facturas, el RFC del proveedor es más importante
            if not expense_data.get("rfc_proveedor") and "rfc_proveedor" not in missing:
                missing.append("rfc_proveedor")
                missing_labels["rfc_proveedor"] = "RFC del proveedor (requerido para facturas)"

        is_complete = len(missing) == 0

        return ValidationResult(
            is_complete=is_complete,
            missing_fields=missing,
            missing_field_labels=missing_labels,
            warnings=warnings
        )

    @classmethod
    def get_completion_prompt_data(
        cls,
        expense_data: Dict[str, Any],
        invoice_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Genera los datos necesarios para mostrar un popup/modal de completado.

        Args:
            expense_data: Datos parciales del expense
            invoice_data: Datos de la factura (si disponible)

        Returns:
            Diccionario con estructura para el popup
        """
        validation = cls.validate_expense_data(expense_data, context="bulk_invoice")

        prompt_data = {
            "needs_completion": not validation.is_complete,
            "expense_id": expense_data.get("id"),
            "missing_fields": [],
            "prefilled_data": {},
            "invoice_reference": None,
        }

        # Construir lista de campos faltantes con metadata
        for field in validation.missing_fields:
            field_info = {
                "field_name": field,
                "label": validation.missing_field_labels.get(field, field),
                "type": cls._get_field_type(field),
                "required": True,
                "suggestions": cls._get_field_suggestions(field, expense_data, invoice_data),
            }
            prompt_data["missing_fields"].append(field_info)

        # Pre-llenar datos disponibles
        prompt_data["prefilled_data"] = {
            k: v for k, v in expense_data.items()
            if v is not None and v != "" and k not in validation.missing_fields
        }

        # Referencia a la factura
        if invoice_data:
            prompt_data["invoice_reference"] = {
                "uuid": invoice_data.get("uuid"),
                "filename": invoice_data.get("filename"),
                "provider_name": invoice_data.get("provider_name"),
                "total_amount": invoice_data.get("total_amount"),
            }

        return prompt_data

    @classmethod
    def _get_field_type(cls, field_name: str) -> str:
        """Determina el tipo de input necesario para un campo."""
        type_mapping = {
            "description": "text",
            "amount": "number",
            "date": "date",
            "category": "select",
            "payment_account_id": "select",
            "proveedor_nombre": "text",
            "rfc_proveedor": "text",
            "metodo_pago": "select",
        }
        return type_mapping.get(field_name, "text")

    @classmethod
    def _get_field_suggestions(
        cls,
        field_name: str,
        expense_data: Dict[str, Any],
        invoice_data: Optional[Dict[str, Any]]
    ) -> List[Any]:
        """
        Genera sugerencias para completar un campo basado en datos disponibles.
        """
        suggestions = []

        if not invoice_data:
            return suggestions

        # Mapeo de campos entre factura y expense
        field_mapping = {
            "description": ["provider_name", "filename"],
            "amount": ["total_amount"],
            "date": ["issued_date"],
            "proveedor_nombre": ["provider_name"],
            "rfc_proveedor": ["provider_rfc"],
        }

        # Buscar valores en invoice_data
        source_fields = field_mapping.get(field_name, [])
        for source_field in source_fields:
            value = invoice_data.get(source_field)
            if value and value not in suggestions:
                suggestions.append(value)

        return suggestions


# Instancia global del validador
expense_validator = ExpenseValidator()
