#!/usr/bin/env python3
"""
Re-process existing payment complements (tipo P) to extract pago20:Pagos data.

This script updates all existing tipo P invoices in the database to include
the payment complement data (parcialidades, documentos relacionados, etc.)
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml

def main():
    # Connect to database
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
        port=int(os.getenv('POSTGRES_PORT', '5433')),
        database=os.getenv('POSTGRES_DB', 'mcp_system'),
        user=os.getenv('POSTGRES_USER', 'mcp_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'changeme')
    )
    conn.autocommit = False
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get all tipo P invoices
    cursor.execute("""
        SELECT id, invoice_file_path, parsed_data, company_id
        FROM sat_invoices
        WHERE parsed_data->>'tipo_comprobante' = 'P'
        ORDER BY created_at DESC
    """)

    invoices = cursor.fetchall()
    print(f"📋 Found {len(invoices)} payment complements to process")

    updated_count = 0
    error_count = 0

    for invoice in invoices:
        session_id = invoice['id']
        file_path = invoice['invoice_file_path']
        current_parsed_data = invoice['parsed_data']
        company_id = invoice['company_id']

        # Check if already has payment_complement
        if 'payment_complement' in current_parsed_data:
            print(f"⏭️  {session_id} already has payment_complement, skipping")
            continue

        try:
            # Read XML file
            if not os.path.exists(file_path):
                print(f"⚠️  {session_id}: File not found: {file_path}")
                error_count += 1
                continue

            with open(file_path, 'rb') as f:
                xml_content = f.read()

            # Re-parse with new parser
            parsed = parse_cfdi_xml(xml_content)

            # Check if payment_complement was extracted
            if 'payment_complement' not in parsed:
                print(f"⚠️  {session_id}: No payment_complement extracted (might not be tipo P)")
                error_count += 1
                continue

            # Merge payment_complement into existing parsed_data
            current_parsed_data['payment_complement'] = parsed['payment_complement']

            # Update database
            cursor.execute("""
                UPDATE sat_invoices
                SET parsed_data = %s,
                    updated_at = now()
                WHERE id = %s
            """, (json.dumps(current_parsed_data), session_id))

            # Get payment details for logging
            pagos = parsed['payment_complement'].get('pagos', [])
            if pagos:
                pago = pagos[0]
                monto = pago.get('monto', 0)
                fecha_pago = pago.get('fecha_pago', 'N/A')
                docs = pago.get('documentos_relacionados', [])
                num_parcialidad = docs[0].get('num_parcialidad', 0) if docs else 0

                print(f"✅ {session_id} ({company_id}): ${monto} MXN - Parcialidad #{num_parcialidad} - {fecha_pago}")
            else:
                print(f"✅ {session_id} ({company_id}): Updated")

            updated_count += 1

        except Exception as e:
            print(f"❌ {session_id}: Error: {e}")
            error_count += 1
            continue

    # Commit all changes
    conn.commit()
    print(f"\n📊 Summary:")
    print(f"   ✅ Updated: {updated_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📋 Total: {len(invoices)}")

    conn.close()

if __name__ == '__main__':
    main()
