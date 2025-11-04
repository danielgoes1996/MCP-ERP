-- =====================================================
-- MIGRACIÓN 011: WEB AUTOMATION ENGINE SYSTEM
-- Fecha: 2025-09-26
-- Descripción: Sistema completo de automatización web multi-browser
-- Coherencia esperada: 60% → 91%
-- =====================================================

-- =====================================================
-- TABLA 1: SESIONES DE AUTOMATIZACIÓN WEB
-- =====================================================
CREATE TABLE IF NOT EXISTS web_automation_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(255) NOT NULL,

    -- Configuración de automatización
    target_url TEXT NOT NULL,
    automation_strategy VARCHAR(50) DEFAULT 'multi_engine' CHECK (automation_strategy IN ('single_engine', 'multi_engine', 'failover', 'parallel')),
    primary_engine VARCHAR(50) DEFAULT 'playwright' CHECK (primary_engine IN ('playwright', 'selenium', 'puppeteer', 'requests_html')),

    -- Browser fingerprinting (CAMPO FALTANTE IMPLEMENTADO) ✅
    browser_fingerprint JSONB DEFAULT '{}', -- ✅ CAMPO FALTANTE: API ← BD → UI

    -- Anti-detection y evasión
    stealth_mode BOOLEAN DEFAULT TRUE,
    user_agent_rotation BOOLEAN DEFAULT TRUE,
    proxy_rotation BOOLEAN DEFAULT FALSE,
    request_delays JSONB DEFAULT '{"min_ms": 1000, "max_ms": 3000}',

    -- Estado de la sesión
    status VARCHAR(50) DEFAULT 'initialized' CHECK (status IN ('initialized', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    progress_percentage DECIMAL(5,2) DEFAULT 0.0,

    -- CAPTCHA handling (CAMPO FALTANTE IMPLEMENTADO) ✅
    captcha_solved JSONB DEFAULT '{}', -- ✅ CAMPO FALTANTE: API ← BD → UI
    captcha_service VARCHAR(50), -- 2captcha, anticaptcha, etc.

    -- Retry management (CAMPO FALTANTE IMPLEMENTADO) ✅
    retry_count INTEGER DEFAULT 0, -- ✅ CAMPO FALTANTE: API → BD → UI
    max_retries INTEGER DEFAULT 5,
    retry_strategy VARCHAR(50) DEFAULT 'exponential_backoff',

    -- Performance y métricas
    execution_time_ms BIGINT DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    data_extraction_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT fk_web_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- TABLA 2: ENGINES DE AUTOMATIZACIÓN
-- =====================================================
CREATE TABLE IF NOT EXISTS web_automation_engines (
    id SERIAL PRIMARY KEY,
    engine_name VARCHAR(50) UNIQUE NOT NULL,
    engine_type VARCHAR(50) NOT NULL CHECK (engine_type IN ('browser_automation', 'http_client', 'hybrid')),

    -- Configuración del engine
    engine_config JSONB NOT NULL DEFAULT '{}',
    capabilities JSONB DEFAULT '[]', -- ['javascript', 'cookies', 'proxy', 'captcha']

    -- Performance metrics
    success_rate DECIMAL(5,2) DEFAULT 0.0,
    average_response_time_ms INTEGER DEFAULT 0,
    memory_usage_mb DECIMAL(8,2) DEFAULT 0.0,

    -- Límites y configuración
    max_concurrent_sessions INTEGER DEFAULT 10,
    timeout_seconds INTEGER DEFAULT 30,
    retry_attempts INTEGER DEFAULT 3,

    -- Estado
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(50) DEFAULT 'unknown' CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
    last_health_check TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLA 3: PASOS DE AUTOMATIZACIÓN WEB
-- =====================================================
CREATE TABLE IF NOT EXISTS web_automation_steps (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES web_automation_sessions(session_id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,

    -- Configuración del paso
    step_type VARCHAR(50) NOT NULL CHECK (step_type IN ('navigate', 'click', 'fill', 'extract', 'wait', 'scroll', 'screenshot', 'javascript', 'captcha_solve')),
    step_description TEXT,
    step_config JSONB NOT NULL DEFAULT '{}',

    -- Selección de elementos
    selector_strategy VARCHAR(50) DEFAULT 'intelligent' CHECK (selector_strategy IN ('css', 'xpath', 'text', 'ai_based', 'intelligent')),
    target_selectors JSONB DEFAULT '[]', -- Array de selectores con prioridad
    fallback_strategies JSONB DEFAULT '[]',

    -- Engine assignment
    assigned_engine VARCHAR(50),
    fallback_engines JSONB DEFAULT '[]',

    -- Estado y resultados
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped', 'retrying')),
    execution_attempts INTEGER DEFAULT 0,
    result_data JSONB DEFAULT '{}',
    extracted_content TEXT,

    -- Error handling
    error_type VARCHAR(100),
    error_message TEXT,
    error_context JSONB DEFAULT '{}',

    -- Performance
    execution_time_ms INTEGER DEFAULT 0,
    network_requests_count INTEGER DEFAULT 0,

    -- Timestamps
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT unique_session_step_number UNIQUE (session_id, step_number)
);

-- =====================================================
-- TABLA 4: DOM ANALYSIS Y ELEMENTOS
-- =====================================================
CREATE TABLE IF NOT EXISTS web_dom_analysis (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES web_automation_sessions(session_id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES web_automation_steps(id) ON DELETE CASCADE,

    -- URL y contexto de página
    page_url TEXT NOT NULL,
    page_title TEXT,
    dom_ready_time_ms INTEGER DEFAULT 0,

    -- Análisis de DOM
    total_elements INTEGER DEFAULT 0,
    interactive_elements INTEGER DEFAULT 0,
    form_elements INTEGER DEFAULT 0,
    iframe_count INTEGER DEFAULT 0,

    -- Elementos detectados
    detected_elements JSONB DEFAULT '[]',
    clickable_elements JSONB DEFAULT '[]',
    input_elements JSONB DEFAULT '[]',

    -- Claude AI analysis
    ai_element_analysis JSONB DEFAULT '{}',
    suggested_selectors JSONB DEFAULT '[]',
    confidence_scores JSONB DEFAULT '{}',

    -- Metadata de análisis
    analysis_engine VARCHAR(50) DEFAULT 'claude',
    analysis_time_ms INTEGER DEFAULT 0,
    analysis_quality_score DECIMAL(3,2) DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLA 5: CAPTCHA SOLUTIONS
-- =====================================================
CREATE TABLE IF NOT EXISTS web_captcha_solutions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES web_automation_sessions(session_id) ON DELETE CASCADE,
    step_id INTEGER REFERENCES web_automation_steps(id) ON DELETE CASCADE,

    -- Información del CAPTCHA
    captcha_type VARCHAR(50) NOT NULL CHECK (captcha_type IN ('recaptcha_v2', 'recaptcha_v3', 'hcaptcha', 'funcaptcha', 'image_captcha', 'text_captcha')),
    captcha_url TEXT,
    site_key VARCHAR(255),

    -- Solución
    solution_method VARCHAR(50) CHECK (solution_method IN ('2captcha', 'anticaptcha', 'manual', 'ai_based')),
    solution_data JSONB DEFAULT '{}',
    solution_token TEXT,

    -- Performance
    solve_time_ms INTEGER DEFAULT 0,
    cost_credits DECIMAL(8,4) DEFAULT 0.0,
    success BOOLEAN DEFAULT FALSE,

    -- Service details
    service_task_id VARCHAR(255),
    service_response JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    solved_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- TABLA 6: ANALYTICS Y MÉTRICAS WEB
-- =====================================================
CREATE TABLE IF NOT EXISTS web_automation_analytics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    date DATE NOT NULL,

    -- Métricas de sesiones
    total_sessions INTEGER DEFAULT 0,
    successful_sessions INTEGER DEFAULT 0,
    failed_sessions INTEGER DEFAULT 0,

    -- Performance metrics
    average_execution_time_ms DECIMAL(12,2) DEFAULT 0.0,
    average_success_rate DECIMAL(5,2) DEFAULT 0.0,
    total_data_extracted_mb DECIMAL(10,2) DEFAULT 0.0,

    -- Engine performance
    engine_usage JSONB DEFAULT '{}', -- Uso por engine
    engine_success_rates JSONB DEFAULT '{}',

    -- Error analytics
    total_errors INTEGER DEFAULT 0,
    error_types JSONB DEFAULT '{}',
    captcha_encounters INTEGER DEFAULT 0,
    captcha_solve_rate DECIMAL(5,2) DEFAULT 0.0,

    -- Anti-detection metrics
    fingerprint_rotations INTEGER DEFAULT 0,
    proxy_rotations INTEGER DEFAULT 0,
    detection_rate DECIMAL(5,2) DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_web_analytics_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_web_user_date UNIQUE (user_id, date)
);

-- =====================================================
-- ÍNDICES DE PERFORMANCE
-- =====================================================

-- Índices para sesiones web
CREATE INDEX IF NOT EXISTS idx_web_sessions_user_id ON web_automation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_web_sessions_company_id ON web_automation_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_web_sessions_status ON web_automation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_web_sessions_strategy ON web_automation_sessions(automation_strategy);
CREATE INDEX IF NOT EXISTS idx_web_sessions_engine ON web_automation_sessions(primary_engine);
CREATE INDEX IF NOT EXISTS idx_web_sessions_created_at ON web_automation_sessions(created_at DESC);

-- Índices para engines
CREATE INDEX IF NOT EXISTS idx_web_engines_type ON web_automation_engines(engine_type);
CREATE INDEX IF NOT EXISTS idx_web_engines_active ON web_automation_engines(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_web_engines_health ON web_automation_engines(health_status);
CREATE INDEX IF NOT EXISTS idx_web_engines_success_rate ON web_automation_engines(success_rate DESC);

-- Índices para pasos
CREATE INDEX IF NOT EXISTS idx_web_steps_session_id ON web_automation_steps(session_id);
CREATE INDEX IF NOT EXISTS idx_web_steps_status ON web_automation_steps(status);
CREATE INDEX IF NOT EXISTS idx_web_steps_type ON web_automation_steps(step_type);
CREATE INDEX IF NOT EXISTS idx_web_steps_engine ON web_automation_steps(assigned_engine);

-- Índices para DOM analysis
CREATE INDEX IF NOT EXISTS idx_web_dom_session_id ON web_dom_analysis(session_id);
CREATE INDEX IF NOT EXISTS idx_web_dom_step_id ON web_dom_analysis(step_id);
CREATE INDEX IF NOT EXISTS idx_web_dom_url ON web_dom_analysis(page_url);
CREATE INDEX IF NOT EXISTS idx_web_dom_created_at ON web_dom_analysis(created_at DESC);

-- Índices para CAPTCHA
CREATE INDEX IF NOT EXISTS idx_web_captcha_session_id ON web_captcha_solutions(session_id);
CREATE INDEX IF NOT EXISTS idx_web_captcha_type ON web_captcha_solutions(captcha_type);
CREATE INDEX IF NOT EXISTS idx_web_captcha_success ON web_captcha_solutions(success);
CREATE INDEX IF NOT EXISTS idx_web_captcha_method ON web_captcha_solutions(solution_method);

-- Índices para analytics
CREATE INDEX IF NOT EXISTS idx_web_analytics_user_id ON web_automation_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_web_analytics_date ON web_automation_analytics(date DESC);

-- =====================================================
-- TRIGGERS DE ACTUALIZACIÓN
-- =====================================================

-- Trigger para actualizar progreso de sesión web
CREATE OR REPLACE FUNCTION update_web_session_progress()
RETURNS TRIGGER AS $$
DECLARE
    completed_steps INTEGER;
    total_steps INTEGER;
    new_progress DECIMAL(5,2);
    current_success_rate DECIMAL(5,2);
BEGIN
    -- Contar pasos completados y totales
    SELECT COUNT(*) FILTER (WHERE status = 'completed'),
           COUNT(*)
    INTO completed_steps, total_steps
    FROM web_automation_steps
    WHERE session_id = NEW.session_id;

    -- Calcular progreso
    IF total_steps > 0 THEN
        new_progress = (completed_steps::DECIMAL / total_steps::DECIMAL) * 100.0;
    ELSE
        new_progress = 0.0;
    END IF;

    -- Calcular tasa de éxito
    IF completed_steps > 0 THEN
        current_success_rate = (completed_steps::DECIMAL / GREATEST(NEW.execution_attempts, 1)) * 100.0;
    ELSE
        current_success_rate = 0.0;
    END IF;

    -- Actualizar sesión
    UPDATE web_automation_sessions
    SET progress_percentage = new_progress,
        current_step = completed_steps,
        success_rate = current_success_rate,
        updated_at = CURRENT_TIMESTAMP
    WHERE session_id = NEW.session_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_web_session_progress
    AFTER UPDATE ON web_automation_steps
    FOR EACH ROW
    WHEN (OLD.status <> NEW.status)
    EXECUTE FUNCTION update_web_session_progress();

-- Trigger para incrementar retry count
CREATE OR REPLACE FUNCTION increment_web_retry_count()
RETURNS TRIGGER AS $$
BEGIN
    -- Incrementar retry count en la sesión
    UPDATE web_automation_sessions
    SET retry_count = retry_count + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE session_id = NEW.session_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_increment_web_retry_count
    AFTER UPDATE ON web_automation_steps
    FOR EACH ROW
    WHEN (OLD.status <> NEW.status AND NEW.status = 'retrying')
    EXECUTE FUNCTION increment_web_retry_count();

-- =====================================================
-- CONSTRAINTS DE SEGURIDAD
-- =====================================================

-- Constraint para limitar tamaño de browser_fingerprint
ALTER TABLE web_automation_sessions
ADD CONSTRAINT check_browser_fingerprint_size
CHECK (pg_column_size(browser_fingerprint) <= 65536); -- 64KB max

-- Constraint para limitar captcha_solved size
ALTER TABLE web_automation_sessions
ADD CONSTRAINT check_captcha_solved_size
CHECK (pg_column_size(captcha_solved) <= 32768); -- 32KB max

-- Constraint para retry count razonable
ALTER TABLE web_automation_sessions
ADD CONSTRAINT check_retry_count_limit
CHECK (retry_count >= 0 AND retry_count <= max_retries);

-- Constraint para success rate válido
ALTER TABLE web_automation_sessions
ADD CONSTRAINT check_success_rate_range
CHECK (success_rate >= 0.0 AND success_rate <= 100.0);

-- =====================================================
-- DATOS INICIALES - ENGINES POR DEFECTO
-- =====================================================

-- Insertar engines de automatización por defecto
INSERT INTO web_automation_engines (engine_name, engine_type, engine_config, capabilities, max_concurrent_sessions, timeout_seconds) VALUES
('playwright', 'browser_automation',
 '{"headless": true, "stealth": true, "user_data_dir": null}',
 '["javascript", "cookies", "proxy", "screenshots", "network_interception"]',
 20, 60),

('selenium', 'browser_automation',
 '{"headless": true, "stealth_mode": true, "page_load_strategy": "normal"}',
 '["javascript", "cookies", "proxy", "screenshots", "file_upload"]',
 15, 45),

('puppeteer', 'browser_automation',
 '{"headless": true, "stealth": true, "no_sandbox": false}',
 '["javascript", "cookies", "proxy", "screenshots", "pdf_generation"]',
 18, 50),

('requests_html', 'http_client',
 '{"render_js": true, "browser_args": ["--no-sandbox", "--disable-gpu"]}',
 '["javascript", "cookies", "simple_forms"]',
 50, 30),

('httpx_client', 'http_client',
 '{"follow_redirects": true, "verify_ssl": true}',
 '["cookies", "headers", "fast_requests"]',
 100, 15)

ON CONFLICT (engine_name) DO NOTHING;

-- =====================================================
-- FUNCIONES UTILITARIAS
-- =====================================================

-- Función para obtener engine recomendado
CREATE OR REPLACE FUNCTION get_recommended_engine(
    target_url TEXT,
    required_capabilities JSONB DEFAULT '[]'
)
RETURNS VARCHAR(50) AS $$
DECLARE
    recommended_engine VARCHAR(50);
BEGIN
    -- Lógica simple de recomendación
    SELECT engine_name INTO recommended_engine
    FROM web_automation_engines
    WHERE is_active = TRUE
    AND health_status = 'healthy'
    AND capabilities @> required_capabilities
    ORDER BY success_rate DESC, average_response_time_ms ASC
    LIMIT 1;

    -- Fallback a playwright si no se encuentra nada
    IF recommended_engine IS NULL THEN
        recommended_engine := 'playwright';
    END IF;

    RETURN recommended_engine;
END;
$$ LANGUAGE plpgsql;

-- Función para limpiar sesiones antiguas
CREATE OR REPLACE FUNCTION cleanup_old_web_sessions(days_old INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM web_automation_sessions
    WHERE created_at < (CURRENT_TIMESTAMP - INTERVAL '1 day' * days_old)
    AND status IN ('completed', 'failed', 'cancelled');

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Limpiar datos huérfanos
    DELETE FROM web_dom_analysis
    WHERE session_id NOT IN (SELECT session_id FROM web_automation_sessions);

    DELETE FROM web_captcha_solutions
    WHERE session_id NOT IN (SELECT session_id FROM web_automation_sessions);

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Función para obtener estadísticas de engine
CREATE OR REPLACE FUNCTION get_engine_statistics(engine_name_param VARCHAR)
RETURNS JSONB AS $$
DECLARE
    stats JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_sessions', COUNT(*),
        'success_rate', ROUND(AVG(success_rate), 2),
        'avg_execution_time_ms', ROUND(AVG(execution_time_ms), 2),
        'last_used', MAX(created_at),
        'captcha_solve_rate', ROUND(AVG(
            CASE WHEN captcha_solved::text <> '{}' THEN 100.0 ELSE 0.0 END
        ), 2)
    ) INTO stats
    FROM web_automation_sessions
    WHERE primary_engine = engine_name_param;

    RETURN stats;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- COMENTARIOS DE DOCUMENTACIÓN
-- =====================================================

COMMENT ON TABLE web_automation_sessions IS 'Sesiones de automatización web multi-engine con anti-detection';
COMMENT ON TABLE web_automation_engines IS 'Engines de automatización disponibles con métricas de performance';
COMMENT ON TABLE web_automation_steps IS 'Pasos individuales de automatización con estrategias de fallback';
COMMENT ON TABLE web_dom_analysis IS 'Análisis inteligente de DOM con Claude AI integration';
COMMENT ON TABLE web_captcha_solutions IS 'Soluciones de CAPTCHA con múltiples métodos';
COMMENT ON TABLE web_automation_analytics IS 'Analytics completas de automatización web';

COMMENT ON COLUMN web_automation_sessions.browser_fingerprint IS 'Fingerprint del navegador (CAMPO FALTANTE IMPLEMENTADO)';
COMMENT ON COLUMN web_automation_sessions.captcha_solved IS 'Información de CAPTCHAs resueltos (CAMPO FALTANTE IMPLEMENTADO)';
COMMENT ON COLUMN web_automation_sessions.retry_count IS 'Contador de reintentos persistente (CAMPO FALTANTE IMPLEMENTADO)';

-- =====================================================
-- VALIDACIÓN DE MIGRACIÓN
-- =====================================================

DO $$
BEGIN
    -- Verificar que todas las tablas fueron creadas
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'web_automation_sessions') THEN
        RAISE EXCEPTION 'Error: Tabla web_automation_sessions no fue creada correctamente';
    END IF;

    -- Verificar campos faltantes implementados
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'web_automation_sessions'
        AND column_name = 'browser_fingerprint'
    ) THEN
        RAISE EXCEPTION 'Error: Campo browser_fingerprint no fue creado';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'web_automation_sessions'
        AND column_name = 'captcha_solved'
    ) THEN
        RAISE EXCEPTION 'Error: Campo captcha_solved no fue creado';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'web_automation_sessions'
        AND column_name = 'retry_count'
    ) THEN
        RAISE EXCEPTION 'Error: Campo retry_count no fue creado';
    END IF;

    RAISE NOTICE 'Migración 011: Web Automation Engine completado exitosamente';
    RAISE NOTICE 'Campos faltantes implementados: browser_fingerprint, captcha_solved, retry_count';
    RAISE NOTICE 'Esperada mejora de coherencia: 60%% -> 91%%';
END $$;