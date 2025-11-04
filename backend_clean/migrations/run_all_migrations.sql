-- Master Migration Script
-- Executes all migrations to fix database coherence issues
-- Based on AUDITORIA_MAESTRA_SISTEMA_MCP findings

-- Begin transaction
BEGIN TRANSACTION;

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Create migrations tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT UNIQUE NOT NULL,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Migration 001: Expense fields
.read migrations/001_add_expense_fields.sql
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('001', 'Add missing expense fields');

-- Migration 002: Invoice fields
.read migrations/002_add_invoice_fields.sql
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('002', 'Add missing invoice fields');

-- Migration 003: Automation fields
.read migrations/003_add_automation_fields.sql
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('003', 'Add automation and system fields');

-- Migration 004: Analytics fields
.read migrations/004_add_analytics_fields.sql
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('004', 'Add analytics and ML fields');

-- Commit transaction
COMMIT;

-- Vacuum to optimize database
VACUUM;

-- Display migration status
SELECT 'Migration Status:' as info;
SELECT version, applied_at, description FROM schema_migrations ORDER BY version;