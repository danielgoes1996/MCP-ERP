-- COMPLETAR TABLAS FALTANTES PARA EXPENSE MANAGEMENT
-- Solo crea las tablas que no existen

-- 1. Verificar y crear tabla de tags
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

-- 2. Crear tabla de relación many-to-many para expense_tags
CREATE TABLE IF NOT EXISTS expense_tag_relations (
    expense_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (expense_id, tag_id),
    FOREIGN KEY (expense_id) REFERENCES expense_records(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES expense_tags(id) ON DELETE CASCADE
);

-- 3. Crear tabla para adjuntos
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

-- 4. Crear índices para tags
CREATE INDEX IF NOT EXISTS idx_expense_tags_tenant ON expense_tags(tenant_id);
CREATE INDEX IF NOT EXISTS idx_expense_tags_name ON expense_tags(name);
CREATE INDEX IF NOT EXISTS idx_tag_relations_expense ON expense_tag_relations(expense_id);
CREATE INDEX IF NOT EXISTS idx_tag_relations_tag ON expense_tag_relations(tag_id);

-- 5. Crear índices para attachments
CREATE INDEX IF NOT EXISTS idx_attachments_expense ON expense_attachments(expense_id);
CREATE INDEX IF NOT EXISTS idx_attachments_type ON expense_attachments(attachment_type);
CREATE INDEX IF NOT EXISTS idx_attachments_uploaded ON expense_attachments(uploaded_at DESC);

-- 6. Insertar tags predeterminados para el tenant principal
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

-- 7. Actualizar metadatos de schema si no existe
INSERT OR IGNORE INTO schema_versions (version, description)
VALUES ('2.0.0', 'Enhanced Expense Management - Complete API-BD Coherence + Tags System');

-- 8. Actualizar registros existentes para tener valores predeterminados
UPDATE expense_records SET
    updated_at = CURRENT_TIMESTAMP
WHERE updated_at IS NULL;