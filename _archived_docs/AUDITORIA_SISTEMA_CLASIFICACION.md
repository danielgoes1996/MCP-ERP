# Auditoría Completa: Sistema de Clasificación Existente vs Necesario

## 📋 Resumen Ejecutivo

**Hallazgo Principal:** Ya tienes **DOS sistemas de clasificación SEPARADOS y FUNCIONALES**:

1. ✅ **Sistema para Expenses/Transacciones Bancarias** - 100% implementado
2. ❌ **Sistema para Facturas CFDI** - 70% implementado (falta integrar)

**La buena noticia:** No tienes que construir desde cero. Solo necesitas **adaptar** el sistema existente de expenses para facturas.

---

## 🔍 PARTE 1: LO QUE YA TIENES (Expenses/Transacciones)

### A. Base de Datos Existente

#### Tabla: `expenses` ✅
```sql
-- Campos relevantes para clasificación:
category VARCHAR(100)               -- Categoría asignada
trend_category TEXT                 -- Categoría de tendencia
ml_features JSON                    -- Features para ML
similarity_scores JSON              -- Scores de similitud
ml_model_version TEXT               -- Versión del modelo
```

#### Tabla: `ai_correction_memory` ✅
```sql
CREATE TABLE ai_correction_memory (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    tenant_id INTEGER,
    user_id INTEGER,

    original_description TEXT NOT NULL,
    normalized_description TEXT NOT NULL,
    ai_category TEXT,              -- Lo que sugirió la IA
    corrected_category TEXT NOT NULL,  -- Lo que corrigió el contador

    movement_kind TEXT,
    amount REAL,
    model_used TEXT,
    notes TEXT,
    raw_transaction TEXT,

    embedding_json TEXT NOT NULL,      -- ← Embedding para búsqueda
    embedding_dimensions INTEGER NOT NULL,
    similarity_hint REAL,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### Tabla: `category_learning_metrics` ✅
```sql
CREATE TABLE category_learning_metrics (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    user_id INTEGER,

    category_name TEXT NOT NULL,

    -- Métricas de precisión
    total_predictions INTEGER DEFAULT 0,
    correct_predictions INTEGER DEFAULT 0,
    accuracy_rate REAL DEFAULT 0.0,
    avg_confidence REAL DEFAULT 0.0,

    -- Patrones aprendidos
    most_common_keywords TEXT,  -- JSON
    most_common_merchants TEXT,  -- JSON
    typical_amount_range TEXT,  -- JSON

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Tabla: `classification_trace` ✅
```sql
CREATE TABLE classification_trace (
    id INTEGER PRIMARY KEY,
    expense_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,

    sat_account_code TEXT,         -- Código SAT
    family_code TEXT,               -- Familia SAT
    confidence_sat REAL,
    confidence_family REAL,

    explanation_short TEXT,
    explanation_detail TEXT,

    tokens TEXT,  -- JSON
    model_version TEXT,
    embedding_version TEXT,
    raw_payload TEXT,  -- JSON

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Tabla: `custom_categories` ✅
```sql
CREATE TABLE custom_categories (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL,

    category_name TEXT NOT NULL,
    category_description TEXT,
    parent_category TEXT,

    -- UI
    color_hex TEXT DEFAULT '#6B7280',
    icon_name TEXT DEFAULT 'folder',

    -- Reglas de matching
    keywords TEXT,  -- JSON
    merchant_patterns TEXT,  -- JSON
    amount_ranges TEXT,  -- JSON

    -- Reglas fiscales
    tax_deductible BOOLEAN DEFAULT TRUE,
    requires_receipt BOOLEAN DEFAULT TRUE,

    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);
```

#### Tabla: `ai_context_memory` ✅
```sql
CREATE TABLE ai_context_memory (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    created_by INTEGER,

    context TEXT,                    -- Contexto del negocio
    onboarding_snapshot TEXT,
    embedding_vector TEXT,           -- Embedding del contexto
    model_name TEXT,

    source TEXT,
    language_detected TEXT,
    context_version INTEGER NOT NULL DEFAULT 1,
    summary TEXT,
    topics TEXT,  -- JSON
    confidence_score REAL,

    last_refresh TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### B. Backend Existente

#### Módulos de Clasificación ✅

**1. `core/ai_pipeline/classification/expense_llm_classifier.py`** ✅
```python
class ExpenseLLMClassifier:
    """Claude Haiku para clasificación SAT"""
    def classify(self, snapshot: Dict, candidates: List[Dict]) -> ClassificationResult
```

**2. `core/accounting/account_catalog.py`** ✅
```python
def retrieve_sat_candidates_by_embedding(
    description: str,
    amount: float,
    top_k: int = 10
) -> List[Dict]:
    """Búsqueda semántica en catálogo SAT"""
```

**3. `core/ai_pipeline/classification/classification_feedback.py`** ✅
```python
def record_feedback(
    conn: Connection,
    tenant_id: int,
    descripcion: str,
    confirmed_sat_code: str,
    suggested_sat_code: Optional[str] = None,
    notes: Optional[str] = None
) -> None
```

**4. `core/reconciliation/embedding_matcher.py`** ✅
```python
class EmbeddingMatcher:
    """Sentence Transformers para matching semántico"""
    def match_batch(...)
```

**5. `core/ai_pipeline/classification/enhanced_categorization_engine.py`** ✅
```python
class EnhancedCategorizationEngine:
    """Motor de categorización con reglas + ML"""
    def categorize_transaction(self, description: str) -> Tuple[str, float, str]
```

**6. `core/ai_pipeline/classification/category_learning_system.py`** ✅
```python
class CategoryLearningSystem:
    """Sistema de aprendizaje con feedback"""
    def process_feedback(self, expense_id: int, feedback_data: Dict)
```

#### APIs Existentes ✅

**`api/category_learning_api.py`** - ✅ COMPLETAMENTE FUNCIONAL

```python
@router.post("/api/category-learning/feedback")
def submit_category_feedback(request: CategoryFeedbackRequest):
    """
    Feedback de categorización
    - accepted: confirmación
    - corrected: corrección con nueva categoría
    - rejected: rechazo
    """

@router.post("/api/category-learning/predict")
def predict_category(request: CategoryPredictionRequest):
    """Predicción de categoría usando ML"""

@router.get("/api/category-learning/metrics")
def get_category_metrics():
    """Métricas de precisión por categoría"""

@router.get("/api/category-learning/stats")
def get_learning_stats():
    """Estadísticas generales del aprendizaje"""
```

### C. Flujo Existente (Expenses)

```
1. Usuario carga gasto/transacción bancaria
   ↓
2. Sistema categoriza (Enhanced Categorization Engine)
   - Usa patrones de regex
   - Usa embeddings si está disponible
   - Usa LLM si está configurado
   ↓
3. Guarda en expenses.category
   ↓
4. Frontend muestra categoría sugerida
   ↓
5. Usuario confirma/corrige
   ↓
6. Si corrige → guarda en ai_correction_memory
   ↓
7. Próxima transacción similar → usa corrección histórica
```

---

## ❌ PARTE 2: LO QUE FALTA (Facturas CFDI)

### A. Base de Datos - GAP Analysis

#### Tabla: `sat_invoices` - ❌ FALTA CAMPO

**Estado actual:**
```sql
-- Tiene estos campos:
parsed_data JSONB           ✅
extracted_data JSONB        ✅
sat_validation_status TEXT  ✅
-- ... pero NO tiene:
accounting_classification JSONB  ❌ FALTA
```

**Necesitas agregar:**
```sql
ALTER TABLE sat_invoices
    ADD COLUMN accounting_classification JSONB;

-- Estructura del JSONB:
{
  "sat_account_code": "601.84.01",
  "family_code": "601",
  "confidence_sat": 0.92,
  "confidence_family": 0.95,
  "status": "pending_confirmation" | "confirmed" | "corrected",
  "classified_at": "2025-11-12T10:30:00Z",
  "confirmed_at": null,
  "corrected_at": null,
  "confirmed_by": null,
  "corrected_sat_code": null,
  "explanation_short": "Compra de materia prima agrícola",
  "explanation_detail": "...",
  "model_version": "claude-3-haiku-20240307",
  "embedding_version": "paraphrase-multilingual-MiniLM-L12-v2",
  "correction_notes": null
}
```

#### Índices Necesarios ❌

```sql
-- Para filtrar por cuenta SAT
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_accounting_code
    ON sat_invoices((accounting_classification->>'sat_account_code'));

-- Para filtrar pendientes de confirmación
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_accounting_status
    ON sat_invoices((accounting_classification->>'status'))
    WHERE accounting_classification->>'status' = 'pending_confirmation';

-- Para búsquedas por tenant
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_company_accounting
    ON sat_invoices(company_id, (accounting_classification->>'status'));
```

### B. Backend - GAP Analysis

#### Archivo: `core/expenses/invoices/universal_invoice_engine_system.py`

**❌ FALTA:** Integración de clasificación

```python
# DESPUÉS de _save_processing_result(), agregar:

async def _classify_invoice_accounting(
    self,
    session_id: str,
    result: Dict[str, Any]
) -> None:
    """
    Clasificación contable usando el sistema existente
    """
    # 1. Verificar UUID
    # 2. Preparar snapshot
    # 3. Buscar candidatos SAT (embeddings)
    # 4. Clasificar con LLM
    # 5. Guardar en accounting_classification
    # 6. Guardar trace
```

**Lógica a implementar:**
- ✅ Ya tienes `ExpenseLLMClassifier` → reutilizar
- ✅ Ya tienes `retrieve_sat_candidates_by_embedding` → reutilizar
- ✅ Ya tienes embedding model cargado → reutilizar
- ❌ Solo falta llamarlo desde Universal Invoice Engine

### C. API Endpoints - GAP Analysis

#### ❌ FALTAN Endpoints para Facturas

Necesitas crear: `api/invoice_classification_api.py`

```python
@router.post("/api/invoice-classification/confirm/{session_id}")
def confirm_classification(session_id: str):
    """Confirmar clasificación de factura"""
    # Similar a category_learning_api.py/feedback
    # pero para sat_invoices

@router.post("/api/invoice-classification/correct/{session_id}")
def correct_classification(session_id: str, corrected_code: str, notes: str):
    """Corregir clasificación de factura"""
    # 1. Actualizar accounting_classification
    # 2. Guardar en ai_correction_memory
    # 3. Actualizar category_learning_metrics

@router.get("/api/invoice-classification/pending")
def get_pending_classifications(company_id: str):
    """Listar facturas pendientes de confirmación"""
    # WHERE accounting_classification->>'status' = 'pending_confirmation'

@router.get("/api/invoice-classification/stats/{company_id}")
def get_classification_stats(company_id: str):
    """Estadísticas de clasificación de facturas"""
    # Análogo a category_learning_api.py/stats
```

#### Modificar Endpoint Existente ✓

**`api/universal_invoice_engine_api.py`** - Actualizar respuesta

```python
# En GET /universal-invoice/sessions/viewer-pro/{tenant_id}
# Agregar accounting_classification a la respuesta

doc = {
    # ... campos existentes ...

    # ✅ NUEVO
    "accountingClassification": session.get('accounting_classification', {
        "status": "not_classified"
    }) if session.get('accounting_classification') else None
}
```

### D. Frontend - GAP Analysis

#### ❌ FALTA: UI de Confirmación/Corrección

**Archivo:** `frontend/app/invoices/page.tsx`

Necesitas agregar:

```typescript
interface InvoiceSession {
  // ... campos existentes ...

  // ✅ NUEVO
  accounting_classification?: {
    sat_account_code: string;
    family_code: string;
    confidence_sat: number;
    status: "pending_confirmation" | "confirmed" | "corrected";
    explanation_short: string;
    explanation_detail: string;
    classified_at: string;
  };
}

// Componente nuevo
function AccountingClassificationBadge({ session }: { session: InvoiceSession }) {
  const classification = session.accounting_classification;

  if (!classification) return null;

  if (classification.status === "pending_confirmation") {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold text-blue-900">Clasificación Sugerida</h4>
        <p className="text-sm text-blue-700">
          {classification.sat_account_code} - {classification.explanation_short}
        </p>
        <p className="text-xs text-blue-600">
          Confianza: {(classification.confidence_sat * 100).toFixed(0)}%
        </p>

        <div className="flex gap-2 mt-3">
          <button onClick={() => handleConfirm(session.id)}>
            ✓ Confirmar
          </button>
          <button onClick={() => handleCorrect(session.id)}>
            ✏️ Corregir
          </button>
        </div>
      </div>
    );
  }

  // Mostrar status confirmed/corrected
}
```

#### ❌ FALTA: Selector de Cuenta SAT

```typescript
function SATAccountSelector({ onSelect }: { onSelect: (code: string) => void }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [accounts, setAccounts] = useState<SATAccount[]>([]);

  // Búsqueda con autocomplete
  useEffect(() => {
    if (searchTerm.length >= 3) {
      fetch(`/api/sat-catalog/search?q=${searchTerm}`)
        .then(res => res.json())
        .then(data => setAccounts(data.results));
    }
  }, [searchTerm]);

  return (
    <div>
      <input
        type="text"
        placeholder="Buscar cuenta SAT..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
      />
      <ul>
        {accounts.map(account => (
          <li key={account.code} onClick={() => onSelect(account.code)}>
            {account.code} - {account.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## 🔄 PARTE 3: MAPEO DE COMPONENTES

### Qué Reutilizar (Expenses → Facturas)

| Componente Existente (Expenses) | Uso en Facturas (CFDI) | Cambios Necesarios |
|---------------------------------|------------------------|-------------------|
| `ExpenseLLMClassifier` ✅ | Clasificar facturas | ✅ Ninguno - reutilizar tal cual |
| `retrieve_sat_candidates_by_embedding` ✅ | Buscar cuentas SAT | ✅ Ninguno - reutilizar tal cual |
| `ai_correction_memory` ✅ | Guardar correcciones | ✅ Ninguno - ya es multi-entidad |
| `category_learning_metrics` ✅ | Métricas de precisión | ✅ Ninguno - ya funciona |
| `classification_trace` ✅ | Auditoría | ⚠️ Cambiar `expense_id` → `session_id` |
| `ai_context_memory` ✅ | Contexto empresa | ✅ Ninguno - ya está por company_id |
| `category_learning_api.py` ✅ | Endpoints de feedback | ⚠️ Crear versión para facturas |
| `EmbeddingMatcher` ✅ | Matching semántico | ✅ Ninguno - útil para conciliación |

### Qué Crear Nuevo

| Componente | Propósito | Complejidad | Tiempo Estimado |
|-----------|-----------|-------------|-----------------|
| Campo `accounting_classification` en `sat_invoices` | Guardar clasificación | Baja | 15 min |
| Método `_classify_invoice_accounting()` | Integrar clasificador | Media | 2 horas |
| API `invoice_classification_api.py` | Endpoints de confirmación/corrección | Media | 2 horas |
| UI `AccountingClassificationBadge` | Mostrar sugerencia | Media | 3 horas |
| UI `SATAccountSelector` | Selector de cuenta SAT | Media | 2 horas |

**Total estimado: ~9 horas (~1 día de desarrollo)**

---

## ✅ PARTE 4: PLAN DE IMPLEMENTACIÓN

### Fase 1: Backend Base (2-3 horas)

**1.1 Migración BD** (15 min)
```sql
-- migrations/2025_11_12_add_accounting_classification.sql
ALTER TABLE sat_invoices
    ADD COLUMN accounting_classification JSONB;

CREATE INDEX idx_universal_invoice_sessions_accounting_code
    ON sat_invoices((accounting_classification->>'sat_account_code'));

CREATE INDEX idx_universal_invoice_sessions_accounting_status
    ON sat_invoices((accounting_classification->>'status'));
```

**1.2 Integración en Universal Invoice Engine** (2 horas)
```python
# core/expenses/invoices/universal_invoice_engine_system.py

async def _save_processing_result(self, session_id, result, ...):
    # ... código existente ...

    # ✅ NUEVO
    asyncio.create_task(
        self._classify_invoice_accounting(session_id, result)
    )

async def _classify_invoice_accounting(self, session_id, result):
    # 1. Extraer datos de result['extracted_data']
    # 2. Preparar snapshot
    # 3. Obtener contexto empresa (reutilizar)
    # 4. Buscar candidatos SAT (reutilizar)
    # 5. Clasificar con LLM (reutilizar)
    # 6. Guardar en accounting_classification
    # 7. Guardar trace
```

**1.3 Testing** (30 min)
- Subir factura de prueba
- Verificar que se clasifica
- Verificar que guarda en BD

### Fase 2: API Endpoints (2 horas)

**2.1 Crear API de clasificación de facturas** (1.5 horas)
```python
# api/invoice_classification_api.py

@router.post("/confirm/{session_id}")
def confirm_classification(session_id: str):
    # Reutilizar lógica de category_learning_api.py

@router.post("/correct/{session_id}")
def correct_classification(session_id: str, corrected_code: str, notes: str):
    # 1. Actualizar sat_invoices
    # 2. Guardar en ai_correction_memory (reutilizar)
    # 3. Actualizar category_learning_metrics (reutilizar)

@router.get("/pending")
def get_pending_classifications(company_id: str):
    # Query simple
```

**2.2 Actualizar API de facturas** (30 min)
```python
# api/universal_invoice_engine_api.py
# Agregar accounting_classification a la respuesta
```

### Fase 3: Frontend (4 horas)

**3.1 Badge de clasificación** (2 horas)
- Componente `AccountingClassificationBadge`
- Botones Confirmar/Corregir
- Modal de explicación detallada

**3.2 Modal de corrección** (2 horas)
- Selector de cuenta SAT con búsqueda
- Campo de notas
- Lógica de envío

### Fase 4: Testing & Refinamiento (1 hora)

- Pruebas end-to-end
- Ajustes de UX
- Documentación

---

## 🎯 PARTE 5: RESPUESTAS AL CHECKLIST

### A. Base de datos ✅

**¿Va en sat_invoices?**
✅ **SÍ** - Es el lugar correcto. Mantiene consistencia.

**¿También en expenses?**
⚠️ **OPCIONAL** - Solo si luego quieres que una factura CFDI se convierta en expense. Por ahora, no es necesario.

**Forma del JSONB:**
✅ Ya definida arriba - usa el mismo formato que `category_learning_api.py` pero adaptado.

**Índices:**
✅ Ya definidos arriba - por código SAT y por status.

**Multi-tenant:**
✅ Ya lo tienes - `company_id` en `sat_invoices` + `tenant_id` en todas las tablas de aprendizaje.

### B. Backend/Pipeline ✅

**¿Clasificación para TODAS las facturas?**
✅ **Recomendado:** Solo para facturas **recibidas** (tipo "I" = Ingreso para el emisor = Gasto para ti).
❌ **Excluir:** Complementos de pago, notas de crédito, facturas emitidas.

**¿Qué pasa con múltiples conceptos?**
✅ **v1 Simple:** Clasificar por primer concepto
⚠️ **v2 Futura:** Clasificar por línea o por concepto dominante (mayor importe)

**Asincronía:**
✅ Ya lo tienes - `asyncio.create_task()` no bloquea upload
✅ Idempotente - revisar `if accounting_classification is None` antes de clasificar

**Límites de coste:**
✅ Usar caché de correcciones históricas (similitud > 0.9 → no llamar LLM)
✅ Batch procesar si suben muchas facturas juntas

**Versionado:**
✅ Guardar `model_version` y `embedding_version` en `accounting_classification`

### C. Endpoints/API ✅

**GET - incluir clasificación:**
✅ Sí - modificar `/universal-invoice/sessions/viewer-pro`

**POST /confirm:**
✅ Rol: Contador o Admin
✅ Body: `{ "session_id": "uis_..." }`

**POST /correct:**
✅ Rol: Contador
✅ Body: `{ "session_id": "uis_...", "corrected_sat_code": "604.01.01", "notes": "..." }`

**Endpoint de reanálisis:**
⚠️ **Nice to have** - para cuando cambies modelo

### D. Frontend/UX ✅

**Dónde mostrar:**
✅ Panel expandido de la factura (dentro del detalle)
✅ Preview en fila: badge pequeño "Cuenta: 601.84.01"

**Flujo confirmación:**
✅ Botón inline - sin modal
✅ Estado visual: badge verde "✓ Clasificado"

**Flujo corrección:**
✅ Modal con selector SAT + notas
✅ Autocomplete por código o descripción

**Bandeja pendientes:**
✅ **NICE TO HAVE** - Vista "Tareas del contador"
⚠️ Por ahora: filtro en vista de facturas

**Manejo errores:**
✅ Badge gris "Sin clasificación" si falla LLM

### E. Observabilidad ✅

**Logging:**
✅ Ya tienes logger en todos los módulos
✅ Agregar: tiempo de clasificación, errores

**Métricas:**
✅ Ya tienes `category_learning_metrics`
✅ Dashboard: reutilizar endpoint `/api/category-learning/stats`

---

## 📊 PARTE 6: COMPARATIVA FINAL

### Tienes (Expenses) → Necesitas (Facturas)

| Componente | Expenses | Facturas CFDI | Acción |
|-----------|----------|---------------|--------|
| **BD - Campo clasificación** | `expenses.category` | `sat_invoices.accounting_classification` | ❌ CREAR |
| **BD - Memoria correcciones** | `ai_correction_memory` | `ai_correction_memory` | ✅ REUTILIZAR |
| **BD - Métricas aprendizaje** | `category_learning_metrics` | `category_learning_metrics` | ✅ REUTILIZAR |
| **BD - Trace auditoría** | `classification_trace` | `classification_trace` | ✅ REUTILIZAR |
| **BD - Contexto empresa** | `ai_context_memory` | `ai_context_memory` | ✅ REUTILIZAR |
| **Backend - Clasificador LLM** | `ExpenseLLMClassifier` | `ExpenseLLMClassifier` | ✅ REUTILIZAR |
| **Backend - Embeddings** | `account_catalog.py` | `account_catalog.py` | ✅ REUTILIZAR |
| **Backend - Feedback** | `classification_feedback.py` | `classification_feedback.py` | ✅ REUTILIZAR |
| **API - Feedback** | `/api/category-learning/feedback` | `/api/invoice-classification/confirm` | ⚠️ ADAPTAR |
| **API - Métricas** | `/api/category-learning/metrics` | `/api/invoice-classification/stats` | ⚠️ ADAPTAR |
| **Frontend - UI confirmación** | ❌ No tiene | AccountingClassificationBadge | ❌ CREAR |

---

## ✅ CONCLUSIÓN

### Ya Tienes (~70% del trabajo):
1. ✅ Toda la infraestructura de BD (tablas de aprendizaje)
2. ✅ Todo el código de clasificación (LLM + embeddings)
3. ✅ Sistema de feedback completo
4. ✅ Endpoints de métricas

### Solo Falta (~30% del trabajo):
1. ❌ Campo en `sat_invoices` (15 min)
2. ❌ Integración en Universal Invoice Engine (2 horas)
3. ❌ Endpoints para facturas (2 horas)
4. ❌ UI de confirmación/corrección (4 horas)

**TOTAL: ~8-9 horas de desarrollo efectivo**

### Próximo Paso Recomendado:
**Empezar con Fase 1** (Backend Base) porque es la base para todo lo demás y puedes testearla de inmediato.

¿Procedo con la implementación de la Fase 1?
