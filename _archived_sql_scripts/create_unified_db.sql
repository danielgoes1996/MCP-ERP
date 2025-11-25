-- UNIFIED MCP SYSTEM DATABASE
-- Consolida todas las DBs fragmentadas en una sola

-- 1. USUARIOS Y TENANTS
CREATE TABLE tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT,
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    tenant_id INTEGER,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 2. GASTOS Y FINANZAS
CREATE TABLE expense_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'MXN',
    description TEXT,
    category TEXT,
    merchant_name TEXT,
    merchant_category TEXT,
    date TIMESTAMP,
    user_id INTEGER,
    tenant_id INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Fiscal pipeline v1
    tax_source TEXT,
    explanation_short TEXT,
    explanation_detail TEXT,
    catalog_version TEXT DEFAULT 'v1',
    classification_source TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE bank_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    description TEXT,
    date TIMESTAMP,
    account TEXT,
    tenant_id INTEGER,
    matched_expense_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (matched_expense_id) REFERENCES expense_records(id)
);

-- 3. FACTURAS
CREATE TABLE expense_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER,
    filename TEXT,
    file_path TEXT,
    content_type TEXT,
    parsed_data TEXT,
    tenant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (expense_id) REFERENCES expense_records(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 4. TICKETS DE SOPORTE
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    assignee TEXT,
    tenant_id INTEGER,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 5. AUTOMATIZACIÓN RPA
CREATE TABLE automation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    merchant_id INTEGER,
    user_id INTEGER,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    automation_type TEXT NOT NULL DEFAULT 'selenium',
    priority INTEGER DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    config TEXT,
    result TEXT,
    error_details TEXT,
    current_step TEXT,
    progress_percentage INTEGER DEFAULT 0,
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    estimated_completion TEXT,
    session_id TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',
    selenium_session_id TEXT,
    captcha_attempts INTEGER DEFAULT 0,
    ocr_confidence REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE automation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    category TEXT,
    message TEXT NOT NULL,
    url TEXT,
    element_selector TEXT,
    screenshot_id INTEGER,
    execution_time_ms INTEGER,
    data TEXT,
    user_agent TEXT,
    ip_address TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    company_id TEXT NOT NULL DEFAULT 'default',
    FOREIGN KEY (job_id) REFERENCES automation_jobs(id)
);

CREATE TABLE automation_screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    screenshot_type TEXT NOT NULL DEFAULT 'step',
    file_path TEXT NOT NULL,
    file_size INTEGER,
    url TEXT,
    window_title TEXT,
    viewport_size TEXT,
    page_load_time_ms INTEGER,
    has_captcha INTEGER DEFAULT 0,
    captcha_type TEXT,
    detected_elements TEXT,
    ocr_text TEXT,
    manual_annotations TEXT,
    is_sensitive INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    company_id TEXT NOT NULL DEFAULT 'default',
    FOREIGN KEY (job_id) REFERENCES automation_jobs(id)
);

-- 6. ANALYTICS DE AI/GPT
CREATE TABLE gpt_usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    field_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    tokens_estimated INTEGER NOT NULL,
    cost_estimated_usd REAL NOT NULL,
    confidence_before REAL NOT NULL,
    confidence_after REAL NOT NULL,
    success INTEGER NOT NULL,
    merchant_type TEXT,
    ticket_id TEXT,
    error_message TEXT,
    tenant_id INTEGER,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 7. TABLAS DE CONTROL
CREATE TABLE schema_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- 8. ÍNDICES PARA PERFORMANCE
CREATE INDEX idx_expense_records_tenant ON expense_records(tenant_id);
CREATE INDEX idx_expense_records_user ON expense_records(user_id);
CREATE INDEX idx_expense_records_date ON expense_records(date);
CREATE INDEX idx_bank_movements_tenant ON bank_movements(tenant_id);
CREATE INDEX idx_tickets_tenant ON tickets(tenant_id);
CREATE INDEX idx_automation_jobs_company ON automation_jobs(company_id);
CREATE INDEX idx_automation_jobs_estado ON automation_jobs(estado);
CREATE INDEX idx_automation_jobs_created ON automation_jobs(created_at);
CREATE INDEX idx_automation_logs_job ON automation_logs(job_id);
CREATE INDEX idx_automation_logs_level ON automation_logs(level);
CREATE INDEX idx_automation_logs_category ON automation_logs(category);
CREATE INDEX idx_automation_screenshots_job ON automation_screenshots(job_id);
CREATE INDEX idx_automation_screenshots_type ON automation_screenshots(screenshot_type);
CREATE INDEX idx_gpt_usage_tenant ON gpt_usage_events(tenant_id);

-- INSERTAR VERSIÓN INICIAL
INSERT INTO schema_versions (version, description)
VALUES ('1.0.0', 'Unified MCP System Database - Initial Schema');

-- Conciliation and CFDI governance enhancements (2025-10-20)
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN';
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS deducible_status TEXT DEFAULT 'pendiente';
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS deducible_percent REAL DEFAULT 100.0;
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS iva_acreditable BOOLEAN DEFAULT 1;
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS periodo TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_records_cfdi_uuid_unique ON expense_records(cfdi_uuid);
CREATE INDEX IF NOT EXISTS idx_expense_records_periodo ON expense_records(periodo, tenant_id);

ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS uuid TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS rfc_emisor TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS nombre_emisor TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS subtotal REAL;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS iva_amount REAL;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS total REAL;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN';
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS fecha_emision TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS metodo_pago TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS forma_pago TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS uso_cfdi TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS tipo_comprobante TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS relacionado_con_uuid TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'vigente';
CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_invoices_uuid_unique ON expense_invoices(uuid);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_rfc_total_fecha ON expense_invoices(rfc_emisor, total, fecha_emision);

ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN';
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS bank_import_fingerprint TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_bank_movements_fingerprint ON bank_movements(bank_import_fingerprint);
CREATE INDEX IF NOT EXISTS idx_bank_movements_fecha_monto ON bank_movements(date, amount);

ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS estatus TEXT DEFAULT 'draft';
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS replaces_poliza_id INTEGER;
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS fecha TEXT DEFAULT (datetime('now'));
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS periodo TEXT;
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS tipo TEXT;

ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS uuid_cfdi TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS rfc_tercero TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS forma_pago TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS metodo_pago TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN';
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS codigo_agrupador_sat TEXT;
CREATE INDEX IF NOT EXISTS idx_polizas_detalle_order ON polizas_detalle(poliza_id, orden);

CREATE TABLE IF NOT EXISTS bank_match_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_movement_id INTEGER NOT NULL REFERENCES bank_movements(id) ON DELETE CASCADE,
    expense_id INTEGER REFERENCES expense_records(id),
    cfdi_uuid TEXT REFERENCES expense_invoices(uuid),
    monto_asignado REAL NOT NULL,
    score REAL,
    source TEXT,
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    tenant_id INTEGER,
    UNIQUE (bank_movement_id, expense_id, cfdi_uuid)
);
CREATE INDEX IF NOT EXISTS idx_bank_match_links_movement ON bank_match_links(bank_movement_id);
CREATE INDEX IF NOT EXISTS idx_bank_match_links_cfdi ON bank_match_links(cfdi_uuid);

CREATE TABLE IF NOT EXISTS cfdi_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid_pago TEXT NOT NULL UNIQUE,
    fecha_pago TIMESTAMP NOT NULL,
    moneda TEXT DEFAULT 'MXN',
    tipo_cambio REAL DEFAULT 1.0,
    tenant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payment_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid_pago TEXT NOT NULL REFERENCES cfdi_payments(uuid_pago) ON DELETE CASCADE,
    cfdi_uuid TEXT NOT NULL REFERENCES expense_invoices(uuid),
    no_parcialidad INTEGER NOT NULL,
    monto_pagado REAL NOT NULL,
    saldo_insoluto REAL NOT NULL,
    moneda TEXT DEFAULT 'MXN',
    tipo_cambio REAL DEFAULT 1.0,
    fecha_pago TIMESTAMP NOT NULL,
    tenant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (uuid_pago, cfdi_uuid, no_parcialidad)
);
CREATE INDEX IF NOT EXISTS idx_payment_applications_cfdi ON payment_applications(cfdi_uuid);
