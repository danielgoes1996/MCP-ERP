"""
Sistema de validación completo para gastos empresariales
Incluye validaciones de negocio, CFDI y campos requeridos
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
import re
import base64
import xml.etree.ElementTree as ET
from core.expense_models import ExpenseModel, Supplier, TaxInfo, Attachment, AttachmentType


class ExpenseValidator:
    """Validador completo de gastos empresariales"""

    def __init__(self):
        self.required_fields = [
            'name', 'description', 'amount', 'expense_date', 'supplier'
        ]

        # Patrones de validación
        self.rfc_pattern = re.compile(r'^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$')
        self.uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')

        # Límites de negocio
        self.max_amount = 100000.0  # Máximo $100,000
        self.max_days_old = 30  # Máximo 30 días de antigüedad

    def validate_expense_payload(self, payload: Dict[str, Any]) -> Tuple[bool, List[str], ExpenseModel]:
        """
        Valida un payload completo de gasto y retorna el modelo validado

        Args:
            payload: Diccionario con datos del gasto

        Returns:
            Tuple[bool, List[str], ExpenseModel]: (es_válido, errores, modelo)
        """
        errors = []

        try:
            # 1. Validaciones de campos requeridos
            missing_fields = self._validate_required_fields(payload)
            errors.extend(missing_fields)

            # 2. Validaciones de formato y tipo
            format_errors = self._validate_field_formats(payload)
            errors.extend(format_errors)

            # 3. Validaciones de negocio
            business_errors = self._validate_business_rules(payload)
            errors.extend(business_errors)

            # 4. Crear modelo si no hay errores críticos
            if not errors:
                try:
                    expense_model = ExpenseModel.from_json(payload)

                    # 5. Validaciones del modelo completo
                    model_errors = expense_model.validate()
                    errors.extend(model_errors)

                    # 6. Validaciones específicas de CFDI
                    cfdi_errors = self._validate_cfdi_attachments(expense_model)
                    errors.extend(cfdi_errors)

                    return len(errors) == 0, errors, expense_model

                except Exception as e:
                    errors.append(f"Error creando modelo: {str(e)}")
                    return False, errors, None

            return False, errors, None

        except Exception as e:
            errors.append(f"Error general de validación: {str(e)}")
            return False, errors, None

    def _validate_required_fields(self, payload: Dict[str, Any]) -> List[str]:
        """Valida que todos los campos requeridos estén presentes"""
        errors = []

        for field in self.required_fields:
            if field not in payload:
                errors.append(f"Campo requerido faltante: {field}")
                continue

            # Validaciones específicas por campo
            if field == 'supplier':
                supplier_data = payload.get('supplier', {})
                if not isinstance(supplier_data, dict):
                    errors.append("Campo 'supplier' debe ser un objeto")
                elif 'name' not in supplier_data or not supplier_data['name']:
                    errors.append("Nombre del proveedor es requerido")

            elif field in ['name', 'description']:
                if not payload[field] or len(str(payload[field]).strip()) < 3:
                    errors.append(f"Campo '{field}' debe tener al menos 3 caracteres")

            elif field == 'amount':
                try:
                    amount = float(payload[field])
                    if amount <= 0:
                        errors.append("El monto debe ser mayor a 0")
                except (ValueError, TypeError):
                    errors.append("El monto debe ser un número válido")

            elif field == 'expense_date':
                if not self._validate_date_format(payload[field]):
                    errors.append("Fecha del gasto debe estar en formato ISO (YYYY-MM-DD)")

        return errors

    def _validate_field_formats(self, payload: Dict[str, Any]) -> List[str]:
        """Valida formatos específicos de campos"""
        errors = []

        # Validar RFC si está presente
        supplier = payload.get('supplier', {})
        if 'rfc' in supplier and supplier['rfc']:
            if not self.rfc_pattern.match(supplier['rfc'].upper()):
                errors.append("RFC del proveedor tiene formato inválido")

        # Validar UUID de CFDI si está presente
        if 'cfdi_uuid' in payload and payload['cfdi_uuid']:
            if not self.uuid_pattern.match(payload['cfdi_uuid']):
                errors.append("UUID del CFDI tiene formato inválido")

        # Validar información de impuestos
        if 'tax_info' in payload:
            tax_info = payload['tax_info']
            try:
                subtotal = float(tax_info.get('subtotal', 0))
                iva_amount = float(tax_info.get('iva_amount', 0))
                total = float(tax_info.get('total', 0))

                if subtotal <= 0:
                    errors.append("Subtotal debe ser mayor a 0")

                if total < subtotal:
                    errors.append("Total no puede ser menor al subtotal")

                # Verificar que el IVA sea consistente
                expected_iva = subtotal * 0.16
                if abs(iva_amount - expected_iva) > 0.01:
                    errors.append(f"IVA inconsistente. Esperado: {expected_iva:.2f}, Recibido: {iva_amount}")

            except (ValueError, TypeError, KeyError) as e:
                errors.append(f"Error en información de impuestos: {str(e)}")

        return errors

    def _validate_business_rules(self, payload: Dict[str, Any]) -> List[str]:
        """Valida reglas de negocio específicas"""
        errors = []

        # Validar límite de monto
        try:
            amount = float(payload.get('amount', 0))
            if amount > self.max_amount:
                errors.append(f"Monto excede el límite máximo de ${self.max_amount:,.2f}")
        except (ValueError, TypeError):
            pass  # Error ya capturado en validaciones básicas

        # Validar antigüedad del gasto
        expense_date_str = payload.get('expense_date')
        if expense_date_str:
            try:
                expense_date = datetime.fromisoformat(expense_date_str.replace('Z', '+00:00'))
                days_old = (datetime.now() - expense_date.replace(tzinfo=None)).days

                if days_old > self.max_days_old:
                    errors.append(f"El gasto es muy antiguo ({days_old} días). Máximo permitido: {self.max_days_old} días")

            except ValueError:
                pass  # Error ya capturado en validaciones de formato

        # Validar coherencia entre forma de pago y quien pagó
        payment_method = payload.get('payment_method', '')
        who_paid = payload.get('who_paid', '')

        if payment_method == 'tarjeta_empresa' and who_paid == 'employee':
            errors.append("Inconsistencia: tarjeta empresa no puede ser pagada por empleado")

        if payment_method == 'efectivo' and who_paid == 'company':
            errors.append("Inconsistencia: efectivo normalmente es pagado por empleado")

        return errors

    def _validate_cfdi_attachments(self, expense_model: ExpenseModel) -> List[str]:
        """Valida adjuntos de CFDI y extrae información"""
        errors = []

        cfdi_xml_attachments = [
            att for att in expense_model.attachments
            if att.attachment_type == AttachmentType.CFDI_XML
        ]

        if not cfdi_xml_attachments:
            return errors  # CFDI es opcional

        if len(cfdi_xml_attachments) > 1:
            errors.append("Solo se permite un archivo CFDI XML por gasto")
            return errors

        cfdi_attachment = cfdi_xml_attachments[0]

        try:
            # Decodificar contenido si está en base64
            xml_content = cfdi_attachment.content
            if isinstance(xml_content, str):
                try:
                    xml_content = base64.b64decode(xml_content)
                except Exception:
                    # Asumir que ya es texto XML
                    xml_content = xml_content.encode('utf-8')

            # Parsear XML
            root = ET.fromstring(xml_content)

            # Validar que sea un CFDI válido
            cfdi_errors = self._validate_cfdi_structure(root, expense_model)
            errors.extend(cfdi_errors)

        except ET.ParseError as e:
            errors.append(f"Error parseando CFDI XML: {str(e)}")
        except Exception as e:
            errors.append(f"Error validando CFDI: {str(e)}")

        return errors

    def _validate_cfdi_structure(self, xml_root: ET.Element, expense_model: ExpenseModel) -> List[str]:
        """Valida la estructura del CFDI y compara con datos del gasto"""
        errors = []

        try:
            # Namespaces comunes de CFDI
            ns = {
                'cfdi': 'http://www.sat.gob.mx/cfd/4'
            }

            # Validar UUID
            uuid_element = xml_root.find('.//cfdi:TimbreFiscalDigital', ns)
            if uuid_element is not None:
                cfdi_uuid = uuid_element.get('UUID')
                if expense_model.cfdi_uuid and expense_model.cfdi_uuid != cfdi_uuid:
                    errors.append("UUID en CFDI no coincide con el proporcionado")
            else:
                errors.append("CFDI no contiene TimbreFiscalDigital válido")

            # Validar total
            total_cfdi = float(xml_root.get('Total', 0))
            if abs(total_cfdi - expense_model.tax_info.total) > 0.01:
                errors.append(f"Total en CFDI ({total_cfdi}) no coincide con total del gasto ({expense_model.tax_info.total})")

            # Validar emisor (proveedor)
            emisor = xml_root.find('.//cfdi:Emisor', ns)
            if emisor is not None:
                rfc_emisor = emisor.get('Rfc', '')
                if expense_model.supplier.rfc and expense_model.supplier.rfc != rfc_emisor:
                    errors.append("RFC del emisor en CFDI no coincide con RFC del proveedor")

        except Exception as e:
            errors.append(f"Error validando estructura CFDI: {str(e)}")

        return errors

    def _validate_date_format(self, date_str: str) -> bool:
        """Valida formato de fecha"""
        try:
            datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False

    def get_validation_summary(self, errors: List[str]) -> Dict[str, Any]:
        """Genera un resumen de validación"""
        return {
            'is_valid': len(errors) == 0,
            'error_count': len(errors),
            'errors': errors,
            'validation_timestamp': datetime.now().isoformat(),
            'severity_breakdown': {
                'critical': len([e for e in errors if 'requerido' in e.lower() or 'faltante' in e.lower()]),
                'business': len([e for e in errors if 'límite' in e.lower() or 'máximo' in e.lower()]),
                'format': len([e for e in errors if 'formato' in e.lower() or 'inválido' in e.lower()]),
                'cfdi': len([e for e in errors if 'cfdi' in e.lower()]),
            }
        }


# Instancia global del validador
expense_validator = ExpenseValidator()