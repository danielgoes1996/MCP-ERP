#!/bin/bash
#
# Setup Monthly CFDI Verification
# ================================
# Este script configura la verificación automática mensual de CFDIs
#

echo "================================================================================"
echo "🔧 CONFIGURACIÓN DE VERIFICACIÓN MENSUAL AUTOMÁTICA"
echo "================================================================================"
echo ""

# Rutas
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
VERIFICATION_SCRIPT="$PROJECT_DIR/scripts/utilities/reprocesar_cfdis_completo.py"
LOG_FILE="/tmp/cfdi_monthly_verification.log"

echo "📁 Directorio del proyecto: $PROJECT_DIR"
echo "📄 Script de verificación: $VERIFICATION_SCRIPT"
echo "📋 Log file: $LOG_FILE"
echo ""

# Verificar que el script existe
if [ ! -f "$VERIFICATION_SCRIPT" ]; then
    echo "❌ ERROR: No se encontró el script de verificación"
    echo "   Ruta esperada: $VERIFICATION_SCRIPT"
    exit 1
fi

# Crear el cron job
CRON_JOB="0 2 1 * * cd $PROJECT_DIR && python3 $VERIFICATION_SCRIPT --company-id 2 --verify-sat >> $LOG_FILE 2>&1"

echo "🔍 Verificando cron jobs actuales..."

# Verificar si ya existe
if crontab -l 2>/dev/null | grep -q "reprocesar_cfdis_completo.py"; then
    echo "⚠️  Ya existe un cron job para verificación de CFDIs"
    echo ""
    echo "Cron job actual:"
    crontab -l | grep "reprocesar_cfdis_completo.py"
    echo ""
    read -p "¿Deseas reemplazarlo? (si/no): " REPLACE

    if [ "$REPLACE" != "si" ] && [ "$REPLACE" != "s" ]; then
        echo "❌ Operación cancelada"
        exit 0
    fi

    # Remover el cron job anterior
    crontab -l | grep -v "reprocesar_cfdis_completo.py" | crontab -
    echo "✅ Cron job anterior removido"
fi

# Agregar el nuevo cron job
echo ""
echo "📝 Agregando nuevo cron job..."
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Cron job agregado exitosamente"
else
    echo "❌ Error agregando cron job"
    exit 1
fi

echo ""
echo "================================================================================"
echo "✅ CONFIGURACIÓN COMPLETADA"
echo "================================================================================"
echo ""
echo "📅 Programación:"
echo "   Frecuencia: Mensual (día 1 a las 2:00 AM)"
echo "   Comando: python3 reprocesar_cfdis_completo.py --company-id 2 --verify-sat"
echo "   Log: $LOG_FILE"
echo ""
echo "🔍 Cron jobs actuales:"
crontab -l
echo ""
echo "================================================================================"
echo ""
echo "📝 Comandos útiles:"
echo ""
echo "   Ver logs:"
echo "   tail -f $LOG_FILE"
echo ""
echo "   Ver cron jobs:"
echo "   crontab -l"
echo ""
echo "   Ejecutar manualmente:"
echo "   python3 $VERIFICATION_SCRIPT --company-id 2 --verify-sat"
echo ""
echo "   Desactivar (remover cron job):"
echo "   crontab -e  # y eliminar la línea"
echo ""
echo "🎯 Próxima ejecución: 1 de $(date -v+1m '+%B %Y') a las 2:00 AM"
echo ""
