-- Migration 009: Automation Engine v2 - Core Tables
-- Created: 2024-09-21
-- Description: Add automation engine tables for robust web automation
-- Breaking Changes: None (pure addition)
-- Rollback Safe: Yes (safe to rollback within 24h)

-- ===================================================================
-- UPGRADE SECTION
-- ===================================================================

-- Note: Migration record will be inserted at the end

-- 1. automation_jobs (core table)
CREATE TABLE automation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Relations (validated FKs)
    ticket_id INTEGER NOT NULL,
    merchant_id INTEGER,
    user_id INTEGER,

    -- State management
    estado TEXT NOT NULL DEFAULT 'pendiente',
    automation_type TEXT NOT NULL DEFAULT 'selenium',

    -- Priority and retry logic
    priority INTEGER DEFAULT 5,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Configuration (JSON fields)
    config TEXT, -- JSON
    result TEXT, -- JSON
    error_details TEXT, -- JSON

    -- Progress tracking
    current_step TEXT,
    progress_percentage INTEGER DEFAULT 0,

    -- Timing
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    estimated_completion TEXT,

    -- Traceability
    session_id TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',

    -- Automation metadata
    selenium_session_id TEXT,
    captcha_attempts INTEGER DEFAULT 0,
    ocr_confidence REAL,

    -- Audit
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Constraints
    CHECK (priority BETWEEN 1 AND 10),
    CHECK (retry_count >= 0),
    CHECK (max_retries >= 0),
    CHECK (progress_percentage BETWEEN 0 AND 100),
    CHECK (estado IN ('pendiente', 'en_progreso', 'completado', 'fallido', 'cancelado', 'pausado')),
    CHECK (automation_type IN ('selenium', 'api', 'manual', 'hybrid')),

    -- Foreign keys (soft - no RESTRICT for rollback safety)
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 2. automation_logs (depends on automation_jobs)
CREATE TABLE automation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,

    -- Log metadata
    level TEXT NOT NULL,
    category TEXT NOT NULL,
    message TEXT NOT NULL,

    -- Technical context
    url TEXT,
    element_selector TEXT,
    screenshot_id INTEGER,
    execution_time_ms INTEGER,

    -- Structured data
    data TEXT, -- JSON

    -- Technical metadata
    user_agent TEXT,
    ip_address TEXT,

    timestamp TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',

    -- Constraints
    CHECK (level IN ('debug', 'info', 'warning', 'error', 'critical')),
    CHECK (category IN ('navigation', 'ocr', 'captcha', 'form_fill', 'download', 'validation')),
    CHECK (execution_time_ms >= 0),

    -- Foreign keys
    FOREIGN KEY (job_id) REFERENCES automation_jobs(id) ON DELETE CASCADE
);

-- 3. automation_screenshots (depends on automation_jobs)
CREATE TABLE automation_screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,

    -- Screenshot metadata
    step_name TEXT NOT NULL,
    screenshot_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,

    -- Navigation context
    url TEXT,
    window_title TEXT,
    viewport_size TEXT,
    page_load_time_ms INTEGER,

    -- Content analysis
    has_captcha BOOLEAN DEFAULT FALSE,
    captcha_type TEXT,
    detected_elements TEXT, -- JSON
    ocr_text TEXT,

    -- Manual annotations
    manual_annotations TEXT, -- JSON
    is_sensitive BOOLEAN DEFAULT FALSE,

    created_at TEXT NOT NULL,
    company_id TEXT NOT NULL DEFAULT 'default',

    -- Constraints
    CHECK (screenshot_type IN ('step', 'error', 'success', 'captcha', 'manual')),
    CHECK (file_size >= 0),
    CHECK (page_load_time_ms >= 0),

    -- Foreign keys
    FOREIGN KEY (job_id) REFERENCES automation_jobs(id) ON DELETE CASCADE
);

-- 4. automation_config (independent)
CREATE TABLE automation_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'string',

    -- Scope management
    scope TEXT NOT NULL DEFAULT 'global',
    scope_id TEXT,

    -- Metadata
    description TEXT,
    category TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_readonly BOOLEAN DEFAULT FALSE,

    -- Change tracking
    previous_value TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    change_reason TEXT,

    -- Constraints
    CHECK (value_type IN ('string', 'boolean', 'integer', 'json')),
    CHECK (scope IN ('global', 'company', 'merchant', 'user')),

    -- Unique constraint
    UNIQUE(key, scope, scope_id)
);

-- ===================================================================
-- INDEXES (order optimized for performance)
-- ===================================================================

-- automation_jobs indexes
CREATE INDEX idx_automation_jobs_estado ON automation_jobs(estado);
CREATE INDEX idx_automation_jobs_company ON automation_jobs(company_id);
CREATE INDEX idx_automation_jobs_session ON automation_jobs(session_id);
CREATE INDEX idx_automation_jobs_ticket ON automation_jobs(ticket_id);
CREATE INDEX idx_automation_jobs_merchant ON automation_jobs(merchant_id);
CREATE INDEX idx_automation_jobs_priority ON automation_jobs(priority, estado);
CREATE INDEX idx_automation_jobs_created ON automation_jobs(created_at);

-- automation_logs indexes
CREATE INDEX idx_automation_logs_job ON automation_logs(job_id);
CREATE INDEX idx_automation_logs_session ON automation_logs(session_id);
CREATE INDEX idx_automation_logs_level ON automation_logs(level);
CREATE INDEX idx_automation_logs_category ON automation_logs(category);
CREATE INDEX idx_automation_logs_timestamp ON automation_logs(timestamp);

-- automation_screenshots indexes
CREATE INDEX idx_automation_screenshots_job ON automation_screenshots(job_id);
CREATE INDEX idx_automation_screenshots_session ON automation_screenshots(session_id);
CREATE INDEX idx_automation_screenshots_type ON automation_screenshots(screenshot_type);

-- automation_config indexes
CREATE INDEX idx_automation_config_key ON automation_config(key);
CREATE INDEX idx_automation_config_scope ON automation_config(scope, scope_id);
CREATE INDEX idx_automation_config_active ON automation_config(is_active);

-- ===================================================================
-- SEED CONFIGURATION
-- ===================================================================

-- Insert seed configuration
INSERT INTO automation_config (key, value, value_type, scope, description, category, is_active, is_readonly, updated_at, updated_by) VALUES
('automation_engine_enabled', 'false', 'boolean', 'global', 'Master switch for automation engine v2', 'automation', 1, 0, datetime('now'), 'migration_009'),
('selenium_grid_url', 'http://localhost:4444/wd/hub', 'string', 'global', 'Selenium Grid hub URL', 'selenium', 1, 0, datetime('now'), 'migration_009'),
('max_concurrent_jobs', '5', 'integer', 'global', 'Maximum concurrent automation jobs', 'automation', 1, 0, datetime('now'), 'migration_009'),
('screenshot_retention_days', '30', 'integer', 'global', 'Days to retain screenshots', 'storage', 1, 0, datetime('now'), 'migration_009'),
('captcha_service_enabled', 'true', 'boolean', 'global', 'Enable 2Captcha integration', 'captcha', 1, 0, datetime('now'), 'migration_009'),
('ocr_backend_primary', 'google_vision', 'string', 'global', 'Primary OCR backend to use', 'ocr', 1, 0, datetime('now'), 'migration_009'),
('default_automation_timeout', '300', 'integer', 'global', 'Default timeout for automation jobs (seconds)', 'automation', 1, 0, datetime('now'), 'migration_009'),
('real_time_logs_enabled', 'true', 'boolean', 'global', 'Enable real-time log streaming via WebSocket', 'ui', 1, 0, datetime('now'), 'migration_009');

-- ===================================================================
-- FINALIZATION
-- ===================================================================

-- Insert migration record (after all tables are created)
INSERT INTO schema_versions (name, applied_at)
VALUES ('009_automation_engine', datetime('now'));

-- Validate that all tables were created successfully
-- This will be checked by the application after migration