-- Optimización de Performance DB - Mitigación de Riesgos
-- Previene joins pesados y queries lentas

-- 1. ÍNDICES CRÍTICOS PARA PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_automation_jobs_performance ON automation_jobs(
    company_id, estado, priority, created_at
) WHERE estado IN ('pendiente', 'en_progreso');

CREATE INDEX IF NOT EXISTS idx_automation_logs_fast_lookup ON automation_logs(
    job_id, timestamp, level
);

CREATE INDEX IF NOT EXISTS idx_tickets_recent_activity ON tickets(
    company_id, estado, created_at DESC
) WHERE created_at > datetime('now', '-30 days');

-- 2. PARTITIONING TEMPORAL (SQLite limitado, pero preparamos estructura)
-- Para futuro MySQL/PostgreSQL
CREATE TABLE IF NOT EXISTS automation_logs_archive AS
SELECT * FROM automation_logs WHERE 1=0;

-- 3. CONSTRAINTS PARA INTEGRIDAD
-- Prevenir datos inconsistentes
ALTER TABLE automation_jobs ADD CONSTRAINT chk_valid_estado
CHECK (estado IN ('pendiente', 'en_progreso', 'completado', 'fallido', 'pausado', 'cancelado'));

ALTER TABLE automation_jobs ADD CONSTRAINT chk_valid_priority
CHECK (priority IN ('baja', 'normal', 'alta', 'urgente'));

-- 4. TRIGGERS PARA AUDIT TRAIL
CREATE TRIGGER IF NOT EXISTS audit_job_status_changes
AFTER UPDATE OF estado ON automation_jobs
WHEN OLD.estado != NEW.estado
BEGIN
    INSERT INTO automation_logs (
        job_id, session_id, level, category, message, timestamp, company_id
    ) VALUES (
        NEW.id,
        COALESCE(NEW.session_id, 'system'),
        'info',
        'status_change',
        'Status changed from ' || OLD.estado || ' to ' || NEW.estado,
        datetime('now'),
        NEW.company_id
    );
END;

-- 5. CLEANUP AUTOMÁTICO (prevenir crecimiento descontrolado)
-- Jobs completados hace más de 90 días
CREATE TRIGGER IF NOT EXISTS cleanup_old_jobs
AFTER INSERT ON automation_jobs
WHEN (SELECT COUNT(*) FROM automation_jobs) > 10000
BEGIN
    DELETE FROM automation_jobs
    WHERE estado = 'completado'
    AND completed_at < datetime('now', '-90 days')
    LIMIT 100;
END;

-- 6. QUERY OPTIMIZATION VIEWS
-- Pre-calculadas para dashboards
CREATE VIEW IF NOT EXISTS vw_job_stats_today AS
SELECT
    company_id,
    COUNT(*) as total_jobs,
    COUNT(CASE WHEN estado = 'completado' THEN 1 END) as completed,
    COUNT(CASE WHEN estado = 'fallido' THEN 1 END) as failed,
    AVG(CASE
        WHEN completed_at IS NOT NULL AND started_at IS NOT NULL
        THEN (julianday(completed_at) - julianday(started_at)) * 86400000
    END) as avg_duration_ms
FROM automation_jobs
WHERE date(created_at) = date('now')
GROUP BY company_id;

-- 7. MIGRATION SAFETY
-- Rollback para cada cambio crítico
CREATE TABLE IF NOT EXISTS migration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_name TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    rollback_sql TEXT,
    checksum TEXT
);

INSERT INTO migration_log (migration_name, applied_at, rollback_sql, checksum)
VALUES (
    'db_performance_optimization',
    datetime('now'),
    'DROP INDEX idx_automation_jobs_performance; DROP INDEX idx_automation_logs_fast_lookup;',
    'perf_opt_v1'
);