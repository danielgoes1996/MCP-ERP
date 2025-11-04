-- Migration 026: Add SAT catalog tables and expense SAT code columns
-- Date: 2025-10-05
-- Purpose: Support SAT catalog integration for accounting normalization

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS sat_account_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    parent_code TEXT,
    type TEXT DEFAULT 'agrupador',
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sat_account_catalog_code
    ON sat_account_catalog(code);

CREATE TABLE IF NOT EXISTS sat_product_service_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    unit_key TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sat_product_service_catalog_code
    ON sat_product_service_catalog(code);

ALTER TABLE expense_records ADD COLUMN sat_account_code TEXT;
ALTER TABLE expense_records ADD COLUMN sat_product_service_code TEXT;

CREATE INDEX IF NOT EXISTS idx_expense_records_sat_account_code
    ON expense_records(sat_account_code);

CREATE INDEX IF NOT EXISTS idx_expense_records_sat_product_code
    ON expense_records(sat_product_service_code);

COMMIT;
