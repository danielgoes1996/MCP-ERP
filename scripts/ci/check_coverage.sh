#!/bin/bash
# Script para validar coverage mínimo
# Fase 2.5 - CI/CD Pipeline

set -e

MIN_COVERAGE=60  # Empezamos con 60%, meta 70%+

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "📊 Checking coverage..."
echo ""

# Install coverage if needed
if ! command -v coverage &> /dev/null; then
    pip install coverage pytest-cov
fi

# Run tests with coverage
pytest tests/ --cov=core --cov=api --cov-report=term --cov-report=xml -q

# Extract coverage percentage from the last line
COVERAGE=$(coverage report | grep "TOTAL" | awk '{print $4}' | sed 's/%//')

echo ""
echo "Coverage: ${COVERAGE}%"
echo "Minimum required: ${MIN_COVERAGE}%"
echo ""

# Compare coverage (bash doesn't do float comparison well, so we use awk)
if awk "BEGIN {exit !($COVERAGE >= $MIN_COVERAGE)}"; then
    echo -e "${GREEN}✅ Coverage ${COVERAGE}% meets minimum ${MIN_COVERAGE}%${NC}"

    # Bonus messages for good coverage
    if awk "BEGIN {exit !($COVERAGE >= 70)}"; then
        echo -e "${GREEN}🎉 Excellent coverage!${NC}"
    elif awk "BEGIN {exit !($COVERAGE >= 60)}"; then
        echo -e "${YELLOW}👍 Good coverage! Try to reach 70%${NC}"
    fi

    exit 0
else
    echo -e "${RED}❌ Coverage ${COVERAGE}% is below minimum ${MIN_COVERAGE}%${NC}"
    echo ""
    echo "To improve coverage:"
    echo "  1. Add more unit tests"
    echo "  2. Focus on untested modules"
    echo "  3. Run: coverage html && open htmlcov/index.html"
    exit 1
fi
