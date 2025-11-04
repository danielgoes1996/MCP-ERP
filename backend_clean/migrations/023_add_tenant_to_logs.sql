-- Migration 023: Add tenant_id to critical log tables
-- Purpose: Enable multi-tenant isolation for all logging and audit tables
-- Priority: CRITICAL (Security risk: cross-tenant data leaks)
-- Date: 2025-10-03

-- ============================================================================
-- STEP 1: Add tenant_id columns to log tables (skip if already exists)
-- ============================================================================

-- Note: All tables already have tenant_id column from previous attempts
-- Skipping ALTER TABLE commands to avoid duplicate column errors

-- ============================================================================
-- STEP 2: Populate tenant_id for existing records
-- ============================================================================

-- missing_transactions_log: Get tenant_id from related extraction_audit
UPDATE missing_transactions_log
SET tenant_id = (
    SELECT pea.tenant_id
    FROM pdf_extraction_audit pea
    WHERE pea.id = missing_transactions_log.extraction_audit_id
    LIMIT 1
)
WHERE missing_transactions_log.extraction_audit_id IS NOT NULL
  AND missing_transactions_log.tenant_id IS NULL;

-- automation_logs: Get tenant_id from related automation_jobs
UPDATE automation_logs
SET tenant_id = (
    SELECT aj.tenant_id
    FROM automation_jobs aj
    WHERE aj.id = automation_logs.job_id
    LIMIT 1
)
WHERE automation_logs.job_id IS NOT NULL
  AND automation_logs.tenant_id IS NULL;

-- validation_issues_log: Get tenant_id from related extraction_audit
UPDATE validation_issues_log
SET tenant_id = (
    SELECT pea.tenant_id
    FROM pdf_extraction_audit pea
    WHERE pea.id = validation_issues_log.extraction_audit_id
    LIMIT 1
)
WHERE validation_issues_log.extraction_audit_id IS NOT NULL
  AND validation_issues_log.tenant_id IS NULL;

-- refresh_tokens: Get tenant_id from users table
UPDATE refresh_tokens
SET tenant_id = (
    SELECT u.tenant_id
    FROM users u
    WHERE u.id = refresh_tokens.user_id
    LIMIT 1
)
WHERE refresh_tokens.user_id IS NOT NULL
  AND refresh_tokens.tenant_id IS NULL;

-- access_log: Get tenant_id from users table
UPDATE access_log
SET tenant_id = (
    SELECT u.tenant_id
    FROM users u
    WHERE u.id = access_log.user_id
    LIMIT 1
)
WHERE access_log.user_id IS NOT NULL
  AND access_log.tenant_id IS NULL;

-- banking_institutions: Assign to default tenant (tenant_id = 1) if system-wide
-- Or make tenant-specific if needed
UPDATE banking_institutions
SET tenant_id = 1
WHERE tenant_id IS NULL;

-- permissions: Assign to default tenant (tenant_id = 1) - system-wide permissions
-- Note: permissions table doesn't have user_id, it's a role-based access control table
UPDATE permissions
SET tenant_id = 1
WHERE tenant_id IS NULL;

-- ============================================================================
-- STEP 3: Create indexes for performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_missing_transactions_tenant
ON missing_transactions_log(tenant_id);

CREATE INDEX IF NOT EXISTS idx_automation_logs_tenant
ON automation_logs(tenant_id);

CREATE INDEX IF NOT EXISTS idx_validation_issues_tenant
ON validation_issues_log(tenant_id);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_tenant
ON refresh_tokens(tenant_id);

CREATE INDEX IF NOT EXISTS idx_banking_institutions_tenant
ON banking_institutions(tenant_id);

CREATE INDEX IF NOT EXISTS idx_permissions_tenant
ON permissions(tenant_id);

CREATE INDEX IF NOT EXISTS idx_access_log_tenant
ON access_log(tenant_id);

-- ============================================================================
-- STEP 4: Create composite indexes for common queries
-- ============================================================================

-- refresh_tokens: Often queried by user_id + tenant_id
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_tenant
ON refresh_tokens(user_id, tenant_id);

-- automation_logs: Often queried by job_id + tenant_id
CREATE INDEX IF NOT EXISTS idx_automation_logs_job_tenant
ON automation_logs(job_id, tenant_id);

-- permissions: Often queried by role + tenant_id
CREATE INDEX IF NOT EXISTS idx_permissions_role_tenant
ON permissions(role, tenant_id);

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Check for NULL tenant_id values:
-- SELECT 'missing_transactions_log' as tabla, COUNT(*) as null_count FROM missing_transactions_log WHERE tenant_id IS NULL
-- UNION ALL
-- SELECT 'automation_logs', COUNT(*) FROM automation_logs WHERE tenant_id IS NULL
-- UNION ALL
-- SELECT 'validation_issues_log', COUNT(*) FROM validation_issues_log WHERE tenant_id IS NULL
-- UNION ALL
-- SELECT 'refresh_tokens', COUNT(*) FROM refresh_tokens WHERE tenant_id IS NULL
-- UNION ALL
-- SELECT 'banking_institutions', COUNT(*) FROM banking_institutions WHERE tenant_id IS NULL
-- UNION ALL
-- SELECT 'permissions', COUNT(*) FROM permissions WHERE tenant_id IS NULL
-- UNION ALL
-- SELECT 'access_log', COUNT(*) FROM access_log WHERE tenant_id IS NULL;

-- Expected result: All counts should be 0 or minimal (orphaned records)

-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. This migration is CRITICAL for security (prevents cross-tenant data leaks)
-- 2. After migration, all INSERT operations MUST include tenant_id
-- 3. All SELECT/UPDATE/DELETE operations MUST filter by tenant_id
-- 4. Code changes required in:
--    - core/internal_db.py (log functions)
--    - core/error_handler.py
--    - Any service writing to these tables
-- 5. banking_institutions may need per-tenant configuration in the future
