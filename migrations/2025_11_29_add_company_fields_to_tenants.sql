-- Migration: Add company-related fields to tenants table
-- Date: 2025-11-29
-- Description: Add logo_url, fiscal_document_url, and rfc fields for company admin page

-- Add logo URL field
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS logo_url TEXT;

-- Add fiscal document URL field (Constancia de Situación Fiscal)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS fiscal_document_url TEXT;

-- Add RFC (Registro Federal de Contribuyentes)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS rfc VARCHAR(13);

-- Add comment
COMMENT ON COLUMN tenants.logo_url IS 'URL to company logo file';
COMMENT ON COLUMN tenants.fiscal_document_url IS 'URL to Constancia de Situación Fiscal document';
COMMENT ON COLUMN tenants.rfc IS 'Registro Federal de Contribuyentes (RFC)';
