-- Migration 009: Add password reset fields
-- Date: 2025-11-09
-- Purpose: Add fields for password reset functionality

BEGIN;

-- Add password reset fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMP;

-- Create index for faster token lookups
CREATE INDEX IF NOT EXISTS idx_users_password_reset_token ON users(password_reset_token);

-- Add comments
COMMENT ON COLUMN users.password_reset_token IS 'Temporary token for password reset';
COMMENT ON COLUMN users.password_reset_expires_at IS 'Expiration timestamp for reset token';

COMMIT;
