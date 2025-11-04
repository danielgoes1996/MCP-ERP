-- Migration 013: Robust Automation Engine System
-- Implementa sistema de automatización robusta con risk assessment y auto-recovery
-- Resuelve gaps: performance_metrics, recovery_actions, automation_health

BEGIN;

-- Tabla principal para sesiones de automatización robusta
CREATE TABLE IF NOT EXISTS robust_automation_sessions (
    id TEXT PRIMARY KEY DEFAULT ('ras_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,
    user_id TEXT,

    -- Información de automatización
    automation_name TEXT NOT NULL,
    automation_type TEXT NOT NULL CHECK (automation_type IN ('web_scraping', 'data_processing', 'workflow', 'integration', 'monitoring')),
    target_system TEXT,
    automation_config JSONB DEFAULT '{}',

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    performance_metrics JSONB DEFAULT '{}',  -- ✅ CAMPO FALTANTE: Métricas de performance
    recovery_actions JSONB DEFAULT '[]',    -- ✅ CAMPO FALTANTE: Acciones de recuperación
    automation_health JSONB DEFAULT '{}',   -- ✅ CAMPO FALTANTE: Estado de salud

    -- Risk Assessment
    risk_level TEXT NOT NULL DEFAULT 'medium' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    risk_factors JSONB DEFAULT '{}',
    risk_score DECIMAL(5,2) DEFAULT 50.00,

    -- Fallback y Recovery
    fallback_used BOOLEAN DEFAULT FALSE,
    fallback_strategy JSONB DEFAULT '{}',
    max_retry_attempts INTEGER DEFAULT 3,
    current_retry_count INTEGER DEFAULT 0,

    -- Estado y timing
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'paused', 'cancelled')),
    execution_mode TEXT DEFAULT 'normal' CHECK (execution_mode IN ('normal', 'safe_mode', 'recovery_mode')),

    -- Performance tracking
    execution_time_ms INTEGER,
    success_rate DECIMAL(5,2) DEFAULT 100.00,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Tabla para pasos de automatización robusta
CREATE TABLE IF NOT EXISTS robust_automation_steps (
    id TEXT PRIMARY KEY DEFAULT ('rast_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,

    -- Configuración del step
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL CHECK (step_type IN ('action', 'validation', 'wait', 'decision', 'recovery')),
    step_config JSONB DEFAULT '{}',

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    performance_metrics JSONB DEFAULT '{}',  -- ✅ CAMPO FALTANTE: Métricas por step
    recovery_actions JSONB DEFAULT '[]',    -- ✅ CAMPO FALTANTE: Acciones por step

    -- Risk y Health por step
    step_risk_level TEXT DEFAULT 'medium',
    step_health_score DECIMAL(5,2) DEFAULT 100.00,

    -- Execution tracking
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped', 'retrying')),
    execution_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Input/Output
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_details TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES robust_automation_sessions(id) ON DELETE CASCADE,
    UNIQUE(session_id, step_number)
);

-- Tabla para risk assessment y monitoring
CREATE TABLE IF NOT EXISTS robust_automation_risks (
    id TEXT PRIMARY KEY DEFAULT ('rar_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,

    -- Risk identification
    risk_category TEXT NOT NULL CHECK (risk_category IN ('technical', 'business', 'security', 'compliance', 'performance')),
    risk_description TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    risk_probability DECIMAL(5,2) DEFAULT 50.00,
    risk_impact DECIMAL(5,2) DEFAULT 50.00,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    performance_metrics JSONB DEFAULT '{}',  -- ✅ CAMPO FALTANTE: Métricas de riesgo

    -- Mitigation strategies
    mitigation_strategies JSONB DEFAULT '[]',
    mitigation_applied BOOLEAN DEFAULT FALSE,
    mitigation_effectiveness DECIMAL(5,2),

    -- Monitoring
    is_active BOOLEAN DEFAULT TRUE,
    detection_method TEXT,
    last_assessment TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES robust_automation_sessions(id) ON DELETE CASCADE
);

-- Tabla para recovery actions y strategies
CREATE TABLE IF NOT EXISTS robust_automation_recovery (
    id TEXT PRIMARY KEY DEFAULT ('rarec_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,
    step_id TEXT,

    -- Recovery configuration
    recovery_trigger TEXT NOT NULL CHECK (recovery_trigger IN ('error', 'timeout', 'health_degradation', 'manual', 'scheduled')),
    recovery_type TEXT NOT NULL CHECK (recovery_type IN ('retry', 'fallback', 'rollback', 'restart', 'safe_mode')),

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    recovery_actions JSONB DEFAULT '[]',     -- ✅ CAMPO FALTANTE: Acciones específicas
    performance_metrics JSONB DEFAULT '{}', -- ✅ CAMPO FALTANTE: Métricas de recovery

    -- Recovery execution
    recovery_config JSONB DEFAULT '{}',
    execution_order INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'executing', 'completed', 'failed')),

    -- Results tracking
    success BOOLEAN,
    execution_time_ms INTEGER,
    recovery_output JSONB DEFAULT '{}',
    error_details TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES robust_automation_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES robust_automation_steps(id) ON DELETE CASCADE
);

-- Tabla para health monitoring
CREATE TABLE IF NOT EXISTS robust_automation_health (
    id TEXT PRIMARY KEY DEFAULT ('rah_' || lower(hex(randomblob(16)))),
    session_id TEXT NOT NULL,

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    automation_health JSONB DEFAULT '{}',    -- ✅ CAMPO FALTANTE: Estado de salud completo
    performance_metrics JSONB DEFAULT '{}', -- ✅ CAMPO FALTANTE: Métricas de salud

    -- Health metrics
    overall_health_score DECIMAL(5,2) DEFAULT 100.00,
    cpu_usage_percent DECIMAL(5,2) DEFAULT 0.00,
    memory_usage_mb DECIMAL(8,2) DEFAULT 0.00,
    network_latency_ms INTEGER DEFAULT 0,
    error_rate DECIMAL(5,2) DEFAULT 0.00,

    -- Health status
    health_status TEXT DEFAULT 'healthy' CHECK (health_status IN ('healthy', 'warning', 'critical', 'unknown')),
    last_health_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    health_trend TEXT DEFAULT 'stable' CHECK (health_trend IN ('improving', 'stable', 'degrading')),

    -- Alerts and notifications
    alert_level TEXT DEFAULT 'none' CHECK (alert_level IN ('none', 'info', 'warning', 'critical')),
    alert_message TEXT,
    notification_sent BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES robust_automation_sessions(id) ON DELETE CASCADE
);

-- Tabla para performance analytics
CREATE TABLE IF NOT EXISTS robust_automation_performance (
    id TEXT PRIMARY KEY DEFAULT ('rap_' || lower(hex(randomblob(16)))),
    company_id TEXT NOT NULL,

    -- Performance period
    measurement_date DATE NOT NULL,
    measurement_hour INTEGER CHECK (measurement_hour >= 0 AND measurement_hour <= 23),

    -- ✅ CAMPOS CRÍTICOS FALTANTES
    performance_metrics JSONB DEFAULT '{}', -- ✅ CAMPO FALTANTE: Métricas agregadas

    -- Aggregate metrics
    total_sessions INTEGER DEFAULT 0,
    successful_sessions INTEGER DEFAULT 0,
    failed_sessions INTEGER DEFAULT 0,
    avg_execution_time_ms INTEGER DEFAULT 0,
    avg_success_rate DECIMAL(5,2) DEFAULT 100.00,

    -- Performance indicators
    avg_cpu_usage DECIMAL(5,2) DEFAULT 0.00,
    avg_memory_usage DECIMAL(8,2) DEFAULT 0.00,
    avg_error_rate DECIMAL(5,2) DEFAULT 0.00,
    total_recovery_actions INTEGER DEFAULT 0,

    -- Risk metrics
    high_risk_sessions INTEGER DEFAULT 0,
    critical_incidents INTEGER DEFAULT 0,
    avg_risk_score DECIMAL(5,2) DEFAULT 50.00,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    UNIQUE(company_id, measurement_date, measurement_hour)
);

-- Índices optimizados para performance
CREATE INDEX IF NOT EXISTS idx_robust_automation_sessions_company ON robust_automation_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_robust_automation_sessions_status ON robust_automation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_robust_automation_sessions_risk ON robust_automation_sessions(risk_level);
CREATE INDEX IF NOT EXISTS idx_robust_automation_sessions_created ON robust_automation_sessions(created_at);

CREATE INDEX IF NOT EXISTS idx_robust_automation_steps_session ON robust_automation_steps(session_id);
CREATE INDEX IF NOT EXISTS idx_robust_automation_steps_status ON robust_automation_steps(status);
CREATE INDEX IF NOT EXISTS idx_robust_automation_steps_type ON robust_automation_steps(step_type);

CREATE INDEX IF NOT EXISTS idx_robust_automation_risks_session ON robust_automation_risks(session_id);
CREATE INDEX IF NOT EXISTS idx_robust_automation_risks_level ON robust_automation_risks(risk_level);
CREATE INDEX IF NOT EXISTS idx_robust_automation_risks_active ON robust_automation_risks(is_active);

CREATE INDEX IF NOT EXISTS idx_robust_automation_recovery_session ON robust_automation_recovery(session_id);
CREATE INDEX IF NOT EXISTS idx_robust_automation_recovery_trigger ON robust_automation_recovery(recovery_trigger);
CREATE INDEX IF NOT EXISTS idx_robust_automation_recovery_status ON robust_automation_recovery(status);

CREATE INDEX IF NOT EXISTS idx_robust_automation_health_session ON robust_automation_health(session_id);
CREATE INDEX IF NOT EXISTS idx_robust_automation_health_status ON robust_automation_health(health_status);
CREATE INDEX IF NOT EXISTS idx_robust_automation_health_check ON robust_automation_health(last_health_check);

CREATE INDEX IF NOT EXISTS idx_robust_automation_performance_company ON robust_automation_performance(company_id);
CREATE INDEX IF NOT EXISTS idx_robust_automation_performance_date ON robust_automation_performance(measurement_date);

-- Triggers para mantener updated_at actualizado
CREATE TRIGGER IF NOT EXISTS update_robust_automation_sessions_updated_at
    AFTER UPDATE ON robust_automation_sessions
    FOR EACH ROW
    BEGIN
        UPDATE robust_automation_sessions
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_robust_automation_steps_updated_at
    AFTER UPDATE ON robust_automation_steps
    FOR EACH ROW
    BEGIN
        UPDATE robust_automation_steps
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_robust_automation_health_updated_at
    AFTER UPDATE ON robust_automation_health
    FOR EACH ROW
    BEGIN
        UPDATE robust_automation_health
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;

-- Trigger para actualizar health score cuando cambia el estado
CREATE TRIGGER IF NOT EXISTS update_automation_health_on_status_change
    AFTER UPDATE OF status ON robust_automation_sessions
    FOR EACH ROW
    WHEN NEW.status != OLD.status
    BEGIN
        INSERT OR REPLACE INTO robust_automation_health (
            session_id,
            automation_health,
            performance_metrics,
            overall_health_score,
            health_status,
            last_health_check
        )
        VALUES (
            NEW.id,
            json_object(
                'session_status', NEW.status,
                'risk_level', NEW.risk_level,
                'success_rate', NEW.success_rate,
                'error_count', NEW.error_count,
                'fallback_used', NEW.fallback_used,
                'execution_mode', NEW.execution_mode,
                'last_updated', CURRENT_TIMESTAMP
            ),
            json_object(
                'execution_time_ms', NEW.execution_time_ms,
                'retry_count', NEW.current_retry_count,
                'max_retries', NEW.max_retry_attempts,
                'performance_score', CASE
                    WHEN NEW.execution_time_ms IS NULL THEN NULL
                    WHEN NEW.execution_time_ms < 1000 THEN 100.0
                    WHEN NEW.execution_time_ms < 5000 THEN 80.0
                    WHEN NEW.execution_time_ms < 10000 THEN 60.0
                    ELSE 40.0
                END
            ),
            CASE
                WHEN NEW.status = 'completed' THEN 100.0
                WHEN NEW.status = 'running' THEN 80.0
                WHEN NEW.status = 'failed' THEN 20.0
                WHEN NEW.status = 'paused' THEN 60.0
                ELSE 70.0
            END,
            CASE
                WHEN NEW.status = 'failed' OR NEW.error_count > 5 THEN 'critical'
                WHEN NEW.status = 'paused' OR NEW.error_count > 2 THEN 'warning'
                WHEN NEW.status = 'completed' OR NEW.status = 'running' THEN 'healthy'
                ELSE 'unknown'
            END,
            CURRENT_TIMESTAMP
        );
    END;

-- Trigger para actualizar métricas de performance agregadas
CREATE TRIGGER IF NOT EXISTS update_robust_automation_performance_on_completion
    AFTER UPDATE OF status ON robust_automation_sessions
    FOR EACH ROW
    WHEN NEW.status = 'completed' AND OLD.status != 'completed'
    BEGIN
        INSERT OR REPLACE INTO robust_automation_performance (
            company_id,
            measurement_date,
            measurement_hour,
            performance_metrics,
            total_sessions,
            successful_sessions,
            avg_execution_time_ms,
            avg_success_rate
        )
        SELECT
            NEW.company_id,
            DATE(NEW.completed_at),
            CAST(strftime('%H', NEW.completed_at) AS INTEGER),
            json_object(
                'last_updated', CURRENT_TIMESTAMP,
                'session_id', NEW.id,
                'automation_type', NEW.automation_type,
                'risk_level', NEW.risk_level,
                'execution_time_ms', NEW.execution_time_ms,
                'success_rate', NEW.success_rate,
                'fallback_used', NEW.fallback_used,
                'recovery_count', (
                    SELECT COUNT(*) FROM robust_automation_recovery
                    WHERE session_id = NEW.id AND success = 1
                )
            ),
            COALESCE(rap.total_sessions, 0) + 1,
            COALESCE(rap.successful_sessions, 0) + 1,
            CASE
                WHEN COALESCE(rap.total_sessions, 0) = 0 THEN NEW.execution_time_ms
                ELSE (COALESCE(rap.avg_execution_time_ms, 0) * COALESCE(rap.total_sessions, 0) + NEW.execution_time_ms) / (COALESCE(rap.total_sessions, 0) + 1)
            END,
            CASE
                WHEN COALESCE(rap.total_sessions, 0) = 0 THEN NEW.success_rate
                ELSE (COALESCE(rap.avg_success_rate, 0) * COALESCE(rap.total_sessions, 0) + NEW.success_rate) / (COALESCE(rap.total_sessions, 0) + 1)
            END
        FROM (
            SELECT * FROM robust_automation_performance
            WHERE company_id = NEW.company_id
              AND measurement_date = DATE(NEW.completed_at)
              AND measurement_hour = CAST(strftime('%H', NEW.completed_at) AS INTEGER)
        ) rap;
    END;

COMMIT;

-- Verificación de la migración
SELECT 'Migration 013: Robust Automation Engine System completed successfully' as status;