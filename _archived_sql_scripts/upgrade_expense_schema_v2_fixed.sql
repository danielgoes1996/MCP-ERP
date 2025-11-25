-- UPGRADE EXPENSE SCHEMA v2 - FIXED VERSION
-- Agrega campos faltantes para completar coherencia API ↔ BD
-- Funcionalidad #5: Gestión de Gastos

-- 1. Agregar campos de negocio faltantes (sin defaults problemáticos)
ALTER TABLE expense_records ADD COLUMN deducible BOOLEAN;
ALTER TABLE expense_records ADD COLUMN requiere_factura BOOLEAN;
ALTER TABLE expense_records ADD COLUMN centro_costo TEXT;
ALTER TABLE expense_records ADD COLUMN proyecto TEXT;
ALTER TABLE expense_records ADD COLUMN metodo_pago TEXT;
ALTER TABLE expense_records ADD COLUMN moneda TEXT;

-- 2. Agregar campos avanzados para mejor tracking
ALTER TABLE expense_records ADD COLUMN rfc_proveedor TEXT;
ALTER TABLE expense_records ADD COLUMN cfdi_uuid TEXT;
ALTER TABLE expense_records ADD COLUMN invoice_status TEXT;
ALTER TABLE expense_records ADD COLUMN bank_status TEXT;
ALTER TABLE expense_records ADD COLUMN approval_status TEXT;
ALTER TABLE expense_records ADD COLUMN approved_by INTEGER;
ALTER TABLE expense_records ADD COLUMN approved_at TIMESTAMP;

-- 3. Campos adicionales para auditoria
ALTER TABLE expense_records ADD COLUMN updated_at TIMESTAMP;
ALTER TABLE expense_records ADD COLUMN updated_by INTEGER;
ALTER TABLE expense_records ADD COLUMN metadata TEXT;

-- 4. Actualizar valores por defecto para campos nuevos
UPDATE expense_records SET
    deducible = TRUE,
    requiere_factura = TRUE,
    moneda = 'MXN',
    invoice_status = 'pending',
    bank_status = 'pending',
    approval_status = 'pending',
    updated_at = CURRENT_TIMESTAMP
WHERE deducible IS NULL;

-- 5. Crear tabla para tags (sistema de etiquetas)
CREATE TABLE IF NOT EXISTS expense_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT DEFAULT '#3498db',
    description TEXT,
    tenant_id INTEGER NOT NULL,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 6. Crear tabla de relación many-to-many para expense_tags
CREATE TABLE IF NOT EXISTS expense_tag_relations (
    expense_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (expense_id, tag_id),
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES expense_tags(id) ON DELETE CASCADE
);

-- 7. Crear tabla para adjuntos
CREATE TABLE IF NOT EXISTS expense_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    mime_type TEXT,
    attachment_type TEXT DEFAULT 'receipt',
    uploaded_by INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- 8. Crear índices para performance (después de agregar columnas)
CREATE INDEX IF NOT EXISTS idx_expense_deducible ON expense_records(deducible);
CREATE INDEX IF NOT EXISTS idx_expense_centro_costo ON expense_records(centro_costo);
CREATE INDEX IF NOT EXISTS idx_expense_proyecto ON expense_records(proyecto);
CREATE INDEX IF NOT EXISTS idx_expense_cfdi ON expense_records(cfdi_uuid);
CREATE INDEX IF NOT EXISTS idx_expense_invoice_status ON expense_records(invoice_status);
CREATE INDEX IF NOT EXISTS idx_expense_bank_status ON expense_records(bank_status);
CREATE INDEX IF NOT EXISTS idx_expense_approval ON expense_records(approval_status);
CREATE INDEX IF NOT EXISTS idx_expense_updated ON expense_records(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_expense_moneda ON expense_records(moneda);
CREATE INDEX IF NOT EXISTS idx_expense_metodo_pago ON expense_records(metodo_pago);

-- Índices para tags
CREATE INDEX IF NOT EXISTS idx_expense_tags_tenant ON expense_tags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_expense_tags_name ON expense_tags(name);
CREATE INDEX IF NOT EXISTS idx_tag_relations_expense ON expense_tag_relations(expense_id);
CREATE INDEX IF NOT EXISTS idx_tag_relations_tag ON expense_tag_relations(tag_id);

-- Índices para attachments
CREATE INDEX IF NOT EXISTS idx_attachments_expense ON expense_attachments(expense_id);
CREATE INDEX IF NOT EXISTS idx_attachments_type ON expense_attachments(attachment_type);
CREATE INDEX IF NOT EXISTS idx_attachments_uploaded ON expense_attachments(uploaded_at DESC);

-- 9. Insertar tags predeterminados para el tenant principal
INSERT OR IGNORE INTO expense_tags (name, color, description, tenant_id, created_by)
VALUES
('Combustible', '#e74c3c', 'Gastos de gasolina y combustibles', 1, 1),
('Comida', '#f39c12', 'Gastos de alimentación y restaurantes', 1, 1),
('Transporte', '#3498db', 'Gastos de transporte y viajes', 1, 1),
('Oficina', '#9b59b6', 'Gastos de oficina y suministros', 1, 1),
('Tecnología', '#1abc9c', 'Gastos de tecnología y software', 1, 1),
('Marketing', '#e67e22', 'Gastos de marketing y publicidad', 1, 1),
('Urgente', '#c0392b', 'Gastos urgentes que requieren atención inmediata', 1, 1),
('Recurrente', '#7f8c8d', 'Gastos que se repiten mensualmente', 1, 1);

-- 10. Crear trigger para actualizar updated_at automáticamente
CREATE TRIGGER IF NOT EXISTS expense_records_updated_at
    AFTER UPDATE ON expense_records
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE expense_records
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- 11. Actualizar metadatos de schema
UPDATE schema_versions
SET version = '2.0.0',
    description = 'Enhanced Expense Management - Complete API-BD Coherence + Tags System'
WHERE version = '1.1.0';

INSERT OR IGNORE INTO schema_versions (version, description)
VALUES ('2.0.0', 'Enhanced Expense Management - Complete API-BD Coherence + Tags System');

PRAGMA foreign_keys = ON;