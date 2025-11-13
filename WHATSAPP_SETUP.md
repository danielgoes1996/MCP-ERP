# Configuración del Webhook de WhatsApp con Ngrok

## Estado Actual ✅

- ✅ Backend corriendo en puerto 8001
- ✅ Ngrok instalado (v3.32.0)
- ✅ Endpoint `/webhooks/whatsapp` configurado
- ✅ Script automatizado creado

## Requisitos Previos

1. **Cuenta de Meta Developer** (Facebook Developers)
2. **Ngrok Auth Token** (obtenerlo en https://dashboard.ngrok.com/get-started/your-authtoken)
3. **Token de verificación** (crear uno único y secreto)

## Configuración Paso a Paso

### 1. Agregar Variables de Entorno

Edita tu archivo `.env` y agrega:

```bash
# WhatsApp Webhook Configuration
WHATSAPP_VERIFY_TOKEN=tu_token_secreto_aqui_123456
WHATSAPP_DEFAULT_TENANT_ID=1
WHATSAPP_DEFAULT_COMPANY_ID=default
WHATSAPP_DEFAULT_USER_ID=1
```

**IMPORTANTE**: El `WHATSAPP_VERIFY_TOKEN` debe ser una cadena única y secreta que tú elijas (ejemplo: `my_secret_token_2024`). Este mismo token lo usarás en Meta Developer Console.

### 2. Iniciar Ngrok

Ejecuta el script automatizado:

```bash
# Primera vez (si necesitas configurar el auth token)
./scripts/start_ngrok.sh TU_NGROK_AUTH_TOKEN

# Siguientes veces (el token ya está guardado)
./scripts/start_ngrok.sh
```

El script te mostrará una URL como:
```
https://abc123.ngrok.io
```

### 3. Configurar en Meta Developer Console

1. Ve a https://developers.facebook.com/
2. Selecciona tu app de WhatsApp
3. Ve a "Configuración de WhatsApp" > "Configuración"
4. En "Configuración del Webhook":
   - **URL del Webhook**: `https://TU-URL-NGROK.ngrok.io/webhooks/whatsapp`
   - **Token de verificación**: El mismo `WHATSAPP_VERIFY_TOKEN` que pusiste en el `.env`
   - Haz clic en "Verificar y guardar"

5. Suscríbete a estos campos:
   - ✅ `messages` (mensajes entrantes)
   - ✅ `message_status` (opcional, para ver estado de entrega)

### 4. Probar el Webhook

1. En Meta Developer Console, envía un mensaje de prueba
2. El backend debería recibir el mensaje
3. Verifica los logs en el backend:

```bash
# Ver logs del backend
tail -f /tmp/backend.log

# O ver logs en tiempo real
python3 main.py
```

## Endpoints Disponibles

### GET `/webhooks/whatsapp` - Verificación
- Usado por Meta para verificar el webhook
- Requiere: `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`
- Responde con el `hub.challenge` si el token es correcto

### POST `/webhooks/whatsapp` - Recibir Mensajes
- Recibe mensajes de WhatsApp
- Procesa texto, imágenes, documentos
- Soporta mensajes de voz (si está habilitado)

## Verificación Manual

Puedes probar el endpoint de verificación manualmente:

```bash
# Reemplaza TU_TOKEN con tu WHATSAPP_VERIFY_TOKEN
curl "http://localhost:8001/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=TU_TOKEN&hub.challenge=test123"

# Debería devolver: test123
```

## Troubleshooting

### Error: Backend no responde
```bash
# Verificar que el backend está corriendo
curl http://localhost:8001/docs

# Si no responde, iniciar el backend
python3 main.py
```

### Error: Ngrok no está instalado
```bash
brew install ngrok
```

### Error: Token de verificación incorrecto
- Asegúrate de que el `WHATSAPP_VERIFY_TOKEN` en `.env` coincida exactamente con el configurado en Meta
- No debe tener espacios ni comillas adicionales

### Ver logs de ngrok
```bash
# En otra terminal
curl http://localhost:4040/api/tunnels | python3 -m json.tool
```

## Flujo de Mensajes

```
WhatsApp User → Meta API → Ngrok Tunnel → Backend (puerto 8001) → Webhook Handler
                                                                    ↓
                                                            Procesar Mensaje
                                                                    ↓
                                                            Responder a Usuario
```

## Notas Importantes

- **Ngrok debe estar corriendo** mientras quieras recibir mensajes
- La URL de ngrok **cambia cada vez** que reinicias (plan gratuito)
- Para URL permanente necesitas ngrok de pago o usar un servidor con IP pública
- El backend en puerto 8001 debe estar corriendo **antes** de iniciar ngrok

## Script Avanzado (Opcional)

Si quieres iniciar backend + ngrok juntos:

```bash
# Crear script combinado
cat > scripts/start_all.sh << 'EOF'
#!/bin/bash
python3 main.py &
BACKEND_PID=$!
sleep 3
./scripts/start_ngrok.sh
kill $BACKEND_PID
EOF

chmod +x scripts/start_all.sh
./scripts/start_all.sh
```

## Referencias

- [Meta WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks)
- [Ngrok Documentation](https://ngrok.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
