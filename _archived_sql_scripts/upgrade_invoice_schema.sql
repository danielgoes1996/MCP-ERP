-- UPGRADE INVOICE SCHEMA
-- Agrega campos faltantes para completar coherencia API ↔ BD
-- Funcionalidad #6: Procesamiento de Facturas

-- 1. Agregar campos faltantes a expense_invoices
ALTER TABLE expense_invoices ADD COLUMN uuid TEXT;
ALTER TABLE expense_invoices ADD COLUMN rfc_emisor TEXT;
ALTER TABLE expense_invoices ADD COLUMN nombre_emisor TEXT;
ALTER TABLE expense_invoices ADD COLUMN subtotal REAL;
ALTER TABLE expense_invoices ADD COLUMN iva_amount REAL;
ALTER TABLE expense_invoices ADD COLUMN total REAL;
ALTER TABLE expense_invoices ADD COLUMN moneda TEXT DEFAULT 'MXN';
ALTER TABLE expense_invoices ADD COLUMN fecha_emision TEXT;
ALTER TABLE expense_invoices ADD COLUMN xml_content TEXT;
ALTER TABLE expense_invoices ADD COLUMN pdf_content BLOB;
ALTER TABLE expense_invoices ADD COLUMN processing_status TEXT DEFAULT 'pending';
ALTER TABLE expense_invoices ADD COLUMN match_confidence REAL DEFAULT 0.0;
ALTER TABLE expense_invoices ADD COLUMN auto_matched BOOLEAN DEFAULT FALSE;
ALTER TABLE expense_invoices ADD COLUMN processed_at TIMESTAMP;
ALTER TABLE expense_invoices ADD COLUMN error_message TEXT;

-- 2. Crear índices para performance
CREATE INDEX IF NOT EXISTS idx_invoices_uuid ON expense_invoices(uuid);
CREATE INDEX IF NOT EXISTS idx_invoices_rfc ON expense_invoices(rfc_emisor);
CREATE INDEX IF NOT EXISTS idx_invoices_total ON expense_invoices(total);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON expense_invoices(processing_status);
CREATE INDEX IF NOT EXISTS idx_invoices_tenant_status ON expense_invoices(tenant_id, processing_status);
CREATE INDEX IF NOT EXISTS idx_invoices_expense_match ON expense_invoices(expense_id, match_confidence);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON expense_invoices(fecha_emision);
CREATE INDEX IF NOT EXISTS idx_invoices_processed ON expense_invoices(processed_at DESC);

-- 3. Crear tabla para histórico de matching
CREATE TABLE IF NOT EXISTS invoice_match_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    expense_id INTEGER,
    match_type TEXT NOT NULL, -- 'auto', 'manual', 'rejected'
    confidence REAL DEFAULT 0.0,
    match_criteria TEXT, -- JSON con los criterios usados
    matched_by INTEGER, -- user_id who performed the match
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    tenant_id INTEGER NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES expense_invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (matched_by) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 4. Índices para la tabla de histórico
CREATE INDEX IF NOT EXISTS idx_match_history_invoice ON invoice_match_history(invoice_id);
CREATE INDEX IF NOT EXISTS idx_match_history_expense ON invoice_match_history(expense_id);
CREATE INDEX IF NOT EXISTS idx_match_history_tenant ON invoice_match_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_match_history_date ON invoice_match_history(matched_at DESC);
CREATE INDEX IF NOT EXISTS idx_match_history_type ON invoice_match_history(match_type);

-- 5. Actualizar datos existentes con valores por defecto
UPDATE expense_invoices SET
    processing_status = 'processed',
    auto_matched = FALSE,
    match_confidence = 1.0,
    processed_at = created_at,
    moneda = 'MXN'
WHERE processing_status IS NULL;

-- 6. Trigger para actualizar timestamps
CREATE TRIGGER IF NOT EXISTS invoice_processed_at_update
    AFTER UPDATE ON expense_invoices
    FOR EACH ROW
    WHEN NEW.processing_status != OLD.processing_status AND NEW.processing_status = 'processed'
BEGIN
    UPDATE expense_invoices
    SET processed_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- 7. Vista para facturas con información enriquecida
CREATE VIEW IF NOT EXISTS invoice_details_view AS
SELECT
    i.*,
    e.description as expense_description,
    e.amount as expense_amount,
    e.category as expense_category,
    e.merchant_name,
    u.name as user_name,
    u.email as user_email,
    CASE
        WHEN i.total IS NOT NULL AND e.amount IS NOT NULL
        THEN ABS(i.total - e.amount)
        ELSE NULL
    END as amount_difference,
    CASE
        WHEN i.total IS NOT NULL AND e.amount IS NOT NULL
        THEN CASE
            WHEN ABS(i.total - e.amount) < 0.01 THEN 'exact'
            WHEN ABS(i.total - e.amount) < 1.0 THEN 'close'
            ELSE 'different'
        END
        ELSE 'unknown'
    END as amount_match_quality
FROM expense_invoices i
LEFT JOIN expense_records e ON i.expense_id = e.id
LEFT JOIN users u ON e.user_id = u.id;

-- 8. Actualizar metadatos de schema
INSERT OR IGNORE INTO schema_versions (version, description)
VALUES ('2.1.0', 'Enhanced Invoice Processing - Complete API-BD Coherence + Matching History');

PRAGMA foreign_keys = ON;