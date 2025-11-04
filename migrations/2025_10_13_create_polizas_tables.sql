-- Create tables for accounting entries linked to bank reconciliation

CREATE TABLE IF NOT EXISTS polizas_contables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_movement_id INTEGER REFERENCES bank_movements(id) ON DELETE SET NULL,
    expense_record_id INTEGER REFERENCES expense_records(id) ON DELETE SET NULL,
    cfdi_uuid TEXT,
    tipo TEXT NOT NULL,
    descripcion TEXT,
    monto_total REAL NOT NULL DEFAULT 0,
    iva_total REAL NOT NULL DEFAULT 0,
    estatus TEXT NOT NULL DEFAULT 'generada',
    periodo TEXT,
    company_id INTEGER,
    tenant_id INTEGER,
    ai_source TEXT,
    ai_confidence REAL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS polizas_detalle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poliza_id INTEGER NOT NULL REFERENCES polizas_contables(id) ON DELETE CASCADE,
    cuenta_contable TEXT NOT NULL,
    descripcion TEXT,
    debe REAL NOT NULL DEFAULT 0,
    haber REAL NOT NULL DEFAULT 0,
    impuesto_tipo TEXT,
    impuesto_monto REAL,
    orden INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_polizas_contables_movement ON polizas_contables(bank_movement_id);
CREATE INDEX IF NOT EXISTS idx_polizas_contables_cfdi ON polizas_contables(cfdi_uuid);
CREATE INDEX IF NOT EXISTS idx_polizas_detalle_poliza ON polizas_detalle(poliza_id);

ALTER TABLE bank_movements ADD COLUMN generated_poliza_id INTEGER REFERENCES polizas_contables(id);
ALTER TABLE bank_movements ADD COLUMN cfdi_uuid TEXT;
