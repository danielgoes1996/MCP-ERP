#!/bin/bash
#
# 🚀 Setup Verificación Automática - Todas las Compañías
# ======================================================
# Este script configura la verificación automática mensual para TODOS tus usuarios
#

clear

echo "================================================================================"
echo "🚀 SETUP - VERIFICACIÓN AUTOMÁTICA PARA TODOS LOS USUARIOS"
echo "================================================================================"
echo ""
echo "Este script configurará:"
echo ""
echo "  ✅ Verificación mensual automática de CFDIs"
echo "  ✅ Para TODAS las compañías activas en tu sistema"
echo "  ✅ Con verificación real en el SAT"
echo "  ✅ Ejecución el día 1 de cada mes a las 2:00 AM"
echo ""
echo "⏱️  Tiempo estimado de configuración: 2 minutos"
echo ""
read -p "¿Deseas continuar? (si/no): " CONFIRM

if [ "$CONFIRM" != "si" ] && [ "$CONFIRM" != "s" ]; then
    echo "❌ Operación cancelada"
    exit 0
fi

# Obtener directorio del proyecto
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VERIFICATION_SCRIPT="$SCRIPT_DIR/scripts/utilities/verificar_todas_companias.py"
LOG_FILE="/var/log/cfdi_auto_verification.log"

echo ""
echo "================================================================================"
echo "PASO 1/3: Verificando configuración"
echo "================================================================================"
echo ""

# Verificar que el script existe
if [ ! -f "$VERIFICATION_SCRIPT" ]; then
    echo "❌ ERROR: No se encontró el script de verificación"
    echo "   Ruta esperada: $VERIFICATION_SCRIPT"
    exit 1
fi

echo "✅ Script de verificación encontrado"

# Verificar permisos de escritura en log
LOG_DIR=$(dirname "$LOG_FILE")
if [ ! -w "$LOG_DIR" ]; then
    echo "⚠️  No hay permisos para escribir en $LOG_DIR"
    echo "   Usando directorio temporal: /tmp"
    LOG_FILE="/tmp/cfdi_auto_verification.log"
fi

echo "✅ Log file: $LOG_FILE"

# Hacer el script ejecutable
chmod +x "$VERIFICATION_SCRIPT"
echo "✅ Permisos configurados"

echo ""
echo "================================================================================"
echo "PASO 2/3: Testeando verificación"
echo "================================================================================"
echo ""

echo "🔍 Ejecutando test en modo DRY-RUN..."
python3 "$VERIFICATION_SCRIPT" --dry-run

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: El test falló"
    echo "   Por favor revisa los errores arriba"
    exit 1
fi

echo ""
echo "✅ Test completado exitosamente"

echo ""
echo "================================================================================"
echo "PASO 3/3: Configurando ejecución automática"
echo "================================================================================"
echo ""

echo "Opciones de configuración:"
echo ""
echo "1. Cron Job (recomendado para servidores Linux/Unix)"
echo "2. Script manual con recordatorio (recomendado para macOS)"
echo "3. Integración con systemd timer (avanzado - Linux)"
echo ""
read -p "Selecciona una opción (1/2/3): " OPTION

case $OPTION in
    1)
        echo ""
        echo "📝 Configurando Cron Job..."

        # Crear el cron job
        CRON_JOB="0 2 1 * * cd $SCRIPT_DIR && python3 $VERIFICATION_SCRIPT --verify-sat --notify --yes >> $LOG_FILE 2>&1"

        # Verificar si ya existe
        if crontab -l 2>/dev/null | grep -q "verificar_todas_companias.py"; then
            echo "⚠️  Ya existe un cron job para verificación automática"
            read -p "¿Deseas reemplazarlo? (si/no): " REPLACE

            if [ "$REPLACE" = "si" ] || [ "$REPLACE" = "s" ]; then
                crontab -l | grep -v "verificar_todas_companias.py" | crontab -
                echo "✅ Cron job anterior removido"
            else
                echo "❌ Manteniendo configuración actual"
                exit 0
            fi
        fi

        # Agregar nuevo cron job
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab - 2>/dev/null

        if [ $? -eq 0 ]; then
            echo "✅ Cron job configurado exitosamente"
            echo ""
            echo "📅 Programación: Día 1 de cada mes a las 2:00 AM"
            echo "📋 Log: $LOG_FILE"
        else
            echo "❌ Error configurando cron job"
            echo ""
            echo "Esto puede ser por permisos en macOS."
            echo "Para configurar manualmente:"
            echo ""
            echo "1. Ejecuta: crontab -e"
            echo "2. Agrega esta línea:"
            echo "   $CRON_JOB"
            echo ""
            echo "Si macOS pide permisos:"
            echo "System Preferences → Security & Privacy → Privacy → Full Disk Access"
            echo "Agregar Terminal"
        fi
        ;;

    2)
        echo ""
        echo "📝 Creando script de recordatorio..."

        cat > "$SCRIPT_DIR/VERIFICAR_TODOS_USUARIOS.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 scripts/utilities/verificar_todas_companias.py --verify-sat --notify --yes
EOF

        chmod +x "$SCRIPT_DIR/VERIFICAR_TODOS_USUARIOS.sh"

        echo "✅ Script creado: $SCRIPT_DIR/VERIFICAR_TODOS_USUARIOS.sh"
        echo ""
        echo "📅 Agrega un recordatorio mensual en tu calendario:"
        echo "   Tarea: Verificar CFDIs de todos los usuarios"
        echo "   Comando: bash $SCRIPT_DIR/VERIFICAR_TODOS_USUARIOS.sh"
        echo "   Frecuencia: Mensual (día 1)"
        ;;

    3)
        echo ""
        echo "📝 Configurando systemd timer..."
        echo ""
        echo "⚠️  Esta opción requiere permisos de root y solo funciona en Linux"
        echo ""

        if [ "$(uname)" != "Linux" ]; then
            echo "❌ systemd solo está disponible en Linux"
            echo "   Tu sistema: $(uname)"
            exit 1
        fi

        echo "Instrucciones para configurar systemd:"
        echo ""
        echo "1. Crear archivo de servicio:"
        echo "   sudo nano /etc/systemd/system/cfdi-verification.service"
        echo ""
        echo "2. Contenido:"
        cat << EOF
[Unit]
Description=CFDI Monthly Verification
After=network.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $VERIFICATION_SCRIPT --verify-sat --notify
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=multi-user.target
EOF
        echo ""
        echo "3. Crear timer:"
        echo "   sudo nano /etc/systemd/system/cfdi-verification.timer"
        echo ""
        echo "4. Contenido:"
        cat << 'EOF'
[Unit]
Description=CFDI Monthly Verification Timer

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target
EOF
        echo ""
        echo "5. Activar:"
        echo "   sudo systemctl enable cfdi-verification.timer"
        echo "   sudo systemctl start cfdi-verification.timer"
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
echo "📊 Comandos útiles:"
echo ""
echo "   Ver logs en tiempo real:"
echo "   tail -f $LOG_FILE"
echo ""
echo "   Ejecutar verificación manual:"
echo "   python3 $VERIFICATION_SCRIPT --verify-sat"
echo ""
echo "   Modo prueba (sin cambios):"
echo "   python3 $VERIFICATION_SCRIPT --dry-run"
echo ""
echo "   Ver estadísticas:"
echo "   curl http://localhost:8000/cfdi/stats | python3 -m json.tool"
echo ""
echo "================================================================================"
echo ""
echo "🎯 Tu sistema verificará automáticamente los CFDIs de TODOS los usuarios"
echo "   el primer día de cada mes."
echo ""
echo "🔔 Próxima ejecución: $(date -v+1m '+1 de %B, %Y a las 2:00 AM')"
echo ""
echo "================================================================================"
echo ""
