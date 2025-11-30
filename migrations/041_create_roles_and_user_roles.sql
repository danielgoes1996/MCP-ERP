-- Migration 041: Create Roles and User Roles Tables
-- Date: 2025-11-28

BEGIN;

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    level INTEGER DEFAULT 0,
    permissions JSONB DEFAULT '{}'::jsonb,
    is_system BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Unique index instead of constraint (allows COALESCE)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_role_per_tenant
    ON roles (COALESCE(tenant_id, 0), name);

CREATE INDEX IF NOT EXISTS idx_roles_tenant ON roles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);
CREATE INDEX IF NOT EXISTS idx_roles_active ON roles(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_roles_level ON roles(level);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    expires_at TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id);

-- Seed system roles
INSERT INTO roles (tenant_id, name, display_name, description, level, is_system, permissions) VALUES
(NULL, 'admin', 'Administrador', 'Administrador del sistema', 100, TRUE, '{"resources":["*"],"actions":["*"],"scope":"all"}'::jsonb),
(NULL, 'contador', 'Contador', 'Contador profesional', 80, TRUE, '{"resources":["invoices","classifications"],"actions":["read","classify","approve","reject"],"scope":"tenant"}'::jsonb),
(NULL, 'accountant', 'Contador General', 'Contador general', 80, TRUE, '{"resources":["invoices","expenses"],"actions":["read","update","approve"],"scope":"tenant"}'::jsonb),
(NULL, 'supervisor', 'Supervisor', 'Supervisor de departamento', 50, TRUE, '{"resources":["expenses"],"actions":["read","approve"],"scope":"department"}'::jsonb),
(NULL, 'manager', 'Gerente', 'Gerente', 60, TRUE, '{"resources":["expenses","reports"],"actions":["read","approve"],"scope":"all"}'::jsonb),
(NULL, 'empleado', 'Empleado', 'Empleado', 0, TRUE, '{"resources":["expenses"],"actions":["read","create","update"],"scope":"own"}'::jsonb),
(NULL, 'viewer', 'Visor', 'Solo lectura', 0, TRUE, '{"resources":["expenses","reports"],"actions":["read"],"scope":"own"}'::jsonb)
ON CONFLICT DO NOTHING;

COMMIT;
