#!/bin/bash

# Script para instalación segura de paquetes Python con timeout extendido
# Uso: ./safe-pip-install.sh <paquete> [version]
# Ejemplo: ./safe-pip-install.sh aiohttp==3.9.5

set -e

if [ $# -eq 0 ]; then
    echo "❌ Error: Debes especificar un paquete"
    echo "📖 Uso: $0 <paquete> [version]"
    echo "📖 Ejemplos:"
    echo "   $0 aiohttp"
    echo "   $0 aiohttp==3.9.5"
    echo "   $0 Pillow>=8.0"
    exit 1
fi

PACKAGE="$1"
echo "⏳ Instalando $PACKAGE con timeout extendido..."
echo "🔧 Comando: pip install --timeout 600 --no-cache-dir -v $PACKAGE"
echo

# Ejecutar instalación con timeout de 10 minutos
pip install --timeout 600 --no-cache-dir -v "$PACKAGE"

echo
echo "✅ Instalación de $PACKAGE completada exitosamente"
echo "📦 Verificando instalación..."

# Extraer solo el nombre del paquete (sin versión)
PACKAGE_NAME=$(echo "$PACKAGE" | sed 's/[<>=!].*//' | sed 's/\[.*\]//')

if pip show "$PACKAGE_NAME" >/dev/null 2>&1; then
    echo "✅ $PACKAGE_NAME instalado correctamente"
    pip show "$PACKAGE_NAME" | head -3
else
    echo "⚠️  No se pudo verificar la instalación de $PACKAGE_NAME"
fi