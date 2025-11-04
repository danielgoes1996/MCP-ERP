-- SQLite Migration: Add audit_trail and ai_context_memory tables
-- Mirrors ContaFlow_DB_v2 schema adapted to SQLite capabilities

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad TEXT NOT NULL,
    entidad_id INTEGER,
    accion TEXT NOT NULL,
    usuario_id INTEGER,
    cambios TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_trail_entidad
    ON audit_trail(entidad);

CREATE INDEX IF NOT EXISTS idx_audit_trail_usuario
    ON audit_trail(usuario_id);

CREATE TABLE IF NOT EXISTS ai_context_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    created_by INTEGER,
    audit_log_id INTEGER,
    context TEXT,
    onboarding_snapshot TEXT,
    embedding_vector TEXT,
    model_name TEXT,
    source TEXT,
    language_detected TEXT,
    context_version INTEGER NOT NULL DEFAULT 1,
    summary TEXT,
    topics TEXT,
    confidence_score REAL,
    last_refresh DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (audit_log_id) REFERENCES audit_trail(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_context_memory_company_version
    ON ai_context_memory(company_id, context_version);

CREATE INDEX IF NOT EXISTS idx_ai_context_memory_created_by
    ON ai_context_memory(created_by);
