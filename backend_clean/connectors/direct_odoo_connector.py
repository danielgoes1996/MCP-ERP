"""
Conector Odoo directo sin dependencias adicionales
"""

import xmlrpc.client
import logging
from typing import Dict, List, Any

# Configuración desde variables de entorno
import os
ODOO_URL = os.getenv("ODOO_URL", "https://your-odoo-instance.odoo.com")
ODOO_DB = os.getenv("ODOO_DB", "your-database")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "your-email@domain.com")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "your-password")

logger = logging.getLogger(__name__)

def get_expenses(params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Obtiene gastos desde Odoo usando configuración directa.
    """
    if params is None:
        params = {}

    limit = params.get('limit', 100)

    try:
        # Conexión y autenticación
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})

        if not uid:
            raise Exception("Fallo en autenticación de Odoo")

        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

        # Buscar gastos
        expense_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'hr.expense', 'search',
            [[]],
            {'limit': limit, 'order': 'id desc'}
        )

        if not expense_ids:
            return []

        # Leer datos de gastos con campos correctos para Odoo 18
        expenses_data = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'hr.expense', 'read',
            [expense_ids, ['name', 'price_unit', 'total_amount', 'state', 'employee_id', 'create_date']]
        )

        # Formatear respuesta
        formatted_expenses = []
        for expense in expenses_data:
            # Manejar empleado
            employee_name = "N/A"
            if expense.get('employee_id') and isinstance(expense['employee_id'], list):
                employee_name = expense['employee_id'][1]

            formatted_expense = {
                "id": expense['id'],
                "name": expense.get('name', 'Sin descripción'),
                "amount": float(expense.get('price_unit', 0.0)),  # Usar price_unit en Odoo 18
                "total_amount": float(expense.get('total_amount', 0.0)),
                "state": expense.get('state', 'draft'),
                "employee": employee_name,
                "date": expense.get('create_date', ''),
            }
            formatted_expenses.append(formatted_expense)

        return formatted_expenses

    except Exception as e:
        logger.error(f"Error obteniendo gastos de Odoo: {str(e)}")
        raise