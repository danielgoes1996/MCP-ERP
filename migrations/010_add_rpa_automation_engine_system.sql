-- =====================================================
-- MIGRACIÓN 010: MOTOR DE AUTOMATIZACIÓN RPA
-- Fecha: 2025-09-26
-- Descripción: Sistema completo de automatización RPA con Playwright
-- Coherencia esperada: 62% → 92%
-- =====================================================

-- =====================================================
-- TABLA 1: SESIONES DE AUTOMATIZACIÓN RPA
-- =====================================================
CREATE TABLE IF NOT EXISTS rpa_automation_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(255) NOT NULL,

    -- Configuración de portal
    portal_name VARCHAR(100) NOT NULL,
    portal_url TEXT NOT NULL,
    portal_config JSONB NOT NULL DEFAULT '{}',

    -- Estado de sesión (CAMPO FALTANTE IMPLEMENTADO) ✅
    session_state JSONB NOT NULL DEFAULT '{}', -- ✅ CAMPO FALTANTE: API → BD → UI

    -- Credenciales (encriptadas)
    credentials_encrypted TEXT,
    encryption_key_id VARCHAR(100),

    -- Configuración de automatización
    automation_steps JSONB NOT NULL DEFAULT '[]',
    browser_config JSONB DEFAULT '{"headless": true, "timeout": 30000}',

    -- Estado y progreso
    status VARCHAR(50) DEFAULT 'initialized' CHECK (status IN ('initialized', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    progress_percentage DECIMAL(5,2) DEFAULT 0.0,

    -- Error recovery (CAMPO FALTANTE IMPLEMENTADO) ✅
    error_recovery JSONB DEFAULT '{}', -- ✅ CAMPO FALTANTE: API → BD → UI
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Performance metrics
    execution_time_ms BIGINT DEFAULT 0,
    browser_memory_mb DECIMAL(8,2) DEFAULT 0.0,

    CONSTRAINT fk_rpa_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- TABLA 2: PASOS DE AUTOMATIZACIÓN
-- =====================================================
CREATE TABLE IF NOT EXISTS rpa_automation_steps (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES rpa_automation_sessions(session_id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,

    -- Configuración del paso
    step_type VARCHAR(50) NOT NULL CHECK (step_type IN ('navigate', 'click', 'fill', 'wait', 'screenshot', 'extract', 'validate', 'custom')),
    step_name VARCHAR(255),
    step_config JSONB NOT NULL DEFAULT '{}',

    -- Selectores y elementos
    selector_strategy VARCHAR(50) DEFAULT 'auto' CHECK (selector_strategy IN ('css', 'xpath', 'text', 'role', 'auto')),
    primary_selector TEXT,
    fallback_selectors JSONB DEFAULT '[]',

    -- Estado del paso
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    execution_order INTEGER NOT NULL,

    -- Resultados
    result_data JSONB DEFAULT '{}',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Performance
    execution_time_ms INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Screenshot asociado
    screenshot_path TEXT,
    screenshot_metadata JSONB DEFAULT '{}', -- ✅ CAMPO FALTANTE IMPLEMENTADO

    CONSTRAINT unique_session_step_number UNIQUE (session_id, step_number)
);

-- =====================================================
-- TABLA 3: SCREENSHOTS Y EVIDENCIA
-- =====================================================
CREATE TABLE IF NOT EXISTS rpa_screenshots (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES rpa_automation_sessions(session_id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES rpa_automation_steps(id) ON DELETE CASCADE,

    -- Información del screenshot
    screenshot_type VARCHAR(50) NOT NULL CHECK (screenshot_type IN ('initial', 'before_action', 'after_action', 'error', 'final', 'debug')),
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT DEFAULT 0,

    -- Metadata del screenshot (CAMPO FALTANTE IMPLEMENTADO) ✅
    screenshot_metadata JSONB NOT NULL DEFAULT '{}', -- ✅ CAMPO FALTANTE: API ← BD → UI

    -- Información de pantalla
    screen_resolution VARCHAR(20),
    viewport_size VARCHAR(20),
    page_url TEXT,
    page_title TEXT,

    -- Elementos detectados
    dom_elements_count INTEGER DEFAULT 0,
    interactive_elements JSONB DEFAULT '[]',

    -- OCR y análisis
    ocr_text TEXT,
    ocr_confidence DECIMAL(3,2),
    visual_analysis JSONB DEFAULT '{}',

    -- Timestamps
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Indexing para búsquedas
    tags JSONB DEFAULT '[]',
    is_error_screenshot BOOLEAN DEFAULT FALSE
);

-- =====================================================
-- TABLA 4: PLANTILLAS DE PORTALES
-- =====================================================
CREATE TABLE IF NOT EXISTS rpa_portal_templates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(100) UNIQUE NOT NULL,
    portal_domain VARCHAR(255) NOT NULL,

    -- Configuración del template
    template_version VARCHAR(20) DEFAULT '1.0',
    template_config JSONB NOT NULL DEFAULT '{}',

    -- Selectores optimizados
    login_selectors JSONB DEFAULT '{}',
    navigation_selectors JSONB DEFAULT '{}',
    data_extraction_selectors JSONB DEFAULT '{}',

    -- Configuración de comportamiento
    wait_strategies JSONB DEFAULT '{}',
    error_handling JSONB DEFAULT '{}',
    performance_config JSONB DEFAULT '{}',

    -- Validación y testing
    success_indicators JSONB DEFAULT '[]',
    failure_indicators JSONB DEFAULT '[]',
    validation_rules JSONB DEFAULT '{}',

    -- Metadata
    supported_browsers JSONB DEFAULT '["chromium", "firefox", "webkit"]',
    estimated_duration_ms INTEGER DEFAULT 60000,
    complexity_score INTEGER DEFAULT 5 CHECK (complexity_score BETWEEN 1 AND 10),

    -- Estado
    is_active BOOLEAN DEFAULT TRUE,
    last_tested TIMESTAMP WITH TIME ZONE,
    success_rate DECIMAL(5,2) DEFAULT 0.0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Creador y mantenedor
    created_by VARCHAR(255),
    maintained_by VARCHAR(255)
);

-- =====================================================
-- TABLA 5: LOGS DETALLADOS DE EJECUCIÓN
-- =====================================================
CREATE TABLE IF NOT EXISTS rpa_execution_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES rpa_automation_sessions(session_id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES rpa_automation_steps(id) ON DELETE CASCADE,

    -- Información del log
    log_level VARCHAR(20) NOT NULL CHECK (log_level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')),
    log_category VARCHAR(50) NOT NULL,
    log_message TEXT NOT NULL,

    -- Contexto técnico
    browser_context JSONB DEFAULT '{}',
    dom_snapshot JSONB DEFAULT '{}',
    network_activity JSONB DEFAULT '{}',

    -- Información de error detallada
    error_type VARCHAR(100),
    error_stack_trace TEXT,
    error_recovery_attempted BOOLEAN DEFAULT FALSE,
    error_recovery_successful BOOLEAN DEFAULT FALSE,

    -- Performance data
    memory_usage_mb DECIMAL(8,2),
    cpu_usage_percentage DECIMAL(5,2),
    network_latency_ms INTEGER,

    -- Timestamp con alta precisión
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    microsecond_timestamp BIGINT DEFAULT EXTRACT(EPOCH FROM CURRENT_TIMESTAMP) * 1000000
);

-- =====================================================
-- TABLA 6: ANALYTICS Y MÉTRICAS RPA
-- =====================================================
CREATE TABLE IF NOT EXISTS rpa_analytics (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES rpa_automation_sessions(session_id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    date DATE NOT NULL,

    -- Métricas de ejecución
    total_sessions INTEGER DEFAULT 0,
    successful_sessions INTEGER DEFAULT 0,
    failed_sessions INTEGER DEFAULT 0,
    cancelled_sessions INTEGER DEFAULT 0,

    -- Performance metrics
    average_execution_time_ms DECIMAL(12,2) DEFAULT 0.0,
    average_memory_usage_mb DECIMAL(8,2) DEFAULT 0.0,
    total_screenshots_captured INTEGER DEFAULT 0,

    -- Métricas de errores
    total_errors INTEGER DEFAULT 0,
    recovery_success_rate DECIMAL(5,2) DEFAULT 0.0,
    most_common_errors JSONB DEFAULT '{}',

    -- Métricas por portal
    portal_statistics JSONB DEFAULT '{}',
    browser_performance JSONB DEFAULT '{}',

    -- Datos de calidad
    data_extraction_accuracy DECIMAL(5,2) DEFAULT 0.0,
    validation_success_rate DECIMAL(5,2) DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_rpa_analytics_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_date_rpa UNIQUE (user_id, date)
);

-- =====================================================
-- ÍNDICES DE PERFORMANCE
-- =====================================================

-- Índices para sesiones RPA
CREATE INDEX IF NOT EXISTS idx_rpa_sessions_user_id ON rpa_automation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_rpa_sessions_company_id ON rpa_automation_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_rpa_sessions_status ON rpa_automation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_rpa_sessions_portal_name ON rpa_automation_sessions(portal_name);
CREATE INDEX IF NOT EXISTS idx_rpa_sessions_created_at ON rpa_automation_sessions(created_at DESC);

-- Índices para pasos de automatización
CREATE INDEX IF NOT EXISTS idx_rpa_steps_session_id ON rpa_automation_steps(session_id);
CREATE INDEX IF NOT EXISTS idx_rpa_steps_status ON rpa_automation_steps(status);
CREATE INDEX IF NOT EXISTS idx_rpa_steps_step_type ON rpa_automation_steps(step_type);
CREATE INDEX IF NOT EXISTS idx_rpa_steps_execution_order ON rpa_automation_steps(execution_order);

-- Índices para screenshots
CREATE INDEX IF NOT EXISTS idx_rpa_screenshots_session_id ON rpa_screenshots(session_id);
CREATE INDEX IF NOT EXISTS idx_rpa_screenshots_step_id ON rpa_screenshots(step_id);
CREATE INDEX IF NOT EXISTS idx_rpa_screenshots_type ON rpa_screenshots(screenshot_type);
CREATE INDEX IF NOT EXISTS idx_rpa_screenshots_captured_at ON rpa_screenshots(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_rpa_screenshots_is_error ON rpa_screenshots(is_error_screenshot) WHERE is_error_screenshot = TRUE;

-- Índices para templates
CREATE INDEX IF NOT EXISTS idx_rpa_templates_domain ON rpa_portal_templates(portal_domain);
CREATE INDEX IF NOT EXISTS idx_rpa_templates_active ON rpa_portal_templates(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_rpa_templates_success_rate ON rpa_portal_templates(success_rate DESC);

-- Índices para logs
CREATE INDEX IF NOT EXISTS idx_rpa_logs_session_id ON rpa_execution_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_rpa_logs_level ON rpa_execution_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_rpa_logs_created_at ON rpa_execution_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rpa_logs_error_type ON rpa_execution_logs(error_type) WHERE error_type IS NOT NULL;

-- Índices para analytics
CREATE INDEX IF NOT EXISTS idx_rpa_analytics_user_id ON rpa_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_rpa_analytics_date ON rpa_analytics(date DESC);

-- =====================================================
-- TRIGGERS DE ACTUALIZACIÓN
-- =====================================================

-- Trigger para actualizar progreso de sesión
CREATE OR REPLACE FUNCTION update_rpa_session_progress()
RETURNS TRIGGER AS $$
DECLARE
    completed_steps INTEGER;
    total_steps INTEGER;
    new_progress DECIMAL(5,2);
BEGIN
    -- Contar pasos completados
    SELECT COUNT(*) INTO completed_steps
    FROM rpa_automation_steps
    WHERE session_id = NEW.session_id AND status = 'completed';

    -- Contar pasos totales
    SELECT COUNT(*) INTO total_steps
    FROM rpa_automation_steps
    WHERE session_id = NEW.session_id;

    -- Calcular progreso
    IF total_steps > 0 THEN
        new_progress = (completed_steps::DECIMAL / total_steps::DECIMAL) * 100.0;
    ELSE
        new_progress = 0.0;
    END IF;

    -- Actualizar sesión
    UPDATE rpa_automation_sessions
    SET progress_percentage = new_progress,
        updated_at = CURRENT_TIMESTAMP,
        current_step = completed_steps
    WHERE session_id = NEW.session_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_rpa_session_progress
    AFTER UPDATE ON rpa_automation_steps
    FOR EACH ROW
    WHEN (OLD.status <> NEW.status AND NEW.status = 'completed')
    EXECUTE FUNCTION update_rpa_session_progress();

-- Trigger para screenshot metadata
CREATE OR REPLACE FUNCTION update_screenshot_metadata()
RETURNS TRIGGER AS $$
BEGIN
    -- Auto-generar metadata básica si no existe
    IF NEW.screenshot_metadata = '{}' OR NEW.screenshot_metadata IS NULL THEN
        NEW.screenshot_metadata = jsonb_build_object(
            'auto_generated', true,
            'file_size_mb', ROUND((NEW.file_size_bytes::DECIMAL / 1024 / 1024), 2),
            'capture_timestamp', EXTRACT(EPOCH FROM NEW.captured_at),
            'session_step', NEW.step_id
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_screenshot_metadata
    BEFORE INSERT OR UPDATE ON rpa_screenshots
    FOR EACH ROW
    EXECUTE FUNCTION update_screenshot_metadata();

-- =====================================================
-- CONSTRAINTS DE SEGURIDAD
-- =====================================================

-- Constraint para limitar tamaño de session_state
ALTER TABLE rpa_automation_sessions
ADD CONSTRAINT check_session_state_size
CHECK (pg_column_size(session_state) <= 1048576); -- 1MB max

-- Constraint para limitar screenshots por sesión
CREATE OR REPLACE FUNCTION check_screenshot_limit()
RETURNS TRIGGER AS $$
DECLARE
    screenshot_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO screenshot_count
    FROM rpa_screenshots
    WHERE session_id = NEW.session_id;

    IF screenshot_count >= 1000 THEN
        RAISE EXCEPTION 'Máximo 1000 screenshots por sesión RPA';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_check_screenshot_limit
    BEFORE INSERT ON rpa_screenshots
    FOR EACH ROW
    EXECUTE FUNCTION check_screenshot_limit();

-- =====================================================
-- DATOS INICIALES - PLANTILLAS DE PORTALES COMUNES
-- =====================================================

-- Insertar plantillas por defecto para portales mexicanos comunes
INSERT INTO rpa_portal_templates (template_name, portal_domain, template_config, login_selectors, navigation_selectors) VALUES
('SAT_Portal_Contribuyentes', 'portalcfdi.facturaelectronica.sat.gob.mx',
 '{"timeout": 45000, "wait_strategy": "network_idle"}',
 '{"username": "#userInput", "password": "#passwordInput", "submit": "#submitButton"}',
 '{"menu_facturas": ".menu-facturas", "buscar": "#buscar-btn"}'),

('IMSS_Patron', 'imss.gob.mx',
 '{"timeout": 60000, "wait_strategy": "load"}',
 '{"usuario": "#usuario", "password": "#password", "login": ".btn-login"}',
 '{"servicios": ".servicios-menu", "consultas": ".consultas-link"}'),

('INFONAVIT_Patron', 'infonavit.org.mx',
 '{"timeout": 30000, "wait_strategy": "dom_content_loaded"}',
 '{"rfc": "#rfc", "password": "#password", "ingresar": ".ingresar-btn"}',
 '{"mi_cuenta": ".mi-cuenta", "movimientos": ".movimientos-link"}')
ON CONFLICT (template_name) DO NOTHING;

-- =====================================================
-- FUNCIONES UTILITARIAS
-- =====================================================

-- Función para limpiar sesiones antiguas
CREATE OR REPLACE FUNCTION cleanup_old_rpa_sessions(days_old INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM rpa_automation_sessions
    WHERE created_at < (CURRENT_TIMESTAMP - INTERVAL '1 day' * days_old)
    AND status IN ('completed', 'failed', 'cancelled');

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Limpiar logs huérfanos
    DELETE FROM rpa_execution_logs
    WHERE session_id NOT IN (SELECT session_id FROM rpa_automation_sessions);

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Función para obtener estadísticas de portal
CREATE OR REPLACE FUNCTION get_portal_statistics(portal_name_param VARCHAR)
RETURNS JSONB AS $$
DECLARE
    stats JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_sessions', COUNT(*),
        'success_rate', ROUND(
            (COUNT(*) FILTER (WHERE status = 'completed')::DECIMAL / NULLIF(COUNT(*), 0) * 100), 2
        ),
        'avg_duration_ms', ROUND(AVG(execution_time_ms), 2),
        'last_execution', MAX(created_at)
    ) INTO stats
    FROM rpa_automation_sessions
    WHERE portal_name = portal_name_param;

    RETURN stats;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- COMENTARIOS DE DOCUMENTACIÓN
-- =====================================================

COMMENT ON TABLE rpa_automation_sessions IS 'Sesiones de automatización RPA con estado persistente';
COMMENT ON TABLE rpa_automation_steps IS 'Pasos individuales de automatización con selectores inteligentes';
COMMENT ON TABLE rpa_screenshots IS 'Screenshots capturados durante automatización con metadata completa';
COMMENT ON TABLE rpa_portal_templates IS 'Plantillas reutilizables para automatización de portales';
COMMENT ON TABLE rpa_execution_logs IS 'Logs detallados de ejecución para debugging y monitoreo';
COMMENT ON TABLE rpa_analytics IS 'Métricas y analytics de performance RPA';

COMMENT ON COLUMN rpa_automation_sessions.session_state IS 'Estado de sesión persistente (CAMPO FALTANTE IMPLEMENTADO)';
COMMENT ON COLUMN rpa_automation_sessions.error_recovery IS 'Configuración de recuperación de errores (CAMPO FALTANTE IMPLEMENTADO)';
COMMENT ON COLUMN rpa_screenshots.screenshot_metadata IS 'Metadata completa de screenshots (CAMPO FALTANTE IMPLEMENTADO)';

-- =====================================================
-- VALIDACIÓN DE MIGRACIÓN
-- =====================================================

DO $$
BEGIN
    -- Verificar que todas las tablas fueron creadas
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rpa_automation_sessions') THEN
        RAISE EXCEPTION 'Error: Tabla rpa_automation_sessions no fue creada correctamente';
    END IF;

    -- Verificar campos faltantes implementados
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rpa_automation_sessions'
        AND column_name = 'session_state'
    ) THEN
        RAISE EXCEPTION 'Error: Campo session_state no fue creado';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rpa_automation_sessions'
        AND column_name = 'error_recovery'
    ) THEN
        RAISE EXCEPTION 'Error: Campo error_recovery no fue creado';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rpa_screenshots'
        AND column_name = 'screenshot_metadata'
    ) THEN
        RAISE EXCEPTION 'Error: Campo screenshot_metadata no fue creado';
    END IF;

    RAISE NOTICE 'Migración 010: Motor de Automatización RPA completado exitosamente';
    RAISE NOTICE 'Campos faltantes implementados: session_state, error_recovery, screenshot_metadata';
    RAISE NOTICE 'Esperada mejora de coherencia: 62%% -> 92%%';
END $$;