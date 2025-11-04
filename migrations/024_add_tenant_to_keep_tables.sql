-- Migration 024: Add tenant_id to DEFINED_NO_DATA KEEP tables
-- Purpose: Enable multi-tenant isolation for tables that will be used
-- Priority: MEDIUM (infrastructure preparation)
-- Date: 2025-10-03
-- Sprint 2A

-- ============================================================================
-- CONTEXT: These tables are DEFINED but have NO DATA yet
-- They will be used in the future, so we add tenant_id now for consistency
-- ============================================================================

-- ============================================================================
-- STEP 1: Add tenant_id to KEEP tables without multi-tenancy
-- ============================================================================

-- Workers table (87 mentions, worker system infrastructure)
ALTER TABLE workers ADD COLUMN tenant_id INTEGER;

-- Automation screenshots (17 mentions, used in playwright engines)
ALTER TABLE automation_screenshots ADD COLUMN tenant_id INTEGER;

-- Automation sessions (20 mentions, RPA state management)
ALTER TABLE automation_sessions ADD COLUMN tenant_id INTEGER;

-- User preferences (17 mentions, UX features)
ALTER TABLE user_preferences ADD COLUMN tenant_id INTEGER;

-- Expense tag relations (11 mentions, many-to-many tags)
ALTER TABLE expense_tag_relations ADD COLUMN tenant_id INTEGER;

-- User sessions (3 mentions, session tracking) - EVALUATE if needed
ALTER TABLE user_sessions ADD COLUMN tenant_id INTEGER;

-- ============================================================================
-- STEP 2: Create indexes for future performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_workers_tenant
ON workers(tenant_id);

CREATE INDEX IF NOT EXISTS idx_automation_screenshots_tenant
ON automation_screenshots(tenant_id);

CREATE INDEX IF NOT EXISTS idx_automation_sessions_tenant
ON automation_sessions(tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_preferences_tenant
ON user_preferences(tenant_id);

CREATE INDEX IF NOT EXISTS idx_expense_tag_relations_tenant
ON expense_tag_relations(tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_sessions_tenant
ON user_sessions(tenant_id);

-- ============================================================================
-- STEP 3: Create composite indexes for common query patterns
-- ============================================================================

-- workers: Often queried by task_type + tenant_id
CREATE INDEX IF NOT EXISTS idx_workers_task_tenant
ON workers(task_type, tenant_id);

-- workers: Often queried by status + tenant_id
CREATE INDEX IF NOT EXISTS idx_workers_status_tenant
ON workers(status, tenant_id);

-- automation_screenshots: Often queried by job_id + tenant_id
CREATE INDEX IF NOT EXISTS idx_screenshots_job_tenant
ON automation_screenshots(job_id, tenant_id);

-- automation_sessions: Often queried by session_id + tenant_id
CREATE INDEX IF NOT EXISTS idx_sessions_session_tenant
ON automation_sessions(session_id, tenant_id);

-- user_preferences: Often queried by user_id + tenant_id
CREATE INDEX IF NOT EXISTS idx_preferences_user_tenant
ON user_preferences(user_id, tenant_id);

-- user_sessions: Often queried by user_id + tenant_id
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_tenant
ON user_sessions(user_id, tenant_id);

-- expense_tag_relations: Often queried by expense_id + tenant_id
CREATE INDEX IF NOT EXISTS idx_tag_relations_expense_tenant
ON expense_tag_relations(expense_id, tenant_id);

-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. These tables have NO DATA yet, so no population needed
-- 2. When populating these tables in the future, ALWAYS include tenant_id
-- 3. Required code changes:
--    - core/worker_system.py: INSERT workers with tenant_id
--    - modules/invoicing_agent/automation_persistence.py: INSERT screenshots with tenant_id
--    - All RPA engines: INSERT sessions with tenant_id
--    - UX features: INSERT user_preferences with tenant_id
--    - Tags system: INSERT expense_tag_relations with tenant_id
-- 4. Verification: All future INSERTs must fail if tenant_id is NULL (consider adding NOT NULL constraint later)
