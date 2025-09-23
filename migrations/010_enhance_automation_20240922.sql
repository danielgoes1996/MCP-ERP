-- Migration 010: Enhance automation tables for robust integration
-- Adds enhanced fields to existing tables without breaking compatibility

-- Add enhanced fields to automation_jobs
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'normal';
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS progress_percentage REAL DEFAULT 0.0;
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS notification_webhook TEXT;
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 3;
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS timeout_seconds INTEGER DEFAULT 300;
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS cost_breakdown TEXT; -- JSON
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS services_used TEXT; -- JSON
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS intervention_instructions TEXT;
ALTER TABLE automation_jobs ADD COLUMN IF NOT EXISTS human_explanation TEXT;

-- Add enhanced fields to automation_logs
ALTER TABLE automation_logs ADD COLUMN IF NOT EXISTS confidence_score REAL;
ALTER TABLE automation_logs ADD COLUMN IF NOT EXISTS retry_attempt INTEGER DEFAULT 0;
ALTER TABLE automation_logs ADD COLUMN IF NOT EXISTS service_used TEXT;
ALTER TABLE automation_logs ADD COLUMN IF NOT EXISTS llm_reasoning TEXT;

-- Add enhanced fields to automation_screenshots
ALTER TABLE automation_screenshots ADD COLUMN IF NOT EXISTS confidence_score REAL;
ALTER TABLE automation_screenshots ADD COLUMN IF NOT EXISTS ocr_text TEXT;
ALTER TABLE automation_screenshots ADD COLUMN IF NOT EXISTS detected_elements_count INTEGER DEFAULT 0;

-- Create feature_flags table for tenant configuration
CREATE TABLE IF NOT EXISTS feature_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    enabled BOOLEAN DEFAULT true,
    config TEXT, -- JSON configuration
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, feature_name)
);

-- Create tenant_config table
CREATE TABLE IF NOT EXISTS tenant_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT UNIQUE NOT NULL,
    max_concurrent_jobs INTEGER DEFAULT 3,
    max_daily_jobs INTEGER DEFAULT 100,
    storage_quota_mb INTEGER DEFAULT 1000,
    webhook_url TEXT,
    custom_timeout_seconds INTEGER DEFAULT 300,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Create automation_batches table for bulk operations
CREATE TABLE IF NOT EXISTS automation_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT UNIQUE NOT NULL,
    company_id TEXT NOT NULL,
    total_jobs INTEGER NOT NULL,
    completed_jobs INTEGER DEFAULT 0,
    failed_jobs INTEGER DEFAULT 0,
    status TEXT DEFAULT 'processing', -- processing, completed, failed, cancelled
    notification_webhook TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Create automation_metrics table for analytics
CREATE TABLE IF NOT EXISTS automation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL,
    date TEXT NOT NULL, -- YYYY-MM-DD
    total_jobs INTEGER DEFAULT 0,
    successful_jobs INTEGER DEFAULT 0,
    failed_jobs INTEGER DEFAULT 0,
    total_processing_time_ms INTEGER DEFAULT 0,
    captchas_solved INTEGER DEFAULT 0,
    total_cost REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_automation_jobs_company_status ON automation_jobs(company_id, estado);
CREATE INDEX IF NOT EXISTS idx_automation_jobs_priority ON automation_jobs(priority, created_at);
CREATE INDEX IF NOT EXISTS idx_automation_logs_job_timestamp ON automation_logs(job_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_automation_screenshots_job_created ON automation_screenshots(job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_feature_flags_company ON feature_flags(company_id);
CREATE INDEX IF NOT EXISTS idx_tenant_config_company ON tenant_config(company_id);
CREATE INDEX IF NOT EXISTS idx_automation_batches_status ON automation_batches(status, created_at);
CREATE INDEX IF NOT EXISTS idx_automation_metrics_company_date ON automation_metrics(company_id, date);

-- Insert default tenant config
INSERT OR IGNORE INTO tenant_config (
    company_id, max_concurrent_jobs, max_daily_jobs, storage_quota_mb,
    created_at, updated_at
) VALUES (
    'default', 3, 100, 1000,
    datetime('now'), datetime('now')
);

-- Insert default feature flags
INSERT OR IGNORE INTO feature_flags (company_id, feature_name, enabled, created_at, updated_at)
VALUES
    ('default', 'enhanced_automation', 1, datetime('now'), datetime('now')),
    ('default', 'claude_analysis', 1, datetime('now'), datetime('now')),
    ('default', 'google_vision_ocr', 1, datetime('now'), datetime('now')),
    ('default', 'captcha_solving', 1, datetime('now'), datetime('now')),
    ('default', 'multi_url_navigation', 1, datetime('now'), datetime('now')),
    ('default', 'screenshot_evidence', 1, datetime('now'), datetime('now')),
    ('default', 'llm_error_explanation', 1, datetime('now'), datetime('now')),
    ('default', 'real_time_streaming', 1, datetime('now'), datetime('now')),
    ('default', 'bulk_operations', 1, datetime('now'), datetime('now'));

-- Add triggers to update timestamps
CREATE TRIGGER IF NOT EXISTS update_automation_jobs_timestamp
AFTER UPDATE ON automation_jobs
BEGIN
    UPDATE automation_jobs SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_feature_flags_timestamp
AFTER UPDATE ON feature_flags
BEGIN
    UPDATE feature_flags SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_tenant_config_timestamp
AFTER UPDATE ON tenant_config
BEGIN
    UPDATE tenant_config SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_automation_batches_timestamp
AFTER UPDATE ON automation_batches
BEGIN
    UPDATE automation_batches SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_automation_metrics_timestamp
AFTER UPDATE ON automation_metrics
BEGIN
    UPDATE automation_metrics SET updated_at = datetime('now') WHERE id = NEW.id;
END;