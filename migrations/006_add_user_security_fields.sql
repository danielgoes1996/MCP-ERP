-- Migration 006: Add security and additional user fields
-- Date: 2025-11-09
-- Purpose: Enhance user table with security features and additional metadata

BEGIN;

-- Add security fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;

-- Add user profile fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);

-- Add onboarding/preferences fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'::jsonb;

-- Add comments for documentation
COMMENT ON COLUMN users.failed_login_attempts IS 'Number of consecutive failed login attempts';
COMMENT ON COLUMN users.locked_until IS 'Account locked until this timestamp due to failed login attempts';
COMMENT ON COLUMN users.last_login IS 'Timestamp of last successful login';
COMMENT ON COLUMN users.employee_id IS 'Optional reference to employee record';
COMMENT ON COLUMN users.phone IS 'Phone number for account recovery';
COMMENT ON COLUMN users.avatar_url IS 'URL to user profile picture';
COMMENT ON COLUMN users.onboarding_completed IS 'Whether user completed onboarding flow';
COMMENT ON COLUMN users.preferences IS 'User preferences (theme, language, notifications, etc.)';

-- Create index for locked accounts lookup
CREATE INDEX IF NOT EXISTS idx_users_locked_until ON users(locked_until) WHERE locked_until IS NOT NULL;

-- Create index for last login analytics
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);

COMMIT;
