-- Migration 042: Create Departments and User Hierarchy Tables
-- Purpose: Add organizational structure with departments and reporting lines
-- Date: 2025-11-28

-- =====================================================
-- DEPARTMENTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50),
    parent_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    manager_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    description TEXT,
    cost_center VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT unique_dept_code_per_tenant UNIQUE (tenant_id, code),
    CONSTRAINT unique_dept_name_per_tenant UNIQUE (tenant_id, name),
    CONSTRAINT check_parent_not_self CHECK (id != parent_id)
);

CREATE INDEX IF NOT EXISTS idx_departments_tenant ON departments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_departments_parent ON departments(parent_id);
CREATE INDEX IF NOT EXISTS idx_departments_manager ON departments(manager_user_id);
CREATE INDEX IF NOT EXISTS idx_departments_active ON departments(is_active) WHERE is_active = TRUE;

-- =====================================================
-- USER_DEPARTMENTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_departments (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, department_id)
);

CREATE INDEX IF NOT EXISTS idx_user_departments_user ON user_departments(user_id);
CREATE INDEX IF NOT EXISTS idx_user_departments_dept ON user_departments(department_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_departments_one_primary ON user_departments(user_id) WHERE is_primary = TRUE;

-- =====================================================
-- USER_HIERARCHY TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_hierarchy (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    supervisor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) DEFAULT 'direct_report',
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, supervisor_id, effective_from),
    CONSTRAINT check_supervisor_not_self CHECK (user_id != supervisor_id)
);

CREATE INDEX IF NOT EXISTS idx_user_hierarchy_user ON user_hierarchy(user_id);
CREATE INDEX IF NOT EXISTS idx_user_hierarchy_supervisor ON user_hierarchy(supervisor_id);
CREATE INDEX IF NOT EXISTS idx_user_hierarchy_active ON user_hierarchy(effective_to) WHERE effective_to IS NULL OR effective_to > CURRENT_DATE;

COMMIT;
