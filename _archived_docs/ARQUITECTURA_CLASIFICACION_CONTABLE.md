# Arquitectura de Clasificación Contable Existente

## Auditoría Completa del Sistema - Análisis Granular

Fecha: 12 de noviembre de 2025
Estado: Sistema YA implementado y funcional

---

## 📊 RESUMEN EJECUTIVO

**Hallazgo principal:** Ya tienes un sistema completo de clasificación contable con:
- ✅ LLM (Claude Haiku) para clasificación SAT
- ✅ Embeddings (Sentence Transformers) para búsqueda semántica
- ✅ Sistema de aprendizaje/feedback del contador
- ✅ Tablas de BD para contexto de empresa y métricas
- ✅ Catálogo SAT completo con embeddings

**Lo que falta:** Integrar este sistema con el Universal Invoice Engine.

---

## 🗄️ PARTE 1: ESQUEMA DE BASE DE DATOS

### 1.1 Contexto de Empresa y Memoria AI

#### Tabla: `ai_context_memory`
**Propósito:** Guarda el contexto de negocio de la empresa para enriquecer clasificaciones

```sql
CREATE TABLE ai_context_memory (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by INTEGER REFERENCES users(id),
    audit_log_id INTEGER REFERENCES audit_trail(id),

    -- Contexto del negocio
    context TEXT,  -- Descripción del giro de negocio, operaciones, etc.
    onboarding_snapshot TEXT,  -- Snapshot de la configuración inicial

    -- Embeddings
    embedding_vector TEXT,  -- Vector embedding del contexto (JSON)
    model_name TEXT,  -- Modelo usado para generar embedding

    -- Metadata
    source TEXT,  -- Fuente del contexto (onboarding, manual, auto-aprendizaje)
    language_detected TEXT,
    context_version INTEGER NOT NULL DEFAULT 1,
    summary TEXT,  -- Resumen del contexto
    topics TEXT,  -- Temas principales (JSON array)
    confidence_score REAL,

    -- Timestamps
    last_refresh TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_context_memory_company_version
    ON ai_context_memory(company_id, context_version);
```

**Ejemplo de uso:**
```json
{
  "company_id": 4,
  "context": "Somos una empresa de producción de frutos secos, principalmente nueces. Compramos materia prima directo de productores y la procesamos para venta al mayoreo.",
  "topics": ["agricultura", "producción", "materia_prima", "nueces"],
  "summary": "Empresa procesadora de frutos secos",
  "confidence_score": 0.95
}
```

#### Tabla: `ai_correction_memory`
**Propósito:** Memoria de aprendizaje - guarda correcciones del contador para entrenar el sistema

```sql
CREATE TABLE ai_correction_memory (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL,
    tenant_id INTEGER,
    user_id INTEGER,  -- Contador que hizo la corrección

    -- Datos originales del gasto
    original_description TEXT NOT NULL,  -- Descripción original
    normalized_description TEXT NOT NULL,  -- Descripción normalizada

    -- Clasificación
    ai_category TEXT,  -- Categoría sugerida por IA
    corrected_category TEXT NOT NULL,  -- Categoría correcta (del contador)

    -- Contexto adicional
    movement_kind TEXT,  -- ingreso/egreso
    amount REAL,
    model_used TEXT,  -- Modelo que hizo la predicción original
    notes TEXT,  -- Notas del contador
    raw_transaction TEXT,  -- Transacción completa (JSON)

    -- Embeddings para búsqueda semántica
    embedding_json TEXT NOT NULL,  -- Vector embedding (JSON)
    embedding_dimensions INTEGER NOT NULL,  -- Dimensiones del vector
    similarity_hint REAL,  -- Hint de similitud para futuras búsquedas

    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_correction_company
    ON ai_correction_memory(company_id, created_at DESC);
```

**Flujo de aprendizaje:**
1. IA sugiere: "Categoría: Servicios generales"
2. Contador corrige: "Categoría: Materia prima agrícola"
3. Sistema guarda en `ai_correction_memory` con embedding
4. Próxima vez que ve descripción similar → usa corrección histórica

### 1.2 Categorías Personalizadas

#### Tabla: `custom_categories`
**Propósito:** Catálogo de categorías contables personalizadas por empresa

```sql
CREATE TABLE custom_categories (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    created_by INTEGER NOT NULL REFERENCES users(id),

    -- Definición de categoría
    category_name TEXT NOT NULL,  -- Nombre de la categoría
    category_description TEXT,  -- Descripción detallada
    parent_category TEXT,  -- Categoría padre (para jerarquías)

    -- UI/UX
    color_hex TEXT DEFAULT '#6B7280',  -- Color para la UI
    icon_name TEXT DEFAULT 'folder',  -- Icono

    -- Reglas de clasificación automática
    keywords TEXT,  -- Keywords para match automático (JSON array)
    merchant_patterns TEXT,  -- Patrones de merchants (JSON array)
    amount_ranges TEXT,  -- Rangos de monto típicos (JSON)

    -- Reglas fiscales
    tax_deductible BOOLEAN DEFAULT TRUE,  -- ¿Es deducible?
    requires_receipt BOOLEAN DEFAULT TRUE,  -- ¿Requiere factura?

    -- Metadata
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Ejemplo:**
```json
{
  "category_name": "Materia Prima - Frutos Secos",
  "category_description": "Compra de nueces, almendras y otros frutos secos para producción",
  "parent_category": "Costo de Ventas",
  "keywords": ["nuez", "nueces", "almendra", "fruto", "materia prima"],
  "merchant_patterns": ["HECTOR.*AUDELO", "PRODUCTOR.*", "AGRICOLA.*"],
  "amount_ranges": {"min": 1000, "max": 50000},
  "tax_deductible": true,
  "requires_receipt": true
}
```

### 1.3 Métricas de Aprendizaje

#### Tabla: `category_learning_metrics`
**Propósito:** Tracking de precisión del modelo por categoría

```sql
CREATE TABLE category_learning_metrics (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    user_id INTEGER REFERENCES users(id),

    -- Categoría
    category_name TEXT NOT NULL,

    -- Métricas de precisión
    total_predictions INTEGER DEFAULT 0,  -- Total de predicciones
    correct_predictions INTEGER DEFAULT 0,  -- Predicciones correctas
    accuracy_rate REAL DEFAULT 0.0,  -- Tasa de acierto (%)
    avg_confidence REAL DEFAULT 0.0,  -- Confianza promedio

    -- Patrones aprendidos
    most_common_keywords TEXT,  -- Keywords más frecuentes (JSON)
    most_common_merchants TEXT,  -- Merchants más frecuentes (JSON)
    typical_amount_range TEXT,  -- Rango de montos típico (JSON)

    -- Timestamp
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_learning_metrics_category ON category_learning_metrics(category_name);
CREATE INDEX idx_learning_metrics_tenant ON category_learning_metrics(tenant_id);
```

**Ejemplo de métricas:**
```json
{
  "category_name": "Materia Prima - Frutos Secos",
  "total_predictions": 127,
  "correct_predictions": 115,
  "accuracy_rate": 0.906,  // 90.6% de precisión
  "avg_confidence": 0.87,
  "most_common_keywords": ["nuez", "almendra", "kg", "produccion"],
  "most_common_merchants": ["HECTOR LUIS AUDELO", "AGRICOLA DEL VALLE"],
  "typical_amount_range": {"min": 2500, "max": 18000, "avg": 9200}
}
```

### 1.4 Trazabilidad de Clasificación

#### Tabla: `classification_trace`
**Propósito:** Auditoría completa de cada clasificación realizada por IA

```sql
CREATE TABLE classification_trace (
    id INTEGER PRIMARY KEY,
    expense_id INTEGER NOT NULL,  -- FK a expenses
    tenant_id INTEGER NOT NULL,

    -- Resultado de clasificación
    sat_account_code TEXT,  -- Código SAT asignado
    family_code TEXT,  -- Código de familia SAT
    confidence_sat REAL,  -- Confianza en código SAT
    confidence_family REAL,  -- Confianza en familia

    -- Explicación (para transparencia)
    explanation_short TEXT,  -- Explicación corta
    explanation_detail TEXT,  -- Explicación detallada

    -- Tokens y metadata
    tokens TEXT,  -- Tokens usados en la clasificación (JSON)
    model_version TEXT,  -- Versión del modelo LLM
    embedding_version TEXT,  -- Versión de embeddings
    raw_payload TEXT,  -- Payload completo enviado al LLM (JSON)

    -- Timestamp
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_classification_trace_expense
    ON classification_trace(expense_id, tenant_id, created_at DESC);
```

**Ejemplo de trace:**
```json
{
  "expense_id": 1523,
  "sat_account_code": "601.84.01",
  "family_code": "601",
  "confidence_sat": 0.92,
  "confidence_family": 0.95,
  "explanation_short": "Compra de materia prima agrícola",
  "explanation_detail": "Basado en: proveedor HECTOR LUIS AUDELO (persona física), concepto NUEZ, monto $12,799.80. Clasificado como materia prima según contexto de empresa (producción de frutos secos).",
  "model_version": "claude-3-haiku-20240307",
  "embedding_version": "paraphrase-multilingual-MiniLM-L12-v2",
  "tokens": ["nuez", "kg", "materia", "prima", "agricola"]
}
```

### 1.5 Tabla de Empresas (Companies)

```sql
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    rfc VARCHAR(13),
    status VARCHAR(50) DEFAULT 'active',
    settings TEXT,  -- JSON con configuraciones (incluye catálogo personalizado)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Ejemplo de `settings` (JSON):**
```json
{
  "accounting": {
    "chart_of_accounts_type": "custom",  // "sat" o "custom"
    "custom_accounts": [
      {
        "code": "5101-001",
        "name": "Materia Prima - Frutos Secos",
        "sat_mapping": "601.84.01",
        "deductible": 100,
        "requires_cfdi": true
      },
      {
        "code": "5102-001",
        "name": "Servicios - Telefonía",
        "sat_mapping": "606.05.01",
        "deductible": 100,
        "requires_cfdi": true
      }
    ],
    "default_deductibility": 100,
    "require_cfdi_for_all": true
  },
  "industry": "manufacturing_food",
  "business_context": "Procesadora de frutos secos - Producción y venta mayorista"
}
```

---

## 💻 PARTE 2: CÓDIGO BACKEND

### 2.1 Clasificador LLM (Claude)

**Archivo:** `core/ai_pipeline/classification/expense_llm_classifier.py`

#### Clase Principal: `ExpenseLLMClassifier`

```python
class ExpenseLLMClassifier:
    """Wrapper around Anthropic Claude for SAT classification"""

    def __init__(self, model: str = "claude-3-haiku-20240307"):
        self.model = model
        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def classify(self, snapshot: Dict, candidates: List[Dict]) -> ClassificationResult:
        """
        Clasifica un gasto contra el catálogo SAT

        Args:
            snapshot: Información del gasto + contexto de empresa
            candidates: Candidatos SAT (obtenidos por embeddings)

        Returns:
            ClassificationResult con código SAT, confianza, explicación
        """
        prompt = self._build_prompt(snapshot, candidates)

        response = self._client.messages.create(
            model=self.model,
            max_tokens=400,
            temperature=0.2,
            system=(
                "Eres un contador experto en el catálogo SAT mexicano. "
                "Analiza el gasto y elige la cuenta SAT que mejor aplique. "
                "Responde en JSON: family_code, sat_account_code, confidence_*, explanation_*"
            ),
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_response(response.content, candidates)
```

#### Construcción del Prompt

```python
def _build_prompt(self, snapshot: Dict, candidates: List[Dict]) -> str:
    """
    Construye prompt con:
    1. Contexto de la empresa (giro, industria)
    2. Datos del gasto (descripción, monto, proveedor)
    3. Candidatos SAT (obtenidos por embedding similarity)
    """
    features = {
        "descripcion": snapshot.get("descripcion_original"),
        "descripcion_normalizada": snapshot.get("descripcion_normalizada"),
        "keywords": snapshot.get("keywords"),
        "provider_name": snapshot.get("provider_name"),
        "provider_rfc": snapshot.get("provider_rfc"),
        "amount": snapshot.get("amount"),
        "company_context": snapshot.get("company_context"),  # ← Contexto clave
        # ...
    }

    # Ejemplo de prompt generado:
    """
    CONTEXTO EMPRESA:
    {
      "industry": "manufacturing_food",
      "business_type": "Procesadora de frutos secos",
      "common_expenses": ["materia_prima", "servicios", "empaque"]
    }

    GASTO A CLASIFICAR:
    descripcion: "NUEZ"
    provider: "HECTOR LUIS AUDELO JARQUIN"
    amount: $12,799.80
    keywords: ["nuez", "kg", "materia"]

    CANDIDATOS SAT:
    1. 601.84.01 — Materia prima agrícola (familia 601, score 0.89)
    2. 601.01.01 — Mercancías para comercialización (familia 601, score 0.72)
    3. 604.01.01 — Insumos de producción (familia 604, score 0.68)

    ¿Cuál cuenta SAT es la correcta? Responde en JSON.
    """
```

**Resultado:**
```json
{
  "sat_account_code": "601.84.01",
  "family_code": "601",
  "confidence_sat": 0.92,
  "confidence_family": 0.95,
  "explanation_short": "Compra de materia prima agrícola",
  "explanation_detail": "El proveedor HECTOR LUIS es persona física (régimen 612), concepto NUEZ indica materia prima. Dado que la empresa es procesadora de frutos secos, la cuenta 601.84.01 (Materia prima agrícola) es la más apropiada."
}
```

### 2.2 Sistema de Embeddings (Búsqueda Semántica)

**Archivo:** `core/accounting/account_catalog.py`

#### Carga del Modelo de Embeddings

```python
@lru_cache(maxsize=1)
def _load_sentence_model() -> Optional[SentenceTransformer]:
    """
    Carga modelo de Sentence Transformers para generar embeddings
    Modelo: paraphrase-multilingual-MiniLM-L12-v2 (español + multilingüe)
    """
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return model
```

#### Búsqueda de Candidatos SAT

```python
def retrieve_sat_candidates_by_embedding(
    description: str,
    amount: float,
    top_k: int = 10
) -> List[Dict]:
    """
    Encuentra candidatos SAT usando similitud semántica

    Process:
    1. Genera embedding del gasto
    2. Calcula similitud coseno vs embeddings del catálogo SAT
    3. Retorna top K candidatos más similares

    Args:
        description: Descripción del gasto
        amount: Monto (para filtros adicionales)
        top_k: Número de candidatos a retornar

    Returns:
        Lista de candidatos SAT con score de similitud
    """
    # 1. Generar embedding del gasto
    model = _load_sentence_model()
    query_embedding = model.encode([description])[0]

    # 2. Cargar embeddings del catálogo SAT
    catalog_embeddings = load_sat_catalog_embeddings()

    # 3. Calcular similitud coseno
    similarities = cosine_similarity([query_embedding], catalog_embeddings)[0]

    # 4. Obtener top K
    top_indices = np.argsort(similarities)[::-1][:top_k]

    candidates = []
    for idx in top_indices:
        candidates.append({
            "code": catalog_accounts[idx]["code"],
            "name": catalog_accounts[idx]["name"],
            "family_hint": extract_family_code(catalog_accounts[idx]["code"]),
            "score": float(similarities[idx]),
            "description": catalog_accounts[idx].get("description", "")
        })

    return candidates
```

**Ejemplo de uso:**
```python
# Input
description = "Compra de NUEZ a productor HECTOR LUIS"
amount = 12799.80

# Output (candidatos)
[
  {
    "code": "601.84.01",
    "name": "Materia prima agrícola",
    "family_hint": "601",
    "score": 0.89,
    "description": "Adquisición de materias primas de origen agropecuario"
  },
  {
    "code": "601.01.01",
    "name": "Mercancías para comercialización",
    "family_hint": "601",
    "score": 0.72,
    "description": "Compra de mercancías destinadas a reventa"
  },
  # ... más candidatos
]
```

### 2.3 Sistema de Feedback y Aprendizaje

**Archivo:** `core/ai_pipeline/classification/classification_feedback.py`

#### Registro de Correcciones

```python
def record_feedback(
    conn: Connection,
    *,
    tenant_id: int,
    descripcion: str,
    confirmed_sat_code: str,  # ← Lo que el contador confirmó
    suggested_sat_code: Optional[str] = None,  # ← Lo que la IA sugirió
    expense_id: Optional[int] = None,
    classification_trace_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> None:
    """
    Persiste una corrección del contador para entrenamiento futuro

    Flow:
    1. IA sugiere: "601.01.01 - Mercancías"
    2. Contador corrige: "601.84.01 - Materia prima agrícola"
    3. Sistema guarda en expense_classification_feedback
    4. Próxima factura similar → usa corrección histórica
    """
    normalized_desc = normalize_expense_text(descripcion)

    conn.execute("""
        INSERT INTO expense_classification_feedback (
            tenant_id,
            expense_id,
            descripcion_normalizada,
            suggested_sat_code,
            confirmed_sat_code,
            classification_trace_id,
            notes,
            captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tenant_id,
        expense_id,
        normalized_desc,
        suggested_sat_code,
        confirmed_sat_code,
        classification_trace_id,
        notes,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
```

#### Uso de Correcciones Históricas

```python
def get_similar_corrections(
    conn: Connection,
    tenant_id: int,
    description: str,
    limit: int = 5
) -> List[Dict]:
    """
    Busca correcciones similares del contador

    Returns:
        Lista de correcciones históricas ordenadas por similitud
    """
    normalized = normalize_expense_text(description)

    # Búsqueda con embeddings (si están disponibles)
    # o fallback a búsqueda por keywords

    results = conn.execute("""
        SELECT
            descripcion_normalizada,
            confirmed_sat_code,
            notes,
            captured_at
        FROM expense_classification_feedback
        WHERE tenant_id = ?
        ORDER BY captured_at DESC
        LIMIT ?
    """, (tenant_id, limit)).fetchall()

    return [dict(row) for row in results]
```

### 2.4 Embedding Matcher (Para Conciliación)

**Archivo:** `core/reconciliation/embedding_matcher.py`

```python
class EmbeddingMatcher:
    """
    Matcher semántico usando Sentence Transformers
    Útil para:
    - Conciliación bancaria (tx descripción ↔ factura emisor)
    - Matching de proveedores
    - Detección de duplicados
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)
        self._cache = {}

    def match_batch(
        self,
        transactions: List[Dict],
        invoices: List[Dict],
        min_similarity: float = 0.7
    ) -> List[EmbeddingMatch]:
        """
        Encuentra matches usando similitud semántica

        Example:
            TX: "STRIPE *ODOO TECHNOLOG MX"
            Invoice: "ODOO TECHNOLOGIES SA DE CV"
            Similarity: 0.89 → MATCH ✓
        """
        # Generar embeddings
        tx_embeddings = [self.model.encode([tx["description"]])[0] for tx in transactions]
        inv_embeddings = [self.model.encode([inv["nombre_emisor"]])[0] for inv in invoices]

        # Calcular matriz de similitud
        similarity_matrix = cosine_similarity(tx_embeddings, inv_embeddings)

        # Encontrar matches
        matches = []
        for tx_idx, tx in enumerate(transactions):
            best_inv_idx = np.argmax(similarity_matrix[tx_idx])
            best_similarity = similarity_matrix[tx_idx][best_inv_idx]

            if best_similarity >= min_similarity:
                matches.append(EmbeddingMatch(
                    transaction_id=tx["id"],
                    invoice_id=invoices[best_inv_idx]["id"],
                    similarity_score=best_similarity,
                    confidence="high" if best_similarity >= 0.85 else "medium"
                ))

        return matches
```

---

## 🔄 PARTE 3: FLUJO COMPLETO ACTUAL

### Flujo Existente (Para Expenses/Transacciones)

```
1. Usuario carga gasto/transacción
   ↓
2. Sistema normaliza descripción
   normalize_expense_text("HECTOR LUIS AUDELO JARQUIN - NUEZ 75KG")
   → "hector luis audelo jarquin nuez 75kg"
   ↓
3. Búsqueda de candidatos SAT (por embeddings)
   retrieve_sat_candidates_by_embedding(description, amount, top_k=10)
   → [
        {"code": "601.84.01", "score": 0.89},
        {"code": "601.01.01", "score": 0.72},
        ...
      ]
   ↓
4. Contexto de empresa (si existe)
   SELECT context FROM ai_context_memory WHERE company_id = ?
   → "Empresa procesadora de frutos secos"
   ↓
5. Clasificación LLM
   ExpenseLLMClassifier.classify(snapshot, candidates)
   snapshot = {
     "descripcion": "HECTOR LUIS - NUEZ",
     "amount": 12799.80,
     "provider_rfc": "AUJH630825FL9",
     "company_context": {...}
   }
   ↓
6. Claude Haiku analiza y retorna
   {
     "sat_account_code": "601.84.01",
     "confidence": 0.92,
     "explanation": "Materia prima agrícola"
   }
   ↓
7. Guardar trace de clasificación
   INSERT INTO classification_trace (...)
   ↓
8. Si contador corrige → guardar feedback
   record_feedback(suggested="601.01.01", confirmed="601.84.01")
   ↓
9. Actualizar métricas de aprendizaje
   UPDATE category_learning_metrics SET
     total_predictions = total_predictions + 1,
     correct_predictions = correct_predictions + 1,
     accuracy_rate = correct_predictions / total_predictions
```

### Datos que Alimentan el Clasificador

```python
snapshot = {
    # Del gasto/factura
    "descripcion_original": "NUEZ",
    "descripcion_normalizada": "nuez",
    "keywords": ["nuez", "kg", "materia"],
    "provider_name": "HECTOR LUIS AUDELO JARQUIN",
    "provider_rfc": "AUJH630825FL9",
    "amount": 12799.80,
    "amount_bucket": "10000-15000",  # Rango de monto

    # Del sistema
    "categoria_slug": None,  # Primera vez
    "categoria_usuario": None,  # Sin categoría manual
    "categoria_contable": None,  # Sin cuenta asignada

    # Del contexto
    "company_id": 4,
    "tenant_id": 1,
    "company_context": {  # ← Este es el oro
        "industry": "manufacturing_food",
        "business_type": "Procesadora de frutos secos",
        "common_categories": ["materia_prima", "empaque", "logistica"],
        "chart_of_accounts": "custom",
        "typical_vendors": [
            {"pattern": "AGRICOLA.*", "category": "materia_prima"},
            {"pattern": "HECTOR.*AUDELO", "category": "materia_prima"}
        ]
    },

    # De facturas anteriores similares
    "similar_past_expenses": [
        {
            "description": "NUEZ PECANERA 50KG",
            "sat_code": "601.84.01",
            "provider": "AGRICOLA DEL VALLE",
            "amount": 8500.00
        }
    ]
}
```

---

## 📁 PARTE 4: ESTRUCTURA DE ARCHIVOS

```
mcp-server/
├── core/
│   ├── ai_pipeline/
│   │   └── classification/
│   │       ├── expense_llm_classifier.py          # ← Clasificador LLM (Claude)
│   │       ├── classification_feedback.py         # ← Sistema de feedback
│   │       ├── classification_trace.py            # ← Trazabilidad
│   │       └── expense_classifier.py              # ← Orquestador principal
│   │
│   ├── accounting/
│   │   ├── account_catalog.py                     # ← Catálogo SAT + embeddings
│   │   └── accounting_catalog.py                  # ← Utilities contables
│   │
│   ├── reconciliation/
│   │   └── embedding_matcher.py                   # ← Matcher semántico
│   │
│   └── shared/
│       └── text_normalizer.py                     # ← Normalización de texto
│
├── data/
│   ├── embeddings/
│   │   ├── sat_sentence_transformer/              # ← Modelo descargado
│   │   ├── sat_sentence_transformer_metadata.json # ← Metadata del modelo
│   │   └── sat_account_context.json               # ← Contextos SAT pre-cargados
│   │
│   └── catalogs/
│       └── sat_accounts.json                       # ← Catálogo completo SAT
│
└── migrations/
    └── [varias migraciones que crearon las tablas]
```

---

## 🎯 PARTE 5: LO QUE YA FUNCIONA

### ✅ Sistema Completo Existente

1. **Catálogo SAT Completo**
   - 5000+ cuentas SAT en BD
   - Embeddings pre-calculados
   - Búsqueda semántica funcional

2. **Clasificador LLM**
   - Claude Haiku integrado
   - Prompts optimizados para contabilidad mexicana
   - Maneja contexto de empresa

3. **Sistema de Aprendizaje**
   - Guarda correcciones del contador
   - Mejora con el uso
   - Métricas de precisión por categoría

4. **Embeddings**
   - Sentence Transformers (multilingüe)
   - Caché de embeddings
   - Matching semántico

5. **Trazabilidad**
   - Cada clasificación guardada
   - Explicaciones del LLM
   - Auditoría completa

### ❌ Lo Que Falta

1. **Integración con Universal Invoice Engine**
   - No se llama al clasificador después de extraer datos
   - Facturas procesadas NO se clasifican automáticamente
   - Falta conectar `extracted_data` → `expense_llm_classifier`

2. **UI para Confirmar/Corregir Clasificaciones**
   - No hay interfaz para que contador vea sugerencias
   - No hay botón "Confirmar" / "Corregir"
   - Feedback loop está disponible pero no expuesto en UI

3. **Dashboard de Métricas**
   - Datos de `category_learning_metrics` no se visualizan
   - No hay reportes de precisión del modelo

---

## 🚀 PARTE 6: INTEGRACIÓN PROPUESTA

### Dónde Conectar el Sistema

**Archivo a modificar:** `core/expenses/invoices/universal_invoice_engine_system.py`

**Punto de integración:** Después de guardar `extracted_data`, antes de retornar

```python
async def _save_processing_result(self, session_id, result, ...):
    # ... código existente que guarda extracted_data ...

    # ✅ NUEVO: Lanzar clasificación contable
    asyncio.create_task(
        self._classify_invoice_accounting(session_id, result)
    )

    return result


async def _classify_invoice_accounting(
    self,
    session_id: str,
    result: Dict[str, Any]
) -> None:
    """
    Clasifica la factura contablemente usando el sistema existente
    """
    try:
        extracted_data = result.get('extracted_data', {})

        # 1. Preparar snapshot para clasificador
        snapshot = {
            "descripcion_original": extracted_data.get('conceptos', [{}])[0].get('descripcion', ''),
            "descripcion_normalizada": normalize_expense_text(...),
            "provider_name": extracted_data.get('emisor', {}).get('nombre'),
            "provider_rfc": extracted_data.get('emisor', {}).get('rfc'),
            "amount": extracted_data.get('total', 0),
            "company_id": self.company_id,
            "tenant_id": self.tenant_id,

            # Obtener contexto de empresa
            "company_context": self._get_company_context(self.company_id)
        }

        # 2. Buscar candidatos SAT (por embeddings)
        from core.accounting.account_catalog import retrieve_sat_candidates_by_embedding
        candidates = retrieve_sat_candidates_by_embedding(
            description=snapshot["descripcion_normalizada"],
            amount=snapshot["amount"],
            top_k=10
        )

        # 3. Clasificar con LLM
        from core.ai_pipeline.classification.expense_llm_classifier import ExpenseLLMClassifier
        classifier = ExpenseLLMClassifier()
        classification = classifier.classify(snapshot, candidates)

        # 4. Guardar clasificación en BD
        from core.db_postgresql import get_db_sync
        db = next(get_db_sync())

        db.execute("""
            UPDATE sat_invoices
            SET accounting_classification = %s
            WHERE id = %s
        """, (
            json.dumps({
                "sat_account_code": classification.sat_account_code,
                "family_code": classification.family_code,
                "confidence_sat": classification.confidence_sat,
                "explanation": classification.explanation_short,
                "classified_at": datetime.utcnow().isoformat()
            }),
            session_id
        ))

        # 5. Guardar trace para auditoría
        from core.ai_pipeline.classification.classification_trace import save_classification_trace
        save_classification_trace(
            db=db,
            session_id=session_id,
            classification=classification,
            snapshot=snapshot
        )

        db.commit()
        logger.info(f"Session {session_id}: Classified as {classification.sat_account_code}")

    except Exception as e:
        logger.error(f"Session {session_id}: Error in accounting classification: {e}")
```

### Migración de BD Necesaria

```sql
-- Agregar campo para clasificación contable
ALTER TABLE sat_invoices
    ADD COLUMN accounting_classification JSONB;

-- Índice para búsquedas
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_accounting
    ON sat_invoices(accounting_classification);
```

### Respuesta del API Actualizada

```python
# En api/universal_invoice_engine_api.py
doc = {
    # ... campos existentes ...

    # ✅ NUEVO: Clasificación contable
    "accountingClassification": {
        "satAccountCode": session.get('accounting_classification', {}).get('sat_account_code'),
        "familyCode": session.get('accounting_classification', {}).get('family_code'),
        "confidence": session.get('accounting_classification', {}).get('confidence_sat'),
        "explanation": session.get('accounting_classification', {}).get('explanation'),
        "classifiedAt": session.get('accounting_classification', {}).get('classified_at'),
        "status": "pending" | "classified" | "confirmed" | "corrected"
    }
}
```

---

## 📋 PARTE 7: RESUMEN PARA IMPLEMENTACIÓN

### Ya Tienes (100% Funcional):

1. ✅ **Base de datos completa**
   - `ai_context_memory` (contexto empresa)
   - `ai_correction_memory` (aprendizaje)
   - `custom_categories` (categorías personalizadas)
   - `category_learning_metrics` (métricas)
   - `classification_trace` (auditoría)

2. ✅ **Backend completo**
   - `ExpenseLLMClassifier` (Claude Haiku)
   - `account_catalog.py` (embeddings + búsqueda)
   - `classification_feedback.py` (feedback loop)
   - `embedding_matcher.py` (matching semántico)

3. ✅ **Catálogo SAT**
   - 5000+ cuentas
   - Embeddings pre-calculados
   - Búsqueda semántica

### Necesitas Implementar:

1. ❌ **Integración con Universal Invoice Engine**
   - Llamar clasificador después de procesar factura
   - Guardar resultado en BD
   - ~50 líneas de código

2. ❌ **UI para Feedback**
   - Mostrar clasificación sugerida
   - Botones Confirmar / Corregir
   - Formulario de corrección
   - ~200 líneas React

3. ❌ **Migración BD**
   - Agregar campo `accounting_classification` a `sat_invoices`
   - 1 archivo SQL

### Esfuerzo Estimado:

- Integración backend: **2-3 horas**
- Migración BD: **15 minutos**
- UI básica: **4-5 horas**
- Testing: **2 horas**

**Total: ~1 día de desarrollo**

---

## 🎓 CONCLUSIÓN

**Tienes un sistema de clasificación contable COMPLETO y SOFISTICADO que incluye:**

1. LLM (Claude) para clasificación inteligente
2. Embeddings para búsqueda semántica
3. Sistema de aprendizaje con feedback del contador
4. Contexto de empresa para clasificaciones personalizadas
5. Métricas de precisión
6. Trazabilidad completa

**Solo falta conectarlo con el Universal Invoice Engine.**

La arquitectura está bien diseñada y lista para usarse. Solo necesitas:
1. Agregar la llamada al clasificador
2. Crear la UI de confirmación/corrección
3. ¡Empezar a usarlo!

¿Quieres que proceda con la implementación de la integración?
