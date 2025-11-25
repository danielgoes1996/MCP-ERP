"""
Optimized family classifier prompt with Anthropic Prompt Caching support.

This version splits the prompt into:
- STATIC BLOCK (cacheable): Plan contable + metodología + 1 ejemplo → ~2,500 tokens
- DYNAMIC BLOCK (not cached): Invoice data + company context + few-shot → ~500 tokens

Expected savings:
- First call: Same cost as original (~4,000 tokens write)
- Subsequent calls: 90% cheaper on static block (~400 tokens write + ~2,500 tokens cached read)
- Latency: ~50% faster after first call

Cache TTL: 5 minutes (default) or 1 hour (with extended-cache-ttl header)
"""

from typing import Dict, Optional, List


def build_static_prompt_block() -> str:
    """
    Build the STATIC portion of the prompt that will be cached.

    This block contains:
    - Plan contable (8 familias)
    - Metodología de clasificación
    - 1 ejemplo completo (el más completo: etiquetas + NIF C-4)
    - Formato de respuesta JSON

    This block NEVER changes between requests, so it can be cached.
    """

    return """Eres un contador experto mexicano especializado en clasificación de gastos bajo el Código Agrupador del SAT.

Tu tarea es clasificar facturas a NIVEL DE FAMILIA (primer nivel jerárquico: 100-800).

PLAN CONTABLE - FAMILIAS (100-800):

100 - ACTIVO | Bienes y derechos propiedad de la empresa. Inventarios, maquinaria, equipo, mobiliario, vehículos, terrenos. INVERSIONES capitalizables.
200 - PASIVO | Deudas y obligaciones. Proveedores por pagar, préstamos, nómina pendiente, impuestos por pagar.
300 - CAPITAL | Aportaciones de socios y resultados acumulados. Capital social, reservas, utilidades retenidas.
400 - INGRESOS | Ventas y otros ingresos. Ventas de productos, servicios, ingresos financieros.
500 - COSTO DE VENTAS | Costo directo de producir/ad

quirir lo vendido. Materia prima, mano de obra directa, compras para reventa.
600 - GASTOS DE OPERACIÓN | Gastos necesarios para operar (NO producción). Renta, luz, teléfono, papelería, honorarios, publicidad, sueldos administrativos.
700 - GASTOS FINANCIEROS | Costos de financiamiento. Intereses sobre préstamos, comisiones bancarias, pérdidas cambiarias.
800 - OTROS INGRESOS/GASTOS | Partidas extraordinarias no recurrentes. Venta de activos, donaciones, subsidios.

METODOLOGÍA DE CLASIFICACIÓN:

PASO 0: DIRECCIÓN DE FACTURA
- RECIBIDA (compra): Materiales → 115 INVENTARIO primero (NIF C-4), luego → 500 al USAR
- EMITIDA (venta): Productos vendidos → 400 INGRESOS + 500 COSTO DE VENTAS

PASO 1: ANÁLISIS SEMÁNTICO
- ¿Bien tangible, servicio, o inversión?
- ¿Material de producción o insumo operativo?

PASO 2: CONTEXTO EMPRESARIAL
- ¿Cómo se usa en el modelo de negocio de esta empresa?
- Ejemplo: "Etiquetas" para SOFTWARE → 600 Gastos | para PRODUCCIÓN → 500 Costo de Ventas

PASO 3: DETERMINACIÓN DE FAMILIA
- 100 ACTIVO: Inversión capitalizable (>$5K, vida útil >1 año) según NIF C-6
- 500 COSTO: Material que se integra físicamente al producto vendido
- 600 GASTOS: Necesario para operar pero NO se integra al producto
- 700 FINANCIEROS: Intereses, comisiones bancarias

PASO 4: VALIDACIÓN CON USOCFDI (SECUNDARIO)
- G01 → SUGIERE 500 o 115 Inventario
- G03 → SUGIERE 600 Gastos Operación
- I01-I08 → SUGIERE 100 Activo
- IMPORTANTE: Si tu análisis contradice UsoCFDI, CONFÍA EN TU ANÁLISIS (proveedores frecuentemente se equivocan)

EJEMPLO COMPLETO:

FACTURA:
- Descripción: "ETIQUETAS ADHESIVAS PARA ENVASES DE MIEL 500ML, IMPRESIÓN A COLOR"
- Proveedor: GARIN ETIQUETAS SA (RFC: GET130827SN7)
- Clave SAT: 55121604
- Monto: $3,450.00 MXN
- UsoCFDI: G03
- Dirección: RECIBIDA (Receptor=POLLENBEEMX tu empresa, Emisor=GARIN proveedor)
- Industria: Producción y comercialización de miel

RAZONAMIENTO:
PASO 0 - Dirección:
  • Receptor = POLLENBEEMX (tu empresa) → FACTURA RECIBIDA = COMPRA
  • Implicación: Material de producción comprado → 115 INVENTARIO (NIF C-4)

PASO 1 - Semántico:
  • Etiquetas personalizadas "PARA ENVASES DE MIEL 500ML"
  • Material de empaque físico

PASO 2 - Contexto:
  • Industria: PRODUCCIÓN DE MIEL (no oficina)
  • Se adhieren físicamente al producto final
  • Sin etiquetas, producto NO PUEDE VENDERSE (NOM-051)

PASO 3 - Determinación:
  • NO es Gasto de Operación (600) - no es suministro de oficina
  • NO es Costo de Ventas (500) - esto es COMPRA, no USO
  • SÍ es INVENTARIO (115) porque:
    - FACTURA RECIBIDA (compra)
    - Se almacenará hasta uso
    - NIF C-4: Compras → Inventario primero, Costo de Ventas cuando se USAN

PASO 4 - UsoCFDI:
  • G03 "Gastos en general" CONTRADICE
  • Debió ser G01 "Adquisición de mercancías"
  • OVERRIDE correcto

RESPUESTA:
{
  "familia_codigo": "100",
  "familia_nombre": "ACTIVO",
  "confianza": 0.98,
  "razonamiento": "FACTURA RECIBIDA de material de producción. Según NIF C-4, compras de materiales → Inventario (115) al momento de compra. Transferencia a Costo de Ventas (500) ocurre cuando se usan, no cuando se compran.",
  "factores_decision": [
    "FACTURA RECIBIDA: Receptor=POLLENBEEMX (tu empresa) = COMPRA",
    "Material de empaque para producción",
    "NIF C-4: Compras materiales → Inventario (115) primero",
    "Proveedor GET130827SN7 = 'packaging_materials_labels'"
  ],
  "uso_cfdi_analisis": "UsoCFDI=G03 incorrecto. Debió ser G01 (materiales).",
  "override_uso_cfdi": true,
  "override_razon": "Dirección de factura (RECIBIDA=compra) + contexto empresarial tienen precedencia. Materiales comprados → Inventario (115) primero, luego Costo de Ventas (500) cuando se usan.",
  "familias_alternativas": [],
  "requiere_revision_humana": false,
  "siguiente_fase": "subfamily",
  "comentarios_adicionales": "En Fase 2, clasificar como 115.01 Inventario de materiales y suministros."
}

FORMATO DE RESPUESTA (JSON estricto):

{
  "familia_codigo": "XXX",  // 100, 200, 300, 400, 500, 600, 700, 800
  "familia_nombre": "NOMBRE FAMILIA",
  "confianza": 0.XX,  // 0.0-1.0 (>=0.95 auto-aprobar)
  "razonamiento": "1-2 oraciones POR QUÉ esta familia",
  "factores_decision": ["Factor 1", "Factor 2", "Factor 3"],
  "uso_cfdi_analisis": "¿Coincide o contradice UsoCFDI? ¿Por qué?",
  "override_uso_cfdi": true/false,
  "override_razon": "Por qué se ignora UsoCFDI" o null,
  "familias_alternativas": [{"codigo": "XXX", "nombre": "FAMILIA", "probabilidad": 0.XX, "razon": "..."}],
  "requiere_revision_humana": true/false,  // true si confianza <0.95
  "siguiente_fase": "subfamily",
  "comentarios_adicionales": "Observaciones para siguientes fases"
}

REGLAS CRÍTICAS:
1. PRIORIDAD: Concepto factura + contexto empresarial > UsoCFDI
2. UsoCFDI es validación secundaria, NO decisión principal
3. Confianza <0.95 → requiere_revision_humana=true
4. Siempre explicar override_uso_cfdi si ocurre
5. Misma descripción puede clasificar diferente según contexto empresa"""


def build_dynamic_prompt_block(
    invoice_data: Dict,
    company_context: Optional[Dict] = None,
    few_shot_examples: Optional[List[Dict]] = None,
) -> str:
    """
    Build the DYNAMIC portion of the prompt that changes per request.

    This block contains:
    - Datos específicos de la factura actual
    - Contexto de la empresa (si aplica)
    - Few-shot examples (si confianza < 80%)

    This block changes every time, so it's NOT cached.
    """

    # Extract invoice fields
    descripcion = invoice_data.get('descripcion', 'N/A')
    proveedor = invoice_data.get('proveedor', 'N/A')
    rfc_proveedor = invoice_data.get('rfc_proveedor', 'N/A')
    clave_prod_serv = invoice_data.get('clave_prod_serv', 'N/A')
    monto = invoice_data.get('monto', 0.0)
    uso_cfdi = invoice_data.get('uso_cfdi', 'N/A')

    # Invoice direction data
    receptor_nombre = invoice_data.get('receptor_nombre', 'N/A')
    receptor_rfc = invoice_data.get('receptor_rfc', 'N/A')
    emisor_nombre = invoice_data.get('emisor_nombre', proveedor)
    emisor_rfc = invoice_data.get('emisor_rfc', rfc_proveedor)

    # Build company context block
    context_block = ""
    if company_context:
        industry = company_context.get('industry_description', 'N/A')
        business_model = company_context.get('business_model_description', 'N/A')
        typical_expenses = company_context.get('typical_expenses', [])

        context_block = f"""
CONTEXTO EMPRESA:
- Industria: {industry}
- Modelo: {business_model}
- Gastos típicos: {', '.join(typical_expenses[:5])}"""  # Limit to 5 to save tokens

    # Build few-shot examples block
    few_shot_block = ""
    if few_shot_examples:
        from core.shared.company_context import format_family_examples_for_prompt
        few_shot_block = "\n" + format_family_examples_for_prompt(few_shot_examples)

    # Build dynamic block
    dynamic_content = f"""
FACTURA A CLASIFICAR:
- Descripción: {descripcion}
- Proveedor: {proveedor} (RFC: {rfc_proveedor})
- Clave SAT: {clave_prod_serv}
- Monto: ${monto:,.2f} MXN
- UsoCFDI: {uso_cfdi}
- Dirección: Emisor={emisor_nombre} ({emisor_rfc}) → Receptor={receptor_nombre} ({receptor_rfc})
{context_block}
{few_shot_block}

Ahora clasifica esta factura siguiendo la metodología."""

    return dynamic_content


def build_family_classification_prompt_cached(
    invoice_data: Dict,
    company_context: Optional[Dict] = None,
    few_shot_examples: Optional[List[Dict]] = None,
    return_blocks: bool = False,
):
    """
    Build optimized prompt with caching support.

    Args:
        invoice_data: Dict with invoice fields
        company_context: Optional company context
        few_shot_examples: Optional list of previous classifications
        return_blocks: If True, return (static_block, dynamic_block) tuple for caching

    Returns:
        If return_blocks=False: Complete prompt string (for non-cached use)
        If return_blocks=True: Tuple of (static_block, dynamic_block) for API caching
    """

    static_block = build_static_prompt_block()
    dynamic_block = build_dynamic_prompt_block(invoice_data, company_context, few_shot_examples)

    if return_blocks:
        return (static_block, dynamic_block)
    else:
        return static_block + "\n\n" + dynamic_block


__all__ = [
    'build_family_classification_prompt_cached',
    'build_static_prompt_block',
    'build_dynamic_prompt_block',
]
