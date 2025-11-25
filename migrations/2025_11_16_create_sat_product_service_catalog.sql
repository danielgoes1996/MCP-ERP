-- Migration: Create SAT Product/Service Catalog Table
-- Date: 2025-11-16
-- Purpose: Store official SAT c_ClaveProdServ catalog for full 8-digit lookup
--          Replaces hardcoded 2-digit SAT mapping in Phase 2

-- Drop table if exists (for clean reinstall)
DROP TABLE IF EXISTS sat_product_service_catalog CASCADE;

-- Create main catalog table
CREATE TABLE sat_product_service_catalog (
    code VARCHAR(8) PRIMARY KEY,           -- Full 8-digit SAT code (e.g., '15101514')
    name VARCHAR(255) NOT NULL,            -- Official SAT name
    description TEXT,                      -- Detailed description
    family_hint VARCHAR(3),                -- First 3 digits for family grouping (e.g., '151')
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for fast lookup
CREATE INDEX idx_sat_catalog_family ON sat_product_service_catalog(family_hint);
CREATE INDEX idx_sat_catalog_name ON sat_product_service_catalog USING gin(to_tsvector('spanish', name));

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_sat_catalog_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_sat_catalog_timestamp
    BEFORE UPDATE ON sat_product_service_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_sat_catalog_timestamp();

-- Add comment for documentation
COMMENT ON TABLE sat_product_service_catalog IS 'Official SAT Product/Service Catalog (c_ClaveProdServ) for invoice classification';
COMMENT ON COLUMN sat_product_service_catalog.code IS 'Full 8-digit SAT product/service code';
COMMENT ON COLUMN sat_product_service_catalog.name IS 'Official SAT description/name';
COMMENT ON COLUMN sat_product_service_catalog.family_hint IS 'First 3 digits for family grouping (e.g., 151=combustibles)';
