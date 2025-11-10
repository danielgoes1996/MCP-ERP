"""
Validador de campos de gastos con generación de templates adaptativos
Detecta campos faltantes y genera respuestas según el canal (web/WhatsApp)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de validación de campos"""
    is_complete: bool
    missing_fields: List[str]
    extracted_fields: Dict[str, Any]
    completion_percentage: float
    adaptive_template: Dict[str, Any]


class ExpenseFieldValidator:
    """
    Validador inteligente de campos de gastos
    Genera templates adaptativos según el canal de entrada
    """

    # Campos obligatorios mínimos para crear un gasto
    REQUIRED_FIELDS = [
        'description',
        'amount',
        'date',
        'payment_account_id'
    ]

    # Campos opcionales pero recomendados
    OPTIONAL_FIELDS = [
        'category',
        'merchant_name',
        'rfc_proveedor',
        'subtotal',
        'iva_16',
        'ticket_folio'
    ]

    # Mapeo de nombres de campo a nombres amigables
    FIELD_LABELS = {
        'description': 'Descripción del gasto',
        'amount': 'Monto total',
        'date': 'Fecha del gasto',
        'payment_account_id': 'Cuenta de pago',
        'category': 'Categoría',
        'merchant_name': 'Nombre del comercio',
        'rfc_proveedor': 'RFC del proveedor',
        'subtotal': 'Subtotal',
        'iva_16': 'IVA 16%',
        'ticket_folio': 'Folio del ticket'
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_expense_data(
        self,
        extracted_data: Dict[str, Any],
        channel: str = "web"
    ) -> ValidationResult:
        """
        Validar completitud de datos de gasto

        Args:
            extracted_data: Datos extraídos del OCR o entrada manual
            channel: Canal de entrada (web, whatsapp)

        Returns:
            ValidationResult con campos faltantes y template adaptativo
        """
        # Identificar campos presentes y faltantes
        present_fields = {}
        missing_fields = []

        for field in self.REQUIRED_FIELDS:
            value = extracted_data.get(field)
            if value is not None and str(value).strip():
                present_fields[field] = value
            else:
                missing_fields.append(field)

        # Calcular porcentaje de completitud
        total_fields = len(self.REQUIRED_FIELDS) + len(self.OPTIONAL_FIELDS)
        present_count = len(present_fields)

        # Contar opcionales presentes
        for field in self.OPTIONAL_FIELDS:
            if extracted_data.get(field):
                present_count += 1

        completion_percentage = (present_count / total_fields) * 100

        # Determinar si está completo
        is_complete = len(missing_fields) == 0

        # Generar template adaptativo
        adaptive_template = self._generate_adaptive_template(
            missing_fields=missing_fields,
            extracted_data=extracted_data,
            channel=channel
        )

        return ValidationResult(
            is_complete=is_complete,
            missing_fields=missing_fields,
            extracted_fields=present_fields,
            completion_percentage=completion_percentage,
            adaptive_template=adaptive_template
        )

    def _generate_adaptive_template(
        self,
        missing_fields: List[str],
        extracted_data: Dict[str, Any],
        channel: str
    ) -> Dict[str, Any]:
        """
        Generar template adaptativo según el canal

        Args:
            missing_fields: Lista de campos faltantes
            extracted_data: Datos ya extraídos
            channel: Canal de comunicación (web, whatsapp)

        Returns:
            Template adaptativo para completar campos
        """
        if channel == "whatsapp":
            return self._generate_whatsapp_template(missing_fields, extracted_data)
        else:
            return self._generate_web_template(missing_fields, extracted_data)

    def _generate_whatsapp_template(
        self,
        missing_fields: List[str],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generar template para WhatsApp Business API

        Returns:
            Template interactivo de WhatsApp
        """
        if not missing_fields:
            return {
                "type": "confirmation",
                "message": "✅ *Gasto registrado exitosamente*\n\n" +
                          self._format_expense_summary(extracted_data)
            }

        # Mensaje principal
        message = "📋 *Necesito algunos datos adicionales:*\n\n"

        # Listar campos faltantes
        for i, field in enumerate(missing_fields, 1):
            label = self.FIELD_LABELS.get(field, field)
            message += f"{i}. {label}\n"

        message += "\n📝 Por favor proporciona la información faltante."

        # Generar botones interactivos para opciones comunes
        buttons = []

        if 'payment_account_id' in missing_fields:
            buttons.append({
                "type": "reply",
                "reply": {
                    "id": "select_account",
                    "title": "Seleccionar cuenta"
                }
            })

        if 'category' in missing_fields:
            buttons.append({
                "type": "reply",
                "reply": {
                    "id": "select_category",
                    "title": "Seleccionar categoría"
                }
            })

        return {
            "type": "interactive",
            "message": message,
            "buttons": buttons,
            "missing_fields": missing_fields,
            "extracted_data": extracted_data
        }

    def _generate_web_template(
        self,
        missing_fields: List[str],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generar template para interfaz web

        Returns:
            Configuración de formulario dinámico
        """
        if not missing_fields:
            return {
                "type": "success",
                "message": "Gasto registrado exitosamente",
                "data": extracted_data
            }

        # Generar configuración de campos de formulario
        form_fields = []

        for field in missing_fields:
            field_config = {
                "name": field,
                "label": self.FIELD_LABELS.get(field, field),
                "required": field in self.REQUIRED_FIELDS
            }

            # Configuración específica por tipo de campo
            if field == 'amount':
                field_config.update({
                    "type": "number",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0"
                })
            elif field == 'date':
                field_config.update({
                    "type": "date",
                    "max": datetime.now().strftime("%Y-%m-%d")
                })
            elif field == 'payment_account_id':
                field_config.update({
                    "type": "select",
                    "fetch_options": "/payment-accounts?active_only=true"
                })
            elif field == 'category':
                field_config.update({
                    "type": "select",
                    "options": [
                        "combustible",
                        "alimentos",
                        "transporte",
                        "servicios",
                        "suministros_oficina",
                        "otros"
                    ]
                })
            else:
                field_config.update({
                    "type": "text",
                    "placeholder": f"Ingrese {self.FIELD_LABELS.get(field, field).lower()}"
                })

            form_fields.append(field_config)

        return {
            "type": "form",
            "message": "Complete los campos faltantes para registrar el gasto",
            "fields": form_fields,
            "extracted_data": extracted_data,
            "completion_percentage": len(extracted_data) / (len(extracted_data) + len(missing_fields)) * 100
        }

    def _format_expense_summary(self, data: Dict[str, Any]) -> str:
        """Formatear resumen del gasto para confirmación"""
        summary = []

        if data.get('description'):
            summary.append(f"📝 {data['description']}")

        if data.get('amount'):
            summary.append(f"💰 ${data['amount']:,.2f} MXN")

        if data.get('merchant_name'):
            summary.append(f"🏪 {data['merchant_name']}")

        if data.get('date'):
            summary.append(f"📅 {data['date']}")

        if data.get('category'):
            summary.append(f"🏷️ {data['category']}")

        return "\n".join(summary)

    def validate_and_prepare_expense(
        self,
        ocr_result: Dict[str, Any],
        user_data: Dict[str, Any],
        channel: str = "web"
    ) -> Tuple[bool, Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Validar y preparar gasto para creación

        Args:
            ocr_result: Resultado del OCR
            user_data: Datos adicionales del usuario (payment_account_id, etc.)
            channel: Canal de entrada

        Returns:
            Tupla (puede_crear, datos_preparados, template_si_incompleto)
        """
        # Combinar datos de OCR con datos del usuario
        combined_data = {**ocr_result, **user_data}

        # Validar completitud
        validation = self.validate_expense_data(combined_data, channel)

        if validation.is_complete:
            # Preparar datos finales para creación
            prepared_data = self._prepare_final_expense_data(
                validation.extracted_fields,
                ocr_result
            )
            return (True, prepared_data, None)
        else:
            # Retornar template para completar campos
            return (False, validation.extracted_fields, validation.adaptive_template)

    def _prepare_final_expense_data(
        self,
        validated_fields: Dict[str, Any],
        ocr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preparar datos finales para crear gasto

        Args:
            validated_fields: Campos validados y completos
            ocr_result: Resultado original del OCR para metadata

        Returns:
            Diccionario con estructura completa de gasto
        """
        import json

        prepared = {
            # Campos básicos
            "description": validated_fields['description'],
            "amount": float(validated_fields['amount']),
            "date": validated_fields['date'],
            "payment_account_id": int(validated_fields['payment_account_id']),

            # Campos opcionales
            "category": validated_fields.get('category', 'General'),
            "merchant_name": validated_fields.get('merchant_name'),
            "rfc_proveedor": validated_fields.get('rfc_proveedor'),

            # Desglose de impuestos
            "subtotal": validated_fields.get('subtotal'),
            "iva_16": validated_fields.get('iva_16', 0),
            "iva_8": validated_fields.get('iva_8', 0),
            "iva_0": validated_fields.get('iva_0', 0),
            "ieps": validated_fields.get('ieps', 0),

            # Información del ticket
            "ticket_folio": validated_fields.get('ticket_folio'),
            "ticket_image_url": validated_fields.get('ticket_image_url'),

            # Estados
            "deducible": True,
            "requiere_factura": validated_fields.get('will_have_cfdi', True),
            "invoice_status": "pending",
            "cfdi_status": "no_disponible",

            # Metadata con datos completos del OCR
            "metadata": json.dumps({
                "ocr_confidence": ocr_result.get('confidence', 0),
                "ocr_raw_text": ocr_result.get('raw_text', ''),
                "extraction_timestamp": datetime.now().isoformat(),
                "validated_fields": list(validated_fields.keys())
            })
        }

        # Calcular impuestos incluidos como array
        impuestos = []
        if prepared.get('iva_16', 0) > 0:
            impuestos.append('IVA 16%')
        if prepared.get('iva_8', 0) > 0:
            impuestos.append('IVA 8%')
        if prepared.get('ieps', 0) > 0:
            impuestos.append('IEPS')

        prepared['impuestos_incluidos'] = json.dumps(impuestos) if impuestos else None

        return prepared


# Singleton instance
_validator_instance = None


def get_expense_validator() -> ExpenseFieldValidator:
    """Obtener instancia singleton del validador"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ExpenseFieldValidator()
    return _validator_instance
