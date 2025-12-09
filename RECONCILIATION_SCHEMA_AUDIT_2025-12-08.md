# 🔍 AUDITORÍA DE ESQUEMAS - SISTEMA DE RECONCILIACIÓN TRIPARTITA
**Fecha**: 2025-12-08
**Database**: PostgreSQL (`mcp_system`)
**Propósito**: Análisis de tablas existentes para implementar reconciliación inteligente de 3 fuentes

---

## 📊 RESUMEN EJECUTIVO

### Hallazgos Principales
1. ✅ **Las 3 tablas necesarias EXISTEN en PostgreSQL**
   - `manual_expenses` (35 columnas, n/d records)
   - `bank_transactions` (20 columnas, n/d records)
   - `sat_invoices` (50 columnas, 10 records)

2. ⚠️ **GAPS CRÍTICOS identificados**:
   - Faltan columnas de reconciliación en TODAS las tablas
   - Falta `vendor_rfc` en `bank_transactions` (solo tiene `vendor_normalized` como texto)
   - No hay foreign keys entre tablas
   - No hay índices para matching de RFC + fecha + monto

3. ✅ **Campos existentes aprovechables**:
   - `sat_invoices` tiene `supplier_embedding` (vector para búsqueda semántica)
   - `sat_invoices.parsed_data` contiene RFC del emisor
   - Todos tienen campos de monto y fecha

---

## 🗂️ TABLA 1: `manual_expenses`

### Schema Actual (35 columnas)
```sql
CREATE TABLE manual_expenses (
    -- Identificadores
    id                          SERIAL PRIMARY KEY,
    provider_name               VARCHAR(255) NOT NULL,
    provider_rfc                VARCHAR(13),               -- ✅ EXISTE para matching

    -- Montos
    amount                      NUMERIC(15,2) NOT NULL,    -- ✅ Para matching

    -- Fechas
    date                        TIMESTAMPTZ NOT NULL,      -- ✅ Para matching
    created_at                  TIMESTAMPTZ,
    updated_at                  TIMESTAMPTZ,

    -- Clasificación Contable
    category_code               VARCHAR(20),
    category_name               VARCHAR(255),
    subcategory                 VARCHAR(255),
    account_code                VARCHAR(50),

    -- Metadata
    description                 TEXT,
    notes                       TEXT,
    invoice_number              VARCHAR(100),
    payment_method              VARCHAR(50),
    tax_percentage              NUMERIC(5,2),
    tax_amount                  NUMERIC(15,2),
    subtotal                    NUMERIC(15,2),
    currency                    VARCHAR(3) DEFAULT 'MXN',
    exchange_rate               NUMERIC(10,4),

    -- Archivos adjuntos
    attachments                 JSONB,

    -- Usuario y tenant
    tenant_id                   INTEGER NOT NULL,
    user_id                     INTEGER,

    -- Procesamiento
    status                      VARCHAR(50) DEFAULT 'pending',
    metadata                    JSONB,

    -- Campos adicionales
    project_id                  INTEGER,
    cost_center                 VARCHAR(100),
    approved_by                 INTEGER,
    approved_at                 TIMESTAMPTZ,
    payment_date                TIMESTAMPTZ,
    reference_number            VARCHAR(100),
    tags                        VARCHAR[],
    is_recurring                BOOLEAN DEFAULT FALSE,
    recurring_frequency         VARCHAR(50)
);
```

### ❌ CAMPOS FALTANTES para Reconciliación
```sql
-- CRÍTICOS
sat_invoice_id              TEXT,                    -- FK a sat_invoices.id
bank_transaction_id         INTEGER,                 -- FK a bank_transactions.id
reconciliation_status       VARCHAR(20),             -- 'matched', 'partial', 'unmatched', 'conflict'
reconciliation_confidence   NUMERIC(3,2),            -- 0.00 a 1.00
reconciliation_layer        VARCHAR(10),             -- 'layer0_sql', 'layer1_math', 'layer2_vector', 'layer3_llm'
reconciliation_date         TIMESTAMPTZ,
reconciliation_notes        TEXT,

-- ÚTILES
match_explanation           TEXT,                    -- Explicación del match (ej: "Layer 0: RFC+monto+fecha exactos")
requires_manual_review      BOOLEAN DEFAULT FALSE,
reviewed_by                 INTEGER,
reviewed_at                 TIMESTAMPTZ,
original_classification     JSONB,                   -- Backup del classifier
manual_override             BOOLEAN DEFAULT FALSE
```

---

## 🗂️ TABLA 2: `bank_transactions`

### Schema Actual (20 columnas)
```sql
CREATE TABLE bank_transactions (
    -- Identificadores
    id                          SERIAL PRIMARY KEY,
    statement_id                INTEGER NOT NULL,          -- FK a bank_statements
    transaction_id              VARCHAR(100),

    -- Montos
    amount                      NUMERIC(15,2) NOT NULL,    -- ✅ Para matching
    balance_after               NUMERIC(15,2),

    -- Fechas
    transaction_date            DATE NOT NULL,             -- ✅ Para matching
    value_date                  DATE,

    -- Descripción y Vendor
    description                 TEXT,
    vendor_normalized           VARCHAR(255),              -- ⚠️ TEXTO, no RFC!

    -- Categorización
    transaction_category        VARCHAR(100),
    movement_kind               VARCHAR(50),               -- 'ingreso', 'gasto', etc.

    -- Metadata bancaria
    reference                   VARCHAR(255),
    check_number                VARCHAR(50),
    currency                    VARCHAR(3) DEFAULT 'MXN',

    -- Timestamps
    created_at                  TIMESTAMPTZ,
    updated_at                  TIMESTAMPTZ,

    -- Sistema
    tenant_id                   INTEGER,
    metadata                    JSONB,
    classification_status       VARCHAR(50),
    notes                       TEXT
);
```

### ❌ CAMPOS FALTANTES para Reconciliación
```sql
-- CRÍTICO: VENDOR RFC
vendor_rfc                  VARCHAR(13),               -- ⚠️ CRÍTICO - actualmente solo hay vendor_normalized (texto)

-- Reconciliación
sat_invoice_id              TEXT,                      -- FK a sat_invoices.id
manual_expense_id           INTEGER,                   -- FK a manual_expenses.id
reconciliation_status       VARCHAR(20),
reconciliation_confidence   NUMERIC(3,2),
reconciliation_layer        VARCHAR(10),
reconciliation_date         TIMESTAMPTZ,
reconciliation_notes        TEXT,

-- Útiles
match_explanation           TEXT,
requires_manual_review      BOOLEAN DEFAULT FALSE,
reviewed_by                 INTEGER,
reviewed_at                 TIMESTAMPTZ,
vendor_rfc_source           VARCHAR(20),               -- 'extracted', 'manual', 'sat_match', 'llm'
vendor_rfc_confidence       NUMERIC(3,2)
```

### 🚨 PROBLEMA CRÍTICO: `vendor_normalized` vs `vendor_rfc`
- **Actual**: `vendor_normalized` = "GASOLINERA LA ESTRELLA SA DE CV" (texto libre)
- **Necesario**: `vendor_rfc` = "GLE850525ABC" (identificador único del SAT)
- **Impacto**: Sin RFC, Layer 0 (SQL matching exacto) NO puede funcionar
- **Solución**: Necesitamos extraer RFCs de las descripciones bancarias o enlazar con SAT

---

## 🗂️ TABLA 3: `sat_invoices`

### Schema Actual (50 columnas)
```sql
CREATE TABLE sat_invoices (
    -- Identificadores
    id                              TEXT PRIMARY KEY,
    company_id                      TEXT NOT NULL,
    user_id                         TEXT,

    -- Archivo
    invoice_file_path               TEXT NOT NULL,
    original_filename               TEXT NOT NULL,
    file_hash                       TEXT NOT NULL,

    -- Estado
    status                          TEXT,
    extraction_status               TEXT,

    -- Timestamps
    created_at                      TIMESTAMP NOT NULL,
    updated_at                      TIMESTAMP,
    completed_at                    TIMESTAMP,

    -- Datos extraídos (JSONB)
    parsed_data                     JSONB,              -- ✅ Contiene RFC emisor, fecha, conceptos
    extracted_data                  JSONB,

    -- Procesamiento
    detected_format                 TEXT,
    parser_used                     TEXT,
    extraction_confidence           DOUBLE PRECISION,
    validation_score                DOUBLE PRECISION,
    overall_quality_score           DOUBLE PRECISION,
    processing_time_ms              INTEGER,

    -- Validación
    template_match                  JSONB,
    validation_results              JSONB,
    validation_errors               JSONB,
    validation_rules                JSONB,
    processing_metrics              JSONB,
    error_message                   TEXT,

    -- Validación SAT (importante!)
    sat_validation_status           TEXT,
    sat_codigo_estatus              TEXT,
    sat_es_cancelable               BOOLEAN,
    sat_estado                      TEXT,
    sat_validacion_efos             TEXT,
    sat_verified_at                 TIMESTAMP,
    sat_last_check_at               TIMESTAMP,
    sat_verification_error          TEXT,
    sat_verification_url            TEXT,

    -- Clasificación Contable
    accounting_classification       JSONB,              -- ✅ Contiene sat_account_code

    -- Importación
    source                          TEXT,
    batch_id                        VARCHAR,

    -- Montos
    amount_total                    NUMERIC,            -- ✅ Para matching
    amount_subtotal                 NUMERIC,
    amount_iva                      NUMERIC,
    amount_pending                  NUMERIC,

    -- Pago
    payment_status                  VARCHAR,
    amount_paid                     NUMERIC,
    currency                        VARCHAR,
    exchange_rate                   NUMERIC,
    last_payment_date               TIMESTAMP,
    last_payment_amount             NUMERIC,
    payment_updated_at              TIMESTAMP,
    payment_updated_by              INTEGER,

    -- Búsqueda semántica
    supplier_embedding              VECTOR                -- ✅ Para Layer 2 (vector similarity)
);
```

### Campos en `parsed_data` (JSONB)
```json
{
  "uuid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
  "emisor": {
    "rfc": "GLE850525ABC",                    // ✅ CRÍTICO para matching
    "nombre": "GASOLINERA LA ESTRELLA SA"
  },
  "receptor": {
    "rfc": "POL210218264",
    "nombre": "CARRETA VERDE SA"
  },
  "fecha": "2025-12-01T10:30:00",            // ✅ Para matching
  "total": 1234.56,                          // ✅ Para matching
  "subtotal": 1064.10,
  "iva": 170.46,
  "conceptos": [...]
}
```

### ❌ CAMPOS FALTANTES para Reconciliación
```sql
-- Reconciliación
bank_transaction_id         INTEGER,                -- FK a bank_transactions.id
manual_expense_id           INTEGER,                -- FK a manual_expenses.id
reconciliation_status       VARCHAR(20),
reconciliation_confidence   NUMERIC(3,2),
reconciliation_layer        VARCHAR(10),
reconciliation_date         TIMESTAMPTZ,
reconciliation_notes        TEXT,

-- Útiles
match_explanation           TEXT,
requires_manual_review      BOOLEAN DEFAULT FALSE,
reviewed_by                 INTEGER,
reviewed_at                 TIMESTAMPTZ,
invoice_rfc_emisor          VARCHAR(13),            -- Columna desnormalizada del JSON para índice
invoice_date                TIMESTAMPTZ,            -- Columna desnormalizada del JSON para índice
invoice_total               NUMERIC(15,2)           -- Columna desnormalizada del JSON para índice
```

---

## 🎯 ARQUITECTURA DE RECONCILIACIÓN PROPUESTA

### Layer 0: SQL Exact Matching (RÁPIDO)
```sql
-- Ejemplo: Match exacto RFC + monto + fecha
SELECT
    me.id as manual_id,
    si.id as sat_id,
    bt.id as bank_id,
    'layer0_sql' as match_layer,
    1.00 as confidence
FROM manual_expenses me
LEFT JOIN sat_invoices si
    ON si.invoice_rfc_emisor = me.provider_rfc           -- Necesita nueva columna
    AND si.invoice_total = me.amount                      -- Necesita nueva columna
    AND DATE(si.invoice_date) = DATE(me.date)             -- Necesita nueva columna
LEFT JOIN bank_transactions bt
    ON bt.vendor_rfc = me.provider_rfc                   -- ⚠️ vendor_rfc NO EXISTE
    AND bt.amount = me.amount
    AND bt.transaction_date = DATE(me.date)
WHERE si.reconciliation_status IS NULL;
```

**Columnas necesarias**:
1. `bank_transactions.vendor_rfc` VARCHAR(13) - **CRÍTICO**
2. `sat_invoices.invoice_rfc_emisor` VARCHAR(13) INDEX
3. `sat_invoices.invoice_date` TIMESTAMPTZ INDEX
4. `sat_invoices.invoice_total` NUMERIC(15,2) INDEX

### Layer 1: Fuzzy Math Matching (MEDIO)
```python
# Ejemplo: Tolerancia de centavos, splits parciales
matches = []
for manual in unmatched_manual:
    for invoice in unmatched_sat:
        # Coincidencia de RFC
        if manual.provider_rfc == invoice.emisor_rfc:
            # Fecha dentro de ±7 días
            if abs(manual.date - invoice.fecha).days <= 7:
                # Monto con tolerancia 1%
                if abs(manual.amount - invoice.total) / invoice.total < 0.01:
                    matches.append({
                        'manual_id': manual.id,
                        'sat_id': invoice.id,
                        'confidence': 0.95,
                        'layer': 'layer1_math'
                    })
```

### Layer 2: Vector Semantic Search (EMBEDDINGS)
- ✅ **Ya existe**: `sat_invoices.supplier_embedding` (vector)
- Necesario: Embeddings en `manual_expenses` y `bank_transactions`

```sql
-- Buscar facturas SAT similares semánticamente
SELECT
    id,
    parsed_data->>'emisor'->>'nombre' as proveedor,
    amount_total,
    supplier_embedding <=> query_embedding as distance
FROM sat_invoices
WHERE supplier_embedding <=> query_embedding < 0.3
ORDER BY distance
LIMIT 10;
```

### Layer 3: LLM Reasoning (LENTO, COSTOSO)
```python
# Para casos ambiguos que requieren razonamiento
prompt = f"""
Determina si estos registros corresponden a la misma transacción:

MANUAL:
  Proveedor: {manual.provider_name}
  RFC: {manual.provider_rfc}
  Monto: ${manual.amount}
  Fecha: {manual.date}
  Descripción: {manual.description}

FACTURA SAT:
  Emisor: {invoice.emisor_nombre}
  RFC: {invoice.emisor_rfc}
  Total: ${invoice.total}
  Fecha: {invoice.fecha}
  Conceptos: {invoice.conceptos}

BANCO:
  Descripción: {bank.description}
  Monto: ${bank.amount}
  Fecha: {bank.transaction_date}
  Vendor: {bank.vendor_normalized}

¿Son la misma transacción? Explain your reasoning.
"""
```

---

## 📋 MIGRATION SCRIPT RECOMENDADO

### 1. Agregar columnas de reconciliación (TODAS las tablas)
```sql
-- Script: migrations/046_add_reconciliation_fields.sql

BEGIN;

-- =====================================================
-- MANUAL_EXPENSES
-- =====================================================
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS sat_invoice_id TEXT REFERENCES sat_invoices(id),
ADD COLUMN IF NOT EXISTS bank_transaction_id INTEGER REFERENCES bank_transactions(id),
ADD COLUMN IF NOT EXISTS reconciliation_status VARCHAR(20) DEFAULT 'unmatched',
ADD COLUMN IF NOT EXISTS reconciliation_confidence NUMERIC(3,2),
ADD COLUMN IF NOT EXISTS reconciliation_layer VARCHAR(10),
ADD COLUMN IF NOT EXISTS reconciliation_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reconciliation_notes TEXT,
ADD COLUMN IF NOT EXISTS match_explanation TEXT,
ADD COLUMN IF NOT EXISTS requires_manual_review BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS reviewed_by INTEGER,
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- Índices
CREATE INDEX idx_manual_expenses_reconciliation
    ON manual_expenses(provider_rfc, date, amount)
    WHERE reconciliation_status IS NULL;

CREATE INDEX idx_manual_expenses_status
    ON manual_expenses(reconciliation_status);

-- =====================================================
-- BANK_TRANSACTIONS
-- =====================================================
ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS vendor_rfc VARCHAR(13),                     -- ⚠️ CRÍTICO
ADD COLUMN IF NOT EXISTS vendor_rfc_source VARCHAR(20),              -- 'extracted', 'manual', 'sat_match'
ADD COLUMN IF NOT EXISTS vendor_rfc_confidence NUMERIC(3,2),
ADD COLUMN IF NOT EXISTS sat_invoice_id TEXT REFERENCES sat_invoices(id),
ADD COLUMN IF NOT EXISTS manual_expense_id INTEGER REFERENCES manual_expenses(id),
ADD COLUMN IF NOT EXISTS reconciliation_status VARCHAR(20) DEFAULT 'unmatched',
ADD COLUMN IF NOT EXISTS reconciliation_confidence NUMERIC(3,2),
ADD COLUMN IF NOT EXISTS reconciliation_layer VARCHAR(10),
ADD COLUMN IF NOT EXISTS reconciliation_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reconciliation_notes TEXT,
ADD COLUMN IF NOT EXISTS match_explanation TEXT,
ADD COLUMN IF NOT EXISTS requires_manual_review BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS reviewed_by INTEGER,
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- Índices
CREATE INDEX idx_bank_transactions_reconciliation
    ON bank_transactions(vendor_rfc, transaction_date, amount)
    WHERE reconciliation_status IS NULL AND vendor_rfc IS NOT NULL;

CREATE INDEX idx_bank_transactions_status
    ON bank_transactions(reconciliation_status);

-- =====================================================
-- SAT_INVOICES
-- =====================================================
ALTER TABLE sat_invoices
ADD COLUMN IF NOT EXISTS bank_transaction_id INTEGER REFERENCES bank_transactions(id),
ADD COLUMN IF NOT EXISTS manual_expense_id INTEGER REFERENCES manual_expenses(id),
ADD COLUMN IF NOT EXISTS reconciliation_status VARCHAR(20) DEFAULT 'unmatched',
ADD COLUMN IF NOT EXISTS reconciliation_confidence NUMERIC(3,2),
ADD COLUMN IF NOT EXISTS reconciliation_layer VARCHAR(10),
ADD COLUMN IF NOT EXISTS reconciliation_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reconciliation_notes TEXT,
ADD COLUMN IF NOT EXISTS match_explanation TEXT,
ADD COLUMN IF NOT EXISTS requires_manual_review BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS reviewed_by INTEGER,
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,

-- Columnas desnormalizadas del JSON para índices (CRÍTICO para Layer 0)
ADD COLUMN IF NOT EXISTS invoice_rfc_emisor VARCHAR(13)
    GENERATED ALWAYS AS (parsed_data->'emisor'->>'rfc') STORED,
ADD COLUMN IF NOT EXISTS invoice_date TIMESTAMPTZ
    GENERATED ALWAYS AS ((parsed_data->>'fecha')::TIMESTAMPTZ) STORED,
ADD COLUMN IF NOT EXISTS invoice_total_extracted NUMERIC(15,2)
    GENERATED ALWAYS AS ((parsed_data->>'total')::NUMERIC) STORED;

-- Índices
CREATE INDEX idx_sat_invoices_reconciliation
    ON sat_invoices(invoice_rfc_emisor, invoice_date, invoice_total_extracted)
    WHERE reconciliation_status IS NULL;

CREATE INDEX idx_sat_invoices_status
    ON sat_invoices(reconciliation_status);

CREATE INDEX idx_sat_invoices_rfc ON sat_invoices(invoice_rfc_emisor);

-- =====================================================
-- TABLA DE MATCHES (para muchos-a-muchos)
-- =====================================================
CREATE TABLE IF NOT EXISTS reconciliation_matches (
    id SERIAL PRIMARY KEY,

    -- Referencias
    manual_expense_id INTEGER REFERENCES manual_expenses(id),
    sat_invoice_id TEXT REFERENCES sat_invoices(id),
    bank_transaction_id INTEGER REFERENCES bank_transactions(id),

    -- Match metadata
    match_layer VARCHAR(10) NOT NULL,  -- 'layer0_sql', 'layer1_math', 'layer2_vector', 'layer3_llm'
    confidence NUMERIC(3,2) NOT NULL,
    explanation TEXT,

    -- Montos asignados (para splits)
    manual_amount_allocated NUMERIC(15,2),
    sat_amount_allocated NUMERIC(15,2),
    bank_amount_allocated NUMERIC(15,2),

    -- Estado
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'accepted', 'rejected'
    requires_review BOOLEAN DEFAULT FALSE,

    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    reviewed_by INTEGER,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- Constraints: al menos 2 fuentes deben estar presentes
    CHECK (
        (manual_expense_id IS NOT NULL AND sat_invoice_id IS NOT NULL) OR
        (manual_expense_id IS NOT NULL AND bank_transaction_id IS NOT NULL) OR
        (sat_invoice_id IS NOT NULL AND bank_transaction_id IS NOT NULL)
    )
);

CREATE INDEX idx_reconciliation_matches_manual ON reconciliation_matches(manual_expense_id);
CREATE INDEX idx_reconciliation_matches_sat ON reconciliation_matches(sat_invoice_id);
CREATE INDEX idx_reconciliation_matches_bank ON reconciliation_matches(bank_transaction_id);
CREATE INDEX idx_reconciliation_matches_status ON reconciliation_matches(status);
CREATE INDEX idx_reconciliation_matches_layer ON reconciliation_matches(match_layer);

COMMIT;
```

### 2. Popular `vendor_rfc` en `bank_transactions`
```python
# Script: scripts/extract_vendor_rfc_from_bank.py

import re
from core.shared.unified_db_adapter import UnifiedDBAdapter

def extract_rfc_from_description(description: str) -> str:
    """
    Extrae RFC de descripciones bancarias usando regex.
    RFC formato: 3-4 letras + 6 dígitos (YYMMDD) + 3 caracteres
    """
    rfc_pattern = r'\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b'
    match = re.search(rfc_pattern, description.upper())
    return match.group(0) if match else None

adapter = UnifiedDBAdapter(config.DB_PATH)
conn = adapter.get_connection()
cursor = conn.cursor()

# Get transactions sin vendor_rfc
cursor.execute("""
    SELECT id, description, vendor_normalized
    FROM bank_transactions
    WHERE vendor_rfc IS NULL
    AND description IS NOT NULL
""")

transactions = cursor.fetchall()
print(f"Processing {len(transactions)} transactions...")

updates = 0
for tx in transactions:
    rfc = extract_rfc_from_description(tx['description'])
    if rfc:
        cursor.execute("""
            UPDATE bank_transactions
            SET vendor_rfc = %s,
                vendor_rfc_source = 'extracted',
                vendor_rfc_confidence = 0.85
            WHERE id = %s
        """, (rfc, tx['id']))
        updates += 1

conn.commit()
print(f"✅ Updated {updates} transactions with extracted RFCs")
```

---

## 🎯 PRÓXIMOS PASOS RECOMENDADOS

### Fase 1: Preparar Tablas (1-2 días)
1. ✅ Ejecutar migration 046 para agregar columnas de reconciliación
2. ✅ Poblar `bank_transactions.vendor_rfc` con script de extracción
3. ✅ Poblar columnas generadas en `sat_invoices` (automático)
4. ✅ Verificar índices

### Fase 2: Implementar Layer 0 (2-3 días)
1. Crear función SQL `reconcile_layer0_exact_match()`
2. Ejecutar en batch sobre registros no reconciliados
3. Marcar matches con `confidence=1.00`
4. Estimar: 60-80% de casos simples resueltos

### Fase 3: Implementar Layer 1 (2-3 días)
1. Crear servicio Python `ReconciliationServiceLayer1`
2. Fuzzy matching con tolerancia configurable
3. Manejar splits parciales
4. Estimar: +10-15% adicional resuelto

### Fase 4: Implementar Layer 2 (3-4 días)
1. Generar embeddings para `manual_expenses.description`
2. Usar `sat_invoices.supplier_embedding` existente
3. Búsqueda vectorial con umbral de distancia
4. Estimar: +5-10% adicional resuelto

### Fase 5: Implementar Layer 3 (2-3 días)
1. LLM reasoning para casos ambiguos
2. Threshold: solo casos con `requires_manual_review=TRUE`
3. Guardar explicación en `match_explanation`
4. Estimar: casos restantes (5-10%)

### Fase 6: UI y Testing (3-5 días)
1. Dashboard de reconciliación
2. Interface para revisar matches ambiguos
3. Bulk approval/rejection
4. Analytics y reportes

---

## 💡 CONSIDERACIONES ADICIONALES

### Performance
- Layer 0 (SQL): <1 segundo para 10k registros
- Layer 1 (Math): ~5-10 segundos para 10k comparaciones
- Layer 2 (Vector): ~2-5 segundos con índice HNSW
- Layer 3 (LLM): ~500ms por caso (solo ambiguos)

### Costos
- Layer 0-1: $0 (solo compute)
- Layer 2: ~$0.0001 por embedding (OpenAI text-embedding-3-small)
- Layer 3: ~$0.002 por match (Sonnet 4.5, ~1k tokens)
- Estimado mensual (1000 gastos/mes, 20% ambiguos): ~$5-10/mes

### Accuracy Esperado
- Layer 0: 99.9% accuracy (matches exactos)
- Layer 1: 95% accuracy (fuzzy con threshold)
- Layer 2: 85-90% accuracy (semántica)
- Layer 3: 90-95% accuracy (LLM reasoning)

---

## 📞 CONTACTO
**Autor**: Claude (Anthropic)
**Revisado por**: Daniel
**Empresa**: Carreta Verde
**Proyecto**: Sistema de Conciliación Tripartita MCP
