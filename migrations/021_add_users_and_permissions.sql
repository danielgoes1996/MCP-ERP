-- Migration 021: Users, Roles and Permissions System
-- Purpose: Add authentication and authorization to MCP System

-- =====================================================
-- USERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Credentials
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,

    -- Profile
    full_name TEXT NOT NULL,
    employee_id INTEGER,  -- Link to employee_advances if user is an employee

    -- Role
    role TEXT NOT NULL CHECK(role IN ('employee', 'accountant', 'manager', 'admin')) DEFAULT 'employee',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_email_verified BOOLEAN DEFAULT FALSE,

    -- Security
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login TIMESTAMP,
    locked_until TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,

    -- Metadata
    created_by INTEGER,
    phone TEXT,
    department TEXT,

    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_employee_id ON users(employee_id);
CREATE INDEX idx_users_is_active ON users(is_active) WHERE is_active = TRUE;

-- =====================================================
-- PERMISSIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Permission definition
    role TEXT NOT NULL,
    resource TEXT NOT NULL,  -- 'employee_advances', 'bank_reconciliation', 'manual_expenses'
    action TEXT NOT NULL,    -- 'read', 'create', 'update', 'delete', '*'
    scope TEXT,              -- 'own', 'all', 'department'

    -- Metadata
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(role, resource, action)
);

CREATE INDEX idx_permissions_role ON permissions(role);
CREATE INDEX idx_permissions_resource ON permissions(resource);

-- =====================================================
-- SESSIONS TABLE (for token management)
-- =====================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,
    token_jti TEXT UNIQUE NOT NULL,  -- JWT ID for revocation

    -- Session info
    ip_address TEXT,
    user_agent TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_token ON user_sessions(token_jti);
CREATE INDEX idx_sessions_active ON user_sessions(user_id)
    WHERE revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP;

-- =====================================================
-- ACCESS LOG TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- User
    user_id INTEGER,
    username TEXT,

    -- Request
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,

    -- Context
    ip_address TEXT,
    user_agent TEXT,

    -- Timing
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER,

    -- Error tracking
    error_message TEXT,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_access_log_user ON access_log(user_id);
CREATE INDEX idx_access_log_timestamp ON access_log(timestamp DESC);
CREATE INDEX idx_access_log_endpoint ON access_log(endpoint);
CREATE INDEX idx_access_log_errors ON access_log(status_code) WHERE status_code >= 400;

-- =====================================================
-- DEFAULT PERMISSIONS
-- =====================================================

-- Employee permissions
INSERT INTO permissions (role, resource, action, scope, description) VALUES
    ('employee', 'manual_expenses', 'read', 'own', 'View own expenses'),
    ('employee', 'manual_expenses', 'create', 'own', 'Create own expenses'),
    ('employee', 'manual_expenses', 'update', 'own', 'Update own expenses'),
    ('employee', 'employee_advances', 'read', 'own', 'View own advances'),
    ('employee', 'employee_advances', 'create', 'own', 'Create own advances'),
    ('employee', 'dashboard', 'read', 'own', 'View own dashboard');

-- Accountant permissions
INSERT INTO permissions (role, resource, action, scope, description) VALUES
    ('accountant', 'manual_expenses', 'read', 'all', 'View all expenses'),
    ('accountant', 'manual_expenses', 'update', 'all', 'Update any expense'),
    ('accountant', 'employee_advances', 'read', 'all', 'View all advances'),
    ('accountant', 'employee_advances', 'update', 'all', 'Process reimbursements'),
    ('accountant', 'employee_advances', 'create', 'all', 'Create advances for any employee'),
    ('accountant', 'bank_reconciliation', 'read', 'all', 'View bank movements'),
    ('accountant', 'bank_reconciliation', 'create', 'all', 'Create reconciliations'),
    ('accountant', 'bank_reconciliation_ai', 'read', 'all', 'View AI suggestions'),
    ('accountant', 'bank_statements', 'upload', 'all', 'Upload bank statements'),
    ('accountant', 'dashboard', 'read', 'all', 'View full dashboard');

-- Manager permissions (accountant + approval)
INSERT INTO permissions (role, resource, action, scope, description) VALUES
    ('manager', 'manual_expenses', 'read', 'all', 'View all expenses'),
    ('manager', 'manual_expenses', 'update', 'all', 'Update any expense'),
    ('manager', 'manual_expenses', 'approve', 'all', 'Approve expenses'),
    ('manager', 'employee_advances', 'read', 'all', 'View all advances'),
    ('manager', 'employee_advances', 'update', 'all', 'Update advances'),
    ('manager', 'employee_advances', 'approve', 'all', 'Approve advances'),
    ('manager', 'bank_reconciliation', 'read', 'all', 'View reconciliations'),
    ('manager', 'dashboard', 'read', 'all', 'View manager dashboard'),
    ('manager', 'reports', 'read', 'all', 'View all reports');

-- Admin permissions (full access)
INSERT INTO permissions (role, resource, action, scope, description) VALUES
    ('admin', '*', '*', 'all', 'Full system access'),
    ('admin', 'users', 'create', 'all', 'Create users'),
    ('admin', 'users', 'update', 'all', 'Update users'),
    ('admin', 'users', 'delete', 'all', 'Delete users'),
    ('admin', 'permissions', 'update', 'all', 'Modify permissions'),
    ('admin', 'system', 'configure', 'all', 'System configuration');

-- =====================================================
-- DEFAULT ADMIN USER
-- =====================================================
-- Password: admin123 (hashed with bcrypt)
-- NOTE: Change this password immediately after first login!
INSERT INTO users (username, email, password_hash, full_name, role, is_active, is_email_verified) VALUES
    ('admin', 'admin@mcpsystem.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIbRgeEM8K', 'System Administrator', 'admin', TRUE, TRUE);

-- Default accountant for testing
-- Password: accountant123
INSERT INTO users (username, email, password_hash, full_name, role, is_active, is_email_verified) VALUES
    ('maria.garcia', 'maria.garcia@mcpsystem.local', '$2b$12$8ZqKjLWp3VJ8W1k5YnKj7O5YzT0mN3xF2hR9wQ4eL6pS8vU2dK1Hy', 'María García', 'accountant', TRUE, TRUE);

-- Default employee for testing
-- Password: employee123
-- Employee ID: 1 (Juan Pérez from previous tests)
INSERT INTO users (username, email, password_hash, full_name, role, employee_id, is_active, is_email_verified) VALUES
    ('juan.perez', 'juan.perez@mcpsystem.local', '$2b$12$9BrLmXp4WK9X2l6ZoOLk8P6Z0U1nO4yG3iS0xR5fM7qT9wV3eL2Iz', 'Juan Pérez', 'employee', 1, TRUE, TRUE);

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS users_updated_at
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Log user creation
CREATE TRIGGER IF NOT EXISTS log_user_creation
AFTER INSERT ON users
FOR EACH ROW
BEGIN
    INSERT INTO access_log (user_id, username, endpoint, method, status_code, timestamp)
    VALUES (NEW.id, NEW.username, '/users', 'CREATE', 201, CURRENT_TIMESTAMP);
END;

-- =====================================================
-- VIEWS
-- =====================================================

-- Active users view
CREATE VIEW IF NOT EXISTS active_users AS
SELECT
    id, username, email, full_name, role, employee_id,
    created_at, last_login
FROM users
WHERE is_active = TRUE;

-- User permissions view
CREATE VIEW IF NOT EXISTS user_permissions AS
SELECT
    u.id as user_id,
    u.username,
    u.role,
    p.resource,
    p.action,
    p.scope
FROM users u
JOIN permissions p ON u.role = p.role
WHERE u.is_active = TRUE;

COMMIT;
