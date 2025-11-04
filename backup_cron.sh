#!/bin/bash
# MCP Database Backup Script
cd /Users/danielgoes96/Desktop/mcp-server

# Backup diario a las 2 AM
python3 simple_backup.py daily

# Limpieza semanal los domingos a las 3 AM
if [ "$(date +%u)" = "7" ]; then
    python3 simple_backup.py cleanup
fi
