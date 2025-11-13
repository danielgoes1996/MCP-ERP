#!/bin/bash

# Script para iniciar ngrok y exponer el webhook de WhatsApp
# Uso: ./scripts/start_ngrok.sh [ngrok_auth_token]

set -e

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  WhatsApp Webhook - Ngrok Setup${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Verificar que ngrok está instalado
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}Error: ngrok no está instalado${NC}"
    echo "Instálalo con: brew install ngrok"
    exit 1
fi

# Verificar que el backend está corriendo
if ! curl -s http://localhost:8001/docs > /dev/null; then
    echo -e "${RED}Error: El backend no está corriendo en el puerto 8001${NC}"
    echo "Inicia el backend con: python3 main.py"
    exit 1
fi

echo -e "${GREEN}✓ Backend detectado en puerto 8001${NC}"

# Configurar auth token si se proporciona
if [ -n "$1" ]; then
    echo -e "${YELLOW}Configurando ngrok auth token...${NC}"
    ngrok config add-authtoken "$1"
    echo -e "${GREEN}✓ Auth token configurado${NC}\n"
fi

# Verificar VERIFY_TOKEN
if [ -f .env ]; then
    VERIFY_TOKEN=$(grep "WHATSAPP_VERIFY_TOKEN" .env | cut -d '=' -f2 | tr -d '"' | tr -d ' ')
    if [ -n "$VERIFY_TOKEN" ]; then
        echo -e "${GREEN}✓ WHATSAPP_VERIFY_TOKEN encontrado: ${VERIFY_TOKEN}${NC}"
    else
        echo -e "${YELLOW}⚠ WHATSAPP_VERIFY_TOKEN no encontrado en .env${NC}"
        echo "Agrégalo con: WHATSAPP_VERIFY_TOKEN=tu_token_secreto"
    fi
else
    echo -e "${YELLOW}⚠ Archivo .env no encontrado${NC}"
fi

# Iniciar ngrok
echo -e "\n${BLUE}Iniciando ngrok en puerto 8001...${NC}\n"
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}INSTRUCCIONES PARA CONFIGURAR META:${NC}"
echo -e "${YELLOW}========================================${NC}"
echo -e "1. Copia la URL HTTPS que aparece abajo"
echo -e "2. Ve a Meta Developer Console"
echo -e "3. Configura el webhook como: ${GREEN}https://TU-URL.ngrok.io/webhooks/whatsapp${NC}"
echo -e "4. Usa el VERIFY_TOKEN de tu .env"
echo -e "5. Suscríbete al campo 'messages'"
echo -e "${YELLOW}========================================${NC}\n"

# Iniciar ngrok (se mantiene en ejecución)
ngrok http 8001

