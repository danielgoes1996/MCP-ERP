#!/usr/bin/env python3
"""
Reclassify PASE invoice to test multi-concept handling fix
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

async def reclassify_pase():
    """Reclassify PASE invoice with multi-concept fix"""

    session_id = "uis_a19973b6cace44ec"  # PASE invoice

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
    cursor.close()
    conn.close()

    if not session:
        logger.error(f"Session {session_id} not found")
        return

    extracted_data = session.get('extracted_data') or {}
    old_classification = session.get('accounting_classification') or {}

    conceptos = extracted_data.get('conceptos', [])

    print("="*100)
    print("RECLASIFICACIÓN PASE - TEST DE FIX MULTI-CONCEPTO")
    print("="*100)

    print(f"\n📄 FACTURA: {session['original_filename']}")
    print(f"   Session: {session_id}")
    print(f"   Total: ${extracted_data.get('total', 0)}")

    print(f"\n📝 CONCEPTOS ({len(conceptos)}):")
    for i, concepto in enumerate(conceptos, 1):
        print(f"   [{i}] {concepto.get('descripcion', 'N/A')}")
        print(f"       Importe: ${concepto.get('importe', 0)}")
        print(f"       ClaveProdServ: {concepto.get('clave_prod_serv', 'N/A')}")

    # Show which concept should be selected
    if len(conceptos) > 1:
        max_concepto = max(conceptos, key=lambda c: float(c.get('importe', 0)))
        print(f"\n🎯 CONCEPTO DE MAYOR IMPORTE (será usado para clasificación):")
        print(f"   '{max_concepto.get('descripcion', 'N/A')}'")
        print(f"   Importe: ${max_concepto.get('importe', 0)}")
        print(f"   ClaveProdServ: {max_concepto.get('clave_prod_serv', 'N/A')}")

    print(f"\n📊 CLASIFICACIÓN ANTERIOR:")
    print(f"   SAT Code: {old_classification.get('sat_account_code', 'N/A')}")
    print(f"   Family: {old_classification.get('family_code', 'N/A')}")
    print(f"   Confidence: {old_classification.get('confidence_sat', 0)*100:.0f}%")
    print(f"   Explicación: {old_classification.get('explanation_short', 'N/A')}")

    old_h_phase1 = old_classification.get('metadata', {}).get('hierarchical_phase1', {})
    if old_h_phase1:
        print(f"   Hierarchical Phase 1: {old_h_phase1.get('family_code')} - {old_h_phase1.get('family_name')}")

    # Get tenant_id for classification
    from core.shared.tenant_utils import get_tenant_and_company
    tenant_id, _ = get_tenant_and_company(session['company_id'])

    parsed_data = extracted_data
    if not parsed_data:
        logger.error("No extracted_data found")
        return

    # Reclassify with new multi-concept logic
    print(f"\n🔄 RECLASIFICANDO CON FIX DE MULTI-CONCEPTO...")

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
    print(f"\n✅ NUEVA CLASIFICACIÓN:")
    print(f"   SAT Code: {classification_dict.get('sat_account_code', 'N/A')}")
    print(f"   Family: {classification_dict.get('family_code', 'N/A')}")
    print(f"   Confidence: {classification_dict.get('confidence_sat', 0)*100:.0f}%")
    print(f"   Explicación: {classification_dict.get('explanation_short', 'N/A')}")

    new_h_phase1 = classification_dict.get('metadata', {}).get('hierarchical_phase1', {})
    if new_h_phase1:
        print(f"   Hierarchical Phase 1: {new_h_phase1.get('family_code')} - {new_h_phase1.get('family_name')}")

    # Validate fix
    print(f"\n🎯 RESULTADO DEL FIX:")
    new_code = classification_dict.get('sat_account_code')
    new_family = classification_dict.get('family_code')

    if new_code == '601.48':
        print(f"   ✅ SUCCESS! Clasificado como 601.48 (Peajes)")
        print(f"   El sistema ahora detecta correctamente que la recarga IDMX es peaje")
    elif new_family == '600':
        print(f"   ⚠️  PARTIAL: Familia 600 correcta (Gastos operación), pero código específico: {new_code}")
    elif new_family == '700':
        print(f"   ❌ FAIL: Sigue clasificando como familia 700 (Gastos financieros)")
        print(f"   Todavía usando el concepto de comisión ($8.62) en lugar del peaje ($336.21)")
    else:
        print(f"   ❓ Clasificó como familia {new_family} - {new_code}")

    print(f"\n🔗 View in UI: http://localhost:3000/invoices")
    print("\n" + "="*100)

if __name__ == "__main__":
    asyncio.run(reclassify_pase())
