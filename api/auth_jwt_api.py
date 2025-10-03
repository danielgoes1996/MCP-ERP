"""
API endpoints for JWT Authentication
Login, logout, and token management
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
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


# =====================================================
# LOGIN ENDPOINT
# =====================================================

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """
    Login with username and password

    **Authentication:**
    - Accepts username or email
    - Returns JWT access token
    - Token expires in 8 hours

    **Account Security:**
    - Locks account after 5 failed attempts (30 minutes)
    - Updates last_login timestamp

    **Request (application/x-www-form-urlencoded):**
    - username: Username or email
    - password: User password

    **Response:**
    - access_token: JWT token for authentication
    - token_type: "bearer"
    - expires_in: Seconds until expiration
    - user: User profile
    """
    try:
        # Authenticate user
        user = authenticate_user(form_data.username, form_data.password)

        if not user:
            logger.warning(f"Failed login attempt for: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create access token
        access_token = create_access_token(user)

        logger.info(f"✅ User {user.username} logged in successfully")

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user
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
