"""
JWT Authentication System for MCP
Uses PostgreSQL directly (no SQLAlchemy dependency)
"""

import os
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
    """User model with multi-role support"""
    id: int
    username: str
    email: str
    full_name: str
    role: str  # Legacy single role (highest level) for backward compatibility
    roles: Optional[List[str]] = None  # NEW: Multi-role support - all assigned roles
    tenant_id: int  # ← Multi-tenancy support
    employee_id: Optional[int] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: Optional[str] = None  # Refresh token for token rotation
    token_type: str = "bearer"
    expires_in: int
    user: User
    tenant: Optional[dict] = None  # 🏢 Multi-tenancy: Tenant information


# =====================================================
# DATABASE
# =====================================================

def get_db_connection():
    """Get database connection - PostgreSQL only"""
    import psycopg2
    import psycopg2.extras
    import os

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB", "mcp_system"),
        user=os.getenv("POSTGRES_USER", "mcp_user"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme")
    )
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
    """Get user by email (PostgreSQL schema uses email as username)"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, email, email, name, role, tenant_id, NULL as employee_id,
                   CASE WHEN status = 'active' THEN TRUE ELSE FALSE END as is_active
            FROM users
            WHERE email = %s AND status = 'active'
        """, (username,))

        row = cursor.fetchone()
        if not row:
            return None

        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            full_name=row[3],
            role=row[4],
            tenant_id=row[5],
            employee_id=row[6],
            is_active=row[7]
        )
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID with multi-role support"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, email, email, name, role, tenant_id, NULL as employee_id,
                   CASE WHEN status = 'active' THEN TRUE ELSE FALSE END as is_active
            FROM users
            WHERE id = %s AND status = 'active'
        """, (user_id,))

        row = cursor.fetchone()
        if not row:
            return None

        # Get all roles assigned to the user (multi-role support)
        user_roles = get_user_roles(user_id)

        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            full_name=row[3],
            role=row[4],
            roles=user_roles,  # NEW: Multi-role support
            tenant_id=row[5],
            employee_id=row[6],
            is_active=row[7]
        )
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
            SELECT id, email, email, name, role, tenant_id, employee_id,
                   CASE WHEN status = 'active' THEN TRUE ELSE FALSE END as is_active,
                   password_hash, failed_login_attempts, locked_until, is_email_verified
            FROM users
            WHERE email = %s
        """, (username,))

        row = cursor.fetchone()
        if not row:
            return None

        user_data = {
            'id': row[0],
            'username': row[1],
            'email': row[2],
            'full_name': row[3],
            'role': row[4],
            'tenant_id': row[5],
            'employee_id': row[6],
            'is_active': row[7],
            'password_hash': row[8],
            'failed_login_attempts': row[9],
            'locked_until': row[10],
            'is_email_verified': row[11]
        }

        # Get all roles assigned to the user (multi-role support)
        user_data['roles'] = get_user_roles(user_data['id'])

        # Check if email is verified
        if not user_data.get('is_email_verified'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before logging in. Check your inbox for the verification link."
            )

        # Check if account is locked
        if user_data.get('locked_until'):
            locked_until = user_data['locked_until']
            if locked_until > datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked until {locked_until.isoformat()}"
                )

        # Verify password
        if not verify_password(password, user_data['password_hash']):
            # Increment failed login attempts
            failed_attempts = (user_data.get('failed_login_attempts') or 0) + 1

            if failed_attempts >= 5:
                # Lock account for 30 minutes
                locked_until = datetime.utcnow() + timedelta(minutes=30)
                cursor.execute("""
                    UPDATE users
                    SET failed_login_attempts = %s, locked_until = %s
                    WHERE id = %s
                """, (failed_attempts, locked_until, user_data['id']))
                conn.commit()

                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account locked due to too many failed login attempts. Try again in 30 minutes."
                )
            else:
                # Increment failed attempts counter
                cursor.execute("""
                    UPDATE users SET failed_login_attempts = %s WHERE id = %s
                """, (failed_attempts, user_data['id']))
                conn.commit()

            return None

        # Check if active
        if not user_data.get('is_active'):
            raise HTTPException(403, "Account inactive")

        # Reset failed attempts and update last login
        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = 0, locked_until = NULL, last_login = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user_data['id'],))
        conn.commit()

        return User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            role=user_data['role'],
            roles=user_data['roles'],  # NEW: Multi-role support
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
    """Create JWT access token with multi-role support"""
    jti = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Get all roles assigned to the user from user_roles table
    user_roles = get_user_roles(user.id)

    to_encode = {
        "sub": str(user.id),  # ← JWT spec requires sub to be a string
        "username": user.username,
        "role": user.role,  # Legacy single role (highest level) for backward compatibility
        "roles": user_roles,  # NEW: Multi-role support - all assigned roles
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


# =====================================================
# ROLE MANAGEMENT (New multi-role system)
# =====================================================

def get_user_roles(user_id: int) -> List[str]:
    """
    Get all roles assigned to a user from user_roles table

    Args:
        user_id: User ID

    Returns:
        List of role names (e.g., ['admin', 'contador'])
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT r.name
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = %s
              AND r.is_active = TRUE
              AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
            ORDER BY r.level DESC
        """, (user_id,))

        roles = [row[0] for row in cursor.fetchall()]
        return roles if roles else []

    except Exception as e:
        # Fallback to users.role column for backward compatibility
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        return [row[0]] if row and row[0] else []
    finally:
        conn.close()


def has_role(user: User, role_name: str) -> bool:
    """
    Check if user has a specific role

    Args:
        user: User object
        role_name: Role name to check (e.g., 'admin', 'contador')

    Returns:
        bool: True if user has the role
    """
    user_roles = get_user_roles(user.id)
    return role_name in user_roles


def has_any_role(user: User, role_names: List[str]) -> bool:
    """
    Check if user has any of the specified roles

    Args:
        user: User object
        role_names: List of role names to check

    Returns:
        bool: True if user has at least one of the roles
    """
    user_roles = get_user_roles(user.id)
    return any(role in user_roles for role in role_names)


def get_user_departments(user_id: int) -> List[int]:
    """
    Get all department IDs assigned to a user

    Args:
        user_id: User ID

    Returns:
        List of department IDs
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT department_id
            FROM user_departments
            WHERE user_id = %s
            ORDER BY is_primary DESC
        """, (user_id,))

        return [row[0] for row in cursor.fetchall()]
    except:
        return []
    finally:
        conn.close()


def get_user_subordinates(user_id: int) -> List[int]:
    """
    Get all user IDs that report to this user

    Args:
        user_id: Supervisor's user ID

    Returns:
        List of subordinate user IDs
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT user_id
            FROM user_hierarchy
            WHERE supervisor_id = %s
              AND (effective_to IS NULL OR effective_to > CURRENT_DATE)
        """, (user_id,))

        return [row[0] for row in cursor.fetchall()]
    except:
        return []
    finally:
        conn.close()


def require_role(allowed_roles: List[str]):
    """
    Require user to have one of the allowed roles (updated for multi-role system)

    Args:
        allowed_roles: List of role names that are allowed

    Returns:
        FastAPI dependency that checks user roles

    Example:
        @router.post("/admin/users")
        async def create_user(current_user: User = Depends(require_role(['admin']))):
            ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)):
        # Get all roles assigned to the user
        user_roles = get_user_roles(current_user.id)

        # Check if user has any of the allowed roles
        if not any(role in allowed_roles for role in user_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required one of: {', '.join(allowed_roles)}. User has: {', '.join(user_roles)}"
            )

        return current_user

    return role_checker


def check_permission(user: User, resource: str, action: str) -> bool:
    """
    Check if user has permission for a resource/action (updated for multi-role system)

    Args:
        user: User object
        resource: Resource type (e.g., 'expenses', 'invoices')
        action: Action type (e.g., 'read', 'create')

    Returns:
        bool: True if user has permission
    """
    # Get all user's roles
    user_roles = get_user_roles(user.id)

    # Admin always has permission
    if 'admin' in user_roles:
        return True

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check permissions from roles table (JSONB permissions column)
        cursor.execute("""
            SELECT r.permissions
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = %s
              AND r.is_active = TRUE
              AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
        """, (user.id,))

        for row in cursor.fetchall():
            perms = row[0] if row[0] else {}

            # Check if permissions contain the resource and action
            resources = perms.get('resources', [])
            actions = perms.get('actions', [])

            if '*' in resources or resource in resources:
                if '*' in actions or action in actions:
                    return True

        return False

    except Exception as e:
        # Fallback: check if user is admin
        return 'admin' in user_roles
    finally:
        conn.close()


def filter_by_scope(user: User, resource: str, query_filters: dict) -> dict:
    """
    Add scope-based filters to query (updated for multi-role system)

    Args:
        user: User object
        resource: Resource type (e.g., 'expenses')
        query_filters: Existing query filters dict

    Returns:
        dict: Updated query filters with scope restrictions
    """
    user_roles = get_user_roles(user.id)

    # Admin sees everything
    if 'admin' in user_roles:
        return query_filters

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get the highest scope from user's roles
        cursor.execute("""
            SELECT r.permissions
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = %s
              AND r.is_active = TRUE
            ORDER BY r.level DESC
        """, (user.id,))

        highest_scope = 'own'  # Default to most restrictive

        for row in cursor.fetchall():
            perms = row[0] if row[0] else {}
            resources = perms.get('resources', [])

            # Check if this role has access to the resource
            if '*' in resources or resource in resources:
                scope = perms.get('scope', 'own')

                # Update to least restrictive scope
                if scope == 'all':
                    highest_scope = 'all'
                    break
                elif scope == 'tenant' and highest_scope != 'all':
                    highest_scope = 'tenant'
                elif scope == 'department' and highest_scope == 'own':
                    highest_scope = 'department'

        # Apply scope filters
        if highest_scope == 'own':
            if resource == 'employee_advances':
                query_filters['employee_id'] = user.employee_id
            elif resource in ['manual_expenses', 'expenses']:
                query_filters['user_id'] = user.id
        elif highest_scope == 'department':
            # Filter by user's departments
            dept_ids = get_user_departments(user.id)
            if dept_ids:
                query_filters['department_id__in'] = dept_ids
        # 'tenant' and 'all' scopes don't add filters (tenant isolation handled by middleware)

        return query_filters

    except Exception as e:
        # Fallback to most restrictive
        query_filters['user_id'] = user.id
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
