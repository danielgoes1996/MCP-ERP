-- ============================================
-- PostgreSQL Initialization Script
-- ============================================
-- This script runs automatically when the
-- database container is first created.
-- ============================================

-- Ensure UTF8 encoding
ALTER DATABASE mcp_system SET client_encoding TO 'UTF8';

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For GIN indexes

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE mcp_system TO mcp_user;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully at %', NOW();
END $$;
