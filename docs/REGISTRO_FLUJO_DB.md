# Flujo de Registro - Base de Datos PostgreSQL

## 📊 Qué sucede cuando un usuario se registra

### Endpoint: `POST /auth/register`

**Request Body:**
```json
{
  "email": "usuario@ejemplo.com",
  "password": "mipassword123",
  "full_name": "Juan Pérez",
  "company_name": "Mi Empresa" (opcional)
}
```

---

## 🔄 Proceso Paso a Paso

### 1️⃣ Validación Inicial
```sql
-- Verifica si el email ya existe
SELECT id FROM users WHERE email = 'usuario@ejemplo.com'
```
- ✅ Si NO existe → Continúa
- ❌ Si existe → Error 400: "User with this email already exists"

---

### 2️⃣ Extracción de Dominio
```
email = "usuario@ejemplo.com"
domain = "ejemplo.com"
```

---

### 3️⃣ Búsqueda/Creación de Tenant

**Opción A: Buscar tenant por dominio**
```sql
SELECT id, name FROM tenants WHERE domain = 'ejemplo.com'
```

**Opción B: Si no existe, usar tenant por defecto (ID=2)**
```sql
SELECT id, name FROM tenants WHERE id = 2
```

**Opción C: Si tampoco existe el default, crear nuevo tenant**
```sql
INSERT INTO tenants (name, domain, status)
VALUES ('Mi Empresa', 'ejemplo.com', 'active')
RETURNING id, name
```

---

### 4️⃣ Hash de Contraseña (bcrypt)
```python
password_hash = bcrypt.hashpw('mipassword123', bcrypt.gensalt())
# Resultado: $2b$12$randomsalt...hashedpassword
```

---

### 5️⃣ Creación del Usuario

```sql
INSERT INTO users (
    tenant_id,           -- ID del tenant (ej: 2)
    email,               -- usuario@ejemplo.com
    password_hash,       -- $2b$12$...
    name,                -- Juan Pérez
    full_name,           -- Juan Pérez
    username,            -- usuario@ejemplo.com (mismo que email)
    role,                -- 'user' (por defecto)
    status,              -- 'active'
    is_active,           -- TRUE
    onboarding_completed -- FALSE
)
VALUES (2, 'usuario@ejemplo.com', '$2b$12$...', 'Juan Pérez',
        'Juan Pérez', 'usuario@ejemplo.com', 'user', 'active', TRUE, FALSE)
RETURNING id;
```

**Resultado:** Retorna el `user_id` del nuevo usuario

---

### 6️⃣ Generación de Token JWT

```python
user = User(
    id=user_id,
    username=email,
    email=email,
    full_name=full_name,
    role='user',
    tenant_id=tenant_id,
    employee_id=None,
    is_active=True
)

access_token = create_access_token(user)
# Genera JWT con expiración de 8 horas
```

---

### 7️⃣ Respuesta al Cliente

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": 4,
    "username": "usuario@ejemplo.com",
    "email": "usuario@ejemplo.com",
    "full_name": "Juan Pérez",
    "role": "user",
    "tenant_id": 2,
    "employee_id": null,
    "is_active": true
  },
  "tenant": {
    "id": 2,
    "name": "Default Tenant",
    "description": null
  }
}
```

---

## 📋 Tabla `users` - Campos Creados

| Campo | Valor | Descripción |
|-------|-------|-------------|
| **id** | 4 | Auto-incrementado |
| **tenant_id** | 2 | Tenant asignado |
| **email** | usuario@ejemplo.com | Email único |
| **username** | usuario@ejemplo.com | Mismo que email |
| **password_hash** | $2b$12$... | Hash bcrypt |
| **name** | Juan Pérez | Nombre corto |
| **full_name** | Juan Pérez | Nombre completo |
| **role** | user | Rol por defecto |
| **status** | active | Estado activo |
| **is_active** | TRUE | Usuario activo |
| **is_superuser** | FALSE | No es superusuario |
| **is_email_verified** | FALSE | Email no verificado aún |
| **onboarding_completed** | FALSE | Onboarding pendiente |
| **failed_login_attempts** | 0 | Sin intentos fallidos |
| **locked_until** | NULL | No bloqueado |
| **last_login** | NULL | Nunca ha hecho login |
| **employee_id** | NULL | Sin empleado asociado |
| **phone** | NULL | Sin teléfono |
| **avatar_url** | NULL | Sin avatar |
| **preferences** | {} | Preferencias vacías (JSONB) |
| **company_id** | NULL | Sin compañía asignada |
| **created_at** | 2025-11-09 23:32:00 | Timestamp de creación |
| **updated_at** | 2025-11-09 23:32:00 | Timestamp de actualización |

---

## 🔐 Seguridad

### Password Hashing (bcrypt)
- **Algoritmo:** bcrypt con salt aleatorio
- **Costo:** 12 rounds (2^12 = 4096 iteraciones)
- **Formato:** `$2b$12$[salt][hash]`
- **Longitud:** ~60 caracteres

**Ejemplo:**
```
Contraseña: "mipassword123"
Hash: $2b$12$UmpIoMabHWPTw78SY8N/beoXYZ... (60 chars)
```

### JWT Token
- **Algoritmo:** HS256 (HMAC-SHA256)
- **Expiración:** 8 horas (28800 segundos)
- **Payload:** user_id, username, role, tenant_id

---

## 📊 Estado Actual de la BD

### Usuarios Registrados (Ejemplo)

```sql
SELECT id, email, full_name, role, tenant_id, created_at
FROM users
ORDER BY id;
```

| ID | Email | Full Name | Role | Tenant | Created At |
|----|-------|-----------|------|--------|------------|
| 1 | daniel@contaflow.ai | Daniel | admin | 2 | 2025-11-08 |
| 2 | demo@contaflow.com | Usuario Demo | admin | 2 | 2025-11-09 |
| 3 | testuser@example.com | Test User | user | 2 | 2025-11-09 |
| 4 | maria@startup.com | Maria Garcia | user | 2 | 2025-11-09 |

### Tenants

```sql
SELECT id, name, domain, status FROM tenants;
```

| ID | Name | Domain | Status |
|----|------|--------|--------|
| 2 | Default Tenant | NULL | active |

---

## 🎯 Mejoras Futuras Posibles

1. **Email Verification**
   - Enviar email con código de verificación
   - Actualizar `is_email_verified = TRUE`

2. **Multi-Tenant por Dominio**
   - Auto-crear tenant nuevo si el dominio no existe
   - Asignar usuarios al mismo tenant si comparten dominio

3. **Onboarding Flow**
   - Tracking de pasos completados
   - Actualizar `onboarding_completed = TRUE` al finalizar

4. **Roles Avanzados**
   - company_admin, manager, accountant, etc.
   - Permisos granulares por rol

5. **OAuth/Social Login**
   - Google, Microsoft, GitHub
   - Campo `auth_provider` para identificar método

---

## 🔍 Queries Útiles

### Ver todos los usuarios de un tenant
```sql
SELECT u.email, u.full_name, u.role, u.created_at
FROM users u
WHERE u.tenant_id = 2
ORDER BY u.created_at DESC;
```

### Usuarios activos vs inactivos
```sql
SELECT
    status,
    COUNT(*) as total
FROM users
GROUP BY status;
```

### Últimos registros
```sql
SELECT email, full_name, created_at
FROM users
ORDER BY created_at DESC
LIMIT 10;
```

### Usuarios sin completar onboarding
```sql
SELECT email, full_name, created_at
FROM users
WHERE onboarding_completed = FALSE
ORDER BY created_at DESC;
```
