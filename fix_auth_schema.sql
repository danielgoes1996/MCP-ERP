-- REPARACIÓN DEL ESQUEMA DE AUTENTICACIÓN
-- Completa la tabla users para autenticación real

-- Agregar campos faltantes para autenticación
ALTER TABLE users ADD COLUMN password_hash TEXT;
ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN locked_until TIMESTAMP;

-- Actualizar columna name para ser más descriptiva
-- SQLite no soporta RENAME COLUMN directamente, usamos recreación
CREATE TABLE users_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    password_hash TEXT,
    tenant_id INTEGER,
    role TEXT DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Migrar datos existentes
INSERT INTO users_new (id, email, full_name, tenant_id, role, created_at)
SELECT id, email, name, tenant_id, role, created_at FROM users;

-- Reemplazar tabla original
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

-- Recrear índices
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_active ON users(is_active);

-- Crear tabla para tokens de refresh
CREATE TABLE refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at);

-- Tabla para sesiones activas (opcional)
CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id TEXT UNIQUE NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_id ON user_sessions(session_id);
CREATE INDEX idx_sessions_active ON user_sessions(is_active);

-- Actualizar usuario existente con password
UPDATE users
SET password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeYiGnQ98bJUOGCOG', -- password: admin123
    is_superuser = TRUE,
    full_name = 'Admin TAFY',
    is_active = TRUE
WHERE email = 'admin@tafy.com';

-- Insertar usuario demo adicional
INSERT INTO users (email, full_name, password_hash, tenant_id, role, is_active, is_superuser)
VALUES (
    'demo@tafy.com',
    'Demo User',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeYiGnQ98bJUOGCOG', -- password: demo123
    1,
    'user',
    TRUE,
    FALSE
);

-- Actualizar versión del schema
UPDATE schema_versions
SET version = '1.1.0',
    description = 'Authentication Schema Complete - Users, Tokens, Sessions'
WHERE version = '1.0.0';

-- Insertar nueva versión si no existe
INSERT OR IGNORE INTO schema_versions (version, description)
VALUES ('1.1.0', 'Authentication Schema Complete - Users, Tokens, Sessions');