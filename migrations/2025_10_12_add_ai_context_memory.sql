-- Migration: Add audit_trail and ai_context_memory tables aligned with ContaFlow_DB_v2 schema
-- Ensures pgvector extension is available and creates required indexes

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
END
$$;

CREATE TABLE IF NOT EXISTS audit_trail (
    id BIGSERIAL PRIMARY KEY,
    entidad TEXT NOT NULL,
    entidad_id BIGINT,
    accion TEXT NOT NULL,
    usuario_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    cambios JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_trail_entidad
    ON audit_trail(entidad);

CREATE INDEX IF NOT EXISTS idx_audit_trail_usuario
    ON audit_trail(usuario_id);

CREATE TABLE IF NOT EXISTS ai_context_memory (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    audit_log_id BIGINT REFERENCES audit_trail(id) ON DELETE SET NULL,
    context JSONB,
    onboarding_snapshot JSONB,
    embedding_vector VECTOR(1536),
    model_name TEXT,
    source TEXT,
    language_detected TEXT,
    context_version INTEGER NOT NULL DEFAULT 1,
    summary TEXT,
    topics JSONB,
    confidence_score REAL,
    last_refresh TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_context_memory_company_version
    ON ai_context_memory(company_id, context_version DESC);

CREATE INDEX IF NOT EXISTS idx_ai_context_memory_created_by
    ON ai_context_memory(created_by);

CREATE INDEX IF NOT EXISTS idx_ai_context_memory_embedding_vector
    ON ai_context_memory USING ivfflat (embedding_vector vector_cosine_ops)
    WITH (lists = 100);
