#!/bin/bash
# Check Docker Status
# Run this to see if Docker Desktop is ready

echo "Checking Docker status..."
echo ""

if docker info > /dev/null 2>&1; then
    echo "✓ Docker is running!"
    echo ""
    echo "Docker containers:"
    docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "mcp-|NAMES"
    echo ""
    echo "You can now run:"
    echo "  ./scripts/setup_fresh_postgresql.sh"
else
    echo "✗ Docker is NOT running"
    echo ""
    echo "Please open Docker Desktop and wait for it to start."
    echo "Then run this script again to check status."
fi
echo ""
