#!/usr/bin/env python3
"""
Manually correct PASE invoice to 601.48 (Peajes)
The system will learn from this correction for future PASE invoices
"""

import sys
sys.path.insert(0, '/Users/danielgoes96/Desktop/mcp-server')

from core.shared.db_config import get_connection
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def correct_pase_invoice():
    """Correct PASE invoice to proper toll classification"""

    session_id = "uis_a19973b6cace44ec"  # PASE invoice

    conn = get_connection(dict_cursor=True)
    cursor = conn.cursor()

    # Get current classification
    cursor.execute("""
        SELECT
            accounting_classification,
            extracted_data
        FROM sat_invoices
        WHERE id = %s
    """, (session_id,))

    session = cursor.fetchone()

    if not session:
        logger.error(f"Session {session_id} not found")
        cursor.close()
        conn.close()
        return

    old_classification = session.get('accounting_classification') or {}
    extracted_data = session.get('extracted_data') or {}

    print("="*80)
    print("CORRECCIÓN MANUAL: PASE INVOICE → 601.48 (PEAJES)")
    print("="*80)

    print(f"\n📊 CLASIFICACIÓN ACTUAL:")
    print(f"   SAT Code: {old_classification.get('sat_account_code')}")
    print(f"   Family: {old_classification.get('family_code')}")
    print(f"   Explicación: {old_classification.get('explanation_short')}")

    # Build corrected classification
    corrected_classification = old_classification.copy()
    corrected_classification['sat_account_code'] = '601.48'
    corrected_classification['family_code'] = '601'
    corrected_classification['confidence_sat'] = 1.0  # 100% because it's manual correction
    corrected_classification['explanation_short'] = 'Recarga de tarjeta de peaje IDMX - Corregido manualmente'
    corrected_classification['explanation'] = (
        'Factura de PASE por recarga del sistema IDMX (Infraestructura de Movilidad de la CDMX). '
        'IDMX es el sistema de pago electrónico de peajes en la Ciudad de México. '
        'Aunque la descripción solo dice "RECARGA IDMX", se trata de una recarga de saldo '
        'para pago de peajes en autopistas urbanas. Clasificación correcta: 601.48 (Peajes y casetas).'
    )

    # Preserve metadata but mark as corrected
    if 'metadata' not in corrected_classification:
        corrected_classification['metadata'] = {}

    corrected_classification['metadata']['manual_correction'] = {
        'corrected_at': 'now()',
        'corrected_from': old_classification.get('sat_account_code'),
        'corrected_to': '601.48',
        'reason': 'PASE + IDMX = Sistema de peajes de CDMX',
        'note': 'Sistema aprenderá de esta corrección para futuras facturas PASE'
    }

    # Update classification
    cursor.execute("""
        UPDATE sat_invoices
        SET accounting_classification = %s,
            updated_at = now()
        WHERE id = %s
    """, (json.dumps(corrected_classification), session_id))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n✅ NUEVA CLASIFICACIÓN:")
    print(f"   SAT Code: {corrected_classification.get('sat_account_code')}")
    print(f"   Family: {corrected_classification.get('family_code')}")
    print(f"   Confianza: {corrected_classification.get('confidence_sat', 0)*100:.0f}%")
    print(f"   Explicación: {corrected_classification.get('explanation_short')}")

    print(f"\n📚 APRENDIZAJE:")
    print(f"   Esta corrección se guardó en el sistema.")
    print(f"   Futuras facturas de PASE con 'RECARGA IDMX' deberían clasificarse")
    print(f"   automáticamente como 601.48 gracias al sistema de correcciones.")

    print(f"\n🔗 View in UI: http://localhost:3000/invoices")
    print("\n" + "="*80)

if __name__ == "__main__":
    correct_pase_invoice()
