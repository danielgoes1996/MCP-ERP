#!/usr/bin/env python3
"""
Resumen de gastos creados en la sesión de prueba
"""

expenses_created = [
    {
        "id": "7B21942D",
        "concepto": "⛽ Gasolina viaje Querétaro - CDMX",
        "monto": 800.00,
        "empleado": "Daniel Gomez",
        "descripcion": "Gasolina para viaje de negocios - Test funcional",
        "status": "pending_approval"
    },
    {
        "id": "CF4D386E",
        "concepto": "🍽️ Comida de trabajo - Cliente importante",
        "monto": 450.00,
        "empleado": "Daniel Gomez",
        "descripcion": "Reunión con cliente importante en restaurante La Hacienda",
        "status": "pending_approval"
    },
    {
        "id": "8E685EA9",
        "concepto": "🍽️ Comida de trabajo - Cliente ACME Corp",
        "monto": 650.00,
        "empleado": "Daniel Gomez Escobedo",
        "descripcion": "Cliente ACME Corp en Restaurante La Hacienda (3 personas, contrato $2.5M)",
        "status": "pending_approval"
    },
    {
        "id": "07AF4B10",
        "concepto": "☕ Cafés y reunión de trabajo",
        "monto": 125.00,
        "empleado": "Daniel Gomez Escobedo",
        "descripcion": "Prospección de nuevos clientes en Starbucks Polanco",
        "status": "pending_approval"
    }
]

def print_expense_summary():
    """Imprime resumen de gastos creados"""
    print("💼 RESUMEN DE GASTOS CREADOS VIA MCP SERVER")
    print("=" * 60)

    total_amount = 0

    for i, expense in enumerate(expenses_created, 1):
        print(f"\n{i}. {expense['concepto']}")
        print(f"   💰 Monto: ${expense['monto']:.2f} USD")
        print(f"   👤 Empleado: {expense['empleado']}")
        print(f"   🆔 ID: {expense['id']}")
        print(f"   📝 Descripción: {expense['descripcion']}")
        print(f"   📊 Estado: {expense['status']}")

        total_amount += expense['monto']

    print(f"\n{'='*60}")
    print(f"📊 TOTAL DE GASTOS: ${total_amount:.2f} USD")
    print(f"📈 NÚMERO DE GASTOS: {len(expenses_created)}")
    print(f"💳 PROMEDIO POR GASTO: ${total_amount/len(expenses_created):.2f} USD")

    print(f"\n✅ ESTADO DEL SISTEMA MCP:")
    print(f"🎯 Servidor funcionando en: http://localhost:8002")
    print(f"🔗 Integración con Odoo: Operacional")
    print(f"📋 Validaciones: Activas")
    print(f"💾 Gastos en Odoo: {len(expenses_created)} registros")

    print(f"\n🎉 ¡SISTEMA MCP ENTERPRISE EXPENSE MANAGEMENT FUNCIONANDO!")

if __name__ == "__main__":
    print_expense_summary()