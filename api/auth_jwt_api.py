"""
API endpoints for JWT Authentication
Login, logout, and token management
"""

from fastapi import APIRouter, HTTPException, Depends, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List
import logging

from core.auth.jwt import (
    User,
    Token,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_db_connection,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from core.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =====================================================
# PASSWORD VALIDATION
# =====================================================

def validate_password_strength(password: str) -> None:
    """
    Validate password meets security requirements

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit

    Raises HTTPException if validation fails
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )

    if not any(c.isupper() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter"
        )

    if not any(c.islower() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter"
        )

    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number"
        )


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
    company_id: Optional[str] = None  # Changed from int to str to match DB schema
    description: Optional[str] = None


class RegisterRequest(BaseModel):
    """User registration request"""
    email: str
    password: str
    full_name: str
    company_name: Optional[str] = None


# =====================================================
# REGISTRATION ENDPOINT
# =====================================================

@router.post("/register")
async def register(request: RegisterRequest):
    """
    Register a new user (requires email verification before login)

    Creates a new user account with email and password.
    Automatically creates a tenant if it's the first user from that domain.
    """
    import bcrypt
    import secrets
    from datetime import datetime, timedelta
    from core.auth.jwt import get_password_hash

    # Validate password strength first (before db connection)
    validate_password_strength(request.password)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (request.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Extract domain from email
        domain = request.email.split('@')[1] if '@' in request.email else 'default'

        # Check if tenant exists for this domain or create default tenant
        cursor.execute("SELECT id, name FROM tenants WHERE domain = %s", (domain,))
        tenant_row = cursor.fetchone()

        if not tenant_row:
            # Check for default tenant
            cursor.execute("SELECT id, name FROM tenants WHERE id = 2")
            tenant_row = cursor.fetchone()

            if not tenant_row:
                # Create default tenant
                cursor.execute("""
                    INSERT INTO tenants (name, domain, status)
                    VALUES (%s, %s, %s)
                    RETURNING id, name
                """, (request.company_name or f"{domain} Company", domain, 'active'))
                tenant_row = cursor.fetchone()
                conn.commit()

        tenant_id = tenant_row[0]
        tenant_name = tenant_row[1]

        # Hash password
        password_hash = get_password_hash(request.password)

        # Generate email verification token (expires in 24 hours)
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.utcnow() + timedelta(hours=24)

        # Create user with verification token
        cursor.execute("""
            INSERT INTO users (
                tenant_id, email, password_hash, name, full_name,
                username, role, status, is_active, onboarding_completed,
                is_email_verified, verification_token, verification_token_expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            tenant_id,
            request.email,
            password_hash,
            request.full_name,
            request.full_name,
            request.email,  # username = email
            'user',  # default role
            'active',
            True,
            False,
            False,  # email not verified yet
            verification_token,
            verification_expires
        ))

        user_row = cursor.fetchone()
        user_id = user_row[0]
        conn.commit()

        # Send verification email
        email_sent = email_service.send_verification_email(
            to_email=request.email,
            full_name=request.full_name,
            verification_token=verification_token
        )

        if email_sent:
            logger.info(f"✅ Verification email sent to {request.email}")
        else:
            logger.warning(f"⚠️  Could not send verification email to {request.email} (email not configured)")

        logger.info(f"✅ New user registered: {request.email} (tenant: {tenant_name})")

        # Don't auto-login - require email verification first
        return {
            "success": True,
            "message": "Registration successful! Please check your email to verify your account.",
            "email": request.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user account"
        )
    finally:
        if conn:
            conn.close()


# =====================================================
# TENANTS ENDPOINT
# =====================================================

@router.get("/tenants", response_model=List[TenantInfo])
async def get_available_tenants(email: Optional[str] = None) -> List[TenantInfo]:
    """
    Get list of available tenants for login selection

    **Public endpoint** - No authentication required

    **Query Parameters:**
    - email: Optional email to filter tenants by user

    **Returns:**
    - List of tenants with id and name
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if email:
            # Filter tenants by user's email - PostgreSQL syntax with %s
            cursor.execute("""
                SELECT DISTINCT t.id, t.name, t.company_id
                FROM tenants t
                INNER JOIN users u ON u.tenant_id = t.id
                WHERE LOWER(u.email) = LOWER(%s)
                ORDER BY t.name
            """, (email.strip(),))
        else:
            # Return all tenants if no email provided
            cursor.execute("""
                SELECT id, name, company_id
                FROM tenants
                ORDER BY name
            """)

        tenants = []
        for row in cursor.fetchall():
            # PostgreSQL returns tuples, not dict rows by default
            tenants.append(TenantInfo(
                id=row[0],
                name=row[1],
                company_id=row[2] if len(row) > 2 else None,
                description=None
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
    Login with username, password, and optional tenant selection

    **Authentication:**
    - Accepts username or email
    - Returns JWT access token + refresh token
    - Access token expires in 8 hours
    - Refresh token expires in 7 days

    **Multi-Tenancy:**
    - tenant_id is optional - if not provided, uses user's default tenant
    - If provided, user must have access to selected tenant

    **Account Security:**
    - Locks account after 5 failed attempts (30 minutes)
    - Updates last_login timestamp

    **Request (application/x-www-form-urlencoded):**
    - username: Username or email
    - password: User password
    - tenant_id: Selected tenant ID (optional - auto-selected if not provided)

    **Response:**
    - access_token: JWT token for authentication
    - refresh_token: Token for refreshing access token
    - token_type: "bearer"
    - expires_in: Seconds until expiration
    - user: User profile
    - tenant: Tenant information
    """
    import secrets
    import hashlib
    from datetime import datetime, timedelta

    try:
        # Authenticate user first
        user = authenticate_user(username, password)

        if not user:
            logger.warning(f"Failed login attempt for: {username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # If tenant_id not provided, use user's default tenant
        if tenant_id is None:
            tenant_id = user.tenant_id
            logger.info(f"Auto-selected tenant_id={tenant_id} for user {username}")

        # 🏢 Validate user has access to tenant
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.id, t.name, t.company_id
            FROM tenants t
            INNER JOIN users u ON u.tenant_id = t.id
            WHERE u.id = %s AND t.id = %s
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
            id=tenant_row[0],
            name=tenant_row[1],
            description=None,
            company_id=tenant_row[2]  # Include company_id from companies table
        )

        # Update user with selected tenant_id
        user.tenant_id = tenant_id

        # Create access token with tenant_id
        access_token = create_access_token(user)

        # Generate refresh token (7 days expiration)
        refresh_token = secrets.token_urlsafe(32)
        refresh_expires = datetime.utcnow() + timedelta(days=7)

        # Hash the refresh token for storage
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Save refresh token to database
        conn_refresh = get_db_connection()
        cursor_refresh = conn_refresh.cursor()

        try:
            # Delete any existing refresh tokens for this user (optional: keep last N tokens)
            cursor_refresh.execute("""
                DELETE FROM refresh_tokens
                WHERE user_id = %s
            """, (user.id,))

            # Insert new refresh token
            cursor_refresh.execute("""
                INSERT INTO refresh_tokens (user_id, tenant_id, token_hash, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (user.id, tenant_id, token_hash, refresh_expires))

            conn_refresh.commit()
        finally:
            conn_refresh.close()

        logger.info(f"✅ User {user.username} logged in successfully to tenant {tenant_info.name}")

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,  # Add refresh token to response
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user,
            tenant={
                "id": tenant_info.id,
                "name": tenant_info.name,
                "company_id": tenant_info.company_id,  # Include company_id for frontend
                "description": tenant_info.description
            }
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
                WHERE user_id = %s AND revoked_at IS NULL
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
# REFRESH TOKEN ENDPOINT
# =====================================================

class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


@router.post("/refresh", response_model=Token)
async def refresh_access_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token

    **Public endpoint** - No authentication required

    **Request:**
    - refresh_token: Refresh token from login

    **Response:**
    - New access_token
    - Same refresh_token (or new one if rotated)
    - user: User profile
    - tenant: Tenant information
    """
    import hashlib
    from datetime import datetime

    try:
        # Hash the provided refresh token
        token_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Find refresh token in database
        cursor.execute("""
            SELECT rt.user_id, rt.tenant_id, rt.expires_at, rt.revoked_at,
                   u.email, u.full_name, u.role, u.is_active
            FROM refresh_tokens rt
            JOIN users u ON u.id = rt.user_id
            WHERE rt.token_hash = %s
        """, (token_hash,))

        token_row = cursor.fetchone()

        if not token_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        user_id = token_row[0]
        tenant_id = token_row[1]
        expires_at = token_row[2]
        revoked_at = token_row[3]
        email = token_row[4]
        full_name = token_row[5]
        role = token_row[6]
        is_active = token_row[7]

        # Check if token is revoked
        if revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked"
            )

        # Check if token is expired
        if datetime.utcnow() > expires_at:
            # Clean up expired token
            cursor.execute("""
                DELETE FROM refresh_tokens WHERE token_hash = %s
            """, (token_hash,))
            conn.commit()
            conn.close()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please login again."
            )

        # Check if user is still active
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Update last_used_at
        cursor.execute("""
            UPDATE refresh_tokens
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE token_hash = %s
        """, (token_hash,))
        conn.commit()

        # Get tenant info
        cursor.execute("""
            SELECT id, name FROM tenants WHERE id = %s
        """, (tenant_id,))
        tenant_row = cursor.fetchone()
        tenant_name = tenant_row[1] if tenant_row else "Unknown"

        conn.close()

        # Create new User object
        user = User(
            id=user_id,
            username=email,
            email=email,
            full_name=full_name,
            role=role,
            tenant_id=tenant_id,
            employee_id=None,
            is_active=is_active
        )

        # Generate new access token
        new_access_token = create_access_token(user)

        logger.info(f"✅ Access token refreshed for user {email}")

        return Token(
            access_token=new_access_token,
            refresh_token=request.refresh_token,  # Return same refresh token
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user,
            tenant={
                "id": tenant_id,
                "name": tenant_name,
                "description": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error refreshing access token"
        )


# =====================================================
# PASSWORD RESET ENDPOINTS
# =====================================================

class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: str


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Request password reset email

    Generates a secure token and sends password reset email to user.
    Token expires in 1 hour.

    **Public endpoint** - No authentication required

    **Request:**
    - email: User's email address

    **Response:**
    - success: True/False
    - message: Confirmation message
    """
    import secrets
    from datetime import datetime, timedelta

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT id, email, full_name FROM users WHERE email = %s", (request.email,))
        user_row = cursor.fetchone()

        # Always return success to prevent email enumeration
        if not user_row:
            logger.warning(f"Password reset requested for non-existent email: {request.email}")
            return {
                "success": True,
                "message": "If the email exists, a password reset link has been sent"
            }

        user_id = user_row[0]
        user_email = user_row[1]
        user_name = user_row[2]

        # Generate secure random token (32 bytes = 64 hex chars)
        reset_token = secrets.token_urlsafe(32)

        # Token expires in 1 hour
        expires_at = datetime.utcnow() + timedelta(hours=1)

        # Save token to database
        cursor.execute("""
            UPDATE users
            SET password_reset_token = %s,
                password_reset_expires_at = %s
            WHERE id = %s
        """, (reset_token, expires_at, user_id))

        conn.commit()
        conn.close()

        # Send password reset email
        email_sent = email_service.send_password_reset_email(
            to_email=user_email,
            full_name=user_name,
            reset_token=reset_token
        )

        if email_sent:
            logger.info(f"✅ Password reset email sent to {user_email}")
        else:
            logger.warning(f"⚠️  Could not send password reset email to {user_email} (email not configured)")

        return {
            "success": True,
            "message": "If the email exists, a password reset link has been sent"
        }

    except Exception as e:
        logger.error(f"Error in forgot password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing password reset request"
        )


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password with token

    Validates the reset token and updates the user's password.

    **Public endpoint** - No authentication required

    **Request:**
    - token: Password reset token from email
    - new_password: New password

    **Response:**
    - success: True/False
    - message: Confirmation message
    """
    from datetime import datetime
    from core.auth.jwt import get_password_hash

    try:
        # Validate new password strength
        validate_password_strength(request.new_password)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Find user by token
        cursor.execute("""
            SELECT id, email, password_reset_expires_at
            FROM users
            WHERE password_reset_token = %s
        """, (request.token,))

        user_row = cursor.fetchone()

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        user_id = user_row[0]
        user_email = user_row[1]
        expires_at = user_row[2]

        # Check if token is expired
        if datetime.utcnow() > expires_at:
            # Clear expired token
            cursor.execute("""
                UPDATE users
                SET password_reset_token = NULL,
                    password_reset_expires_at = NULL
                WHERE id = %s
            """, (user_id,))
            conn.commit()
            conn.close()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired. Please request a new one."
            )

        # Hash new password
        new_password_hash = get_password_hash(request.new_password)

        # Update password and clear reset token
        cursor.execute("""
            UPDATE users
            SET password_hash = %s,
                password_reset_token = NULL,
                password_reset_expires_at = NULL,
                failed_login_attempts = 0,
                locked_until = NULL
            WHERE id = %s
        """, (new_password_hash, user_id))

        conn.commit()
        conn.close()

        logger.info(f"✅ Password reset successful for {user_email}")

        return {
            "success": True,
            "message": "Password has been reset successfully. You can now login with your new password."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error resetting password"
        )


# =====================================================
# EMAIL VERIFICATION ENDPOINTS
# =====================================================

class VerifyEmailRequest(BaseModel):
    """Email verification request"""
    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request"""
    email: str


@router.post("/verify-email")
async def verify_email(request: VerifyEmailRequest):
    """
    Verify email address with token

    Validates the verification token and marks email as verified.

    **Public endpoint** - No authentication required

    **Request:**
    - token: Email verification token from email

    **Response:**
    - success: True/False
    - message: Confirmation message
    """
    from datetime import datetime

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find user by token
        cursor.execute("""
            SELECT id, email, verification_token_expires_at, is_email_verified
            FROM users
            WHERE verification_token = %s
        """, (request.token,))

        user_row = cursor.fetchone()

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )

        user_id = user_row[0]
        user_email = user_row[1]
        expires_at = user_row[2]
        already_verified = user_row[3]

        # Check if already verified
        if already_verified:
            return {
                "success": True,
                "message": "Email is already verified"
            }

        # Check if token is expired
        if datetime.utcnow() > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired. Please request a new one."
            )

        # Mark email as verified and clear token
        cursor.execute("""
            UPDATE users
            SET is_email_verified = TRUE,
                verification_token = NULL,
                verification_token_expires_at = NULL
            WHERE id = %s
        """, (user_id,))

        conn.commit()
        conn.close()

        logger.info(f"✅ Email verified successfully for {user_email}")

        return {
            "success": True,
            "message": "Email verified successfully! You can now login."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in email verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error verifying email"
        )


@router.post("/resend-verification")
async def resend_verification_email(request: ResendVerificationRequest):
    """
    Resend verification email

    Generates a new verification token and sends it to the user.

    **Public endpoint** - No authentication required

    **Request:**
    - email: User's email address

    **Response:**
    - success: True/False
    - message: Confirmation message
    """
    import secrets
    from datetime import datetime, timedelta

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("""
            SELECT id, email, full_name, is_email_verified
            FROM users
            WHERE email = %s
        """, (request.email,))

        user_row = cursor.fetchone()

        # Always return success to prevent email enumeration
        if not user_row:
            logger.warning(f"Verification resend requested for non-existent email: {request.email}")
            return {
                "success": True,
                "message": "If the email exists and is not verified, a new verification link has been sent"
            }

        user_id = user_row[0]
        user_email = user_row[1]
        user_name = user_row[2]
        already_verified = user_row[3]

        # If already verified, don't send new token
        if already_verified:
            return {
                "success": True,
                "message": "This email is already verified"
            }

        # Generate new verification token (expires in 24 hours)
        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.utcnow() + timedelta(hours=24)

        # Update verification token
        cursor.execute("""
            UPDATE users
            SET verification_token = %s,
                verification_token_expires_at = %s
            WHERE id = %s
        """, (verification_token, verification_expires, user_id))

        conn.commit()
        conn.close()

        # Send verification email
        email_sent = email_service.send_verification_email(
            to_email=user_email,
            full_name=user_name,
            verification_token=verification_token
        )

        if email_sent:
            logger.info(f"✅ Verification email resent to {user_email}")
        else:
            logger.warning(f"⚠️  Could not resend verification email to {user_email} (email not configured)")

        return {
            "success": True,
            "message": "If the email exists and is not verified, a new verification link has been sent"
        }

    except Exception as e:
        logger.error(f"Error in resend verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error sending verification email"
        )
