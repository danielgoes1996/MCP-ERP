-- Migration 025: Remove obsolete DEFINED_NO_DATA tables
-- Purpose: Clean up tables that are never used and have no roadmap
-- Priority: LOW (cleanup)
-- Date: 2025-10-03
-- Sprint 2B

-- ============================================================================
-- CONTEXT: These tables have:
-- - 0 or minimal data (1-3 rows)
-- - Minimal code references (1 mention or less)
-- - No active functionality
-- - No roadmap for future use
-- ============================================================================

-- ============================================================================
-- BACKUP REMINDER
-- ============================================================================
-- Before running this migration, ensure backups are taken if needed:
-- sqlite3 unified_mcp_system.db ".dump expense_attachments" > expense_attachments_backup.sql
-- sqlite3 unified_mcp_system.db ".dump bank_reconciliation_feedback" > bank_reconciliation_feedback_backup.sql
-- sqlite3 unified_mcp_system.db ".dump duplicate_detection" > duplicate_detection_backup.sql

-- ============================================================================
-- STEP 1: Remove obsolete tables
-- ============================================================================

-- 1. expense_attachments (1 mention only in models.py, never used)
DROP TABLE IF EXISTS expense_attachments;

-- 2. bank_reconciliation_feedback (1 mention, 1 INSERT but 0 SELECTs)
-- Note: This table has 0 rows and minimal usage
DROP TABLE IF EXISTS bank_reconciliation_feedback;

-- 3. duplicate_detection (legacy version, replaced by duplicate_detections)
-- Note: duplicate_detections has tenant_id and is the current version
DROP TABLE IF EXISTS duplicate_detection;

-- ============================================================================
-- STEP 2: Verification queries
-- ============================================================================
-- After migration, verify tables are removed:
-- SELECT name FROM sqlite_master WHERE type='table' AND name IN ('expense_attachments', 'bank_reconciliation_feedback', 'duplicate_detection');
-- Expected: 0 rows

-- ============================================================================
-- ROLLBACK PLAN (if needed)
-- ============================================================================
-- If you need to rollback, restore from backups:
-- sqlite3 unified_mcp_system.db < expense_attachments_backup.sql
-- sqlite3 unified_mcp_system.db < bank_reconciliation_feedback_backup.sql
-- sqlite3 unified_mcp_system.db < duplicate_detection_backup.sql

-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. Impact: ZERO - these tables are not used in production code
-- 2. Risk: LOW - no data will be lost (tables are empty or near-empty)
-- 3. Migration can be run safely without downtime
-- 4. If any code references these tables, it should be removed first:
--    - Search for: expense_attachments, bank_reconciliation_feedback, duplicate_detection
--    - Update or remove any references
-- 5. Consider removing these tables from:
--    - core/api_models.py (if referenced)
--    - core/unified_db_adapter.py (if referenced)
