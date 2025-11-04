
-- POSTGRESQL SCHEMA FOR MCP SYSTEM
-- Migración desde SQLite unificado

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. TENANTS
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    api_key VARCHAR(500),
    config JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. USERS
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(320) UNIQUE NOT NULL,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. EXPENSE RECORDS
CREATE TABLE expense_records (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'MXN',
    description TEXT,
    category VARCHAR(100),
    merchant_name VARCHAR(255),
    merchant_category VARCHAR(100),
    date TIMESTAMP WITH TIME ZONE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    moneda VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio NUMERIC(12,6) DEFAULT 1.0,
    deducible_status VARCHAR(20) DEFAULT 'pendiente',
    deducible_percent NUMERIC(5,2) DEFAULT 100.0,
    iva_acreditable BOOLEAN DEFAULT TRUE,
    periodo VARCHAR(7),
    cfdi_uuid VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. BANK MOVEMENTS
CREATE TABLE bank_movements (
    id SERIAL PRIMARY KEY,
    amount DECIMAL(15,2) NOT NULL,
    description TEXT,
    date TIMESTAMP WITH TIME ZONE,
    account VARCHAR(100),
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    matched_expense_id INTEGER REFERENCES expense_records(id) ON DELETE SET NULL,
    moneda VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio NUMERIC(12,6) DEFAULT 1.0,
    bank_import_fingerprint VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. EXPENSE INVOICES
CREATE TABLE expense_invoices (
    id SERIAL PRIMARY KEY,
    expense_id INTEGER REFERENCES expense_records(id) ON DELETE CASCADE,
    filename VARCHAR(500),
    file_path VARCHAR(1000),
    content_type VARCHAR(100),
    parsed_data JSONB,
    uuid VARCHAR(64),
    rfc_emisor VARCHAR(13),
    nombre_emisor VARCHAR(255),
    subtotal DECIMAL(15,2),
    iva_amount DECIMAL(15,2),
    total DECIMAL(15,2),
    moneda VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio NUMERIC(12,6) DEFAULT 1.0,
    fecha_emision TIMESTAMP WITH TIME ZONE,
    metodo_pago VARCHAR(5),
    forma_pago VARCHAR(5),
    uso_cfdi VARCHAR(5),
    tipo_comprobante VARCHAR(1),
    relacionado_con_uuid VARCHAR(64),
    status VARCHAR(20) DEFAULT 'vigente',
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. TICKETS
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'open',
    priority VARCHAR(20) DEFAULT 'medium',
    assignee VARCHAR(255),
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. AUTOMATION JOBS
CREATE TABLE automation_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    config JSONB,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. AUTOMATION LOGS
CREATE TABLE automation_logs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES automation_jobs(id) ON DELETE CASCADE,
    level VARCHAR(20) DEFAULT 'info',
    message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. AUTOMATION SCREENSHOTS
CREATE TABLE automation_screenshots (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES automation_jobs(id) ON DELETE CASCADE,
    filename VARCHAR(500),
    file_path VARCHAR(1000),
    step_name VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. GPT USAGE EVENTS
CREATE TABLE gpt_usage_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    reason TEXT NOT NULL,
    tokens_estimated INTEGER NOT NULL,
    cost_estimated_usd DECIMAL(10,4) NOT NULL,
    confidence_before DECIMAL(5,4) NOT NULL,
    confidence_after DECIMAL(5,4) NOT NULL,
    success BOOLEAN NOT NULL,
    merchant_type VARCHAR(100),
    ticket_id VARCHAR(50),
    error_message TEXT,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE
);

-- 11. SCHEMA VERSIONS
CREATE TABLE schema_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- PERFORMANCE INDEXES
CREATE INDEX idx_expense_tenant_status ON expense_records(tenant_id, status);
CREATE INDEX idx_expense_user_date ON expense_records(user_id, date DESC);
CREATE INDEX idx_expense_category ON expense_records(category);
CREATE INDEX idx_expense_amount ON expense_records(amount DESC);
CREATE INDEX idx_expense_created ON expense_records(created_at DESC);

CREATE INDEX idx_bank_tenant_date ON bank_movements(tenant_id, date DESC);
CREATE INDEX idx_bank_matched ON bank_movements(matched_expense_id);
CREATE INDEX idx_bank_amount ON bank_movements(amount);
CREATE UNIQUE INDEX idx_expense_cfdi_uuid_unique ON expense_records(cfdi_uuid);
CREATE INDEX idx_expense_periodo ON expense_records(periodo, tenant_id);
CREATE UNIQUE INDEX idx_bank_movements_fingerprint ON bank_movements(bank_import_fingerprint);
CREATE INDEX idx_bank_movements_fecha_monto ON bank_movements(date, amount);
CREATE UNIQUE INDEX idx_expense_invoices_uuid_unique ON expense_invoices(uuid);
CREATE INDEX idx_expense_invoices_rfc_total_fecha ON expense_invoices(rfc_emisor, total, fecha_emision);

CREATE INDEX idx_automation_tenant_status ON automation_jobs(tenant_id, status);
CREATE INDEX idx_automation_type ON automation_jobs(job_type);
CREATE INDEX idx_automation_created ON automation_jobs(created_at DESC);

CREATE INDEX idx_logs_job_timestamp ON automation_logs(job_id, timestamp DESC);
CREATE INDEX idx_logs_level ON automation_logs(level);

CREATE INDEX idx_tickets_tenant_status ON tickets(tenant_id, status);
CREATE INDEX idx_tickets_user ON tickets(user_id);
CREATE INDEX idx_tickets_priority ON tickets(priority);
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);

CREATE INDEX idx_invoices_expense ON expense_invoices(expense_id);
CREATE INDEX idx_invoices_tenant ON expense_invoices(tenant_id);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant ON users(tenant_id);

CREATE INDEX idx_gpt_tenant_timestamp ON gpt_usage_events(tenant_id, timestamp DESC);
CREATE INDEX idx_gpt_field_name ON gpt_usage_events(field_name);
CREATE INDEX idx_gpt_success ON gpt_usage_events(success);

-- 12. POLIZAS CONTABLES
CREATE TABLE polizas_contables (
    id SERIAL PRIMARY KEY,
    bank_movement_id INTEGER REFERENCES bank_movements(id) ON DELETE SET NULL,
    expense_record_id INTEGER REFERENCES expense_records(id) ON DELETE SET NULL,
    cfdi_uuid VARCHAR(64),
    tipo VARCHAR(20) NOT NULL,
    descripcion TEXT,
    monto_total DECIMAL(15,2) NOT NULL DEFAULT 0,
    iva_total DECIMAL(15,2) NOT NULL DEFAULT 0,
    estatus VARCHAR(20) NOT NULL DEFAULT 'draft',
    periodo VARCHAR(7),
    fecha TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1,
    replaces_poliza_id INTEGER REFERENCES polizas_contables(id) ON DELETE SET NULL,
    company_id INTEGER,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    ai_source VARCHAR(100),
    ai_confidence NUMERIC(5,2),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE polizas_detalle (
    id SERIAL PRIMARY KEY,
    poliza_id INTEGER REFERENCES polizas_contables(id) ON DELETE CASCADE,
    cuenta_contable VARCHAR(100) NOT NULL,
    descripcion TEXT,
    debe DECIMAL(15,2) NOT NULL DEFAULT 0,
    haber DECIMAL(15,2) NOT NULL DEFAULT 0,
    uuid_cfdi VARCHAR(64),
    rfc_tercero VARCHAR(13),
    forma_pago VARCHAR(5),
    metodo_pago VARCHAR(5),
    moneda VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio NUMERIC(12,6) DEFAULT 1.0,
    codigo_agrupador_sat VARCHAR(20),
    impuesto_tipo VARCHAR(10),
    impuesto_monto DECIMAL(15,2),
    orden INTEGER DEFAULT 0
);

CREATE INDEX idx_polizas_contables_periodo ON polizas_contables(periodo, tenant_id);
CREATE INDEX idx_polizas_contables_cfdi ON polizas_contables(cfdi_uuid);
CREATE INDEX idx_polizas_detalle_poliza ON polizas_detalle(poliza_id, orden);

-- 13. BANK MATCH LINKS
CREATE TABLE bank_match_links (
    id SERIAL PRIMARY KEY,
    bank_movement_id INTEGER NOT NULL REFERENCES bank_movements(id) ON DELETE CASCADE,
    expense_id INTEGER REFERENCES expense_records(id) ON DELETE SET NULL,
    cfdi_uuid VARCHAR(64) REFERENCES expense_invoices(uuid) ON DELETE SET NULL,
    monto_asignado DECIMAL(15,2) NOT NULL,
    score NUMERIC(5,2),
    source VARCHAR(10) CHECK (source IN ('regla','ia','manual')),
    explanation TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE (bank_movement_id, expense_id, cfdi_uuid)
);

CREATE INDEX idx_bank_match_links_movement ON bank_match_links(bank_movement_id);
CREATE INDEX idx_bank_match_links_cfdi ON bank_match_links(cfdi_uuid);

-- 14. CFDI PAYMENTS
CREATE TABLE cfdi_payments (
    id SERIAL PRIMARY KEY,
    uuid_pago VARCHAR(64) NOT NULL UNIQUE,
    fecha_pago TIMESTAMP WITH TIME ZONE NOT NULL,
    moneda VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio NUMERIC(12,6) DEFAULT 1.0,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE payment_applications (
    id SERIAL PRIMARY KEY,
    uuid_pago VARCHAR(64) NOT NULL REFERENCES cfdi_payments(uuid_pago) ON DELETE CASCADE,
    cfdi_uuid VARCHAR(64) NOT NULL REFERENCES expense_invoices(uuid) ON DELETE CASCADE,
    no_parcialidad INTEGER NOT NULL,
    monto_pagado DECIMAL(15,2) NOT NULL,
    saldo_insoluto DECIMAL(15,2) NOT NULL,
    moneda VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio NUMERIC(12,6) DEFAULT 1.0,
    fecha_pago TIMESTAMP WITH TIME ZONE NOT NULL,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (uuid_pago, cfdi_uuid, no_parcialidad)
);

CREATE INDEX idx_payment_applications_cfdi ON payment_applications(cfdi_uuid);

-- Compound indexes for complex queries
CREATE INDEX idx_expense_tenant_user_date ON expense_records(tenant_id, user_id, date DESC);
CREATE INDEX idx_bank_tenant_amount_date ON bank_movements(tenant_id, amount DESC, date DESC);

-- UPDATE triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expense_records_updated_at BEFORE UPDATE ON expense_records FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_bank_movements_updated_at BEFORE UPDATE ON bank_movements FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expense_invoices_updated_at BEFORE UPDATE ON expense_invoices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tickets_updated_at BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_automation_jobs_updated_at BEFORE UPDATE ON automation_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial schema version
INSERT INTO schema_versions (version, description)
VALUES ('2.0.0', 'PostgreSQL Migration - Production Schema');
