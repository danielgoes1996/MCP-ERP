"""
JWT Authentication System for MCP
Uses SQLite directly (no SQLAlchemy dependency)
"""

import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
import bcrypt

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mcp-secret-key-change-in-production-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# =====================================================
# MODELS
# =====================================================

class User(BaseModel):
    """User model"""
    id: int
    username: str
    email: str
    full_name: str
    role: str
    tenant_id: int  # ← Multi-tenancy support
    employee_id: Optional[int] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User
    tenant: Optional[dict] = None  # 🏢 Multi-tenancy: Tenant information


# =====================================================
# DATABASE
# =====================================================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect("unified_mcp_system.db")
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# PASSWORD OPERATIONS
# =====================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        # Handle both bcrypt hashes and old SHA hashes
        if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'):
            # bcrypt hash
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        else:
            # Old hash format - deny access (require password reset)
            return False
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# =====================================================
# USER OPERATIONS
# =====================================================

def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, username, email, full_name, role, tenant_id, employee_id, is_active
            FROM users
            WHERE username = ? AND is_active = TRUE
        """, (username,))

        row = cursor.fetchone()
        if not row:
            return None

        return User(**dict(row))
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, username, email, full_name, role, tenant_id, employee_id, is_active
            FROM users
            WHERE id = ? AND is_active = TRUE
        """, (user_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return User(**dict(row))
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticate user with username and password
    Returns User if successful, None otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, username, email, full_name, role, tenant_id, employee_id,
                   is_active, password_hash, failed_login_attempts, locked_until
            FROM users
            WHERE username = ? OR email = ?
        """, (username, username))

        row = cursor.fetchone()
        if not row:
            return None

        user_data = dict(row)

        # Check if locked
        if user_data.get('locked_until'):
            locked_until = datetime.fromisoformat(user_data['locked_until'])
            if locked_until > datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked until {locked_until.isoformat()}"
                )

        # Verify password
        if not verify_password(password, user_data['password_hash']):
            # Increment failed attempts
            failed_attempts = (user_data.get('failed_login_attempts') or 0) + 1

            if failed_attempts >= 5:
                locked_until = datetime.utcnow() + timedelta(minutes=30)
                cursor.execute("""
                    UPDATE users
                    SET failed_login_attempts = ?, locked_until = ?
                    WHERE id = ?
                """, (failed_attempts, locked_until.isoformat(), user_data['id']))
                conn.commit()

                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account locked due to failed login attempts"
                )
            else:
                cursor.execute("""
                    UPDATE users SET failed_login_attempts = ? WHERE id = ?
                """, (failed_attempts, user_data['id']))
                conn.commit()

            return None

        # Check if active
        if not user_data.get('is_active'):
            raise HTTPException(403, "Account inactive")

        # Reset failed attempts
        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = 0, locked_until = NULL, last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_data['id'],))
        conn.commit()

        return User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            role=user_data['role'],
            tenant_id=user_data['tenant_id'],
            employee_id=user_data.get('employee_id'),
            is_active=user_data['is_active']
        )

    finally:
        conn.close()


# =====================================================
# TOKEN OPERATIONS
# =====================================================

def create_access_token(user: User) -> str:
    """Create JWT access token"""
    jti = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user.id),  # ← JWT spec requires sub to be a string
        "username": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id,  # ← Include tenant_id in JWT
        "jti": jti,
        "exp": expires
    }

    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Store session
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO user_sessions (user_id, token_jti, expires_at)
            VALUES (?, ?, ?)
        """, (user.id, jti, expires.isoformat()))
        conn.commit()
    except:
        pass  # Ignore if session table doesn't exist
    finally:
        conn.close()

    return token


def is_token_revoked(jti: str) -> bool:
    """Check if token revoked"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT revoked_at FROM user_sessions WHERE token_jti = ?
        """, (jti,))

        row = cursor.fetchone()
        return row and row['revoked_at'] is not None
    except:
        return False  # If table doesn't exist, assume not revoked
    finally:
        conn.close()


# =====================================================
# DEPENDENCIES
# =====================================================

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get current user from JWT token"""
    import logging
    logger = logging.getLogger(__name__)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        logger.info(f"🔐 Validating JWT token (first 20 chars): {token[:20]}...")
        logger.info(f"🔑 Using SECRET_KEY: {SECRET_KEY[:10]}... / Algorithm: {ALGORITHM}")

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        jti: str = payload.get("jti")

        logger.info(f"✅ JWT decoded successfully - user_id: {user_id}, jti: {jti}")

        if user_id is None or jti is None:
            logger.warning(f"❌ Missing user_id or jti in payload")
            raise credentials_exception

        if is_token_revoked(jti):
            logger.warning(f"❌ Token {jti} is revoked")
            raise HTTPException(401, "Token revoked")

    except JWTError as e:
        logger.error(f"❌ JWT decode error: {e}")
        raise credentials_exception

    user = get_user_by_id(user_id)
    if user is None:
        logger.warning(f"❌ User {user_id} not found in database")
        raise credentials_exception

    logger.info(f"✅ User authenticated: {user.username} (tenant: {user.tenant_id})")
    return user


def require_role(allowed_roles: List[str]):
    """Require user to have one of the allowed roles"""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user.role}' not authorized. Required: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker


def check_permission(user: User, resource: str, action: str) -> bool:
    """Check if user has permission"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if user.role == 'admin':
            return True

        cursor.execute("""
            SELECT id FROM permissions
            WHERE role = ? AND (resource = ? OR resource = '*')
            AND (action = ? OR action = '*')
        """, (user.role, resource, action))

        return cursor.fetchone() is not None

    except:
        # If permissions table doesn't exist, allow admins only
        return user.role == 'admin'
    finally:
        conn.close()


def filter_by_scope(user: User, resource: str, query_filters: dict) -> dict:
    """Add scope-based filters to query"""
    if user.role == 'admin':
        return query_filters

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT scope FROM permissions
            WHERE role = ? AND resource = ? AND action = 'read'
        """, (user.role, resource))

        row = cursor.fetchone()

        if not row:
            query_filters['_no_results'] = True
            return query_filters

        scope = row['scope']

        if scope == 'own':
            if resource == 'employee_advances':
                query_filters['employee_id'] = user.employee_id
            elif resource == 'expenses':
                query_filters['user_id'] = user.id

        return query_filters

    except:
        return query_filters
    finally:
        conn.close()


# =====================================================
# TENANT ISOLATION
# =====================================================

def enforce_tenant_isolation(current_user: User, resource_tenant_id: Optional[int] = None) -> int:
    """
    Enforce tenant isolation - ensures users can only access their own tenant's data

    Args:
        current_user: Current authenticated user
        resource_tenant_id: Tenant ID of the resource being accessed (if known)

    Returns:
        Tenant ID to use for filtering queries

    Raises:
        HTTPException 403: If user tries to access another tenant's data

    Usage:
        tenant_id = enforce_tenant_isolation(current_user)
        results = db.query(f"SELECT * FROM table WHERE tenant_id = {tenant_id}")
    """
    # Superusers (role='superadmin') can access any tenant
    if current_user.role == 'superadmin':
        return resource_tenant_id if resource_tenant_id else current_user.tenant_id

    # Regular users can only access their own tenant
    if resource_tenant_id and resource_tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: Cannot access tenant {resource_tenant_id}"
        )

    return current_user.tenant_id


def get_tenant_filter(current_user: User) -> dict:
    """
    Get tenant filter for database queries

    Returns:
        Dictionary with tenant_id filter

    Usage:
        filters = get_tenant_filter(current_user)
        # filters = {'tenant_id': 1}
    """
    tenant_id = enforce_tenant_isolation(current_user)
    return {'tenant_id': tenant_id}
