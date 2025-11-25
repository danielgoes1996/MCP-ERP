#!/usr/bin/env python3
"""
Trace detallado de las 5 facturas nuevas para entender el razonamiento del LLM en cada fase.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_pipeline.classification.classification_service import ClassificationService
from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml
from core.shared.db_config import get_connection


def get_account_name(code: str) -> str:
    """Fetch account name from database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sat_account_embeddings WHERE code = %s LIMIT 1",
            (code,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else 'N/A'
    except Exception as e:
        return f'Error: {e}'


def trace_invoice(xml_path: str, invoice_num: int, description: str):
    """Trace classification for a single invoice with full reasoning."""

    print(f"\n{'='*100}")
    print(f"FACTURA #{invoice_num}: {description}")
    print(f"{'='*100}")

    # Parse XML
    try:
        with open(xml_path, 'rb') as f:
            xml_bytes = f.read()
    except FileNotFoundError:
        print(f"❌ Archivo no encontrado: {xml_path}")
        return

    parsed_data = parse_cfdi_xml(xml_bytes)

    # Display invoice data
    emisor = parsed_data.get('emisor', {})
    receptor = parsed_data.get('receptor', {})
    conceptos = parsed_data.get('conceptos', [{}])
    concepto = conceptos[0] if conceptos else {}

    print(f"\n📋 DATOS DE LA FACTURA:")
    print(f"   Proveedor: {emisor.get('nombre', 'N/A')}")
    print(f"   RFC: {emisor.get('rfc', 'N/A')}")
    print(f"   Concepto: {concepto.get('descripcion', 'N/A')[:80]}")
    print(f"   Monto: ${parsed_data.get('total', 0):,.2f} MXN")
    print(f"   Método pago: {parsed_data.get('metodo_pago', 'N/A')}")
    print(f"   Forma pago: {parsed_data.get('forma_pago', 'N/A')}")
    print(f"   UsoCFDI: {receptor.get('uso_cfdi', 'N/A')}")
    print(f"   ClaveProdServ: {concepto.get('clave_prod_serv', 'N/A')}")

    # Classify
    service = ClassificationService()

    try:
        result = service.classify_invoice(
            session_id=f"trace-{invoice_num:03d}",
            company_id=1,
            parsed_data=parsed_data,
            top_k=10
        )

        if not result:
            print(f"\n❌ Clasificación falló")
            return

        # Display hierarchy
        print(f"\n🎯 RESULTADO FINAL:")
        print(f"   Cuenta: {result.sat_account_code} - {get_account_name(result.sat_account_code)}")
        print(f"   Confianza: {result.confidence_sat:.2%}")

        print(f"\n📊 JERARQUÍA COMPLETA:")

        # PHASE 1: Family
        if hasattr(result, 'hierarchical_phase1') and result.hierarchical_phase1:
            phase1 = result.hierarchical_phase1
            familia = phase1.get('family_code', '?')
            familia_nombre = phase1.get('family_name', '?')
            familia_conf = phase1.get('confidence', 0)

            print(f"\n   ├─ FASE 1 (Familia): {familia} - {familia_nombre} ({familia_conf:.2%})")

            if phase1.get('reasoning'):
                print(f"      💭 Razonamiento: {phase1.get('reasoning')[:200]}...")

        # PHASE 2A: Subfamily
        if hasattr(result, 'hierarchical_phase2a') and result.hierarchical_phase2a:
            phase2a = result.hierarchical_phase2a
            subfamilia = phase2a.get('subfamily_code', '?')
            subfamilia_nombre = phase2a.get('subfamily_name', '?')
            subfamilia_conf = phase2a.get('subfamily_confidence', 0)

            print(f"\n   ├─ FASE 2A (Subfamilia): {subfamilia} - {subfamilia_nombre} ({subfamilia_conf:.2%})")

            if phase2a.get('reasoning'):
                print(f"      💭 Razonamiento: {phase2a.get('reasoning')[:200]}...")

            # Show alternatives considered
            alternatives = phase2a.get('alternative_subfamilies', [])
            if alternatives:
                print(f"      🔄 Alternativas consideradas:")
                for alt in alternatives[:3]:
                    print(f"         • {alt.get('code')} - {alt.get('name')} "
                          f"(prob: {alt.get('probability', 0):.1%})")

        # PHASE 2B: Embedding search
        if hasattr(result, 'hierarchical_phase2b') and result.hierarchical_phase2b:
            phase2b = result.hierarchical_phase2b

            print(f"\n   ├─ FASE 2B (Búsqueda embeddings):")
            print(f"      Método filtrado: {phase2b.get('filtering_method', 'N/A')}")
            print(f"      Filtro usado: {phase2b.get('filter_used', 'N/A')}")
            print(f"      Candidatos recuperados: {phase2b.get('candidates_filtered', 0)}")

            # Use 'sample_candidates' not 'top_candidates'
            candidates = phase2b.get('sample_candidates', [])
            if candidates:
                print(f"      🔍 Top candidatos recuperados:")
                for i, cand in enumerate(candidates, 1):
                    code = cand.get('code', '?')
                    name = cand.get('name', '?')[:50]
                    score = cand.get('score', 0)
                    print(f"         {i}. {code:<10} {name}")
                    print(f"            Score: {score:.4f}")
            else:
                print(f"      ⚠️  NO se recuperaron candidatos de embeddings")

        # PHASE 3: Specific account selection
        print(f"\n   └─ FASE 3 (Cuenta específica): {result.sat_account_code}")

        if hasattr(result, 'hierarchical_phase3') and result.hierarchical_phase3:
            phase3 = result.hierarchical_phase3

            if phase3.get('reasoning'):
                print(f"      💭 Razonamiento: {phase3.get('reasoning')[:200]}...")

        # Validation
        print(f"\n✅ VALIDACIÓN:")
        cuenta_familia = result.sat_account_code[0] + "00" if result.sat_account_code else '?'

        if hasattr(result, 'hierarchical_phase1') and result.hierarchical_phase1:
            familia = result.hierarchical_phase1.get('family_code', '?')
            if cuenta_familia == familia:
                print(f"   ✅ Jerarquía consistente")
            else:
                print(f"   ⚠️  Inconsistencia: Familia {familia} pero cuenta {result.sat_account_code}")

        # Check if classification makes sense
        print(f"\n💡 ANÁLISIS:")
        account_name = get_account_name(result.sat_account_code)
        print(f"   Clasificado como: {result.sat_account_code} - {account_name}")
        print(f"   Concepto factura: {concepto.get('descripcion', 'N/A')[:80]}")

        # Check if it makes sense
        concepto_desc = concepto.get('descripcion', '').lower()
        account_name_lower = account_name.lower()

        # Simple heuristics
        if 'amazon' in concepto_desc and 'almacenamiento' in concepto_desc:
            if 'patente' in account_name_lower or 'marca' in account_name_lower:
                print(f"   ❌ CLASIFICACIÓN INCORRECTA: Almacenamiento Amazon → Patentes y marcas")
                print(f"   ✅ DEBERÍA SER: 602.84 (Fletes y acarreos) o similar")

        if 'odoo' in concepto_desc or 'software' in concepto_desc:
            if 'patente' in account_name_lower or 'marca' in account_name_lower:
                print(f"   ❌ CLASIFICACIÓN INCORRECTA: Software → Patentes y marcas")
                print(f"   ✅ DEBERÍA SER: 601.83 (Gastos de instalación) o similar")

        if 'comision' in concepto_desc or 'recarga' in concepto_desc:
            if 'patente' in account_name_lower or 'marca' in account_name_lower:
                print(f"   ❌ CLASIFICACIÓN INCORRECTA: Comisión → Patentes y marcas")

        if 'afinacion' in concepto_desc or 'motor' in concepto_desc or 'vehiculo' in concepto_desc:
            if 'combustible' in account_name_lower or 'lubricante' in account_name_lower:
                print(f"   ✅ CLASIFICACIÓN RAZONABLE (mantenimiento vehículo)")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("\n" + "="*100)
    print("TRACE DETALLADO - 5 FACTURAS NUEVAS")
    print("="*100)

    # Test cases
    invoices = [
        {
            'path': '/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_153628_60a9d3e4-2f35-11f0-af84-b1cfc01deddb.xml',
            'desc': 'Amazon Storage'
        },
        {
            'path': '/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171342_7fa003f7-9fe8-459f-809b-0ea3bbfe5401.xml',
            'desc': 'Odoo Software'
        },
        {
            'path': '/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171346_1fd2b97c-1ce0-4a0d-8497-de8b7c98d416.xml',
            'desc': 'Comisión Recarga'
        },
        {
            'path': '/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171350_aaa18285-8601-41b7-a08a-38d64eafd492.xml',
            'desc': 'Afinación Motor'
        },
        {
            'path': '/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171406_c38ac70f-9bc5-11f0-84cb-ed22a95b5aec.xml',
            'desc': 'Amazon Prolonged Storage'
        },
    ]

    for i, invoice in enumerate(invoices, 1):
        trace_invoice(invoice['path'], i, invoice['desc'])

    print("\n" + "="*100)
    print("FIN DEL TRACE")
    print("="*100 + "\n")


if __name__ == '__main__':
    main()
