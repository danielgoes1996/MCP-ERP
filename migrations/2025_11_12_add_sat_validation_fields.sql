-- Migration: Add SAT Validation Fields to Universal Invoice Sessions
-- Created: 2025-11-12
-- Purpose: Track real-time SAT verification status for CFDIs

BEGIN;

-- Add SAT validation fields to sat_invoices
ALTER TABLE sat_invoices
    ADD COLUMN sat_validation_status TEXT DEFAULT 'pending' CHECK (
        sat_validation_status IN (
            'pending',      -- Not yet verified
            'verifying',    -- Verification in progress
            'vigente',      -- SAT confirmed vigente
            'cancelado',    -- SAT confirmed cancelado
            'sustituido',   -- SAT confirmed sustituido
            'por_cancelar', -- SAT confirmed por_cancelar
            'no_encontrado',-- SAT says not found
            'error'         -- Error during verification
        )
    );

ALTER TABLE sat_invoices
    ADD COLUMN sat_codigo_estatus TEXT;

ALTER TABLE sat_invoices
    ADD COLUMN sat_es_cancelable BOOLEAN;

ALTER TABLE sat_invoices
    ADD COLUMN sat_estado TEXT;

ALTER TABLE sat_invoices
    ADD COLUMN sat_validacion_efos TEXT;

ALTER TABLE sat_invoices
    ADD COLUMN sat_verified_at TIMESTAMP;

ALTER TABLE sat_invoices
    ADD COLUMN sat_last_check_at TIMESTAMP;

ALTER TABLE sat_invoices
    ADD COLUMN sat_verification_error TEXT;

ALTER TABLE sat_invoices
    ADD COLUMN sat_verification_url TEXT;

-- Create index for SAT validation queries
CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_sat_status
    ON sat_invoices(sat_validation_status, sat_verified_at);

CREATE INDEX IF NOT EXISTS idx_universal_invoice_sessions_sat_pending
    ON sat_invoices(sat_validation_status)
    WHERE sat_validation_status = 'pending';

-- Create table for SAT verification history (audit trail)
CREATE TABLE IF NOT EXISTS sat_verification_history (
    id TEXT PRIMARY KEY DEFAULT ('svh_' || replace(gen_random_uuid()::text, '-', '')),
    session_id TEXT NOT NULL,
    company_id TEXT NOT NULL,

    -- CFDI identifiers
    uuid TEXT NOT NULL,
    rfc_emisor TEXT,
    rfc_receptor TEXT,
    total DECIMAL(15,2),

    -- Verification result
    status TEXT NOT NULL,
    codigo_estatus TEXT,
    es_cancelable BOOLEAN,
    estado TEXT,
    validacion_efos TEXT,

    -- Metadata
    verification_url TEXT,
    error_message TEXT,
    is_retry BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES sat_invoices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sat_verification_history_session
    ON sat_verification_history(session_id);

CREATE INDEX IF NOT EXISTS idx_sat_verification_history_uuid
    ON sat_verification_history(uuid);

CREATE INDEX IF NOT EXISTS idx_sat_verification_history_verified_at
    ON sat_verification_history(verified_at DESC);

COMMIT;
