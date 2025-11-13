# Configuración de Email Service

Guía completa para configurar el envío de correos electrónicos en ContaFlow.

## 📧 Características

El sistema de emails envía correos HTML profesionales para:

- ✉️ **Verificación de cuenta** - Al registrarse un nuevo usuario
- 🔑 **Restablecimiento de contraseña** - Cuando se solicita forgot password
- 🔄 **Reenvío de verificación** - Si el usuario necesita un nuevo link

## 🚀 Configuración Rápida (Gmail)

### 1. Habilitar Verificación en 2 Pasos en Gmail

1. Ve a [https://myaccount.google.com/](https://myaccount.google.com/)
2. Navega a **Seguridad** → **Verificación en dos pasos**
3. Sigue el proceso para habilitar 2FA (obligatorio para contraseñas de aplicación)

### 2. Generar Contraseña de Aplicación

1. Ve a [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Selecciona **Correo** y el dispositivo que uses
3. Haz clic en **Generar**
4. Copia la contraseña de 16 caracteres (sin espacios)

### 3. Configurar Variables de Entorno

Edita tu archivo `.env`:

```env
# SMTP Configuration (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop  # Contraseña de aplicación de Gmail
FROM_EMAIL=tu-email@gmail.com
FROM_NAME=ContaFlow

# Frontend URL (para links en emails)
FRONTEND_URL=http://localhost:3001
```

### 4. Probar el Sistema

Reinicia el backend y registra un nuevo usuario:

```bash
# El backend debe estar corriendo
python3 -m uvicorn main:app --reload --port 8001

# Abre el frontend
# http://localhost:3001/auth/register
```

Deberías recibir un email de verificación en tu bandeja de entrada.

---

## 🔧 Configuración Avanzada

### Outlook / Office 365

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=tu-email@outlook.com
SMTP_PASSWORD=tu-contraseña
FROM_EMAIL=tu-email@outlook.com
FROM_NAME=ContaFlow
```

### SendGrid (Recomendado para Producción)

1. Crea cuenta en [SendGrid](https://sendgrid.com/)
2. Genera una API Key
3. Configura:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=noreply@tudominio.com
FROM_NAME=ContaFlow
```

### Amazon SES

```env
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=tu-smtp-username
SMTP_PASSWORD=tu-smtp-password
FROM_EMAIL=noreply@tudominio.com
FROM_NAME=ContaFlow
```

---

## 📝 Comportamiento del Sistema

### Modo Desarrollo (Sin Email Configurado)

Si **NO** configuras SMTP (dejas `SMTP_USER` y `SMTP_PASSWORD` vacíos):

- ⚠️ Los emails NO se envían
- ✅ El registro sigue funcionando
- 📋 Los links se loggean en consola del backend:
  ```
  ⚠️  Could not send verification email to user@example.com (email not configured)
  ```

### Modo Producción (Con Email Configurado)

Si configuras SMTP correctamente:

- ✅ Los emails se envían automáticamente
- 📧 Los usuarios reciben correos HTML profesionales
- ✅ Los links están ocultos (solo en el email, no en API response)

---

## 🎨 Templates de Email

Los emails incluyen:

- **Diseño responsive** (se ven bien en móvil y desktop)
- **Colores del brand** (gradiente púrpura)
- **Botones clickeables** grandes
- **Fallback de texto plano** para clientes antiguos
- **Links de respaldo** si el botón no funciona

### Vista Previa

Los emails tienen este aspecto:

```
┌──────────────────────────────────────────┐
│        ¡Bienvenido a ContaFlow!         │
│         (fondo gradiente púrpura)        │
└──────────────────────────────────────────┘
│                                          │
│  Hola Juan Pérez,                       │
│                                          │
│  Gracias por registrarte en ContaFlow.  │
│  Por favor verifica tu email...         │
│                                          │
│    [  Verificar mi cuenta  ]  ←botón    │
│                                          │
│  Si no puedes hacer clic en el botón:   │
│  http://localhost:3001/auth/verify...   │
│                                          │
│  Este enlace expira en 24 horas.        │
│                                          │
└──────────────────────────────────────────┘
│     © 2025 ContaFlow                    │
└──────────────────────────────────────────┘
```

---

## 🔍 Debugging

### Ver Logs del Backend

```bash
tail -f /tmp/uvicorn.log | grep -E "email|Email|✅|⚠️"
```

Deberías ver:
```
✅ Verification email sent to user@example.com
```

O si no está configurado:
```
⚠️  Could not send verification email to user@example.com (email not configured)
```

### Probar Envío Manual

Crea un script de prueba:

```python
from core.email_service import email_service

email_sent = email_service.send_verification_email(
    to_email="tu-email@gmail.com",
    full_name="Usuario de Prueba",
    verification_token="test-token-12345"
)

print(f"Email enviado: {email_sent}")
```

### Problemas Comunes

1. **Error: "Username and Password not accepted"**
   - ✅ Solución: Usa una **contraseña de aplicación**, no tu contraseña normal de Gmail

2. **Email no llega**
   - Revisa spam/promociones
   - Verifica que `FROM_EMAIL` sea el mismo que `SMTP_USER`
   - Comprueba que el puerto sea 587 (TLS)

3. **Error: "SMTP AUTH extension not supported"**
   - ✅ Solución: Usa puerto 587 (no 25 o 465)
   - Asegúrate de usar TLS

4. **Email llega pero los links no funcionan**
   - Verifica que `FRONTEND_URL` apunte a la URL correcta
   - En producción, debe ser `https://tudominio.com`

---

## 🔒 Seguridad

### Mejores Prácticas

- ✅ Nunca commites tu `.env` a Git
- ✅ Usa contraseñas de aplicación (no la contraseña principal)
- ✅ Rota las credenciales regularmente
- ✅ En producción, usa SendGrid/AWS SES (más confiable que Gmail)
- ✅ Habilita SPF, DKIM y DMARC en tu dominio

### Límites de Envío

- **Gmail**: ~500 emails/día (cuenta gratuita)
- **SendGrid**: 100 emails/día (plan gratuito), hasta 100k/mes (planes pagos)
- **AWS SES**: Pay-as-you-go, muy escalable

---

## 📊 Endpoints Afectados

Los siguientes endpoints ahora envían emails:

1. **POST /auth/register**
   - Envía email de verificación
   - Usuario debe verificar antes del primer login

2. **POST /auth/forgot-password**
   - Envía email con link de reset password
   - Token expira en 1 hora

3. **POST /auth/resend-verification**
   - Reenvía email de verificación
   - Solo si el email no está verificado

---

## 🎯 Próximos Pasos

Una vez configurado el email:

1. ✅ Registra una cuenta de prueba
2. ✅ Verifica que el email llegue
3. ✅ Haz clic en el link de verificación
4. ✅ Prueba forgot password
5. ✅ Prueba resend verification

---

## 📚 Referencias

- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)
- [SendGrid Docs](https://docs.sendgrid.com/)
- [AWS SES Docs](https://docs.aws.amazon.com/ses/)
- [Python smtplib](https://docs.python.org/3/library/smtplib.html)

---

¿Problemas? Abre un issue en GitHub o revisa los logs del backend.
