-- UNIFIED MIGRATION: Add Missing Fields to Unified MCP System Database
-- Adapts field additions to use correct table names from unified schema
-- Based on AUDITORIA_MAESTRA_SISTEMA_MCP findings

-- Begin transaction
BEGIN TRANSACTION;

-- ========================================
-- 1. EXPENSE_RECORDS TABLE (was expenses)
-- ========================================

-- Add expense enhancement fields
ALTER TABLE expense_records ADD COLUMN deducible BOOLEAN DEFAULT TRUE;
ALTER TABLE expense_records ADD COLUMN centro_costo TEXT;
ALTER TABLE expense_records ADD COLUMN proyecto TEXT;
ALTER TABLE expense_records ADD COLUMN tags TEXT; -- SQLite doesn't support JSON type, use TEXT

-- Add audit and tracking fields
ALTER TABLE expense_records ADD COLUMN audit_trail TEXT; -- JSON as TEXT
ALTER TABLE expense_records ADD COLUMN user_context TEXT;
ALTER TABLE expense_records ADD COLUMN enhanced_data TEXT; -- JSON as TEXT

-- Add completion and validation fields
ALTER TABLE expense_records ADD COLUMN completion_status TEXT DEFAULT 'draft';
ALTER TABLE expense_records ADD COLUMN validation_errors TEXT; -- JSON as TEXT
ALTER TABLE expense_records ADD COLUMN field_completeness REAL DEFAULT 0.0; -- DECIMAL as REAL

-- ========================================
-- 2. EXPENSE_INVOICES TABLE (was invoices)
-- ========================================

-- Add invoice breakdown fields
ALTER TABLE expense_invoices ADD COLUMN subtotal REAL;
ALTER TABLE expense_invoices ADD COLUMN iva_amount REAL;
ALTER TABLE expense_invoices ADD COLUMN discount REAL DEFAULT 0.0;
ALTER TABLE expense_invoices ADD COLUMN retention REAL DEFAULT 0.0;

-- Add invoice metadata fields
ALTER TABLE expense_invoices ADD COLUMN xml_content TEXT;
ALTER TABLE expense_invoices ADD COLUMN validation_status TEXT DEFAULT 'pending';
ALTER TABLE expense_invoices ADD COLUMN processing_metadata TEXT; -- JSON as TEXT

-- Add template matching fields (✅ CAMPOS FALTANTES CRÍTICOS)
ALTER TABLE expense_invoices ADD COLUMN template_match REAL; -- DECIMAL as REAL
ALTER TABLE expense_invoices ADD COLUMN validation_rules TEXT; -- JSON as TEXT
ALTER TABLE expense_invoices ADD COLUMN detected_format TEXT;
ALTER TABLE expense_invoices ADD COLUMN parser_used TEXT;

-- Add OCR and processing fields (✅ CAMPOS FALTANTES CRÍTICOS)
ALTER TABLE expense_invoices ADD COLUMN ocr_confidence REAL; -- DECIMAL as REAL
ALTER TABLE expense_invoices ADD COLUMN processing_metrics TEXT; -- JSON as TEXT
ALTER TABLE expense_invoices ADD COLUMN quality_score REAL; -- DECIMAL as REAL
ALTER TABLE expense_invoices ADD COLUMN processor_used TEXT;
ALTER TABLE expense_invoices ADD COLUMN extraction_confidence REAL;

-- ========================================
-- 3. BANK_MOVEMENTS TABLE
-- ========================================

-- Add bank movement enhancements (✅ CAMPOS FALTANTES CRÍTICOS)
ALTER TABLE bank_movements ADD COLUMN decision TEXT;
ALTER TABLE bank_movements ADD COLUMN bank_metadata TEXT; -- JSON as TEXT
ALTER TABLE bank_movements ADD COLUMN matching_confidence REAL; -- DECIMAL as REAL

-- ========================================
-- 4. AUTOMATION TABLES ENHANCEMENTS
-- ========================================

-- Add checkpoint and recovery fields (✅ CAMPOS FALTANTES CRÍTICOS)
ALTER TABLE automation_jobs ADD COLUMN checkpoint_data TEXT; -- JSON as TEXT
ALTER TABLE automation_jobs ADD COLUMN recovery_metadata TEXT; -- JSON as TEXT
ALTER TABLE automation_jobs ADD COLUMN session_id TEXT;
ALTER TABLE automation_jobs ADD COLUMN automation_health TEXT; -- JSON as TEXT
ALTER TABLE automation_jobs ADD COLUMN performance_metrics TEXT; -- JSON as TEXT
ALTER TABLE automation_jobs ADD COLUMN recovery_actions TEXT; -- JSON as TEXT

-- ========================================
-- 5. WORKERS TABLE (if not exists)
-- ========================================

-- Create workers table if not exists (✅ CAMPOS FALTANTES CRÍTICOS)
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    tenant_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    progress REAL DEFAULT 0.0, -- ✅ CAMPO FALTANTE CRÍTICO
    worker_metadata TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    retry_policy TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    retry_count INTEGER DEFAULT 0,
    result_data TEXT, -- JSON as TEXT
    performance_tracking TEXT, -- JSON as TEXT
    task_scheduling TEXT, -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- ========================================
-- 6. AUTOMATION_SESSIONS TABLE (if not exists)
-- ========================================

-- Create automation_sessions table if not exists
CREATE TABLE IF NOT EXISTS automation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    tenant_id INTEGER NOT NULL,
    state_data TEXT, -- JSON as TEXT
    checkpoint_data TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    recovery_metadata TEXT, -- ✅ CAMPO FALTANTE CRÍTICO (JSON as TEXT)
    session_status TEXT DEFAULT 'active',
    compression_type TEXT DEFAULT 'gzip',
    integrity_validation TEXT, -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- ========================================
-- 7. SYSTEM_HEALTH TABLE (if not exists)
-- ========================================

-- Create system_health table for monitoring
CREATE TABLE IF NOT EXISTS system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_name TEXT NOT NULL,
    health_status TEXT NOT NULL,
    automation_health TEXT, -- JSON as TEXT
    performance_metrics TEXT, -- JSON as TEXT
    error_count INTEGER DEFAULT 0,
    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT -- JSON as TEXT
);

-- ========================================
-- 8. USER_PREFERENCES TABLE (if not exists)
-- ========================================

-- Create user preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    preferences TEXT, -- JSON as TEXT
    onboarding_step TEXT DEFAULT 'start',
    demo_preferences TEXT, -- JSON as TEXT
    completion_rules TEXT, -- JSON as TEXT
    field_priorities TEXT, -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- ========================================
-- 9. CREATE PERFORMANCE INDEXES
-- ========================================

-- Expense records indexes
CREATE INDEX IF NOT EXISTS idx_expense_records_deducible ON expense_records(deducible);
CREATE INDEX IF NOT EXISTS idx_expense_records_centro_costo ON expense_records(centro_costo);
CREATE INDEX IF NOT EXISTS idx_expense_records_proyecto ON expense_records(proyecto);
CREATE INDEX IF NOT EXISTS idx_expense_records_completion ON expense_records(completion_status);

-- Invoice indexes
CREATE INDEX IF NOT EXISTS idx_expense_invoices_validation_status ON expense_invoices(validation_status);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_template_match ON expense_invoices(template_match);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_detected_format ON expense_invoices(detected_format);
CREATE INDEX IF NOT EXISTS idx_expense_invoices_quality_score ON expense_invoices(quality_score);

-- Bank movements indexes
CREATE INDEX IF NOT EXISTS idx_bank_movements_decision ON bank_movements(decision);
CREATE INDEX IF NOT EXISTS idx_bank_movements_confidence ON bank_movements(matching_confidence);

-- Automation indexes
CREATE INDEX IF NOT EXISTS idx_automation_jobs_session ON automation_jobs(session_id);
CREATE INDEX IF NOT EXISTS idx_automation_sessions_tenant ON automation_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_automation_sessions_status ON automation_sessions(session_status);

-- Workers indexes
CREATE INDEX IF NOT EXISTS idx_workers_tenant ON workers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_workers_task_type ON workers(task_type);

-- System health indexes
CREATE INDEX IF NOT EXISTS idx_system_health_component ON system_health(component_name);
CREATE INDEX IF NOT EXISTS idx_system_health_status ON system_health(health_status);

-- User preferences indexes
CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_tenant ON user_preferences(tenant_id);

-- ========================================
-- 10. UPDATE EXISTING RECORDS WITH DEFAULTS
-- ========================================

-- Update existing expense records with sensible defaults
UPDATE expense_records
SET completion_status = 'complete',
    field_completeness = 1.0,
    deducible = TRUE
WHERE description IS NOT NULL AND amount > 0;

-- Update existing invoices with calculated values
UPDATE expense_invoices
SET subtotal = (
    SELECT amount * 0.86
    FROM expense_records
    WHERE expense_records.id = expense_invoices.expense_id
    LIMIT 1
),
iva_amount = (
    SELECT amount * 0.14
    FROM expense_records
    WHERE expense_records.id = expense_invoices.expense_id
    LIMIT 1
),
validation_status = 'validated'
WHERE subtotal IS NULL;

-- ========================================
-- 11. TRACK MIGRATION
-- ========================================

-- Insert migration record
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('unified_001', 'Add all 17+ missing critical fields to unified MCP schema');

-- Commit transaction
COMMIT;

-- Vacuum to optimize database
VACUUM;

-- Display success message
SELECT 'SUCCESS: All 17+ critical fields added to unified MCP database!' as result;
SELECT 'Tables updated: expense_records, expense_invoices, bank_movements, automation_jobs' as tables_updated;
SELECT 'New tables created: workers, automation_sessions, system_health, user_preferences' as new_tables;