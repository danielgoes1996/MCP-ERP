-- =====================================================
-- Rollback Migration 035: Revert expense_invoices Enhancement
-- Created: 2025-11-07
-- Description: Rollback all changes from migration 035
-- WARNING: This will drop columns and data - use with caution!
-- =====================================================

-- =====================================================
-- STEP 1: Drop invoice_import_logs table
-- =====================================================

DROP TABLE IF EXISTS invoice_import_logs;

-- =====================================================
-- STEP 2: Drop triggers
-- =====================================================

DROP TRIGGER IF EXISTS expense_invoices_calculate_total;
DROP TRIGGER IF EXISTS expense_invoices_update_total;

-- =====================================================
-- STEP 3: Recreate original expense_invoices table structure
-- =====================================================

-- Create the original table structure
CREATE TABLE expense_invoices_rollback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER,
    filename TEXT,
    file_path TEXT,
    content_type TEXT,
    parsed_data TEXT,
    tenant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subtotal REAL,
    iva_amount REAL,
    discount REAL DEFAULT 0.0,
    retention REAL DEFAULT 0.0,
    xml_content TEXT,
    validation_status TEXT DEFAULT 'pending',
    processing_metadata TEXT,
    template_match REAL,
    validation_rules TEXT,
    detected_format TEXT,
    parser_used TEXT,
    ocr_confidence REAL,
    processing_metrics TEXT,
    quality_score REAL,
    processor_used TEXT,
    extraction_confidence REAL,

    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Copy data back (only original columns)
INSERT INTO expense_invoices_rollback (
    id, expense_id, filename, file_path, content_type,
    parsed_data, tenant_id, created_at,
    subtotal, iva_amount, discount, retention,
    xml_content, validation_status, processing_metadata,
    template_match, validation_rules, detected_format,
    parser_used, ocr_confidence, processing_metrics,
    quality_score, processor_used, extraction_confidence
)
SELECT
    id, expense_id, filename, file_path, content_type,
    parsed_data, tenant_id, created_at,
    subtotal, iva_amount, discount, retention,
    xml_content, validation_status, processing_metadata,
    template_match, validation_rules, detected_format,
    parser_used, ocr_confidence, processing_metrics,
    quality_score, processor_used, extraction_confidence
FROM expense_invoices;

-- Drop new table
DROP TABLE expense_invoices;

-- Rename rollback table to original name
ALTER TABLE expense_invoices_rollback RENAME TO expense_invoices;

-- =====================================================
-- STEP 4: Recreate original indexes only
-- =====================================================

CREATE INDEX idx_expense_invoices_expense_id ON expense_invoices (expense_id);
CREATE INDEX idx_expense_invoices_validation_status ON expense_invoices(validation_status);
CREATE INDEX idx_expense_invoices_template_match ON expense_invoices(template_match);
CREATE INDEX idx_expense_invoices_detected_format ON expense_invoices(detected_format);
CREATE INDEX idx_expense_invoices_quality_score ON expense_invoices(quality_score);

-- =====================================================
-- STEP 5: Remove migration record
-- =====================================================

DELETE FROM schema_migrations WHERE version = '035';

-- =====================================================
-- STEP 6: Remove comments
-- =====================================================

DELETE FROM table_comments
WHERE table_name IN ('expense_invoices', 'invoice_import_logs')
AND created_at >= (
    SELECT created_at FROM schema_migrations
    WHERE version = '034'
    ORDER BY applied_at DESC
    LIMIT 1
);

-- =====================================================
-- Rollback Complete
-- =====================================================

SELECT 'Rollback completed successfully' as status;
