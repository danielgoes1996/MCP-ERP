#!/usr/bin/env python3
"""Script simple para borrar todas las facturas de carreta_verde."""

from core.internal_db import get_db

def delete_all_carreta_verde_data():
    """Borra TODAS las facturas y registros de carreta_verde."""
    db = get_db()
    cursor = db.cursor()

    company_id = 'carreta_verde'
    tenant_id = 3

    print(f"Borrando datos de company_id='{company_id}', tenant_id={tenant_id}")

    # 1. Borrar de expense_records
    cursor.execute("DELETE FROM expense_records WHERE company_id = ? OR tenant_id = ?", (company_id, tenant_id))
    deleted_records = cursor.rowcount
    print(f"✅ Borrados {deleted_records} registros de expense_records")

    # 2. Borrar de expense_invoices
    cursor.execute("DELETE FROM expense_invoices WHERE tenant_id = ?", (tenant_id,))
    deleted_invoices = cursor.rowcount
    print(f"✅ Borrados {deleted_invoices} registros de expense_invoices")

    # 3. Borrar attachments
    cursor.execute("DELETE FROM expense_attachments WHERE tenant_id = ?", (tenant_id,))
    deleted_attachments = cursor.rowcount
    print(f"✅ Borrados {deleted_attachments} registros de expense_attachments")

    # 4. Commit
    db.commit()
    print(f"\n✅ COMPLETADO: Todos los datos de '{company_id}' han sido eliminados")

    # Verificar
    cursor.execute("SELECT COUNT(*) FROM expense_records WHERE company_id = ? OR tenant_id = ?", (company_id, tenant_id))
    remaining = cursor.fetchone()[0]
    print(f"Verificación: {remaining} registros restantes (debería ser 0)")

if __name__ == "__main__":
    delete_all_carreta_verde_data()
