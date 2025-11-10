-- ========================================
-- MIGRATION 004: SAT WEB SERVICE DESCARGA MASIVA
-- ========================================
-- Purpose: Tables for SAT automatic CFDI download integration
-- Author: ContaFlow Backend Team
-- Date: 2025-01-08
-- Phase: 3.1 - SAT Integration

-- ========================================
-- TABLE 1: sat_efirma_credentials
-- ========================================
-- Stores e.firma certificate metadata (NOT the actual certificates)
-- Actual .cer and .key files should be in HashiCorp Vault or AWS Secrets Manager

CREATE TABLE IF NOT EXISTS sat_efirma_credentials (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    rfc VARCHAR(13) NOT NULL,

    -- Vault/Secrets Manager paths (NOT actual files)
    vault_cer_path TEXT NOT NULL,  -- e.g., "sat/pol210218264/certificate"
    vault_key_path TEXT NOT NULL,  -- e.g., "sat/pol210218264/key"
    vault_password_path TEXT NOT NULL,  -- e.g., "sat/pol210218264/password"

    -- Certificate metadata
    certificate_serial_number VARCHAR(40),
    certificate_valid_from TIMESTAMP,
    certificate_valid_until TIMESTAMP,

    -- Status
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),

    -- Constraints
    CONSTRAINT unique_company_rfc UNIQUE(company_id, rfc),
    CONSTRAINT valid_rfc_length CHECK (length(rfc) IN (12, 13))
);

CREATE INDEX idx_sat_efirma_company ON sat_efirma_credentials(company_id);
CREATE INDEX idx_sat_efirma_active ON sat_efirma_credentials(is_active);

-- ========================================
-- TABLE 2: sat_requests
-- ========================================
-- Tracks SAT download requests (solicitudes)

CREATE TABLE IF NOT EXISTS sat_requests (
    request_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    rfc VARCHAR(13) NOT NULL,

    -- Request parameters
    tipo_solicitud VARCHAR(20) NOT NULL,  -- 'CFDI' or 'Metadata'
    fecha_inicial DATE NOT NULL,
    fecha_final DATE NOT NULL,
    rfc_emisor VARCHAR(13),  -- Filter by issuer (optional)
    rfc_receptor VARCHAR(13),  -- Filter by receiver (optional)
    tipo_comprobante VARCHAR(1),  -- 'I', 'P', 'E', etc. (optional)

    -- SAT response
    request_uuid UUID,  -- SAT's request ID
    request_status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed, expired
    status_code VARCHAR(10),  -- SAT status codes: 1=accepted, 2=in_progress, 3=completed, 5=error
    status_message TEXT,

    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    last_error TEXT,

    -- NOM-151 Evidence
    request_evidence JSONB,  -- Complete request/response for legal compliance

    -- Timestamps
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP,  -- SAT requests expire after 7 days

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);

CREATE INDEX idx_sat_requests_company ON sat_requests(company_id);
CREATE INDEX idx_sat_requests_status ON sat_requests(request_status);
CREATE INDEX idx_sat_requests_uuid ON sat_requests(request_uuid);
CREATE INDEX idx_sat_requests_dates ON sat_requests(fecha_inicial, fecha_final);

-- ========================================
-- TABLE 3: sat_packages
-- ========================================
-- Downloaded ZIP packages from SAT

CREATE TABLE IF NOT EXISTS sat_packages (
    package_id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES sat_requests(request_id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- Package metadata
    package_uuid UUID NOT NULL,  -- SAT package identifier
    package_number INTEGER,  -- Some requests generate multiple packages

    -- Download info
    download_url TEXT,  -- Temporary URL from SAT
    zip_file_path TEXT,  -- Local storage path
    zip_size_bytes BIGINT,
    zip_hash_sha256 VARCHAR(64),

    -- Extraction info
    xml_count INTEGER DEFAULT 0,  -- Number of XMLs in package
    extracted_at TIMESTAMP,

    -- Processing status
    download_status VARCHAR(20) DEFAULT 'pending',  -- pending, downloading, downloaded, extracted, processed, failed
    processing_status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed

    -- NOM-151 Evidence
    download_evidence JSONB,  -- Download metadata for legal compliance

    -- Timestamps
    available_at TIMESTAMP,  -- When SAT made package available
    downloaded_at TIMESTAMP,
    processed_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sat_packages_request ON sat_packages(request_id);
CREATE INDEX idx_sat_packages_company ON sat_packages(company_id);
CREATE INDEX idx_sat_packages_uuid ON sat_packages(package_uuid);
CREATE INDEX idx_sat_packages_status ON sat_packages(download_status, processing_status);

-- ========================================
-- TABLE 4: sat_invoice_mapping
-- ========================================
-- Links SAT downloads to processed invoices

CREATE TABLE IF NOT EXISTS sat_invoice_mapping (
    id SERIAL PRIMARY KEY,
    package_id INTEGER NOT NULL REFERENCES sat_packages(package_id) ON DELETE CASCADE,
    invoice_id INTEGER NOT NULL REFERENCES expense_invoices(id) ON DELETE CASCADE,

    -- Metadata
    uuid UUID NOT NULL,
    filename VARCHAR(255),
    was_duplicate BOOLEAN DEFAULT false,  -- True if already existed in DB

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_package_invoice UNIQUE(package_id, invoice_id)
);

CREATE INDEX idx_sat_mapping_package ON sat_invoice_mapping(package_id);
CREATE INDEX idx_sat_mapping_invoice ON sat_invoice_mapping(invoice_id);
CREATE INDEX idx_sat_mapping_uuid ON sat_invoice_mapping(uuid);

-- ========================================
-- TABLE 5: sat_download_logs
-- ========================================
-- Audit trail for all SAT operations

CREATE TABLE IF NOT EXISTS sat_download_logs (
    log_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    request_id INTEGER REFERENCES sat_requests(request_id),

    -- Log details
    operation VARCHAR(50) NOT NULL,  -- 'solicitar', 'verificar', 'descargar', 'procesar'
    status VARCHAR(20) NOT NULL,  -- 'success', 'error', 'warning'
    message TEXT,

    -- Error tracking
    error_code VARCHAR(50),
    error_details JSONB,

    -- Context
    user_id INTEGER REFERENCES users(id),
    ip_address INET,
    user_agent TEXT,

    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sat_logs_company ON sat_download_logs(company_id);
CREATE INDEX idx_sat_logs_request ON sat_download_logs(request_id);
CREATE INDEX idx_sat_logs_operation ON sat_download_logs(operation);
CREATE INDEX idx_sat_logs_created ON sat_download_logs(created_at);

-- ========================================
-- TRIGGERS: Auto-update updated_at
-- ========================================

CREATE OR REPLACE FUNCTION update_sat_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sat_efirma_updated
    BEFORE UPDATE ON sat_efirma_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_sat_timestamp();

CREATE TRIGGER trigger_sat_requests_updated
    BEFORE UPDATE ON sat_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_sat_timestamp();

CREATE TRIGGER trigger_sat_packages_updated
    BEFORE UPDATE ON sat_packages
    FOR EACH ROW
    EXECUTE FUNCTION update_sat_timestamp();

-- ========================================
-- INITIAL DATA: Add POL210218264 placeholder
-- ========================================
-- This is just metadata - actual certificates must be in Vault

INSERT INTO sat_efirma_credentials (
    company_id,
    rfc,
    vault_cer_path,
    vault_key_path,
    vault_password_path,
    is_active,
    created_by
) VALUES (
    2,  -- POL210218264 company
    'POL210218264',
    'sat/pol210218264/certificate',
    'sat/pol210218264/private_key',
    'sat/pol210218264/password',
    false,  -- Set to false until actual certificates are uploaded to Vault
    1  -- Admin user
) ON CONFLICT (company_id, rfc) DO NOTHING;

-- ========================================
-- COMMENTS
-- ========================================

COMMENT ON TABLE sat_efirma_credentials IS 'e.firma certificate metadata for SAT authentication (actual certs in Vault)';
COMMENT ON TABLE sat_requests IS 'SAT CFDI download requests (solicitudes)';
COMMENT ON TABLE sat_packages IS 'Downloaded ZIP packages containing CFDIs';
COMMENT ON TABLE sat_invoice_mapping IS 'Links SAT packages to processed invoices';
COMMENT ON TABLE sat_download_logs IS 'Audit trail for SAT operations';

COMMENT ON COLUMN sat_efirma_credentials.vault_cer_path IS 'Path to .cer file in Vault (NOT filesystem)';
COMMENT ON COLUMN sat_efirma_credentials.vault_key_path IS 'Path to .key file in Vault (NOT filesystem)';
COMMENT ON COLUMN sat_requests.request_evidence IS 'NOM-151: Complete request/response for legal compliance';
COMMENT ON COLUMN sat_packages.download_evidence IS 'NOM-151: Download metadata for legal compliance';

-- ========================================
-- VERIFICATION QUERIES
-- ========================================

-- Check table creation
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name LIKE 'sat_%'
ORDER BY table_name;

-- Check indexes
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename LIKE 'sat_%'
ORDER BY tablename, indexname;
