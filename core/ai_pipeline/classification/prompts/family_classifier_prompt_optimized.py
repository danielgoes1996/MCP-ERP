"""
Optimized family-level classifier prompt (reduced from ~6,051 to ~2,900 tokens).

Key optimizations:
- Condensed plan contable descriptions (8 families → compact format)
- Reduced from 3 examples to 1 critical example (NIF C-4 inventory case)
- Eliminated redundant explanations
- Kept core methodology intact
- Maintained accuracy while reducing tokens by ~52%
"""

from typing import Dict, Optional, List


def build_family_classification_prompt_optimized(
    invoice_data: Dict,
    company_context: Optional[Dict] = None,
    few_shot_examples: Optional[List[Dict]] = None,
) -> str:
    """
    Build optimized prompt for family-level classification (100-800).

    Reduced from ~6,051 tokens to ~2,900 tokens (~52% reduction).
    """

    # Extract invoice fields
    descripcion = invoice_data.get('descripcion', 'N/A')
    proveedor = invoice_data.get('proveedor', 'N/A')
    rfc_proveedor = invoice_data.get('rfc_proveedor', 'N/A')
    clave_prod_serv = invoice_data.get('clave_prod_serv', 'N/A')
    monto = invoice_data.get('monto', 0.0)
    uso_cfdi = invoice_data.get('uso_cfdi', 'N/A')
    receptor_nombre = invoice_data.get('receptor_nombre', 'N/A')
    receptor_rfc = invoice_data.get('receptor_rfc', 'N/A')
    emisor_nombre = invoice_data.get('emisor_nombre', proveedor)
    emisor_rfc = invoice_data.get('emisor_rfc', rfc_proveedor)

    # Build company context block (compact)
    context_block = ""
    threshold_text = ""
    cogs_text = ""
    opex_text = ""
    sales_text = ""

    if company_context:
        industry = company_context.get('industry_description', company_context.get('industry', 'N/A'))
        business_model = company_context.get('business_model_description', company_context.get('business_model', 'N/A'))
        context_block = f"\nCONTEXTO EMPRESA: {industry} | {business_model}"

        # Capitalization threshold
        threshold = company_context.get('capitalization_threshold_mxn')
        if threshold:
            threshold_text = f"\nUMBRAL CAPITALIZACIÓN: ${threshold:,.0f} MXN (NIF C-6: Activos >umbral → capitalizan en 181, <umbral → gastos en 600)"

        # COGS definition
        cogs_def = company_context.get('cogs_definition')
        if cogs_def:
            cogs_text = f"\nCOGS (500): {cogs_def}"

        # Operating expenses definition
        opex_def = company_context.get('operating_expenses_definition')
        if opex_def:
            opex_text = f"\nGASTOS OPERATIVOS (600): {opex_def}"

        # Sales expenses definition
        sales_def = company_context.get('sales_expenses_definition')
        if sales_def:
            sales_text = f"\nGASTOS VENTA (600-610): {sales_def}"

        context_block += threshold_text + cogs_text + opex_text + sales_text

    # Build few-shot examples block
    few_shot_block = ""
    if few_shot_examples:
        from core.shared.company_context import format_family_examples_for_prompt
        few_shot_block = "\n" + format_family_examples_for_prompt(few_shot_examples)

    prompt = f"""Eres un contador experto mexicano. Clasifica esta factura a NIVEL DE FAMILIA (100-800) del Código Agrupador SAT.

FACTURA:
- Descripción: {descripcion}
- Proveedor: {proveedor} (RFC: {rfc_proveedor})
- Clave SAT: {clave_prod_serv} | Monto: ${monto:,.2f} MXN | UsoCFDI: {uso_cfdi}
- Emisor: {emisor_nombre} ({emisor_rfc}) → Receptor: {receptor_nombre} ({receptor_rfc})
{context_block}{few_shot_block}

FAMILIAS SAT (100-800):

100 ACTIVO - Bienes/derechos. Inventarios, maquinaria, equipo, vehículos, terrenos. INVERSIONES capitalizables.
200 PASIVO - Deudas/obligaciones. Proveedores por pagar, préstamos, nómina pendiente, impuestos por pagar.
300 CAPITAL - Aportaciones de socios y resultados acumulados.
400 INGRESOS - Ventas y otros ingresos. Ventas de productos, servicios, ingresos financieros.
500 COSTO DE VENTAS - Costo directo de producir/adquirir lo vendido. Materia prima, mano de obra directa.
600 GASTOS OPERACIÓN - Gastos para operar (NO producción). Renta, luz, teléfono, honorarios, publicidad.
700 GASTOS FINANCIEROS - Costos de financiamiento. Intereses, comisiones bancarias, pérdidas cambiarias.
800 OTROS INGRESOS/GASTOS - Partidas extraordinarias no recurrentes.

METODOLOGÍA:

PASO 0 - DIRECCIÓN FACTURA (CRÍTICO):
• RECIBIDA (Receptor=tu empresa): Materiales → 115 INVENTARIO primero (NIF C-4), luego → 500 al USAR
• EMITIDA (Emisor=tu empresa): Ventas → 400 INGRESOS + 500 COSTO VENTAS

PASO 1 - ANÁLISIS SEMÁNTICO:
¿Bien tangible, servicio, o inversión? ¿Material de producción o insumo operativo?

PASO 2 - CONTEXTO EMPRESARIAL:
¿Cómo se usa en el modelo de negocio de esta empresa?
Ejemplo: "Etiquetas" para SOFTWARE → 600 | para PRODUCCIÓN → 115 Inventario (compra) o 500 (uso)

PASO 3 - DETERMINACIÓN:
• 100 ACTIVO: Inversión capitalizable (>$5K, vida útil >1 año NIF C-6) O materiales comprados (115 Inventario)
• 500 COSTO: Material que se integra físicamente al producto vendido
• 600 GASTOS: Necesario para operar pero NO se integra al producto
• 700 FINANCIEROS: Intereses, comisiones bancarias

PASO 4 - VALIDACIÓN USOCFDI (SECUNDARIO):
G01 → SUGIERE 500 o 115 | G03 → SUGIERE 600 | I01-I08 → SUGIERE 100
Si tu análisis contradice UsoCFDI, CONFÍA EN TU ANÁLISIS (proveedores se equivocan).

EJEMPLO CRÍTICO (NIF C-4):

FACTURA:
- Descripción: "ETIQUETAS ADHESIVAS PARA ENVASES MIEL 500ML, IMPRESIÓN COLOR"
- Proveedor: GARIN ETIQUETAS SA (RFC: GET130827SN7)
- Clave SAT: 55121604 | Monto: $3,450 MXN | UsoCFDI: G03
- Emisor: GARIN ETIQUETAS → Receptor: POLLENBEEMX (tu empresa)

CONTEXTO: Producción y comercialización de miel

RAZONAMIENTO:
PASO 0: Receptor=POLLENBEEMX → FACTURA RECIBIDA (compra). Material producción → 115 INVENTARIO (NO 500)
PASO 1: Etiquetas físicas "PARA ENVASES MIEL 500ML" → material empaque
PASO 2: Industria PRODUCCIÓN MIEL (no oficina). Etiquetas se adhieren al producto final.
PASO 3: NO es 600 (no es papelería oficina). NO es 500 (esto es COMPRA, no USO). SÍ es 115 INVENTARIO:
  - FACTURA RECIBIDA (compra proveedor)
  - Se almacena hasta uso
  - NIF C-4: Compras materiales → Inventario, luego Costo Ventas cuando se USAN
PASO 4: UsoCFDI=G03 CONTRADICE. Debió ser G01. OVERRIDE correcto.

RESPUESTA:
{{
  "familia_codigo": "100",
  "familia_nombre": "ACTIVO",
  "confianza": 0.98,
  "razonamiento": "FACTURA RECIBIDA de material producción. NIF C-4: compras materiales → Inventario (115) al comprar, Costo Ventas (500) al usar.",
  "factores_decision": [
    "FACTURA RECIBIDA: Receptor=tu empresa = COMPRA",
    "Material empaque producción",
    "NIF C-4: Compras → Inventario (115) primero",
    "Proveedor GET130827SN7 = packaging_materials"
  ],
  "uso_cfdi_analisis": "UsoCFDI=G03 incorrecto. Debió ser G01 (materiales).",
  "override_uso_cfdi": true,
  "override_razon": "Dirección factura + contexto empresarial > UsoCFDI. Materiales comprados → Inventario (115), luego Costo Ventas cuando se usan.",
  "familias_alternativas": [],
  "requiere_revision_humana": false,
  "siguiente_fase": "subfamily",
  "comentarios_adicionales": "Material de producción que forma parte del inventario de materiales."
}}

FORMATO RESPUESTA (JSON):

{{
  "familia_codigo": "XXX",  // 100, 200, 300, 400, 500, 600, 700, 800
  "familia_nombre": "NOMBRE FAMILIA",
  "confianza": 0.XX,  // 0.0-1.0 (>=0.95 auto-aprobar)
  "razonamiento": "REQUERIDO: 1-2 oraciones explicando POR QUÉ esta familia (NUNCA dejar vacío, SIEMPRE explicar tu decisión)",
  "factores_decision": ["Factor 1", "Factor 2", "Factor 3"],
  "uso_cfdi_analisis": "¿Coincide o contradice UsoCFDI? ¿Por qué?",
  "override_uso_cfdi": true/false,
  "override_razon": "Por qué se ignora UsoCFDI" o null,
  "familias_alternativas": [{{"codigo": "XXX", "nombre": "FAMILIA", "probabilidad": 0.XX, "razon": "..."}}],
  "requiere_revision_humana": true/false,  // true si confianza <0.95
  "siguiente_fase": "subfamily",
  "comentarios_adicionales": "Observaciones generales (NO sugerir códigos específicos ej: 600.01, 613.45)"
}}

REGLAS:
1. Concepto factura + contexto empresarial > UsoCFDI
2. UsoCFDI es validación secundaria
3. Confianza <0.95 → requiere_revision_humana=true
4. Explicar override_uso_cfdi si ocurre
5. SOLO determinar FAMILIA (100-800), NO sugerir códigos de subfamilia específicos (ej: 600.01, 613.45)
6. comentarios_adicionales: observaciones generales, NO códigos específicos
7. **CRÍTICO**: El campo "razonamiento" es OBLIGATORIO y NUNCA debe estar vacío. Incluye SIEMPRE una explicación clara de tu decisión, incluso si tienes alta confianza (>95%)

Clasifica la factura.
"""

    return prompt


__all__ = ['build_family_classification_prompt_optimized']
