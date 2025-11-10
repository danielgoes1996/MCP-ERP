#!/bin/bash
# Script para ejecutar linters localmente
# Fase 2.5 - CI/CD Pipeline

set -e

echo "🔍 Running linters..."
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

FAILED=0

# Install tools if needed
if ! command -v flake8 &> /dev/null; then
    echo "Installing linting tools..."
    pip install flake8 black isort
fi

# Run flake8
echo -e "${YELLOW}Running flake8...${NC}"
if flake8 core/ api/ app/ --max-line-length=120 --statistics; then
    echo -e "${GREEN}✅ flake8 passed${NC}"
else
    echo -e "${RED}❌ flake8 found issues${NC}"
    FAILED=1
fi
echo ""

# Check black formatting
echo -e "${YELLOW}Checking black formatting...${NC}"
if black --check core/ api/ app/ --line-length=120; then
    echo -e "${GREEN}✅ black formatting check passed${NC}"
else
    echo -e "${RED}❌ black found formatting issues${NC}"
    echo "Run: black core/ api/ app/ --line-length=120 to fix"
    FAILED=1
fi
echo ""

# Check isort
echo -e "${YELLOW}Checking isort...${NC}"
if isort --check-only core/ api/ app/ --profile black; then
    echo -e "${GREEN}✅ isort check passed${NC}"
else
    echo -e "${RED}❌ isort found issues${NC}"
    echo "Run: isort core/ api/ app/ --profile black to fix"
    FAILED=1
fi
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All linters passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some linters failed${NC}"
    exit 1
fi
