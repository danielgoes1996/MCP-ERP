#!/bin/bash
#
# 🚀 Setup Completo - Verificación y Extracción Automática
# ========================================================
# Configura dos procesos automáticos:
# 1. Extracción semanal de facturas nuevas del SAT (cada lunes)
# 2. Verificación mensual de CFDIs existentes (día 1 de cada mes)
#

clear

echo "================================================================================"
echo "🚀 SETUP COMPLETO - SISTEMA AUTOMÁTICO DE FACTURAS"
echo "================================================================================"
echo ""
echo "Este script configurará:"
echo ""
echo "  📥 EXTRACCIÓN SEMANAL (cada lunes a las 3:00 AM)"
echo "     → Descarga facturas nuevas de los últimos 7 días"
echo "     → Para TODAS las compañías activas"
echo "     → Desde el portal del SAT"
echo ""
echo "  ✅ VERIFICACIÓN MENSUAL (día 1 a las 2:00 AM)"
echo "     → Verifica estado de CFDIs existentes"
echo "     → Detecta facturas canceladas"
echo "     → Con verificación real en el SAT"
echo ""
echo "⏱️  Tiempo estimado de configuración: 3 minutos"
echo ""
read -p "¿Deseas continuar? (si/no): " CONFIRM

if [ "$CONFIRM" != "si" ] && [ "$CONFIRM" != "s" ]; then
    echo "❌ Operación cancelada"
    exit 0
fi

# Obtener directorio del proyecto
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXTRACTION_SCRIPT="$SCRIPT_DIR/scripts/utilities/extraer_facturas_nuevas.py"
VERIFICATION_SCRIPT="$SCRIPT_DIR/scripts/utilities/verificar_todas_companias.py"
LOG_DIR="/var/log"
EXTRACTION_LOG="$LOG_DIR/cfdi_extraction.log"
VERIFICATION_LOG="$LOG_DIR/cfdi_verification.log"

echo ""
echo "================================================================================"
echo "PASO 1/4: Verificando scripts"
echo "================================================================================"
echo ""

# Verificar que los scripts existen
if [ ! -f "$EXTRACTION_SCRIPT" ]; then
    echo "❌ ERROR: No se encontró el script de extracción"
    echo "   Ruta esperada: $EXTRACTION_SCRIPT"
    exit 1
fi

if [ ! -f "$VERIFICATION_SCRIPT" ]; then
    echo "❌ ERROR: No se encontró el script de verificación"
    echo "   Ruta esperada: $VERIFICATION_SCRIPT"
    exit 1
fi

echo "✅ Script de extracción encontrado"
echo "✅ Script de verificación encontrado"

# Verificar permisos de escritura en log
if [ ! -w "$LOG_DIR" ]; then
    echo "⚠️  No hay permisos para escribir en $LOG_DIR"
    echo "   Usando directorio temporal: /tmp"
    EXTRACTION_LOG="/tmp/cfdi_extraction.log"
    VERIFICATION_LOG="/tmp/cfdi_verification.log"
fi

echo "✅ Log extracción: $EXTRACTION_LOG"
echo "✅ Log verificación: $VERIFICATION_LOG"

# Hacer los scripts ejecutables
chmod +x "$EXTRACTION_SCRIPT"
chmod +x "$VERIFICATION_SCRIPT"
echo "✅ Permisos configurados"

echo ""
echo "================================================================================"
echo "PASO 2/4: Testeando extracción"
echo "================================================================================"
echo ""

echo "🔍 Ejecutando test de extracción en modo DRY-RUN..."
python3 "$EXTRACTION_SCRIPT" --ultimos-7-dias --dry-run

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: El test de extracción falló"
    echo "   Por favor revisa los errores arriba"
    exit 1
fi

echo ""
echo "✅ Test de extracción completado exitosamente"

echo ""
echo "================================================================================"
echo "PASO 3/4: Testeando verificación"
echo "================================================================================"
echo ""

echo "🔍 Ejecutando test de verificación en modo DRY-RUN..."
python3 "$VERIFICATION_SCRIPT" --dry-run

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: El test de verificación falló"
    echo "   Por favor revisa los errores arriba"
    exit 1
fi

echo ""
echo "✅ Test de verificación completado exitosamente"

echo ""
echo "================================================================================"
echo "PASO 4/4: Configurando ejecución automática"
echo "================================================================================"
echo ""

echo "Opciones de configuración:"
echo ""
echo "1. Cron Jobs (recomendado para servidores Linux/Unix)"
echo "2. Scripts manuales con recordatorio (recomendado para macOS)"
echo ""
read -p "Selecciona una opción (1/2): " OPTION

case $OPTION in
    1)
        echo ""
        echo "📝 Configurando Cron Jobs..."

        # Crear los cron jobs
        EXTRACTION_CRON="0 3 * * 1 cd $SCRIPT_DIR && python3 $EXTRACTION_SCRIPT --ultimos-7-dias --yes >> $EXTRACTION_LOG 2>&1"
        VERIFICATION_CRON="0 2 1 * * cd $SCRIPT_DIR && python3 $VERIFICATION_SCRIPT --verify-sat --notify --yes >> $VERIFICATION_LOG 2>&1"

        # Verificar si ya existen
        EXTRACTION_EXISTS=$(crontab -l 2>/dev/null | grep -c "extraer_facturas_nuevas.py")
        VERIFICATION_EXISTS=$(crontab -l 2>/dev/null | grep -c "verificar_todas_companias.py")

        if [ $EXTRACTION_EXISTS -gt 0 ] || [ $VERIFICATION_EXISTS -gt 0 ]; then
            echo "⚠️  Ya existen cron jobs para CFDIs"
            echo ""
            crontab -l | grep -E "(extraer_facturas_nuevas|verificar_todas_companias)"
            echo ""
            read -p "¿Deseas reemplazarlos? (si/no): " REPLACE

            if [ "$REPLACE" = "si" ] || [ "$REPLACE" = "s" ]; then
                crontab -l | grep -v "extraer_facturas_nuevas.py" | grep -v "verificar_todas_companias.py" | crontab -
                echo "✅ Cron jobs anteriores removidos"
            else
                echo "❌ Manteniendo configuración actual"
                exit 0
            fi
        fi

        # Agregar nuevos cron jobs
        (crontab -l 2>/dev/null; echo "$EXTRACTION_CRON"; echo "$VERIFICATION_CRON") | crontab - 2>/dev/null

        if [ $? -eq 0 ]; then
            echo "✅ Cron jobs configurados exitosamente"
            echo ""
            echo "📅 Programación:"
            echo "   EXTRACCIÓN:"
            echo "   - Frecuencia: Cada lunes a las 3:00 AM"
            echo "   - Facturas: Últimos 7 días"
            echo "   - Log: $EXTRACTION_LOG"
            echo ""
            echo "   VERIFICACIÓN:"
            echo "   - Frecuencia: Día 1 de cada mes a las 2:00 AM"
            echo "   - Acción: Verificar estado con SAT"
            echo "   - Log: $VERIFICATION_LOG"
        else
            echo "❌ Error configurando cron jobs"
            echo ""
            echo "Esto puede ser por permisos en macOS."
            echo "Para configurar manualmente, ejecuta: crontab -e"
            echo "Y agrega estas líneas:"
            echo ""
            echo "$EXTRACTION_CRON"
            echo "$VERIFICATION_CRON"
            echo ""
            echo "Si macOS pide permisos:"
            echo "System Preferences → Security & Privacy → Privacy → Full Disk Access"
            echo "Agregar Terminal"
        fi
        ;;

    2)
        echo ""
        echo "📝 Creando scripts de recordatorio..."

        # Script de extracción semanal
        cat > "$SCRIPT_DIR/EXTRAER_FACTURAS_SEMANAL.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "================================================================================"
echo "📥 EXTRACCIÓN SEMANAL DE FACTURAS"
echo "================================================================================"
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes
EOF

        # Script de verificación mensual
        cat > "$SCRIPT_DIR/VERIFICAR_FACTURAS_MENSUAL.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "================================================================================"
echo "✅ VERIFICACIÓN MENSUAL DE FACTURAS"
echo "================================================================================"
python3 scripts/utilities/verificar_todas_companias.py --verify-sat --notify --yes
EOF

        chmod +x "$SCRIPT_DIR/EXTRAER_FACTURAS_SEMANAL.sh"
        chmod +x "$SCRIPT_DIR/VERIFICAR_FACTURAS_MENSUAL.sh"

        echo "✅ Scripts creados exitosamente"
        echo ""
        echo "📅 Agrega recordatorios en tu calendario:"
        echo ""
        echo "   RECORDATORIO SEMANAL (cada lunes):"
        echo "   Tarea: Extraer facturas nuevas"
        echo "   Comando: bash $SCRIPT_DIR/EXTRAER_FACTURAS_SEMANAL.sh"
        echo ""
        echo "   RECORDATORIO MENSUAL (día 1):"
        echo "   Tarea: Verificar facturas"
        echo "   Comando: bash $SCRIPT_DIR/VERIFICAR_FACTURAS_MENSUAL.sh"
        ;;

    *)
        echo "❌ Opción inválida"
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo "✅ CONFIGURACIÓN COMPLETADA"
echo "================================================================================"
echo ""
echo "📊 Tu sistema ahora tiene automatización completa:"
echo ""
echo "   🔄 CICLO SEMANAL (cada lunes):"
echo "   └─ Descarga facturas nuevas de los últimos 7 días"
echo ""
echo "   🔄 CICLO MENSUAL (día 1):"
echo "   └─ Verifica estado de todas las facturas existentes"
echo ""
echo "📝 Comandos útiles:"
echo ""
echo "   Ver logs de extracción:"
echo "   tail -f $EXTRACTION_LOG"
echo ""
echo "   Ver logs de verificación:"
echo "   tail -f $VERIFICATION_LOG"
echo ""
echo "   Ejecutar extracción manual:"
echo "   python3 $EXTRACTION_SCRIPT --ultimos-7-dias"
echo ""
echo "   Ejecutar verificación manual:"
echo "   python3 $VERIFICATION_SCRIPT --verify-sat"
echo ""
echo "   Ver cron jobs (si aplicable):"
echo "   crontab -l"
echo ""
echo "================================================================================"
echo ""
echo "🎯 Próximas ejecuciones:"
if [ "$OPTION" = "1" ]; then
    NEXT_MONDAY=$(date -v+mon '+%d de %B, %Y')
    NEXT_MONTH=$(date -v+1m '+1 de %B, %Y')
    echo "   Extracción: $NEXT_MONDAY a las 3:00 AM"
    echo "   Verificación: $NEXT_MONTH a las 2:00 AM"
else
    echo "   Revisa tus recordatorios en el calendario"
fi
echo ""
echo "================================================================================"
echo ""
