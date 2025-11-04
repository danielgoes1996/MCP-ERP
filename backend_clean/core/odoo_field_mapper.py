"""
Odoo Field Mapper - Mapeo completo de campos JSON a hr.expense en Odoo
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import xmlrpc.client

logger = logging.getLogger(__name__)


class OdooFieldMapper:
    """
    Clase para mapear campos JSON completos a Odoo hr.expense
    """

    def __init__(self):
        self.odoo_connection = None
        self.field_mapping = {
            # Mapeo completo JSON → Odoo (Español)
            'descripcion': 'name',                    # char - Descripción del gasto
            'monto_total': 'total_amount',           # float - Total con impuestos
            'subtotal': 'price_unit',                # float - Precio sin impuestos
            'cantidad': 'quantity',                  # float - Cantidad (default: 1.0)
            'fecha_gasto': 'date',                   # date - Fecha real del gasto
            'pagado_por': 'payment_mode',            # selection (own_account/company_account)
            'empleado_id': 'employee_id',            # many2one (hr.employee)
            'cuenta_contable': 'account_id',         # many2one (account.account)
            'notas': 'description',                  # text - Notas adicionales
            # Mapeo directo (Inglés) - campos que ya están en formato Odoo
            'name': 'name',                          # char - Descripción del gasto
            'total_amount': 'total_amount',          # float - Total con impuestos
            'unit_amount': 'price_unit',             # float - Precio sin impuestos
            'price_unit': 'price_unit',              # float - Precio sin impuestos
            'quantity': 'quantity',                  # float - Cantidad
            'date': 'date',                          # date - Fecha real del gasto
            'payment_mode': 'payment_mode',          # selection (own_account/company_account)
            'employee_id': 'employee_id',            # many2one (hr.employee)
            'account_id': 'account_id',              # many2one (account.account)
            'description': 'description',            # text - Notas adicionales
        }

        # Campos requeridos mínimos para crear gasto
        self.required_fields = ['name', 'total_amount', 'date', 'employee_id']

        # Campos opcionales pero recomendados
        self.optional_fields = ['price_unit', 'quantity', 'payment_mode',
                               'account_id', 'description']

        # Valores por defecto para Carreta Verde
        self.defaults = {
            'quantity': 1.0,
            'payment_mode': 'own_account',
            'company_id': 1,  # ID de Carreta Verde
        }

        # Catálogo de productos/categorías de gastos para Carreta Verde
        self.expense_categories = {
            'combustible': {'name': 'Combustible', 'account_code': '601.01'},
            'alimentos': {'name': 'Alimentos y Bebidas', 'account_code': '601.02'},
            'hospedaje': {'name': 'Hospedaje', 'account_code': '601.03'},
            'transporte': {'name': 'Transporte', 'account_code': '601.04'},
            'comunicacion': {'name': 'Comunicación', 'account_code': '601.05'},
            'materiales': {'name': 'Materiales de Oficina', 'account_code': '601.06'},
            'marketing': {'name': 'Marketing y Publicidad', 'account_code': '601.07'},
            'capacitacion': {'name': 'Capacitación', 'account_code': '601.08'},
            'representacion': {'name': 'Gastos de Representación', 'account_code': '601.09'},
            'otros': {'name': 'Otros Gastos', 'account_code': '601.99'},
        }

    def connect_to_odoo(self) -> bool:
        """
        Establece conexión con Odoo
        """
        try:
            url = os.getenv("ODOO_URL")
            db = os.getenv("ODOO_DB")
            username = os.getenv("ODOO_USERNAME")
            password = os.getenv("ODOO_PASSWORD")

            if not all([url, db, username, password]):
                logger.error("Credenciales de Odoo incompletas")
                return False

            # Conectar
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
            uid = common.authenticate(db, username, password, {})

            if not uid:
                logger.error("Fallo en autenticación de Odoo")
                return False

            self.odoo_connection = {
                'url': url,
                'db': db,
                'uid': uid,
                'password': password,
                'models': xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
            }

            logger.info("Conexión a Odoo establecida exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error conectando a Odoo: {e}")
            return False

    def map_expense_data(self, json_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Mapea datos JSON a campos de Odoo y detecta campos faltantes

        Args:
            json_data: Datos del gasto en formato JSON

        Returns:
            Tuple[Dict[str, Any], List[str]]: (datos_mapeados, campos_faltantes)
        """
        mapped_data = {}
        missing_fields = []

        # Mapear campos directos
        for json_field, odoo_field in self.field_mapping.items():
            if json_field in json_data and json_data[json_field] is not None:
                mapped_data[odoo_field] = self._convert_field_value(
                    odoo_field, json_data[json_field]
                )

        # Aplicar valores por defecto
        for field, default_value in self.defaults.items():
            if field not in mapped_data:
                mapped_data[field] = default_value

        # Detectar campos faltantes requeridos
        for required_field in self.required_fields:
            if required_field not in mapped_data:
                missing_fields.append(required_field)

        # Validar y enriquecer datos
        mapped_data = self._enrich_mapped_data(mapped_data)

        logger.info(f"Datos mapeados: {len(mapped_data)} campos")
        logger.info(f"Campos faltantes: {missing_fields}")

        return mapped_data, missing_fields

    def _convert_field_value(self, odoo_field: str, value: Any) -> Any:
        """
        Convierte valores según el tipo de campo de Odoo
        """
        try:
            # Campos de fecha
            if odoo_field == 'date' and isinstance(value, str):
                # Convertir string a formato YYYY-MM-DD
                if 'T' in value:  # ISO format
                    return value.split('T')[0]
                return value

            # Campos monetarios
            elif odoo_field in ['total_amount', 'price_unit']:
                return float(value)

            # Campos de cantidad
            elif odoo_field == 'quantity':
                return float(value) if value else 1.0

            # Campos de selección
            elif odoo_field == 'payment_mode':
                # Mapear valores comunes
                payment_mapping = {
                    'empleado': 'own_account',
                    'empresa': 'company_account',
                    'reembolso': 'own_account',
                    'directo': 'company_account'
                }
                return payment_mapping.get(str(value).lower(), value)

            # Campos many2one - se resolverán posteriormente
            elif odoo_field in ['employee_id', 'account_id']:
                return value  # Se procesará en _enrich_mapped_data

            # Campos de texto
            else:
                return str(value) if value is not None else ''

        except Exception as e:
            logger.warning(f"Error convirtiendo campo {odoo_field}: {e}")
            return value

    def _enrich_mapped_data(self, mapped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece los datos mapeados resolviendo IDs y agregando campos calculados
        """
        enriched_data = mapped_data.copy()

        try:
            # Resolver employee_id por defecto (Daniel Gómez)
            if 'employee_id' not in enriched_data:
                employee_id = self._resolve_employee_id("Daniel Gómez")
                if employee_id:
                    enriched_data['employee_id'] = employee_id


            # Calcular price_unit si no está presente
            if 'price_unit' not in enriched_data and 'total_amount' in enriched_data:
                total = enriched_data['total_amount']
                quantity = enriched_data.get('quantity', 1.0)
                # Asumir IVA 16% incluido en México
                enriched_data['price_unit'] = total / 1.16 / quantity

            # Agregar fecha si no está presente
            if 'date' not in enriched_data:
                enriched_data['date'] = datetime.now().strftime('%Y-%m-%d')

        except Exception as e:
            logger.error(f"Error enriqueciendo datos: {e}")

        return enriched_data

    def _resolve_currency_id(self, currency_code: str) -> Optional[int]:
        """
        Resuelve código de moneda a ID de Odoo
        """
        try:
            if not self.odoo_connection:
                return None

            models = self.odoo_connection['models']
            currency_ids = models.execute_kw(
                self.odoo_connection['db'], self.odoo_connection['uid'], self.odoo_connection['password'],
                'res.currency', 'search',
                [['name', '=', currency_code.upper()]]
            )
            return currency_ids[0] if currency_ids else None

        except Exception as e:
            logger.warning(f"Error resolviendo currency_id para {currency_code}: {e}")
            return None

    def _resolve_employee_id(self, employee_name: str) -> Optional[int]:
        """
        Resuelve nombre de empleado a ID de Odoo
        """
        try:
            if not self.odoo_connection:
                return None

            models = self.odoo_connection['models']
            employee_ids = models.execute_kw(
                self.odoo_connection['db'], self.odoo_connection['uid'], self.odoo_connection['password'],
                'hr.employee', 'search',
                [['name', 'ilike', employee_name]]
            )
            return employee_ids[0] if employee_ids else None

        except Exception as e:
            logger.warning(f"Error resolviendo employee_id para {employee_name}: {e}")
            return None

    def _resolve_product_id(self, category: str) -> Optional[int]:
        """
        Resuelve categoría a product_id de gastos en Odoo
        """
        try:
            if not self.odoo_connection:
                return None

            category_info = self.expense_categories.get(category.lower(), self.expense_categories['otros'])

            models = self.odoo_connection['models']
            product_ids = models.execute_kw(
                self.odoo_connection['db'], self.odoo_connection['uid'], self.odoo_connection['password'],
                'product.product', 'search',
                [['name', 'ilike', category_info['name']], ['can_be_expensed', '=', True]]
            )
            return product_ids[0] if product_ids else None

        except Exception as e:
            logger.warning(f"Error resolviendo product_id para categoría {category}: {e}")
            return None

    def get_missing_fields_info(self, missing_fields: List[str]) -> List[Dict[str, Any]]:
        """
        Obtiene información detallada de campos faltantes para mostrar al usuario
        """
        field_info = {
            'name': {
                'label': 'Descripción del gasto',
                'type': 'text',
                'required': True,
                'help': 'Describe brevemente el gasto (ej: "Gasolina para vehículo")'
            },
            'total_amount': {
                'label': 'Monto total',
                'type': 'number',
                'required': True,
                'help': 'Monto total del gasto incluyendo impuestos'
            },
            'date': {
                'label': 'Fecha del gasto',
                'type': 'date',
                'required': True,
                'help': 'Fecha en que se realizó el gasto'
            },
            'employee_id': {
                'label': 'Empleado',
                'type': 'select',
                'required': True,
                'help': 'Empleado que realizó el gasto',
                'options': self._get_employee_options()
            },
            'price_unit': {
                'label': 'Subtotal (sin impuestos)',
                'type': 'number',
                'required': False,
                'help': 'Monto sin impuestos'
            },
            'product_id': {
                'label': 'Categoría de gasto',
                'type': 'select',
                'required': False,
                'help': 'Tipo de gasto para contabilidad',
                'options': [{'id': k, 'name': v['name']} for k, v in self.expense_categories.items()]
            },
            'partner_id': {
                'label': 'Proveedor',
                'type': 'text',
                'required': False,
                'help': 'Nombre del proveedor o establecimiento'
            },
            'payment_mode': {
                'label': 'Forma de pago',
                'type': 'select',
                'required': False,
                'help': 'Quién pagó el gasto',
                'options': [
                    {'id': 'own_account', 'name': 'Empleado (a reembolsar)'},
                    {'id': 'company_account', 'name': 'Empresa (pago directo)'}
                ]
            }
        }

        return [field_info.get(field, {'label': field, 'type': 'text'}) for field in missing_fields]

    def _get_employee_options(self) -> List[Dict[str, Any]]:
        """
        Obtiene lista de empleados disponibles en Odoo
        """
        try:
            if not self.odoo_connection:
                return [{'id': 1, 'name': 'Daniel Gómez'}]  # Fallback

            models = self.odoo_connection['models']
            employees = models.execute_kw(
                self.odoo_connection['db'], self.odoo_connection['uid'], self.odoo_connection['password'],
                'hr.employee', 'search_read',
                [['active', '=', True]], {'fields': ['id', 'name']}
            )
            return employees

        except Exception as e:
            logger.warning(f"Error obteniendo empleados: {e}")
            return [{'id': 1, 'name': 'Daniel Gómez'}]

    def create_expense_in_odoo(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea el gasto en Odoo con los datos completos mapeados
        """
        try:
            if not self.odoo_connection:
                if not self.connect_to_odoo():
                    raise Exception("No se pudo conectar a Odoo")

            models = self.odoo_connection['models']

            # Crear gasto+
            expense_id = models.execute_kw(
                self.odoo_connection['db'], self.odoo_connection['uid'], self.odoo_connection['password'],
                'hr.expense', 'create',
                [expense_data]
            )

            logger.info(f"Gasto creado en Odoo con ID: {expense_id}")

            return {
                'success': True,
                'expense_id': expense_id,
                'odoo_data': expense_data
            }

        except Exception as e:
            logger.error(f"Error creando gasto en Odoo: {e}")
            return {
                'success': False,
                'error': str(e),
                'odoo_data': expense_data
            }


# Instancia global
odoo_mapper = None

def get_odoo_mapper() -> OdooFieldMapper:
    """
    Obtiene o crea la instancia global del mapper
    """
    global odoo_mapper
    if odoo_mapper is None:
        odoo_mapper = OdooFieldMapper()
    return odoo_mapper