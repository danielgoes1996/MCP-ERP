-- SAT Sync History Table
-- =======================
-- Tabla para rastrear el historial completo de sincronizaciones del SAT
-- (a diferencia de sat_sync_config que solo guarda el último sync)

CREATE TABLE IF NOT EXISTS sat_sync_history (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    tenant_id VARCHAR(255),

    -- Información del sync
    sync_started_at TIMESTAMP NOT NULL,
    sync_completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Configuración usada
    frequency VARCHAR(20),
    lookback_days INTEGER,

    -- Resultados
    status VARCHAR(50) NOT NULL DEFAULT 'running',  -- running, success, error
    invoices_downloaded INTEGER DEFAULT 0,
    invoices_classified INTEGER DEFAULT 0,
    invoices_failed INTEGER DEFAULT 0,

    -- Detalles técnicos
    sat_request_id TEXT,
    sat_request_uuid TEXT,
    packages_downloaded INTEGER DEFAULT 0,

    -- Errores
    error_message TEXT,
    error_details JSONB,

    -- Notificaciones
    email_sent BOOLEAN DEFAULT false,
    email_sent_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key
    CONSTRAINT fk_sat_sync_history_company
        FOREIGN KEY (company_id)
        REFERENCES sat_sync_config(company_id)
        ON DELETE CASCADE
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_sat_sync_history_company
    ON sat_sync_history(company_id);

CREATE INDEX IF NOT EXISTS idx_sat_sync_history_status
    ON sat_sync_history(status);

CREATE INDEX IF NOT EXISTS idx_sat_sync_history_started
    ON sat_sync_history(sync_started_at DESC);

CREATE INDEX IF NOT EXISTS idx_sat_sync_history_company_started
    ON sat_sync_history(company_id, sync_started_at DESC);

-- Comentarios
COMMENT ON TABLE sat_sync_history IS 'Historial completo de sincronizaciones automáticas con el SAT';
COMMENT ON COLUMN sat_sync_history.status IS 'Estado: running, success, error';
COMMENT ON COLUMN sat_sync_history.duration_seconds IS 'Duración total del proceso de sincronización en segundos';
COMMENT ON COLUMN sat_sync_history.sat_request_id IS 'ID del request en la tabla sat_download_requests';
COMMENT ON COLUMN sat_sync_history.error_details IS 'Detalles JSON del error para debugging';
