-- Migration 007: Add fields required by unified auth system
-- Date: 2025-11-09
-- Purpose: Add missing fields for unified authentication (username, is_superuser, etc.)

BEGIN;

-- Add missing authentication fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id INTEGER;

-- Rename 'name' to 'full_name' for consistency
-- First check if full_name exists, if not create it from name
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'full_name'
    ) THEN
        ALTER TABLE users ADD COLUMN full_name VARCHAR(255);
        UPDATE users SET full_name = name WHERE name IS NOT NULL;
    END IF;
END $$;

-- Create is_active as boolean from status
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
UPDATE users SET is_active = (status = 'active') WHERE is_active IS NULL;

-- Update username from email if not set
UPDATE users SET username = email WHERE username IS NULL;

-- Add unique constraint on username
CREATE UNIQUE INDEX IF NOT EXISTS users_username_key ON users(username);

-- Add comments
COMMENT ON COLUMN users.username IS 'Username for login (usually same as email)';
COMMENT ON COLUMN users.is_superuser IS 'Whether user has superuser privileges';
COMMENT ON COLUMN users.is_email_verified IS 'Whether email has been verified';
COMMENT ON COLUMN users.company_id IS 'Optional company/organization ID';
COMMENT ON COLUMN users.full_name IS 'Full name of the user';
COMMENT ON COLUMN users.is_active IS 'Boolean version of status field';

COMMIT;
