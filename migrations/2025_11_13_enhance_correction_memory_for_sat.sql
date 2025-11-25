-- Migration: Enhance ai_correction_memory for SAT classification learning
-- Date: 2025-11-13
-- Purpose: Add fields to enable self-training from accountant corrections

-- Add SAT-specific fields for invoice classification corrections
ALTER TABLE ai_correction_memory
ADD COLUMN IF NOT EXISTS provider_name TEXT,
ADD COLUMN IF NOT EXISTS provider_rfc TEXT,
ADD COLUMN IF NOT EXISTS clave_prod_serv TEXT,
ADD COLUMN IF NOT EXISTS original_sat_code TEXT,
ADD COLUMN IF NOT EXISTS corrected_sat_code TEXT,
ADD COLUMN IF NOT EXISTS corrected_by_user_id INTEGER,
ADD COLUMN IF NOT EXISTS corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS invoice_id INTEGER,
ADD COLUMN IF NOT EXISTS confidence_before DECIMAL(3,2);

-- Create indexes for fast lookup during classification
CREATE INDEX IF NOT EXISTS idx_corrections_company_provider
ON ai_correction_memory(company_id, provider_rfc)
WHERE provider_rfc IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_corrections_company_sat_code
ON ai_correction_memory(company_id, corrected_sat_code)
WHERE corrected_sat_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_corrections_company_clave_prod
ON ai_correction_memory(company_id, clave_prod_serv)
WHERE clave_prod_serv IS NOT NULL;

-- Add comments
COMMENT ON COLUMN ai_correction_memory.provider_name IS 'Provider/vendor name for pattern matching';
COMMENT ON COLUMN ai_correction_memory.provider_rfc IS 'Provider RFC for exact matching';
COMMENT ON COLUMN ai_correction_memory.clave_prod_serv IS 'SAT product/service key from CFDI';
COMMENT ON COLUMN ai_correction_memory.original_sat_code IS 'SAT code originally assigned by AI';
COMMENT ON COLUMN ai_correction_memory.corrected_sat_code IS 'SAT code corrected by accountant';
COMMENT ON COLUMN ai_correction_memory.corrected_by_user_id IS 'User ID who made the correction';
COMMENT ON COLUMN ai_correction_memory.corrected_at IS 'Timestamp of correction';
COMMENT ON COLUMN ai_correction_memory.invoice_id IS 'Reference to expense_invoices.id';
COMMENT ON COLUMN ai_correction_memory.confidence_before IS 'AI confidence before correction (0.0-1.0)';

-- Example of expected data after a correction:
-- {
--   "company_id": 2,
--   "original_description": "Servicios de facturación",
--   "provider_name": "FINKOK",
--   "provider_rfc": "FIN1203015JA",
--   "clave_prod_serv": "84111506",
--   "original_sat_code": "614.03",  -- AI suggested "Gastos de venta"
--   "corrected_sat_code": "613.01",  -- Accountant corrected to "Servicios administrativos"
--   "corrected_by_user_id": 5,
--   "corrected_at": "2025-11-13 14:30:00",
--   "confidence_before": 0.85
-- }
