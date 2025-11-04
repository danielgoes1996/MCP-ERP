-- Migration 003: Add Missing Automation and System Fields
-- Based on AUDITORIA_MAESTRA_SISTEMA_MCP findings
-- Priority: MEDIUM - These fields support automation and monitoring features

-- Bank movements enhancements
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS decision TEXT;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS bank_metadata JSON;
ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS matching_confidence DECIMAL(3,2);

-- Create automation_sessions table if not exists
CREATE TABLE IF NOT EXISTS automation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    company_id INTEGER NOT NULL,
    state_data JSON,
    checkpoint_data JSON,
    recovery_metadata JSON,
    session_status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Create workers table if not exists
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    company_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    progress DECIMAL(3,2) DEFAULT 0.0,
    worker_metadata JSON,
    retry_policy JSON,
    retry_count INTEGER DEFAULT 0,
    result_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Create system_health table for monitoring
CREATE TABLE IF NOT EXISTS system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_name TEXT NOT NULL,
    health_status TEXT NOT NULL,
    automation_health JSON,
    performance_metrics JSON,
    error_count INTEGER DEFAULT 0,
    last_check DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

-- Create user preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_id INTEGER NOT NULL,
    preferences JSON,
    onboarding_step TEXT DEFAULT 'start',
    demo_preferences JSON,
    completion_rules JSON,
    field_priorities JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_automation_sessions_company ON automation_sessions(company_id);
CREATE INDEX IF NOT EXISTS idx_automation_sessions_status ON automation_sessions(session_status);
CREATE INDEX IF NOT EXISTS idx_workers_company ON workers(company_id);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_workers_task_type ON workers(task_type);
CREATE INDEX IF NOT EXISTS idx_system_health_component ON system_health(component_name);
CREATE INDEX IF NOT EXISTS idx_system_health_status ON system_health(health_status);
CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_company ON user_preferences(company_id);