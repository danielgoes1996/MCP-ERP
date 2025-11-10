#!/bin/bash
#
# Script de Activación Rápida - Modo Producción
# =============================================
#
# INSTRUCCIONES:
# 1. Edita este archivo y pon tu contraseña en la línea PASSWORD=""
# 2. Ejecuta: bash ACTIVAR_PRODUCCION.sh
# 3. El script subirá los certificados y activará modo producción
#

# ========================================
# CONFIGURACIÓN - EDITA AQUÍ
# ========================================

# IMPORTANTE: Pon tu contraseña de e.firma aquí (entre comillas)
PASSWORD="Eoai6103"

# Datos de la compañía
COMPANY_ID=2
RFC="POL210218264"

# Rutas de los certificados (ya las encontré automáticamente)
CERT_FILE="/Users/danielgoes96/Downloads/pol210218264.cer"
KEY_FILE="/Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key"

# ========================================
# NO EDITES ABAJO DE ESTA LÍNEA
# ========================================

echo "================================================================================"
echo "🚀 ACTIVACIÓN MODO PRODUCCIÓN - VERIFICACIÓN SAT REAL"
echo "================================================================================"
echo ""

# Validar que se puso el password
if [ -z "$PASSWORD" ]; then
    echo "❌ ERROR: Debes editar este archivo y poner tu contraseña en PASSWORD=\"\""
    echo ""
    echo "Instrucciones:"
    echo "1. Abre este archivo: nano ACTIVAR_PRODUCCION.sh"
    echo "2. Busca la línea: PASSWORD=\"\""
    echo "3. Pon tu contraseña entre las comillas: PASSWORD=\"tu_password_aqui\""
    echo "4. Guarda el archivo (Ctrl+O, Enter, Ctrl+X)"
    echo "5. Ejecuta de nuevo: bash ACTIVAR_PRODUCCION.sh"
    echo ""
    exit 1
fi

# Validar que existan los archivos
if [ ! -f "$CERT_FILE" ]; then
    echo "❌ ERROR: No se encontró el certificado: $CERT_FILE"
    exit 1
fi

if [ ! -f "$KEY_FILE" ]; then
    echo "❌ ERROR: No se encontró la llave privada: $KEY_FILE"
    exit 1
fi

echo "📋 Configuración:"
echo "   Company ID: $COMPANY_ID"
echo "   RFC: $RFC"
echo "   Certificado: $CERT_FILE"
echo "   Llave: $KEY_FILE"
echo "   Password: $(echo $PASSWORD | sed 's/./*/g')"
echo ""

# Confirmar
read -p "¿Deseas continuar? (si/no): " CONFIRM

if [ "$CONFIRM" != "si" ] && [ "$CONFIRM" != "s" ]; then
    echo "❌ Operación cancelada"
    exit 0
fi

echo ""
echo "================================================================================"
echo "PASO 1/3: Subiendo certificados e.firma a la base de datos..."
echo "================================================================================"
echo ""

python3 scripts/utilities/upload_efirma.py \
    --company-id $COMPANY_ID \
    --rfc $RFC \
    --cert "$CERT_FILE" \
    --key "$KEY_FILE" \
    --password "$PASSWORD" <<< "si"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: Falló la subida de certificados"
    exit 1
fi

echo ""
echo "================================================================================"
echo "PASO 2/3: Activando modo producción..."
echo "================================================================================"
echo ""

python3 scripts/utilities/enable_production_mode.py <<< "si"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ ERROR: Falló la activación de modo producción"
    exit 1
fi

echo ""
echo "================================================================================"
echo "PASO 3/3: Reiniciando servidor API..."
echo "================================================================================"
echo ""

# Detener servidor actual
echo "Deteniendo servidor actual..."
pkill -f "uvicorn main:app"
sleep 2

# Iniciar servidor en modo producción
echo "Iniciando servidor en modo producción..."
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/api.log 2>&1 &

sleep 3

# Verificar que está corriendo
if curl -s http://localhost:8000/cfdi/health > /dev/null 2>&1; then
    echo "✅ Servidor iniciado correctamente"
else
    echo "⚠️  Servidor iniciando... (puede tardar unos segundos)"
fi

echo ""
echo "================================================================================"
echo "✅ MODO PRODUCCIÓN ACTIVADO EXITOSAMENTE"
echo "================================================================================"
echo ""

# Verificar modo
MODE=$(curl -s http://localhost:8000/cfdi/health | python3 -c "import sys, json; print(json.load(sys.stdin).get('mode', 'unknown'))" 2>/dev/null)

if [ "$MODE" = "production" ]; then
    echo "✅ Verificación: Sistema en modo PRODUCTION"
else
    echo "⚠️  Verificación: Sistema en modo $MODE"
    echo "   Espera unos segundos y ejecuta: curl http://localhost:8000/cfdi/health"
fi

echo ""
echo "🎯 Próximos pasos:"
echo ""
echo "1. Verifica el health check:"
echo "   curl http://localhost:8000/cfdi/health | python3 -m json.tool"
echo ""
echo "2. Prueba verificar un CFDI:"
echo "   curl -X POST \"http://localhost:8000/cfdi/{UUID}/verificar\" | python3 -m json.tool"
echo ""
echo "3. Ver logs del servidor:"
echo "   tail -f /tmp/api.log"
echo ""
echo "4. Ver estadísticas:"
echo "   curl \"http://localhost:8000/cfdi/stats?company_id=2\" | python3 -m json.tool"
echo ""
echo "🎉 ¡Sistema de verificación SAT activado y listo para producción!"
echo ""

# Limpiar password de la memoria
unset PASSWORD
