-- Migration 001: Add Missing Expense Fields
-- Based on AUDITORIA_MAESTRA_SISTEMA_MCP findings
-- Priority: HIGH - These fields are referenced in API/UI but missing in DB

-- Add expense enhancement fields
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS deducible BOOLEAN DEFAULT TRUE;
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS centro_costo TEXT;
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS proyecto TEXT;
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS tags JSON;

-- Add audit and tracking fields
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS audit_trail JSON;
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS user_context TEXT;
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS enhanced_data JSON;

-- Add completion and validation fields
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS completion_status TEXT DEFAULT 'draft';
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS validation_errors JSON;
ALTER TABLE manual_expenses ADD COLUMN IF NOT EXISTS field_completeness DECIMAL(3,2) DEFAULT 0.0;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_expenses_deducible ON expenses(deducible);
CREATE INDEX IF NOT EXISTS idx_expenses_centro_costo ON expenses(centro_costo);
CREATE INDEX IF NOT EXISTS idx_expenses_proyecto ON expenses(proyecto);
CREATE INDEX IF NOT EXISTS idx_expenses_completion ON expenses(completion_status);

-- Update existing records to have valid completion status
UPDATE manual_expenses SET completion_status = 'complete' WHERE descripcion IS NOT NULL AND monto_total > 0;