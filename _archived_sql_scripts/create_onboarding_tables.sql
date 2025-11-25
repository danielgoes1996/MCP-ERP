-- CREAR TABLAS PARA FUNCIONALIDAD #8: ONBOARDING DE USUARIOS
-- Mejora coherencia del 81% al 95%

-- 1. Crear tabla tenants si no existe
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT,
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Crear tabla users base
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    tenant_id INTEGER DEFAULT 1,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Campos de autenticación (de fix_auth_schema.sql)
    password_hash TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,

    -- Campos de onboarding (FALTANTE en auditoria)
    identifier TEXT, -- email o phone
    full_name TEXT,
    company_name TEXT,
    onboarding_step INTEGER DEFAULT 0, -- ⚠️ FALTABA EN BD
    demo_preferences TEXT, -- JSON - ❌ FALTABA EN API
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_completed_at TIMESTAMP,

    -- Metadata adicional
    phone TEXT,
    registration_method TEXT DEFAULT 'email', -- 'email', 'whatsapp'
    verification_token TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 3. Crear tabla de configuración de demo por usuario
CREATE TABLE IF NOT EXISTS user_demo_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    demo_type TEXT NOT NULL, -- 'expense_data', 'bank_data', 'invoice_data'
    config_data TEXT, -- JSON con preferencias específicas
    generated_records INTEGER DEFAULT 0,
    last_generated TIMESTAMP,
    tenant_id INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 4. Crear tabla de pasos de onboarding
CREATE TABLE IF NOT EXISTS onboarding_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_number INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    description TEXT,
    required BOOLEAN DEFAULT TRUE,
    active BOOLEAN DEFAULT TRUE,
    tenant_id INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- 5. Crear tabla de progreso de onboarding por usuario
CREATE TABLE IF NOT EXISTS user_onboarding_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'in_progress', 'completed', 'skipped'
    completed_at TIMESTAMP,
    metadata TEXT, -- JSON con datos específicos del paso
    tenant_id INTEGER DEFAULT 1,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES onboarding_steps(id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),

    UNIQUE(user_id, step_id)
);

-- 6. Índices para performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_identifier ON users(identifier);
CREATE INDEX IF NOT EXISTS idx_users_onboarding_step ON users(onboarding_step);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_verification ON users(verification_token);
CREATE INDEX IF NOT EXISTS idx_users_registration_method ON users(registration_method);

CREATE INDEX IF NOT EXISTS idx_user_demo_config_user ON user_demo_config(user_id);
CREATE INDEX IF NOT EXISTS idx_user_demo_config_type ON user_demo_config(demo_type);
CREATE INDEX IF NOT EXISTS idx_user_demo_config_tenant ON user_demo_config(tenant_id);

CREATE INDEX IF NOT EXISTS idx_onboarding_steps_number ON onboarding_steps(step_number);
CREATE INDEX IF NOT EXISTS idx_onboarding_steps_active ON onboarding_steps(active);
CREATE INDEX IF NOT EXISTS idx_onboarding_steps_tenant ON onboarding_steps(tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_progress_user ON user_onboarding_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_user_progress_status ON user_onboarding_progress(status);
CREATE INDEX IF NOT EXISTS idx_user_progress_tenant ON user_onboarding_progress(tenant_id);

-- 7. Insertar tenant por defecto
INSERT OR IGNORE INTO tenants (id, name, api_key)
VALUES (1, 'Default Tenant', 'default-api-key-123');

-- 8. Insertar pasos de onboarding por defecto
INSERT OR IGNORE INTO onboarding_steps (step_number, step_name, description, required, tenant_id) VALUES
(1, 'welcome', 'Bienvenida y configuración inicial', TRUE, 1),
(2, 'profile_setup', 'Configuración de perfil personal', TRUE, 1),
(3, 'company_setup', 'Configuración de empresa', TRUE, 1),
(4, 'demo_data', 'Generación de datos de demo', FALSE, 1),
(5, 'tour_features', 'Tour de funcionalidades principales', FALSE, 1),
(6, 'first_expense', 'Primer gasto de ejemplo', FALSE, 1);

-- 9. Vista consolidada para onboarding
CREATE VIEW IF NOT EXISTS onboarding_status_view AS
SELECT
    u.id as user_id,
    u.name,
    u.email,
    u.identifier,
    u.full_name,
    u.company_name,
    u.onboarding_step,
    u.onboarding_completed,
    u.registration_method,
    u.email_verified,
    u.phone_verified,
    u.demo_preferences,
    COUNT(uop.id) as completed_steps,
    MAX(os.step_number) as total_steps,
    CASE
        WHEN u.onboarding_completed = TRUE THEN 'completed'
        WHEN COUNT(uop.id) = 0 THEN 'not_started'
        WHEN COUNT(uop.id) < MAX(os.step_number) THEN 'in_progress'
        ELSE 'ready_to_complete'
    END as overall_status
FROM users u
CROSS JOIN (SELECT MAX(step_number) as step_number FROM onboarding_steps WHERE active = TRUE AND tenant_id = 1) os
LEFT JOIN user_onboarding_progress uop ON u.id = uop.user_id AND uop.status = 'completed'
WHERE u.tenant_id = 1
GROUP BY u.id;

PRAGMA foreign_keys = ON;