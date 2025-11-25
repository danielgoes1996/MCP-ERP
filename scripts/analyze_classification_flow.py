#!/usr/bin/env python3
"""
Analyze classification flow for invoices.
Shows what happened during classification and what fields are populated.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os

def analyze_invoices(company_id: str = 'carreta_verde'):
    """Analyze classification flow for a company's invoices."""

    conn = psycopg2.connect(
        host=os.getenv('PG_HOST', '127.0.0.1'),
        port=int(os.getenv('PG_PORT', 5433)),
        database=os.getenv('PG_DB', 'mcp_system'),
        user=os.getenv('PG_USER', 'mcp_user'),
        password=os.getenv('PG_PASSWORD', 'changeme')
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get all invoices with detailed classification info
        query = """
            SELECT
                id,
                original_filename,
                status,
                created_at,
                accounting_classification
            FROM sat_invoices
            WHERE company_id = %s
            ORDER BY created_at DESC
            LIMIT 15
        """

        cursor.execute(query, (company_id,))
        invoices = cursor.fetchall()

        print("="*100)
        print(f"ANÁLISIS DE CLASIFICACIÓN - {company_id}")
        print("="*100)
        print(f"\nTotal de facturas encontradas: {len(invoices)}\n")

        for idx, invoice in enumerate(invoices, 1):
            print(f"\n{'='*100}")
            print(f"FACTURA #{idx}: {invoice['original_filename'][:70]}")
            print(f"{'='*100}")
            print(f"ID: {invoice['id']}")
            print(f"Status: {invoice['status']}")
            print(f"Fecha creación: {invoice['created_at']}")

            acc_class = invoice.get('accounting_classification')

            if not acc_class:
                print("\n⚠️  SIN CLASIFICACIÓN")
                continue

            print(f"\n--- CLASIFICACIÓN CONTABLE ---")

            # Core classification fields
            print(f"\nCódigo SAT: {acc_class.get('sat_account_code', 'N/A')}")
            print(f"Nombre SAT: {acc_class.get('sat_account_name', '❌ FALTA')}")
            print(f"Código familia: {acc_class.get('family_code', 'N/A')}")
            print(f"Confianza SAT: {acc_class.get('confidence_sat', 'N/A')}")
            print(f"Confianza familia: {acc_class.get('confidence_family', 'N/A')}")

            # Explanation fields
            print(f"\n--- EXPLICACIÓN ---")
            print(f"Corta: {acc_class.get('explanation_short', 'N/A')}")
            print(f"Detallada: {acc_class.get('explanation_detail', '❌ FALTA')[:100] if acc_class.get('explanation_detail') else '❌ FALTA'}")

            # Model info
            print(f"\n--- MODELO ---")
            print(f"Versión modelo: {acc_class.get('model_version', '❌ FALTA')}")
            print(f"Versión prompt: {acc_class.get('prompt_version', '❌ FALTA')}")

            # Metadata
            metadata = acc_class.get('metadata', {})
            if not metadata:
                metadata = {}

            print(f"\n--- METADATA ---")
            has_raw = 'llm_raw_response' in metadata
            print(f"Respuesta LLM guardada: {'✅ SÍ' if has_raw else '❌ NO'}")

            if has_raw:
                raw_response = metadata['llm_raw_response']
                print(f"Longitud respuesta: {len(raw_response)} caracteres")
                print(f"Preview: {raw_response[:150]}...")

                # Check if it's wrapped in markdown
                if '```json' in raw_response:
                    print("⚠️  FORMATO: Markdown code block detectado")
                elif raw_response.strip().startswith('{'):
                    print("✅ FORMATO: JSON directo")
                else:
                    print("⚠️  FORMATO: Formato desconocido")

            # Alternative candidates
            alt_candidates = acc_class.get('alternative_candidates', [])
            if alt_candidates and len(alt_candidates) > 0:
                print(f"\n--- CANDIDATOS ALTERNATIVOS ---")
                print(f"Total: {len(alt_candidates)}")
                for i, cand in enumerate(alt_candidates[:3], 1):
                    print(f"  {i}. {cand.get('code', 'N/A')} - {cand.get('name', 'N/A')[:50]} (score: {cand.get('score', 'N/A')})")
            else:
                print(f"\n--- CANDIDATOS ALTERNATIVOS ---")
                print("❌ NO HAY")

            # Status
            print(f"\n--- ESTADO ---")
            print(f"Status clasificación: {acc_class.get('status', 'N/A')}")
            print(f"Clasificado en: {acc_class.get('classified_at', 'N/A')}")
            print(f"Confirmado en: {acc_class.get('confirmed_at', 'N/A')}")

        # Summary
        print(f"\n\n{'='*100}")
        print("RESUMEN")
        print(f"{'='*100}")

        total = len(invoices)
        with_classification = sum(1 for inv in invoices if inv.get('accounting_classification'))
        with_sat_name = sum(1 for inv in invoices if inv.get('accounting_classification', {}).get('sat_account_name'))
        with_metadata = sum(1 for inv in invoices if inv.get('accounting_classification', {}).get('metadata'))
        with_llm_raw = sum(1 for inv in invoices if inv.get('accounting_classification', {}).get('metadata', {}).get('llm_raw_response'))
        with_explanation_detail = sum(1 for inv in invoices if inv.get('accounting_classification', {}).get('explanation_detail'))
        with_model_version = sum(1 for inv in invoices if inv.get('accounting_classification', {}).get('model_version'))
        with_alternatives = sum(1 for inv in invoices if inv.get('accounting_classification', {}).get('alternative_candidates'))

        print(f"\nTotal facturas: {total}")
        print(f"Con clasificación: {with_classification} ({with_classification/total*100 if total > 0 else 0:.1f}%)")
        print(f"Con nombre SAT: {with_sat_name} ({with_sat_name/total*100 if total > 0 else 0:.1f}%)")
        print(f"Con metadata: {with_metadata} ({with_metadata/total*100 if total > 0 else 0:.1f}%)")
        print(f"Con respuesta LLM: {with_llm_raw} ({with_llm_raw/total*100 if total > 0 else 0:.1f}%)")
        print(f"Con explicación detallada: {with_explanation_detail} ({with_explanation_detail/total*100 if total > 0 else 0:.1f}%)")
        print(f"Con versión modelo: {with_model_version} ({with_model_version/total*100 if total > 0 else 0:.1f}%)")
        print(f"Con candidatos alternativos: {with_alternatives} ({with_alternatives/total*100 if total > 0 else 0:.1f}%)")

        print(f"\n{'='*100}")
        print("DIAGNÓSTICO")
        print(f"{'='*100}")

        if with_sat_name < total:
            print(f"\n❌ PROBLEMA: {total - with_sat_name} facturas sin nombre SAT oficial")
            print("   CAUSA: Campo 'sat_account_name' no se estaba guardando en DB")
            print("   FIX: Aplicado en universal_invoice_engine_system.py línea 1358")

        if with_llm_raw == 0 and with_classification > 0:
            print(f"\n❌ PROBLEMA: Ninguna factura tiene la respuesta LLM guardada")
            print("   CAUSA: Campo 'metadata' con 'llm_raw_response' no se estaba guardando")
            print("   FIX: Aplicado en universal_invoice_engine_system.py línea 1374")

        if with_explanation_detail < total:
            print(f"\n❌ PROBLEMA: {total - with_explanation_detail} facturas sin explicación detallada")
            print("   CAUSA: Campo 'explanation_detail' no se estaba guardando")
            print("   FIX: Aplicado en universal_invoice_engine_system.py línea 1370")

        print(f"\n{'='*100}")
        print("PRÓXIMOS PASOS")
        print(f"{'='*100}")
        print("\n1. ✅ Correcciones aplicadas al código")
        print("2. 🔄 Backend reiniciado con los cambios")
        print("3. 📤 Necesario: Subir nuevas facturas para probar el fix completo")
        print("4. ✓  Verificar que las nuevas facturas tengan:")
        print("     - Nombre SAT oficial")
        print("     - Metadata con respuesta LLM")
        print("     - Explicación detallada")
        print("     - Versión de modelo y prompt")
        print("     - Candidatos alternativos")

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--company-id', default='carreta_verde', help='Company ID')
    args = parser.parse_args()

    analyze_invoices(args.company_id)
