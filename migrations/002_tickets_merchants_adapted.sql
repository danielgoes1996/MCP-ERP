-- ===============================================================
-- MIGRACIÓN ADAPTADA: Tickets y Merchants para MCP System
-- Compatible con manual_expenses (INTEGER) y departments existentes
-- ===============================================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ===============================================================
-- 1. TABLA MERCHANTS (Catálogo de Comercios)
-- ===============================================================
CREATE TABLE IF NOT EXISTS merchants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Información básica
    name VARCHAR(255) NOT NULL,
    rfc VARCHAR(13),

    -- Configuración de facturación
    invoicing_method VARCHAR(50) NOT NULL, -- 'portal', 'email', 'api'
    portal_url VARCHAR(500),
    portal_config JSONB DEFAULT '{}',

    -- Patrones de identificación (para clasificador)
    regex_patterns JSONB DEFAULT '[]',  -- ["PEMEX", "GASOLINERA.*PEMEX"]
    keywords JSONB DEFAULT '[]',         -- ["pemex", "gasolinera"]

    -- Metadata adicional
    metadata JSONB DEFAULT '{}',  -- credenciales, configs específicas

    -- Estado y estadísticas
    is_active BOOLEAN DEFAULT true,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    total_processed INTEGER DEFAULT 0,

    -- Auditoría
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);

-- Índices para merchants
CREATE INDEX IF NOT EXISTS idx_merchants_tenant ON merchants(tenant_id);
CREATE INDEX IF NOT EXISTS idx_merchants_active ON merchants(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_merchants_name_trgm ON merchants USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_merchants_rfc ON merchants(rfc);

-- ===============================================================
-- 2. TABLA TICKETS (Tickets de Compra/Gastos)
-- ===============================================================
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Relaciones (compatible con sistema actual)
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id),  -- INTEGER, no UUID
    user_id INTEGER NOT NULL REFERENCES users(id),
    merchant_id UUID REFERENCES merchants(id),
    expense_id INTEGER REFERENCES manual_expenses(id),  -- ← Bidireccionalidad

    -- Información del merchant (desnormalizado para performance)
    merchant_name VARCHAR(255),
    merchant_confidence DECIMAL(3,2),  -- 0.00 - 1.00

    -- Origen del ticket
    source_type VARCHAR(20) NOT NULL, -- 'upload', 'whatsapp', 'email', 'voice'
    source_module VARCHAR(50) DEFAULT 'manual_upload',

    -- Contenido original
    raw_file_url VARCHAR(500),
    raw_data TEXT,  -- Texto extraído o datos originales
    mime_type VARCHAR(100),

    -- Datos extraídos (OCR/IA)
    ocr_data JSONB DEFAULT '{}',  -- {text, confidence, language}
    extracted_data JSONB DEFAULT '{}',  -- {amount, date, merchant, items}

    -- Datos fiscales
    folio VARCHAR(100),
    ticket_date DATE,
    subtotal DECIMAL(12,2),
    iva DECIMAL(12,2),
    total DECIMAL(12,2),
    currency VARCHAR(3) DEFAULT 'MXN',

    -- Estados
    status VARCHAR(50) DEFAULT 'pending',
    -- 'pending', 'processing', 'processed', 'matched_to_expense', 'failed'
    processing_status VARCHAR(50) DEFAULT 'pending',
    invoice_status VARCHAR(50) DEFAULT 'pending',

    -- Facturación
    will_have_cfdi BOOLEAN DEFAULT true,
    cfdi_uuid VARCHAR(36),
    cfdi_xml_url VARCHAR(500),
    cfdi_pdf_url VARCHAR(500),
    cfdi_data JSONB,

    -- Logs y errores
    processing_logs JSONB DEFAULT '[]',
    error_messages JSONB DEFAULT '[]',

    -- Metadata adicional
    metadata JSONB DEFAULT '{}',

    -- Auditoría
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para tickets
CREATE INDEX IF NOT EXISTS idx_tickets_tenant ON tickets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tickets_company ON tickets(company_id);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_merchant ON tickets(merchant_id);
CREATE INDEX IF NOT EXISTS idx_tickets_expense ON tickets(expense_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tickets_user_created ON tickets(user_id, created_at DESC);

-- Índice compuesto para dashboard por departamento
CREATE INDEX IF NOT EXISTS idx_tickets_user_merchant_date
ON tickets(user_id, merchant_id, created_at DESC);

-- ===============================================================
-- 3. AGREGAR COLUMNA A MANUAL_EXPENSES (Bidireccionalidad)
-- ===============================================================
ALTER TABLE manual_expenses
ADD COLUMN IF NOT EXISTS ticket_id UUID REFERENCES tickets(id);

-- Índice para la relación bidireccional
CREATE INDEX IF NOT EXISTS idx_manual_expenses_ticket
ON manual_expenses(ticket_id);

-- ===============================================================
-- 4. TABLA INVOICE_AUTOMATION_JOBS (Jobs de Facturación)
-- ===============================================================
CREATE TABLE IF NOT EXISTS invoice_automation_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Relaciones
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    merchant_id UUID REFERENCES merchants(id),

    -- Configuración del job
    job_type VARCHAR(20) NOT NULL DEFAULT 'auto_invoice',
    priority INTEGER DEFAULT 5,

    -- Estado
    status VARCHAR(20) DEFAULT 'pending',
    scheduled_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,

    -- Ejecución
    execution_config JSONB DEFAULT '{}',
    max_retries INTEGER DEFAULT 3,
    retry_count INTEGER DEFAULT 0,

    -- Resultados
    execution_result JSONB,
    error_details JSONB,
    ai_plan JSONB,
    execution_steps JSONB DEFAULT '[]',

    -- Auditoría
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para jobs
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON invoice_automation_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_ticket ON invoice_automation_jobs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON invoice_automation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_scheduled ON invoice_automation_jobs(scheduled_at);

-- ===============================================================
-- 5. TRIGGERS PARA UPDATED_AT
-- ===============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_merchants_updated_at
BEFORE UPDATE ON merchants
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tickets_updated_at
BEFORE UPDATE ON tickets
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at
BEFORE UPDATE ON invoice_automation_jobs
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===============================================================
-- 6. COMENTARIOS EN TABLAS
-- ===============================================================
COMMENT ON TABLE merchants IS 'Catálogo de comercios/proveedores para clasificación automática';
COMMENT ON TABLE tickets IS 'Tickets de compra subidos por usuarios (evidencias de gasto)';
COMMENT ON TABLE invoice_automation_jobs IS 'Jobs de facturación automática (RPA)';

COMMENT ON COLUMN tickets.expense_id IS 'Vínculo bidireccional con manual_expenses';
COMMENT ON COLUMN tickets.merchant_confidence IS 'Confianza de clasificación (0.00-1.00)';
COMMENT ON COLUMN tickets.status IS 'Estado del ticket: pending, processed, matched_to_expense';
COMMENT ON COLUMN manual_expenses.ticket_id IS 'Vínculo bidireccional con tickets';
