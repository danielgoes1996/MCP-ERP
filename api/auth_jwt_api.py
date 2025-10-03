"""
API endpoints for JWT Authentication
Login, logout, and token management
"""

from fastapi import APIRouter, HTTPException, Depends, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List
import logging

from core.auth_jwt import (
    User,
    Token,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_db_connection,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =====================================================
# MODELS
# =====================================================

class UserProfile(BaseModel):
    """User profile response"""
    id: int
    username: str
    email: str
    full_name: str
    role: str
    employee_id: Optional[int] = None


class TenantInfo(BaseModel):
    """Tenant information response"""
    id: int
    name: str
    description: Optional[str] = None


# =====================================================
# TENANTS ENDPOINT
# =====================================================

@router.get("/tenants", response_model=List[TenantInfo])
async def get_available_tenants() -> List[TenantInfo]:
    """
    Get list of available tenants for login selection

    **Public endpoint** - No authentication required

    **Returns:**
    - List of tenants with id and name
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, description
            FROM tenants
            WHERE is_active = 1
            ORDER BY name
        """)

        tenants = []
        for row in cursor.fetchall():
            tenants.append(TenantInfo(
                id=row['id'],
                name=row['name'],
                description=row['description'] if row['description'] else None
            ))

        conn.close()
        return tenants

    except Exception as e:
        logger.exception(f"Error fetching tenants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching available tenants"
        )


# =====================================================
# LOGIN ENDPOINT
# =====================================================

@router.post("/login", response_model=Token)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    tenant_id: Optional[int] = Form(None)
) -> Token:
    """
    Login with username, password, and tenant selection

    **Authentication:**
    - Accepts username or email
    - Returns JWT access token with tenant_id
    - Token expires in 8 hours

    **Multi-Tenancy:**
    - tenant_id is required for multi-tenant access
    - User must have access to selected tenant

    **Account Security:**
    - Locks account after 5 failed attempts (30 minutes)
    - Updates last_login timestamp

    **Request (application/x-www-form-urlencoded):**
    - username: Username or email
    - password: User password
    - tenant_id: Selected tenant ID (required)

    **Response:**
    - access_token: JWT token for authentication
    - token_type: "bearer"
    - expires_in: Seconds until expiration
    - user: User profile
    - tenant: Tenant information
    """
    try:
        # Validate tenant_id provided
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id is required for login"
            )

        # Authenticate user
        user = authenticate_user(username, password)

        if not user:
            logger.warning(f"Failed login attempt for: {username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 🏢 Validate user has access to tenant
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.id, t.name, t.description
            FROM tenants t
            INNER JOIN users u ON u.tenant_id = t.id
            WHERE u.id = ? AND t.id = ? AND t.is_active = 1
        """, (user.id, tenant_id))

        tenant_row = cursor.fetchone()
        conn.close()

        if not tenant_row:
            logger.warning(f"User {username} attempted to access unauthorized tenant {tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this tenant"
            )

        tenant_info = TenantInfo(
            id=tenant_row['id'],
            name=tenant_row['name'],
            description=tenant_row['description'] if tenant_row['description'] else None
        )

        # Update user with selected tenant_id
        user.tenant_id = tenant_id

        # Create access token with tenant_id
        access_token = create_access_token(user)

        logger.info(f"✅ User {user.username} logged in successfully to tenant {tenant_info.name}")

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user,
            tenant=tenant_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )


# =====================================================
# CURRENT USER ENDPOINT
# =====================================================

@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: User = Depends(get_current_user)) -> UserProfile:
    """
    Get current authenticated user profile

    **Requires:** Valid JWT token in Authorization header

    **Returns:**
    - User profile information
    - Role and permissions
    """
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        employee_id=current_user.employee_id
    )


# =====================================================
# LOGOUT ENDPOINT
# =====================================================

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout current user

    **Requires:** Valid JWT token

    **Process:**
    - Revokes current token
    - Token cannot be used after logout

    **Note:** Client should also delete token from local storage
    """
    try:
        # Revoke token in database
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE user_sessions
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND revoked_at IS NULL
            """, (current_user.id,))
            conn.commit()

            logger.info(f"✅ User {current_user.username} logged out")

            return {
                "success": True,
                "message": "Logout successful"
            }

        finally:
            conn.close()

    except Exception as e:
        logger.exception(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout"
        )


# =====================================================
# PASSWORD RESET (Future endpoint)
# =====================================================

# TODO: Implement password reset functionality
# @router.post("/reset-password")
# async def reset_password(email: str):
#     """Request password reset"""
#     pass
