#!/bin/bash
# Setup Fresh PostgreSQL Environment
# This script initializes PostgreSQL with fresh data for testing

set -e

echo "=================================="
echo "PostgreSQL Fresh Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check Docker is running
echo -e "${YELLOW}[1/6]${NC} Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Docker is not running"
    echo ""
    echo "Please start Docker Desktop and run this script again."
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker is running"
echo ""

# Step 2: Start containers
echo -e "${YELLOW}[2/6]${NC} Starting PostgreSQL and Redis containers..."
cd /Users/danielgoes96/Desktop/mcp-server
docker-compose up -d db redis
echo ""

# Step 3: Wait for PostgreSQL to be ready
echo -e "${YELLOW}[3/6]${NC} Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec mcp-postgres pg_isready -U mcp_user -d mcp_system > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} PostgreSQL is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗${NC} PostgreSQL failed to start"
    exit 1
fi
echo ""

# Step 4: Run migrations
echo -e "${YELLOW}[4/6]${NC} Running database migrations..."
python3 scripts/migration/apply_migrations_postgres.py
echo -e "${GREEN}✓${NC} Migrations complete"
echo ""

# Step 5: Create user and company
echo -e "${YELLOW}[5/6]${NC} Creating user account..."
python3 << 'EOF'
import psycopg2
from passlib.hash import bcrypt
import uuid
from datetime import datetime

conn = psycopg2.connect(
    host='127.0.0.1',
    port=5433,
    database='mcp_system',
    user='mcp_user',
    password='changeme'
)
cursor = conn.cursor()

try:
    # Check if company exists
    cursor.execute("SELECT id FROM companies WHERE company_id = 'carreta_verde'")
    result = cursor.fetchone()

    if result:
        company_id = result[0]
        print(f"   Company 'carreta_verde' already exists (ID: {company_id})")
    else:
        # Create company
        company_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO companies (id, company_id, name, rfc, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            company_id,
            'carreta_verde',
            'Carreta Verde',
            'POL210218264',
            datetime.utcnow(),
            datetime.utcnow()
        ))
        print(f"   Created company 'Carreta Verde' (ID: {company_id})")

    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE email = 'daniel@carretaverde.com'")
    result = cursor.fetchone()

    if result:
        # Update existing user
        user_id = result[0]
        hashed_password = bcrypt.hash('password123')
        cursor.execute("""
            UPDATE users
            SET password_hash = %s,
                company_id = %s,
                updated_at = %s
            WHERE id = %s
        """, (hashed_password, company_id, datetime.utcnow(), user_id))
        print(f"   Updated user 'daniel@carretaverde.com' (ID: {user_id})")
    else:
        # Create new user
        user_id = str(uuid.uuid4())
        hashed_password = bcrypt.hash('password123')
        cursor.execute("""
            INSERT INTO users (id, email, password_hash, name, company_id, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            'daniel@carretaverde.com',
            hashed_password,
            'Daniel',
            company_id,
            True,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        print(f"   Created user 'daniel@carretaverde.com' (ID: {user_id})")

    conn.commit()
    print("")
    print("   Credentials:")
    print("   Email: daniel@carretaverde.com")
    print("   Password: password123")

except Exception as e:
    conn.rollback()
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cursor.close()
    conn.close()
EOF
echo ""

# Step 6: Verify system
echo -e "${YELLOW}[6/6]${NC} Verifying system..."

# Check PostgreSQL connection
python3 << 'EOF'
import psycopg2
try:
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=5433,
        database='mcp_system',
        user='mcp_user',
        password='changeme'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM companies")
    company_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sat_invoices")
    invoice_count = cursor.fetchone()[0]

    print(f"   Users: {user_count}")
    print(f"   Companies: {company_count}")
    print(f"   Invoices: {invoice_count}")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"   Error: {e}")
EOF

echo ""
echo -e "${GREEN}=================================="
echo "Setup Complete!"
echo "==================================${NC}"
echo ""
echo "Your system is ready for fresh invoice uploads:"
echo ""
echo "1. Frontend: http://localhost:3000"
echo "2. Backend API: http://localhost:8001"
echo "3. PostgreSQL: localhost:5433"
echo "4. PgAdmin (optional): http://localhost:5050"
echo ""
echo "Login credentials:"
echo "  Email: daniel@carretaverde.com"
echo "  Password: password123"
echo ""
echo "You can now upload invoices and test the complete pipeline!"
echo ""
