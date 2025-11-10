#!/bin/bash
#
# 📅 Verificación Mensual de CFDIs
# ================================
# Ejecuta este script el primer día de cada mes para verificar todos tus CFDIs con el SAT
#
# Uso: bash VERIFICAR_CFDIS_MENSUAL.sh
#

clear

echo "================================================================================"
echo "📅 VERIFICACIÓN MENSUAL DE CFDIs"
echo "================================================================================"
echo ""
echo "Este script verificará todos tus CFDIs con el SAT para detectar:"
echo "  ✓ Facturas canceladas por el proveedor"
echo "  ✓ Facturas sustituidas"
echo "  ✓ Facturas no encontradas en el SAT"
echo ""
echo "⏱️  Tiempo estimado: 4 minutos"
echo ""
read -p "¿Deseas continuar? (si/no): " CONFIRM

if [ "$CONFIRM" != "si" ] && [ "$CONFIRM" != "s" ]; then
    echo "❌ Operación cancelada"
    exit 0
fi

echo ""
echo "================================================================================"
echo "🔄 INICIANDO VERIFICACIÓN..."
echo "================================================================================"
echo ""

# Obtener directorio del script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Ejecutar verificación
python3 "$SCRIPT_DIR/scripts/utilities/reprocesar_cfdis_completo.py" --company-id 2 --verify-sat

EXIT_CODE=$?

echo ""
echo "================================================================================"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ VERIFICACIÓN COMPLETADA EXITOSAMENTE"
    echo "================================================================================"
    echo ""

    # Consultar si hay CFDIs inválidos
    echo "🔍 Consultando CFDIs inválidos..."
    INVALIDOS=$(psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -t -c "SELECT COUNT(*) FROM vw_cfdis_invalidos WHERE company_id = 2;" 2>/dev/null)

    if [ $? -eq 0 ]; then
        if [ "$INVALIDOS" -eq 0 ]; then
            echo ""
            echo "✅ ¡Excelente! Todos tus CFDIs están VIGENTES"
            echo ""
        else
            echo ""
            echo "⚠️  ATENCIÓN: Se encontraron $INVALIDOS CFDIs inválidos o cancelados"
            echo ""
            echo "Para ver el detalle, ejecuta:"
            echo "psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c \"SELECT uuid, nombre_emisor, sat_status FROM vw_cfdis_invalidos WHERE company_id = 2;\""
            echo ""
        fi
    fi

    echo "📊 Ver estadísticas completas:"
    echo "   http://localhost:8000/cfdi/stats?company_id=2"
    echo ""
    echo "📋 Próxima verificación recomendada: $(date -v+1m '+%d de %B, %Y')"
    echo ""
else
    echo "❌ ERROR EN LA VERIFICACIÓN"
    echo "================================================================================"
    echo ""
    echo "Por favor revisa los errores arriba."
    echo ""
fi

echo "================================================================================"
echo ""
