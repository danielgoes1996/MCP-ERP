#!/usr/bin/env python3
"""
Reclassify a single invoice to test hierarchical family constraint fix
"""

import sys
import asyncio
sys.path.insert(0, '/Users/danielgoes96/Desktop/mcp-server')

from core.shared.db_config import get_connection
from core.ai_pipeline.classification.classification_service import classify_invoice_session
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reclassify_invoice(session_id: str):
    """Reclassify a single invoice"""

    # Get the invoice data
    conn = get_connection(dict_cursor=True)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            company_id,
            user_id,
            original_filename,
            extracted_data,
            accounting_classification
        FROM sat_invoices
        WHERE id = %s
    """, (session_id,))

    session = cursor.fetchone()

    if not session:
        logger.error(f"Session {session_id} not found")
        cursor.close()
        conn.close()
        return

    logger.info(f"Found invoice: {session['original_filename']}")
    logger.info(f"Company: {session['company_id']}, User: {session['user_id']}")

    # Get tenant_id for classification
    from core.shared.tenant_utils import get_tenant_and_company
    tenant_id, _ = get_tenant_and_company(session['company_id'])

    parsed_data = session.get('extracted_data')
    if not parsed_data:
        logger.error("No extracted_data found")
        cursor.close()
        conn.close()
        return

    # Show old classification
    old_classification = session.get('accounting_classification', {})
    logger.info(f"\n📊 OLD CLASSIFICATION:")
    logger.info(f"   SAT Code: {old_classification.get('sat_account_code')}")
    logger.info(f"   Family: {old_classification.get('family_code')}")
    logger.info(f"   Confidence: {old_classification.get('confidence_sat', 0)*100:.0f}%")

    old_h_phase1 = old_classification.get('metadata', {}).get('hierarchical_phase1', {})
    if old_h_phase1:
        logger.info(f"   Hierarchical Phase 1:")
        logger.info(f"     - Family: {old_h_phase1.get('family_code')} - {old_h_phase1.get('family_name')}")
        logger.info(f"     - Confidence: {old_h_phase1.get('confidence', 0)*100:.0f}%")
        logger.info(f"     - Override: {old_h_phase1.get('override_uso_cfdi')}")

    cursor.close()
    conn.close()

    # Reclassify
    logger.info(f"\n🔄 RECLASSIFYING WITH HIERARCHICAL CONSTRAINT...")

    classification_dict = classify_invoice_session(
        session_id=session_id,
        company_id=tenant_id,
        parsed_data=parsed_data,
        top_k=10
    )

    if not classification_dict:
        logger.error("Classification failed")
        return

    # Save new classification
    conn = get_connection(dict_cursor=True)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sat_invoices
        SET accounting_classification = %s,
            updated_at = now()
        WHERE id = %s
    """, (json.dumps(classification_dict), session_id))

    conn.commit()
    cursor.close()
    conn.close()

    # Show new classification
    logger.info(f"\n✅ NEW CLASSIFICATION:")
    logger.info(f"   SAT Code: {classification_dict.get('sat_account_code')}")
    logger.info(f"   Family: {classification_dict.get('family_code')}")
    logger.info(f"   Confidence: {classification_dict.get('confidence_sat', 0)*100:.0f}%")
    logger.info(f"   Explanation: {classification_dict.get('explanation_short')}")

    new_h_phase1 = classification_dict.get('metadata', {}).get('hierarchical_phase1', {})
    if new_h_phase1:
        logger.info(f"   Hierarchical Phase 1:")
        logger.info(f"     - Family: {new_h_phase1.get('family_code')} - {new_h_phase1.get('family_name')}")
        logger.info(f"     - Confidence: {new_h_phase1.get('confidence', 0)*100:.0f}%")
        logger.info(f"     - Override: {new_h_phase1.get('override_uso_cfdi')}")
        if new_h_phase1.get('override_reason'):
            logger.info(f"     - Reason: {new_h_phase1.get('override_reason')}")

    # Validate fix
    if new_h_phase1:
        h_family = new_h_phase1.get('family_code')
        final_family = classification_dict.get('family_code')

        if h_family and final_family:
            if h_family == final_family:
                logger.info(f"\n✅ SUCCESS! Final classification respects hierarchical family constraint")
                logger.info(f"   Phase 1 family: {h_family} == Final family: {final_family}")
            else:
                logger.error(f"\n❌ FAIL! Final classification violates hierarchical family constraint")
                logger.error(f"   Phase 1 family: {h_family} != Final family: {final_family}")

    logger.info(f"\n🔗 View in UI: http://localhost:3000/invoices")

if __name__ == "__main__":
    session_id = "uis_7aeab6fb6f7e066d"  # GARIN invoice
    asyncio.run(reclassify_invoice(session_id))
