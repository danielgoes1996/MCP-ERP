# Connectors Directory

Este directorio contendrá los conectores específicos para sistemas externos.

## Conectores Planeados

### 📦 odoo_connector.py
- **Propósito**: Integración con Odoo ERP
- **Métodos**: get_inventory, create_order, update_product, get_customers
- **Autenticación**: XML-RPC con usuario/contraseña

### 🏦 bank_connector.py
- **Propósito**: Integración con APIs bancarias
- **Métodos**: get_balance, create_transfer, get_transactions
- **Autenticación**: API Key + certificados SSL

### 🏢 erp_connector.py
- **Propósito**: Conector genérico para ERPs
- **Métodos**: create_expense, get_employees, create_invoice
- **Autenticación**: Bearer token / OAuth2

## Estructura de un Conector

Cada conector debe implementar:

```python
class BaseConnector:
    def __init__(self, config: dict):
        self.config = config

    def connect(self) -> bool:
        # Establecer conexión
        pass

    def execute_method(self, method: str, params: dict) -> dict:
        # Ejecutar método específico
        pass

    def disconnect(self):
        # Cerrar conexión
        pass
```

## Estado Actual

Por ahora este directorio está vacío y el MCP Server usa datos mock.
Los conectores reales se implementarán en fases posteriores del desarrollo.