# 🚀 Mejoras Recomendadas - Sistema de Autenticación

## Análisis del Estado Actual

### ✅ Lo que funciona bien:
- Login con PostgreSQL
- Registro con PostgreSQL
- Bcrypt para passwords
- JWT tokens con expiración
- Multi-tenancy básico
- Bloqueo por intentos fallidos
- CORS configurado

### ⚠️ Lo que falta o se puede mejorar:

---

## 🎯 PRIORIDAD ALTA (Implementar primero)

### 1. **Email Verification** ⭐⭐⭐
**Problema actual:** Los usuarios pueden registrarse con emails falsos

**Solución:**
```sql
-- Agregar campos
ALTER TABLE users ADD COLUMN verification_token VARCHAR(255);
ALTER TABLE users ADD COLUMN verification_token_expires_at TIMESTAMP;

-- Crear índice
CREATE INDEX idx_users_verification_token ON users(verification_token);
```

**Flujo:**
1. Al registrarse, generar token único
2. Enviar email con link: `https://app.com/verify?token=XXX`
3. Usuario hace click → marcar `is_email_verified = TRUE`
4. Solo permitir login si está verificado

**Endpoint nuevo:**
```python
@router.post("/verify-email")
async def verify_email(token: str):
    # Buscar usuario por token
    # Verificar que no expiró
    # Actualizar is_email_verified = TRUE
    # Borrar token
```

---

### 2. **Password Reset (Recuperación de contraseña)** ⭐⭐⭐
**Problema actual:** Si olvidas tu contraseña, no hay forma de recuperarla

**Solución:**
```sql
-- Agregar campos
ALTER TABLE users ADD COLUMN password_reset_token VARCHAR(255);
ALTER TABLE users ADD COLUMN password_reset_expires_at TIMESTAMP;
```

**Endpoints:**
```python
@router.post("/forgot-password")
async def forgot_password(email: str):
    # Generar token temporal
    # Enviar email con link de reset

@router.post("/reset-password")
async def reset_password(token: str, new_password: str):
    # Validar token
    # Actualizar password
    # Borrar token
```

---

### 3. **Refresh Tokens** ⭐⭐⭐
**Problema actual:** Access token expira en 8 horas, usuario debe hacer login otra vez

**Solución:** Implementar refresh tokens para renovar sin re-login

**Ya existe la tabla `refresh_tokens`, solo falta usarla:**

```python
@router.post("/login")
async def login(...):
    # Generar access_token (8 horas)
    # Generar refresh_token (7 días)
    # Guardar refresh_token en BD
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,  # ← NUEVO
        ...
    }

@router.post("/refresh")
async def refresh(refresh_token: str):
    # Validar refresh_token
    # Generar nuevo access_token
    # Opcionalmente rotar refresh_token
```

---

### 4. **Rate Limiting en Login** ⭐⭐⭐
**Problema actual:** Alguien puede hacer 1000 intentos de login por segundo (brute force)

**Solución:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")  # Máximo 5 intentos por minuto
async def login(...):
    ...
```

---

### 5. **Validación de Contraseñas Fuertes** ⭐⭐
**Problema actual:** Acepta contraseñas débiles como "123456"

**Solución:**
```python
def validate_password_strength(password: str):
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    if not any(c.isupper() for c in password):
        raise HTTPException(400, "Password must contain uppercase letter")

    if not any(c.islower() for c in password):
        raise HTTPException(400, "Password must contain lowercase letter")

    if not any(c.isdigit() for c in password):
        raise HTTPException(400, "Password must contain number")

    # Opcionalmente caracteres especiales
    # if not any(c in "!@#$%^&*" for c in password):
    #     raise HTTPException(400, "Password must contain special character")
```

---

## 🎯 PRIORIDAD MEDIA (Mejorar UX)

### 6. **Onboarding Flow** ⭐⭐
**Problema actual:** Nuevo usuario no sabe qué hacer después de registrarse

**Solución:**
```sql
-- Ya existe onboarding_completed, agregar steps
ALTER TABLE users ADD COLUMN onboarding_step INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN onboarding_data JSONB DEFAULT '{}';
```

**Steps sugeridos:**
1. Bienvenida + tour
2. Completar perfil (teléfono, avatar)
3. Configurar preferencias
4. Conectar primera cuenta bancaria
5. Subir primer CFDI
6. ✓ Completado

**Endpoint:**
```python
@router.post("/onboarding/complete-step")
async def complete_onboarding_step(
    step: int,
    data: dict,
    current_user: User = Depends(get_current_user)
):
    # Actualizar onboarding_step
    # Guardar datos en onboarding_data (JSONB)
    # Si step == 6: onboarding_completed = TRUE
```

---

### 7. **User Profile Management** ⭐⭐
**Problema actual:** No hay forma de actualizar nombre, teléfono, avatar

**Endpoints:**
```python
@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    # Retornar perfil completo

@router.put("/profile")
async def update_profile(
    full_name: Optional[str],
    phone: Optional[str],
    avatar_url: Optional[str],
    current_user: User = Depends(get_current_user)
):
    # Actualizar campos

@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile,
    current_user: User = Depends(get_current_user)
):
    # Subir imagen a S3/CloudFlare
    # Actualizar avatar_url
```

---

### 8. **User Preferences (Configuración)** ⭐⭐
**Problema actual:** No hay forma de guardar preferencias de usuario

**Ya existe el campo `preferences` (JSONB), usarlo:**

```python
@router.get("/preferences")
async def get_preferences(current_user: User = Depends(get_current_user)):
    return current_user.preferences

@router.put("/preferences")
async def update_preferences(
    preferences: dict,  # { "theme": "dark", "language": "es", ... }
    current_user: User = Depends(get_current_user)
):
    # Actualizar preferences JSONB
```

**Preferencias sugeridas:**
```json
{
  "theme": "dark|light",
  "language": "es|en",
  "notifications": {
    "email": true,
    "push": false,
    "sms": false
  },
  "dashboard": {
    "default_view": "expenses|reconciliation",
    "show_tutorials": false
  },
  "timezone": "America/Mexico_City"
}
```

---

### 9. **Session Management** ⭐⭐
**Problema actual:** No puedes ver dónde estás logueado ni cerrar otras sesiones

**Solución:**
```sql
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token_hash VARCHAR(255) UNIQUE,
    device_info JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    revoked_at TIMESTAMP
);
```

**Endpoints:**
```python
@router.get("/sessions")
async def get_active_sessions(current_user: User = Depends(get_current_user)):
    # Listar todas las sesiones activas del usuario

@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: int, current_user: User):
    # Cerrar sesión específica

@router.delete("/sessions/all")
async def revoke_all_sessions(current_user: User):
    # Cerrar todas las sesiones excepto la actual
```

---

## 🎯 PRIORIDAD BAJA (Nice to have)

### 10. **OAuth / Social Login** ⭐
**Login con Google, Microsoft, GitHub**

```python
@router.get("/oauth/google")
async def google_oauth_login():
    # Redirect a Google OAuth

@router.get("/oauth/google/callback")
async def google_oauth_callback(code: str):
    # Exchange code por access_token
    # Obtener info del usuario
    # Crear/actualizar usuario
    # Generar JWT
```

---

### 11. **Two-Factor Authentication (2FA)** ⭐
**TOTP (Google Authenticator) o SMS**

```sql
ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN two_factor_secret VARCHAR(255);
ALTER TABLE users ADD COLUMN two_factor_backup_codes TEXT[];
```

---

### 12. **Audit Log (Trazabilidad)** ⭐
**Registrar todas las acciones importantes**

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100),  -- 'login', 'logout', 'password_change', etc.
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 13. **Multi-Tenant por Dominio Automático** ⭐
**Problema actual:** Todos los usuarios van al mismo tenant (ID=2)

**Solución:** Auto-crear tenant si es email corporativo

```python
domain = email.split('@')[1]

# Si es dominio genérico (gmail, outlook) → tenant default
if domain in ['gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com']:
    tenant_id = 2  # Default
else:
    # Buscar o crear tenant por dominio
    tenant = get_or_create_tenant_by_domain(domain)
    tenant_id = tenant.id
```

---

### 14. **User Roles y Permissions (RBAC)** ⭐
**Más granularidad en permisos**

```sql
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE,
    permissions JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_roles (
    user_id INTEGER REFERENCES users(id),
    role_id INTEGER REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);
```

**Roles sugeridos:**
- `super_admin` - Todo acceso
- `company_admin` - Administrador de empresa
- `accountant` - Contador (solo lectura financiera)
- `manager` - Gerente (aprobaciones)
- `employee` - Empleado básico
- `viewer` - Solo lectura

---

## 📊 Métricas y Monitoreo

### 15. **Analytics de Usuarios**
```sql
-- Usuarios activos por día
SELECT DATE(last_login), COUNT(*)
FROM users
WHERE last_login > NOW() - INTERVAL '30 days'
GROUP BY DATE(last_login);

-- Tasa de conversión de onboarding
SELECT
    COUNT(*) FILTER (WHERE onboarding_completed = TRUE) * 100.0 / COUNT(*) as conversion_rate
FROM users
WHERE created_at > NOW() - INTERVAL '30 days';
```

---

## 🛠️ Mejoras Técnicas

### 16. **Database Connection Pooling**
```python
# Usar pgbouncer o asyncpg con pool
import asyncpg

pool = await asyncpg.create_pool(
    host='127.0.0.1',
    port=5433,
    user='mcp_user',
    password='changeme',
    database='mcp_system',
    min_size=10,
    max_size=20
)
```

### 17. **Caching con Redis**
```python
import redis

redis_client = redis.Redis(host='localhost', port=6379)

# Cache de usuarios frecuentes
def get_user_cached(user_id: int):
    cached = redis_client.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    user = get_user_from_db(user_id)
    redis_client.setex(f"user:{user_id}", 3600, json.dumps(user))
    return user
```

### 18. **API Versioning**
```python
# Mantener compatibilidad con versiones anteriores
@router.post("/v1/auth/login")  # Versión actual
@router.post("/v2/auth/login")  # Nueva versión con cambios
```

---

## 📝 Resumen de Prioridades

### Implementar AHORA (1-2 semanas):
1. ✅ Email Verification
2. ✅ Password Reset
3. ✅ Refresh Tokens
4. ✅ Rate Limiting
5. ✅ Password Strength Validation

### Siguiente Sprint (3-4 semanas):
6. ✅ Onboarding Flow
7. ✅ User Profile Management
8. ✅ User Preferences
9. ✅ Session Management

### Roadmap Futuro (2-3 meses):
10. OAuth Social Login
11. Two-Factor Auth (2FA)
12. Audit Logs
13. Multi-Tenant Automático
14. RBAC (Roles y Permisos)

---

## 🎯 Mi Recomendación TOP 3 para empezar YA:

### 1️⃣ **Password Reset** (2-3 horas)
Es crítico. Si alguien olvida su contraseña, está bloqueado.

### 2️⃣ **Email Verification** (3-4 horas)
Evita registros falsos y spam. Mejora seguridad.

### 3️⃣ **Refresh Tokens** (2-3 horas)
Mejor UX. Usuario no tiene que hacer login cada 8 horas.

---

¿Quieres que implemente alguna de estas mejoras ahora?
