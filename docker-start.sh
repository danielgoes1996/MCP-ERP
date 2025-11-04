#!/bin/bash
# ============================================
# Docker Quick Start Script
# ============================================
# Quick script to start the entire stack
# ============================================

set -e

echo "🐳 Starting MCP Server Docker Stack..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env and configure your settings before production use!"
    echo ""
fi

# Start services
echo "🚀 Starting Docker Compose services..."
docker-compose up -d

echo ""
echo "✅ Services started successfully!"
echo ""
echo "📊 Service URLs:"
echo "   API:     http://localhost:8000"
echo "   Docs:    http://localhost:8000/docs"
echo "   PgAdmin: http://localhost:5050"
echo ""
echo "📝 View logs with: docker-compose logs -f"
echo "🛑 Stop with:      docker-compose down"
echo ""
