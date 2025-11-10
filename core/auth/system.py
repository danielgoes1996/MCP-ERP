"""
Sistema de autenticación JWT para MCP Server
Proporciona autenticación segura, roles y middleware
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
import logging
import json

logger = logging.getLogger(__name__)

# Configuración JWT
SECRET_KEY = "mcp-server-secret-key-change-in-production"  # TODO: Move to env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer()


class UserRole:
    """Roles de usuario del sistema"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    COMPANY_ADMIN = "company_admin"

    @classmethod
    def get_all_roles(cls) -> List[str]:
        return [cls.ADMIN, cls.USER, cls.VIEWER, cls.COMPANY_ADMIN]


class User(BaseModel):
    """Modelo de usuario del sistema"""
    id: int
    email: str
    company_id: str
    company_name: Optional[str] = None
    tenant_id: Optional[int] = None
    role: str = UserRole.USER
    is_active: bool = True
    created_at: datetime
    full_name: Optional[str] = None


class TokenData(BaseModel):
    """Datos del token JWT"""
    user_id: int
    email: str
    company_id: str
    role: str
    exp: datetime


class AuthResponse(BaseModel):
    """Respuesta de autenticación"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class LoginRequest(BaseModel):
    """Request de login"""
    email: str
    password: str
    company_id: Optional[str] = None


class RegisterRequest(BaseModel):
    """Request de registro"""
    email: str
    password: str
    full_name: str
    company_id: Optional[str] = None


class AuthService:
    """Servicio de autenticación"""

    def __init__(self):
        import os
        # PostgreSQL connection params
        self.db_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
        self.db_port = os.getenv("POSTGRES_PORT", "5433")
        self.db_name = os.getenv("POSTGRES_DB", "mcp_system")
        self.db_user = os.getenv("POSTGRES_USER", "mcp_user")
        self.db_password = os.getenv("POSTGRES_PASSWORD", "changeme")

        self.users_db: Dict[str, Dict] = {
            # Usuario demo para testing - eliminar en producción
            "admin@mcp.com": {
                "id": 1,
                "email": "admin@mcp.com",
                "hashed_password": self.get_password_hash("admin123"),
                "company_id": "mcp-demo",
                "company_name": "MCP Demo",
                "tenant_id": None,
                "role": UserRole.ADMIN,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "full_name": "MCP Administrator"
            }
        }

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verificar contraseña"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash de contraseña"""
        return pwd_context.hash(password)

    def get_user_from_db(self, email: str) -> Optional[Dict]:
        """Obtener usuario de la base de datos PostgreSQL"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.email, u.full_name, u.password_hash, u.tenant_id, u.role,
                       CASE WHEN u.status = 'active' THEN 1 ELSE 0 END as is_active, u.created_at,
                       t.name AS tenant_name, t.settings AS tenant_config
                FROM users u
                LEFT JOIN tenants t ON u.tenant_id = t.id
                WHERE u.email = %s AND u.status = 'active'
            """, (email,))

            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                company_name = None
                tenant_config = row[9]
                if tenant_config:
                    try:
                        config_data = json.loads(tenant_config) if isinstance(tenant_config, str) else tenant_config
                        company_name = config_data.get("company_name")
                    except Exception as parse_error:
                        logger.debug(f"Could not parse tenant config for {email}: {parse_error}")

                if not company_name and row[8]:
                    company_name = row[8]

                return {
                    "id": row[0],
                    "email": row[1],
                    "full_name": row[2] or "",
                    "hashed_password": row[3],
                    "company_id": f"tenant_{row[4]}",
                    "company_name": company_name,
                    "role": row[5],
                    "is_active": bool(row[6]),
                    "created_at": row[7] if row[7] else datetime.utcnow(),
                    "tenant_id": row[4]
                }
        except Exception as e:
            logger.error(f"Database error getting user {email}: {e}")

        return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Obtener usuario por email (primero DB, luego memoria)"""
        # Primero intentar obtener de la base de datos
        db_user = self.get_user_from_db(email)
        if db_user:
            return db_user

        # Si no está en DB, buscar en memoria (usuarios demo)
        return self.users_db.get(email)

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Autenticar usuario"""
        try:
            user_data = self.get_user_by_email(email)
            if not user_data:
                logger.warning(f"User not found: {email}")
                return None

            if not self.verify_password(password, user_data["hashed_password"]):
                logger.warning(f"Invalid password for user: {email}")
                return None

            if not user_data.get("is_active", True):
                logger.warning(f"Inactive user attempted login: {email}")
                return None

            return User(**user_data)

        except Exception as e:
            logger.error(f"Error authenticating user {email}: {e}")
            return None

    def create_access_token(self, user: User) -> str:
        """Crear token de acceso"""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {
            "user_id": user.id,
            "email": user.email,
            "company_id": user.company_id,
            "role": user.role,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def create_refresh_token(self, user: User) -> str:
        """Crear token de refresh"""
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode = {
            "user_id": user.id,
            "email": user.email,
            "company_id": user.company_id,
            "role": user.role,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verificar y decodificar token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            # Validar campos requeridos
            user_id: int = payload.get("user_id")
            email: str = payload.get("email")
            company_id: str = payload.get("company_id")
            role: str = payload.get("role")
            exp: datetime = datetime.fromtimestamp(payload.get("exp"))

            if not all([user_id, email, company_id, role]):
                logger.warning("Token missing required fields")
                return None

            # Verificar expiración
            if datetime.utcnow() > exp:
                logger.warning(f"Token expired for user: {email}")
                return None

            return TokenData(
                user_id=user_id,
                email=email,
                company_id=company_id,
                role=role,
                exp=exp
            )

        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None

    def register_user(self, request: RegisterRequest) -> User:
        """Registrar nuevo usuario"""
        email = request.email.lower().strip()

        # Validar que no exista el usuario
        if self.get_user_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )

        # Crear ID único (en producción usar DB auto-increment)
        new_id = max((user["id"] for user in self.users_db.values()), default=0) + 1

        # Generar company_id si no se proporciona
        company_id = request.company_id or f"company_{new_id}"

        # Hash password
        hashed_password = self.get_password_hash(request.password)

        # Crear usuario
        user_data = {
            "id": new_id,
            "email": email,
            "hashed_password": hashed_password,
            "company_id": company_id,
            "role": UserRole.USER,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "full_name": request.full_name.strip()
        }

        # Guardar en "DB" (en memoria para demo)
        self.users_db[email] = user_data

        logger.info(f"User registered: {email} for company: {company_id}")

        return User(**user_data)

    def login_user(self, request: LoginRequest) -> AuthResponse:
        """Login de usuario"""
        user = self.authenticate_user(request.email, request.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Crear tokens
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)

        logger.info(f"User logged in: {user.email}")

        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # En segundos
            user=user
        )

    def refresh_access_token(self, refresh_token: str) -> AuthResponse:
        """Renovar token de acceso"""
        token_data = self.verify_token(refresh_token)

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Obtener usuario actual
        user_data = self.get_user_by_email(token_data.email)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        user = User(**user_data)

        # Crear nuevo access token
        new_access_token = self.create_access_token(user)

        return AuthResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,  # Mantener el mismo refresh token
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user
        )


# Instancia global del servicio
auth_service = AuthService()


# Dependencias de FastAPI
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Dependency para obtener usuario actual autenticado"""
    token = credentials.credentials
    token_data = auth_service.verify_token(token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = auth_service.get_user_by_email(token_data.email)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return User(**user_data)


def require_role(required_role: str):
    """Decorator para requerir rol específico"""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {required_role} required"
            )
        return current_user

    return role_checker


def require_company_access(current_user: User = Depends(get_current_user)):
    """Dependency para verificar acceso a la empresa"""
    def company_checker(company_id: str) -> User:
        if current_user.company_id != company_id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this company"
            )
        return current_user

    return company_checker


# Middleware personalizado para logging de auth
class AuthMiddleware:
    """Middleware para logging de autenticación"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        # Log de request con auth info
        auth_header = request.headers.get("authorization")
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
                token_data = auth_service.verify_token(token)
                if token_data:
                    logger.info(f"Authenticated request: {request.method} {request.url.path} - User: {token_data.email}")
                else:
                    logger.warning(f"Invalid token in request: {request.method} {request.url.path}")
            except Exception:
                logger.warning(f"Malformed auth header: {request.method} {request.url.path}")

        response = await call_next(request)
        return response


# Utilidades adicionales
def get_token_from_request(request: Request) -> Optional[str]:
    """Extraer token de la request"""
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    return None


def is_token_expired(token: str) -> bool:
    """Verificar si un token está expirado"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload.get("exp", 0))
        return datetime.utcnow() > exp
    except Exception:
        return True


# Validaciones de contraseña
def validate_password_strength(password: str) -> bool:
    """Validar fortaleza de contraseña"""
    if len(password) < 8:
        return False

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)

    return has_upper and has_lower and has_digit


def generate_secure_password() -> str:
    """Generar contraseña segura aleatoria"""
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(12))
    return password


if __name__ == "__main__":
    # Test básico del sistema
    auth = AuthService()

    # Test login
    try:
        response = auth.login_user(LoginRequest(
            email="admin@mcp.com",
            password="admin123"
        ))
        print(f"✅ Login successful: {response.user.email}")
        print(f"✅ Token created, expires in: {response.expires_in} seconds")

        # Test token verification
        token_data = auth.verify_token(response.access_token)
        print(f"✅ Token verified: {token_data.email} - Role: {token_data.role}")

    except Exception as e:
        print(f"❌ Test failed: {e}")
