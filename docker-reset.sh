#!/bin/bash
# ============================================
# Docker Reset Script
# ============================================
# DANGER: This removes all containers,
# volumes, and data. Use with caution!
# ============================================

set -e

echo "⚠️  WARNING: This will delete all Docker data!"
echo "   - All containers will be removed"
echo "   - All volumes will be deleted"
echo "   - All database data will be lost"
echo ""
read -p "Are you sure? (type 'yes' to continue): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "❌ Cancelled"
    exit 1
fi

echo "🗑️  Removing containers and volumes..."
docker-compose down -v

echo "🧹 Removing Docker images..."
docker-compose rm -f

echo ""
echo "✅ Reset complete! All data has been deleted."
echo ""
echo "💡 Run ./docker-start.sh to start fresh"
echo ""
