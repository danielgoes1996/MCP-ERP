-- Migration: SAT Auto Sync Configuration
-- Date: 2025-11-24
-- Description: Agrega tabla de configuración para sincronización automática con SAT

-- Tabla de configuración por compañía
CREATE TABLE IF NOT EXISTS sat_sync_config (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    tenant_id VARCHAR(255),

    -- Configuración de sync
    enabled BOOLEAN DEFAULT false,
    frequency VARCHAR(20) DEFAULT 'weekly',  -- 'daily', 'weekly', 'biweekly', 'monthly'
    day_of_week INTEGER,  -- 0=Lunes, 1=Martes, etc (si weekly)
    time VARCHAR(5) DEFAULT '02:00',  -- Hora del día
    lookback_days INTEGER DEFAULT 10,  -- Ventana de descarga (overlap para capturas tardías)

    -- Opciones
    auto_classify BOOLEAN DEFAULT true,  -- Clasificar automáticamente con IA
    notify_email BOOLEAN DEFAULT true,  -- Enviar email cuando hay nuevas
    notify_threshold INTEGER DEFAULT 5,  -- Mínimo de facturas para notificar

    -- Estado
    last_sync_at TIMESTAMP,  -- Última sincronización
    last_sync_status VARCHAR(50),  -- 'success', 'error', 'pending'
    last_sync_count INTEGER DEFAULT 0,  -- Facturas descargadas en última sync
    last_sync_error TEXT,  -- Error si hubo

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,

    CONSTRAINT unique_company_config UNIQUE (company_id)
);

-- Índices
CREATE INDEX idx_sat_sync_company ON sat_sync_config(company_id);
CREATE INDEX idx_sat_sync_enabled ON sat_sync_config(enabled);
CREATE INDEX idx_sat_sync_tenant ON sat_sync_config(tenant_id);

-- Agregar columna 'source' a invoices si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='invoices' AND column_name='source'
    ) THEN
        ALTER TABLE invoices ADD COLUMN source VARCHAR(50) DEFAULT 'manual';
        CREATE INDEX idx_invoices_source ON invoices(source);
    END IF;
END $$;

-- Valores por defecto para source
UPDATE invoices SET source = 'manual' WHERE source IS NULL;

COMMENT ON TABLE sat_sync_config IS 'Configuración de sincronización automática con SAT por compañía';
COMMENT ON COLUMN sat_sync_config.lookback_days IS 'Días hacia atrás para descargar (overlap para facturas timbradas tarde)';
COMMENT ON COLUMN sat_sync_config.notify_threshold IS 'Notificar solo si hay al menos N facturas nuevas';
