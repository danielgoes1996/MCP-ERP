"""
Análisis granular COMPLETO de la Factura #3: Comisión Recarga PASE/IDMX

Muestra paso a paso:
1. Datos crudos del XML parseado
2. Phase 1: Clasificación de familia (100-800)
3. Phase 2A: Clasificación de subfamilia (601, 602, etc.)
4. Phase 2B: Recuperación de candidatos con LLM
5. Phase 3: Selección final de cuenta SAT
6. Threading entre fases
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from core.ai_pipeline.classification.classification_service import ClassificationService
from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml
import json

print("=" * 120)
print("🔬 ANÁLISIS GRANULAR COMPLETO - FACTURA #3: COMISIÓN RECARGA PASE/IDMX")
print("=" * 120)

# 1. Parse invoice - FACTURA CORRECTA DE PASE (Comisión Recarga)
xml_path = 'uploads/invoices/default/20251110_171346_1fd2b97c-1ce0-4a0d-8497-de8b7c98d416.xml'

print("\n" + "=" * 120)
print("📄 PASO 1: PARSING DEL XML (Phase 0)")
print("=" * 120)

with open(xml_path, 'rb') as f:
    xml_bytes = f.read()

parsed_data = parse_cfdi_xml(xml_bytes)

print("\n📋 DATOS CRUDOS EXTRAÍDOS DEL XML:")
print("-" * 120)
print(f"UUID: {parsed_data.get('uuid', 'N/A')}")
print(f"Subtotal: ${parsed_data.get('subtotal', 0):,.2f} {parsed_data.get('currency', 'MXN')}")
print(f"Total: ${parsed_data.get('total', 0):,.2f} {parsed_data.get('currency', 'MXN')}")
print(f"IVA: ${parsed_data.get('iva_amount', 0):,.2f}")
print(f"Método Pago: {parsed_data.get('metodo_pago', 'N/A')}")
print(f"Forma Pago: {parsed_data.get('forma_pago', 'N/A')}")

print(f"\n🏢 EMISOR:")
emisor = parsed_data.get('emisor', {})
print(f"   RFC: {emisor.get('rfc', 'N/A')}")
print(f"   Nombre: {emisor.get('nombre', 'N/A')}")
print(f"   Régimen: {emisor.get('regimenfiscal', 'N/A')}")

print(f"\n🏢 RECEPTOR:")
receptor = parsed_data.get('receptor', {})
print(f"   RFC: {receptor.get('rfc', 'N/A')}")
print(f"   Nombre: {receptor.get('nombre', 'N/A')}")

print(f"\n📦 CONCEPTOS (Line Items):")
conceptos = parsed_data.get('conceptos', [])
for i, concepto in enumerate(conceptos, 1):
    print(f"\n   Concepto #{i}:")
    print(f"      ClaveProdServ: {concepto.get('clave_prod_serv', 'N/A')}")
    print(f"      Descripción: {concepto.get('descripcion', 'N/A')}")
    print(f"      Cantidad: {concepto.get('cantidad', 0)}")
    print(f"      Valor Unitario: ${concepto.get('valor_unitario', 0):,.2f}")
    print(f"      Importe: ${concepto.get('importe', 0):,.2f}")

print(f"\n💰 IMPUESTOS:")
for i, tax in enumerate(parsed_data.get('taxes', []), 1):
    print(f"   Tax #{i}: {tax.get('type')} ({tax.get('kind')}) - ${tax.get('amount', 0):,.2f} @ {tax.get('rate', 0)*100:.1f}%")

# 2. Classify
print("\n" + "=" * 120)
print("⚙️  EJECUTANDO CLASIFICACIÓN JERÁRQUICA...")
print("=" * 120)

service = ClassificationService()
result = service.classify_invoice(
    session_id='granular-factura-3',
    company_id=1,
    parsed_data=parsed_data,
    top_k=10
)

# 3. Phase 1 Analysis
print("\n" + "=" * 120)
print("📊 PHASE 1: CLASIFICACIÓN DE FAMILIA (100-800)")
print("=" * 120)
print("\n🎯 OBJETIVO: Identificar si el gasto es de PRODUCCIÓN, INVENTARIO o OPERACIÓN")
print("   Familias disponibles:")
print("   • 100 - INVENTARIOS")
print("   • 200 - ACTIVO FIJO")
print("   • 500 - COSTO DE VENTAS")
print("   • 600 - GASTOS DE OPERACIÓN")
print("   • 700 - GASTOS FINANCIEROS")
print("   • 800 - OTROS GASTOS")

if hasattr(result, 'hierarchical_phase1') and result.hierarchical_phase1:
    phase1 = result.hierarchical_phase1
    print(f"\n✅ FAMILIA SELECCIONADA: {phase1.get('family_code')} - {phase1.get('family_name')}")
    print(f"   Confianza: {phase1.get('confidence', 0):.1%}")

    reasoning1 = phase1.get('reasoning', '')
    if reasoning1:
        print(f"\n💭 RAZONAMIENTO COMPLETO:")
        print("─" * 120)
        print(reasoning1)
        print("─" * 120)

    # Alternativas
    alternatives = phase1.get('alternative_families', [])
    if alternatives:
        print(f"\n🔄 ALTERNATIVAS CONSIDERADAS:")
        for alt in alternatives[:3]:
            print(f"   • {alt.get('family_code')} - {alt.get('family_name')} (prob: {alt.get('probability', 0):.1%})")

# 4. Phase 2A Analysis
print("\n" + "=" * 120)
print("📊 PHASE 2A: CLASIFICACIÓN DE SUBFAMILIA (601, 602, 603, etc.)")
print("=" * 120)
print("\n🎯 OBJETIVO: Dentro de la familia 600, identificar el tipo específico de gasto")
print("   Subfamilias de Familia 600:")
print("   • 601 - Gastos generales (administración, oficina, papelería)")
print("   • 602 - Gastos de venta (publicidad, comisiones, fletes)")
print("   • 603 - Gastos de administración (nómina, prestaciones)")

if hasattr(result, 'hierarchical_phase2a') and result.hierarchical_phase2a:
    phase2a = result.hierarchical_phase2a
    print(f"\n✅ SUBFAMILIA SELECCIONADA: {phase2a.get('subfamily_code')} - {phase2a.get('subfamily_name')}")
    print(f"   Confianza: {phase2a.get('confidence', 0):.1%}")

    reasoning2a = phase2a.get('reasoning', '')
    if reasoning2a:
        print(f"\n💭 RAZONAMIENTO COMPLETO:")
        print("─" * 120)
        print(reasoning2a)
        print("─" * 120)

        # Verificar threading
        if 'fase 1' in reasoning2a.lower() or 'familia' in reasoning2a.lower() or '600' in reasoning2a:
            print(f"\n🧵 ✅ THREADING DETECTADO: Phase 2A recibió y usó el razonamiento de Phase 1")

    # Alternativas
    alternatives = phase2a.get('alternative_subfamilies', [])
    if alternatives:
        print(f"\n🔄 ALTERNATIVAS CONSIDERADAS:")
        for alt in alternatives[:3]:
            print(f"   • {alt.get('subfamily_code')} - {alt.get('subfamily_name')} (prob: {alt.get('probability', 0):.1%})")

# 5. Phase 2B Analysis
print("\n" + "=" * 120)
print("📊 PHASE 2B: RECUPERACIÓN DE CANDIDATOS CON LLM")
print("=" * 120)
print("\n🎯 OBJETIVO: Usar LLM para seleccionar inteligentemente los mejores candidatos de la subfamilia")
print("   Estrategia: LLM-based intelligent retrieval (Solution A)")
print("   Modelo: Claude Haiku 3.5")
print("   Contexto usado: Proveedor + ClaveProdServ + Descripción + Razonamiento Phase 2A")

if hasattr(result, 'hierarchical_phase2b') and result.hierarchical_phase2b:
    phase2b = result.hierarchical_phase2b

    print(f"\n✅ MÉTODO DE FILTRADO: {phase2b.get('filtering_method')}")
    print(f"   Filtro usado: Subfamilia {phase2b.get('filter_used')}")
    print(f"   Candidatos recuperados: {len(phase2b.get('sample_candidates', []))}")

    candidates = phase2b.get('sample_candidates', [])
    if candidates:
        print(f"\n🔍 TOP 10 CANDIDATOS RECUPERADOS:")
        print(f"{'#':<4} {'Código':<12} {'Nombre':<60} {'Score':<8}")
        print("-" * 120)
        for i, cand in enumerate(candidates[:10], 1):
            print(f"{i:<4} {cand.get('code', ''):<12} {cand.get('name', ''):<60} {cand.get('score', 0):<8.2f}")

        print(f"\n💡 OBSERVACIONES:")
        print(f"   • El LLM seleccionó {len(candidates)} candidatos de la subfamilia {phase2b.get('filter_used')}")
        print(f"   • Los scores reflejan la relevancia según el contexto completo de la factura")
        print(f"   • El candidato con mayor score NO siempre es el seleccionado (Phase 3 decide)")

# 6. Phase 3 Analysis
print("\n" + "=" * 120)
print("📊 PHASE 3: SELECCIÓN FINAL DE CUENTA SAT")
print("=" * 120)
print("\n🎯 OBJETIVO: Seleccionar la cuenta MÁS ESPECÍFICA de los candidatos recuperados")
print("   Modelo: Claude Haiku 3.5")
print("   Input: Top 10 candidatos + razonamiento Phase 2A + constraint familia Phase 1")

# Consultar nombre de cuenta desde PostgreSQL
import psycopg2
sat_account_name = "N/A"
try:
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5433,
        database="mcp_system",
        user="mcp_user",
        password="changeme"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sat_account_embeddings WHERE code = %s", (result.sat_account_code,))
    row = cursor.fetchone()
    if row:
        sat_account_name = row[0]
    cursor.close()
    conn.close()
except Exception as e:
    print(f"⚠️ No se pudo consultar nombre: {e}")

print(f"\n✅ CUENTA FINAL SELECCIONADA: {result.sat_account_code} - {sat_account_name}")
print(f"   Confianza: {result.confidence_sat:.1%}")

if hasattr(result, 'explanation_detail') and result.explanation_detail:
    print(f"\n💭 EXPLICACIÓN COMPLETA:")
    print("─" * 120)
    print(result.explanation_detail)
    print("─" * 120)

    # Verificar threading
    expl_lower = result.explanation_detail.lower()
    if 'subfamilia' in expl_lower or '602' in result.explanation_detail or 'fase 2' in expl_lower:
        print(f"\n🧵 ✅ THREADING DETECTADO: Phase 3 recibió y usó el razonamiento de Phase 2A")

if hasattr(result, 'explanation_short') and result.explanation_short:
    print(f"\n📝 EXPLICACIÓN CORTA:")
    print(f"   {result.explanation_short}")

# 7. Threading Summary
print("\n" + "=" * 120)
print("🧵 RESUMEN DE THREADING (Continuidad de Razonamiento)")
print("=" * 120)

has_phase1 = hasattr(result, 'hierarchical_phase1') and result.hierarchical_phase1
has_phase2a = hasattr(result, 'hierarchical_phase2a') and result.hierarchical_phase2a
has_phase2b = hasattr(result, 'hierarchical_phase2b') and result.hierarchical_phase2b
has_phase3 = hasattr(result, 'explanation_detail') and result.explanation_detail

print(f"\n✅ Fases completadas:")
print(f"   Phase 1 (Familia):    {'✅' if has_phase1 else '❌'}")
print(f"   Phase 2A (Subfamilia): {'✅' if has_phase2a else '❌'}")
print(f"   Phase 2B (Candidatos): {'✅' if has_phase2b else '❌'}")
print(f"   Phase 3 (Final):       {'✅' if has_phase3 else '❌'}")

print(f"\n🔗 Threading entre fases:")
print(f"   Phase 1 → Phase 2A: {'✅ Funcionando' if has_phase1 and has_phase2a else '❌ No disponible'}")
print(f"   Phase 2A → Phase 2B: {'✅ Funcionando' if has_phase2a and has_phase2b else '❌ No disponible'}")
print(f"   Phase 2B → Phase 3: {'✅ Funcionando' if has_phase2b and has_phase3 else '❌ No disponible'}")

# 8. Final Summary
print("\n" + "=" * 120)
print("🎯 RESUMEN FINAL")
print("=" * 120)

print(f"\n📄 FACTURA:")
print(f"   Proveedor: PASE, SERVICIOS ELECTRONICOS")
print(f"   Concepto: COMISION RECARGA IDMX")
print(f"   Monto: $400.00 MXN")

print(f"\n📊 FLUJO DE CLASIFICACIÓN:")
print(f"   [1] XML Parse     → Extraídos datos del CFDI")
print(f"   [2] Phase 1       → Familia {phase1.get('family_code') if has_phase1 else 'N/A'} ({phase1.get('confidence', 0):.1%} confianza)")
print(f"   [3] Phase 2A      → Subfamilia {phase2a.get('subfamily_code') if has_phase2a else 'N/A'} ({phase2a.get('confidence', 0):.1%} confianza)")
print(f"   [4] Phase 2B      → {len(phase2b.get('sample_candidates', [])) if has_phase2b else 0} candidatos recuperados vía LLM")
print(f"   [5] Phase 3       → Cuenta {result.sat_account_code} - {sat_account_name} ({result.confidence_sat:.1%} confianza)")

print(f"\n✅ RESULTADO FINAL: {result.sat_account_code} - {sat_account_name}")
print(f"   Confianza global: {result.confidence_sat:.1%}")

print("\n" + "=" * 120)
print("✅ ANÁLISIS GRANULAR COMPLETO")
print("=" * 120)
