-- Migration 010: Add email verification fields
-- Date: 2025-11-09
-- Purpose: Add fields for email verification functionality

BEGIN;

-- Add email verification fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token_expires_at TIMESTAMP;

-- Create index for faster token lookups
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token);

-- Add comments
COMMENT ON COLUMN users.verification_token IS 'Temporary token for email verification';
COMMENT ON COLUMN users.verification_token_expires_at IS 'Expiration timestamp for verification token';

COMMIT;
