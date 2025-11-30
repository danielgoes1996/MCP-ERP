#!/bin/bash
# =============================================================================
# Script para Desactivar SQLite Completamente
# =============================================================================
# Este script desactiva el uso de SQLite después de la migración a PostgreSQL
# Fecha: 2024-11-28

set -e

echo "============================================================="
echo "DESACTIVACIÓN DE SQLITE - Sistema Migrado a PostgreSQL"
echo "============================================================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar que estamos en el directorio correcto
if [ ! -f "migrations/002_tickets_merchants_adapted.sql" ]; then
    echo -e "${RED}Error: Este script debe ejecutarse desde el directorio raíz del proyecto${NC}"
    exit 1
fi

echo -e "${YELLOW}IMPORTANTE:${NC} Este script desactivará SQLite completamente."
echo "Asegúrate de que:"
echo "  1. La migración a PostgreSQL está completa"
echo "  2. Todos los tests pasan con PostgreSQL"
echo "  3. Has hecho backup de tus datos"
echo ""
read -p "¿Continuar? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Operación cancelada."
    exit 0
fi

echo ""
echo "=== PASO 1: Hacer backup de SQLite ==="

# Crear directorio de backups si no existe
mkdir -p backups/sqlite_legacy

# Backup del archivo SQLite
if [ -f "data/mcp_internal.db" ]; then
    echo "Copiando data/mcp_internal.db a backups/sqlite_legacy/"
    cp data/mcp_internal.db backups/sqlite_legacy/mcp_internal.db.backup.$(date +%Y%m%d_%H%M%S)
    echo -e "${GREEN}✓ Backup creado${NC}"
else
    echo -e "${YELLOW}! SQLite database no encontrado${NC}"
fi

echo ""
echo "=== PASO 2: Renombrar base de datos SQLite ==="

if [ -f "data/mcp_internal.db" ]; then
    mv data/mcp_internal.db data/mcp_internal.db.DISABLED
    echo -e "${GREEN}✓ data/mcp_internal.db → data/mcp_internal.db.DISABLED${NC}"
fi

echo ""
echo "=== PASO 3: Crear archivo de notificación ==="

cat > data/SQLITE_DISABLED.txt << 'EOF'
=============================================================================
SQLITE HA SIDO DESACTIVADO
=============================================================================

Este sistema ha sido migrado completamente a PostgreSQL.

Fecha de migración: 2024-11-28

ARCHIVOS DESACTIVADOS:
- data/mcp_internal.db → data/mcp_internal.db.DISABLED

NUEVA BASE DE DATOS:
- PostgreSQL (127.0.0.1:5433)
- Database: mcp_system
- tenant_id: 3

ARCHIVOS DE CÓDIGO:
- modules/invoicing_agent/models.py → PostgreSQL (activo)
- modules/invoicing_agent/models_sqlite_LEGACY.py → SQLite (legacy)

CATÁLOGO DE MERCHANTS:
- 24 merchants mexicanos en PostgreSQL
- Ver: migrations/003_seed_merchants_catalog.sql

DOCUMENTACIÓN:
- MERCHANT_SYSTEM_DOCS.md → Documentación completa del sistema

BACKUP DE SQLITE:
- backups/sqlite_legacy/

Para revertir (NO RECOMENDADO):
  1. mv data/mcp_internal.db.DISABLED data/mcp_internal.db
  2. cd modules/invoicing_agent
  3. mv models.py models_postgres_NEW.py
  4. mv models_sqlite_LEGACY.py models.py

Contacto: Equipo de Desarrollo
=============================================================================
EOF

echo -e "${GREEN}✓ Creado data/SQLITE_DISABLED.txt${NC}"

echo ""
echo "=== PASO 4: Actualizar archivo de configuración SQLite ==="

# Renombrar core/internal_db.py si existe
if [ -f "core/internal_db.py" ]; then
    if ! grep -q "DEPRECATED" core/internal_db.py; then
        # Agregar advertencia al inicio del archivo
        cat > /tmp/internal_db_header.py << 'EOF'
"""
⚠️  DEPRECATED - ESTE MÓDULO USA SQLITE (LEGACY)
=============================================================================
Este módulo ha sido deprecado. El sistema ahora usa PostgreSQL.

Para nuevos desarrollos, usar:
  - modules/invoicing_agent/models.py (PostgreSQL)
  - core/shared/db_config.py (PostgreSQL connection)

Este archivo se mantiene solo para compatibilidad con código legacy.
=============================================================================
"""

EOF
        cat /tmp/internal_db_header.py core/internal_db.py > /tmp/internal_db_new.py
        mv /tmp/internal_db_new.py core/internal_db.py
        echo -e "${GREEN}✓ Agregada advertencia de deprecación a core/internal_db.py${NC}"
        rm /tmp/internal_db_header.py
    fi
fi

echo ""
echo "=== PASO 5: Verificar estado de PostgreSQL ==="

# Verificar que PostgreSQL está funcionando
if command -v psql &> /dev/null; then
    echo "Verificando conexión a PostgreSQL..."
    PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "SELECT COUNT(*) FROM merchants" &> /dev/null
    if [ $? -eq 0 ]; then
        MERCHANT_COUNT=$(PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -t -c "SELECT COUNT(*) FROM merchants WHERE tenant_id = 3")
        echo -e "${GREEN}✓ PostgreSQL funcionando correctamente${NC}"
        echo "  Merchants en tenant_id=3: $MERCHANT_COUNT"
    else
        echo -e "${RED}✗ No se pudo conectar a PostgreSQL${NC}"
        echo -e "${YELLOW}  Verifica que PostgreSQL esté corriendo${NC}"
    fi
else
    echo -e "${YELLOW}! psql no está instalado, saltando verificación${NC}"
fi

echo ""
echo "============================================================="
echo -e "${GREEN}✓ SQLITE DESACTIVADO EXITOSAMENTE${NC}"
echo "============================================================="
echo ""
echo "RESUMEN:"
echo "  ✓ Backup creado en backups/sqlite_legacy/"
echo "  ✓ SQLite database renombrado a .DISABLED"
echo "  ✓ Archivo de notificación creado"
echo "  ✓ Advertencias de deprecación agregadas"
echo ""
echo "PRÓXIMOS PASOS:"
echo "  1. Ejecutar tests para verificar funcionamiento"
echo "  2. Monitorear logs en producción"
echo "  3. Después de 30 días sin issues, eliminar archivos .DISABLED"
echo ""
echo "Para revertir: ver data/SQLITE_DISABLED.txt"
echo "============================================================="
