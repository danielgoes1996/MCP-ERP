#!/usr/bin/env python3
"""
Trace what exact description Phase 2A receives for Amazon invoices.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.shared.db_config import get_connection

def trace_amazon_invoice():
    """Show exactly what Phase 2A receives for Amazon invoice."""

    conn = get_connection()
    cursor = conn.cursor()

    # Get an Amazon Storage invoice
    cursor.execute("""
        SELECT
            id,
            provider_name,
            provider_rfc,
            description,
            amount,
            metodo_pago,
            forma_pago,
            enhanced_data
        FROM expenses
        WHERE provider_name LIKE '%AMAZON%'
          AND description LIKE '%Tarifas de almacenamiento%'
        LIMIT 1
    """)

    row = cursor.fetchone()
    if not row:
        print("❌ No Amazon storage invoice found")
        return

    (expense_id, provider_name, provider_rfc, descripcion, monto,
     metodo_pago, forma_pago, enhanced_data) = row

    # Parse enhanced_data to get SAT fields and all_conceptos
    import json
    enhanced = json.loads(enhanced_data) if enhanced_data else {}
    uso_cfdi = enhanced.get('uso_cfdi', 'N/A')
    clave_prod_serv = enhanced.get('clave_prod_serv', 'N/A')
    all_conceptos = enhanced.get('all_conceptos', [])

    print("\n" + "="*100)
    print("🔍 TRACE: WHAT PHASE 2A RECEIVES FOR AMAZON STORAGE INVOICE")
    print("="*100)

    print(f"\n📋 RAW DATABASE DATA:")
    print(f"   Expense ID: {expense_id}")
    print(f"   Provider: {provider_name}")
    print(f"   RFC: {provider_rfc}")
    print(f"   Descripción DB: {descripcion}")
    print(f"   Monto: ${monto:,.2f}")
    print(f"   Método pago: {metodo_pago}")
    print(f"   Forma pago: {forma_pago}")
    print(f"   Uso CFDI: {uso_cfdi}")
    print(f"   ClaveProdServ: {clave_prod_serv}")
    print(f"   All conceptos: {all_conceptos}")

    # Now simulate what classification_service.py does
    print(f"\n🔧 SIMULATING CLASSIFICATION_SERVICE.PY PROCESSING:")

    # all_conceptos is already parsed from enhanced_data
    try:
        if all_conceptos:
            conceptos_list = all_conceptos
            print(f"   ✅ Parsed {len(conceptos_list)} conceptos")

            # Build enriched description (as per classification_service.py lines 137-182)
            enriched_desc_parts = []

            if conceptos_list and len(conceptos_list) > 0:
                # Primary concept (highest amount)
                primary = conceptos_list[0]
                primary_desc = primary.get('descripcion', '')
                primary_sat = primary.get('sat_name', '')
                primary_pct = primary.get('percentage', 0)

                print(f"\n   📌 PRIMARY CONCEPT:")
                print(f"      Descripción: {primary_desc}")
                print(f"      SAT Name: {primary_sat}")
                print(f"      Percentage: {primary_pct:.1f}%")

                if primary_desc:
                    if primary_sat:
                        enriched_desc_parts.append(f"{primary_desc} ({primary_pct:.1f}% - {primary_sat})")
                    else:
                        enriched_desc_parts.append(f"{primary_desc} ({primary_pct:.1f}%)")

                # Additional concepts if any
                if len(conceptos_list) > 1:
                    print(f"\n   📎 ADDITIONAL CONCEPTS:")
                    additional_descs = []
                    for i, concepto in enumerate(conceptos_list[1:], start=2):
                        desc = concepto.get('descripcion', '')
                        pct = concepto.get('percentage', 0)
                        sat_name = concepto.get('sat_name', '')

                        print(f"      {i}. {desc} ({pct:.1f}%) - {sat_name}")

                        if desc:
                            if pct >= 5.0:
                                additional_descs.append(f"{desc} ({pct:.1f}%)")
                            else:
                                additional_descs.append(desc)

                    if additional_descs:
                        enriched_desc_parts.append(f"Adicionales: {', '.join(additional_descs)}")

            # Combine or fallback to original
            enriched_description = ' | '.join(enriched_desc_parts) if enriched_desc_parts else descripcion

            print(f"\n🎯 FINAL ENRICHED DESCRIPTION SENT TO PHASE 2A:")
            print(f"   \"{enriched_description}\"")

            print(f"\n📊 COMPARISON:")
            print(f"   ❌ OLD (just primary): \"{descripcion}\"")
            print(f"   ✅ NEW (enriched):     \"{enriched_description}\"")

            # Check if keywords are present
            keywords_to_check = ['almacenamiento', 'logística', 'amazon', 'storage', 'fba']
            print(f"\n🔎 KEYWORD PRESENCE CHECK:")
            for kw in keywords_to_check:
                present = kw.lower() in enriched_description.lower()
                print(f"   {'✅' if present else '❌'} '{kw}': {present}")

    except Exception as e:
        print(f"   ❌ Error parsing conceptos: {e}")
        import traceback
        traceback.print_exc()

    cursor.close()
    conn.close()

    print("\n" + "="*100)


if __name__ == '__main__':
    trace_amazon_invoice()
