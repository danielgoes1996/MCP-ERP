-- ============================================
-- PostgreSQL Schema Initialization
-- Migrated from SQLite migrations
-- ============================================

-- Core tables for tenant/company system
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    settings TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    rfc VARCHAR(13),
    status VARCHAR(50) DEFAULT 'active',
    settings TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Payment accounts
CREATE TABLE IF NOT EXISTS payment_accounts (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    company_id INT,
    account_name VARCHAR(255) NOT NULL,
    account_number VARCHAR(100),
    bank_name VARCHAR(255),
    account_type VARCHAR(50),
    currency VARCHAR(10) DEFAULT 'MXN',
    balance DOUBLE PRECISION DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Expense invoices table with CFDI fields (Migration 035)
CREATE TABLE IF NOT EXISTS expense_invoices (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    company_id INT,

    -- Core invoice data
    filename VARCHAR(500),
    file_path VARCHAR(1000),
    file_hash VARCHAR(64),
    file_size INT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- CFDI fiscal fields
    uuid VARCHAR(36) UNIQUE,
    rfc_emisor VARCHAR(13),
    nombre_emisor VARCHAR(500),
    rfc_receptor VARCHAR(13),
    nombre_receptor VARCHAR(500),
    fecha_emision TIMESTAMP,
    fecha_timbrado TIMESTAMP,
    cfdi_status VARCHAR(20) DEFAULT 'vigente',
    version_cfdi VARCHAR(10) DEFAULT '4.0',

    -- Financial amounts
    subtotal DOUBLE PRECISION,
    iva_amount DOUBLE PRECISION,
    total DOUBLE PRECISION,
    isr_retenido DOUBLE PRECISION DEFAULT 0,
    iva_retenido DOUBLE PRECISION DEFAULT 0,
    ieps_amount DOUBLE PRECISION DEFAULT 0,

    -- Additional fields
    currency VARCHAR(10) DEFAULT 'MXN',
    tipo_comprobante VARCHAR(10),
    forma_pago VARCHAR(50),
    metodo_pago VARCHAR(50),
    uso_cfdi VARCHAR(10),
    lugar_expedicion VARCHAR(10),
    regimen_fiscal VARCHAR(10),

    -- Tax period
    mes_fiscal VARCHAR(7),
    ejercicio_fiscal INT,

    -- Raw XML storage
    raw_xml TEXT,

    -- Linking
    linked_expense_id INT,
    match_confidence DOUBLE PRECISION,
    match_method VARCHAR(100),
    match_date TIMESTAMP,

    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by INT,
    reviewed_at TIMESTAMP,

    -- Metadata
    notes TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_expense_invoices_uuid ON expense_invoices(uuid);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_tenant ON expense_invoices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_company ON expense_invoices(company_id);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_rfc_emisor ON expense_invoices(rfc_emisor);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_fecha_emision ON expense_invoices(fecha_emision);

-- Expenses table
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    company_id INT,
    amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) DEFAULT 'MXN',
    description TEXT,
    expense_date DATE,
    category VARCHAR(100),
    payment_method VARCHAR(50),
    payment_account_id INT,

    -- Provider info
    provider_name VARCHAR(500),
    provider_rfc VARCHAR(13),

    -- Invoice status
    invoice_required BOOLEAN DEFAULT TRUE,
    invoice_uploaded BOOLEAN DEFAULT FALSE,
    invoice_id INT,

    -- Tax
    is_tax_deductible BOOLEAN DEFAULT TRUE,
    iva_amount DOUBLE PRECISION DEFAULT 0,

    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    approved BOOLEAN DEFAULT FALSE,
    approved_by INT,
    approved_at TIMESTAMP,

    -- Metadata
    notes TEXT,
    tags TEXT,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (payment_account_id) REFERENCES payment_accounts(id),
    FOREIGN KEY (invoice_id) REFERENCES expense_invoices(id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_tenant ON expenses(tenant_id);
CREATE INDEX IF NOT EXISTS idx_expenses_company ON expenses(company_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_provider_rfc ON expenses(provider_rfc);

-- Invoice import logs
CREATE TABLE IF NOT EXISTS invoice_import_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    company_id INT,
    batch_id VARCHAR(50),
    filename VARCHAR(500),
    file_hash VARCHAR(64),
    file_size INT,
    uuid VARCHAR(36),
    status VARCHAR(50),
    error_message TEXT,
    invoice_id INT,
    processing_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (invoice_id) REFERENCES expense_invoices(id)
);

CREATE INDEX IF NOT EXISTS idx_invoice_import_logs_batch ON invoice_import_logs(batch_id);
CREATE INDEX IF NOT EXISTS idx_invoice_import_logs_hash ON invoice_import_logs(file_hash);
CREATE INDEX IF NOT EXISTS idx_invoice_import_logs_status ON invoice_import_logs(status);

-- Bulk invoice processing tables
CREATE TABLE IF NOT EXISTS bulk_invoice_batches (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) UNIQUE NOT NULL,
    company_id INT NOT NULL,
    total_invoices INT DEFAULT 0,
    processed_count INT DEFAULT 0,
    linked_count INT DEFAULT 0,
    no_matches_count INT DEFAULT 0,
    errors_count INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    auto_link_threshold DOUBLE PRECISION DEFAULT 0.8,
    auto_mark_invoiced BOOLEAN DEFAULT FALSE,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    processing_time_ms INT,
    batch_metadata TEXT,
    request_metadata TEXT,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS bulk_invoice_batch_items (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    filename VARCHAR(500),
    uuid VARCHAR(36),
    total_amount DOUBLE PRECISION,
    subtotal_amount DOUBLE PRECISION,
    iva_amount DOUBLE PRECISION,
    currency VARCHAR(10) DEFAULT 'MXN',
    issued_date TIMESTAMP,
    provider_name VARCHAR(500),
    provider_rfc VARCHAR(13),
    file_size INT,
    file_hash VARCHAR(64),
    item_status VARCHAR(50) DEFAULT 'pending',
    matched_expense_id INT,
    match_confidence DOUBLE PRECISION,
    match_method VARCHAR(100),
    error_message TEXT,
    processing_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES bulk_invoice_batches(batch_id),
    FOREIGN KEY (matched_expense_id) REFERENCES expenses(id)
);

-- Insert default tenant and company if not exists
INSERT INTO tenants (id, name, status)
VALUES (2, 'Default Tenant', 'active')
ON CONFLICT (id) DO NOTHING;

INSERT INTO companies (id, tenant_id, name, rfc, status)
VALUES (2, 2, 'Default Company', 'XAXX010101000', 'active')
ON CONFLICT (id) DO NOTHING;

-- Insert or update user daniel@contaflow.ai
-- Password: ContaFlow2025! (hashed with bcrypt)
INSERT INTO users (tenant_id, email, password_hash, name, role, status)
VALUES (
    2,
    'daniel@contaflow.ai',
    '$2b$12$YXGabxMUmz7pJcZGWz0YG.vKdqGxmQw0SZ4HqKJHAOd0TkNyZJ4Iq',
    'Daniel',
    'admin',
    'active'
)
ON CONFLICT (email) DO UPDATE
SET password_hash = '$2b$12$YXGabxMUmz7pJcZGWz0YG.vKdqGxmQw0SZ4HqKJHAOd0TkNyZJ4Iq',
    updated_at = CURRENT_TIMESTAMP;
