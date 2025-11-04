#!/bin/bash
# ============================================
# Docker Entrypoint Script
# ============================================
# This script prepares the environment and
# starts the FastAPI application
# ============================================

set -e

echo "🐳 Starting MCP Server..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h db -p 5432 -U mcp_user; do
    sleep 1
done
echo "✅ PostgreSQL is ready!"

# Wait for Redis to be ready
echo "⏳ Waiting for Redis..."
while ! redis-cli -h redis ping > /dev/null 2>&1; do
    sleep 1
done
echo "✅ Redis is ready!"

# Run database migrations (if using Alembic)
if [ -d "migrations" ]; then
    echo "🔄 Running database migrations..."
    alembic upgrade head || echo "⚠️  No migrations to run or migration failed"
fi

# Start the application
echo "🚀 Starting FastAPI application..."
exec "$@"
