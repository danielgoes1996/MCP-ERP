-- =====================================================
-- Migration 035: Enhance expense_invoices with Fiscal Fields and Traceability
-- Created: 2025-11-07
-- Description:
--   1. Add fiscal CFDI fields (UUID, RFC, dates, tax details)
--   2. Add computed total column
--   3. Make critical columns NOT NULL
--   4. Create indexes for performance
--   5. Create invoice_import_logs table for audit trail
-- =====================================================

-- Disable foreign key constraints temporarily
PRAGMA foreign_keys = OFF;

-- Start transaction
BEGIN TRANSACTION;

-- =====================================================
-- STEP 1: Cleanup - Set default values for existing NULL records
-- =====================================================

UPDATE expense_invoices SET filename = 'unknown' WHERE filename IS NULL;
UPDATE expense_invoices SET content_type = 'unknown' WHERE content_type IS NULL;
UPDATE expense_invoices SET tenant_id = 1 WHERE tenant_id IS NULL;
DELETE FROM expense_invoices WHERE expense_id IS NULL;

-- =====================================================
-- STEP 2: Drop bank_match_links temporarily (will recreate later)
-- =====================================================

DROP TABLE IF EXISTS bank_match_links;

-- =====================================================
-- STEP 4: SQLite doesn't support ALTER COLUMN, so we need to recreate the table
--         with NOT NULL constraints
-- =====================================================

-- Create new table with NOT NULL constraints
CREATE TABLE expense_invoices_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Core Relations (NOT NULL)
    expense_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,

    -- File Information (NOT NULL)
    filename TEXT NOT NULL,
    file_path TEXT,
    content_type TEXT NOT NULL,

    -- CFDI Identification
    uuid TEXT,
    rfc_emisor TEXT,
    nombre_emisor TEXT,
    rfc_receptor TEXT,

    -- CFDI Dates
    fecha_emision TIMESTAMP,
    fecha_timbrado TIMESTAMP,

    -- CFDI Status and Version
    cfdi_status TEXT DEFAULT 'vigente',
    version_cfdi TEXT DEFAULT '4.0',

    -- Amounts
    subtotal REAL,
    iva_amount REAL,
    discount REAL DEFAULT 0.0,
    retention REAL DEFAULT 0.0,
    total REAL,

    -- Tax Details
    tasa REAL,
    tipo_impuesto TEXT,
    tipo_factor TEXT,
    isr_retenido REAL DEFAULT 0,
    iva_retenido REAL DEFAULT 0,
    ieps REAL DEFAULT 0,
    otros_impuestos REAL DEFAULT 0,

    -- Organization and Import
    mes_fiscal TEXT,
    xml_path TEXT,
    origen_importacion TEXT DEFAULT 'manual',

    -- Content
    xml_content TEXT,
    parsed_data TEXT,

    -- Processing
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

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Keys
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Copy data from old table to new table
INSERT INTO expense_invoices_new (
    id, expense_id, tenant_id, filename, file_path, content_type,
    subtotal, iva_amount, discount, retention,
    xml_content, parsed_data,
    validation_status, processing_metadata, template_match, validation_rules,
    detected_format, parser_used, ocr_confidence, processing_metrics,
    quality_score, processor_used, extraction_confidence,
    created_at
)
SELECT
    id, expense_id, tenant_id, filename, file_path, content_type,
    subtotal, iva_amount, discount, retention,
    xml_content, parsed_data,
    validation_status, processing_metadata, template_match, validation_rules,
    detected_format, parser_used, ocr_confidence, processing_metrics,
    quality_score, processor_used, extraction_confidence,
    created_at
FROM expense_invoices;

-- Drop old table
DROP TABLE expense_invoices;

-- Rename new table
ALTER TABLE expense_invoices_new RENAME TO expense_invoices;

-- =====================================================
-- STEP 4: Create Indexes
-- =====================================================

-- Existing indexes (recreate them)
CREATE INDEX idx_expense_invoices_expense_id ON expense_invoices (expense_id);
CREATE INDEX idx_expense_invoices_validation_status ON expense_invoices(validation_status);
CREATE INDEX idx_expense_invoices_template_match ON expense_invoices(template_match);
CREATE INDEX idx_expense_invoices_detected_format ON expense_invoices(detected_format);
CREATE INDEX idx_expense_invoices_quality_score ON expense_invoices(quality_score);

-- New indexes for fiscal fields
CREATE UNIQUE INDEX idx_expense_invoices_uuid ON expense_invoices(uuid) WHERE uuid IS NOT NULL;
CREATE INDEX idx_expense_invoices_mes_fiscal ON expense_invoices(mes_fiscal);
CREATE INDEX idx_expense_invoices_cfdi_status ON expense_invoices(cfdi_status);
CREATE INDEX idx_expense_invoices_tenant_id ON expense_invoices(tenant_id);
CREATE INDEX idx_expense_invoices_rfc_emisor ON expense_invoices(rfc_emisor);
CREATE INDEX idx_expense_invoices_fecha_emision ON expense_invoices(fecha_emision);
CREATE INDEX idx_expense_invoices_origen ON expense_invoices(origen_importacion);

-- Compound indexes for common queries
CREATE INDEX idx_expense_invoices_tenant_status ON expense_invoices(tenant_id, cfdi_status);
CREATE INDEX idx_expense_invoices_tenant_mes ON expense_invoices(tenant_id, mes_fiscal);
CREATE INDEX idx_expense_invoices_tenant_fecha ON expense_invoices(tenant_id, fecha_emision);

-- =====================================================
-- STEP 5: Create Trigger to Auto-Calculate Total
-- =====================================================

CREATE TRIGGER expense_invoices_calculate_total
    AFTER INSERT ON expense_invoices
    FOR EACH ROW
    WHEN NEW.total IS NULL
BEGIN
    UPDATE expense_invoices
    SET total = COALESCE(NEW.subtotal, 0)
                + COALESCE(NEW.iva_amount, 0)
                - COALESCE(NEW.discount, 0)
                - COALESCE(NEW.retention, 0)
                + COALESCE(NEW.ieps, 0)
                + COALESCE(NEW.otros_impuestos, 0)
                - COALESCE(NEW.isr_retenido, 0)
                - COALESCE(NEW.iva_retenido, 0)
    WHERE id = NEW.id;
END;

CREATE TRIGGER expense_invoices_update_total
    AFTER UPDATE OF subtotal, iva_amount, discount, retention, ieps, otros_impuestos, isr_retenido, iva_retenido ON expense_invoices
    FOR EACH ROW
BEGIN
    UPDATE expense_invoices
    SET total = COALESCE(NEW.subtotal, 0)
                + COALESCE(NEW.iva_amount, 0)
                - COALESCE(NEW.discount, 0)
                - COALESCE(NEW.retention, 0)
                + COALESCE(NEW.ieps, 0)
                + COALESCE(NEW.otros_impuestos, 0)
                - COALESCE(NEW.isr_retenido, 0)
                - COALESCE(NEW.iva_retenido, 0)
    WHERE id = NEW.id;
END;

-- =====================================================
-- STEP 6: Create invoice_import_logs table
-- =====================================================

CREATE TABLE invoice_import_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Import Details
    filename TEXT NOT NULL,
    uuid_detectado TEXT,
    tenant_id INTEGER NOT NULL,

    -- Status and Error Handling
    status TEXT NOT NULL CHECK(status IN ('success', 'error', 'duplicate', 'skipped', 'pending')),
    error_message TEXT,

    -- Source and Method
    source TEXT DEFAULT 'manual',  -- manual, email, api, bulk_upload, automation
    import_method TEXT,  -- drag_drop, file_upload, email_forward, api_call

    -- Metadata
    file_size INTEGER,
    file_hash TEXT,  -- MD5 or SHA256 hash to detect exact duplicates
    detected_format TEXT,  -- XML, PDF, JPG, PNG
    processing_time_ms INTEGER,

    -- User Context
    imported_by INTEGER,  -- FK to users.id
    batch_id TEXT,  -- For bulk imports

    -- Timestamps
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,

    -- Additional Info
    invoice_id INTEGER,  -- FK to expense_invoices.id if created
    expense_id INTEGER,  -- FK to expense_records.id if matched

    -- Metadata JSON
    metadata TEXT,  -- JSON with additional context

    -- Foreign Keys
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (imported_by) REFERENCES users(id),
    FOREIGN KEY (invoice_id) REFERENCES expense_invoices(id) ON DELETE SET NULL,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE SET NULL
);

-- =====================================================
-- STEP 7: Create Indexes for invoice_import_logs
-- =====================================================

CREATE INDEX idx_invoice_import_logs_tenant ON invoice_import_logs(tenant_id);
CREATE INDEX idx_invoice_import_logs_status ON invoice_import_logs(status);
CREATE INDEX idx_invoice_import_logs_uuid ON invoice_import_logs(uuid_detectado);
CREATE INDEX idx_invoice_import_logs_date ON invoice_import_logs(import_date DESC);
CREATE INDEX idx_invoice_import_logs_batch ON invoice_import_logs(batch_id);
CREATE INDEX idx_invoice_import_logs_source ON invoice_import_logs(source);
CREATE INDEX idx_invoice_import_logs_file_hash ON invoice_import_logs(file_hash);

-- Compound indexes for common queries
CREATE INDEX idx_invoice_import_logs_tenant_status ON invoice_import_logs(tenant_id, status);
CREATE INDEX idx_invoice_import_logs_tenant_date ON invoice_import_logs(tenant_id, import_date DESC);

-- =====================================================
-- STEP 8: Add comments (SQLite doesn't support COMMENT, so we use a metadata table)
-- =====================================================

-- Create table_comments if it doesn't exist
CREATE TABLE IF NOT EXISTS table_comments (
    table_name TEXT NOT NULL,
    column_name TEXT,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (table_name, column_name)
);

-- Add comments for new columns
INSERT OR REPLACE INTO table_comments (table_name, column_name, comment) VALUES
    ('expense_invoices', 'uuid', 'UUID del CFDI (Folio Fiscal)'),
    ('expense_invoices', 'rfc_emisor', 'RFC de quien emite la factura'),
    ('expense_invoices', 'nombre_emisor', 'Razón social del emisor'),
    ('expense_invoices', 'rfc_receptor', 'RFC de quien recibe la factura'),
    ('expense_invoices', 'fecha_emision', 'Fecha en que se emitió la factura'),
    ('expense_invoices', 'fecha_timbrado', 'Fecha en que el SAT timbró el CFDI'),
    ('expense_invoices', 'cfdi_status', 'Estado del CFDI: vigente, cancelado'),
    ('expense_invoices', 'version_cfdi', 'Versión del CFDI (3.3 o 4.0)'),
    ('expense_invoices', 'mes_fiscal', 'Mes fiscal en formato YYYY-MM para agrupación'),
    ('expense_invoices', 'xml_path', 'Ruta al archivo XML CFDI'),
    ('expense_invoices', 'origen_importacion', 'Origen: manual, email, api, bulk'),
    ('expense_invoices', 'total', 'Total calculado automáticamente'),
    ('expense_invoices', 'tasa', 'Tasa del impuesto (ej: 0.16 para IVA 16%)'),
    ('expense_invoices', 'tipo_impuesto', 'Tipo: IVA, ISR, IEPS'),
    ('expense_invoices', 'tipo_factor', 'Tasa, Cuota, Exento'),
    ('expense_invoices', 'isr_retenido', 'ISR retenido en la factura'),
    ('expense_invoices', 'iva_retenido', 'IVA retenido en la factura'),
    ('expense_invoices', 'ieps', 'IEPS aplicado'),
    ('expense_invoices', 'otros_impuestos', 'Otros impuestos aplicados'),
    ('invoice_import_logs', NULL, 'Registro de todas las importaciones de facturas'),
    ('invoice_import_logs', 'status', 'success: importado, error: falló, duplicate: duplicado'),
    ('invoice_import_logs', 'file_hash', 'Hash MD5/SHA256 para detectar archivos exactamente iguales'),
    ('invoice_import_logs', 'batch_id', 'ID de lote para importaciones masivas');

-- =====================================================
-- STEP 9: Recreate bank_match_links with correct FK to expense_invoices.uuid
-- =====================================================

CREATE TABLE bank_match_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_movement_id INTEGER NOT NULL,
    expense_id INTEGER,
    cfdi_uuid TEXT,
    monto_asignado REAL NOT NULL,
    score REAL,
    source TEXT,
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    tenant_id INTEGER,

    -- Foreign Keys (cfdi_uuid now references expense_invoices.uuid correctly)
    FOREIGN KEY (bank_movement_id) REFERENCES bank_movements(id) ON DELETE CASCADE,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (cfdi_uuid) REFERENCES expense_invoices(uuid),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),

    UNIQUE (bank_movement_id, expense_id, cfdi_uuid)
);

-- Create indexes for bank_match_links
CREATE INDEX idx_bank_match_links_movement ON bank_match_links(bank_movement_id);
CREATE INDEX idx_bank_match_links_expense ON bank_match_links(expense_id);
CREATE INDEX idx_bank_match_links_uuid ON bank_match_links(cfdi_uuid);
CREATE INDEX idx_bank_match_links_tenant ON bank_match_links(tenant_id);

-- =====================================================
-- STEP 10: Insert sample data for testing (optional)
-- =====================================================

-- This section is commented out - uncomment if you want sample data

/*
INSERT INTO invoice_import_logs (
    filename, uuid_detectado, tenant_id, status, source,
    import_method, imported_by, batch_id
) VALUES
    ('factura_001.xml', 'A1B2C3D4-E5F6-7890-ABCD-EF1234567890', 2, 'success', 'manual', 'drag_drop', 1, NULL),
    ('factura_002.xml', 'B2C3D4E5-F6G7-8901-BCDE-FG2345678901', 2, 'duplicate', 'manual', 'drag_drop', 1, NULL),
    ('factura_003.pdf', NULL, 2, 'error', 'manual', 'file_upload', 1, NULL);
*/

-- =====================================================
-- STEP 11: Update schema version
-- =====================================================

INSERT INTO schema_migrations (version, description)
VALUES ('035', 'Enhance expense_invoices with fiscal fields and create invoice_import_logs');

-- =====================================================
-- Migration Complete
-- =====================================================

-- Commit transaction
COMMIT;

-- Re-enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Verify the migration
SELECT
    'expense_invoices columns' as check_type,
    COUNT(*) as column_count
FROM pragma_table_info('expense_invoices')

UNION ALL

SELECT
    'expense_invoices indexes' as check_type,
    COUNT(*) as index_count
FROM sqlite_master
WHERE type = 'index'
AND tbl_name = 'expense_invoices'

UNION ALL

SELECT
    'invoice_import_logs exists' as check_type,
    COUNT(*) as table_exists
FROM sqlite_master
WHERE type = 'table'
AND name = 'invoice_import_logs';
