"""
MCP Handler - Core logic for handling MCP method calls
This module contains the main handler function that processes MCP requests
and routes them to appropriate mock implementations.
"""

from typing import Dict, Any
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


def handle_mcp_request(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main handler for MCP requests. Routes method calls to appropriate handlers.

    Args:
        method (str): The MCP method to call (e.g., 'get_inventory', 'create_order')
        params (Dict[str, Any]): Parameters for the method call

    Returns:
        Dict[str, Any]: Response data or error message
    """

    # Route to appropriate handler based on method
    if method == "get_inventory":
        return _handle_get_inventory(params)
    elif method == "create_order":
        return _handle_create_order(params)
    elif method == "create_expense":
        return _handle_create_expense(params)
    elif method == "get_expenses":
        return _handle_get_expenses(params)
    elif method == "create_complete_expense":
        return _handle_create_complete_expense(params)
    else:
        return {"error": "Method not supported"}


def _handle_get_inventory(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mock implementation for get_inventory method.

    Args:
        params: Should contain 'product_id' and optionally 'location'

    Returns:
        Dict with inventory information
    """
    product_id = params.get("product_id", "UNKNOWN")
    location = params.get("location", "WAREHOUSE_A")

    # Mock inventory data
    mock_inventory = {
        "product_id": product_id,
        "quantity": 150,
        "location": location,
        "unit": "pieces",
        "last_updated": datetime.now().isoformat(),
        "reserved_quantity": 25,
        "available_quantity": 125
    }

    return mock_inventory


def _handle_create_order(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mock implementation for create_order method.

    Args:
        params: Should contain customer info and items

    Returns:
        Dict with order creation result
    """
    customer = params.get("customer", "DEFAULT_CUSTOMER")
    items = params.get("items", [])

    # Generate mock order
    order_id = str(uuid.uuid4())[:8].upper()

    mock_order = {
        "order_id": order_id,
        "status": "confirmed",
        "customer": customer,
        "items": items if items else [
            {"product_id": "SAMPLE_001", "quantity": 1, "price": 99.99}
        ],
        "total_amount": sum(item.get("price", 0) * item.get("quantity", 1) for item in items) if items else 99.99,
        "created_date": datetime.now().isoformat(),
        "estimated_delivery": "2024-03-15"
    }

    return mock_order


def _handle_create_expense(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Real implementation for create_expense method using Odoo integration.
    Now with LLM enhancement for better descriptions and field mapping.

    Args:
        params: Should contain employee, amount, description

    Returns:
        Dict with expense creation result
    """
    try:
        # Extraer datos básicos
        employee = params.get("employee", "DEFAULT_EMPLOYEE")
        amount = params.get("amount", 0.0)
        description = params.get("description", "Business expense")

        logger.info(f"Creando gasto mejorado: {description} - ${amount}")

        # NUEVO: Mejorar gasto con LLM
        try:
            from core.expenses.completion.expense_enhancer import enhance_expense_from_voice
            enhanced_expense_data = enhance_expense_from_voice(description, amount)
            logger.info("Gasto mejorado con LLM exitosamente")
        except ImportError:
            logger.warning("Expense enhancer no disponible, usando datos básicos")
            enhanced_expense_data = {
                'name': description,
                'description': description,
                'price_unit': float(amount),
                'quantity': 1.0,
                'total_amount': float(amount),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'payment_mode': 'own_account',
            }
        except Exception as e:
            logger.error(f"Error en LLM enhancement: {e}")
            enhanced_expense_data = {
                'name': description,
                'description': description,
                'price_unit': float(amount),
                'quantity': 1.0,
                'total_amount': float(amount),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'payment_mode': 'own_account',
            }

        # Crear gasto directamente en Odoo
        import xmlrpc.client
        import os

        url = os.getenv("ODOO_URL", "https://your-odoo-instance.odoo.com")
        db = os.getenv("ODOO_DB", "your-database")
        username = os.getenv("ODOO_USERNAME", "your-email@domain.com")
        password = os.getenv("ODOO_PASSWORD", "your-password")

        # Conectar a Odoo
        common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
        uid = common.authenticate(db, username, password, {})

        if not uid:
            raise Exception("Fallo en autenticación de Odoo")

        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

        # Usar datos mejorados para crear en Odoo
        expense_id = models.execute_kw(
            db, uid, password,
            'hr.expense', 'create',
            [enhanced_expense_data]
        )

        result = {'success': True, 'expense_id': expense_id}

        if result.get('success'):
            return {
                "expense_id": str(result.get('expense_id', 'UNKNOWN')),
                "status": "pending_approval",
                "employee": employee,
                "amount": float(amount),
                "currency": "USD",
                "date": datetime.now().isoformat(),
                "description": enhanced_expense_data.get('name', description),
                "description_detailed": enhanced_expense_data.get('description', description),
                "category": enhanced_expense_data.get('category', 'general'),
                "payment_mode": enhanced_expense_data.get('payment_mode', 'own_account'),
                "receipt_required": True,
                "odoo_id": result.get('expense_id'),
                "enhanced": True,
                "original_transcript": description
            }
        else:
            # Fallback a mock si falla Odoo
            expense_id = str(uuid.uuid4())[:8].upper()
            return {
                "expense_id": expense_id,
                "status": "error",
                "employee": employee,
                "amount": float(amount),
                "currency": "USD",
                "date": datetime.now().isoformat(),
                "description": description,
                "category": "general",
                "receipt_required": True,
                "error": result.get('error', 'Unknown error')
            }

    except Exception as e:
        # Fallback a mock si hay error de integración
        expense_id = str(uuid.uuid4())[:8].upper()
        return {
            "expense_id": expense_id,
            "status": "error",
            "employee": params.get("employee", "DEFAULT_EMPLOYEE"),
            "amount": float(params.get("amount", 0.0)),
            "currency": "USD",
            "date": datetime.now().isoformat(),
            "description": params.get("description", "Business expense"),
            "category": "general",
            "receipt_required": True,
            "error": str(e)
        }


def _handle_get_expenses(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler para obtener gastos desde Odoo.
    Integración real con el módulo hr.expense de Odoo.

    Args:
        params: Parámetros opcionales (limit, etc.)

    Returns:
        Dict with expenses list or error message
    """
    try:
        # Importar el conector Odoo directo (sin dotenv)
        from connectors.direct_odoo_connector import get_expenses

        logger.info("Obteniendo gastos desde Odoo...")
        expenses = get_expenses(params)

        logger.info(f"Obtenidos {len(expenses)} gastos desde Odoo")

        return {
            "manual_expenses": expenses,
            "total_count": len(expenses),
            "source": "odoo_hr_expense",
            "timestamp": datetime.now().isoformat()
        }

    except ImportError as e:
        logger.error(f"Error importando conector Odoo: {str(e)}")
        return {"error": "Conector Odoo no disponible"}

    except Exception as e:
        logger.error(f"Error obteniendo gastos de Odoo: {str(e)}")
        return {"error": "No se pudo conectar a Odoo"}


def _handle_create_complete_expense(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler para crear gastos completos con validación, proveedores y adjuntos.
    Integración avanzada con Odoo incluyendo CFDI y documentos.

    Args:
        params: Payload completo del gasto con todos los campos

    Returns:
        Dict with creation result or error message
    """
    try:
        # Importar módulos necesarios
        from core.expenses.validation.expense_validator import expense_validator
        from connectors.enhanced_odoo_connector import create_complete_expense
        from core.expenses.models import ExpenseModel

        logger.info("Iniciando creación de gasto completo...")

        # 1. Validar payload completo
        is_valid, validation_errors, expense_model = expense_validator.validate_expense_payload(params)

        if not is_valid:
            logger.warning(f"Validación falló: {len(validation_errors)} errores")
            return {
                "error": "Validación del gasto falló",
                "validation_errors": validation_errors,
                "validation_summary": expense_validator.get_validation_summary(validation_errors)
            }

        logger.info("Validación exitosa, creando gasto en Odoo...")

        # 2. Crear gasto completo en Odoo
        creation_result = create_complete_expense(expense_model)

        if not creation_result.get('success'):
            logger.error(f"Error en creación: {creation_result.get('error')}")
            return {
                "error": "Error creando gasto en Odoo",
                "details": creation_result.get('error'),
                "odoo_response": creation_result
            }

        logger.info(f"Gasto completo creado exitosamente. ID: {creation_result.get('expense_id')}")

        # 3. Preparar respuesta exitosa
        return {
            "success": True,
            "expense_id": creation_result.get('expense_id'),
            "expense_data": creation_result.get('expense_data'),
            "supplier_id": creation_result.get('supplier_id'),
            "attachments_uploaded": len(creation_result.get('attachments', [])),
            "attachments_details": creation_result.get('attachments'),
            "reference": creation_result.get('expense_data', {}).get('reference'),
            "total_amount": expense_model.tax_info.total,
            "supplier_name": expense_model.supplier.name,
            "created_at": datetime.now().isoformat(),
            "source": "mcp_enhanced",
            "message": creation_result.get('message')
        }

    except ImportError as e:
        logger.error(f"Error importando módulos: {str(e)}")
        return {"error": "Módulos de gastos completos no disponibles"}

    except Exception as e:
        logger.error(f"Error creando gasto completo: {str(e)}")
        return {
            "error": "Error interno creando gasto completo",
            "details": str(e)
        }