# Database Audit: Multi-Source Reconciliation Architecture
## Date: 2025-12-08
## Auditor: Claude (Backend Refactor Branch)

---

## Executive Summary

**Objetivo**: Auditar esquema actual de base de datos para evaluar viabilidad de arquitectura de matching inteligente entre 3 fuentes de datos:
- `manual_expenses` (Gastos manuales departamentales)
- `bank_transactions` (Transacciones bancarias parseadas)
- **SAT Invoices** (Facturas fiscales del SAT)

**Hallazgo crítico**: La tabla `sat_invoices` NO EXISTE en PostgreSQL. Las facturas SAT están almacenadas como archivos XML en el filesystem (`uploads/invoices/*/`) pero **NO indexadas en base de datos**.

**Estado actual**: Sistema tiene 2 de 3 fuentes necesarias para reconciliación. Se requiere crear tabla SAT antes de implementar matching inteligente.

---

## 1. Tablas Existentes: Esquema Actual

### 1.1 `manual_expenses` ✅ EXISTE
**Propósito**: Gastos registrados manualmente por empleados/departamentos

```sql
CREATE TABLE manual_expenses (
    id                    integer PRIMARY KEY,
    tenant_id             integer DEFAULT 1,
    company_id            varchar(100) DEFAULT 'default',
    user_id               integer,
    project_id            integer,  -- FK to projects table

    -- Expense details
    description           text,
    amount                numeric(15,2),
    currency              varchar(3) DEFAULT 'MXN',
    date                  timestamptz DEFAULT now(),

    -- Vendor information
    provider_name         varchar(255),
    provider_fiscal_name  varchar(255),
    provider_rfc          varchar(13),  -- 🔑 KEY FOR MATCHING

    -- Classification
    category              varchar(100),
    sat_account_code      varchar(20),

    -- Status fields
    status                varchar(50) DEFAULT 'pending',
    workflow_status       varchar(50) DEFAULT 'pendiente_validacion',
    invoice_status        varchar(50) DEFAULT 'pendiente',
    registro_via          varchar(50) DEFAULT 'manual',

    -- Metadata
    tax_info              jsonb,
    movimientos_bancarios jsonb,  -- 📌 POSSIBLY stores bank reconciliation?
    events                jsonb,
    warnings              jsonb,
    category_alternatives jsonb,
    audit_trail           jsonb,
    user_context          text,
    enhanced_data         jsonb,
    validation_errors     jsonb,

    -- Project tracking
    deducible             boolean DEFAULT true,
    centro_costo          text,
    proyecto              text,
    tags                  jsonb,

    -- Completeness
    completion_status     text DEFAULT 'draft',
    field_completeness    numeric(3,2) DEFAULT 0.0,

    -- Timestamps
    created_at            timestamptz DEFAULT now(),
    updated_at            timestamptz DEFAULT now()
)
```

**Análisis para Matching**:
- ✅ Tiene `provider_rfc` para match exacto con facturas SAT
- ✅ Tiene `amount` para validación numérica
- ✅ Tiene `date` para ventana temporal
- ✅ Tiene `movimientos_bancarios` JSONB (posible link a bank_transactions)
- ❌ NO tiene campo explícito `sat_invoice_id` (foreign key faltante)
- ❌ NO tiene campo explícito `bank_transaction_id` (foreign key faltante)
- ❌ NO tiene `reconciliation_status` (pendiente/matched/conflict)
- ❌ NO tiene `match_confidence` para tracking AI predictions

**Observaciones**:
- `invoice_status = 'pendiente'` sugiere workflow manual de esperar factura
- `movimientos_bancarios` JSONB podría contener referencias bancarias no estructuradas

---

### 1.2 `bank_transactions` ✅ EXISTE
**Propósito**: Transacciones bancarias parseadas de estados de cuenta

```sql
CREATE TABLE bank_transactions (
    id                     integer PRIMARY KEY,
    statement_id           integer NOT NULL,  -- FK to bank_statements

    -- Transaction details
    transaction_date       date NOT NULL,
    description            text,
    description_clean      text,
    reference              varchar(100),
    amount                 numeric(15,2) NOT NULL,  -- 🔑 KEY FOR MATCHING
    balance                numeric(15,2),

    -- Classification (enriched by AI)
    transaction_type       varchar(20) NOT NULL,  -- debit/credit
    transaction_class      varchar(50),  -- ingreso/gasto/transferencia/traspaso_interno
    category               varchar(100),
    subcategory            varchar(100),
    vendor_normalized      varchar(255),  -- 🔑 KEY FOR MATCHING (not RFC)

    -- Enrichment metadata
    is_recurring           boolean DEFAULT false,
    enrichment_confidence  numeric(3,2),
    enriched_at            timestamp,
    manually_corrected     boolean DEFAULT false,
    manual_correction_date timestamp,

    -- Timestamps
    created_at             timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at             timestamp DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT check_transaction_class
        CHECK (transaction_class IN ('ingreso', 'gasto', 'transferencia')),
    CONSTRAINT check_transaction_type
        CHECK (transaction_type IN ('debit', 'credit'))
)
```

**Análisis para Matching**:
- ✅ Tiene `amount` para match numérico
- ✅ Tiene `transaction_date` para ventana temporal
- ✅ Tiene `vendor_normalized` pero NO es RFC (nombre limpio)
- ✅ Tiene `enrichment_confidence` (podría reutilizarse para match confidence)
- ❌ NO tiene `vendor_rfc` (problema crítico para match exacto)
- ❌ NO tiene `sat_invoice_id` (foreign key faltante)
- ❌ NO tiene `manual_expense_id` (foreign key faltante)
- ❌ NO tiene `reconciliation_status`
- ❌ NO tiene campo `matched_at` timestamp

**Observaciones**:
- `check_transaction_class` constraint NO incluye `'traspaso_interno'` (migration 051 pendiente?)
- `vendor_normalized` es texto libre, NO RFC oficial
- Sistema de clasificación AI ya existe (campos `enrichment_*`)

---

### 1.3 `sat_invoices` ❌ NO EXISTE
**Propósito**: Facturas fiscales descargadas del SAT

**Estado actual**:
- ❌ Tabla NO existe en PostgreSQL
- ✅ Archivos XML existen en filesystem: `uploads/invoices/carreta_verde/*.xml`
- ⚠️  Migration 014 define la tabla pero usa sintaxis SQLite (`randomblob()`)
- ⚠️  Posiblemente nunca se migró a PostgreSQL

**Schema esperado** (basado en migration 014, adaptado a PostgreSQL):
```sql
CREATE TABLE sat_invoices (
    id                      TEXT PRIMARY KEY,  -- Necesita cambiar a SERIAL/UUID
    company_id              TEXT NOT NULL,
    user_id                 TEXT,

    -- File information
    invoice_file_path       TEXT NOT NULL,
    original_filename       TEXT,
    file_size_bytes         INTEGER,
    file_hash               TEXT,

    -- Format detection
    detected_format         TEXT,
    format_confidence       DECIMAL(5,2) DEFAULT 0.00,
    parser_used             TEXT,
    backup_parsers          JSONB DEFAULT '[]',

    -- Processing results
    extraction_status       TEXT DEFAULT 'pending',
    extracted_data          JSONB DEFAULT '{}',  -- 🔑 PARSED INVOICE DATA
    validation_status       TEXT DEFAULT 'pending',
    validation_errors       JSONB DEFAULT '[]',

    -- Quality metrics
    extraction_confidence   DECIMAL(5,2) DEFAULT 0.00,
    validation_score        DECIMAL(5,2) DEFAULT 0.00,
    overall_quality_score   DECIMAL(5,2) DEFAULT 0.00,

    -- Timestamps
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at            TIMESTAMP
)
```

**Campos críticos faltantes para matching**:
```sql
-- Campos que DEBEN agregarse:
emisor_rfc              VARCHAR(13),     -- 🔑 RFC del emisor (proveedor)
receptor_rfc            VARCHAR(13),     -- RFC del receptor (empresa)
total                   NUMERIC(15,2),   -- 🔑 Monto total factura
fecha_emision           DATE,            -- 🔑 Fecha de emisión
uuid                    VARCHAR(36),     -- UUID fiscal único
tipo_comprobante        VARCHAR(10),     -- I (Ingreso), E (Egreso), etc.
metodo_pago             VARCHAR(10),     -- PUE, PPD
forma_pago              VARCHAR(10),     -- 03 (Transferencia), etc.
moneda                  VARCHAR(3),      -- MXN, USD, etc.

-- Campos para reconciliación:
reconciliation_status   VARCHAR(50),     -- unmatched/partial/full/conflict
matched_bank_tx_id      INTEGER,         -- FK to bank_transactions
matched_expense_id      INTEGER,         -- FK to manual_expenses
match_confidence        NUMERIC(3,2),    -- Confianza del match AI
matched_at              TIMESTAMP,       -- Cuándo se hizo el match
matched_by              VARCHAR(50),     -- 'auto' / 'manual'

-- Embeddings para búsqueda vectorial:
description_embedding   VECTOR(1536),    -- pgvector embedding
```

---

## 2. Análisis de Gaps: Lo que Falta

### 2.1 Tabla `sat_invoices` - NO EXISTE
**Prioridad**: 🔴 CRÍTICA - Sin esta tabla, reconciliación de 3 fuentes es imposible

**Acción requerida**:
1. Crear migration PostgreSQL para tabla `sat_invoices`
2. Importar XMLs existentes desde `uploads/invoices/*/`
3. Parsear XMLs y extraer campos clave (`emisor_rfc`, `total`, `fecha_emision`, `uuid`)
4. Poblar columna `extracted_data` JSONB con datos completos del XML

---

### 2.2 Campos de Reconciliación - FALTAN EN TODAS LAS TABLAS
**Prioridad**: 🟠 ALTA - Sin estos campos, tracking de matches es manual

**Campos requeridos en cada tabla**:

#### En `manual_expenses`:
```sql
ALTER TABLE manual_expenses ADD COLUMN sat_invoice_id INTEGER REFERENCES sat_invoices(id);
ALTER TABLE manual_expenses ADD COLUMN bank_transaction_id INTEGER REFERENCES bank_transactions(id);
ALTER TABLE manual_expenses ADD COLUMN reconciliation_status VARCHAR(50) DEFAULT 'unmatched';
ALTER TABLE manual_expenses ADD COLUMN match_confidence NUMERIC(3,2);
ALTER TABLE manual_expenses ADD COLUMN matched_at TIMESTAMP;
ALTER TABLE manual_expenses ADD COLUMN matched_by VARCHAR(50);  -- 'auto' / 'manual'
```

#### En `bank_transactions`:
```sql
ALTER TABLE bank_transactions ADD COLUMN sat_invoice_id INTEGER REFERENCES sat_invoices(id);
ALTER TABLE bank_transactions ADD COLUMN manual_expense_id INTEGER REFERENCES manual_expenses(id);
ALTER TABLE bank_transactions ADD COLUMN vendor_rfc VARCHAR(13);  -- 🔑 CRÍTICO para match exacto
ALTER TABLE bank_transactions ADD COLUMN reconciliation_status VARCHAR(50) DEFAULT 'unmatched';
ALTER TABLE bank_transactions ADD COLUMN match_confidence NUMERIC(3,2);
ALTER TABLE bank_transactions ADD COLUMN matched_at TIMESTAMP;
ALTER TABLE bank_transactions ADD COLUMN matched_by VARCHAR(50);
```

#### En `sat_invoices` (cuando se cree):
```sql
-- Ya incluidos en diseño arriba
```

---

### 2.3 Tabla de Audit Trail para Matches
**Prioridad**: 🟡 MEDIA - Útil para debugging y rollback

**Nueva tabla**:
```sql
CREATE TABLE reconciliation_matches (
    id                      SERIAL PRIMARY KEY,
    tenant_id               INTEGER NOT NULL,

    -- Match relationship
    sat_invoice_id          INTEGER REFERENCES sat_invoices(id),
    bank_transaction_id     INTEGER REFERENCES bank_transactions(id),
    manual_expense_id       INTEGER REFERENCES manual_expenses(id),

    -- Match metadata
    match_type              VARCHAR(50),  -- 'exact' / 'fuzzy' / 'split' / 'manual'
    match_layer             VARCHAR(20),  -- 'layer_0_sql' / 'layer_1_math' / 'layer_2_vector' / 'layer_3_llm'
    match_confidence        NUMERIC(3,2) NOT NULL,
    match_explanation       TEXT,

    -- AI reasoning
    llm_reasoning           TEXT,
    embedding_similarity    NUMERIC(3,2),
    amount_delta            NUMERIC(15,2),  -- Diferencia en montos
    date_delta_days         INTEGER,        -- Diferencia en días

    -- Split handling
    is_split_match          BOOLEAN DEFAULT false,
    split_group_id          VARCHAR(36),    -- UUID para agrupar splits
    split_total_amount      NUMERIC(15,2),

    -- Status
    status                  VARCHAR(50) DEFAULT 'proposed',  -- proposed/confirmed/rejected
    confirmed_by            INTEGER,        -- user_id
    confirmed_at            TIMESTAMP,

    -- Timestamps
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (match_confidence >= 0 AND match_confidence <= 1)
)
```

---

### 2.4 Índices y Embeddings
**Prioridad**: 🟡 MEDIA - Performance crítica para búsqueda vectorial

**Extensión requerida**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector for embeddings
```

**Índices necesarios**:
```sql
-- En sat_invoices (cuando se cree)
CREATE INDEX idx_sat_invoices_emisor_rfc ON sat_invoices(emisor_rfc);
CREATE INDEX idx_sat_invoices_total ON sat_invoices(total);
CREATE INDEX idx_sat_invoices_fecha ON sat_invoices(fecha_emision);
CREATE INDEX idx_sat_invoices_reconciliation ON sat_invoices(reconciliation_status);
CREATE INDEX idx_sat_invoices_embedding ON sat_invoices
    USING ivfflat (description_embedding vector_cosine_ops);

-- En bank_transactions (nuevos campos)
CREATE INDEX idx_bank_tx_vendor_rfc ON bank_transactions(vendor_rfc);
CREATE INDEX idx_bank_tx_reconciliation ON bank_transactions(reconciliation_status);
CREATE INDEX idx_bank_tx_sat_invoice ON bank_transactions(sat_invoice_id);

-- En manual_expenses (nuevos campos)
CREATE INDEX idx_manual_exp_sat_invoice ON manual_expenses(sat_invoice_id);
CREATE INDEX idx_manual_exp_bank_tx ON manual_expenses(bank_transaction_id);
CREATE INDEX idx_manual_exp_reconciliation ON manual_expenses(reconciliation_status);
```

---

## 3. Arquitectura Propuesta: Cómo se Integra con Schema Actual

### 3.1 Layer 0: SQL Exact Match (Gratis, 0ms)
**Query ejemplo**:
```sql
-- Match SAT Invoice → Bank Transaction
SELECT
    si.id as sat_invoice_id,
    bt.id as bank_transaction_id,
    'exact' as match_type,
    1.0 as confidence
FROM sat_invoices si
JOIN bank_transactions bt
    ON si.emisor_rfc = bt.vendor_rfc
    AND ABS(si.total) = ABS(bt.amount)
    AND DATE(si.fecha_emision) = DATE(bt.transaction_date)
WHERE si.reconciliation_status = 'unmatched'
  AND bt.reconciliation_status = 'unmatched';
```

**Problema actual**:
- ❌ `sat_invoices` no existe
- ❌ `bank_transactions.vendor_rfc` no existe

---

### 3.2 Layer 1: Mathematical Filters (1ms, $0)
**Query ejemplo**:
```sql
-- Find candidates with ±10% amount tolerance, ±7 day window
SELECT
    si.id as sat_invoice_id,
    bt.id as bank_transaction_id,
    ABS(si.total - bt.amount) as amount_delta,
    ABS(DATE_PART('day', si.fecha_emision - bt.transaction_date)) as day_delta,
    'fuzzy' as match_type
FROM sat_invoices si
CROSS JOIN bank_transactions bt
WHERE si.reconciliation_status = 'unmatched'
  AND bt.reconciliation_status = 'unmatched'
  AND ABS(si.total - bt.amount) / GREATEST(ABS(si.total), ABS(bt.amount)) < 0.10
  AND ABS(DATE_PART('day', si.fecha_emision - bt.transaction_date)) <= 7
LIMIT 50;
```

---

### 3.3 Layer 2: Vector Search (50ms, $0)
**Query ejemplo** (requiere pgvector):
```sql
-- Find semantically similar invoices using embeddings
SELECT
    si.id as sat_invoice_id,
    bt.id as bank_transaction_id,
    1 - (si.description_embedding <=> bt.description_embedding) as similarity,
    'vector' as match_type
FROM sat_invoices si
CROSS JOIN bank_transactions bt
WHERE si.reconciliation_status = 'unmatched'
  AND bt.reconciliation_status = 'unmatched'
  AND 1 - (si.description_embedding <=> bt.description_embedding) > 0.85
ORDER BY similarity DESC
LIMIT 20;
```

**Problema actual**:
- ❌ `description_embedding` no existe en ninguna tabla
- ❌ pgvector extension NO instalada (probablemente)

---

### 3.4 Layer 3: LLM Reasoning (500ms, $0.002)
Usa resultados de Layer 2 como candidates, envía a Claude/GPT para validación final.

---

## 4. Roadmap: Plan de Implementación

### 🔴 Fase 1: Tabla SAT Invoices (BLOQUEADOR)
**Duración estimada**: 2-3 horas

1. **Migration 052**: Crear tabla `sat_invoices` en PostgreSQL
   - Copiar estructura de migration 014
   - Adaptar sintaxis SQLite → PostgreSQL
   - Agregar campos de reconciliación

2. **Script de importación**: Parsear XMLs existentes
   ```bash
   python scripts/import_sat_xmls_to_postgres.py
   ```
   - Leer archivos de `uploads/invoices/carreta_verde/*.xml`
   - Parsear con `lxml` o `xml.etree`
   - Extraer: `emisor_rfc`, `total`, `fecha_emision`, `uuid`
   - Insertar en `sat_invoices`

3. **Validación**:
   ```sql
   SELECT COUNT(*) FROM sat_invoices;  -- Debe ser > 0
   SELECT * FROM sat_invoices LIMIT 5;
   ```

---

### 🟠 Fase 2: Campos de Reconciliación
**Duración estimada**: 1 hora

1. **Migration 053**: ALTER TABLEs
   - Agregar FKs: `sat_invoice_id`, `bank_transaction_id`
   - Agregar `reconciliation_status`, `match_confidence`
   - Agregar `vendor_rfc` a `bank_transactions`

2. **Validación**:
   ```sql
   \d bank_transactions
   \d manual_expenses
   ```

---

### 🟡 Fase 3: Audit Trail Table
**Duración estimada**: 30 minutos

1. **Migration 054**: Crear `reconciliation_matches`
2. **Validación**: Insertar match de prueba

---

### 🟡 Fase 4: Vector Search Setup
**Duración estimada**: 2 horas

1. **Instalar pgvector**:
   ```sql
   CREATE EXTENSION vector;
   ```

2. **Migration 055**: Agregar columnas `embedding VECTOR(1536)`
   - En `sat_invoices`
   - En `bank_transactions`
   - En `manual_expenses`

3. **Script**: Generar embeddings para registros existentes
   ```python
   python scripts/backfill_reconciliation_embeddings.py
   ```

4. **Crear índices** ivfflat/hnsw

---

## 5. Respuestas a Preguntas de Arquitectura

### Q1: ¿Qué tan frecuente son SPLITS (1 pago → N facturas)?
**Respuesta del usuario**: B) Ocasional (20-30%)

**Implicación**:
- Layer 0 (SQL exact match) captura 70-80% de casos
- Layer 1.5 (Knapsack Solver) necesario para 20-30%
- Complejidad: Buscar combinaciones de max 3-4 facturas del mismo proveedor

**Query para identificar splits**:
```sql
-- Find potential splits: same vendor, multiple invoices, sum ≈ bank amount
SELECT
    bt.id as bank_tx_id,
    bt.vendor_rfc,
    bt.amount as bank_amount,
    STRING_AGG(si.id::TEXT, ',') as invoice_ids,
    SUM(si.total) as invoices_sum,
    COUNT(si.id) as num_invoices
FROM bank_transactions bt
JOIN sat_invoices si
    ON si.emisor_rfc = bt.vendor_rfc
    AND si.reconciliation_status = 'unmatched'
WHERE bt.reconciliation_status = 'unmatched'
  AND si.fecha_emision BETWEEN bt.transaction_date - INTERVAL '7 days'
                           AND bt.transaction_date + INTERVAL '7 days'
GROUP BY bt.id, bt.vendor_rfc, bt.amount
HAVING ABS(SUM(si.total) - bt.amount) / GREATEST(ABS(SUM(si.total)), ABS(bt.amount)) < 0.02
   AND COUNT(si.id) BETWEEN 2 AND 4
ORDER BY bt.transaction_date DESC;
```

---

### Q2: ¿Jerarquía de verdad en conflictos?
**Respuesta del usuario**: A) Banco/Factura mandan (auto-correct manual expenses)

**Implicación**:
- Si `bank_transactions.amount` ≠ `manual_expenses.amount`, corregir manual expense
- Si `sat_invoices.total` ≠ `manual_expenses.amount`, corregir manual expense
- Trigger de auto-corrección:
  ```sql
  CREATE TRIGGER auto_correct_manual_expense
  AFTER INSERT ON reconciliation_matches
  FOR EACH ROW
  WHEN (NEW.status = 'confirmed' AND NEW.manual_expense_id IS NOT NULL)
  EXECUTE FUNCTION correct_manual_expense_from_authoritative_source();
  ```

**Función**:
```sql
CREATE FUNCTION correct_manual_expense_from_authoritative_source()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE manual_expenses
    SET
        amount = COALESCE(
            (SELECT total FROM sat_invoices WHERE id = NEW.sat_invoice_id),
            (SELECT amount FROM bank_transactions WHERE id = NEW.bank_transaction_id)
        ),
        provider_rfc = COALESCE(
            (SELECT emisor_rfc FROM sat_invoices WHERE id = NEW.sat_invoice_id),
            provider_rfc
        ),
        audit_trail = jsonb_set(
            COALESCE(audit_trail, '{}'),
            '{auto_corrections}',
            (COALESCE(audit_trail->'auto_corrections', '[]'::jsonb) || jsonb_build_object(
                'timestamp', NOW(),
                'corrected_by', 'auto_reconciliation',
                'old_amount', amount,
                'new_amount', COALESCE(
                    (SELECT total FROM sat_invoices WHERE id = NEW.sat_invoice_id),
                    (SELECT amount FROM bank_transactions WHERE id = NEW.bank_transaction_id)
                ),
                'reason', 'Bank/SAT authoritative source override'
            ))
        )
    WHERE id = NEW.manual_expense_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

### Q3: ¿Timing de Gasto Manual?
**Respuesta del usuario**: C) DESPUÉS (Retroactivo) - Empleados suben gastos días/semanas después

**Implicación**:
- Gastos manuales son "orphans" por defecto
- Necesitamos **Orphan Sweeper** batch job diario:
  ```sql
  -- Encuentra gastos manuales sin match que ahora tienen candidatos
  SELECT me.id, me.provider_rfc, me.amount, me.date
  FROM manual_expenses me
  WHERE me.reconciliation_status = 'unmatched'
    AND me.created_at < NOW() - INTERVAL '1 day'  -- Al menos 1 día viejo
    AND EXISTS (
        SELECT 1 FROM bank_transactions bt
        WHERE bt.vendor_rfc = me.provider_rfc
          AND ABS(bt.amount - me.amount) / GREATEST(ABS(bt.amount), ABS(me.amount)) < 0.10
          AND bt.transaction_date BETWEEN me.date - INTERVAL '90 days'
                                      AND me.date + INTERVAL '7 days'
    )
  LIMIT 100;
  ```

- Cron job:
  ```bash
  # /etc/cron.d/reconciliation-sweeper
  0 2 * * * python /app/scripts/orphan_sweeper.py >> /var/log/orphan_sweeper.log 2>&1
  ```

---

## 6. Conclusiones y Recomendaciones

### ✅ Lo que SÍ existe y funciona:
1. ✅ `manual_expenses` con campos básicos de matching
2. ✅ `bank_transactions` con clasificación AI ya implementada
3. ✅ PostgreSQL con pgvector instalado (probablemente, verificar)
4. ✅ XMLs de facturas SAT en filesystem

### ❌ Blockers críticos:
1. ❌ **Tabla `sat_invoices` no existe** → Prioridad #1
2. ❌ **Foreign keys de reconciliación faltan** → Prioridad #2
3. ❌ **`bank_transactions.vendor_rfc` falta** → Prioridad #3
4. ❌ **Embeddings columns faltan** → Prioridad #4

### 🎯 Orden de implementación recomendado:
1. **HOY**: Migration 052 → Crear tabla `sat_invoices`
2. **HOY**: Script → Importar XMLs a base de datos
3. **MAÑANA**: Migration 053 → Campos de reconciliación
4. **DÍA 3**: Implementar Layer 0 (SQL exact match)
5. **DÍA 4**: Implementar Layer 1 (Math filters) + Knapsack Solver
6. **SEMANA 2**: pgvector embeddings + Layer 2
7. **SEMANA 3**: LLM reasoning + Orphan Sweeper

### 📊 ROI Esperado:
- **Sin matching**: 100% reconciliación manual (~30 min/transacción)
- **Con Layer 0**: 70% auto-match (21 transacciones/hora automatizadas)
- **Con Layer 1**: 90% auto-match (27 transacciones/hora)
- **Con Layer 2+3**: 95% auto-match (28.5 transacciones/hora)

**Tiempo ahorrado**: ~25 horas/mes (asumiendo 100 transacciones/mes)

---

## 7. SQL Script: Crear Tabla SAT Invoices (URGENTE)

```sql
-- Migration 052: Create sat_invoices table (PostgreSQL-compatible)
-- Replaces migration 014 which was SQLite-only

BEGIN;

-- Enable UUID extension for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main table for SAT fiscal invoices
CREATE TABLE IF NOT EXISTS sat_invoices (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id               INTEGER NOT NULL DEFAULT 1,
    company_id              INTEGER NOT NULL,
    user_id                 INTEGER,

    -- SAT-specific fields (CRITICAL FOR MATCHING)
    uuid                    VARCHAR(36) UNIQUE NOT NULL,  -- UUID fiscal
    emisor_rfc              VARCHAR(13) NOT NULL,         -- 🔑 Proveedor RFC
    emisor_nombre           VARCHAR(255),
    receptor_rfc            VARCHAR(13) NOT NULL,         -- Empresa RFC
    receptor_nombre         VARCHAR(255),
    total                   NUMERIC(15,2) NOT NULL,       -- 🔑 Monto
    subtotal                NUMERIC(15,2),
    descuento               NUMERIC(15,2) DEFAULT 0,
    fecha_emision           DATE NOT NULL,                -- 🔑 Fecha
    fecha_timbrado          TIMESTAMP,
    tipo_comprobante        VARCHAR(10),                  -- I, E, N, P, T
    metodo_pago             VARCHAR(10),                  -- PUE, PPD
    forma_pago              VARCHAR(10),                  -- 03, 04, etc
    moneda                  VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio             NUMERIC(10,4) DEFAULT 1.0,
    lugar_expedicion        VARCHAR(5),                   -- Código postal

    -- File information
    invoice_file_path       TEXT NOT NULL,
    original_filename       TEXT,
    file_size_bytes         INTEGER,
    file_hash               VARCHAR(64),  -- SHA256
    batch_id                VARCHAR(50),  -- ID del lote de descarga SAT

    -- Parsed data (full XML as JSONB)
    parsed_data             JSONB DEFAULT '{}',
    conceptos               JSONB DEFAULT '[]',           -- Line items
    impuestos               JSONB DEFAULT '{}',
    complementos            JSONB DEFAULT '[]',

    -- Classification (AI-generated)
    accounting_classification JSONB DEFAULT '{}',
    sat_account_code        VARCHAR(20),

    -- Processing status
    extraction_status       VARCHAR(50) DEFAULT 'pending',
    validation_status       VARCHAR(50) DEFAULT 'pending',
    validation_errors       JSONB DEFAULT '[]',

    -- Reconciliation fields (NEW)
    reconciliation_status   VARCHAR(50) DEFAULT 'unmatched',
    matched_bank_tx_id      INTEGER REFERENCES bank_transactions(id),
    matched_expense_id      INTEGER REFERENCES manual_expenses(id),
    match_confidence        NUMERIC(3,2),
    matched_at              TIMESTAMP,
    matched_by              VARCHAR(50),

    -- Embedding for vector search
    description_embedding   VECTOR(1536),

    -- Timestamps
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at            TIMESTAMP,

    -- Constraints
    CHECK (reconciliation_status IN ('unmatched', 'partial', 'full', 'conflict')),
    CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed', 'partial')),
    CHECK (validation_status IN ('pending', 'validating', 'valid', 'invalid', 'warning')),
    CHECK (match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1))
);

-- Indexes for matching performance
CREATE INDEX idx_sat_invoices_emisor_rfc ON sat_invoices(emisor_rfc);
CREATE INDEX idx_sat_invoices_total ON sat_invoices(total);
CREATE INDEX idx_sat_invoices_fecha ON sat_invoices(fecha_emision);
CREATE INDEX idx_sat_invoices_uuid ON sat_invoices(uuid);
CREATE INDEX idx_sat_invoices_reconciliation ON sat_invoices(reconciliation_status) WHERE reconciliation_status = 'unmatched';
CREATE INDEX idx_sat_invoices_tenant ON sat_invoices(tenant_id, company_id);
CREATE INDEX idx_sat_invoices_batch ON sat_invoices(batch_id);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_sat_invoices_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sat_invoices_updated_at
BEFORE UPDATE ON sat_invoices
FOR EACH ROW
EXECUTE FUNCTION update_sat_invoices_updated_at();

COMMIT;
```

---

**Fin del Audit**
**Siguiente paso**: Ejecutar migration 052 para crear tabla `sat_invoices`
