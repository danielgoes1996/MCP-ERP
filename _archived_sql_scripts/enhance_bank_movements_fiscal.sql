-- Mejoras fiscales y de conciliación para bank_movements
-- Agregar campos para inteligencia financiera empresarial

-- Campos para información fiscal
ALTER TABLE bank_movements ADD COLUMN subcategory TEXT;
ALTER TABLE bank_movements ADD COLUMN tax_deductible BOOLEAN DEFAULT FALSE;
ALTER TABLE bank_movements ADD COLUMN requires_receipt BOOLEAN DEFAULT TRUE;
ALTER TABLE bank_movements ADD COLUMN iva_rate REAL DEFAULT 0.0;
ALTER TABLE bank_movements ADD COLUMN iva_amount REAL DEFAULT 0.0;

-- Campos para conciliación dinámica
ALTER TABLE bank_movements ADD COLUMN matched_cfdi_uuid TEXT;
ALTER TABLE bank_movements ADD COLUMN matched_whatsapp_id TEXT;
ALTER TABLE bank_movements ADD COLUMN matched_invoice_id TEXT;
ALTER TABLE bank_movements ADD COLUMN reconciliation_status TEXT DEFAULT 'pending'; -- pending, partial, complete
ALTER TABLE bank_movements ADD COLUMN reconciliation_confidence REAL DEFAULT 0.0;

-- Campos para análisis de flujo de efectivo
ALTER TABLE bank_movements ADD COLUMN cash_flow_category TEXT; -- operating, investing, financing
ALTER TABLE bank_movements ADD COLUMN business_purpose TEXT;
ALTER TABLE bank_movements ADD COLUMN project_code TEXT;

-- Campos para alertas y anomalías
ALTER TABLE bank_movements ADD COLUMN is_anomaly BOOLEAN DEFAULT FALSE;
ALTER TABLE bank_movements ADD COLUMN anomaly_reason TEXT;
ALTER TABLE bank_movements ADD COLUMN unusual_amount BOOLEAN DEFAULT FALSE;

-- Campos para tracking de cambios
ALTER TABLE bank_movements ADD COLUMN last_categorized_at TIMESTAMP;
ALTER TABLE bank_movements ADD COLUMN categorized_by TEXT DEFAULT 'system';
ALTER TABLE bank_movements ADD COLUMN manual_override BOOLEAN DEFAULT FALSE;

-- Índices para optimización
CREATE INDEX IF NOT EXISTS idx_bank_movements_subcategory ON bank_movements(subcategory);
CREATE INDEX IF NOT EXISTS idx_bank_movements_tax_deductible ON bank_movements(tax_deductible) WHERE tax_deductible = TRUE;
CREATE INDEX IF NOT EXISTS idx_bank_movements_reconciliation_status ON bank_movements(reconciliation_status);
CREATE INDEX IF NOT EXISTS idx_bank_movements_matched_cfdi ON bank_movements(matched_cfdi_uuid) WHERE matched_cfdi_uuid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bank_movements_cash_flow_category ON bank_movements(cash_flow_category);
CREATE INDEX IF NOT EXISTS idx_bank_movements_anomaly ON bank_movements(is_anomaly) WHERE is_anomaly = TRUE;
CREATE INDEX IF NOT EXISTS idx_bank_movements_categorized_at ON bank_movements(last_categorized_at DESC);