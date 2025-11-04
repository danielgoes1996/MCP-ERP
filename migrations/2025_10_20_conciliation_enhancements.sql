-- Migration: conciliation enhancements, CFDI governance, and SAT alignment
-- Applies to SQLite (unified DB). For PostgreSQL equivalent, see postgresql_migration updates.

BEGIN;

-- === expense_records adjustments ===
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN';
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS deducible_status TEXT DEFAULT 'pendiente';
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS deducible_percent REAL DEFAULT 100.0;
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS iva_acreditable BOOLEAN DEFAULT TRUE;
ALTER TABLE expense_records ADD COLUMN IF NOT EXISTS periodo TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_records_cfdi_uuid_unique ON expense_records(cfdi_uuid);
CREATE INDEX IF NOT EXISTS idx_expense_records_periodo ON expense_records(periodo, tenant_id);

-- Backfill defaults where NULL
UPDATE expense_records SET moneda = COALESCE(moneda, currency);
UPDATE expense_records SET tipo_cambio = COALESCE(tipo_cambio, 1.0);
UPDATE expense_records SET deducible_status = COALESCE(deducible_status, 'pendiente');
UPDATE expense_records SET deducible_percent = COALESCE(deducible_percent, 100.0);
UPDATE expense_records SET iva_acreditable = COALESCE(iva_acreditable, 1);

-- === expense_invoices adjustments ===
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS metodo_pago TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS forma_pago TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS uso_cfdi TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS tipo_comprobante TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS relacionado_con_uuid TEXT;
ALTER TABLE expense_invoices ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'vigente';

CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_invoices_uuid_unique ON expense_invoices(uuid);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_rfc_total_fecha
    ON expense_invoices(rfc_emisor, total, fecha_emision);

UPDATE expense_invoices SET status = COALESCE(status, 'vigente');
UPDATE expense_invoices SET tipo_cambio = COALESCE(tipo_cambio, 1.0);

-- === bank_movements adjustments ===
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN';
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS bank_import_fingerprint TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_bank_movements_fingerprint ON bank_movements(bank_import_fingerprint);
CREATE INDEX IF NOT EXISTS idx_bank_movements_fecha_monto ON bank_movements(date, amount);

UPDATE bank_movements SET moneda = COALESCE(moneda, 'MXN');
UPDATE bank_movements SET tipo_cambio = COALESCE(tipo_cambio, 1.0);

-- === polizas_contables adjustments ===
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS estatus TEXT DEFAULT 'draft';
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS replaces_poliza_id INTEGER;
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS periodo TEXT;
ALTER TABLE polizas_contables ADD COLUMN IF NOT EXISTS tipo TEXT;

-- === polizas_detalle adjustments ===
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS uuid_cfdi TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS rfc_tercero TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS forma_pago TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS metodo_pago TEXT;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'MXN';
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS tipo_cambio REAL DEFAULT 1.0;
ALTER TABLE polizas_detalle ADD COLUMN IF NOT EXISTS codigo_agrupador_sat TEXT;

CREATE INDEX IF NOT EXISTS idx_polizas_detalle_order ON polizas_detalle(poliza_id, orden);

UPDATE polizas_detalle SET moneda = COALESCE(moneda, 'MXN');
UPDATE polizas_detalle SET tipo_cambio = COALESCE(tipo_cambio, 1.0);

-- === new tables ===

CREATE TABLE IF NOT EXISTS bank_match_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_movement_id INTEGER NOT NULL REFERENCES bank_movements(id) ON DELETE CASCADE,
    expense_id INTEGER REFERENCES expense_records(id),
    cfdi_uuid TEXT REFERENCES expense_invoices(uuid),
    monto_asignado REAL NOT NULL,
    score REAL,
    source TEXT CHECK (source IN ('regla','ia','manual')),
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

COMMIT;
