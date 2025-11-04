-- Migration 005: Expense Actions Audit System
-- Punto 12: Acciones de Gastos - Audit Trail Implementation
-- Priority: HIGH - Sistema completo de auditoría para acciones

-- Tabla principal de auditoría de acciones
CREATE TABLE IF NOT EXISTS expense_action_audit (
    id SERIAL PRIMARY KEY,
    action_id VARCHAR(50) UNIQUE NOT NULL,
    action_type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL,

    -- Contexto del usuario
    user_id INTEGER NOT NULL,
    company_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(50) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    api_version VARCHAR(20),
    client_info JSONB,

    -- Datos de la acción
    target_expense_ids INTEGER[] NOT NULL,
    parameters JSONB DEFAULT '{}',
    snapshots JSONB DEFAULT '[]',

    -- Datos de rollback
    rollback_data JSONB,
    rollback_executed BOOLEAN DEFAULT FALSE,
    rollback_executed_at TIMESTAMP WITH TIME ZONE,
    rollback_executed_by INTEGER,

    -- Timing y performance
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    execution_time_ms INTEGER,

    -- Resultado
    affected_records INTEGER DEFAULT 0,
    error_message TEXT,

    -- Metadata adicional
    batch_id VARCHAR(50), -- Para agrupar operaciones relacionadas
    parent_action_id VARCHAR(50), -- Para acciones jerárquicas
    priority INTEGER DEFAULT 5, -- 1=high, 5=normal, 10=low

    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (rollback_executed_by) REFERENCES users(id)
);

-- Tabla para tracking de cambios individuales por campo
CREATE TABLE IF NOT EXISTS expense_field_changes (
    id SERIAL PRIMARY KEY,
    action_id VARCHAR(50) NOT NULL,
    expense_id INTEGER NOT NULL,
    field_name VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    data_type VARCHAR(20), -- 'string', 'number', 'boolean', 'json', 'date'
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (action_id) REFERENCES expense_action_audit(action_id) ON DELETE CASCADE,
    FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
);

-- Tabla para notificaciones de acciones
CREATE TABLE IF NOT EXISTS expense_action_notifications (
    id SERIAL PRIMARY KEY,
    action_id VARCHAR(50) NOT NULL,
    notification_type VARCHAR(30) NOT NULL, -- 'email', 'webhook', 'internal'
    recipient VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'sent', 'failed', 'skipped'
    subject VARCHAR(255),
    message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    FOREIGN KEY (action_id) REFERENCES expense_action_audit(action_id) ON DELETE CASCADE
);

-- Tabla para configuración de reglas de validación
CREATE TABLE IF NOT EXISTS expense_action_rules (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(30) NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    rule_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL,

    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Índices para performance optimizado
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_audit_company_date
ON expense_action_audit(company_id, started_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_audit_user_date
ON expense_action_audit(user_id, started_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_audit_status
ON expense_action_audit(status) WHERE status != 'completed';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_audit_action_type
ON expense_action_audit(action_type, started_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_audit_target_expenses
ON expense_action_audit USING gin(target_expense_ids);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_audit_execution_time
ON expense_action_audit(execution_time_ms DESC) WHERE execution_time_ms IS NOT NULL;

-- Índices para field changes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_field_changes_expense_date
ON expense_field_changes(expense_id, changed_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_field_changes_action
ON expense_field_changes(action_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_field_changes_field_name
ON expense_field_changes(field_name, changed_at DESC);

-- Índices para notificaciones
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_notifications_status
ON expense_action_notifications(status) WHERE status != 'sent';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_notifications_type
ON expense_action_notifications(notification_type, status);

-- Índices para reglas
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_action_rules_company_type
ON expense_action_rules(company_id, action_type) WHERE is_active = TRUE;

-- Función para limpiar auditoría antigua (mantener solo últimos 6 meses)
CREATE OR REPLACE FUNCTION cleanup_old_audit_records()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Eliminar registros más antiguos de 6 meses
    DELETE FROM expense_action_audit
    WHERE started_at < CURRENT_TIMESTAMP - INTERVAL '6 months'
    AND status IN ('completed', 'failed');

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Log la limpieza
    INSERT INTO system_health (component_name, health_status, metadata)
    VALUES ('audit_cleanup', 'healthy',
            json_build_object(
                'deleted_records', deleted_count,
                'cleanup_date', CURRENT_TIMESTAMP
            ));

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Función para calcular estadísticas de performance
CREATE OR REPLACE FUNCTION get_action_performance_stats(
    p_company_id VARCHAR(50),
    p_days_back INTEGER DEFAULT 30
)
RETURNS TABLE (
    action_type VARCHAR(30),
    total_actions BIGINT,
    avg_execution_time_ms NUMERIC,
    max_execution_time_ms INTEGER,
    success_rate NUMERIC,
    total_expenses_affected BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        eaa.action_type,
        COUNT(*) as total_actions,
        AVG(eaa.execution_time_ms) as avg_execution_time_ms,
        MAX(eaa.execution_time_ms) as max_execution_time_ms,
        ROUND(
            COUNT(*) FILTER (WHERE eaa.status = 'completed')::numeric /
            COUNT(*)::numeric * 100, 2
        ) as success_rate,
        SUM(eaa.affected_records) as total_expenses_affected
    FROM expense_action_audit eaa
    WHERE eaa.company_id = p_company_id
    AND eaa.started_at >= CURRENT_TIMESTAMP - (p_days_back || ' days')::INTERVAL
    GROUP BY eaa.action_type
    ORDER BY total_actions DESC;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar updated_at en expense_action_rules
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_expense_action_rules_modtime
BEFORE UPDATE ON expense_action_rules
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Vista para estadísticas rápidas de auditoría
CREATE OR REPLACE VIEW expense_action_audit_summary AS
SELECT
    company_id,
    action_type,
    status,
    DATE(started_at) as action_date,
    COUNT(*) as action_count,
    SUM(affected_records) as total_expenses_affected,
    AVG(execution_time_ms) as avg_execution_time_ms,
    MAX(execution_time_ms) as max_execution_time_ms,
    MIN(execution_time_ms) as min_execution_time_ms
FROM expense_action_audit
WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '90 days'
GROUP BY company_id, action_type, status, DATE(started_at)
ORDER BY action_date DESC, company_id, action_type;

-- Datos iniciales: reglas por defecto
INSERT INTO expense_action_rules (company_id, action_type, rule_name, rule_config, created_by)
VALUES
('default', 'bulk_update', 'Max Batch Size', '{"max_records": 1000, "warning_threshold": 500}', 1),
('default', 'mark_invoiced', 'Require Invoice Data', '{"require_uuid": true, "require_amount_match": true}', 1),
('default', 'delete', 'Prevent Recent Deletion', '{"min_age_days": 1, "require_approval": true}', 1),
('default', 'bulk_update', 'Time Limit', '{"max_execution_time_ms": 300000}', 1)
ON CONFLICT DO NOTHING;

-- Actualizar schema_migrations
INSERT INTO schema_migrations (version, description)
VALUES ('005', 'Expense actions audit system with rollback and notifications')
ON CONFLICT (version) DO NOTHING;