#!/usr/bin/env python3
"""
Analyze a sample of invoices to see what providers we have.
This helps identify diverse test cases for classification.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

# Sample invoice files
INVOICE_FILES = [
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171358_a27b580a-cb31-5060-90e6-c3af6c7f2f35.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171354_5097cf95-278a-404c-83fb-80782dd1d36c.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171337_37be3d46-8f2d-11f0-87ec-59c2dcfb9125.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171405_f0c96e92-c13c-49b2-9dbd-f17f06ba07d1.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171402_522a1f68-90c3-11f0-ab6e-5715480b719a.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171357_4ded7350-e382-46d5-814b-ed59e55f441c.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/carreta_verde/20251110_221643_bd56661a-4d1b-4915-9303-c18fed78fa64.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/carreta_verde/20251110_223035_c84300b0-56bf-4418-9f0a-6fdc446f1295.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/carreta_verde/20251110_220914_0470d70c-f03f-4a2b-ad58-078c84508e6c.xml",
    "/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/carreta_verde/20251112_231848_c40ca329-4e4d-4a3a-8849-7ee80a806ca3.xml",
]

def parse_invoice_quick(file_path: str):
    """Quick parse to extract provider info."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # CFDI namespace
        ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4',
              'cfdi3': 'http://www.sat.gob.mx/cfd/3'}

        # Try CFDI 4.0
        emisor = root.find('.//cfdi:Emisor', ns)
        receptor = root.find('.//cfdi:Receptor', ns)
        conceptos = root.findall('.//cfdi:Concepto', ns)

        # Fallback to CFDI 3.3
        if emisor is None:
            emisor = root.find('.//cfdi3:Emisor', ns)
            receptor = root.find('.//cfdi3:Receptor', ns)
            conceptos = root.findall('.//cfdi3:Concepto', ns)

        if emisor is None:
            return None

        provider_name = emisor.get('Nombre', 'N/A')
        provider_rfc = emisor.get('Rfc', 'N/A')

        # Get first concepto description
        description = 'N/A'
        clave_prod_serv = 'N/A'
        if conceptos:
            concepto = conceptos[0]
            description = concepto.get('Descripcion', 'N/A')
            clave_prod_serv = concepto.get('ClaveProdServ', 'N/A')

        # Get total
        total = root.get('Total', '0.00')

        return {
            'file': Path(file_path).name,
            'provider_name': provider_name,
            'provider_rfc': provider_rfc,
            'description': description[:80],  # Truncate
            'clave_prod_serv': clave_prod_serv,
            'total': total
        }
    except Exception as e:
        return {
            'file': Path(file_path).name,
            'error': str(e)
        }

if __name__ == "__main__":
    print("=" * 100)
    print("📋 ANALYZING SAMPLE INVOICES")
    print("=" * 100)

    invoices_data = []

    for i, file_path in enumerate(INVOICE_FILES, 1):
        print(f"\n{i}. Parsing: {Path(file_path).name}")
        data = parse_invoice_quick(file_path)

        if data and 'error' not in data:
            invoices_data.append(data)
            print(f"   Provider: {data['provider_name']}")
            print(f"   RFC: {data['provider_rfc']}")
            print(f"   Description: {data['description']}")
            print(f"   Clave: {data['clave_prod_serv']}")
            print(f"   Total: ${data['total']} MXN")
        else:
            print(f"   ❌ Error: {data.get('error', 'Unknown error')}")

    print("\n" + "=" * 100)
    print(f"📊 SUMMARY - Found {len(invoices_data)} valid invoices")
    print("=" * 100)

    # Group by provider
    providers = {}
    for inv in invoices_data:
        rfc = inv['provider_rfc']
        if rfc not in providers:
            providers[rfc] = {
                'name': inv['provider_name'],
                'count': 0,
                'samples': []
            }
        providers[rfc]['count'] += 1
        providers[rfc]['samples'].append({
            'file': inv['file'],
            'description': inv['description']
        })

    print(f"\n🏢 Unique Providers: {len(providers)}")
    print("=" * 100)

    for rfc, info in providers.items():
        print(f"\n{info['name']} ({rfc})")
        print(f"   Count: {info['count']} invoices")
        for sample in info['samples'][:2]:  # Show max 2 samples
            print(f"   - {sample['description'][:60]}...")

    print("\n" + "=" * 100)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 100)

    print("\n💡 Next Steps:")
    print("1. Review the providers above")
    print("2. Select diverse providers for testing (FINKOK, logistics, services, etc.)")
    print("3. Run: python3 test_batch_classification.py")
