#!/bin/bash
# ============================================
# Master Migration Script
# SQLite → PostgreSQL Complete Migration
# ============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SQLITE_DB="${SQLITE_DB:-unified_mcp_system.db}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-mcp_system}"
POSTGRES_USER="${POSTGRES_USER:-mcp_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-changeme}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🐘 SQLite → PostgreSQL Migration${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if SQLite database exists
if [ ! -f "$PROJECT_ROOT/$SQLITE_DB" ]; then
    echo -e "${RED}❌ Error: SQLite database not found: $SQLITE_DB${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found SQLite database: $SQLITE_DB${NC}"

# Check PostgreSQL connection
echo ""
echo -e "${YELLOW}⏳ Checking PostgreSQL connection...${NC}"

export PGPASSWORD="$POSTGRES_PASSWORD"
if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; then
    echo -e "${GREEN}✅ PostgreSQL connection successful${NC}"
else
    echo -e "${RED}❌ Error: Cannot connect to PostgreSQL${NC}"
    echo -e "${YELLOW}💡 Make sure Docker is running: ./docker-start.sh${NC}"
    exit 1
fi

# Backup SQLite database
echo ""
echo -e "${YELLOW}📦 Creating backup of SQLite database...${NC}"
BACKUP_FILE="$PROJECT_ROOT/backups/sqlite_backup_$(date +%Y%m%d_%H%M%S).db"
mkdir -p "$PROJECT_ROOT/backups"
cp "$PROJECT_ROOT/$SQLITE_DB" "$BACKUP_FILE"
echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"

# Step 1: Extract SQLite schema
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}📋 Step 1: Extract SQLite Schema${NC}"
echo -e "${BLUE}============================================${NC}"

cd "$PROJECT_ROOT"
python3 "$SCRIPT_DIR/extract_sqlite_schema.py" "$SQLITE_DB" "$SCRIPT_DIR/sqlite_schema.json"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to extract schema${NC}"
    exit 1
fi

# Step 2: Convert to PostgreSQL
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔄 Step 2: Convert to PostgreSQL Schema${NC}"
echo -e "${BLUE}============================================${NC}"

python3 "$SCRIPT_DIR/convert_to_postgres.py" \
    "$SCRIPT_DIR/sqlite_schema.json" \
    "$SCRIPT_DIR/postgres_schema.sql"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to convert schema${NC}"
    exit 1
fi

# Step 3: Create PostgreSQL schema
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🏗️  Step 3: Create PostgreSQL Schema${NC}"
echo -e "${BLUE}============================================${NC}"

echo -e "${YELLOW}⏳ Dropping existing tables if any...${NC}"
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true

echo -e "${YELLOW}⏳ Creating tables, indexes, and views...${NC}"
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -f "$SCRIPT_DIR/postgres_schema.sql"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create PostgreSQL schema${NC}"
    exit 1
fi

echo -e "${GREEN}✅ PostgreSQL schema created successfully${NC}"

# Step 4: Migrate data
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}📊 Step 4: Migrate Data${NC}"
echo -e "${BLUE}============================================${NC}"

export SQLITE_DB="$SQLITE_DB"
export POSTGRES_HOST="$POSTGRES_HOST"
export POSTGRES_PORT="$POSTGRES_PORT"
export POSTGRES_DB="$POSTGRES_DB"
export POSTGRES_USER="$POSTGRES_USER"
export POSTGRES_PASSWORD="$POSTGRES_PASSWORD"

python3 "$SCRIPT_DIR/migrate_data.py"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Data migration failed${NC}"
    echo -e "${YELLOW}💡 Check errors above. Database schema is preserved.${NC}"
    exit 1
fi

# Step 5: Validate migration
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}✔️  Step 5: Validate Migration${NC}"
echo -e "${BLUE}============================================${NC}"

python3 "$SCRIPT_DIR/validate_migration.py"

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Validation warnings detected${NC}"
    echo -e "${YELLOW}💡 Review validation output above${NC}"
else
    echo -e "${GREEN}✅ Validation passed!${NC}"
fi

# Success
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✅ Migration Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${GREEN}📊 Summary:${NC}"
echo -e "   SQLite DB: $SQLITE_DB"
echo -e "   PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
echo -e "   Backup: $BACKUP_FILE"
echo ""
echo -e "${YELLOW}🔧 Next Steps:${NC}"
echo -e "   1. Update .env file:"
echo -e "      DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
echo ""
echo -e "   2. Restart your application:"
echo -e "      ./docker-start.sh"
echo ""
echo -e "   3. Run tests to verify everything works:"
echo -e "      docker-compose exec api pytest"
echo ""
