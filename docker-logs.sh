#!/bin/bash
# ============================================
# Docker Logs Script
# ============================================

SERVICE=${1:-all}

if [ "$SERVICE" = "all" ]; then
    echo "📝 Showing logs for all services..."
    docker-compose logs -f
else
    echo "📝 Showing logs for: $SERVICE"
    docker-compose logs -f $SERVICE
fi
