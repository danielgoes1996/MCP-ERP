# Auth Module

Sistema de autenticación unificado para MCP Server.

## 📁 Estructura

```
auth/
├── __init__.py          # Exports públicos del módulo
├── jwt.py              # Autenticación JWT (primaria)
├── unified.py          # Sistema unificado de auth
├── system.py           # Sistema de autenticación base
└── legacy.py           # Auth legacy (deprecated)
```

## 🔑 Componentes Principales

### JWT Authentication (jwt.py)
Sistema principal de autenticación basado en JWT tokens.

**Funciones principales:**
- `get_current_user()` - Obtiene usuario actual desde token
- `create_access_token()` - Crea token JWT
- `verify_token()` - Verifica validez del token

**Uso:**
```python
from core.auth import get_current_user, create_access_token

# Crear token
token = create_access_token(data={"sub": user.email})

# Obtener usuario actual (en endpoint)
@app.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
```

### Unified Auth (unified.py)
Sistema unificado que maneja registro, login, y refresh tokens.

**Funciones principales:**
- `authenticate_user()` - Autentica usuario con email/password
- `create_user()` - Registra nuevo usuario
- `create_tokens_for_user()` - Genera access + refresh tokens
- `verify_refresh_token()` - Valida refresh token
- `revoke_refresh_token()` - Revoca refresh token

**Uso:**
```python
from core.auth import authenticate_user, create_tokens_for_user

# Login
user = await authenticate_user(db, email, password)
tokens = await create_tokens_for_user(db, user)
```

### Auth System (system.py)
Sistema base con utilidades de autenticación.

**Funciones principales:**
- `hash_password()` - Hashea password con bcrypt
- `verify_password()` - Verifica password contra hash

## 🔐 Modelos

### User
```python
class User(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool
    tenant_id: int
```

### LoginRequest
```python
class LoginRequest(BaseModel):
    email: str
    password: str
```

### Token
```python
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

## 📝 Configuración

Variables de entorno requeridas:
```bash
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## 🧪 Testing

```bash
# Tests del módulo auth
pytest tests/test_auth.py -v

# Tests de JWT
pytest tests/test_auth.py::test_jwt_token -v

# Tests de unified auth
pytest tests/test_auth.py::test_unified_auth -v
```

## 🚀 Migración desde Estructura Antigua

**Antes:**
```python
from core.auth_jwt import get_current_user
from core.unified_auth import authenticate_user
```

**Ahora:**
```python
from core.auth import get_current_user, authenticate_user
```

## ⚠️ Deprecations

- `legacy.py` - Sistema de auth antiguo, se eliminará en v3.0
  - Usar `jwt.py` o `unified.py` en su lugar

## 📚 Referencias

- [JWT.io](https://jwt.io/) - JWT token debugger
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Passlib](https://passlib.readthedocs.io/) - Password hashing
