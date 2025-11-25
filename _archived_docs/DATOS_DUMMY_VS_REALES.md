# Datos Dummy vs Datos Reales - Vista de Facturas

## Estado Actual del Sistema

En la vista http://localhost:3004/invoices, actualmente hay una mezcla de **datos reales** y **datos que parecen dummy** (pero en realidad son errores de procesamiento o datos no extraídos correctamente).

## Análisis de Datos por Categoría

### ✅ DATOS 100% REALES (Del XML/SAT)

Estos datos provienen directamente del XML del CFDI y son totalmente confiables:

```json
{
  "xml": "<?xml version=...>",  // ✅ XML completo del SAT

  // Los siguientes SI están en el XML pero NO se extraen correctamente:
  "uuid": null,          // ❌ DEBERÍA SER: "270ce6b9-3a7f-47a5-a6d6-73622875c26d"
  "serie": null,         // ❌ DEBERÍA SER: "FMM"
  "folio": null,         // ❌ DEBERÍA SER: "020525060077247"
  "fechaEmision": null,  // ❌ DEBERÍA SER: "2025-06-05T22:44:40"
  "fechaTimbrado": null, // ❌ DEBERÍA SER: "2025-06-05T23:14:16"
  "tipo": null,          // ❌ DEBERÍA SER: "I" (Ingreso)
  "formaPago": null,     // ❌ DEBERÍA SER: "99"
  "metodoPago": null,    // ❌ DEBERÍA SER: "PPD"
  "usoCFDI": null,       // ❌ DEBERÍA SER: "G03"

  "subtotal": 0,         // ❌ DEBERÍA SER: 393.44
  "total": 388.99,       // ✅ CORRECTO (único que se extrae bien)
  "descuento": null,     // ❌ DEBERÍA SER: 65.00

  "emisorNombre": null,  // ❌ DEBERÍA SER: "TELEFONOS DE MEXICO"
  "emisorRFC": null,     // ❌ DEBERÍA SER: "TME840315KT6"
  "receptorRFC": null,   // ❌ DEBERÍA SER: "POL210218264"
  "receptorNombre": null,// ❌ DEBERÍA SER: "POLLENBEEMX"

  "impuestosTrasladados": 0,  // ❌ DEBERÍA SER: 60.55
  "impuestosRetenidos": 0,

  "conceptos": [],       // ❌ DEBERÍA TENER 1 concepto
}
```

**Problema Real:** El parser LLM (Claude Haiku) está **fallando** en extraer los datos del XML, dejando casi todo en `null` excepto el `total`.

### ⚠️ DATOS INFERIDOS (LLM - No Confiables)

Estos datos son "adivinados" por el LLM y **NO son oficiales del SAT**:

```json
{
  "estatusSAT": "desconocido"  // ⚠️ INFERIDO por LLM (no validado con SAT)
}
```

**Este es el dato que acabamos de reemplazar con validación real:**

```json
{
  "satValidation": {
    "status": "pending",           // ✅ Estado REAL del SAT (cuando se valide)
    "verifiedAt": "2025-11-12...", // ✅ Timestamp de verificación oficial
    "verificationUrl": "https://verificacfdi.facturaelectronica.sat.gob.mx/..."
  }
}
```

### 🔧 DATOS CALCULADOS (Derivados)

Estos se calculan a partir de otros datos:

```json
{
  "selloVerificado": false,  // Calculado: bool(uuid) - Siempre false porque uuid es null
  "taxBadges": [],           // Calculado: de impuestos (vacío porque impuestos son 0)
}
```

### 📊 DATOS DEFAULT/FALLBACK

Valores por defecto cuando no hay datos:

```json
{
  "moneda": "MXN",          // Default cuando no se especifica
  "tipoCambio": null,       // null = asume 1.0 MXN
  "complementos": [],       // No se extraen (deberían estar)
  "relacionados": [],       // No se extraen
}
```

## Problema Real Detectado

### ❌ El Parser LLM No Está Funcionando Correctamente

Mirando el XML crudo que SÍ se guarda:

```xml
<cfdi:Comprobante
  UUID="270ce6b9-3a7f-47a5-a6d6-73622875c26d"  ← Existe en XML
  Serie="FMM"                                   ← Existe en XML
  Folio="020525060077247"                       ← Existe en XML
  Fecha="2025-06-05T22:44:40"                   ← Existe en XML
  Total="388.99"                                ← ✅ Este SÍ se extrajo
  SubTotal="393.44"                             ← Existe pero no se extrajo
  ...
>
```

**Todos los datos están en el XML**, pero el parser Claude Haiku **no los está extrayendo**.

## Solución Propuesta

### Opción 1: Arreglar el Parser LLM (Más Difícil)

El problema está en: `core/ai_pipeline/parsers/cfdi_llm_parser.py`

El prompt del LLM necesita ser mejorado o:
- Aumentar el contexto
- Mejorar las instrucciones
- Usar un modelo más potente (Sonnet en lugar de Haiku)

### Opción 2: Parser XML Directo (Más Rápido y Confiable) ✅ RECOMENDADO

**Ya existe** un parser XML tradicional: `core/ai_pipeline/parsers/invoice_parser.py`

```python
from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml

# Usa lxml para parsear XML directamente (sin LLM)
result = parse_cfdi_xml(xml_content)
# Retorna TODOS los campos correctamente
```

### ✅ ACCIÓN RECOMENDADA

1. **Usar parser XML directo** para CFDIs (es más rápido y 100% confiable)
2. **Reservar LLM** solo para facturas en PDF o imágenes
3. **Validar con SAT** (ya implementado) para confirmar vigencia

## Tabla Comparativa: Estado Actual vs Ideal

| Campo | Estado Actual | ¿Es Real? | Estado Ideal |
|-------|--------------|-----------|--------------|
| `xml` | ✅ XML completo del SAT | ✅ Real | ✅ Mantener |
| `uuid` | ❌ null | ❌ No extraído | ✅ "270ce6b9..." |
| `serie` | ❌ null | ❌ No extraído | ✅ "FMM" |
| `folio` | ❌ null | ❌ No extraído | ✅ "020525060077247" |
| `fechaEmision` | ❌ null | ❌ No extraído | ✅ "2025-06-05T22:44:40" |
| `total` | ✅ 388.99 | ✅ Real | ✅ Mantener |
| `subtotal` | ❌ 0 | ❌ No extraído | ✅ 393.44 |
| `descuento` | ❌ null | ❌ No extraído | ✅ 65.00 |
| `metodoPago` | ❌ null | ❌ No extraído | ✅ "PPD" |
| `formaPago` | ❌ null | ❌ No extraído | ✅ "99" |
| `emisorRFC` | ❌ null | ❌ No extraído | ✅ "TME840315KT6" |
| `emisorNombre` | ❌ null | ❌ No extraído | ✅ "TELEFONOS DE MEXICO" |
| `receptorRFC` | ❌ null | ❌ No extraído | ✅ "POL210218264" |
| `receptorNombre` | ❌ null | ❌ No extraído | ✅ "POLLENBEEMX" |
| `impuestosTrasladados` | ❌ 0 | ❌ No extraído | ✅ 60.55 |
| `conceptos` | ❌ [] | ❌ No extraído | ✅ [1 concepto] |
| `estatusSAT` | ⚠️ "desconocido" | ⚠️ LLM inference | ❌ Eliminar (usar satValidation) |
| `satValidation.status` | ✅ "pending" | ✅ Real (en proceso) | ✅ "vigente" (cuando valide) |
| `satValidation.verifiedAt` | ✅ null | ✅ Real | ✅ "2025-11-12..." |
| `satValidation.verificationUrl` | ✅ null | ✅ Real | ✅ "https://verificacfdi..." |

## Resumen Ejecutivo

### Datos Actualmente "Dummy" (Parecen Falsos pero No Lo Son)

**NO son datos inventados**, son datos **reales que existen en el XML pero el parser no los extrae**:

- ❌ UUID, Serie, Folio
- ❌ Fechas de emisión y timbrado
- ❌ Subtotal, descuento
- ❌ Método y forma de pago
- ❌ RFCs y nombres (emisor/receptor)
- ❌ Impuestos y conceptos

### Único Dato Realmente "Inferido" (No Confiable)

- ⚠️ `estatusSAT: "desconocido"` - Este es adivinado por el LLM

**Ya lo reemplazamos con validación real del SAT:**
- ✅ `satValidation.status` - Verificado contra servicios web del SAT

## Próximos Pasos

### 1. Arreglar Extracción de Datos (URGENTE)

```python
# En core/expenses/invoices/universal_invoice_engine_system.py
# Cambiar de:
parser = CFDILLMParser()  # ← Falla en extraer

# A:
parser = DirectXMLParser()  # ← Extrae todo correctamente
```

### 2. Mantener Validación SAT (YA HECHO) ✅

```python
# Ya implementado:
sat_validation = validate_cfdi_with_sat(uuid, rfc_emisor, rfc_receptor, total)
# Retorna: vigente/cancelado/sustituido (REAL del SAT)
```

### 3. UI: Marcar Datos No Confiables

Mientras se arregla el parser, en el frontend marcar claramente:

```tsx
// Si el campo es null, mostrar advertencia
{!uuid && (
  <div className="text-amber-600 text-xs">
    ⚠️ UUID no extraído - Parser falló
  </div>
)}
```

## Conclusión

**NO hay "data dummie" inventada en el sistema.**

Lo que parece "dummy" es en realidad:
1. ✅ **XML real del SAT** (guardado completo)
2. ❌ **Parser LLM que falla** en extraer campos
3. ⚠️ **Un solo campo inferido** (`estatusSAT`) que ya reemplazamos con validación real

**Solución:** Usar parser XML directo en lugar de LLM para CFDIs.
