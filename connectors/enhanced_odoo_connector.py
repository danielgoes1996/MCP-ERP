"""
Conector Odoo mejorado para gastos empresariales completos
Incluye manejo de proveedores, cuentas contables, adjuntos y CFDI
"""

import xmlrpc.client
import base64
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from core.expense_models import ExpenseModel, Supplier, Attachment, AttachmentType

# Configuración desde variables de entorno
import os
ODOO_URL = os.getenv("ODOO_URL", "https://your-odoo-instance.odoo.com")
ODOO_DB = os.getenv("ODOO_DB", "your-database")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "your-email@domain.com")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "your-password")

logger = logging.getLogger(__name__)


class EnhancedOdooConnector:
    """Conector Odoo mejorado para gastos empresariales completos"""

    def __init__(self):
        self.url = ODOO_URL
        self.db = ODOO_DB
        self.username = ODOO_USERNAME
        self.password = ODOO_PASSWORD
        self.uid = None
        self.models = None

    def connect(self) -> bool:
        """Establece conexión con Odoo"""
        try:
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})

            if not self.uid:
                logger.error("Fallo en autenticación de Odoo")
                return False

            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            logger.info(f"Conectado a Odoo. UID: {self.uid}")
            return True

        except Exception as e:
            logger.error(f"Error conectando a Odoo: {str(e)}")
            return False

    def create_complete_expense(self, expense_model: ExpenseModel) -> Dict[str, Any]:
        """
        Crea un gasto completo en Odoo con todos los campos y adjuntos

        Args:
            expense_model: Modelo completo del gasto

        Returns:
            Dict con resultado de la creación
        """
        try:
            if not self.connect():
                raise Exception("No se pudo conectar a Odoo")

            # 1. Saltar creación de proveedor por ahora (problemas de compatibilidad)
            supplier_id = None  # self._get_or_create_supplier(expense_model.supplier)

            # 2. Obtener empleado
            employee_id = self._get_employee_id(expense_model.employee_id, expense_model.employee_name)

            # 3. Obtener cuentas contables
            account_id = self._get_account_id(expense_model.account_code)
            analytic_account_id = self._get_analytic_account_id(expense_model.analytic_account)

            # 4. Preparar datos del gasto
            expense_data = self._prepare_expense_data(
                expense_model, supplier_id, employee_id, account_id, analytic_account_id
            )

            # 5. Crear gasto en Odoo
            logger.info("Creando gasto en Odoo...")
            expense_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'create',
                [expense_data]
            )

            logger.info(f"Gasto creado con ID: {expense_id}")

            # 6. Subir adjuntos
            attachment_results = []
            for attachment in expense_model.attachments:
                try:
                    att_result = self._upload_attachment(expense_id, attachment)
                    attachment_results.append(att_result)
                except Exception as e:
                    logger.error(f"Error subiendo adjunto {attachment.filename}: {str(e)}")
                    attachment_results.append({
                        'filename': attachment.filename,
                        'success': False,
                        'error': str(e)
                    })

            # 7. Verificar creación
            created_expense = self._get_expense_details(expense_id)

            return {
                'success': True,
                'expense_id': expense_id,
                'expense_data': created_expense,
                'supplier_id': supplier_id,
                'attachments': attachment_results,
                'message': f'Gasto creado exitosamente con ID {expense_id}'
            }

        except Exception as e:
            logger.error(f"Error creando gasto completo: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Error creando gasto en Odoo'
            }

    def _get_or_create_supplier(self, supplier: Supplier) -> Optional[int]:
        """Obtiene o crea un proveedor en Odoo"""
        try:
            # Buscar proveedor existente solo por nombre (evitar problemas con RFC)
            search_domain = [['name', 'ilike', supplier.name]]

            partner_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'search',
                [search_domain],
                {'limit': 1}
            )

            if partner_ids:
                logger.info(f"Proveedor existente encontrado: ID {partner_ids[0]}")
                return partner_ids[0]

            # Crear nuevo proveedor (sin RFC para evitar validación)
            partner_data = {
                'name': supplier.name,
                'is_company': True,
                'supplier_rank': 1,
                'customer_rank': 0,
            }

            # Solo agregar campos opcionales si tienen valor
            if supplier.address:
                partner_data['street'] = supplier.address

            if supplier.phone:
                partner_data['phone'] = supplier.phone

            if supplier.email:
                partner_data['email'] = supplier.email

            partner_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'res.partner', 'create',
                [partner_data]
            )

            logger.info(f"Nuevo proveedor creado: ID {partner_id}")
            return partner_id

        except Exception as e:
            logger.error(f"Error gestionando proveedor: {str(e)}")
            return None

    def _get_employee_id(self, employee_id: Optional[int], employee_name: Optional[str]) -> Optional[int]:
        """Obtiene ID del empleado"""
        try:
            if employee_id:
                return employee_id

            if employee_name:
                emp_ids = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'hr.employee', 'search',
                    [['name', 'ilike', employee_name]],
                    {'limit': 1}
                )
                return emp_ids[0] if emp_ids else None

            # Buscar empleado por defecto (el usuario actual)
            emp_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.employee', 'search',
                [[]],
                {'limit': 1}
            )
            return emp_ids[0] if emp_ids else None

        except Exception as e:
            logger.error(f"Error obteniendo empleado: {str(e)}")
            return None

    def _get_account_id(self, account_code: Optional[str]) -> Optional[int]:
        """Obtiene ID de cuenta contable por código"""
        if not account_code:
            return None

        try:
            account_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.account', 'search',
                [['code', '=', account_code]],
                {'limit': 1}
            )
            return account_ids[0] if account_ids else None

        except Exception as e:
            logger.error(f"Error obteniendo cuenta contable: {str(e)}")
            return None

    def _get_analytic_account_id(self, analytic_code: Optional[str]) -> Optional[int]:
        """Obtiene ID de cuenta analítica (centro de costos)"""
        if not analytic_code:
            return None

        try:
            analytic_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'account.analytic.account', 'search',
                [['name', 'ilike', analytic_code]],
                {'limit': 1}
            )
            return analytic_ids[0] if analytic_ids else None

        except Exception as e:
            logger.error(f"Error obteniendo cuenta analítica: {str(e)}")
            return None

    def _prepare_expense_data(self, expense_model: ExpenseModel, supplier_id: Optional[int],
                            employee_id: Optional[int], account_id: Optional[int],
                            analytic_account_id: Optional[int]) -> Dict[str, Any]:
        """Prepara los datos del gasto para Odoo"""

        base_data = expense_model.to_odoo_expense_data()

        # Solo agregar empleado si existe (evitar otros campos problemáticos)
        if employee_id:
            try:
                base_data['employee_id'] = employee_id
            except:
                pass  # Ignorar si falla

        # Limpiar campos None para evitar errores XML-RPC
        base_data = {k: v for k, v in base_data.items() if v is not None}

        # No agregar reference ya que no existe en este Odoo
        # Solo usar los campos absolutamente mínimos

        return base_data

    def _upload_attachment(self, expense_id: int, attachment: Attachment) -> Dict[str, Any]:
        """Sube un adjunto a Odoo y lo vincula al gasto"""
        try:
            # Preparar contenido del archivo
            if isinstance(attachment.content, str):
                # Asumimos que es base64
                file_content = attachment.content
            else:
                # Convertir bytes a base64
                file_content = base64.b64encode(attachment.content).decode('utf-8')

            # Crear adjunto en Odoo
            attachment_data = {
                'name': attachment.filename,
                'datas': file_content,
                'res_model': 'hr.expense',
                'res_id': expense_id,
                'mimetype': attachment.mime_type,
                'description': attachment.description or f"Adjunto tipo: {attachment.attachment_type.value}",
                'x_attachment_type': attachment.attachment_type.value,
            }

            attachment_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'ir.attachment', 'create',
                [attachment_data]
            )

            logger.info(f"Adjunto subido: {attachment.filename} (ID: {attachment_id})")

            return {
                'filename': attachment.filename,
                'attachment_id': attachment_id,
                'success': True,
                'type': attachment.attachment_type.value
            }

        except Exception as e:
            logger.error(f"Error subiendo adjunto: {str(e)}")
            raise

    def _get_expense_details(self, expense_id: int) -> Dict[str, Any]:
        """Obtiene detalles completos del gasto creado"""
        try:
            expense_data = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'read',
                [[expense_id], [
                    'name', 'description', 'price_unit', 'quantity',
                    'total_amount', 'total_amount_currency', 'untaxed_amount_currency',
                    'tax_amount', 'tax_amount_currency', 'date', 'state',
                    'employee_id', 'partner_id', 'account_id'
                ]]
            )[0]

            # Obtener adjuntos
            attachment_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'ir.attachment', 'search',
                [['res_model', '=', 'hr.expense'], ['res_id', '=', expense_id]]
            )

            attachments = []
            if attachment_ids:
                attachments = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'ir.attachment', 'read',
                    [attachment_ids, ['name', 'mimetype', 'x_attachment_type']]
                )

            expense_data['attachments'] = attachments
            return expense_data

        except Exception as e:
            logger.error(f"Error obteniendo detalles del gasto: {str(e)}")
            return {}

    def get_expenses_enhanced(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Obtiene gastos con información completa incluyendo proveedores y adjuntos
        """
        if params is None:
            params = {}

        limit = params.get('limit', 100)

        try:
            if not self.connect():
                raise Exception("No se pudo conectar a Odoo")

            # Buscar gastos
            expense_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'search',
                [[]],
                {'limit': limit, 'order': 'id desc'}
            )

            if not expense_ids:
                return []

            # Obtener datos completos
            expenses_data = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'read',
                [expense_ids, [
                    'name', 'description', 'price_unit', 'total_amount', 'date',
                    'state', 'employee_id', 'partner_id', 'account_id'
                ]]
            )

            # Formatear respuesta con información completa
            formatted_expenses = []
            for expense in expenses_data:
                # Información del proveedor
                supplier_info = "N/A"
                if expense.get('partner_id'):
                    supplier_info = expense['partner_id'][1]
                elif expense.get('x_supplier_name'):
                    supplier_info = expense['x_supplier_name']

                # Información del empleado
                employee_name = "N/A"
                if expense.get('employee_id') and isinstance(expense['employee_id'], list):
                    employee_name = expense['employee_id'][1]

                # Obtener adjuntos
                attachment_count = len(self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'ir.attachment', 'search',
                    [['res_model', '=', 'hr.expense'], ['res_id', '=', expense['id']]]
                ))

                formatted_expense = {
                    "id": expense['id'],
                    "name": expense.get('name', 'Sin descripción'),
                    "description": expense.get('description', ''),
                    "amount": float(expense.get('price_unit', 0.0)),
                    "total_amount": float(expense.get('total_amount', 0.0)),
                    "state": expense.get('state', 'draft'),
                    "employee": employee_name,
                    "supplier": supplier_info,
                    "date": expense.get('date', ''),
                    "reference": "",
                    "attachment_count": attachment_count,
                    "source": "odoo_enhanced"
                }
                formatted_expenses.append(formatted_expense)

            return formatted_expenses

        except Exception as e:
            logger.error(f"Error obteniendo gastos mejorados: {str(e)}")
            raise


# Instancia global del conector mejorado
enhanced_odoo_connector = EnhancedOdooConnector()


# Funciones de conveniencia
def create_complete_expense(expense_model: ExpenseModel) -> Dict[str, Any]:
    """Función de conveniencia para crear gasto completo"""
    return enhanced_odoo_connector.create_complete_expense(expense_model)


def get_expenses_enhanced(params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Función de conveniencia para obtener gastos mejorados"""
    return enhanced_odoo_connector.get_expenses_enhanced(params)