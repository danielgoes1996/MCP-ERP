-- Migration: Expense-Ticket Escalation System
-- Date: 2025-01-15
-- Purpose: Vincular expense_records con tickets para escalamiento automático

-- 1. Agregar columnas a expense_records para tracking de escalamiento
-- Nota: will_have_cfdi ya existe, solo agregamos las columnas de escalamiento

ALTER TABLE expense_records ADD COLUMN escalated_to_invoicing BOOLEAN DEFAULT 0;
ALTER TABLE expense_records ADD COLUMN escalated_ticket_id INTEGER;
ALTER TABLE expense_records ADD COLUMN escalation_reason TEXT;
ALTER TABLE expense_records ADD COLUMN escalated_at TIMESTAMP;

-- 2. Agregar columnas a tickets para vincular con expense_records
ALTER TABLE tickets ADD COLUMN raw_data TEXT;
ALTER TABLE tickets ADD COLUMN tipo TEXT DEFAULT 'texto';
ALTER TABLE tickets ADD COLUMN estado TEXT DEFAULT 'pendiente';
ALTER TABLE tickets ADD COLUMN whatsapp_message_id TEXT;
ALTER TABLE tickets ADD COLUMN company_id TEXT DEFAULT 'default';
ALTER TABLE tickets ADD COLUMN original_image TEXT;
ALTER TABLE tickets ADD COLUMN merchant_id INTEGER;
ALTER TABLE tickets ADD COLUMN merchant_name TEXT;
ALTER TABLE tickets ADD COLUMN category TEXT;
ALTER TABLE tickets ADD COLUMN confidence REAL;
ALTER TABLE tickets ADD COLUMN invoice_data TEXT;
ALTER TABLE tickets ADD COLUMN llm_analysis TEXT;
ALTER TABLE tickets ADD COLUMN extracted_text TEXT;

-- 3. Columna clave: expense_id para vincular ticket espejo con gasto original
ALTER TABLE tickets ADD COLUMN expense_id INTEGER;
ALTER TABLE tickets ADD COLUMN is_mirror_ticket BOOLEAN DEFAULT 0;

-- 4. Crear índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_tickets_expense_id ON tickets(expense_id);
CREATE INDEX IF NOT EXISTS idx_tickets_company_id ON tickets(company_id);
CREATE INDEX IF NOT EXISTS idx_tickets_estado ON tickets(estado);
CREATE INDEX IF NOT EXISTS idx_tickets_mirror ON tickets(is_mirror_ticket, expense_id);

CREATE INDEX IF NOT EXISTS idx_expense_escalated ON expense_records(escalated_to_invoicing, will_have_cfdi);
CREATE INDEX IF NOT EXISTS idx_expense_escalated_ticket ON expense_records(escalated_ticket_id);

-- 5. Crear tabla de merchants si no existe (para Advanced Ticket Dashboard)
CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    metodo_facturacion TEXT NOT NULL,
    metadata TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_merchants_nombre ON merchants(nombre);
CREATE INDEX IF NOT EXISTS idx_merchants_active ON merchants(is_active);

-- 6. Crear tabla de invoicing_jobs si no existe
CREATE TABLE IF NOT EXISTS invoicing_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    merchant_id INTEGER,
    estado TEXT DEFAULT 'pendiente',
    resultado TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP,
    completed_at TIMESTAMP,
    company_id TEXT DEFAULT 'default',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

CREATE INDEX IF NOT EXISTS idx_invoicing_jobs_ticket ON invoicing_jobs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_invoicing_jobs_estado ON invoicing_jobs(estado);
CREATE INDEX IF NOT EXISTS idx_invoicing_jobs_company ON invoicing_jobs(company_id);

-- 7. Insertar versión de migración
CREATE TABLE IF NOT EXISTS schema_versions (
    version TEXT PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_versions (version, description)
VALUES ('1.1.0', 'Expense-Ticket Escalation System: Vincular gastos con tickets de facturación');

-- 8. Comentarios explicativos
-- expense_records.will_have_cfdi: TRUE = requiere factura, debe escalar a invoicing
-- expense_records.escalated_to_invoicing: TRUE = ya se creó ticket espejo
-- expense_records.escalated_ticket_id: ID del ticket espejo creado
-- tickets.expense_id: ID del gasto que originó este ticket (si es espejo)
-- tickets.is_mirror_ticket: TRUE = ticket creado por escalamiento automático
