#!/usr/bin/env python3
"""Inspect detailed invoice information from XMLs."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml

# Factura 1: DISTRIBUIDORA PREZ
with open('/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171337_37be3d46-8f2d-11f0-87ec-59c2dcfb9125.xml', 'rb') as f:
    data1 = parse_cfdi_xml(f.read())

print('='*100)
print('FACTURA #1: DISTRIBUIDORA PREZ')
print('='*100)
print(f"Proveedor: {data1.get('emisor', {}).get('nombre')}")
print(f"RFC: {data1.get('emisor', {}).get('rfc')}")
print(f"Régimen fiscal: {data1.get('emisor', {}).get('regimen_fiscal', 'N/A')}")
print(f"\nConcepto: {data1.get('conceptos', [{}])[0].get('descripcion')}")
print(f"Unidad: {data1.get('conceptos', [{}])[0].get('unidad', 'N/A')}")
print(f"Cantidad: {data1.get('conceptos', [{}])[0].get('cantidad', 'N/A')}")
print(f"Precio unitario: ${data1.get('conceptos', [{}])[0].get('valor_unitario', 0):,.2f}")
print(f"ClaveProdServ: {data1.get('conceptos', [{}])[0].get('clave_prod_serv')}")
print(f"\nMétodo pago: {data1.get('metodo_pago', 'N/A')}")
print(f"Forma pago: {data1.get('forma_pago', 'N/A')}")
print(f"Condiciones pago: {data1.get('condiciones_pago', 'N/A')}")
print(f"\nSubtotal: ${data1.get('subtotal', 0):,.2f}")
print(f"IVA: ${data1.get('total_impuestos_trasladados', 0):,.2f}")
print(f"Total: ${data1.get('total', 0):,.2f}")

# Check if it's PPD or PUE
print(f"\n💡 ANÁLISIS:")
metodo_pago_1 = data1.get('metodo_pago', '')
if metodo_pago_1 == 'PPD':
    print("   ⚠️  PAGO EN PARCIALIDADES O DIFERIDO (PPD)")
    print("   → Esto indica que es un ANTICIPO o pago futuro")
elif metodo_pago_1 == 'PUE':
    print("   ✅ PAGO EN UNA SOLA EXHIBICIÓN (PUE)")
    print("   → El pago se realiza de contado")

# Factura 2: GARIN ETIQUETAS
with open('/Users/danielgoes96/Desktop/mcp-server/uploads/invoices/default/20251110_171357_4ded7350-e382-46d5-814b-ed59e55f441c.xml', 'rb') as f:
    data2 = parse_cfdi_xml(f.read())

print('\n' + '='*100)
print('FACTURA #2: GARIN ETIQUETAS')
print('='*100)
print(f"Proveedor: {data2.get('emisor', {}).get('nombre')}")
print(f"RFC: {data2.get('emisor', {}).get('rfc')}")
print(f"Régimen fiscal: {data2.get('emisor', {}).get('regimen_fiscal', 'N/A')}")
print(f"\nConcepto: {data2.get('conceptos', [{}])[0].get('descripcion')}")
print(f"Unidad: {data2.get('conceptos', [{}])[0].get('unidad', 'N/A')}")
print(f"Cantidad: {data2.get('conceptos', [{}])[0].get('cantidad', 'N/A')}")
print(f"Precio unitario: ${data2.get('conceptos', [{}])[0].get('valor_unitario', 0):,.2f}")
print(f"ClaveProdServ: {data2.get('conceptos', [{}])[0].get('clave_prod_serv')}")
print(f"\nMétodo pago: {data2.get('metodo_pago', 'N/A')}")
print(f"Forma pago: {data2.get('forma_pago', 'N/A')}")
print(f"Condiciones pago: {data2.get('condiciones_pago', 'N/A')}")
print(f"\nSubtotal: ${data2.get('subtotal', 0):,.2f}")
print(f"IVA: ${data2.get('total_impuestos_trasladados', 0):,.2f}")
print(f"Total: ${data2.get('total', 0):,.2f}")

# Check if it's PPD or PUE
print(f"\n💡 ANÁLISIS:")
metodo_pago_2 = data2.get('metodo_pago', '')
if metodo_pago_2 == 'PPD':
    print("   ⚠️  PAGO EN PARCIALIDADES O DIFERIDO (PPD)")
    print("   → Esto indica que es un ANTICIPO o pago futuro")
    print("   → CLASIFICACIÓN 120 (Anticipo a proveedores) SERÍA CORRECTA ✅")
elif metodo_pago_2 == 'PUE':
    print("   ✅ PAGO EN UNA SOLA EXHIBICIÓN (PUE)")
    print("   → El pago se realiza de contado")
    print("   → CLASIFICACIÓN 120 (Anticipo) SERÍA INCORRECTA ❌")

# Comparison
print('\n' + '='*100)
print('📊 COMPARACIÓN Y CLASIFICACIÓN CORRECTA')
print('='*100)

print("\n🏭 FACTURA #1: DISTRIBUIDORA PREZ - '16 OZ. W/M LABEL PANEL'")
print("   Producto: Paneles de etiquetas para ENVASES de 16 oz")
print("   ClaveProdServ: 24122003")
if metodo_pago_1 == 'PPD':
    print("   ✅ Si es PPD → 120 (Anticipo a proveedores) es correcto")
    print("   ❌ Si es PUE → 115 (Inventario) o 164.01 (Moldes/herramental) sería correcto")
else:
    print("   ✅ Como es PUE → 115 (Inventario) o 164.01 podría ser correcto")

print("\n🏭 FACTURA #2: GARIN ETIQUETAS - 'ETQ. DIGITAL BOPP TRANSPARENTE'")
print("   Producto: Etiquetas digitales para productos")
print("   ClaveProdServ: 55121600")
if metodo_pago_2 == 'PPD':
    print("   ✅ Si es PPD → 120 (Anticipo a proveedores) ES CORRECTO")
    print("   → El sistema clasificó correctamente basándose en método de pago")
else:
    print("   ❌ Si es PUE → 120 (Anticipo) es INCORRECTO")
    print("   → Debería ser 115 (Inventario)")
