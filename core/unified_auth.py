#!/usr/bin/env python3
"""
Sistema de autenticación unificado integrado con BD
Combina la robustez de auth.py con la BD unificada real
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, ConfigDict
import logging
import hashlib
import secrets
import json
import sqlite3

from core.unified_db_adapter import get_unified_adapter
from core.ai.ai_context_memory_service import analyze_and_store_context

logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
import os
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY and ENVIRONMENT in {"development", "local", "test", "testing"}:
    SECRET_KEY = "dev-insecure-secret"
    logger.warning(
        "JWT_SECRET_KEY no configurada. Usando clave insegura de desarrollo; configura JWT_SECRET_KEY en producción."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

class UserRole:
    """Roles de usuario del sistema"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    COMPANY_ADMIN = "company_admin"

    @classmethod
    def get_all_roles(cls) -> List[str]:
        return [cls.ADMIN, cls.USER, cls.VIEWER, cls.COMPANY_ADMIN]

# Pydantic models
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    role: str = UserRole.USER
    tenant_id: int
    onboarding_completed: bool = False
    company_id: Optional[int] = None

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: int
    password_hash: str
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime
    onboarding_completed_at: Optional[datetime] = None

class User(UserBase):
    id: int
    created_at: datetime
    onboarding_completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    tenant_id: Optional[int] = None  # Include tenant_id for frontend

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthProvider(str, Enum):
    PASSWORD = "password"
    GOOGLE = "google"


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: Optional[str] = None
    company_name: Optional[str] = None
    tenant_id: Optional[int] = None
    role: Optional[str] = None
    auth_provider: AuthProvider = AuthProvider.PASSWORD
    onboarding_context: Optional[str] = None
    invite_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RegistrationError(Exception):
    def __init__(self, message: str, *, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "live.com",
    "msn.com",
    "protonmail.com",
    "gmx.com",
    "yandex.com",
    "aol.com",
    "me.com",
    "pm.me",
    "zoho.com",
    "mail.com",
}


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _extract_domain(email: str) -> str:
    return email.split("@", 1)[1].lower()


def _is_generic_domain(domain: str) -> bool:
    return domain in GENERIC_EMAIL_DOMAINS


def _humanize_domain_name(domain: str) -> str:
    """Convert a domain into a readable organization name."""
    base = domain.split(".", 1)[0]
    return base.replace("-", " ").replace("_", " ").title()


def _build_tenant_config(company_name: str, domain: Optional[str], source: str, metadata: Optional[Dict[str, Any]]) -> str:
    payload = {
        "company_name": company_name,
        "domain": domain,
        "created_via": source,
        "created_at": datetime.utcnow().isoformat(),
    }
    if metadata:
        payload["metadata"] = metadata
    return json.dumps(payload, ensure_ascii=False)


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def _find_tenant_by_domain(cursor: sqlite3.Cursor, domain: str) -> Optional[Dict[str, Any]]:
    if not domain:
        return None

    candidate_ids: set[int] = set()

    cursor.execute(
        """
        SELECT id
          FROM tenants
         WHERE LOWER(domain) = LOWER(?)
        """,
        (domain,),
    )
    candidate_ids.update(int(row[0]) for row in cursor.fetchall() if row and row[0] is not None)

    cursor.execute(
        """
        SELECT DISTINCT tenant_id
          FROM users
         WHERE LOWER(email) LIKE ?
        """,
        (f"%@{domain.lower()}",),
    )
    tenant_refs = [int(row[0]) for row in cursor.fetchall() if row and row[0] is not None]
    candidate_ids.update(tenant_refs)

    if not candidate_ids:
        return None

    domain_base = domain.split(".", 1)[0].lower()
    best_match: Optional[Tuple[Dict[str, Any], int]] = None

    for candidate_id in candidate_ids:
        cursor.execute(
            "SELECT id, name, domain, config FROM tenants WHERE id = ?",
            (candidate_id,),
        )
        tenant_row = cursor.fetchone()
        if not tenant_row:
            continue

        tenant_data = _row_to_dict(tenant_row) or {}
        score = 0

        tenant_domain = (tenant_data.get("domain") or "").lower()
        if tenant_domain == domain.lower():
            score += 5

        tenant_name = (tenant_data.get("name") or "").lower()
        if domain_base and domain_base in tenant_name:
            score += 2

        config = tenant_data.get("config")
        if config:
            try:
                config_data = json.loads(config)
                cfg_domain = (config_data.get("domain") or "").lower()
                if cfg_domain == domain.lower():
                    score += 4
                cfg_company = (config_data.get("company_name") or "").lower()
                if domain_base and domain_base in cfg_company:
                    score += 2
            except (TypeError, json.JSONDecodeError):
                pass

        cursor.execute(
            """
            SELECT company_name
              FROM companies
             WHERE tenant_id = ?
             ORDER BY created_at ASC
             LIMIT 1
            """,
            (candidate_id,),
        )
        company_row = cursor.fetchone()
        if company_row:
            company_name = (company_row[0] or "").lower()
            if domain_base and domain_base in company_name:
                score += 3

        if best_match is None or score > best_match[1]:
            best_match = (tenant_data, score)

    return best_match[0] if best_match else None


def _derive_company_name(
    provided_name: Optional[str],
    full_name: str,
    domain: str,
    is_generic: bool,
) -> str:
    if provided_name and provided_name.strip():
        return provided_name.strip()

    if not is_generic and domain:
        return _humanize_domain_name(domain)

    if full_name and full_name.strip():
        return full_name.strip()

    return "Cuenta Individual"


def _ensure_company_for_tenant(
    cursor: sqlite3.Cursor,
    tenant_id: int,
    company_name: str,
    domain: Optional[str],
    contact_email: str,
    metadata: Dict[str, Any],
) -> Tuple[int, bool]:
    cursor.execute(
        """
        SELECT id
          FROM companies
         WHERE tenant_id = ?
         ORDER BY created_at ASC
         LIMIT 1
        """,
        (tenant_id,),
    )
    existing = cursor.fetchone()
    if existing:
        return int(existing[0]), False

    company_config = {
        "domain": domain,
        "created_via": metadata.get("auth_provider"),
        "owner_email": contact_email,
    }

    cursor.execute(
        """
        INSERT INTO companies (
            tenant_id,
            company_name,
            legal_name,
            short_name,
            email,
            is_active,
            config
        ) VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (
            tenant_id,
            company_name,
            company_name,
            company_name[:50],
            contact_email,
            json.dumps(company_config, ensure_ascii=False),
        ),
    )
    company_id = cursor.lastrowid
    return int(company_id), True


def _insert_audit_entry(
    cursor: sqlite3.Cursor,
    entidad: str,
    entidad_id: Optional[int],
    accion: str,
    usuario_id: Optional[int],
    cambios: Optional[Dict[str, Any]] = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO audit_trail (entidad, entidad_id, accion, usuario_id, cambios)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            entidad,
            entidad_id,
            accion,
            usuario_id,
            json.dumps(cambios or {}, ensure_ascii=False),
        ),
    )

# Utility functions
def _ensure_secret_key() -> str:
    """Return a secure JWT secret key or raise if misconfigured."""
    if not SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY environment variable must be set with a secure value.")
    if SECRET_KEY == "mcp-secret-key-change-in-production-2025":
        raise RuntimeError(
            "JWT_SECRET_KEY is using an insecure default. Set JWT_SECRET_KEY to a unique, unpredictable value."
        )
    return SECRET_KEY


try:
    _ensure_secret_key()
except RuntimeError as exc:
    logger.error("JWT secret key misconfiguration: %s", exc)
    raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar password contra hash"""
    try:
        # Check if it's a SHA256 hash (64 hex characters) - primary method
        if len(hashed_password) == 64 and all(c in '0123456789abcdef' for c in hashed_password.lower()):
            import hashlib
            legacy_match = hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
            if legacy_match:
                logger.warning("Legacy SHA256 password verified for user; consider triggering bcrypt rehash.")
            return legacy_match

        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash de password utilizando bcrypt."""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Crear JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, _ensure_secret_key(), algorithm=ALGORITHM)

    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Crear JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, _ensure_secret_key(), algorithm=ALGORITHM)

    return encoded_jwt

def decode_token(token: str) -> TokenData:
    """Decodificar y validar JWT token"""
    # Handle demo token special case
    if token == "demo_token":
        return TokenData(email="demo@example.com", user_id=999, tenant_id=1)

    try:
        payload = jwt.decode(
            token,
            _ensure_secret_key(),
            algorithms=[ALGORITHM],
            options={"verify_sub": False}
        )

        raw_sub = payload.get("sub")
        email: Optional[str] = None
        user_id: Optional[int] = payload.get("user_id")
        tenant_id: Optional[int] = payload.get("tenant_id")

        # Attempt to derive values from new JWT structure (core.auth_jwt)
        if isinstance(raw_sub, str) and "@" in raw_sub:
            email = raw_sub
        if isinstance(raw_sub, int):
            user_id = user_id or raw_sub
        elif isinstance(raw_sub, str):
            try:
                user_id = user_id or int(raw_sub)
            except ValueError:
                pass

        # Fallback to explicit username/email fields present in new JWTs
        if email is None:
            username = payload.get("username") or payload.get("email")
            if isinstance(username, str):
                email = username

        # If still missing user_id, try resolving it from the database using email
        if user_id is None and email:
            user = get_user_by_email(email)
            if user:
                user_id = user.id
                tenant_id = tenant_id or user.tenant_id

        if user_id is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(email=email, user_id=user_id, tenant_id=tenant_id)

    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Database integration functions
def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Obtener usuario por email desde BD unificada"""
    try:
        adapter = get_unified_adapter()
        with adapter.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, full_name, password_hash, tenant_id, role,
                       is_active, is_superuser, last_login, failed_login_attempts,
                       locked_until, created_at, onboarding_completed, onboarding_completed_at,
                       company_id
                FROM users
                WHERE email = ? AND is_active = 1
                """,
                (email,),
            )

            row = cursor.fetchone()
            if row:
                return UserInDB(
                    id=row["id"],
                    email=row["email"],
                    full_name=row["full_name"],
                    password_hash=row["password_hash"] or "",
                    tenant_id=row["tenant_id"],
                    role=row["role"],
                    is_active=bool(row["is_active"]),
                    is_superuser=bool(row["is_superuser"]),
                    last_login=row["last_login"],
                    failed_login_attempts=row["failed_login_attempts"] or 0,
                    locked_until=row["locked_until"],
                    created_at=row["created_at"],
                    onboarding_completed=bool(row["onboarding_completed"]) if row["onboarding_completed"] is not None else False,
                    onboarding_completed_at=row["onboarding_completed_at"],
                    company_id=row["company_id"],
                )
            return None

    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        return None

def get_user_by_id(user_id: int) -> Optional[UserInDB]:
    """Obtener usuario por ID"""
    # Handle demo user special case
    if user_id == 999:
        from datetime import datetime
        return UserInDB(
            id=999,
            email="demo@example.com",
            full_name="Demo User",
            password_hash="",
            tenant_id=1,
            role=UserRole.USER,
            is_active=True,
            is_superuser=False,
            last_login=datetime.now(),
            failed_login_attempts=0,
            locked_until=None,
            created_at=datetime.now()
        )

    try:
        adapter = get_unified_adapter()
        with adapter.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, email, full_name, password_hash, tenant_id, role,
                       is_active, is_superuser, last_login, failed_login_attempts,
                       locked_until, created_at, onboarding_completed, onboarding_completed_at,
                       company_id
                FROM users
                WHERE id = ? AND is_active = 1
                """,
                (user_id,),
            )

            row = cursor.fetchone()
            if row:
                return UserInDB(
                    id=row["id"],
                    email=row["email"],
                    full_name=row["full_name"],
                    password_hash=row["password_hash"] or "",
                    tenant_id=row["tenant_id"],
                    role=row["role"],
                    is_active=bool(row["is_active"]),
                    is_superuser=bool(row["is_superuser"]),
                    last_login=row["last_login"],
                    failed_login_attempts=row["failed_login_attempts"] or 0,
                    locked_until=row["locked_until"],
                    created_at=row["created_at"],
                    onboarding_completed=bool(row["onboarding_completed"]) if row["onboarding_completed"] is not None else False,
                    onboarding_completed_at=row["onboarding_completed_at"],
                    company_id=row["company_id"],
                )
            return None

    except Exception as e:
        logger.error(f"Error getting user by id: {e}")
        return None

def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
    """Autenticar usuario con email y password"""
    user = get_user_by_email(email)

    if not user:
        logger.warning(f"User not found: {email}")
        return None

    # Verificar si está bloqueado
    if user.locked_until and user.locked_until > datetime.utcnow():
        logger.warning(f"User locked: {email}")
        return None

    # Verificar password
    if not user.password_hash:
        logger.warning(f"User has no password hash: {email}")
        return None

    if not verify_password(password, user.password_hash):
        # Incrementar intentos fallidos
        increment_failed_attempts(user.id)
        logger.warning(f"Invalid password for user: {email}")
        return None

    # Login exitoso - resetear intentos y actualizar último login
    update_successful_login(user.id)

    return user

def increment_failed_attempts(user_id: int):
    """Incrementar intentos fallidos de login"""
    try:
        adapter = get_unified_adapter()
        with adapter.get_connection() as conn:
            cursor = conn.cursor()

            # Incrementar intentos
            cursor.execute("""
                UPDATE users
                SET failed_login_attempts = failed_login_attempts + 1
                WHERE id = ?
            """, (user_id,))

            # Si llega a 5 intentos, bloquear por 30 minutos
            cursor.execute("""
                UPDATE users
                SET locked_until = datetime('now', '+30 minutes')
                WHERE id = ? AND failed_login_attempts >= 5
            """, (user_id,))

            conn.commit()

    except Exception as e:
        logger.error(f"Error incrementing failed attempts: {e}")

def update_successful_login(user_id: int):
    """Actualizar último login exitoso"""
    try:
        adapter = get_unified_adapter()
        with adapter.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP,
                    failed_login_attempts = 0,
                    locked_until = NULL
                WHERE id = ?
            """, (user_id,))
            conn.commit()

    except Exception as e:
        logger.error(f"Error updating successful login: {e}")

def create_tenant(
    company_name: str,
    *,
    domain: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    source: str = "register_api",
    connection=None,
) -> Optional[int]:
    """Crear nuevo tenant/empresa y retornar su ID."""
    adapter = get_unified_adapter()
    external_connection = connection is not None
    conn = connection or adapter.get_connection()

    try:
        cursor = conn.cursor()
        config_payload = _build_tenant_config(company_name, domain, source, metadata)
        cursor.execute(
            """
            INSERT INTO tenants (name, config, domain)
            VALUES (?, ?, ?)
            """,
            (company_name, config_payload, domain),
        )
        tenant_id = cursor.lastrowid

        if not external_connection:
            conn.commit()

        logger.info("✅ New tenant created: %s (ID: %s)", company_name, tenant_id)
        return tenant_id

    except Exception as e:
        logger.error("Error creating tenant: %s", e)
        if not external_connection:
            conn.rollback()
        return None
    finally:
        if not external_connection:
            conn.close()

def create_user(user_data: RegisterRequest) -> Optional[UserInDB]:
    """Crear nuevo usuario siguiendo el flujo multiempresa."""
    adapter = get_unified_adapter()
    email = _normalize_email(user_data.email)
    full_name = (user_data.full_name or "").strip()

    if not full_name:
        raise RegistrationError("Full name is required")

    if get_user_by_email(email):
        raise RegistrationError("User already exists")

    if user_data.auth_provider == AuthProvider.PASSWORD and not user_data.password:
        raise RegistrationError("Password is required for email/password registration")

    metadata: Dict[str, Any] = {k: v for k, v in (user_data.metadata or {}).items() if v is not None}
    metadata.setdefault("registration_flow", "multi_tenant_v1")
    metadata.setdefault("auth_provider", user_data.auth_provider.value)
    if user_data.invite_code:
        metadata.setdefault("invite_code", user_data.invite_code)

    password_hash = get_password_hash(user_data.password or secrets.token_urlsafe(24))
    domain = _extract_domain(email)
    is_generic_domain = _is_generic_domain(domain)
    company_name = _derive_company_name(user_data.company_name, full_name, domain, is_generic_domain)

    conn = adapter.get_connection()
    user_id: Optional[int] = None
    company_id: Optional[int] = None
    tenant_id: Optional[int] = user_data.tenant_id
    tenant_created = False
    company_created = False

    try:
        cursor = conn.cursor()
        conn.execute("BEGIN")

        tenant_info: Optional[Dict[str, Any]] = None
        if tenant_id:
            cursor.execute("SELECT id, name, domain FROM tenants WHERE id = ?", (tenant_id,))
            tenant_info = _row_to_dict(cursor.fetchone())
            if not tenant_info:
                raise RegistrationError("Specified tenant does not exist")
            if not tenant_info.get("domain") and not is_generic_domain:
                cursor.execute(
                    "UPDATE tenants SET domain = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (domain, tenant_id),
                )
        else:
            if not is_generic_domain:
                tenant_info = _find_tenant_by_domain(cursor, domain)
                if tenant_info:
                    tenant_id = int(tenant_info["id"])
                    if not tenant_info.get("domain"):
                        cursor.execute(
                            "UPDATE tenants SET domain = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (domain, tenant_id),
                        )

            if not tenant_info:
                tenant_name = company_name
                tenant_id = create_tenant(
                    tenant_name,
                    domain=None if is_generic_domain else domain,
                    metadata=metadata,
                    source=f"{user_data.auth_provider.value}_register",
                    connection=conn,
                )
                if not tenant_id:
                    raise RegistrationError("Failed to create tenant")
                tenant_created = True
                tenant_info = {"id": tenant_id, "name": tenant_name, "domain": None if is_generic_domain else domain}

        if tenant_id is None:
            raise RegistrationError("Tenant resolution failed")

        company_id, company_created = _ensure_company_for_tenant(
            cursor,
            tenant_id,
            company_name,
            None if is_generic_domain else domain,
            email,
            metadata,
        )

        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE tenant_id = ?",
            (tenant_id,),
        )
        existing_user_count = int(cursor.fetchone()[0] or 0)

        resolved_role = user_data.role or (UserRole.ADMIN if existing_user_count == 0 else UserRole.USER)
        if resolved_role not in UserRole.get_all_roles():
            resolved_role = UserRole.USER

        is_superuser = resolved_role == UserRole.ADMIN
        email_verified = user_data.auth_provider == AuthProvider.GOOGLE

        cursor.execute(
            """
            INSERT INTO users (
                email,
                full_name,
                password_hash,
                tenant_id,
                role,
                is_active,
                is_superuser,
                username,
                company_id,
                is_email_verified
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                email,
                full_name,
                password_hash,
                tenant_id,
                resolved_role,
                int(is_superuser),
                email,
                company_id,
                int(email_verified),
            ),
        )
        user_id = int(cursor.lastrowid)

        _insert_audit_entry(
            cursor,
            "users",
            user_id,
            "insert",
            user_id,
            {
                "tenant_id": tenant_id,
                "company_id": company_id,
                "role": resolved_role,
                "auth_provider": user_data.auth_provider.value,
            },
        )

        if tenant_created:
            _insert_audit_entry(
                cursor,
                "tenants",
                tenant_id,
                "insert",
                user_id,
                {
                    "domain": None if is_generic_domain else domain,
                    "company_name": company_name,
                },
            )

        if company_created and company_id is not None:
            _insert_audit_entry(
                cursor,
                "companies",
                company_id,
                "insert",
                user_id,
                {
                    "tenant_id": tenant_id,
                    "company_name": company_name,
                    "domain": None if is_generic_domain else domain,
                },
            )

        conn.commit()

    except RegistrationError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        logger.error("Error creating user: %s", exc)
        return None
    finally:
        conn.close()

    created_user = get_user_by_id(user_id) if user_id is not None else None

    if company_id and user_data.onboarding_context:
        try:
            analyze_and_store_context(
                company_id=company_id,
                context_text=user_data.onboarding_context,
                source="onboarding",
                created_by=user_id,
                preference="stub",
            )
        except Exception as context_exc:  # pragma: no cover - resilience path
            logger.warning(
                "Failed to persist AI context for company %s (tenant %s): %s",
                company_id,
                tenant_id,
                context_exc,
            )

    return created_user

def store_refresh_token(user_id: int, refresh_token: str):
    """Almacenar refresh token en BD"""
    try:
        adapter = get_unified_adapter()
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        with adapter.get_connection() as conn:
            cursor = conn.cursor()

            # Get tenant_id from user
            cursor.execute("SELECT tenant_id FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            tenant_id = result[0] if result else None

            cursor.execute("""
                INSERT INTO refresh_tokens (user_id, tenant_id, token_hash, expires_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, tenant_id, token_hash, expires_at))
            conn.commit()

    except Exception as e:
        logger.error(f"Error storing refresh token: {e}")

def verify_refresh_token(refresh_token: str) -> Optional[int]:
    """Verificar refresh token y obtener user_id"""
    try:
        adapter = get_unified_adapter()
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        with adapter.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM refresh_tokens
                WHERE token_hash = ?
                AND expires_at > CURRENT_TIMESTAMP
                AND is_revoked = 0
            """, (token_hash,))

            row = cursor.fetchone()
            return row[0] if row else None

    except Exception as e:
        logger.error(f"Error verifying refresh token: {e}")
        return None

def revoke_refresh_token(refresh_token: str):
    """Revocar refresh token"""
    try:
        adapter = get_unified_adapter()
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        with adapter.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE refresh_tokens
                SET is_revoked = 1
                WHERE token_hash = ?
            """, (token_hash,))
            conn.commit()

    except Exception as e:
        logger.error(f"Error revoking refresh token: {e}")

# Dependency functions
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Obtener usuario actual autenticado"""
    token_data = decode_token(token)
    user = get_user_by_id(token_data.user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """Obtener usuario actual activo"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return current_user

async def get_current_superuser(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """Obtener superusuario actual"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    return current_user

def create_tokens_for_user(user: UserInDB) -> Token:
    """Crear tokens de acceso y refresh para usuario"""
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "role": user.role
        }
    )

    refresh_token = create_refresh_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "tenant_id": user.tenant_id
        }
    )

    # Almacenar refresh token en BD
    store_refresh_token(user.id, refresh_token)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        tenant_id=user.tenant_id,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

if __name__ == "__main__":
    # Test de funciones
    print("🔐 Testing Unified Auth System")

    # Test password hashing
    test_password = "admin123"
    hashed = get_password_hash(test_password)
    print(f"✅ Password hash: {hashed[:50]}...")
    print(f"✅ Verify: {verify_password(test_password, hashed)}")

    # Test get user
    user = get_user_by_email("admin@tafy.com")
    if user:
        print(f"✅ User found: {user.email}, role: {user.role}, superuser: {user.is_superuser}")
    else:
        print("❌ User not found")

    # Test authentication
    auth_user = authenticate_user("admin@tafy.com", "admin123")
    if auth_user:
        print(f"✅ Authentication successful: {auth_user.email}")

        # Test token creation
        tokens = create_tokens_for_user(auth_user)
        print(f"✅ Access token: {tokens.access_token[:50]}...")
        print(f"✅ Refresh token: {tokens.refresh_token[:50]}...")
    else:
        print("❌ Authentication failed")

    print("🎉 Unified Auth System test completed!")
