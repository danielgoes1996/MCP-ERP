# 🔄 Flujo Completo de Clasificación de Facturas

## Arquitectura General del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SISTEMA DE CLASIFICACIÓN JERÁRQUICA                       │
│                           (4 Fases + Aprendizaje)                                │
└─────────────────────────────────────────────────────────────────────────────────┘

   FASE 0          FASE 1          FASE 2A         FASE 2B         FASE 3

┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│Learning │ → │ Family  │ → │Subfamily│ → │Embedding│ → │ Account │
│Context  │    │Classifier│   │Classifier│   │ Search  │    │Selector │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
   Claude         Claude         Claude       SentenceT.      Claude
   Sonnet 3.7     Sonnet 3.7     Haiku       (all-MiniLM)    Sonnet 3.7
```

---

## 📤 **INICIO: Upload de Factura XML**

**Archivo:** `api/invoice_classification_api.py`

### Input:
```python
POST /api/classify-invoice
{
  "xml_file": "<archivo CFDI XML>",
  "company_id": 1,
  "session_id": "uuid-12345"
}
```

### Proceso:
1. **Parseo XML CFDI** (`invoice_parser.py`)
   - Extrae: Emisor, Receptor, Conceptos, Totales, Impuestos
   - Valida estructura XML
   - Extrae campos SAT: `clave_prod_serv`, `uso_cfdi`, `metodo_pago`, `forma_pago`

2. **Construye Snapshot** (`classification_service.py:390-415`)
   ```python
   snapshot = {
       'description': "Concepto principal",
       'provider_name': "PROVEEDOR SA",
       'amount': 1000.00,
       'all_conceptos': [
           {
               'descripcion': 'Concepto 1',
               'amount': 840.00,
               'percentage': 84.0,
               'sat_name': 'Proveedores de servicios'
           },
           {
               'descripcion': 'Concepto 2',
               'amount': 160.00,
               'percentage': 16.0,
               'sat_name': 'Logística'
           }
       ]
   }
   ```

---

## 🧠 **FASE 0: Learning Context (Aprendizaje de Contexto)**

**Archivo:** `classification/learning_context_builder.py`
**Modelo:** Claude Sonnet 3.7
**Tiene Prompt:** ✅ SÍ

### Propósito:
Construir contexto del proveedor basado en facturas históricas para mejorar clasificación.

### Input:
```python
{
  'provider_name': 'SERVICIOS COMERCIALES AMAZON MEXICO',
  'provider_rfc': 'ANE140618P37',
  'descripcion': 'Tarifas de almacenamiento'
}
```

### Prompt:
```
Analiza el siguiente proveedor y sus facturas históricas para determinar:
1. Tipo de negocio del proveedor
2. Servicios/productos que típicamente proporciona
3. Patrón de clasificación contable

PROVEEDOR: {provider_name}
RFC: {provider_rfc}

FACTURAS HISTÓRICAS:
{historial de facturas del proveedor}

FACTURA ACTUAL:
{descripcion}

Responde con JSON:
{
  "business_type": "logistics/software/professional_services/etc",
  "typical_services": ["almacenamiento", "logística"],
  "classification_pattern": {
    "most_common_family": "600",
    "most_common_subfamily": "602",
    "confidence": 0.85
  },
  "reasoning": "Amazon proporciona servicios de fulfillment..."
}
```

### Output:
```python
{
  'business_type': 'logistics',
  'typical_services': ['almacenamiento', 'fulfillment', 'FBA'],
  'classification_pattern': {
    'most_common_family': '600',
    'most_common_subfamily': '602',
    'confidence': 0.85
  }
}
```

### Uso:
Este contexto se pasa a Fase 1 y 2A para mejorar clasificación.

---

## 📊 **FASE 1: Family Classification (Clasificación a Familia)**

**Archivo:** `classification/family_classifier.py`
**Modelo:** Claude Sonnet 3.7
**Tiene Prompt:** ✅ SÍ

### Propósito:
Clasificar la factura a nivel de **familia** (100-800): ACTIVO, PASIVO, CAPITAL, INGRESOS, GASTOS, etc.

### Input:
```python
invoice_data = {
  'descripcion': 'Suscripción (84.4%) | Adicionales: Tarifas de almacenamiento',
  'proveedor': 'AMAZON MEXICO',
  'rfc_proveedor': 'ANE140618P37',
  'monto': 612.73,
  'clave_prod_serv': '81141601',
  'uso_cfdi': 'G03',
  'metodo_pago': 'PPD',
  'forma_pago': '03'
}
```

### Prompt Principal:
```
Eres un contador experto mexicano. Clasifica esta factura en UNA FAMILIA del Código Agrupador SAT.

FACTURA:
- Descripción: {descripcion}
- Proveedor: {proveedor}
- Monto: ${monto} MXN
- Clave Prod/Serv: {clave_prod_serv}
- Uso CFDI: {uso_cfdi}

FAMILIAS DISPONIBLES:
100 - ACTIVO CIRCULANTE
200 - ACTIVO FIJO
300 - ACTIVO DIFERIDO
400 - PASIVO
500 - CAPITAL
600 - GASTOS OPERACIÓN
700 - INGRESOS
800 - CUENTAS DE ORDEN

CONTEXTO DEL PROVEEDOR (si disponible):
{learning_context}

REGLAS:
1. Si es un gasto/compra → 600 (GASTOS OPERACIÓN)
2. Si es inventario/material → 100 (ACTIVO CIRCULANTE)
3. Si es activo fijo → 200 (ACTIVO FIJO)
4. Si es ingreso/venta → 700 (INGRESOS)

Responde SOLO con JSON:
{
  "familia_codigo": "600",
  "familia_nombre": "GASTOS OPERACIÓN",
  "confianza": 0.95,
  "razonamiento": "Es un gasto operativo de almacenamiento...",
  "alternativas": [
    {"codigo": "100", "probabilidad": 0.05, "razon": "Podría ser..."}
  ]
}
```

### Output:
```python
{
  'familia_codigo': '600',
  'familia_nombre': 'GASTOS OPERACIÓN',
  'confianza': 0.95,
  'razonamiento': 'Gasto por servicios de almacenamiento'
}
```

### Decisión:
- Si `confianza >= 0.80` → Continuar a Fase 2A
- Si `confianza < 0.80` → Marcar para revisión humana

---

## 🎯 **FASE 2A: Subfamily Classification (Clasificación a Subfamilia)**

**Archivo:** `classification/subfamily_classifier.py`
**Modelo:** Claude Haiku (claude-3-5-haiku-20241022)
**Tiene Prompt:** ✅ SÍ (ACTUALIZADO CON FIX)

### Propósito:
Clasificar la factura a nivel de **subfamilia** (601, 602, 603...): Gastos generales, Gastos de venta, Gastos de administración.

### Input:
```python
invoice_data = {
  'descripcion': 'Suscripción (84.4% - Proveedores servicios aplicación) | Adicionales: Tarifas de almacenamiento de Logística de Amazon',  # ✅ DESCRIPCIÓN ENRIQUECIDA
  'proveedor': 'AMAZON MEXICO',
  'monto': 612.73,
  'metodo_pago': 'PPD',
  'forma_pago': '03'
}

family_code = '600'
family_name = 'GASTOS OPERACIÓN'
family_confidence = 0.95
```

### Prompt Principal (ACTUALIZADO):
```
Clasifica esta factura en UNA SUBFAMILIA del Código Agrupador SAT.

FACTURA:
- Descripción: {descripcion}  ← ✅ AHORA INCLUYE CONCEPTOS ADICIONALES
- Proveedor: {proveedor}
- Monto: ${monto} MXN
- Método de Pago: {metodo_pago}
- Forma de Pago: {forma_pago}

CONTEXTO JERÁRQUICO (Fase 1):
- Familia: {family_code} - {family_name}
- Confianza: {family_confidence}

SUBFAMILIAS DISPONIBLES PARA 600:
601 - Gastos generales
602 - Gastos de venta
603 - Gastos de administración
604 - Gastos financieros

🎯 REGLAS IMPERATIVAS:

**IMPORTANTE: Analiza TODA la descripción completa (incluyendo conceptos adicionales).**

**PASO 1: Busca KEYWORDS DE LOGÍSTICA/VENTA:**
Si encuentras CUALQUIERA de estas palabras → DEBE ser 602:
- "almacenamiento", "storage", "bodega", "warehouse"
- "logística", "logistics", "fulfillment", "FBA"
- "flete", "envío", "shipping", "delivery", "entrega", "paquetería"
- "distribución", "acarreo", "transportación de mercancías"
- "comisión venta", "comisión vendedor", "publicidad", "marketing"

⚠️ IMPORTANTE: Si estas palabras aparecen en "Adicionales:", aún aplica 602
⚠️ EJEMPLO: "Suscripción (84%) | Adicionales: Tarifas de almacenamiento de Amazon" → 602

**EXCEPCIONES (NO son 602, son 601):**
- "mantenimiento vehículo", "afinación", "reparación vehículo" → 601
- "combustible", "gasolina", "diesel" (sin mención de reparto) → 601

**PASO 2: Si NO hay keywords logística, busca SERVICIOS FINANCIEROS:**
- "comisión bancaria", "honorarios", "asesoría", "consultoría" → 603

**PASO 3: Si NO es logística NI financiero:**
- Servicios/software interno, mantenimiento, suministros → 601

Responde SOLO con JSON:
{
  "subfamily_code": "602",
  "subfamily_name": "Gastos de venta",
  "confidence": 0.95,
  "reasoning": "Contiene keywords 'almacenamiento' y 'logística' en adicionales",
  "alternative_subfamilies": [...]
}
```

### Output:
```python
{
  'subfamily_code': '602',
  'subfamily_name': 'Gastos de venta',
  'confidence': 0.95,
  'reasoning': 'Keywords "almacenamiento" y "logística" detectadas en descripción'
}
```

### Decisión:
- Si `confidence >= 0.90` → Continuar a Fase 2B
- Si `confidence < 0.90` → Marcar para revisión humana

---

## 🔍 **FASE 2B: Embedding Search (Búsqueda por Embeddings)**

**Archivo:** `classification/embedding_search.py`
**Modelo:** SentenceTransformer (all-MiniLM-L6-v2)
**Tiene Prompt:** ❌ NO (es búsqueda vectorial)

### Propósito:
Reducir el espacio de búsqueda usando embeddings semánticos y filtrado jerárquico por subfamilia.

### Input:
```python
query = {
  'descripcion': 'Suscripción (84.4%) | Adicionales: Tarifas de almacenamiento de Logística de Amazon',
  'metadata': {
    'clave_prod_serv': '81141601',
    'subfamily_filter': '602'  # ✅ FILTRO POR SUBFAMILIA
  }
}
```

### Proceso:

1. **Genera Embedding del Query**
   ```python
   from sentence_transformers import SentenceTransformer

   model = SentenceTransformer('all-MiniLM-L6-v2')
   query_embedding = model.encode(query['descripcion'], normalize_embeddings=True)
   # vector de 384 dimensiones normalizado
   ```

2. **Búsqueda Vectorial en PostgreSQL con Filtro Jerárquico**
   ```sql
   SELECT
       code,
       name,
       description,
       1 - (embedding <=> %s) AS similarity_score,  -- Cosine similarity
       CASE
           WHEN clave_prod_serv = %s THEN 1.15  -- Boost si coincide clave SAT
           ELSE 1.0
       END AS clave_boost
   FROM sat_account_embeddings
   WHERE
       code LIKE '602.%'  -- ✅ FILTRADO POR SUBFAMILIA (96% reducción)
       AND LENGTH(code) >= 5
   ORDER BY
       (1 - (embedding <=> %s)) * clave_boost DESC
   LIMIT 10;
   ```

3. **Ranking con Boost**
   ```python
   for account in candidates:
       base_score = account['similarity_score']  # 0.0 - 1.0
       clave_boost = account['clave_boost']      # 1.0 o 1.15
       final_score = base_score * clave_boost
   ```

### Output:
```python
[
  {
    'code': '602.72',
    'name': 'Fletes y acarreos',
    'description': 'Gastos por transporte y almacenamiento de mercancías',
    'score': 0.78,
    'distance': 0.22
  },
  {
    'code': '602.46',
    'name': 'Servicios de almacenamiento',
    'score': 0.75,
    'distance': 0.25
  },
  # ... 8 candidatos más
]
```

### Métricas:
- **Reducción de espacio**: ~96% (de 1,200 cuentas a ~50 por subfamilia)
- **Top-K**: 10 candidatos
- **Distancia**: Cosine similarity con embeddings normalizados

---

## 🎓 **FASE 3: Account Selection (Selección de Cuenta Específica)**

**Archivo:** `classification/account_selector.py`
**Modelo:** Claude Sonnet 3.7
**Tiene Prompt:** ✅ SÍ

### Propósito:
Seleccionar la cuenta contable específica (602.72, 603.52, etc.) de entre los 10 candidatos de Fase 2B.

### Input:
```python
invoice_data = {
  'descripcion': 'Suscripción | Adicionales: Tarifas de almacenamiento',
  'proveedor': 'AMAZON MEXICO',
  'monto': 612.73
}

candidates = [
  {'code': '602.72', 'name': 'Fletes y acarreos', 'score': 0.78},
  {'code': '602.46', 'name': 'Servicios de almacenamiento', 'score': 0.75},
  # ... 8 más
]

hierarchical_context = {
  'family': '600 - GASTOS OPERACIÓN',
  'subfamily': '602 - Gastos de venta',
  'family_reasoning': 'Gasto operativo de almacenamiento',
  'subfamily_reasoning': 'Keywords logística detectadas'
}
```

### Prompt Principal:
```
Selecciona LA MEJOR cuenta contable SAT para esta factura.

FACTURA:
- Descripción: {descripcion}
- Proveedor: {proveedor}
- Monto: ${monto} MXN

JERARQUÍA YA DETERMINADA:
- Familia: {family} (Fase 1)
- Subfamilia: {subfamily} (Fase 2A)
- Razonamiento familia: {family_reasoning}
- Razonamiento subfamilia: {subfamily_reasoning}

CANDIDATOS (Top 10 por similitud semántica):
1. 602.72 - Fletes y acarreos (score: 0.78)
   Descripción: Gastos por transporte y almacenamiento de mercancías

2. 602.46 - Servicios de almacenamiento (score: 0.75)
   Descripción: Servicios de bodega y almacenamiento

3. 602.64 - Asistencia técnica (score: 0.68)
   ...

INSTRUCCIONES:
1. Analiza cada candidato considerando:
   - Similitud semántica (score)
   - Descripción detallada de la cuenta
   - Contexto jerárquico previo

2. Valida que la cuenta pertenezca a la subfamilia {subfamily}

3. Selecciona la cuenta MÁS ESPECÍFICA que mejor describe el gasto

Responde SOLO con JSON:
{
  "sat_account_code": "602.46",
  "sat_account_name": "Servicios de almacenamiento",
  "confidence_sat": 0.85,
  "reasoning": "La cuenta 602.46 es más específica para almacenamiento...",
  "validation": {
    "matches_subfamily": true,
    "hierarchy_consistent": true
  }
}
```

### Output:
```python
{
  'sat_account_code': '602.46',
  'sat_account_name': 'Servicios de almacenamiento',
  'confidence_sat': 0.85,
  'reasoning': 'Cuenta específica para servicios de almacenamiento',
  'validation': {
    'matches_subfamily': True,
    'hierarchy_consistent': True
  }
}
```

### Validación Jerárquica:
```python
# Validar que 602.46 pertenece a subfamilia 602
assert '602.46'.startswith('602')  # ✅

# Validar jerarquía completa
600 (Familia) → 602 (Subfamilia) → 602.46 (Cuenta) ✅
```

---

## ✅ **RESULTADO FINAL Y GUARDADO**

**Archivo:** `classification_service.py:580-650`

### Construcción del Resultado:
```python
result = ClassificationResult(
    # Cuenta final
    sat_account_code='602.46',
    sat_account_name='Servicios de almacenamiento',
    confidence_sat=0.85,

    # Metadata jerárquica
    hierarchical_phase1={
        'family_code': '600',
        'family_name': 'GASTOS OPERACIÓN',
        'confidence': 0.95,
        'reasoning': 'Gasto operativo de almacenamiento',
        'model_used': 'claude-sonnet-3-7'
    },

    hierarchical_phase2a={
        'subfamily_code': '602',
        'subfamily_name': 'Gastos de venta',
        'subfamily_confidence': 0.95,
        'reasoning': 'Keywords logística/almacenamiento detectadas',
        'model_used': 'claude-3-5-haiku-20241022'
    },

    hierarchical_phase2b={
        'filtering_method': 'hierarchical_subfamily_based',
        'filter_used': '602',
        'candidates_filtered': 10,
        'embedding_model': 'all-MiniLM-L6-v2',
        'sample_candidates': [...]
    },

    hierarchical_phase3={
        'selected_account': '602.46',
        'confidence': 0.85,
        'reasoning': 'Cuenta específica para almacenamiento',
        'model_used': 'claude-sonnet-3-7'
    },

    # Learning context si existe
    learning_context={
        'business_type': 'logistics',
        'confidence': 0.85
    },

    # Timestamps
    timestamp='2025-01-19T05:45:00Z',
    processing_time_ms=2450
)
```

---

## 📊 **REVISIÓN HUMANA (si es necesario)**

**Archivo:** `frontend/app/invoices/classification/page.tsx`

### Criterios para Revisión:
```python
requires_review = (
    family_confidence < 0.80 or
    subfamily_confidence < 0.90 or
    account_confidence < 0.85 or
    not hierarchy_consistent
)
```

### UI de Revisión:
```
┌────────────────────────────────────────────────────┐
│ 🔍 Revisión de Clasificación                       │
├────────────────────────────────────────────────────┤
│                                                    │
│ Factura: AMAZON MEXICO - $612.73                  │
│ Descripción: Tarifas de almacenamiento            │
│                                                    │
│ Jerarquía Propuesta:                              │
│ 600 → 602 → 602.46                                │
│ GASTOS OPERACIÓN → Gastos venta → Almacenamiento │
│                                                    │
│ Confianza: 85% ⚠️                                  │
│                                                    │
│ ┌─────────────────────┐  ┌──────────────────────┐│
│ │  ✅ Aceptar         │  │  ✏️ Corregir         ││
│ └─────────────────────┘  └──────────────────────┘│
│                                                    │
│ Alternativas Sugeridas:                           │
│ • 602.72 - Fletes y acarreos (75%)               │
│ • 601.64 - Asistencia técnica (60%)              │
└────────────────────────────────────────────────────┘
```

### Acciones del Usuario:
1. **✅ Aceptar**: Guarda clasificación tal cual
2. **✏️ Corregir**: Permite seleccionar otra cuenta
3. **💬 Comentar**: Añade nota de justificación

---

## 💾 **GUARDADO Y APRENDIZAJE**

**Archivo:** `api/invoice_classification_api.py:save_classification`

### Guardado en Base de Datos:
```sql
-- Tabla: invoice_classifications
INSERT INTO invoice_classifications (
    invoice_id,
    session_id,

    -- Cuenta final
    sat_account_code,
    sat_account_name,
    confidence,

    -- Jerarquía completa
    family_code,
    family_name,
    family_confidence,
    family_reasoning,

    subfamily_code,
    subfamily_name,
    subfamily_confidence,
    subfamily_reasoning,

    -- Metadata
    embedding_candidates_count,
    processing_time_ms,
    model_versions,

    -- Aprendizaje
    was_corrected,
    correction_reason,

    -- Audit
    classified_at,
    classified_by
) VALUES (...);
```

### Aprendizaje Continuo (Fase 0):
```python
# Si el usuario corrigió la clasificación
if was_corrected:
    learning_service.record_correction(
        provider_name='AMAZON MEXICO',
        original_classification='602.64',
        corrected_classification='602.46',
        reasoning=correction_reason
    )

    # Este contexto se usará en futuras clasificaciones del mismo proveedor
```

---

## 📈 **RESUMEN DE MODELOS Y PROMPTS**

| Fase | Nombre | Modelo | Prompt | Propósito |
|------|--------|--------|--------|-----------|
| **0** | Learning Context | Claude Sonnet 3.7 | ✅ SÍ | Aprender patrón del proveedor |
| **1** | Family Classifier | Claude Sonnet 3.7 | ✅ SÍ | Clasificar a familia (100-800) |
| **2A** | Subfamily Classifier | Claude Haiku | ✅ SÍ (MEJORADO) | Clasificar a subfamilia (601, 602...) |
| **2B** | Embedding Search | SentenceTransformer | ❌ NO | Búsqueda vectorial con filtro jerárquico |
| **3** | Account Selector | Claude Sonnet 3.7 | ✅ SÍ | Seleccionar cuenta específica |

### Prompts Actualizados:
- ✅ **Fase 2A**: Ahora recibe descripción enriquecida multi-concepto
- ✅ **Fase 2A**: Prompt con keywords explícitas de logística/almacenamiento
- ✅ **Fase 2A**: Búsqueda en "Adicionales:" incluida

---

## 🎯 **MEJORAS IMPLEMENTADAS (Phase 2A Fix)**

### Antes del Fix:
```
Phase 2A INPUT: "Suscripción"
                 ↓
            Clasifica: 601 (Gastos generales) ❌
```

### Después del Fix:
```
Phase 2A INPUT: "Suscripción (84.4%) | Adicionales: Tarifas de almacenamiento de Logística de Amazon"
                 ↓
            Detecta keywords: "almacenamiento", "logística"
                 ↓
            Clasifica: 602 (Gastos de venta) ✅
```

### Cambios Clave:
1. **Enriquecimiento Multi-Concepto** (`classification_service.py:137-182`)
2. **Prompt Keyword-Driven** (`subfamily_classifier.py:297-330`)
3. **Búsqueda en Adicionales** incluida explícitamente

---

## 📊 **MÉTRICAS DE PERFORMANCE**

```
Tiempo Promedio Total: ~2.5 segundos

Fase 0 (Learning):      ~400ms  (Claude Sonnet 3.7)
Fase 1 (Family):        ~600ms  (Claude Sonnet 3.7)
Fase 2A (Subfamily):    ~300ms  (Claude Haiku)
Fase 2B (Embeddings):   ~150ms  (SentenceTransformer + pgvector)
Fase 3 (Account):       ~500ms  (Claude Sonnet 3.7)
Post-processing:        ~50ms

Reducción de Espacio:
- Sin filtro: 1,200 cuentas
- Con subfamilia: ~50 cuentas (96% reducción)
- Top-K final: 10 candidatos

Precisión:
- Family (Fase 1): 95% confianza promedio
- Subfamily (Fase 2A): 90-95% confianza
- Account (Fase 3): 85% confianza promedio
```

---

## 🔄 **FLUJO COMPLETO RESUMIDO**

```
1. 📤 Upload XML
   └─> Parseo CFDI

2. 🧠 Fase 0: Aprender contexto proveedor
   └─> Claude Sonnet 3.7 + Historial

3. 📊 Fase 1: Clasificar familia (600)
   └─> Claude Sonnet 3.7 + Prompt imperativo

4. 🎯 Fase 2A: Clasificar subfamilia (602)
   └─> Claude Haiku + Descripción enriquecida + Keywords

5. 🔍 Fase 2B: Búsqueda embeddings
   └─> SentenceTransformer + Filtro jerárquico (602.*)

6. 🎓 Fase 3: Seleccionar cuenta (602.46)
   └─> Claude Sonnet 3.7 + Top 10 candidatos

7. ✅ Validación jerárquica
   └─> 600 → 602 → 602.46

8. 💾 Guardar resultado
   └─> PostgreSQL + Aprendizaje continuo

9. 📊 UI para revisión (si confianza < umbral)
   └─> React + Aceptar/Corregir
```

---

## 🚀 **PRÓXIMOS PASOS**

- [ ] Validar con auditoría completa (22+ facturas)
- [ ] Monitorear precisión de Phase 2A post-fix
- [ ] Considerar fine-tuning de embeddings específicos del dominio
- [ ] Implementar A/B testing para prompts
- [ ] Dashboard de métricas en tiempo real
