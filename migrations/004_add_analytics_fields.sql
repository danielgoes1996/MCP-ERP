-- Migration 004: Add Missing Analytics and Reporting Fields
-- Based on AUDITORIA_MAESTRA_SISTEMA_MCP findings
-- Priority: MEDIUM - These fields support analytics and ML features

-- Add analytics fields to expenses for enhanced reporting
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS trend_category TEXT;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS forecast_confidence DECIMAL(3,2);
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS seasonality_factor DECIMAL(3,2);

-- Add ML and prediction fields
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS ml_features JSON;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS similarity_scores JSON;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS duplicate_risk_level TEXT DEFAULT 'low';
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS ml_model_version TEXT;

-- Create analytics_cache table for performance
CREATE TABLE IF NOT EXISTS analytics_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    cache_key TEXT NOT NULL,
    cache_data JSON,
    cache_type TEXT NOT NULL,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Create category_learning table for ML
CREATE TABLE IF NOT EXISTS category_learning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    description_pattern TEXT,
    predicted_category TEXT,
    confidence DECIMAL(3,2),
    user_feedback TEXT,
    learning_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Create duplicate_detection table
CREATE TABLE IF NOT EXISTS duplicate_detection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    expense_id_1 INTEGER,
    expense_id_2 INTEGER,
    similarity_score DECIMAL(3,2),
    detection_method TEXT,
    status TEXT DEFAULT 'pending',
    user_decision TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (expense_id_1) REFERENCES expenses(id),
    FOREIGN KEY (expense_id_2) REFERENCES expenses(id)
);

-- Create error_logs table for better error tracking
CREATE TABLE IF NOT EXISTS error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    user_id INTEGER,
    error_code TEXT,
    error_message TEXT,
    stack_trace TEXT,
    user_context JSON,
    request_data JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_expenses_trend_category ON expenses(trend_category);
CREATE INDEX IF NOT EXISTS idx_expenses_duplicate_risk ON expenses(duplicate_risk_level);
CREATE INDEX IF NOT EXISTS idx_analytics_cache_company ON analytics_cache(company_id);
CREATE INDEX IF NOT EXISTS idx_analytics_cache_key ON analytics_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_analytics_cache_type ON analytics_cache(cache_type);
CREATE INDEX IF NOT EXISTS idx_category_learning_company ON category_learning(company_id);
CREATE INDEX IF NOT EXISTS idx_category_learning_pattern ON category_learning(description_pattern);
CREATE INDEX IF NOT EXISTS idx_duplicate_detection_company ON duplicate_detection(company_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_detection_score ON duplicate_detection(similarity_score);
CREATE INDEX IF NOT EXISTS idx_error_logs_company ON error_logs(company_id);
CREATE INDEX IF NOT EXISTS idx_error_logs_code ON error_logs(error_code);