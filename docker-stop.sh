#!/bin/bash
# ============================================
# Docker Stop Script
# ============================================

set -e

echo "🛑 Stopping MCP Server Docker Stack..."

docker-compose down

echo ""
echo "✅ All services stopped!"
echo ""
echo "💡 Data is preserved in Docker volumes."
echo "   To remove volumes too, use: docker-compose down -v"
echo ""
