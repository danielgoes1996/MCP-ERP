#!/usr/bin/env python3
"""
Crear gasto de comida de trabajo para demostrar funcionamiento
"""

import json
from datetime import datetime, timedelta

# Gasto de comida de trabajo
food_expense = {
    "name": "🍽️ Comida de trabajo - Cliente ACME Corp",
    "description": "Reunión de negocios en restaurante La Hacienda para cerrar contrato de distribución. Asistieron 3 personas del equipo comercial.",
    "amount": 650.00,
    "expense_date": (datetime.now() - timedelta(hours=2)).isoformat(),

    "supplier": {
        "name": "Restaurante La Hacienda S.A. de C.V.",
        "rfc": "RLH850920ABC",
        "address": "Av. Presidente Masaryk 415, Polanco, CDMX",
        "phone": "55-5280-1234",
        "email": "facturacion@lahacienda.mx"
    },

    "tax_info": {
        "subtotal": 560.34,
        "iva_rate": 0.16,
        "iva_amount": 89.66,
        "total": 650.00
    },

    "account_code": "5203001",  # Gastos de representación
    "analytic_account": "VENTAS_COMERCIAL",
    "category": "Gastos de Representación",

    "payment_method": "tarjeta_empresa",
    "who_paid": "company",

    "employee_id": 1,
    "employee_name": "Daniel Gomez Escobedo",

    "status": "draft",
    "created_by": "user@company.com",
    "notes": "Reunión exitosa - Cliente confirmó contrato anual por $2.5M MXN"
}

def create_food_expense():
    """Crea gasto de comida usando método completo"""

    payload = {
        "method": "create_complete_expense",
        "params": food_expense
    }

    print("🍽️ CREANDO GASTO DE COMIDA DE TRABAJO")
    print("=" * 50)
    print(f"Concepto: {food_expense['name']}")
    print(f"Monto: ${food_expense['amount']:.2f} MXN")
    print(f"Proveedor: {food_expense['supplier']['name']}")
    print(f"RFC: {food_expense['supplier']['rfc']}")
    print(f"Descripción: {food_expense['description']}")
    print()

    # Mostrar el payload JSON
    print("📄 PAYLOAD JSON:")
    print("-" * 30)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()

    # Generar comando curl
    json_str = json.dumps(payload, ensure_ascii=False).replace("'", "\\'")
    print("🚀 COMANDO CURL:")
    print("-" * 30)
    print(f"""curl -X POST "http://localhost:8002/mcp" \\
     -H "Content-Type: application/json" \\
     -d '{json_str}'""")

    print()
    print("🎯 RESULTADO ESPERADO:")
    print("✅ Validación exitosa de campos")
    print("✅ Mapeo de proveedor 'Restaurante La Hacienda'")
    print("✅ Creación de gasto en Odoo con ID único")
    print("✅ Registro en cuenta contable 5203001")
    print("✅ Asignación a centro de costos VENTAS_COMERCIAL")

if __name__ == "__main__":
    create_food_expense()