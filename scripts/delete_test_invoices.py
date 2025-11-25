#!/usr/bin/env python3
"""
Delete test invoices for daniel@carretaverde.com
"""

import sys
sys.path.insert(0, '/Users/danielgoes96/Desktop/mcp-server')

import psycopg2
from psycopg2.extras import RealDictCursor
from core.shared.db_config import POSTGRES_CONFIG

def delete_test_invoices():
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    # First, get the user_id for the email
    print("Buscando usuario daniel@carretaverde.com...")
    cursor.execute("""
        SELECT id, email, name
        FROM users
        WHERE email = 'daniel@carretaverde.com'
    """)

    user = cursor.fetchone()

    if not user:
        print("No se encontró el usuario daniel@carretaverde.com")
        conn.close()
        return

    user_id = str(user['id'])  # Convert to string since user_id column is TEXT
    print(f"Usuario encontrado: {user['name']} (ID: {user_id})")

    # Now, list the invoices to be deleted
    print(f"\nBuscando facturas para el usuario {user['email']}...")
    cursor.execute("""
        SELECT
            id,
            status,
            created_at,
            original_filename,
            company_id
        FROM sat_invoices
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))

    invoices = cursor.fetchall()

    if not invoices:
        print("No se encontraron facturas para eliminar")
        conn.close()
        return

    print(f"\nSe encontraron {len(invoices)} facturas:")
    for inv in invoices:
        print(f"  - ID: {inv['id']} | Filename: {inv['original_filename']} | Status: {inv['status']} | Company: {inv['company_id']} | Created: {inv['created_at']}")

    # Delete the invoices (auto-confirmed since user requested deletion)
    print(f"\n🗑️  Eliminando {len(invoices)} facturas...")
    cursor.execute("""
        DELETE FROM sat_invoices
        WHERE user_id = %s
    """, (user_id,))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"✅ Se eliminaron {deleted_count} facturas exitosamente")

if __name__ == "__main__":
    delete_test_invoices()
