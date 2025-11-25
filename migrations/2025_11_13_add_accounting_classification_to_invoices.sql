-- Migration: Add accounting classification to expense_invoices
-- Date: 2025-11-13
-- Purpose: Move classification from sessions to invoices (single source of truth)

-- Add classification column
ALTER TABLE expense_invoices
ADD COLUMN IF NOT EXISTS accounting_classification JSONB;

-- Add optional session reference for audit trail
ALTER TABLE expense_invoices
ADD COLUMN IF NOT EXISTS session_id TEXT;

-- Create GIN index for fast JSONB queries
CREATE INDEX IF NOT EXISTS idx_expense_invoices_classification_gin
ON expense_invoices USING GIN (accounting_classification);

-- Create index for classification status (for pending queries)
CREATE INDEX IF NOT EXISTS idx_expense_invoices_classification_status
ON expense_invoices ((accounting_classification->>'status'))
WHERE accounting_classification IS NOT NULL;

-- Create index for SAT account code (for reporting)
CREATE INDEX IF NOT EXISTS idx_expense_invoices_sat_code
ON expense_invoices ((accounting_classification->>'sat_account_code'))
WHERE accounting_classification->>'sat_account_code' IS NOT NULL;

-- Create index for session_id (optional FK)
CREATE INDEX IF NOT EXISTS idx_expense_invoices_session_id
ON expense_invoices (session_id)
WHERE session_id IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN expense_invoices.accounting_classification IS
'AI-powered accounting classification (JSONB): {
  "sat_account_code": "601.84.01",
  "family_code": "601",
  "confidence_sat": 0.82,
  "status": "pending_confirmation|confirmed|corrected|not_classified",
  "classified_at": "2025-11-12T10:30:00Z",
  "confirmed_at": null,
  "confirmed_by": null,
  "corrected_at": null,
  "corrected_sat_code": null,
  "correction_notes": null,
  "explanation_short": "Brief explanation",
  "model_version": "claude-3-haiku-20240307"
}';

COMMENT ON COLUMN expense_invoices.session_id IS
'Optional reference to sat_invoices.id for audit trail';
