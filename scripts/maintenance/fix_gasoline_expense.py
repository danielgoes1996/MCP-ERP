#!/usr/bin/env python3
"""
Crear y actualizar gasto de gasolina directamente
"""

import xmlrpc.client

# Configuración desde variables de entorno
import os
ODOO_URL = os.getenv("ODOO_URL", "https://your-odoo-instance.odoo.com")
ODOO_DB = os.getenv("ODOO_DB", "your-database")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "your-email@domain.com")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "your-password")

def fix_gasoline_expense():
    try:
        # Conexión
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')

        # Buscar empleado
        employee_ids = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'hr.employee', 'search',
            [[]],
            {'limit': 1}
        )
        employee_id = employee_ids[0] if employee_ids else False

        print("⛽ Creando gasto básico primero...")

        # Crear gasto básico
        expense_data = {
            'name': 'GASOLINA VEHÍCULO EMPRESA - $800.00 MXN',
            'description': 'Combustible para vehículo de la empresa - Por facturar',
        }

        if employee_id:
            expense_data['employee_id'] = employee_id

        expense_id = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'hr.expense', 'create',
            [expense_data]
        )

        print(f"✅ Gasto creado con ID: {expense_id}")

        # Ahora actualizar con el monto
        print("💰 Actualizando con monto de $800...")

        update_result = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'hr.expense', 'write',
            [[expense_id], {
                'price_unit': 800.0,
                'quantity': 1.0
            }]
        )

        print(f"✅ Actualización: {update_result}")

        # Verificar resultado final
        print("🔍 Verificando gasto final...")
        expense_final = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'hr.expense', 'read',
            [[expense_id], ['name', 'price_unit', 'quantity', 'total_amount', 'state', 'employee_id']]
        )[0]

        print(f"\n📋 GASTO FINAL:")
        print(f"  • ID: {expense_final['id']}")
        print(f"  • Nombre: {expense_final.get('name')}")
        print(f"  • Precio unitario: ${expense_final.get('price_unit')}")
        print(f"  • Cantidad: {expense_final.get('quantity')}")
        print(f"  • Total: ${expense_final.get('total_amount')}")
        print(f"  • Estado: {expense_final.get('state')}")

        if expense_final.get('employee_id'):
            print(f"  • Empleado: {expense_final['employee_id'][1]}")

        return expense_id

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

if __name__ == "__main__":
    result = fix_gasoline_expense()
    if result:
        print(f"\n🎉 ¡Gasto de gasolina por $800 creado exitosamente! ID: {result}")
    else:
        print("\n💥 Error creando el gasto")