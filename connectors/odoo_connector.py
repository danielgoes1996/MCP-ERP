"""
Odoo Connector for MCP Server
Integración real con Odoo usando XML-RPC para consultar gastos y otros módulos.
"""

import xmlrpc.client
import logging
from typing import Dict, List, Any, Optional, Tuple
from config.config import config

logger = logging.getLogger(__name__)


class OdooConnector:
    """
    Conector para integración con Odoo ERP usando XML-RPC.
    Maneja autenticación y operaciones CRUD básicas.
    """

    def __init__(self):
        self.url = config.ODOO_URL
        self.db = config.ODOO_DB
        self.username = config.ODOO_USERNAME
        self.password = config.ODOO_PASSWORD
        self.uid = None
        self.models = None
        self.common = None

    def connect_odoo(self) -> Tuple[Optional[int], Optional[xmlrpc.client.ServerProxy]]:
        """
        Establece conexión con Odoo y autentica al usuario.

        Returns:
            Tuple[Optional[int], Optional[xmlrpc.client.ServerProxy]]:
            (uid, models) si la conexión es exitosa, (None, None) en caso de error
        """
        try:
            logger.info(f"Intentando conectar a Odoo: {self.url}")

            # Conexión al servicio común para autenticación
            self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')

            # Verificar versión de Odoo
            version_info = self.common.version()
            logger.info(f"Conectado a Odoo versión: {version_info.get('server_version', 'unknown')}")

            # Autenticación
            self.uid = self.common.authenticate(
                self.db,
                self.username,
                self.password,
                {}
            )

            if not self.uid:
                logger.error("Fallo en autenticación de Odoo: credenciales inválidas")
                return None, None

            logger.info(f"Autenticación exitosa. UID: {self.uid}")

            # Conexión al servicio de modelos
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')

            return self.uid, self.models

        except Exception as e:
            logger.error(f"Error conectando a Odoo: {str(e)}")
            return None, None

    def get_expenses(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtiene lista de gastos desde el modelo hr.expense de Odoo.

        Args:
            limit (int): Número máximo de registros a obtener

        Returns:
            List[Dict[str, Any]]: Lista de gastos con formato:
            [
                {"id": 1, "name": "Gasto de comida", "amount": 95.23, "state": "draft"},
                {"id": 2, "name": "Gasolina", "amount": 50.00, "state": "done"}
            ]
        """
        try:
            # Verificar conexión
            if not self.uid or not self.models:
                uid, models = self.connect_odoo()
                if not uid:
                    raise Exception("No se pudo establecer conexión con Odoo")

            # Buscar gastos - campos comunes en hr.expense
            expense_fields = ['name', 'unit_amount', 'state', 'employee_id', 'date', 'currency_id']

            # Obtener IDs de gastos
            expense_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'search',
                [[]],  # Dominio vacío = todos los registros
                {'limit': limit, 'order': 'date desc'}
            )

            logger.info(f"Encontrados {len(expense_ids)} gastos en Odoo")

            if not expense_ids:
                return []

            # Leer datos de los gastos
            expenses_data = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'read',
                [expense_ids, expense_fields]
            )

            # Formatear respuesta
            formatted_expenses = []
            for expense in expenses_data:
                # Obtener nombre del empleado si existe
                employee_name = "N/A"
                if expense.get('employee_id') and isinstance(expense['employee_id'], list):
                    employee_name = expense['employee_id'][1]  # [id, name]

                # Obtener símbolo de moneda si existe
                currency_symbol = ""
                if expense.get('currency_id') and isinstance(expense['currency_id'], list):
                    currency_symbol = expense['currency_id'][1]  # [id, name]

                formatted_expense = {
                    "id": expense['id'],
                    "name": expense.get('name', 'Sin descripción'),
                    "amount": float(expense.get('unit_amount', 0.0)),
                    "state": expense.get('state', 'draft'),
                    "employee": employee_name,
                    "date": expense.get('date', ''),
                    "currency": currency_symbol
                }
                formatted_expenses.append(formatted_expense)

            logger.info(f"Procesados {len(formatted_expenses)} gastos exitosamente")
            return formatted_expenses

        except Exception as e:
            logger.error(f"Error obteniendo gastos de Odoo: {str(e)}")
            raise

    def create_expense(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo gasto en Odoo.

        Args:
            expense_data (Dict): Datos del gasto a crear

        Returns:
            Dict: Información del gasto creado
        """
        try:
            if not self.uid or not self.models:
                uid, models = self.connect_odoo()
                if not uid:
                    raise Exception("No se pudo establecer conexión con Odoo")

            # Crear gasto
            expense_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                'hr.expense', 'create',
                [expense_data]
            )

            logger.info(f"Gasto creado en Odoo con ID: {expense_id}")

            return {
                "id": expense_id,
                "status": "created",
                "message": f"Gasto creado exitosamente con ID {expense_id}"
            }

        except Exception as e:
            logger.error(f"Error creando gasto en Odoo: {str(e)}")
            raise

    def test_connection(self) -> Dict[str, Any]:
        """
        Prueba la conexión con Odoo.

        Returns:
            Dict: Estado de la conexión
        """
        try:
            uid, models = self.connect_odoo()
            if uid:
                return {
                    "status": "success",
                    "message": f"Conexión exitosa. UID: {uid}",
                    "url": self.url,
                    "database": self.db
                }
            else:
                return {
                    "status": "error",
                    "message": "Fallo en autenticación",
                    "url": self.url,
                    "database": self.db
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error de conexión: {str(e)}",
                "url": self.url,
                "database": self.db
            }


# Instancia global del conector para reutilización
odoo_connector = OdooConnector()


# Funciones de conveniencia para usar en mcp_handler.py
def get_expenses(params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Función de conveniencia para obtener gastos desde Odoo.

    Args:
        params (Dict): Parámetros opcionales (limit, etc.)

    Returns:
        List[Dict]: Lista de gastos
    """
    if params is None:
        params = {}

    limit = params.get('limit', 100)
    return odoo_connector.get_expenses(limit=limit)


def create_expense_odoo(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función de conveniencia para crear gastos en Odoo.

    Args:
        params (Dict): Datos del gasto

    Returns:
        Dict: Resultado de la creación
    """
    return odoo_connector.create_expense(params)


def test_odoo_connection() -> Dict[str, Any]:
    """
    Función de conveniencia para probar conexión con Odoo.

    Returns:
        Dict: Estado de la conexión
    """
    return odoo_connector.test_connection()