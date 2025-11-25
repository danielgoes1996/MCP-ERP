-- Migration 021: Update Users Table for Authentication System
-- Purpose: Add missing fields to existing users table

BEGIN TRANSACTION;

-- Add missing columns to users table
ALTER TABLE users ADD COLUMN username TEXT UNIQUE;
ALTER TABLE users ADD COLUMN employee_id INTEGER;
ALTER TABLE users ADD COLUMN phone TEXT;
ALTER TABLE users ADD COLUMN department TEXT;
ALTER TABLE users ADD COLUMN created_by INTEGER REFERENCES users(id);
ALTER TABLE users ADD COLUMN is_email_verified BOOLEAN DEFAULT FALSE;

-- Update role column to use proper values
UPDATE users SET role = 'admin' WHERE role = 'superuser' OR is_superuser = TRUE;
UPDATE users SET role = 'employee' WHERE role = 'user';

-- =====================================================
-- PERMISSIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    scope TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role, resource, action)
);

-- =====================================================
-- SESSIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_jti TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =====================================================
-- ACCESS LOG TABLE (if not exists)
-- =====================================================
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER,
    error_message TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- =====================================================
-- DEFAULT PERMISSIONS
-- =====================================================
DELETE FROM permissions;  -- Clear any existing

INSERT INTO permissions (role, resource, action, scope, description) VALUES
    -- Employee
    ('employee', 'manual_expenses', 'read', 'own', 'View own expenses'),
    ('employee', 'manual_expenses', 'create', 'own', 'Create own expenses'),
    ('employee', 'manual_expenses', 'update', 'own', 'Update own expenses'),
    ('employee', 'employee_advances', 'read', 'own', 'View own advances'),
    ('employee', 'employee_advances', 'create', 'own', 'Create own advances'),

    -- Accountant
    ('accountant', 'manual_expenses', 'read', 'all', 'View all expenses'),
    ('accountant', 'manual_expenses', 'update', 'all', 'Update any expense'),
    ('accountant', 'employee_advances', 'read', 'all', 'View all advances'),
    ('accountant', 'employee_advances', 'update', 'all', 'Process reimbursements'),
    ('accountant', 'employee_advances', 'create', 'all', 'Create advances'),
    ('accountant', 'bank_reconciliation', 'read', 'all', 'View bank movements'),
    ('accountant', 'bank_reconciliation', 'create', 'all', 'Create reconciliations'),
    ('accountant', 'bank_reconciliation_ai', 'read', 'all', 'View AI suggestions'),

    -- Admin
    ('admin', '*', '*', 'all', 'Full system access');

-- =====================================================
-- UPDATE EXISTING USERS
-- =====================================================

-- Set usernames for existing users (use email prefix)
UPDATE users SET username = LOWER(SUBSTR(email, 1, INSTR(email, '@') - 1))
WHERE username IS NULL;

-- =====================================================
-- CREATE DEFAULT USERS (if not exist)
-- =====================================================

-- Admin user (password: admin123)
INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_active, is_email_verified)
VALUES ('admin', 'admin@mcpsystem.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIbRgeEM8K', 'System Administrator', 'admin', TRUE, TRUE);

-- Accountant user (password: accountant123)
INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_active, is_email_verified)
VALUES ('maria.garcia', 'maria.garcia@mcpsystem.local', '$2b$12$8ZqKjLWp3VJ8W1k5YnKj7O5YzT0mN3xF2hR9wQ4eL6pS8vU2dK1Hy', 'María García', 'accountant', TRUE, TRUE);

-- Employee user (password: employee123)
INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, employee_id, is_active, is_email_verified)
VALUES ('juan.perez', 'juan.perez@mcpsystem.local', '$2b$12$9BrLmXp4WK9X2l6ZoOLk8P6Z0U1nO4yG3iS0xR5fM7qT9wV3eL2Iz', 'Juan Pérez', 'employee', 1, TRUE, TRUE);

COMMIT;
