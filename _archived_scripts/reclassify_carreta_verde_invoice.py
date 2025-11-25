#!/usr/bin/env python3
"""
Reclassify the Carreta Verde invoice that was skipped due to company_id bug
"""

from core.ai_pipeline.classification.classification_service import classify_invoice_session
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

# Get the invoice that was skipped
conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
    port=int(os.getenv('POSTGRES_PORT', '5433')),
    database=os.getenv('POSTGRES_DB', 'mcp_system'),
    user=os.getenv('POSTGRES_USER', 'mcp_user'),
    password=os.getenv('POSTGRES_PASSWORD', 'changeme')
)
conn.cursor_factory = RealDictCursor
cursor = conn.cursor()

# Get the invoice with null classification
cursor.execute("""
    SELECT id, company_id, parsed_data
    FROM sat_invoices
    WHERE company_id = 'carreta_verde'
    AND accounting_classification IS NULL
    ORDER BY created_at DESC
    LIMIT 1
""")

row = cursor.fetchone()
if not row:
    print("❌ No unclassified invoices found for carreta_verde")
    exit(1)

session_id = row['id']
parsed_data = row['parsed_data']

print(f"📋 Found invoice: {session_id}")
print(f"   Provider: {parsed_data.get('emisor', {}).get('nombre')}")
print(f"   Total: ${parsed_data.get('total')}")
print(f"   First concept: {parsed_data.get('conceptos', [{}])[0].get('descripcion', 'N/A')}")

# Map carreta_verde to tenant_id
from core.shared.tenant_utils import get_tenant_and_company
tenant_id, company_id = get_tenant_and_company('carreta_verde')

print(f"\n🔄 Mapping: company_id='{company_id}' → tenant_id={tenant_id}")
print(f"⏳ Classifying invoice...")

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
    else:
        print("\n⚠️  No alternative_candidates in result")

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
