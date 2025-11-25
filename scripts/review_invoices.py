#!/usr/bin/env python3
"""
Review processed invoices one by one with detailed classification info
"""

import sys
sys.path.insert(0, '/Users/danielgoes96/Desktop/mcp-server')

from core.shared.db_config import get_connection
import json

conn = get_connection(dict_cursor=True)
cursor = conn.cursor()

cursor.execute('''
    SELECT
        id,
        original_filename,
        extracted_data,
        accounting_classification,
        created_at
    FROM sat_invoices
    WHERE company_id = %s
      AND user_id = %s
    ORDER BY created_at DESC
    LIMIT 10
''', ('carreta_verde', '11'))

sessions = cursor.fetchall()
cursor.close()
conn.close()

print('\n' + '='*100)
print(f'RESUMEN: {len(sessions)} FACTURAS PROCESADAS')
print('='*100 + '\n')

for idx, s in enumerate(sessions, 1):
    data = s.get('extracted_data') or {}
    classification = s.get('accounting_classification') or {}
    h_phase1 = classification.get('metadata', {}).get('hierarchical_phase1', {})

    emisor = data.get('emisor', {})
    receptor = data.get('receptor', {})
    total = data.get('total', 0)
    conceptos = data.get('conceptos', [])
    descripcion = conceptos[0].get('descripcion', 'N/A') if conceptos else 'N/A'

    print('─'*100)
    print(f'[{idx}] {s["original_filename"][:60]}')
    print('─'*100)
    print(f'📄 Proveedor: {emisor.get("nombre", "N/A")}')
    print(f'   RFC: {emisor.get("rfc", "N/A")}')
    print(f'💰 Total: ${total:,.2f} MXN')
    print(f'📝 Descripción: {descripcion[:80]}')
    print(f'📌 UsoCFDI declarado por proveedor: {receptor.get("uso_cfdi", "N/A")}')

    if h_phase1:
        print(f'\n🏷️  CLASIFICACIÓN JERÁRQUICA (Fase 1):')
        print(f'   • Familia: {h_phase1.get("family_code")} - {h_phase1.get("family_name")}')
        print(f'   • Confianza: {h_phase1.get("confidence", 0)*100:.0f}%')

        if h_phase1.get('override_uso_cfdi'):
            print(f'   🔄 OVERRIDE DETECTADO:')
            override_reason = h_phase1.get("override_reason", "N/A")
            # Wrap long text
            if len(override_reason) > 90:
                words = override_reason.split()
                lines = []
                current_line = []
                current_length = 0
                for word in words:
                    if current_length + len(word) + 1 > 90:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                        current_length = len(word)
                    else:
                        current_line.append(word)
                        current_length += len(word) + 1
                if current_line:
                    lines.append(' '.join(current_line))
                print(f'      Razón: {lines[0]}')
                for line in lines[1:]:
                    print(f'             {line}')
            else:
                print(f'      Razón: {override_reason}')

    if classification.get('sat_account_code'):
        print(f'\n📊 CLASIFICACIÓN SAT:')
        print(f'   • Código SAT: {classification.get("sat_account_code")}')
        print(f'   • Confianza: {classification.get("confidence_sat", 0)*100:.0f}%')
        print(f'   • Explicación: {classification.get("explanation_short", "N/A")}')

        # Show alternatives if available
        alternatives = classification.get('alternative_candidates', [])
        if alternatives:
            print(f'\n   Alternativas sugeridas:')
            for alt in alternatives[:3]:  # Show top 3
                print(f'      - {alt.get("code")} ({alt.get("score", 0)*100:.0f}%) - {alt.get("name", "N/A")[:50]}')

    print()

print('='*100)
print('\n✅ Todas las facturas están listas para revisión en el frontend')
print('   Abre http://localhost:3000/invoices para verlas con la UI completa\n')
