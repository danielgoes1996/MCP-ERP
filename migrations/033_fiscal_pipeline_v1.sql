-- Fiscal pipeline v1
BEGIN TRANSACTION;

-- Nuevos campos de trazabilidad fiscal en expense_records
ALTER TABLE expense_records ADD COLUMN tax_source TEXT;
ALTER TABLE expense_records ADD COLUMN explanation_short TEXT;
ALTER TABLE expense_records ADD COLUMN explanation_detail TEXT;
ALTER TABLE expense_records ADD COLUMN catalog_version TEXT DEFAULT 'v1';
ALTER TABLE expense_records ADD COLUMN classification_source TEXT;

-- Tabla de reglas persistentes por proveedor
CREATE TABLE IF NOT EXISTS provider_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER REFERENCES tenants(id),
    provider_name_normalized TEXT,
    category_slug TEXT,
    sat_account_code TEXT,
    sat_product_service_code TEXT,
    default_iva_rate REAL DEFAULT 0,
    iva_tipo TEXT DEFAULT 'tasa_0',
    confidence REAL DEFAULT 0.9,
    last_confirmed_by INTEGER,
    last_confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
