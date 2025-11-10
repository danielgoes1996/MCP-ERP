-- Migration 008: Create refresh_tokens table
-- Date: 2025-11-09
-- Purpose: Store JWT refresh tokens for unified auth system

BEGIN;

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP,
    last_used_at TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_tenant_id ON refresh_tokens(tenant_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

-- Add comments
COMMENT ON TABLE refresh_tokens IS 'JWT refresh tokens for user authentication';
COMMENT ON COLUMN refresh_tokens.user_id IS 'User who owns this refresh token';
COMMENT ON COLUMN refresh_tokens.tenant_id IS 'Tenant context for this token';
COMMENT ON COLUMN refresh_tokens.token_hash IS 'SHA256 hash of the refresh token';
COMMENT ON COLUMN refresh_tokens.expires_at IS 'When this token expires';
COMMENT ON COLUMN refresh_tokens.revoked_at IS 'When this token was revoked (if applicable)';
COMMENT ON COLUMN refresh_tokens.last_used_at IS 'Last time this token was used to refresh';

COMMIT;
