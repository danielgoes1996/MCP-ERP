-- =====================================================
-- Migration 046: Add Reconciliation Fields (LIGHTWEIGHT)
-- Database: PostgreSQL
-- Created: 2025-12-08
-- Description:
--   Solo agrega campos faltantes para reconciliación
--   NO recrea tablas, NO elimina datos
--   Compatible con estructura PostgreSQL existente
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: ALTER manual_expenses (agregar campos faltantes)
-- =====================================================

-- Agregar campos de reconciliación
ALTER TABLE manual_expenses
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

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_manual_expenses_reconciliation
    ON manual_expenses(provider_rfc, expense_date, amount)
    WHERE reconciliation_status = 'unmatched';

CREATE INDEX IF NOT EXISTS idx_manual_expenses_sat_invoice
    ON manual_expenses(sat_invoice_id)
    WHERE sat_invoice_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_manual_expenses_bank_tx
    ON manual_expenses(bank_transaction_id)
    WHERE bank_transaction_id IS NOT NULL;

-- =====================================================
-- STEP 2: ALTER bank_transactions (agregar vendor_rfc)
-- =====================================================

-- Nota: reconciliation_status, match_confidence, sat_invoice_id YA EXISTEN
-- Solo agregamos vendor_rfc y campos relacionados

ALTER TABLE bank_transactions
ADD COLUMN IF NOT EXISTS vendor_rfc VARCHAR(13),
ADD COLUMN IF NOT EXISTS vendor_rfc_source VARCHAR(20),
ADD COLUMN IF NOT EXISTS vendor_rfc_confidence NUMERIC(3,2),
ADD COLUMN IF NOT EXISTS manual_expense_id INTEGER REFERENCES manual_expenses(id),
ADD COLUMN IF NOT EXISTS reconciliation_layer VARCHAR(10),
ADD COLUMN IF NOT EXISTS reconciliation_date TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS reconciliation_notes TEXT,
ADD COLUMN IF NOT EXISTS match_explanation TEXT,
ADD COLUMN IF NOT EXISTS requires_manual_review BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS reviewed_by INTEGER,
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_bank_transactions_vendor_rfc
    ON bank_transactions(vendor_rfc)
    WHERE vendor_rfc IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bank_transactions_reconciliation
    ON bank_transactions(vendor_rfc, transaction_date, amount)
    WHERE reconciliation_status = 'unmatched' AND vendor_rfc IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_bank_transactions_manual_expense
    ON bank_transactions(manual_expense_id)
    WHERE manual_expense_id IS NOT NULL;

-- =====================================================
-- STEP 3: ALTER sat_invoices (columnas desnormalizadas)
-- =====================================================

-- ⚠️ NOTA: parsed_data YA está desnormalizado en el nivel raíz
-- No necesitamos columnas GENERATED porque podemos acceder directamente:
--   parsed_data->>'rfc_emisor', parsed_data->>'total', etc.
-- Solo agregamos campos de reconciliación

ALTER TABLE sat_invoices
-- Campos de reconciliación
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
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- Índices funcionales sobre JSONB (más simples que GENERATED columns)
-- PostgreSQL optimiza estos índices automáticamente
CREATE INDEX IF NOT EXISTS idx_sat_invoices_rfc_emisor
    ON sat_invoices((parsed_data->>'rfc_emisor'));

CREATE INDEX IF NOT EXISTS idx_sat_invoices_fecha
    ON sat_invoices((parsed_data->>'fecha_emision'));

CREATE INDEX IF NOT EXISTS idx_sat_invoices_total
    ON sat_invoices((parsed_data->>'total'));

-- Índice compuesto para Layer 0 matching (sin casts, PostgreSQL compara text)
CREATE INDEX IF NOT EXISTS idx_sat_invoices_reconciliation
    ON sat_invoices((parsed_data->>'rfc_emisor'), (parsed_data->>'fecha_emision'), (parsed_data->>'total'))
    WHERE reconciliation_status = 'unmatched';

CREATE INDEX IF NOT EXISTS idx_sat_invoices_bank_tx
    ON sat_invoices(bank_transaction_id)
    WHERE bank_transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sat_invoices_manual_expense
    ON sat_invoices(manual_expense_id)
    WHERE manual_expense_id IS NOT NULL;

-- =====================================================
-- STEP 4: Tabla de Matches (muchos-a-muchos)
-- =====================================================

CREATE TABLE IF NOT EXISTS reconciliation_matches (
    id SERIAL PRIMARY KEY,

    -- Referencias a las 3 fuentes
    manual_expense_id INTEGER REFERENCES manual_expenses(id) ON DELETE CASCADE,
    sat_invoice_id TEXT REFERENCES sat_invoices(id) ON DELETE CASCADE,
    bank_transaction_id INTEGER REFERENCES bank_transactions(id) ON DELETE CASCADE,

    -- Metadata del match
    match_layer VARCHAR(10) NOT NULL,  -- 'layer0_sql', 'layer1_math', 'layer2_vector', 'layer3_llm'
    confidence NUMERIC(3,2) NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    explanation TEXT,

    -- Montos asignados (para splits)
    manual_amount_allocated NUMERIC(15,2),
    sat_amount_allocated NUMERIC(15,2),
    bank_amount_allocated NUMERIC(15,2),

    -- Estado del match
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'accepted', 'rejected', 'superseded'
    requires_review BOOLEAN DEFAULT FALSE,

    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INTEGER,
    reviewed_by INTEGER,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- Tenant
    tenant_id INTEGER NOT NULL,

    -- Constraints: al menos 2 fuentes deben estar presentes
    CONSTRAINT at_least_two_sources CHECK (
        (manual_expense_id IS NOT NULL AND sat_invoice_id IS NOT NULL) OR
        (manual_expense_id IS NOT NULL AND bank_transaction_id IS NOT NULL) OR
        (sat_invoice_id IS NOT NULL AND bank_transaction_id IS NOT NULL)
    )
);

-- Índices para búsquedas
CREATE INDEX IF NOT EXISTS idx_reconciliation_matches_manual
    ON reconciliation_matches(manual_expense_id);

CREATE INDEX IF NOT EXISTS idx_reconciliation_matches_sat
    ON reconciliation_matches(sat_invoice_id);

CREATE INDEX IF NOT EXISTS idx_reconciliation_matches_bank
    ON reconciliation_matches(bank_transaction_id);

CREATE INDEX IF NOT EXISTS idx_reconciliation_matches_status
    ON reconciliation_matches(status, requires_review);

CREATE INDEX IF NOT EXISTS idx_reconciliation_matches_tenant
    ON reconciliation_matches(tenant_id, created_at DESC);

-- =====================================================
-- STEP 5: Copiar vendor_rfc inicial desde likely_vendor_rfc
-- =====================================================

-- Copiar RFCs ya detectados
UPDATE bank_transactions
SET
    vendor_rfc = likely_vendor_rfc,
    vendor_rfc_source = 'extracted',
    vendor_rfc_confidence = 0.70
WHERE likely_vendor_rfc IS NOT NULL
  AND vendor_rfc IS NULL
  AND likely_vendor_rfc ~ '^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$';  -- Validar formato RFC

-- =====================================================
-- STEP 6: Marcar status inicial
-- =====================================================

-- Manual expenses sin factura SAT
UPDATE manual_expenses
SET reconciliation_status = 'unmatched'
WHERE sat_invoice_id IS NULL
  AND reconciliation_status IS NULL;

-- Manual expenses CON factura SAT
UPDATE manual_expenses
SET reconciliation_status = 'matched',
    reconciliation_layer = 'existing',
    reconciliation_date = NOW()
WHERE sat_invoice_id IS NOT NULL
  AND reconciliation_status IS NULL;

-- Bank transactions
UPDATE bank_transactions
SET reconciliation_status = 'unmatched'
WHERE sat_invoice_id IS NULL
  AND reconciliation_status IS NULL;

UPDATE bank_transactions
SET reconciliation_status = 'matched',
    reconciliation_layer = 'existing',
    reconciliation_date = NOW()
WHERE sat_invoice_id IS NOT NULL
  AND reconciliation_status IS NULL;

-- SAT invoices
UPDATE sat_invoices
SET reconciliation_status = 'unmatched'
WHERE reconciliation_status IS NULL;

-- =====================================================
-- STEP 7: Update schema version
-- =====================================================

INSERT INTO schema_migrations (id, version, description, applied_at)
VALUES (
    (SELECT COALESCE(MAX(id), 0) + 1 FROM schema_migrations),
    '046',
    'Add reconciliation fields (lightweight)',
    NOW()
)
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- =====================================================
-- Verificación
-- =====================================================

-- Verificar columnas agregadas
SELECT
    'manual_expenses' as table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'manual_expenses'
  AND column_name IN ('bank_transaction_id', 'reconciliation_status', 'match_explanation')

UNION ALL

SELECT
    'bank_transactions' as table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'bank_transactions'
  AND column_name IN ('vendor_rfc', 'manual_expense_id', 'reconciliation_layer')

UNION ALL

SELECT
    'sat_invoices' as table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'sat_invoices'
  AND column_name IN ('invoice_rfc_emisor', 'invoice_date', 'reconciliation_status');

-- Contar registros sin RFC
SELECT
    'bank_transactions sin vendor_rfc' as check_type,
    COUNT(*) as count
FROM bank_transactions
WHERE vendor_rfc IS NULL

UNION ALL

SELECT
    'manual_expenses sin reconciliation_status' as check_type,
    COUNT(*) as count
FROM manual_expenses
WHERE reconciliation_status IS NULL;
