"""
Expense Validator - Validación y completado de campos de gastos
"""

import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ExpenseValidator:
    """
    Validador que verifica completitud de campos y genera formularios dinámicos
    """

    def __init__(self):
        # Campos requeridos absolutos (no se puede crear gasto sin estos)
        self.critical_fields = ['name', 'total_amount']

        # Campos importantes para una gestión profesional
        self.important_fields = ['date', 'employee_id', 'product_id', 'payment_mode']

        # Campos opcionales pero útiles
        self.optional_fields = ['unit_amount', 'partner_id', 'currency_id', 'description']

    def validate_expense_data(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida datos de gasto y determina qué campos faltan

        Args:
            expense_data: Datos del gasto desde LLM

        Returns:
            Dict con resultado de validación
        """
        validation_result = {
            'is_complete': True,
            'can_create': True,
            'missing_critical': [],
            'missing_important': [],
            'missing_optional': [],
            'completeness_score': 0,
            'suggestions': []
        }

        # Verificar campos críticos
        for field in self.critical_fields:
            if field not in expense_data or not expense_data[field]:
                validation_result['missing_critical'].append(field)
                validation_result['can_create'] = False

        # Verificar campos importantes
        for field in self.important_fields:
            if field not in expense_data or not expense_data[field]:
                validation_result['missing_important'].append(field)
                validation_result['is_complete'] = False

        # Verificar campos opcionales
        for field in self.optional_fields:
            if field not in expense_data or not expense_data[field]:
                validation_result['missing_optional'].append(field)

        # Calcular score de completitud
        total_fields = len(self.critical_fields + self.important_fields + self.optional_fields)
        present_fields = total_fields - len(validation_result['missing_critical'] +
                                          validation_result['missing_important'] +
                                          validation_result['missing_optional'])
        validation_result['completeness_score'] = round((present_fields / total_fields) * 100)

        # Generar sugerencias
        validation_result['suggestions'] = self._generate_suggestions(expense_data, validation_result)

        logger.info(f"Validación completada - Score: {validation_result['completeness_score']}%")
        return validation_result

    def _generate_suggestions(self, expense_data: Dict[str, Any], validation: Dict[str, Any]) -> List[str]:
        """
        Genera sugerencias para mejorar el gasto
        """
        suggestions = []

        # Sugerencias para campos críticos
        if 'name' in validation['missing_critical']:
            suggestions.append("⚠️ Se requiere una descripción del gasto")

        if 'total_amount' in validation['missing_critical']:
            suggestions.append("⚠️ Se requiere el monto total del gasto")

        # Sugerencias para campos importantes
        if 'date' in validation['missing_important']:
            suggestions.append("📅 Agregar fecha del gasto mejora el control")

        if 'employee_id' in validation['missing_important']:
            suggestions.append("👤 Especificar empleado facilita los reembolsos")

        if 'product_id' in validation['missing_important']:
            suggestions.append("🏷️ Categorizar el gasto ayuda en contabilidad")

        if 'payment_mode' in validation['missing_important']:
            suggestions.append("💳 Indicar forma de pago acelera reembolsos")

        # Sugerencias para campos opcionales
        if 'partner_id' in validation['missing_optional']:
            suggestions.append("🏪 Agregar proveedor mejora trazabilidad")

        if 'unit_amount' in validation['missing_optional']:
            suggestions.append("🧮 Especificar subtotal ayuda con impuestos")

        # Sugerencias inteligentes basadas en contenido
        if expense_data.get('name'):
            name_lower = expense_data['name'].lower()

            if any(word in name_lower for word in ['gasolina', 'combustible', 'gas']):
                if 'product_id' in validation['missing_important']:
                    suggestions.append("⛽ Sugerencia: Categoría → Combustible")

            if any(word in name_lower for word in ['restaurante', 'comida', 'almuerzo']):
                if 'product_id' in validation['missing_important']:
                    suggestions.append("🍽️ Sugerencia: Categoría → Alimentos y Bebidas")

            if any(word in name_lower for word in ['hotel', 'hospedaje']):
                if 'product_id' in validation['missing_important']:
                    suggestions.append("🏨 Sugerencia: Categoría → Hospedaje")

        return suggestions

    def create_completion_form(self, expense_data: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea formulario dinámico para completar campos faltantes

        Args:
            expense_data: Datos actuales del gasto
            validation: Resultado de validación

        Returns:
            Dict con formulario para el frontend
        """
        form_data = {
            'form_id': f"expense_completion_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'title': 'Completar información del gasto',
            'subtitle': f'Completitud actual: {validation["completeness_score"]}%',
            'can_skip': validation['can_create'],
            'sections': []
        }

        # Sección de campos críticos (si los hay)
        if validation['missing_critical']:
            form_data['sections'].append({
                'title': '⚠️ Campos Requeridos',
                'description': 'Estos campos son obligatorios para crear el gasto',
                'priority': 'critical',
                'fields': self._create_fields_for_section(validation['missing_critical'], expense_data)
            })

        # Sección de campos importantes
        if validation['missing_important']:
            form_data['sections'].append({
                'title': '📋 Información Importante',
                'description': 'Estos campos mejoran la gestión profesional del gasto',
                'priority': 'important',
                'fields': self._create_fields_for_section(validation['missing_important'], expense_data)
            })

        # Sección de campos opcionales (solo si hay pocos faltantes)
        if validation['missing_optional'] and len(validation['missing_optional']) <= 3:
            form_data['sections'].append({
                'title': '➕ Información Adicional',
                'description': 'Campos opcionales para mayor detalle',
                'priority': 'optional',
                'fields': self._create_fields_for_section(validation['missing_optional'], expense_data)
            })

        # Agregar sugerencias
        if validation['suggestions']:
            form_data['suggestions'] = validation['suggestions']

        # Agregar datos actuales para referencia
        form_data['current_data'] = self._format_current_data(expense_data)

        return form_data

    def _create_fields_for_section(self, field_names: List[str], expense_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Crea campos del formulario para una sección específica
        """
        field_definitions = {
            'name': {
                'id': 'name',
                'label': 'Descripción del gasto',
                'type': 'text',
                'placeholder': 'Ej: Gasolina para vehículo de empresa',
                'required': True,
                'help': 'Describe brevemente en qué se gastó'
            },
            'total_amount': {
                'id': 'total_amount',
                'label': 'Monto total (MXN)',
                'type': 'number',
                'placeholder': '0.00',
                'required': True,
                'help': 'Monto total incluyendo impuestos'
            },
            'date': {
                'id': 'date',
                'label': 'Fecha del gasto',
                'type': 'date',
                'placeholder': datetime.now().strftime('%Y-%m-%d'),
                'required': False,
                'help': 'Fecha en que se realizó el gasto'
            },
            'employee_id': {
                'id': 'employee_id',
                'label': 'Empleado',
                'type': 'select',
                'required': False,
                'help': 'Empleado que realizó el gasto',
                'options': [
                    {'value': 1, 'label': 'Daniel Gómez'},
                    {'value': 2, 'label': 'Otro empleado'}
                ]
            },
            'product_id': {
                'id': 'product_id',
                'label': 'Categoría de gasto',
                'type': 'select',
                'required': False,
                'help': 'Tipo de gasto para contabilidad',
                'options': [
                    {'value': 'combustible', 'label': '⛽ Combustible'},
                    {'value': 'alimentos', 'label': '🍽️ Alimentos y Bebidas'},
                    {'value': 'transporte', 'label': '🚗 Transporte'},
                    {'value': 'hospedaje', 'label': '🏨 Hospedaje'},
                    {'value': 'comunicacion', 'label': '📞 Comunicación'},
                    {'value': 'materiales', 'label': '📋 Materiales de Oficina'},
                    {'value': 'marketing', 'label': '📢 Marketing y Publicidad'},
                    {'value': 'capacitacion', 'label': '🎓 Capacitación'},
                    {'value': 'representacion', 'label': '🤝 Gastos de Representación'},
                    {'value': 'otros', 'label': '📦 Otros Gastos'}
                ]
            },
            'payment_mode': {
                'id': 'payment_mode',
                'label': 'Forma de pago',
                'type': 'select',
                'required': False,
                'help': 'Quién pagó el gasto',
                'options': [
                    {'value': 'own_account', 'label': '💳 Empleado (a reembolsar)'},
                    {'value': 'company_account', 'label': '🏢 Empresa (pago directo)'}
                ]
            },
            'partner_id': {
                'id': 'partner_id',
                'label': 'Proveedor/Establecimiento',
                'type': 'text',
                'placeholder': 'Ej: Pemex, Walmart, etc.',
                'required': False,
                'help': 'Nombre del proveedor o establecimiento'
            },
            'unit_amount': {
                'id': 'unit_amount',
                'label': 'Subtotal (sin IVA)',
                'type': 'number',
                'placeholder': '0.00',
                'required': False,
                'help': 'Monto sin impuestos'
            },
            'currency_id': {
                'id': 'currency_id',
                'label': 'Moneda',
                'type': 'select',
                'required': False,
                'help': 'Moneda del gasto',
                'options': [
                    {'value': 'MXN', 'label': '🇲🇽 Peso Mexicano (MXN)'},
                    {'value': 'USD', 'label': '🇺🇸 Dólar Americano (USD)'},
                    {'value': 'EUR', 'label': '🇪🇺 Euro (EUR)'}
                ]
            },
            'description': {
                'id': 'description',
                'label': 'Notas adicionales',
                'type': 'textarea',
                'placeholder': 'Información adicional sobre el gasto...',
                'required': False,
                'help': 'Detalles adicionales o justificación del gasto'
            }
        }

        fields = []
        for field_name in field_names:
            if field_name in field_definitions:
                field = field_definitions[field_name].copy()

                # Agregar valor actual si existe
                if field_name in expense_data:
                    field['current_value'] = expense_data[field_name]

                fields.append(field)

        return fields

    def _format_current_data(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formatea los datos actuales para mostrar al usuario
        """
        formatted = {}

        for key, value in expense_data.items():
            if value is not None and value != '':
                if key == 'total_amount':
                    formatted['Monto'] = f"${value:,.2f} MXN"
                elif key == 'name':
                    formatted['Descripción'] = value
                elif key == 'date':
                    formatted['Fecha'] = value
                elif key == 'payment_mode':
                    mode_map = {
                        'own_account': 'Empleado (a reembolsar)',
                        'company_account': 'Empresa (pago directo)'
                    }
                    formatted['Forma de pago'] = mode_map.get(value, value)
                else:
                    formatted[key.replace('_', ' ').title()] = str(value)

        return formatted

    def validate_expense_payload(self, params: Dict[str, Any]) -> Tuple[bool, List[str], Any]:
        """
        Valida payload completo de gasto y crea modelo

        Returns:
            Tuple[bool, List[str], ExpenseModel]: (is_valid, errors, model)
        """
        try:
            from core.expenses.models import ExpenseModel

            errors = []

            # Crear modelo desde parámetros
            expense_model = ExpenseModel.from_json(params)

            # Validar modelo
            validation_result = expense_model.validate()

            if not validation_result['is_valid']:
                errors.extend(validation_result['errors'])

            is_valid = len(errors) == 0

            return is_valid, errors, expense_model if is_valid else None

        except Exception as e:
            return False, [f"Error creando modelo: {str(e)}"], None

    def get_validation_summary(self, errors: List[str]) -> str:
        """
        Genera resumen de errores de validación
        """
        if not errors:
            return "Validación exitosa"

        return f"Encontrados {len(errors)} errores: {'; '.join(errors[:3])}{'...' if len(errors) > 3 else ''}"


# Instancia global
expense_validator = ExpenseValidator()


def validate_expense(expense_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función de conveniencia para validar gastos
    """
    return expense_validator.validate_expense_data(expense_data)