#!/bin/bash
# Script para ejecutar tests localmente
# Fase 2.5 - CI/CD Pipeline

set -e

echo "🧪 Running tests..."
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Installing...${NC}"
    pip install pytest pytest-cov pytest-asyncio pytest-mock
fi

# Run tests with coverage
echo -e "${YELLOW}Running unit tests with coverage...${NC}"
pytest tests/ -v \
    --cov=core \
    --cov=api \
    --cov-report=html \
    --cov-report=term \
    --cov-report=xml \
    --tb=short \
    --maxfail=5 \
    || {
        echo -e "${RED}❌ Some tests failed${NC}"
        exit 1
    }

echo ""
echo -e "${GREEN}✅ All tests passed!${NC}"
echo ""
echo "📊 Coverage report generated:"
echo "  - HTML: htmlcov/index.html"
echo "  - XML: coverage.xml"
echo ""
echo "To view HTML report:"
echo "  open htmlcov/index.html"
