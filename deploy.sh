#!/bin/bash

# =====================================================
# Production Deployment Script
# Despliega MV Refresh Strategy + Vertical System
# =====================================================

set -e  # Exit on error

ENVIRONMENT=${1:-staging}  # Default: staging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =====================================================
# Helper Functions
# =====================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 not found. Please install it first."
        exit 1
    fi
}

# =====================================================
# Pre-Deployment Checks
# =====================================================

pre_deployment_checks() {
    log_info "🔍 Running pre-deployment checks..."

    # Check required commands
    check_command psql
    check_command python3
    check_command curl
    check_command git

    # Check we're on correct branch
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$ENVIRONMENT" == "production" ] && [ "$CURRENT_BRANCH" != "main" ]; then
        log_error "Production deployments must be from 'main' branch"
        log_error "Current branch: $CURRENT_BRANCH"
        exit 1
    fi

    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        log_warn "You have uncommitted changes!"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    log_info "✅ Pre-deployment checks passed"
}

# =====================================================
# Run Tests
# =====================================================

run_tests() {
    log_info "🧪 Running critical tests..."

    cd "$SCRIPT_DIR"

    # Run shared logic tests (CRÍTICO)
    log_info "Running shared_logic tests..."
    python3 -m pytest tests/test_shared_logic.py -v --tb=short

    if [ $? -ne 0 ]; then
        log_error "❌ Critical tests failed!"
        log_error "shared_logic.py tests must pass before deployment"
        exit 1
    fi

    log_info "✅ All critical tests passed"
}

# =====================================================
# Database Connection
# =====================================================

get_db_config() {
    if [ "$ENVIRONMENT" == "production" ]; then
        export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
        export POSTGRES_PORT=${POSTGRES_PORT:-5433}
        export POSTGRES_DB=${POSTGRES_DB:-mcp_system}
        export POSTGRES_USER=${POSTGRES_USER:-mcp_user}
        export PGPASSWORD=${POSTGRES_PASSWORD:-changeme}
    else
        # Staging
        export POSTGRES_HOST=${POSTGRES_HOST_STAGING:-localhost}
        export POSTGRES_PORT=${POSTGRES_PORT_STAGING:-5434}
        export POSTGRES_DB=${POSTGRES_DB_STAGING:-mcp_system_staging}
        export POSTGRES_USER=${POSTGRES_USER_STAGING:-mcp_user}
        export PGPASSWORD=${POSTGRES_PASSWORD_STAGING:-changeme}
    fi

    log_info "Database: $POSTGRES_USER@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
}

test_db_connection() {
    log_info "🔌 Testing database connection..."

    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1;" > /dev/null 2>&1

    if [ $? -ne 0 ]; then
        log_error "❌ Cannot connect to database"
        log_error "Check your database credentials and ensure PostgreSQL is running"
        exit 1
    fi

    log_info "✅ Database connection successful"
}

# =====================================================
# Backup Database
# =====================================================

backup_database() {
    log_info "💾 Creating database backup..."

    BACKUP_DIR="$SCRIPT_DIR/backups"
    mkdir -p "$BACKUP_DIR"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/backup_${ENVIRONMENT}_${TIMESTAMP}.sql"

    pg_dump -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB > "$BACKUP_FILE"

    if [ $? -eq 0 ]; then
        log_info "✅ Backup created: $BACKUP_FILE"
        log_info "   Size: $(du -h $BACKUP_FILE | cut -f1)"
    else
        log_error "❌ Backup failed"
        exit 1
    fi
}

# =====================================================
# Apply Migrations
# =====================================================

apply_migrations() {
    log_info "🗄️  Applying migrations..."

    # Migration 062: CPG Retail Vertical
    log_info "Applying 062_cpg_retail_vertical_tables.sql..."
    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        < "$SCRIPT_DIR/migrations/062_cpg_retail_vertical_tables.sql"

    if [ $? -ne 0 ]; then
        log_error "❌ Migration 062 failed"
        exit 1
    fi

    # Migration 064: MV Refresh Strategy
    log_info "Applying 064_mv_refresh_strategy.sql..."
    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        < "$SCRIPT_DIR/migrations/064_mv_refresh_strategy.sql"

    if [ $? -ne 0 ]; then
        log_error "❌ Migration 064 failed"
        exit 1
    fi

    # Universal Transactions Model
    log_info "Applying 000_universal_transaction_model.sql..."
    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        < "$SCRIPT_DIR/migrations/verticals/000_universal_transaction_model.sql"

    if [ $? -ne 0 ]; then
        log_error "❌ Universal transactions model failed"
        exit 1
    fi

    log_info "✅ All migrations applied successfully"
}

# =====================================================
# Verify Migrations
# =====================================================

verify_migrations() {
    log_info "🔍 Verifying migrations..."

    # Verify cpg_pos table exists
    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        -c "\dt cpg_pos" | grep "cpg_pos" > /dev/null

    if [ $? -ne 0 ]; then
        log_error "❌ cpg_pos table not found"
        exit 1
    fi

    # Verify mv_refresh_log table exists
    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        -c "\dt mv_refresh_log" | grep "mv_refresh_log" > /dev/null

    if [ $? -ne 0 ]; then
        log_error "❌ mv_refresh_log table not found"
        exit 1
    fi

    # Verify universal_transactions_mv exists
    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        -c "\dm universal_transactions_mv" | grep "universal_transactions_mv" > /dev/null

    if [ $? -ne 0 ]; then
        log_error "❌ universal_transactions_mv not found"
        exit 1
    fi

    log_info "✅ All database objects verified"
}

# =====================================================
# Initial MV Refresh
# =====================================================

initial_mv_refresh() {
    log_info "🔄 Running initial MV refresh..."

    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        -c "SELECT * FROM refresh_universal_transactions_logged('deployment', 'deploy_script');"

    if [ $? -eq 0 ]; then
        log_info "✅ Initial MV refresh completed"
    else
        log_warn "⚠️  Initial MV refresh failed (may be expected if no data yet)"
    fi
}

# =====================================================
# Setup CRON Jobs (Optional)
# =====================================================

setup_cron_jobs() {
    log_info "⏰ Setting up CRON jobs..."

    # Check if pg_cron is installed
    psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        -c "SELECT 1 FROM pg_extension WHERE extname = 'pg_cron';" | grep -q 1

    if [ $? -eq 0 ]; then
        log_info "pg_cron is installed, setting up jobs..."

        # Schedule hourly refresh
        psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB <<EOF
            SELECT cron.schedule(
                'refresh-universal-transactions-hourly',
                '0 * * * *',
                \$\$SELECT refresh_universal_transactions_logged('cron', 'hourly_job')\$\$
            );

            SELECT cron.schedule(
                'process-mv-refresh-events',
                '*/5 * * * *',
                \$\$SELECT process_pending_mv_refreshes()\$\$
            );
EOF

        log_info "✅ CRON jobs configured"
    else
        log_warn "⚠️  pg_cron not installed, skipping CRON setup"
        log_warn "   You'll need to manually schedule MV refreshes"
    fi
}

# =====================================================
# Health Check
# =====================================================

health_check() {
    log_info "🏥 Running health check..."

    # Check MV health
    HEALTH=$(psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB \
        -t -c "SELECT jsonb_pretty(to_jsonb(mv_health_check.*)) FROM mv_health_check();")

    echo "$HEALTH"

    log_info "✅ Health check completed"
}

# =====================================================
# Test API Endpoint (if running)
# =====================================================

test_api() {
    log_info "🌐 Testing API endpoint..."

    API_URL=${API_URL:-http://localhost:8001}

    # Test health endpoint
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")

    if [ "$HTTP_CODE" == "200" ]; then
        log_info "✅ API is responding (HTTP $HTTP_CODE)"

        # Test MV health endpoint
        curl -s "$API_URL/api/v1/mv/health/universal-transactions" | python3 -m json.tool || true
    else
        log_warn "⚠️  API not responding or not running (HTTP $HTTP_CODE)"
        log_warn "   Make sure to restart the API server after deployment"
    fi
}

# =====================================================
# Deployment Summary
# =====================================================

deployment_summary() {
    echo ""
    echo "========================================"
    echo "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY"
    echo "========================================"
    echo ""
    echo "Environment: $ENVIRONMENT"
    echo "Database: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
    echo ""
    echo "✅ Migrations Applied:"
    echo "   - 062_cpg_retail_vertical_tables.sql"
    echo "   - 064_mv_refresh_strategy.sql"
    echo "   - 000_universal_transaction_model.sql"
    echo ""
    echo "✅ Database Objects Created:"
    echo "   - cpg_pos"
    echo "   - cpg_consignment"
    echo "   - mv_refresh_log"
    echo "   - universal_transactions_mv"
    echo ""
    echo "📋 Next Steps:"
    echo "   1. Restart API server: docker-compose restart backend"
    echo "   2. Verify API: curl $API_URL/health"
    echo "   3. Test MV refresh: curl -X POST $API_URL/api/v1/mv/refresh"
    echo "   4. Monitor logs: tail -f logs/app.log"
    echo ""
    echo "📊 Monitor MV freshness:"
    echo "   psql -c \"SELECT * FROM mv_health_check();\""
    echo ""
    echo "🔄 Manual MV refresh if needed:"
    echo "   psql -c \"SELECT refresh_universal_transactions_logged('manual', 'admin');\""
    echo ""
}

# =====================================================
# Rollback Function
# =====================================================

rollback() {
    log_error "🔙 Rolling back deployment..."

    # Restore from backup
    if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
        log_info "Restoring from backup: $BACKUP_FILE"
        psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB < "$BACKUP_FILE"
        log_info "✅ Rollback completed"
    else
        log_error "❌ No backup file found for rollback"
        log_error "   You may need to restore manually"
    fi
}

# =====================================================
# Main Deployment Flow
# =====================================================

main() {
    echo ""
    echo "========================================"
    echo "🚀 MCP SYSTEM DEPLOYMENT"
    echo "========================================"
    echo ""
    echo "Environment: $ENVIRONMENT"
    echo "Script: $(basename $0)"
    echo ""

    # Confirmation for production
    if [ "$ENVIRONMENT" == "production" ]; then
        log_warn "⚠️  YOU ARE DEPLOYING TO PRODUCTION!"
        read -p "Are you sure? Type 'yes' to continue: " -r
        echo
        if [ "$REPLY" != "yes" ]; then
            log_info "Deployment cancelled"
            exit 0
        fi
    fi

    # Execute deployment steps
    pre_deployment_checks
    run_tests
    get_db_config
    test_db_connection
    backup_database
    apply_migrations
    verify_migrations
    initial_mv_refresh
    setup_cron_jobs
    health_check
    test_api
    deployment_summary

    log_info "🎉 Deployment completed successfully!"
}

# Trap errors and rollback
trap 'rollback' ERR

# Run main
main

exit 0
