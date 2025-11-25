"""
Family-level classifier prompt for hierarchical invoice classification.

This is PHASE 1 of a 3-phase classification system:
- Phase 1: Classify to family level (100-800) with >95% confidence
- Phase 2: Refine to subfamily (e.g., 600 → 613) with >90% confidence
- Phase 3: Select detailed account (e.g., 613 → 613.01) with >85% confidence

KEY PHILOSOPHY:
- PRIMARY: Invoice concept (description) + company context
- SECONDARY: UsoCFDI as supporting validation only
- Provider reliability varies, so we don't trust UsoCFDI as primary signal
"""

from typing import Dict, Optional, List


def build_family_classification_prompt(
    invoice_data: Dict,
    company_context: Optional[Dict] = None,
    few_shot_examples: Optional[List[Dict]] = None,
) -> str:
    """
    Build prompt for family-level classification (100-800).

    Args:
        invoice_data: Dict with descripcion, proveedor, rfc, clave_prod_serv, monto, uso_cfdi
        company_context: Optional company context with industry, business_model, typical_expenses, provider_treatments
        few_shot_examples: Optional list of previous family classifications for few-shot learning

    Returns:
        Formatted prompt string for Claude
    """

    # Extract invoice fields
    descripcion = invoice_data.get('descripcion', 'N/A')
    proveedor = invoice_data.get('proveedor', 'N/A')
    rfc_proveedor = invoice_data.get('rfc_proveedor', 'N/A')
    clave_prod_serv = invoice_data.get('clave_prod_serv', 'N/A')
    monto = invoice_data.get('monto', 0.0)
    uso_cfdi = invoice_data.get('uso_cfdi', 'N/A')

    # NEW: Extract invoice direction data (CRITICAL for inventory vs cost of sales)
    receptor_nombre = invoice_data.get('receptor_nombre', 'N/A')
    receptor_rfc = invoice_data.get('receptor_rfc', 'N/A')
    emisor_nombre = invoice_data.get('emisor_nombre', proveedor)  # Fallback to proveedor
    emisor_rfc = invoice_data.get('emisor_rfc', rfc_proveedor)  # Fallback to rfc_proveedor

    # Build company context block
    context_block = ""
    if company_context:
        industry = company_context.get('industry_description', 'N/A')
        business_model = company_context.get('business_model_description', 'N/A')
        typical_expenses = company_context.get('typical_expenses', [])
        provider_treatments = company_context.get('provider_treatments', {})

        context_block = f"""
CONTEXTO DE LA EMPRESA:
- Industria: {industry}
- Modelo de negocio: {business_model}
- Gastos típicos: {', '.join(typical_expenses)}

TRATAMIENTOS ESPECIALES DE PROVEEDORES:
"""
        if provider_treatments:
            for rfc, treatment in provider_treatments.items():
                context_block += f"  • {rfc}: {treatment}\n"
        else:
            context_block += "  (ninguno configurado)\n"

    # Detect invoice direction (RECIBIDA vs EMITIDA) - CRITICAL for proper classification
    invoice_direction_block = f"""
⚠️  DIRECCIÓN DE LA FACTURA (CRÍTICO):
- Emisor (quien emite): {emisor_nombre} (RFC: {emisor_rfc})
- Receptor (quien recibe): {receptor_nombre} (RFC: {receptor_rfc})
"""

    # Check if this is a RECIBIDA (purchase from supplier) or EMITIDA (sale to customer)
    # For now, we'll include both names and let the LLM determine based on company context
    # In a future enhancement, we could auto-detect by comparing receptor_rfc with company RFC

    # Build few-shot examples block (conditional learning)
    few_shot_block = ""
    if few_shot_examples:
        from core.shared.company_context import format_family_examples_for_prompt
        few_shot_block = format_family_examples_for_prompt(few_shot_examples)

    prompt = f"""Eres un contador experto mexicano especializado en clasificación de gastos bajo el Código Agrupador del SAT.

Tu tarea es clasificar esta factura a NIVEL DE FAMILIA (primer nivel jerárquico: 100-800).

DATOS DE LA FACTURA:
- Descripción: {descripcion}
- Proveedor/Emisor: {proveedor} (RFC: {rfc_proveedor})
- Clave SAT: {clave_prod_serv}
- Monto: ${monto:,.2f} MXN
- UsoCFDI declarado: {uso_cfdi}

{invoice_direction_block}
{context_block}
{few_shot_block}

PLAN CONTABLE - FAMILIAS (100-800):

100 - ACTIVO
  Descripción: Bienes y derechos propiedad de la empresa
  Ejemplos: Inventarios, maquinaria, equipo de cómputo, mobiliario, vehículos, terrenos, construcciones
  Características: INVERSIONES que se capitalizan, NO son gastos del ejercicio

200 - PASIVO
  Descripción: Deudas y obligaciones de la empresa
  Ejemplos: Proveedores por pagar, préstamos, nómina pendiente de pago, impuestos por pagar
  Características: Obligaciones financieras, cuentas por pagar

300 - CAPITAL
  Descripción: Aportaciones de socios y resultados acumulados
  Ejemplos: Capital social, reservas, utilidades retenidas
  Características: Patrimonio de los accionistas

400 - INGRESOS
  Descripción: Ventas y otros ingresos de la empresa
  Ejemplos: Ventas de productos, prestación de servicios, ingresos financieros
  Características: Entradas de dinero por actividades ordinarias y extraordinarias

500 - COSTO DE VENTAS
  Descripción: Costo directo de producir/adquirir lo que se vende
  Ejemplos: Materia prima, mano de obra directa, compras de mercancía para reventa
  Características: SOLO costos directamente relacionados con productos vendidos

600 - GASTOS DE OPERACIÓN
  Descripción: Gastos necesarios para operar el negocio (NO relacionados con producción)
  Ejemplos: Renta de oficina, luz, teléfono, papelería, honorarios, publicidad, sueldos administrativos
  Características: Gastos indirectos, administrativos, de venta

700 - GASTOS FINANCIEROS
  Descripción: Costos de financiamiento y operaciones financieras
  Ejemplos: Intereses sobre préstamos, comisiones bancarias, pérdidas cambiarias
  Características: Relacionados con deuda y operaciones financieras

800 - OTROS INGRESOS/GASTOS
  Descripción: Partidas extraordinarias o no recurrentes
  Ejemplos: Venta de activos fijos, donaciones, subsidios gubernamentales
  Características: NO relacionados con la operación ordinaria


METODOLOGÍA DE CLASIFICACIÓN:

PASO 0: DETERMINAR DIRECCIÓN DE LA FACTURA (CRÍTICO)
Primero, identifica si esta es una factura RECIBIDA (compra) o EMITIDA (venta):

**FACTURA RECIBIDA (Compra de proveedor):**
- Receptor = Tu empresa (el cliente que recibe datos en CONTEXTO DE LA EMPRESA)
- Emisor = Proveedor externo
- Interpretación contable:
  * Materiales/insumos → 115 INVENTARIO (al momento de compra)
  * Gastos operativos → 600 GASTOS DE OPERACIÓN
  * Inversiones → 100 ACTIVO

**FACTURA EMITIDA (Venta a cliente):**
- Emisor = Tu empresa
- Receptor = Cliente externo
- Interpretación contable:
  * Venta de productos → 400 INGRESOS + 500 COSTO DE VENTAS (uso de inventario)
  * Servicios prestados → 400 INGRESOS

⚠️  REGLA CRÍTICA PARA MATERIALES DE PRODUCCIÓN:
- Si es RECIBIDA + material de producción/empaque → 115 INVENTARIO (no 500)
  Razón: Según NIF C-4, las compras de materiales se registran primero como
  inventario. La transferencia a 500 Costo de Ventas ocurre cuando se USAN,
  no cuando se COMPRAN.

- Si es EMITIDA (venta) + materiales usados → 500 COSTO DE VENTAS
  Razón: Al vender, se reconoce el costo de los materiales que salieron del inventario.

PASO 1: ANÁLISIS SEMÁNTICO DE LA DESCRIPCIÓN
Analiza el concepto de la factura para entender QUÉ se está comprando:
- ¿Es un bien tangible (producto físico)?
- ¿Es un servicio (trabajo, asesoría, mantenimiento)?
- ¿Es una inversión de largo plazo o un gasto del ejercicio?
- ¿Es material de producción o insumo operativo?

PASO 2: CONTEXTUALIZACIÓN CON LA EMPRESA
Evalúa cómo se relaciona con el modelo de negocio:
- ¿Este gasto es típico para la industria de la empresa?
- ¿El proveedor tiene tratamiento especial configurado?
- ¿Cómo lo usaría esta empresa específica en su operación?

Ejemplo crítico:
- "Etiquetas adhesivas" para una empresa de SOFTWARE → 600 Gastos de Operación (papelería de oficina)
- "Etiquetas adhesivas" para una empresa de PRODUCCIÓN DE MIEL → 500 Costo de Ventas (material de empaque)

PASO 3: DETERMINACIÓN DE LA FAMILIA
Basándote en el análisis semántico + contexto empresarial, determina:
- 100 ACTIVO: ¿Es una inversión capitalizable de largo plazo? (>$5,000 MXN y vida útil >1 año)
- 500 COSTO DE VENTAS: ¿Es material/insumo que se integra físicamente al producto que vende?
- 600 GASTOS OPERACIÓN: ¿Es un gasto necesario para operar pero NO se integra al producto?
- 700 GASTOS FINANCIEROS: ¿Es costo de financiamiento (intereses, comisiones bancarias)?
- 400 INGRESOS / 200 PASIVO / 300 CAPITAL: (raro en facturas de compra)

PASO 4: VALIDACIÓN CON USOCFDI (OPCIONAL)
El UsoCFDI es una PISTA ADICIONAL, pero NO es la decisión principal:
- G01 "Adquisición de mercancías" → SUGIERE 500 Costo de Ventas o 115 Inventario
- G03 "Gastos en general" → SUGIERE 600 Gastos de Operación
- I01-I08 "Inversiones" → SUGIERE 100 Activo

IMPORTANTE: Si tu análisis (PASO 1-3) contradice el UsoCFDI, CONFÍA EN TU ANÁLISIS.
Razón: Los proveedores frecuentemente seleccionan UsoCFDI incorrectamente.

CÁLCULO DE CONFIANZA:
- Confianza >= 0.95: La descripción + contexto claramente indican una familia específica
- Confianza 0.85-0.94: El concepto es claro pero hay ligera ambigüedad
- Confianza < 0.85: Múltiples familias son plausibles, REQUIERE REVISIÓN HUMANA


EJEMPLOS COMPLETOS:

--- EJEMPLO 1 ---
FACTURA:
- Descripción: "Laptop Dell Inspiron 15, Intel i7, 16GB RAM, 512GB SSD"
- Proveedor: Office Depot (RFC: OFD990528LJ8)
- Clave SAT: 43211507 (Computadoras portátiles)
- Monto: $18,500.00 MXN
- UsoCFDI: G03 (Gastos en general)

CONTEXTO EMPRESA:
- Industria: Consultoría de software
- Modelo: Servicios profesionales
- Gastos típicos: Equipos de cómputo, oficina, nómina

RAZONAMIENTO:
PASO 1 - Análisis semántico:
  • Es un bien tangible (laptop nueva)
  • Clave SAT 43211507 confirma: computadora portátil
  • Monto $18,500 MXN es significativo
  • Vida útil estimada: 3-4 años

PASO 2 - Contexto empresarial:
  • Consultoría de software: Las laptops son herramientas de trabajo fundamentales
  • Monto >$5,000 y vida útil >1 año → CRITERIO DE CAPITALIZACIÓN
  • Se deprecia a lo largo de varios ejercicios fiscales

PASO 3 - Determinación:
  • NO es Costo de Ventas (500) porque no se integra a productos vendidos
  • NO es Gasto de Operación (600) porque se capitaliza por su monto y durabilidad
  • SÍ es Activo (100) - específicamente equipo de cómputo

PASO 4 - Validación UsoCFDI:
  • UsoCFDI = G03 "Gastos en general" CONTRADICE nuestra clasificación
  • DECISIÓN: Ignorar UsoCFDI porque el proveedor lo seleccionó incorrectamente
  • Según NIF C-6, equipos >$5,000 con vida útil >1 año SE CAPITALIZAN

RESPUESTA:
{{
  "familia_codigo": "100",
  "familia_nombre": "ACTIVO",
  "confianza": 0.98,
  "razonamiento": "Laptop con valor de $18,500 MXN y vida útil de 3-4 años cumple criterios de capitalización según NIF C-6. Es una inversión en activo fijo (equipo de cómputo) que se deprecia en ejercicios futuros.",
  "factores_decision": [
    "Monto $18,500 MXN excede umbral de capitalización ($5,000)",
    "Vida útil estimada 3-4 años (>1 año)",
    "Clave SAT 43211507 confirma: computadora portátil",
    "Empresa de consultoría: herramienta de trabajo fundamental"
  ],
  "uso_cfdi_analisis": "UsoCFDI=G03 contradice la clasificación correcta. El proveedor debió usar I01-I08 (Inversiones). Prevalece la realidad económica sobre la declaración formal.",
  "override_uso_cfdi": true,
  "override_razon": "Criterios de capitalización NIF C-6 tienen precedencia sobre UsoCFDI mal seleccionado por proveedor.",
  "familias_alternativas": [],
  "requiere_revision_humana": false,
  "siguiente_fase": "subfamily",
  "comentarios_adicionales": "En Fase 2, clasificar dentro de familia 100 a subcuenta específica de Equipo de Cómputo (probablemente 184)."
}}

--- EJEMPLO 2 ---
FACTURA:
- Descripción: "ETIQUETAS ADHESIVAS PARA ENVASES DE MIEL 500ML, IMPRESIÓN A COLOR"
- Proveedor/Emisor: GARIN ETIQUETAS SA DE CV (RFC: GET130827SN7)
- Clave SAT: 55121604 (Etiquetas autoadhesivas)
- Monto: $3,450.00 MXN
- UsoCFDI declarado: G03 (Gastos en general)

⚠️  DIRECCIÓN DE LA FACTURA (CRÍTICO):
- Emisor (quien emite): GARIN ETIQUETAS SA DE CV (RFC: GET130827SN7)
- Receptor (quien recibe): POLLENBEEMX SA DE CV (RFC: POL180515XX3)

CONTEXTO EMPRESA:
- Industria: Producción y comercialización de miel de abeja
- Modelo: Producción, envasado y distribución de miel
- Gastos típicos: Materias primas, materiales de empaque, logística
- Tratamiento especial: RFC GET130827SN7 → "packaging_materials_labels"

RAZONAMIENTO:
PASO 0 - Dirección de factura:
  • Receptor = POLLENBEEMX (tu empresa según contexto) → FACTURA RECIBIDA (compra)
  • Emisor = GARIN ETIQUETAS (proveedor) → Compraste etiquetas de proveedor externo
  • ⚠️  IMPLICACIÓN CRÍTICA: Como es COMPRA de material de producción,
    debe clasificarse como 115 INVENTARIO según NIF C-4, NO como 500 Costo de Ventas

PASO 1 - Análisis semántico:
  • Es un bien tangible (etiquetas físicas)
  • Descripción específica: "PARA ENVASES DE MIEL 500ML"
  • Clave SAT 55121604: Etiquetas autoadhesivas
  • Impresión personalizada para producto específico

PASO 2 - Contexto empresarial:
  • Industria: PRODUCCIÓN DE MIEL (no es oficina administrativa)
  • Las etiquetas se ADHIEREN FÍSICAMENTE al producto final (envases de miel)
  • Proveedor GET130827SN7 tiene tratamiento especial: "packaging_materials_labels"
  • Sin las etiquetas, el producto NO PUEDE VENDERSE (requisito NOM-051)
  • Material de empaque es PARTE INTEGRAL del producto

PASO 3 - Determinación CON DIRECCIÓN DE FACTURA:
  • NO es Activo fijo (inversión largo plazo) pero SÍ es Activo circulante (Inventario)
  • NO es Gasto de Operación (600) porque NO es suministro de oficina
  • NO es Costo de Ventas (500) porque esto es una COMPRA, no un USO
  • SÍ es INVENTARIO (115) porque:
    - Es una FACTURA RECIBIDA (compra de proveedor)
    - Material de producción que se almacenará hasta su uso
    - Según NIF C-4: Compras de materiales → Inventario primero
    - Transferencia a 500 Costo de Ventas ocurre cuando se USAN, no cuando se COMPRAN

PASO 4 - Validación UsoCFDI:
  • UsoCFDI = G03 "Gastos en general" CONTRADICE nuestra clasificación
  • DECISIÓN: Ignorar UsoCFDI - debió ser G01 "Adquisición de mercancías"

RESPUESTA:
{{
  "familia_codigo": "100",
  "familia_nombre": "ACTIVO",
  "confianza": 0.98,
  "razonamiento": "FACTURA RECIBIDA de etiquetas personalizadas para producción. Según NIF C-4, las compras de materiales de producción se registran como Inventario (115) al momento de compra. La transferencia a Costo de Ventas (500) ocurre cuando se usan, no cuando se compran.",
  "factores_decision": [
    "FACTURA RECIBIDA: Receptor=POLLENBEEMX (tu empresa) = COMPRA",
    "Material de empaque para producción de miel",
    "NIF C-4: Compras de materiales → Inventario (115), NO Costo de Ventas (500)",
    "Descripción 'PARA ENVASES DE MIEL 500ML' confirma uso en producción",
    "Proveedor GET130827SN7 configurado como 'packaging_materials_labels'"
  ],
  "uso_cfdi_analisis": "UsoCFDI=G03 es incorrecto. Debió ser G01 (Adquisición de mercancías) porque son materiales de producción.",
  "override_uso_cfdi": true,
  "override_razon": "La dirección de factura (RECIBIDA=compra) + contexto empresarial tienen precedencia absoluta. Materiales comprados van a Inventario (115) primero, luego a Costo de Ventas (500) cuando se usan.",
  "familias_alternativas": [],
  "requiere_revision_humana": false,
  "siguiente_fase": "subfamily",
  "comentarios_adicionales": "CRÍTICO: Mismo material puede ser 115 (si es compra) o 500 (si es uso/venta). La DIRECCIÓN de factura determina la clasificación. En Fase 2, clasificar como 115.01 Inventario de materiales y suministros."
}}

--- EJEMPLO 3 ---
FACTURA:
- Descripción: "Servicios profesionales de contabilidad - Mes de enero 2025"
- Proveedor: Despacho Fiscal González y Asociados (RFC: DFG890123HJ5)
- Clave SAT: 84111505 (Servicios de contabilidad)
- Monto: $8,500.00 MXN
- UsoCFDI: G03 (Gastos en general)

CONTEXTO EMPRESA:
- Industria: Producción de miel de abeja
- Modelo: Producción, envasado y distribución
- Gastos típicos: Materias primas, empaque, logística, servicios administrativos

RAZONAMIENTO:
PASO 1 - Análisis semántico:
  • Es un servicio profesional (NO un bien tangible)
  • Clave SAT 84111505 confirma: Servicios de contabilidad
  • Servicio recurrente mensual
  • NO es producción, es administración

PASO 2 - Contexto empresarial:
  • Aunque la empresa es de producción, la contabilidad es un SERVICIO ADMINISTRATIVO
  • NO se integra al producto (miel)
  • Es un gasto necesario para operar, pero indirecto
  • Típico en "servicios administrativos" de la empresa

PASO 3 - Determinación:
  • NO es Activo (100) porque es un servicio mensual, no una inversión
  • NO es Costo de Ventas (500) porque NO se relaciona con producción directa
  • SÍ es Gasto de Operación (600) porque:
    - Servicio administrativo indirecto
    - Necesario para operar pero no para producir
    - Gasto recurrente del ejercicio

PASO 4 - Validación UsoCFDI:
  • UsoCFDI = G03 "Gastos en general" COINCIDE con nuestra clasificación
  • Confirmación adicional de que la clasificación es correcta

RESPUESTA:
{{
  "familia_codigo": "600",
  "familia_nombre": "GASTOS DE OPERACIÓN",
  "confianza": 0.99,
  "razonamiento": "Servicios profesionales de contabilidad son un gasto administrativo indirecto necesario para operar el negocio, pero no relacionado con la producción directa de miel.",
  "factores_decision": [
    "Clave SAT 84111505 confirma: Servicios de contabilidad",
    "Servicio administrativo indirecto (NO producción)",
    "NO se integra al producto final",
    "Gasto recurrente mensual del ejercicio",
    "Clasificación típica de honorarios profesionales administrativos"
  ],
  "uso_cfdi_analisis": "UsoCFDI=G03 coincide perfectamente con la clasificación. El proveedor seleccionó correctamente.",
  "override_uso_cfdi": false,
  "override_razon": null,
  "familias_alternativas": [],
  "requiere_revision_humana": false,
  "siguiente_fase": "subfamily",
  "comentarios_adicionales": "En Fase 2, probablemente clasificar en 625 Honorarios Profesionales."
}}


FORMATO DE RESPUESTA (JSON estricto):

Debes responder ÚNICAMENTE con un objeto JSON con esta estructura:

{{
  "familia_codigo": "XXX",  // Código de 3 dígitos: 100, 200, 300, 400, 500, 600, 700, 800
  "familia_nombre": "NOMBRE DE LA FAMILIA",  // Nombre completo en mayúsculas
  "confianza": 0.XX,  // Float entre 0 y 1 (requiere >=0.95 para auto-aprobar)
  "razonamiento": "Explicación de 1-2 oraciones de POR QUÉ esta familia",
  "factores_decision": [
    "Factor 1 que influyó en la decisión",
    "Factor 2...",
    "Factor 3..."
  ],
  "uso_cfdi_analisis": "Análisis del UsoCFDI: ¿coincide o contradice? ¿por qué?",
  "override_uso_cfdi": true/false,  // true si tu clasificación contradice UsoCFDI
  "override_razon": "Explicación de por qué se ignora UsoCFDI" o null,
  "familias_alternativas": [  // Lista vacía si confianza >0.95
    {{"codigo": "XXX", "nombre": "FAMILIA", "probabilidad": 0.XX, "razon": "..."}}
  ],
  "requiere_revision_humana": true/false,  // true si confianza <0.95
  "siguiente_fase": "subfamily",  // Siempre "subfamily" para continuar clasificación
  "comentarios_adicionales": "Observaciones relevantes para las siguientes fases"
}}

REGLAS CRÍTICAS:
1. **PRIORIDAD ABSOLUTA**: Concepto de factura + contexto empresarial
2. UsoCFDI es solo validación secundaria, NO decisión principal
3. Si confianza < 0.95, marcar requiere_revision_humana=true
4. Siempre explicar override_uso_cfdi si ocurre
5. La misma descripción puede clasificar diferente según el contexto de la empresa

Ahora clasifica la factura proporcionada.
"""

    return prompt


__all__ = ['build_family_classification_prompt']
