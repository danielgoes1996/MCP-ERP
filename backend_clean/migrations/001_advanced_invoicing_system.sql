-- ===============================================================
-- SISTEMA AVANZADO DE FACTURACIÓN AUTOMÁTICA DE TICKETS
-- Arquitectura escalable para miles de tickets diarios
-- ===============================================================

-- Crear extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ===============================================================
-- 1. TABLAS PRINCIPALES
-- ===============================================================

-- Empresas/Compañías
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    rfc VARCHAR(13) UNIQUE NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    address JSONB,
    fiscal_regime VARCHAR(10),
    -- Configuración de facturación
    invoicing_config JSONB DEFAULT '{}',
    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- Merchants/Comercios
CREATE TABLE IF NOT EXISTS merchants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    rfc VARCHAR(13),
    -- Configuración de portal de facturación
    portal_url VARCHAR(500),
    portal_type VARCHAR(50), -- 'web_form', 'api', 'email', 'whatsapp'
    portal_config JSONB DEFAULT '{}',
    -- Patrones de identificación
    identification_patterns JSONB DEFAULT '[]',
    -- Configuración de campos requeridos
    required_fields JSONB DEFAULT '[]',
    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    total_processed INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true
);

-- Tickets subidos por usuarios
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),

    -- Datos del ticket original
    source_type VARCHAR(20) NOT NULL, -- 'voice', 'image', 'pdf', 'email', 'whatsapp'
    source_content JSONB NOT NULL, -- Contenido original (base64, texto, etc.)

    -- Metadatos de subida
    uploaded_by VARCHAR(255),
    upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Estado del procesamiento
    processing_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'processed', 'failed'

    -- Datos extraídos por OCR/IA
    extracted_data JSONB DEFAULT '{}',
    merchant_id UUID REFERENCES merchants(id),

    -- Datos fiscales extraídos
    merchant_rfc VARCHAR(13),
    folio VARCHAR(50),
    ticket_date DATE,
    subtotal DECIMAL(12,2),
    iva DECIMAL(12,2),
    total DECIMAL(12,2),
    currency VARCHAR(3) DEFAULT 'MXN',

    -- Estado de facturación
    invoice_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'invoiced', 'failed', 'manual_review'
    will_have_cfdi BOOLEAN DEFAULT true,

    -- Datos de la factura generada
    cfdi_data JSONB,
    xml_content TEXT,
    pdf_url VARCHAR(500),

    -- Conciliación bancaria
    bank_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'matched', 'manual'
    bank_movement_id UUID,

    -- Auditoría y logs
    processing_logs JSONB DEFAULT '[]',
    error_messages JSONB DEFAULT '[]',

    -- Índices y timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Jobs de facturación automática
CREATE TABLE IF NOT EXISTS invoice_automation_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    company_id UUID NOT NULL REFERENCES companies(id),
    merchant_id UUID REFERENCES merchants(id),

    -- Configuración del job
    job_type VARCHAR(20) NOT NULL, -- 'auto_invoice', 'retry', 'manual_review'
    priority INTEGER DEFAULT 5, -- 1-10, mayor número = mayor prioridad

    -- Estado y programación
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    scheduled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Configuración de ejecución
    execution_config JSONB DEFAULT '{}',
    max_retries INTEGER DEFAULT 3,
    retry_count INTEGER DEFAULT 0,

    -- Resultados
    execution_result JSONB,
    error_details JSONB,

    -- Plan de ejecución IA
    ai_plan JSONB, -- Plan generado por LLM
    execution_steps JSONB DEFAULT '[]', -- Pasos ejecutados

    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===============================================================
-- 2. TABLAS DE AUTOMATIZACIÓN RPA
-- ===============================================================

-- Plantillas de automatización para diferentes portales
CREATE TABLE IF NOT EXISTS automation_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id UUID REFERENCES merchants(id),

    -- Configuración de la plantilla
    name VARCHAR(255) NOT NULL,
    portal_url VARCHAR(500) NOT NULL,
    template_type VARCHAR(50), -- 'web_form', 'spa', 'legacy'

    -- Selectores y configuración
    selectors JSONB NOT NULL, -- Selectores CSS/XPath para campos
    automation_steps JSONB NOT NULL, -- Pasos de automatización
    validation_rules JSONB DEFAULT '{}',

    -- Configuración de browser
    browser_config JSONB DEFAULT '{}',

    -- Estadísticas de éxito
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    total_executions INTEGER DEFAULT 0,
    last_successful_execution TIMESTAMP WITH TIME ZONE,

    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- Ejecuciones de automatización
CREATE TABLE IF NOT EXISTS automation_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES invoice_automation_jobs(id),
    template_id UUID REFERENCES automation_templates(id),

    -- Configuración de ejecución
    browser_session_id VARCHAR(100),
    execution_mode VARCHAR(20) DEFAULT 'headless', -- 'headless', 'visible', 'debug'

    -- Timeline de ejecución
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,

    -- Estado y resultado
    status VARCHAR(20) NOT NULL, -- 'running', 'completed', 'failed', 'timeout'
    success BOOLEAN DEFAULT false,

    -- Datos de entrada y salida
    input_data JSONB NOT NULL,
    output_data JSONB,

    -- Logs detallados
    execution_logs JSONB DEFAULT '[]',
    screenshots JSONB DEFAULT '[]', -- URLs de capturas de pantalla

    -- Análisis de errores
    error_type VARCHAR(50),
    error_message TEXT,
    error_screenshot_url VARCHAR(500),

    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===============================================================
-- 3. TABLAS DE CREDENCIALES Y SEGURIDAD
-- ===============================================================

-- Credenciales seguras para merchants
CREATE TABLE IF NOT EXISTS merchant_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    merchant_id UUID NOT NULL REFERENCES merchants(id),

    -- Tipo de credencial
    credential_type VARCHAR(20) NOT NULL, -- 'web_login', 'api_key', 'email'

    -- Datos encriptados (usar vault en producción)
    encrypted_data JSONB NOT NULL,
    vault_path VARCHAR(255), -- Path en HashiCorp Vault

    -- Estado y validación
    is_valid BOOLEAN DEFAULT true,
    last_validated TIMESTAMP WITH TIME ZONE,
    validation_errors JSONB DEFAULT '[]',

    -- Metadatos
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(company_id, merchant_id, credential_type)
);

-- ===============================================================
-- 4. TABLAS DE CONCILIACIÓN BANCARIA
-- ===============================================================

-- Movimientos bancarios
CREATE TABLE IF NOT EXISTS bank_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),

    -- Datos del movimiento
    bank_account VARCHAR(50),
    transaction_date DATE NOT NULL,
    description TEXT,
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'MXN',

    -- Clasificación
    movement_type VARCHAR(20), -- 'debit', 'credit'
    category VARCHAR(50),

    -- Estado de conciliación
    reconciliation_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'matched', 'manual', 'excluded'
    matched_ticket_id UUID REFERENCES tickets(id),

    -- Metadatos de importación
    import_batch_id UUID,
    external_reference VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===============================================================
-- 5. TABLAS DE AUDITORÍA Y LOGS
-- ===============================================================

-- Eventos del sistema para auditoría completa
CREATE TABLE IF NOT EXISTS system_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Contexto del evento
    event_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50), -- 'ticket', 'job', 'automation', etc.
    entity_id UUID,

    -- Usuario y compañía
    company_id UUID REFERENCES companies(id),
    user_id VARCHAR(255),

    -- Datos del evento
    event_data JSONB NOT NULL,

    -- Metadatos
    ip_address INET,
    user_agent TEXT,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Métricas de rendimiento
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Métricas por día/hora
    metric_date DATE NOT NULL,
    metric_hour INTEGER, -- 0-23, NULL para métricas diarias

    -- Contexto
    company_id UUID REFERENCES companies(id),
    merchant_id UUID REFERENCES merchants(id),

    -- Métricas de tickets
    tickets_uploaded INTEGER DEFAULT 0,
    tickets_processed INTEGER DEFAULT 0,
    tickets_auto_invoiced INTEGER DEFAULT 0,
    tickets_manual_review INTEGER DEFAULT 0,

    -- Métricas de tiempo
    avg_processing_time_ms INTEGER,
    avg_invoicing_time_ms INTEGER,

    -- Métricas de éxito
    success_rate DECIMAL(5,2),

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(metric_date, metric_hour, company_id, merchant_id)
);

-- ===============================================================
-- 6. ÍNDICES PARA RENDIMIENTO
-- ===============================================================

-- Índices en tickets
CREATE INDEX IF NOT EXISTS idx_tickets_company_status ON tickets(company_id, processing_status);
CREATE INDEX IF NOT EXISTS idx_tickets_invoice_status ON tickets(invoice_status);
CREATE INDEX IF NOT EXISTS idx_tickets_merchant_date ON tickets(merchant_id, ticket_date);
CREATE INDEX IF NOT EXISTS idx_tickets_total ON tickets(total);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at);

-- Índices en jobs
CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON invoice_automation_jobs(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_scheduled_at ON invoice_automation_jobs(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON invoice_automation_jobs(company_id);

-- Índices en merchants
CREATE INDEX IF NOT EXISTS idx_merchants_rfc ON merchants(rfc);
CREATE INDEX IF NOT EXISTS idx_merchants_name_trgm ON merchants USING gin(name gin_trgm_ops);

-- Índices en movimientos bancarios
CREATE INDEX IF NOT EXISTS idx_bank_movements_company_date ON bank_movements(company_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_bank_movements_amount ON bank_movements(amount);
CREATE INDEX IF NOT EXISTS idx_bank_movements_reconciliation ON bank_movements(reconciliation_status);

-- Índices en eventos del sistema
CREATE INDEX IF NOT EXISTS idx_system_events_type_date ON system_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_system_events_entity ON system_events(entity_type, entity_id);

-- ===============================================================
-- 7. TRIGGERS PARA TIMESTAMPS AUTOMÁTICOS
-- ===============================================================

-- Función para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Aplicar triggers
CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_merchants_updated_at BEFORE UPDATE ON merchants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tickets_updated_at BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON invoice_automation_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_credentials_updated_at BEFORE UPDATE ON merchant_credentials FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_bank_movements_updated_at BEFORE UPDATE ON bank_movements FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===============================================================
-- 8. DATOS INICIALES
-- ===============================================================

-- Merchants populares precargados
INSERT INTO merchants (name, rfc, portal_url, portal_type, identification_patterns, required_fields) VALUES
('OXXO', 'OXX970814HS9', 'https://factura.oxxo.com', 'web_form',
 '["OXXO", "CADENA COMERCIAL OXXO"]',
 '["folio", "fecha", "total"]'),

('Walmart', 'WAL9709244W4', 'https://factura.walmart.com.mx', 'web_form',
 '["WALMART", "WAL-MART", "SUPERCENTER"]',
 '["folio", "fecha", "total", "tienda"]'),

('Costco', 'COS050815PE4', 'https://facturaelectronica.costco.com.mx', 'web_form',
 '["COSTCO", "WHOLESALE"]',
 '["folio", "fecha", "total", "almacen"]'),

('Home Depot', 'HDM930228Q90', 'https://homedepot.com.mx/facturacion', 'web_form',
 '["HOME DEPOT", "THE HOME DEPOT"]',
 '["folio", "fecha", "total", "tienda"]'),

('Soriana', 'SOR810511HN9', 'https://facturacion.soriana.com', 'web_form',
 '["SORIANA", "HIPER SORIANA", "MEGA SORIANA"]',
 '["folio", "fecha", "total"]'),

('Farmacia del Ahorro', 'FDA970304GH6', 'https://facturacion.fahorro.com.mx', 'web_form',
 '["FARMACIA DEL AHORRO", "FAHORRO"]',
 '["folio", "fecha", "total"]'),

('7-Eleven', 'SEL991209KE7', 'https://facturacion.7-eleven.com.mx', 'web_form',
 '["7-ELEVEN", "7 ELEVEN", "SEVEN ELEVEN"]',
 '["folio", "fecha", "total"]'),

('Mejor Futuro', 'MFU761216I40', 'https://facturacion.inforest.com.mx', 'web_form',
 '["MEJOR FUTURO", "MEJOR FUTURO S.A. DE C.V.", "MFU761216I40"]',
 '["folio", "fecha", "total"]')

ON CONFLICT (rfc) DO UPDATE SET
    portal_url = EXCLUDED.portal_url,
    identification_patterns = EXCLUDED.identification_patterns,
    required_fields = EXCLUDED.required_fields,
    updated_at = NOW();

-- ===============================================================
-- 9. FUNCIONES ÚTILES
-- ===============================================================

-- Función para obtener estadísticas de empresa
CREATE OR REPLACE FUNCTION get_company_stats(company_uuid UUID)
RETURNS JSON AS $$
DECLARE
    stats JSON;
BEGIN
    SELECT json_build_object(
        'total_tickets', COUNT(*),
        'pending_invoicing', COUNT(*) FILTER (WHERE invoice_status = 'pending'),
        'auto_invoiced', COUNT(*) FILTER (WHERE invoice_status = 'invoiced'),
        'manual_review', COUNT(*) FILTER (WHERE invoice_status = 'manual_review'),
        'success_rate', ROUND(
            (COUNT(*) FILTER (WHERE invoice_status = 'invoiced') * 100.0 / NULLIF(COUNT(*), 0)), 2
        ),
        'avg_processing_time', AVG(
            EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000
        )
    ) INTO stats
    FROM tickets
    WHERE company_id = company_uuid
    AND created_at >= NOW() - INTERVAL '30 days';

    RETURN stats;
END;
$$ LANGUAGE plpgsql;

-- Función para obtener próximos jobs a ejecutar
CREATE OR REPLACE FUNCTION get_pending_jobs(limit_count INTEGER DEFAULT 10)
RETURNS TABLE(
    job_id UUID,
    ticket_id UUID,
    company_id UUID,
    merchant_id UUID,
    priority INTEGER,
    scheduled_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        j.id,
        j.ticket_id,
        j.company_id,
        j.merchant_id,
        j.priority,
        j.scheduled_at
    FROM invoice_automation_jobs j
    WHERE j.status = 'pending'
    AND j.scheduled_at <= NOW()
    ORDER BY j.priority DESC, j.scheduled_at ASC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- ===============================================================
-- COMENTARIOS FINALES
-- ===============================================================

-- Esta base de datos está diseñada para:
-- 1. Escalar a miles de tickets diarios
-- 2. Soportar múltiples companies/tenants
-- 3. Automatización completa con RPA
-- 4. Auditoría total de todas las operaciones
-- 5. Conciliación bancaria automática
-- 6. Métricas de rendimiento en tiempo real
-- 7. Manejo seguro de credenciales
-- 8. Recuperación ante fallos con retry logic

COMMENT ON TABLE tickets IS 'Tickets subidos por usuarios para facturación automática';
COMMENT ON TABLE invoice_automation_jobs IS 'Jobs de automatización RPA para facturación';
COMMENT ON TABLE automation_templates IS 'Plantillas de automatización para diferentes portales';
COMMENT ON TABLE merchant_credentials IS 'Credenciales seguras para acceso a portales de merchants';
COMMENT ON TABLE system_events IS 'Auditoría completa de eventos del sistema';
COMMENT ON TABLE performance_metrics IS 'Métricas de rendimiento y KPIs del sistema';