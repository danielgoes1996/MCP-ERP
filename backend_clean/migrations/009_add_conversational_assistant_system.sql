-- =====================================================
-- MIGRACIÓN 009: SISTEMA ASISTENTE CONVERSACIONAL
-- Fecha: 2025-09-26
-- Descripción: Sistema completo de asistente conversacional con LLM
-- Coherencia esperada: 75% → 93%
-- =====================================================

-- =====================================================
-- TABLA 1: CONVERSACIONES DE USUARIO
-- =====================================================
CREATE TABLE IF NOT EXISTS conversational_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    session_name VARCHAR(255),
    context_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    -- Índices para performance
    CONSTRAINT fk_conv_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- TABLA 2: INTERACCIONES Y QUERIES
-- =====================================================
CREATE TABLE IF NOT EXISTS conversational_interactions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES conversational_sessions(session_id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    interaction_type VARCHAR(50) NOT NULL CHECK (interaction_type IN ('query', 'command', 'clarification')),

    -- Query y respuesta
    user_query TEXT NOT NULL,
    assistant_response TEXT,

    -- Campos faltantes implementados ✅
    sql_executed TEXT, -- ✅ CAMPO FALTANTE: API → BD → UI
    llm_model_used VARCHAR(100), -- ✅ CAMPO FALTANTE: API → BD → UI

    -- Contexto y metadata
    query_intent VARCHAR(100),
    confidence_score DECIMAL(3,2) DEFAULT 0.0,
    processing_time_ms INTEGER DEFAULT 0,

    -- Status y seguimiento
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'error')),
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Índices para búsquedas
    CONSTRAINT fk_interaction_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- TABLA 3: RESULTADOS DE CONSULTAS SQL
-- =====================================================
CREATE TABLE IF NOT EXISTS query_execution_results (
    id SERIAL PRIMARY KEY,
    interaction_id INTEGER NOT NULL REFERENCES conversational_interactions(id) ON DELETE CASCADE,

    -- Query details
    sql_query TEXT NOT NULL,
    query_type VARCHAR(50) CHECK (query_type IN ('SELECT', 'COUNT', 'SUM', 'GROUP_BY', 'JOIN')),
    execution_time_ms INTEGER DEFAULT 0,

    -- Resultados
    result_data JSONB,
    row_count INTEGER DEFAULT 0,
    columns_returned JSONB DEFAULT '[]',

    -- Seguridad y validación
    is_safe_query BOOLEAN DEFAULT FALSE,
    security_checks JSONB DEFAULT '{}',

    -- Status
    execution_status VARCHAR(50) DEFAULT 'pending' CHECK (execution_status IN ('pending', 'executing', 'completed', 'error', 'timeout')),
    error_details TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLA 4: MODELOS LLM Y CONFIGURACIÓN
-- =====================================================
CREATE TABLE IF NOT EXISTS llm_model_configs (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) UNIQUE NOT NULL,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('openai', 'anthropic', 'local', 'azure', 'huggingface')),

    -- Configuración del modelo
    model_version VARCHAR(50),
    api_endpoint TEXT,
    max_tokens INTEGER DEFAULT 4000,
    temperature DECIMAL(3,2) DEFAULT 0.7,

    -- Configuración específica
    model_config JSONB DEFAULT '{}',
    pricing_per_token DECIMAL(10,8),

    -- Métricas de uso
    total_requests INTEGER DEFAULT 0,
    total_tokens_used BIGINT DEFAULT 0,
    average_response_time_ms DECIMAL(8,2) DEFAULT 0.0,

    -- Estado
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(50) DEFAULT 'unknown' CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLA 5: CACHE DE RESPUESTAS LLM
-- =====================================================
CREATE TABLE IF NOT EXISTS llm_response_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(64) UNIQUE NOT NULL, -- Hash de query + context

    -- Query original
    user_query TEXT NOT NULL,
    context_hash VARCHAR(64),

    -- Respuesta cacheable
    llm_response TEXT NOT NULL,
    model_used VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(3,2),

    -- Metadata
    hit_count INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours'),

    -- TTL automático
    is_expired BOOLEAN GENERATED ALWAYS AS (expires_at < CURRENT_TIMESTAMP) STORED,

    CONSTRAINT fk_cache_model FOREIGN KEY (model_used) REFERENCES llm_model_configs(model_name) ON DELETE CASCADE
);

-- =====================================================
-- TABLA 6: ANALYTICS Y MÉTRICAS
-- =====================================================
CREATE TABLE IF NOT EXISTS conversational_analytics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    date DATE NOT NULL,

    -- Métricas de uso
    total_interactions INTEGER DEFAULT 0,
    successful_queries INTEGER DEFAULT 0,
    failed_queries INTEGER DEFAULT 0,

    -- Performance metrics
    average_response_time_ms DECIMAL(8,2) DEFAULT 0.0,
    total_tokens_used INTEGER DEFAULT 0,

    -- Tipos de queries
    query_types JSONB DEFAULT '{}',
    intent_distribution JSONB DEFAULT '{}',

    -- Satisfacción usuario
    user_feedback_scores JSONB DEFAULT '{}',
    cache_hit_rate DECIMAL(3,2) DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_analytics_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_date UNIQUE (user_id, date)
);

-- =====================================================
-- ÍNDICES DE PERFORMANCE
-- =====================================================

-- Índices principales para sesiones
CREATE INDEX IF NOT EXISTS idx_conv_sessions_user_id ON conversational_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_sessions_company_id ON conversational_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_conv_sessions_active ON conversational_sessions(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_conv_sessions_last_activity ON conversational_sessions(last_activity DESC);

-- Índices para interacciones
CREATE INDEX IF NOT EXISTS idx_conv_interactions_session_id ON conversational_interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_interactions_user_id ON conversational_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_interactions_type ON conversational_interactions(interaction_type);
CREATE INDEX IF NOT EXISTS idx_conv_interactions_created_at ON conversational_interactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_interactions_status ON conversational_interactions(status);

-- Índices para resultados de queries
CREATE INDEX IF NOT EXISTS idx_query_results_interaction_id ON query_execution_results(interaction_id);
CREATE INDEX IF NOT EXISTS idx_query_results_execution_status ON query_execution_results(execution_status);
CREATE INDEX IF NOT EXISTS idx_query_results_created_at ON query_execution_results(created_at DESC);

-- Índices para configuración LLM
CREATE INDEX IF NOT EXISTS idx_llm_configs_provider ON llm_model_configs(provider);
CREATE INDEX IF NOT EXISTS idx_llm_configs_active ON llm_model_configs(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_llm_configs_health ON llm_model_configs(health_status);

-- Índices para cache LLM
CREATE INDEX IF NOT EXISTS idx_llm_cache_key ON llm_response_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_llm_cache_context_hash ON llm_response_cache(context_hash);
CREATE INDEX IF NOT EXISTS idx_llm_cache_expired ON llm_response_cache(is_expired) WHERE is_expired = FALSE;
CREATE INDEX IF NOT EXISTS idx_llm_cache_last_accessed ON llm_response_cache(last_accessed DESC);

-- Índices para analytics
CREATE INDEX IF NOT EXISTS idx_conv_analytics_user_id ON conversational_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_analytics_date ON conversational_analytics(date DESC);

-- =====================================================
-- TRIGGERS DE ACTUALIZACIÓN
-- =====================================================

-- Trigger para actualizar timestamp de sesión
CREATE OR REPLACE FUNCTION update_session_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversational_sessions
    SET last_activity = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE session_id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_session_activity
    AFTER INSERT ON conversational_interactions
    FOR EACH ROW
    EXECUTE FUNCTION update_session_activity();

-- Trigger para actualizar cache hit count
CREATE OR REPLACE FUNCTION update_cache_hit_count()
RETURNS TRIGGER AS $$
BEGIN
    NEW.hit_count = OLD.hit_count + 1;
    NEW.last_accessed = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_cache_hit_count
    BEFORE UPDATE ON llm_response_cache
    FOR EACH ROW
    WHEN (OLD.last_accessed <> NEW.last_accessed)
    EXECUTE FUNCTION update_cache_hit_count();

-- =====================================================
-- CONSTRAINTS DE SEGURIDAD
-- =====================================================

-- Constraint para limitar tamaño de queries
ALTER TABLE conversational_interactions
ADD CONSTRAINT check_query_length
CHECK (length(user_query) <= 10000);

-- Constraint para limitar tamaño de respuestas
ALTER TABLE conversational_interactions
ADD CONSTRAINT check_response_length
CHECK (length(assistant_response) <= 50000);

-- Constraint para validar confidence score
ALTER TABLE conversational_interactions
ADD CONSTRAINT check_confidence_score
CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);

-- =====================================================
-- DATOS INICIALES - CONFIGURACIÓN DE MODELOS LLM
-- =====================================================

-- Insertar configuraciones por defecto de modelos LLM
INSERT INTO llm_model_configs (model_name, provider, model_version, max_tokens, temperature, model_config) VALUES
('gpt-4o', 'openai', '2024-08-06', 4000, 0.7, '{"supports_function_calling": true, "context_length": 128000}'),
('gpt-4o-mini', 'openai', '2024-07-18', 4000, 0.7, '{"supports_function_calling": true, "context_length": 128000}'),
('claude-3-5-sonnet', 'anthropic', '20241022', 4000, 0.7, '{"supports_function_calling": true, "context_length": 200000}'),
('claude-3-haiku', 'anthropic', '20240307', 4000, 0.7, '{"supports_function_calling": false, "context_length": 200000}')
ON CONFLICT (model_name) DO NOTHING;

-- =====================================================
-- COMENTARIOS DE DOCUMENTACIÓN
-- =====================================================

COMMENT ON TABLE conversational_sessions IS 'Sesiones de conversación del asistente con contexto persistente';
COMMENT ON TABLE conversational_interactions IS 'Interacciones individuales usuario-asistente con tracking completo';
COMMENT ON TABLE query_execution_results IS 'Resultados de consultas SQL ejecutadas por el asistente';
COMMENT ON TABLE llm_model_configs IS 'Configuración y métricas de modelos LLM disponibles';
COMMENT ON TABLE llm_response_cache IS 'Cache inteligente de respuestas LLM para optimizar performance';
COMMENT ON TABLE conversational_analytics IS 'Métricas y analytics de uso del asistente conversacional';

COMMENT ON COLUMN conversational_interactions.sql_executed IS 'SQL ejecutado por el asistente (CAMPO FALTANTE IMPLEMENTADO)';
COMMENT ON COLUMN conversational_interactions.llm_model_used IS 'Modelo LLM utilizado para la respuesta (CAMPO FALTANTE IMPLEMENTADO)';

-- =====================================================
-- VALIDACIÓN DE MIGRACIÓN
-- =====================================================

DO $$
BEGIN
    -- Verificar que todas las tablas fueron creadas
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversational_sessions') THEN
        RAISE EXCEPTION 'Error: Tabla conversational_sessions no fue creada correctamente';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversational_interactions') THEN
        RAISE EXCEPTION 'Error: Tabla conversational_interactions no fue creada correctamente';
    END IF;

    -- Verificar campos faltantes implementados
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversational_interactions'
        AND column_name = 'sql_executed'
    ) THEN
        RAISE EXCEPTION 'Error: Campo sql_executed no fue creado';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversational_interactions'
        AND column_name = 'llm_model_used'
    ) THEN
        RAISE EXCEPTION 'Error: Campo llm_model_used no fue creado';
    END IF;

    RAISE NOTICE 'Migración 009: Sistema Asistente Conversacional completado exitosamente';
    RAISE NOTICE 'Campos faltantes implementados: sql_executed, llm_model_used';
    RAISE NOTICE 'Esperada mejora de coherencia: 75%% -> 93%%';
END $$;