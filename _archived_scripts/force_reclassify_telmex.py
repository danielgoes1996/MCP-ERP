#!/usr/bin/env python3
"""
Force reclassify the TELMEX invoice to test alternative_candidates
"""

from core.ai_pipeline.classification.classification_service import classify_invoice_session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

# Get the TELMEX invoice
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
    port=int(os.getenv('POSTGRES_PORT', '5433')),
    database=os.getenv('POSTGRES_DB', 'mcp_system'),
    user=os.getenv('POSTGRES_USER', 'mcp_user'),
    password=os.getenv('POSTGRES_PASSWORD', 'changeme')
)
conn.cursor_factory = RealDictCursor
cursor = conn.cursor()

# Get the TELMEX invoice (uis_7836c15cbc22d6e1)
cursor.execute("""
    SELECT id, company_id, parsed_data, accounting_classification
    FROM sat_invoices
    WHERE id = 'uis_7836c15cbc22d6e1'
""")

row = cursor.fetchone()
if not row:
    print("❌ TELMEX invoice not found")
    exit(1)

session_id = row['id']
parsed_data = row['parsed_data']
current_classification = row['accounting_classification']

print(f"📋 Found invoice: {session_id}")
print(f"   Provider: {parsed_data.get('emisor', {}).get('nombre')}")
print(f"   Total: ${parsed_data.get('total')}")
print(f"   Current SAT: {current_classification.get('sat_account_code') if current_classification else 'None'}")

# Map carreta_verde to tenant_id
from core.shared.tenant_utils import get_tenant_and_company
tenant_id, company_id = get_tenant_and_company('carreta_verde')

print(f"\n🔄 Mapping: company_id='{company_id}' → tenant_id={tenant_id}")
print(f"⏳ Force reclassifying invoice...")

try:
    # Classify using tenant_id
    result = classify_invoice_session(
        session_id=session_id,
        company_id=tenant_id,  # Use tenant_id as int
        parsed_data=parsed_data,
        top_k=10
    )

    if not result:
        print("❌ Classification returned None")
        exit(1)

    print("\n✅ Classification completed!")
    print(f"   SAT code: {result.get('sat_account_code')}")
    print(f"   Confidence: {result.get('confidence_sat')}")
    print(f"   Explanation: {result.get('explanation_short')}")

    # Check alternative_candidates
    if result.get('alternative_candidates'):
        print(f"\n🎯 Alternative candidates: {len(result['alternative_candidates'])}")
        for i, alt in enumerate(result['alternative_candidates'], 1):
            print(f"   {i}. {alt['code']} - {alt['name']} (score: {alt['score']:.2f})")
        print("\n✅ SUCCESS! alternative_candidates are now included!")
    else:
        print("\n⚠️  WARNING: No alternative_candidates in result")
        print(f"   Result keys: {list(result.keys())}")

    # Save to database
    cursor.execute("""
        UPDATE sat_invoices
        SET accounting_classification = %s,
            updated_at = now()
        WHERE id = %s
    """, (json.dumps(result), session_id))

    conn.commit()
    print(f"\n💾 Saved to database")
    print(f"\n✅ Done! Refresh the frontend at http://localhost:3004/invoices/classification")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    conn.close()
