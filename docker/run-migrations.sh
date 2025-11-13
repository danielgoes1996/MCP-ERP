#!/bin/bash
#
# Run all SQL migrations inside PostgreSQL container
# This applies the complete database schema from migrations/
#

set -e

echo "=================================================="
echo "PostgreSQL Schema Migration"
echo "=================================================="

CONTAINER_NAME="mcp-postgres"
DB_NAME="mcp_system"
DB_USER="mcp_user"
MIGRATIONS_DIR="/tmp/migrations"

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ PostgreSQL container is not running!"
    echo "Start it with: docker-compose up -d db"
    exit 1
fi

echo "✓ PostgreSQL container is running"

# Copy migrations directory to container
echo "📦 Copying migrations to container..."
docker cp ../migrations "$CONTAINER_NAME:/tmp/"

# Count migration files
MIGRATION_COUNT=$(docker exec $CONTAINER_NAME bash -c "ls -1 /tmp/migrations/*.sql | wc -l")
echo "📊 Found $MIGRATION_COUNT migration files"

# Apply migrations in order
echo ""
echo "=================================================="
echo "Applying migrations..."
echo "=================================================="

docker exec $CONTAINER_NAME bash -c "
cd /tmp/migrations
for sql_file in \$(ls *.sql | sort); do
    echo \"\"
    echo \"Applying: \$sql_file\"
    psql -U $DB_USER -d $DB_NAME -f \$sql_file 2>&1 | grep -v '^$' || true
done
"

echo ""
echo "=================================================="
echo "Verification"
echo "=================================================="

# Count tables
TABLE_COUNT=$(docker exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
echo "✓ Total tables in PostgreSQL: $TABLE_COUNT"

# List tables
echo ""
echo "Tables created:"
docker exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c "\dt" | head -30

echo ""
echo "=================================================="
echo "✓ Migration completed!"
echo "=================================================="
