# 📧 Configuración de Notificaciones por Email

## Resumen

Tu sistema de verificación y extracción automática de CFDIs ahora incluye notificaciones por email para mantenerte informado sobre:

- ✅ Verificaciones completadas (con estadísticas completas)
- 📥 Extracciones completadas (con facturas nuevas descargadas)
- 🚨 Alertas críticas (CFDIs cancelados detectados)

---

## 🚀 Configuración Rápida

### Paso 1: Configurar Variables de Entorno

Crear o editar archivo `.env` en el directorio raíz del proyecto:

```bash
# Configuración SMTP (Gmail ejemplo)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña-de-aplicacion
SMTP_FROM_EMAIL=tu-email@gmail.com
SMTP_FROM_NAME=Sistema CFDI
SMTP_USE_TLS=true

# Habilitar/deshabilitar notificaciones
EMAIL_NOTIFICATIONS_ENABLED=true

# Destinatarios (separados por comas)
NOTIFICATION_EMAILS=contador@empresa.com,admin@empresa.com
```

### Paso 2: Generar Contraseña de Aplicación (Gmail)

Si usas Gmail, necesitas crear una contraseña de aplicación:

1. Ve a tu cuenta de Google: https://myaccount.google.com/
2. Seguridad → Verificación en dos pasos (activar si no está activo)
3. Seguridad → Contraseñas de aplicaciones
4. Selecciona "Correo" y "Otro (nombre personalizado)"
5. Escribe "Sistema CFDI"
6. Copia la contraseña generada (16 caracteres)
7. Úsala en `SMTP_PASSWORD`

### Paso 3: Probar la Configuración

```bash
# Test con verificación (modo dry-run con notificación)
python3 scripts/utilities/verificar_todas_companias.py --dry-run --notify

# Test con extracción (modo dry-run con notificación)
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --dry-run --notify
```

---

## 📬 Proveedores SMTP Soportados

### Gmail (Recomendado para testing)

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña-de-aplicacion  # Generar en Google Account
SMTP_USE_TLS=true
```

**Notas:**
- Requiere verificación en dos pasos
- Contraseña de aplicación (no tu contraseña normal)
- Límite: 500 emails/día

### Outlook / Office 365

```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=tu-email@outlook.com
SMTP_PASSWORD=tu-contraseña
SMTP_USE_TLS=true
```

### SendGrid (Recomendado para producción)

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=tu-api-key-de-sendgrid
SMTP_USE_TLS=true
```

**Ventajas:**
- 100 emails/día gratis
- Mejor deliverability
- Analytics incluidos

### Amazon SES (Para producción con volumen)

```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=tu-smtp-username
SMTP_PASSWORD=tu-smtp-password
SMTP_USE_TLS=true
```

**Ventajas:**
- $0.10 por 1000 emails
- Alta disponibilidad
- Escalable

---

## 🔧 Uso de Notificaciones

### Verificación Automática con Notificación

```bash
# Verificar todas las compañías y enviar email
python3 scripts/utilities/verificar_todas_companias.py --verify-sat --notify --yes

# Cron job (lunes 2:00 AM con notificación)
0 2 1 * * cd /path/to/mcp-server && python3 scripts/utilities/verificar_todas_companias.py --verify-sat --notify --yes >> /tmp/cfdi_verification.log 2>&1
```

### Extracción Automática con Notificación

```bash
# Extraer facturas de últimos 7 días y enviar email
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --notify --yes

# Cron job (día 1 de cada mes 3:00 AM con notificación)
0 3 * * 1 cd /path/to/mcp-server && python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --notify --yes >> /tmp/cfdi_extraction.log 2>&1
```

---

## 📨 Ejemplos de Emails

### Email de Verificación Exitosa

**Asunto:** ✅ Verificación CFDI Completada - 228 facturas verificadas

**Contenido:**
```
Resumen de Verificación
=======================
Fecha: 8 de noviembre, 2025 - 14:30

Estadísticas Generales:
- Compañías procesadas: 1/1
- CFDIs verificados: 228
- Vigentes: 228
- Cancelados: 0
- Errores: 0
- Tiempo total: 3.6 minutos

Compañías Exitosas (1):
• Default Company: 228 verificados en 216.5s

Próxima verificación: 1 de diciembre, 2025
```

### Email de Alerta (CFDIs Cancelados)

**Asunto:** 🚨 ALERTA: 5 CFDIs Cancelados Detectados

**Contenido:**
```
CFDIs Cancelados Detectados
===========================
Se encontraron 5 facturas canceladas en el SAT.

Por favor, revisa las facturas marcadas como canceladas:
- Verifica con los proveedores
- Solicita reexpedición si es necesario
- Actualiza registros contables

Estadísticas:
- Vigentes: 223
- Cancelados: 5
```

### Email de Extracción Completada

**Asunto:** 📥 15 Nuevas Facturas Extraídas del SAT

**Contenido:**
```
Resumen de Extracción
=====================
Fecha: 8 de noviembre, 2025 - 15:00
Período: 01/11/2025 - 08/11/2025

Estadísticas Generales:
- Compañías procesadas: 1/1
- Facturas nuevas: 15
- Facturas existentes: 3
- Errores: 0
- Tiempo total: 2.1 minutos

Compañías Exitosas (1):
• Default Company: 15 nuevas en 125.3s

Próxima extracción: 15 de noviembre, 2025
```

---

## 🎨 Personalización de Emails

### Modificar Templates

Los templates están en: [core/notifications/email_service.py](core/notifications/email_service.py:123-421)

Puedes personalizar:
- Colores y estilos CSS
- Estructura del mensaje
- Información incluida
- Formato de fecha/hora

### Agregar Nuevos Tipos de Notificación

Ejemplo: Notificación de backup completado

```python
# En core/notifications/email_service.py

def send_backup_complete(self, to_emails, backup_info):
    """Envía notificación de backup completado"""
    subject = f"✅ Backup Completado - {backup_info['size']} MB"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Backup Completado</h1>
        <p>Tamaño: {backup_info['size']} MB</p>
        <p>Duración: {backup_info['duration']} segundos</p>
    </body>
    </html>
    """

    return self._send_email(to_emails, subject, html_body)
```

---

## 🔒 Seguridad

### Mejores Prácticas

1. **Nunca commits credenciales al código:**
   ```bash
   # Agregar .env a .gitignore
   echo ".env" >> .gitignore
   ```

2. **Usar contraseñas de aplicación (no tu contraseña real):**
   - Gmail: Contraseñas de aplicación
   - SendGrid: API keys
   - AWS SES: IAM users con permisos limitados

3. **Limitar destinatarios:**
   ```bash
   # Solo emails autorizados
   NOTIFICATION_EMAILS=contador@empresa.com,ceo@empresa.com
   ```

4. **Deshabilitar en desarrollo si es necesario:**
   ```bash
   EMAIL_NOTIFICATIONS_ENABLED=false
   ```

---

## 🐛 Troubleshooting

### Error: "Autenticación fallida"

**Problema:** Gmail rechaza las credenciales

**Solución:**
1. Verificar que la verificación en dos pasos esté activa
2. Generar nueva contraseña de aplicación
3. Copiar la contraseña exacta (sin espacios)

### Error: "Connection timeout"

**Problema:** No se puede conectar al servidor SMTP

**Solución:**
1. Verificar SMTP_HOST y SMTP_PORT correctos
2. Verificar firewall/antivirus no bloquea puerto 587
3. Intentar con puerto alternativo (465 con SSL)

### Error: "No se encontraron destinatarios"

**Problema:** NOTIFICATION_EMAILS no está configurado

**Solución:**
```bash
export NOTIFICATION_EMAILS=tu-email@empresa.com
```

### Emails no llegan

**Problema:** Emails enviados pero no llegan a la bandeja

**Solución:**
1. Revisar carpeta de spam
2. Agregar remitente a contactos
3. Verificar deliverability del proveedor SMTP
4. Considerar usar SendGrid o AWS SES

---

## 📊 Monitoreo

### Ver Logs de Email

```bash
# Ver intentos de envío en logs del script
tail -f /tmp/cfdi_verification.log | grep EMAIL
tail -f /tmp/cfdi_extraction.log | grep EMAIL
```

### Verificar Configuración Actual

```bash
# Script de verificación
python3 -c "
from core.notifications.email_service import EmailConfig, get_notification_recipients
import os

config = EmailConfig.from_env()
recipients = get_notification_recipients()

print('Configuración SMTP:')
print(f'  Host: {config.smtp_host}')
print(f'  Port: {config.smtp_port}')
print(f'  User: {config.smtp_user}')
print(f'  Enabled: {config.enabled}')
print(f'\\nDestinatarios: {recipients}')
"
```

---

## 🔄 Integración con Cron Jobs

### Setup Completo con Notificaciones

Actualizar los cron jobs para incluir `--notify`:

```bash
# Editar crontab
crontab -e

# Agregar/modificar líneas:

# Extracción semanal con notificación
0 3 * * 1 cd /Users/danielgoes96/Desktop/mcp-server && python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --notify --yes >> /tmp/cfdi_extraction.log 2>&1

# Verificación mensual con notificación
0 2 1 * * cd /Users/danielgoes96/Desktop/mcp-server && python3 scripts/utilities/verificar_todas_companias.py --verify-sat --notify --yes >> /tmp/cfdi_verification.log 2>&1
```

### Configurar Variables de Entorno para Cron

Crear archivo: `/Users/danielgoes96/Desktop/mcp-server/.env`

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña-aplicacion
SMTP_FROM_EMAIL=tu-email@gmail.com
SMTP_FROM_NAME=Sistema CFDI
EMAIL_NOTIFICATIONS_ENABLED=true
NOTIFICATION_EMAILS=contador@empresa.com,admin@empresa.com
```

Luego modificar scripts para cargar .env:

```python
# Agregar al inicio de scripts/utilities/verificar_todas_companias.py
# y scripts/utilities/extraer_facturas_nuevas.py

from dotenv import load_dotenv
load_dotenv()  # Carga variables desde .env
```

**Instalar python-dotenv:**

```bash
pip3 install python-dotenv
```

---

## ✅ Checklist de Configuración

- [ ] Variables de entorno configuradas en `.env`
- [ ] Contraseña de aplicación generada (Gmail) o API key (SendGrid/SES)
- [ ] Destinatarios configurados en `NOTIFICATION_EMAILS`
- [ ] Prueba exitosa con `--dry-run --notify`
- [ ] Email recibido correctamente en bandeja de entrada
- [ ] Cron jobs actualizados con flag `--notify`
- [ ] `.env` agregado a `.gitignore`
- [ ] `python-dotenv` instalado

---

## 📚 Próximos Pasos

1. **Configurar Slack (Opcional):**
   - Crear webhook de Slack
   - Agregar `SlackNotificationService`
   - Integrar en scripts

2. **Dashboard de Notificaciones:**
   - Crear panel web para ver historial de notificaciones
   - Integrar con PostgreSQL para logs

3. **Notificaciones Avanzadas:**
   - Notificaciones por WhatsApp (Twilio)
   - Notificaciones por SMS
   - Integración con Telegram

4. **Analytics:**
   - Tracking de apertura de emails
   - Estadísticas de notificaciones enviadas
   - Dashboard de métricas

---

## 🆘 Soporte

### Recursos Útiles

- **Gmail SMTP:** https://support.google.com/mail/answer/7126229
- **SendGrid Docs:** https://docs.sendgrid.com/
- **AWS SES:** https://docs.aws.amazon.com/ses/
- **Python smtplib:** https://docs.python.org/3/library/smtplib.html

### Contacto

Para problemas técnicos o preguntas, consulta:
- Logs del sistema: `/tmp/cfdi_*.log`
- Documentación del código: [core/notifications/email_service.py](core/notifications/email_service.py)

---

**¡Tu sistema de notificaciones está listo! 🎉**

Ahora recibirás emails automáticos cada vez que se complete una verificación o extracción de CFDIs.
