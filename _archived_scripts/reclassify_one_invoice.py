#!/usr/bin/env python3
"""
Reclassify one invoice from carreta_verde to add alternative_candidates
"""

from core.ai_pipeline.classification.classification_service import classify_invoice_session

# Reclassify one specific session
session_id = "uis_b3e66458071744fc"  # FINKOK invoice

print(f"📋 Reclassifying invoice: {session_id}")
print("⏳ This will update the classification with alternative_candidates...")

try:
    result = classify_invoice_session(session_id, force_reclassify=True)

    print("\n✅ Classification completed!")
    print(f"   SAT code: {result.get('sat_account_code')}")
    print(f"   Confidence: {result.get('confidence_sat')}")
    print(f"   Explanation: {result.get('explanation_short')}")

    if result.get('alternative_candidates'):
        print(f"\n🎯 Alternative candidates: {len(result['alternative_candidates'])}")
        for i, alt in enumerate(result['alternative_candidates'], 1):
            print(f"   {i}. {alt['code']} - {alt['name']} (score: {alt['score']:.2f})")
    else:
        print("\n❌ No alternative_candidates in result")

    print("\n✅ Done! Now refresh the frontend to see the dropdown.")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
