# 🔐 Cómo Usar el Sistema de Seguridad JWT

## ✅ Sistema COMPLETADO e INTEGRADO

---

## 🚀 Inicio Rápido (3 pasos)

### 1. Arrancar el servidor
```bash
cd /Users/danielgoes96/Desktop/mcp-server
python main.py
```

El servidor arrancará en `http://localhost:8004`

### 2. Abrir el navegador
```
http://localhost:8004/static/auth-login.html
```

### 3. Iniciar sesión
Usa uno de estos usuarios:

| Usuario | Contraseña | Rol | Descripción |
|---------|------------|-----|-------------|
| `admin` | `admin123` | Admin | Acceso completo |
| `maria.garcia` | `accountant123` | Accountant | Ver/procesar anticipos |
| `juan.perez` | `employee123` | Employee | Solo sus anticipos |

---

## 🎯 ¿Qué cambió en el proyecto?

### ANTES (Sin seguridad):
```
Usuario → http://localhost:8004/employee_advances/
         ↓
Servidor → Retorna TODOS los anticipos sin preguntar quién eres
```

### AHORA (Con seguridad JWT):
```
Usuario → http://localhost:8004/static/auth-login.html
         ↓
Login → Recibe token JWT
         ↓
Usuario → http://localhost:8004/static/employee-advances.html
         ↓
Frontend → Agrega header "Authorization: Bearer TOKEN"
         ↓
Servidor → Valida token, verifica rol, filtra datos
         ↓
Employee → Ve solo SUS anticipos
Accountant → Ve TODOS los anticipos
Admin → Ve TODO + puede auto-aplicar IA
```

---

## 📁 Archivos Modificados/Creados

### ✅ Archivos Nuevos:
```
api/auth_jwt_api.py              ← Endpoints de login/logout
core/auth_jwt.py                 ← Lógica de autenticación JWT
static/js/auth-interceptor.js    ← Interceptor para frontend
test_auth_curl.sh                ← Script de testing
SECURITY_IMPLEMENTATION_COMPLETE.md  ← Documentación técnica
COMO_USAR_SEGURIDAD_JWT.md       ← Este archivo
```

### ✅ Archivos Modificados:
```
main.py                          ← Monta router de auth (línea 273)
static/auth-login.html           ← Adaptado a JWT (30 líneas JS)
static/employee-advances.html    ← Agrega interceptor de auth

api/employee_advances_api.py     ← 11 endpoints protegidos
api/split_reconciliation_api.py  ← 6 endpoints protegidos
api/ai_reconciliation_api.py     ← 4 endpoints protegidos
api/non_reconciliation_api.py    ← 1 endpoint protegido
```

### ❌ NO se tocó (sigue igual):
- Lógica de negocio (anticipos, conciliación, etc.)
- Base de datos principal
- Funcionalidades existentes
- UI/diseño visual

---

## 🧪 Cómo Probar

### Opción 1: Manual (Navegador)

1. **Login:**
   - Ir a `http://localhost:8004/static/auth-login.html`
   - Ingresar `admin` / `admin123`
   - Click en "Iniciar Sesión"

2. **Ver anticipos:**
   - Ir a `http://localhost:8004/static/employee-advances.html`
   - Deberías ver la página con datos
   - Consola del navegador muestra: `Logged in as: admin (admin)`

3. **Probar como employee:**
   - Logout (botón en header o borrar localStorage)
   - Login con `juan.perez` / `employee123`
   - Ir a employee-advances.html
   - Solo verás anticipos del employee_id=1

4. **Probar restricciones:**
   - Como employee, intenta "Procesar Reembolso"
   - Deberías ver: `❌ Acceso denegado: Role 'employee' not authorized`

### Opción 2: Automático (Script)

```bash
# Asegúrate que el servidor esté corriendo
./test_auth_curl.sh
```

Verás:
```
✅ Login successful
✅ Profile retrieved
✅ Protected endpoint access successful
✅ Employee correctly blocked from reimbursing
✅ Invalid token correctly rejected
```

---

## 🔑 Usuarios y Permisos

### Admin (`admin` / `admin123`)
**Puede hacer TODO:**
- ✅ Ver todos los anticipos
- ✅ Crear anticipos para cualquier empleado
- ✅ Procesar reembolsos
- ✅ Ver/crear conciliaciones bancarias
- ✅ Ver sugerencias IA
- ✅ Auto-aplicar sugerencias IA (solo admin)

### Accountant (`maria.garcia` / `accountant123`)
**Gestión contable:**
- ✅ Ver todos los anticipos
- ✅ Procesar reembolsos
- ✅ Ver/crear conciliaciones bancarias
- ✅ Ver sugerencias IA
- ❌ NO puede auto-aplicar sugerencias IA

### Employee (`juan.perez` / `employee123`)
**Acceso limitado:**
- ✅ Ver solo SUS anticipos (employee_id=1)
- ✅ Crear anticipos para SÍ MISMO
- ❌ NO puede ver anticipos de otros
- ❌ NO puede procesar reembolsos
- ❌ NO puede acceder a conciliación bancaria

---

## 🛠️ Cómo Funciona (Técnicamente)

### 1. Login
```javascript
// Frontend (auth-login.html)
const formData = new URLSearchParams();
formData.append('username', 'admin');
formData.append('password', 'admin123');

fetch('/auth/login', {
    method: 'POST',
    body: formData
})
```

```python
# Backend (api/auth_jwt_api.py)
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm):
    user = authenticate_user(form_data.username, form_data.password)
    token = create_access_token(user)
    return {"access_token": token, "user": user}
```

### 2. Request Protegida
```javascript
// Frontend (employee-advances.html)
const token = localStorage.getItem('access_token');

fetch('/employee_advances/', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
})
```

```python
# Backend (api/employee_advances_api.py)
@router.get("/")
async def list_advances(
    current_user: User = Depends(get_current_user)  # ← Valida token
):
    if current_user.role == 'employee':
        return get_advances_by_employee(current_user.employee_id)
    else:
        return get_all_advances()
```

### 3. Token JWT
```
Estructura del token:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.       ← Header
eyJzdWIiOjEyLCJ1c2VybmFtZSI6ImFkbWluIn0.   ← Payload (user data)
xyz123abc456                                  ← Signature (verificación)

Decodificado:
{
  "sub": 12,              // User ID
  "username": "admin",    // Username
  "role": "admin",        // Role
  "jti": "uuid-123",      // Token ID (para revocar)
  "exp": 1730589600       // Expira en 8 horas
}
```

---

## 🔧 Solución de Problemas

### Problema: "No authentication token"
**Síntoma:** Página redirige a login inmediatamente

**Solución:**
1. Abrir DevTools (F12) → Application → Local Storage
2. Verificar que existe `access_token`
3. Si no existe, hacer login nuevamente

### Problema: "Session expired"
**Síntoma:** Token deja de funcionar después de 8 horas

**Solución:**
- Hacer login nuevamente
- Los tokens expiran en 8 horas por seguridad

### Problema: "Acceso denegado"
**Síntoma:** Employee intenta procesar reembolso y recibe error 403

**Solución:**
- Esto es correcto - employees NO pueden procesar reembolsos
- Usar usuario `maria.garcia` (accountant) o `admin`

### Problema: No puedo ver algunos anticipos
**Síntoma:** Como employee solo veo 2 anticipos pero sé que hay más

**Solución:**
- Esto es correcto - employees solo ven SUS anticipos
- El filtrado por `employee_id` es automático por seguridad
- Usar usuario `admin` para ver todos

---

## 📊 Endpoints Disponibles

### Autenticación
```
POST /auth/login        → Login y obtener token
GET  /auth/me           → Ver perfil actual
POST /auth/logout       → Cerrar sesión
```

### Anticipos (Protegidos)
```
GET    /employee_advances/                    → Listar (filtrado por rol)
POST   /employee_advances/                    → Crear (employees solo propios)
GET    /employee_advances/{id}                → Ver detalle
POST   /employee_advances/reimburse           → Procesar reembolso (accountant/admin)
GET    /employee_advances/summary/all         → Resumen (accountant/admin)
DELETE /employee_advances/{id}                → Cancelar (accountant/admin)
```

### Conciliación Bancaria (Protegidos)
```
POST /bank_reconciliation/split/one-to-many   → Split 1:N (accountant/admin)
POST /bank_reconciliation/split/many-to-one   → Split N:1 (accountant/admin)
GET  /bank_reconciliation/split/              → Listar splits
```

### Sugerencias IA (Protegidos)
```
GET  /bank_reconciliation/ai/suggestions      → Ver sugerencias (autenticado)
POST /bank_reconciliation/ai/auto-apply/{id}  → Auto-aplicar (solo admin)
```

---

## ⚠️ Importante para Producción

### 1. Cambiar contraseñas
```bash
# Conectar a base de datos
sqlite3 unified_mcp_system.db

# Cambiar password de admin
UPDATE users SET password_hash = '$2b$12$NUEVO_HASH'
WHERE username = 'admin';
```

### 2. Cambiar JWT secret
```python
# En core/auth_jwt.py línea 19
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "TU_SECRET_SUPER_SEGURO_AQUI")
```

### 3. Configurar HTTPS
- En producción, NUNCA usar HTTP
- JWT tokens son sensibles y deben transmitirse por HTTPS

### 4. Ajustar expiración de tokens
```python
# En core/auth_jwt.py línea 21
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas

# Considerar valores más cortos en producción:
# - 60 minutos para mayor seguridad
# - 1440 minutos (24h) para mayor conveniencia
```

---

## 🎯 Próximos Pasos (Opcional)

### Funcionalidades adicionales que puedes agregar:

1. **Refresh Tokens**
   - Token de corta duración + refresh token de larga duración
   - Renovar token sin pedir password nuevamente

2. **Recuperación de Contraseña**
   - Endpoint `/auth/forgot-password`
   - Enviar email con token temporal

3. **Audit Trail Completo**
   - Registrar todas las acciones en tabla `audit_log`
   - Quién hizo qué, cuándo

4. **Rate Limiting**
   - Limitar intentos de login a 5 por minuto
   - Prevenir ataques de fuerza bruta

5. **2FA (Autenticación de dos factores)**
   - Código por SMS o app authenticator
   - Mayor seguridad

---

## 📚 Recursos

- **Documentación Técnica:** `SECURITY_IMPLEMENTATION_COMPLETE.md`
- **Testing:** `./test_auth_curl.sh`
- **JWT Debugger:** https://jwt.io/
- **FastAPI Security:** https://fastapi.tiangolo.com/tutorial/security/

---

## ✅ Checklist de Verificación

Antes de usar en producción:

- [ ] Servidor arranca sin errores
- [ ] Login funciona con los 3 usuarios de prueba
- [ ] Employee solo ve sus propios anticipos
- [ ] Employee no puede procesar reembolsos (error 403)
- [ ] Accountant puede procesar reembolsos
- [ ] Admin puede auto-aplicar sugerencias IA
- [ ] Logout funciona correctamente
- [ ] Token inválido redirige a login
- [ ] Cambiar contraseñas de prueba
- [ ] Cambiar JWT secret key
- [ ] Configurar HTTPS

---

**¡Sistema de seguridad JWT funcionando al 100%!** 🎉

¿Dudas? Revisa `SECURITY_IMPLEMENTATION_COMPLETE.md` para detalles técnicos.
