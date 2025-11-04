-- Migration 012: Hybrid Processor System
-- Implementa sistema de procesamiento híbrido multi-modal con quality scoring
-- Resuelve gaps: ocr_confidence, processing_metrics, engine_performance

BEGIN;

-- Tabla principal para sesiones de procesamiento híbrido
CREATE TABLE IF NOT EXISTS hybrid_processor_sessions (
    id TEXT PRIMARY KEY DEFAULT ('hps_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,
    user_id TEXT,

    -- Información de input
    input_data JSONB NOT NULL,
    input_type TEXT NOT NULL CHECK (input_type IN ('document', 'image', 'text', 'audio', 'mixed')),
    source_url TEXT,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    ocr_confidence DECIMAL(5,2) DEFAULT 0.00, -- ✅ CAMPO FALTANTE: Confianza OCR promedio
    processing_metrics JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Métricas detalladas

    -- Engine selection y performance
    processor_used TEXT NOT NULL DEFAULT 'auto',
    quality_score DECIMAL(5,2) DEFAULT 0.00,
    engine_performance JSONB DEFAULT '{}',

    -- Configuración de procesamiento
    processing_config JSONB DEFAULT '{}',
    fallback_engines JSONB DEFAULT '[]',
    max_retries INTEGER DEFAULT 3,

    -- Estado y resultados
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'timeout')),
    result_data JSONB DEFAULT '{}',
    error_details TEXT,

    -- Timing y performance
    processing_time_ms INTEGER,
    queue_time_ms INTEGER,
    total_time_ms INTEGER,

    -- Metadatos de tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Tabla para steps individuales de procesamiento
CREATE TABLE IF NOT EXISTS hybrid_processor_steps (
    id TEXT PRIMARY KEY DEFAULT ('hpst_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,

    -- Configuración del step
    step_type TEXT NOT NULL CHECK (step_type IN ('ocr', 'classification', 'extraction', 'validation', 'enhancement')),
    engine_name TEXT NOT NULL,
    engine_config JSONB DEFAULT '{}',

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    ocr_confidence DECIMAL(5,2) DEFAULT 0.00, -- ✅ CAMPO FALTANTE: Confianza por step
    processing_metrics JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Métricas por step

    -- Input/Output del step
    input_data JSONB NOT NULL,
    output_data JSONB DEFAULT '{}',
    quality_score DECIMAL(5,2) DEFAULT 0.00,

    -- Estado y timing
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
    processing_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,

    -- Error handling
    error_details TEXT,
    fallback_used BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES hybrid_processor_sessions(id) ON DELETE CASCADE,
    UNIQUE(session_id, step_number)
);

-- Tabla para engines disponibles y su configuración
CREATE TABLE IF NOT EXISTS hybrid_processor_engines (
    id TEXT PRIMARY KEY DEFAULT ('hpe_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,

    -- Información del engine
    engine_name TEXT NOT NULL,
    engine_type TEXT NOT NULL CHECK (engine_type IN ('ocr', 'nlp', 'classification', 'extraction', 'validation')),
    engine_version TEXT,

    -- Configuración
    engine_config JSONB DEFAULT '{}',
    capabilities JSONB DEFAULT '[]',
    supported_formats JSONB DEFAULT '[]',

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    processing_metrics JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Métricas históricas

    -- Performance tracking
    avg_processing_time_ms INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 100.00,
    avg_quality_score DECIMAL(5,2) DEFAULT 0.00,
    usage_count INTEGER DEFAULT 0,

    -- Estado del engine
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 50,
    max_concurrent_jobs INTEGER DEFAULT 5,

    -- Health check
    last_health_check TIMESTAMP,
    health_status TEXT DEFAULT 'unknown' CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, engine_name, engine_type)
);

-- Tabla para métricas y analytics
CREATE TABLE IF NOT EXISTS hybrid_processor_metrics (
    id TEXT PRIMARY KEY DEFAULT ('hpm_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,

    -- Período de métricas
    metric_date DATE NOT NULL,
    metric_hour INTEGER CHECK (metric_hour >= 0 AND metric_hour <= 23),

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    processing_metrics JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Métricas agregadas

    -- Métricas de volumen
    total_sessions INTEGER DEFAULT 0,
    successful_sessions INTEGER DEFAULT 0,
    failed_sessions INTEGER DEFAULT 0,

    -- Métricas de calidad
    avg_ocr_confidence DECIMAL(5,2) DEFAULT 0.00,
    avg_quality_score DECIMAL(5,2) DEFAULT 0.00,
    avg_processing_time_ms INTEGER DEFAULT 0,

    -- Métricas por engine
    engine_usage JSONB DEFAULT '{}',
    engine_performance JSONB DEFAULT '{}',

    -- Métricas de error
    error_rate DECIMAL(5,2) DEFAULT 0.00,
    common_errors JSONB DEFAULT '[]',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, metric_date, metric_hour)
);

-- Tabla para resultados y outputs
CREATE TABLE IF NOT EXISTS hybrid_processor_results (
    id TEXT PRIMARY KEY DEFAULT ('hpr_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,

    -- Datos del resultado
    result_type TEXT NOT NULL CHECK (result_type IN ('text', 'json', 'xml', 'binary', 'structured')),
    result_data JSONB NOT NULL,
    confidence_score DECIMAL(5,2) DEFAULT 0.00,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    ocr_confidence DECIMAL(5,2) DEFAULT 0.00, -- ✅ CAMPO FALTANTE: Confianza final OCR
    processing_metrics JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Métricas de resultado

    -- Metadatos de calidad
    quality_checks JSONB DEFAULT '{}',
    validation_results JSONB DEFAULT '{}',
    improvement_suggestions JSONB DEFAULT '[]',

    -- Archivos asociados
    output_files JSONB DEFAULT '[]',
    preview_data JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES hybrid_processor_sessions(id) ON DELETE CASCADE
);

-- Tabla para configuraciones de quality scoring
CREATE TABLE IF NOT EXISTS hybrid_processor_quality_configs (
    id TEXT PRIMARY KEY DEFAULT ('hpqc_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,

    -- Configuración específica
    config_name TEXT NOT NULL,
    input_type TEXT NOT NULL,

    -- Reglas de scoring
    scoring_rules JSONB DEFAULT '{}',
    weight_config JSONB DEFAULT '{}',
    threshold_config JSONB DEFAULT '{}',

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    processing_metrics JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Métricas de config

    -- Configuración avanzada
    fallback_strategy JSONB DEFAULT '{}',
    quality_targets JSONB DEFAULT '{}',

    -- Estado
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, config_name, input_type)
);

-- Índices optimizados para performance
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_sessions_company ON hybrid_processor_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_sessions_status ON hybrid_processor_sessions(status);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_sessions_created ON hybrid_processor_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_sessions_quality ON hybrid_processor_sessions(quality_score);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_sessions_ocr_confidence ON hybrid_processor_sessions(ocr_confidence); -- ✅ ÍNDICE PARA CAMPO FALTANTE

CREATE INDEX IF NOT EXISTS idx_hybrid_processor_steps_session ON hybrid_processor_steps(session_id);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_steps_type ON hybrid_processor_steps(step_type);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_steps_status ON hybrid_processor_steps(status);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_steps_ocr_confidence ON hybrid_processor_steps(ocr_confidence); -- ✅ ÍNDICE PARA CAMPO FALTANTE

CREATE INDEX IF NOT EXISTS idx_hybrid_processor_engines_company ON hybrid_processor_engines(company_id);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_engines_type ON hybrid_processor_engines(engine_type);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_engines_active ON hybrid_processor_engines(is_active);

CREATE INDEX IF NOT EXISTS idx_hybrid_processor_metrics_company ON hybrid_processor_metrics(company_id);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_metrics_date ON hybrid_processor_metrics(metric_date);

CREATE INDEX IF NOT EXISTS idx_hybrid_processor_results_session ON hybrid_processor_results(session_id);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_results_confidence ON hybrid_processor_results(confidence_score);

CREATE INDEX IF NOT EXISTS idx_hybrid_processor_quality_configs_company ON hybrid_processor_quality_configs(company_id);
CREATE INDEX IF NOT EXISTS idx_hybrid_processor_quality_configs_active ON hybrid_processor_quality_configs(is_active);

-- Triggers para mantener updated_at actualizado
CREATE TRIGGER IF NOT EXISTS update_hybrid_processor_sessions_updated_at
    AFTER UPDATE ON hybrid_processor_sessions
    FOR EACH ROW
    BEGIN
        UPDATE hybrid_processor_sessions
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_hybrid_processor_steps_updated_at
    AFTER UPDATE ON hybrid_processor_steps
    FOR EACH ROW
    BEGIN
        UPDATE hybrid_processor_steps
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_hybrid_processor_engines_updated_at
    AFTER UPDATE ON hybrid_processor_engines
    FOR EACH ROW
    BEGIN
        UPDATE hybrid_processor_engines
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_hybrid_processor_quality_configs_updated_at
    AFTER UPDATE ON hybrid_processor_quality_configs
    FOR EACH ROW
    BEGIN
        UPDATE hybrid_processor_quality_configs
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

-- Trigger para actualizar métricas cuando se completa una sesión
CREATE TRIGGER IF NOT EXISTS update_hybrid_processor_metrics_on_completion
    AFTER UPDATE OF status ON hybrid_processor_sessions
    FOR EACH ROW
    WHEN NEW.status = 'completed' AND OLD.status != 'completed'
    BEGIN
        INSERT OR REPLACE INTO hybrid_processor_metrics (
            company_id,
            metric_date,
            metric_hour,
            total_sessions,
            successful_sessions,
            avg_ocr_confidence,
            avg_quality_score,
            avg_processing_time_ms,
            processing_metrics
        )
        SELECT
            NEW.company_id,
            DATE(NEW.completed_at),
            CAST(strftime('%H', NEW.completed_at) AS INTEGER),
            COALESCE(hpm.total_sessions, 0) + 1,
            COALESCE(hpm.successful_sessions, 0) + 1,
            CASE
                WHEN COALESCE(hpm.total_sessions, 0) = 0 THEN NEW.ocr_confidence
                ELSE (COALESCE(hpm.avg_ocr_confidence, 0) * COALESCE(hpm.total_sessions, 0) + NEW.ocr_confidence) / (COALESCE(hpm.total_sessions, 0) + 1)
            END,
            CASE
                WHEN COALESCE(hpm.total_sessions, 0) = 0 THEN NEW.quality_score
                ELSE (COALESCE(hpm.avg_quality_score, 0) * COALESCE(hpm.total_sessions, 0) + NEW.quality_score) / (COALESCE(hpm.total_sessions, 0) + 1)
            END,
            CASE
                WHEN COALESCE(hpm.total_sessions, 0) = 0 THEN NEW.processing_time_ms
                ELSE (COALESCE(hpm.avg_processing_time_ms, 0) * COALESCE(hpm.total_sessions, 0) + NEW.processing_time_ms) / (COALESCE(hpm.total_sessions, 0) + 1)
            END,
            json_object(
                'last_updated', CURRENT_TIMESTAMP,
                'session_id', NEW.id,
                'processor_used', NEW.processor_used,
                'processing_time_ms', NEW.processing_time_ms,
                'ocr_confidence', NEW.ocr_confidence,
                'quality_score', NEW.quality_score
            )
        FROM (
            SELECT * FROM hybrid_processor_metrics
            WHERE company_id = NEW.company_id
              AND metric_date = DATE(NEW.completed_at)
              AND metric_hour = CAST(strftime('%H', NEW.completed_at) AS INTEGER)
        ) hpm;
    END;

COMMIT;

-- Verificación de la migración
SELECT 'Migration 012: Hybrid Processor System completed successfully' as status;