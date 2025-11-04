-- Migration 002: Add Missing Invoice Fields
-- Based on AUDITORIA_MAESTRA_SISTEMA_MCP findings
-- Priority: HIGH - These fields are referenced in API/UI but missing in DB

-- Add invoice breakdown fields
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS subtotal DECIMAL(10,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS iva_amount DECIMAL(10,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS discount DECIMAL(10,2) DEFAULT 0.0;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS retention DECIMAL(10,2) DEFAULT 0.0;

-- Add invoice metadata fields
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS xml_content TEXT;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS validation_status TEXT DEFAULT 'pending';
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS processing_metadata JSON;

-- Add template matching fields
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS template_match DECIMAL(3,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS validation_rules JSON;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS detected_format TEXT;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS parser_used TEXT;

-- Add OCR and processing fields
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS ocr_confidence DECIMAL(3,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS processing_metrics JSON;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS quality_score DECIMAL(3,2);
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS processor_used TEXT;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_invoices_validation_status ON invoices(validation_status);
CREATE INDEX IF NOT EXISTS idx_invoices_template_match ON invoices(template_match);
CREATE INDEX IF NOT EXISTS idx_invoices_detected_format ON invoices(detected_format);
CREATE INDEX IF NOT EXISTS idx_invoices_quality_score ON invoices(quality_score);

-- Update existing records with default values
UPDATE invoices
SET subtotal = total * 0.86,
    iva_amount = total * 0.14,
    validation_status = 'validated'
WHERE subtotal IS NULL AND total > 0;