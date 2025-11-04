ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS context_used TEXT;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS ai_model TEXT;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS context_confidence REAL;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS context_version INTEGER;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS company_id INTEGER;
