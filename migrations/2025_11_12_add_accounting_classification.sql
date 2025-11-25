-- Migration: Add accounting_classification to sat_invoices
-- Date: 2025-11-12
-- Purpose: Enable AI-powered accounting classification for invoices
-- Author: System (Fase 1 - v1)

-- ============================================================================
-- Add accounting_classification column
-- ============================================================================

ALTER TABLE sat_invoices
    ADD COLUMN IF NOT EXISTS accounting_classification JSONB;

COMMENT ON COLUMN sat_invoices.accounting_classification IS
'AI-powered accounting classification result. Structure:
{
  "sat_account_code": "601.84.01",
  "family_code": "601",
  "confidence_sat": 0.92,
  "status": "pending_confirmation" | "confirmed" | "corrected" | "not_classified",
  "classified_at": "2025-11-12T10:30:00Z",
  "confirmed_at": null,
  "confirmed_by": null,
  "corrected_at": null,
  "corrected_sat_code": null,
  "correction_notes": null,
  "explanation_short": "Compra de materia prima agrícola"
}';

-- ============================================================================
-- Create indexes for fast queries
-- ============================================================================

-- Index for filtering by SAT account code
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_accounting_code
    ON sat_invoices((accounting_classification->>'sat_account_code'))
    WHERE accounting_classification IS NOT NULL;

-- Index for filtering pending confirmations
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_accounting_status
    ON sat_invoices((accounting_classification->>'status'))
    WHERE accounting_classification->>'status' = 'pending_confirmation';

-- Composite index for company + classification status queries
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_company_accounting
    ON sat_invoices(company_id, (accounting_classification->>'status'))
    WHERE accounting_classification IS NOT NULL;

-- ============================================================================
-- Verification queries (for testing)
-- ============================================================================

-- Check column was added
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'sat_invoices'
        AND column_name = 'accounting_classification'
    ) THEN
        RAISE NOTICE 'SUCCESS: Column accounting_classification added to sat_invoices';
    ELSE
        RAISE EXCEPTION 'ERROR: Column accounting_classification was not added';
    END IF;
END $$;

-- Check indexes were created
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'sat_invoices'
        AND indexname = 'idx_universal_invoice_sessions_accounting_code'
    ) THEN
        RAISE NOTICE 'SUCCESS: Index idx_universal_invoice_sessions_accounting_code created';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'sat_invoices'
        AND indexname = 'idx_universal_invoice_sessions_accounting_status'
    ) THEN
        RAISE NOTICE 'SUCCESS: Index idx_universal_invoice_sessions_accounting_status created';
    END IF;
END $$;
