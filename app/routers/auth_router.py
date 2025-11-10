"""Unified authentication router (new modular structure)."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import HTTPAuthorizationCredentials

from core.auth.system import (
    LoginRequest,
    RegisterRequest,
    AuthResponse,
    User,
    UserRole,
    security,
    get_current_user,
    require_role,
)
from core.auth.jwt import (
    User as JWTUser,
    get_current_user as get_current_jwt_user,
    Token,
)
from app.services import auth_service as auth_services
from api.auth_api import ChangePasswordRequest, UserProfileResponse
from api.auth_jwt_api import TenantInfo, UserProfile
from api.v1.user_context import (
    AuthStatusResponse,
    MarkOnboardingResponse,
    ContextStatusResponse,
    UserFullContextResponse,
    UserProfileContext,
    _build_ai_context_summary,
    _build_company_settings_response,
    _build_ai_stack,
    _derive_permissions,
)
from core.auth.jwt import get_db_connection
from core.config.company_settings import get_company_settings_by_tenant

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(request: Request) -> AuthResponse:
    """Login endpoint that accepts JSON or form payloads."""
    try:
        content_type = request.headers.get("content-type", "").lower()

        if "application/json" in content_type:
            payload = await request.json()
        elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            payload = {key: form.get(key) for key in form.keys()}
        else:
            # fallback: try json
            payload = await request.json()

        email = payload.get("email") or payload.get("username") or ""
        password = payload.get("password") or ""
        company_id = payload.get("company_id") or payload.get("tenant_id")

        login_request = LoginRequest(email=email, password=password, company_id=company_id)
        return auth_services.login(login_request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest) -> AuthResponse:
    """Register new user and return auth tokens."""
    return auth_services.register(request)


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthResponse:
    """Refresh access token using the provided refresh token."""
    return auth_services.refresh(credentials.credentials)


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    """Return profile for the currently authenticated user."""
    user = auth_services.get_profile(current_user)
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name or "No name",
        company_id=user.company_id,
        company_name=getattr(user, "company_name", None),
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if getattr(user, "created_at", None) else None,
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Change password for the current user."""
    return auth_services.change_password(current_user, request.current_password, request.new_password)


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)) -> dict:
    """Invalidate current session (stateless demo)."""
    return auth_services.logout(current_user)


@router.get("/verify")
async def verify_token(current_user: User = Depends(get_current_user)) -> dict:
    """Verify validity of the provided access token."""
    return auth_services.verify(current_user)


@router.get("/users", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def list_users() -> dict:
    """List registered users (admin only)."""
    return auth_services.list_users()


@router.get("/tenants", response_model=List[TenantInfo])
async def list_tenants(email: Optional[str] = None) -> List[TenantInfo]:
    """Expose tenants available for selection during login."""
    data = auth_services.get_available_tenants(email)
    return [TenantInfo(**item) for item in data]


@router.post("/login/form", response_model=Token)
async def jwt_login(
    username: str = Form(...),
    password: str = Form(...),
    tenant_id: Optional[int] = Form(None),
) -> Token:
    """Form-based login supporting tenant selection (legacy compatibility)."""
    return auth_services.jwt_login(username, password, tenant_id)


@router.get("/me", response_model=AuthStatusResponse)
async def get_auth_status(current_user: JWTUser = Depends(get_current_jwt_user)) -> AuthStatusResponse:
    """Return authentication status and onboarding metadata using JWT auth."""
    context_summary = _build_ai_context_summary(current_user.tenant_id)
    return AuthStatusResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        onboarding_completed=getattr(current_user, "onboarding_completed", False),
        onboarding_completed_at=getattr(current_user, "onboarding_completed_at", None),
        last_context_update=context_summary.last_context_update,
        topics=context_summary.topics,
        summary=context_summary.summary,
    )


@router.post("/mark_onboarding", response_model=MarkOnboardingResponse)
async def mark_onboarding_completed(current_user: JWTUser = Depends(get_current_jwt_user)) -> MarkOnboardingResponse:
    """Mark onboarding as completed for the current user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET onboarding_completed = 1,
                onboarding_completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (current_user.id,),
        )
        conn.commit()

        cursor.execute(
            """
            SELECT onboarding_completed, onboarding_completed_at
            FROM users
            WHERE id = ?
            """,
            (current_user.id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return MarkOnboardingResponse(
            onboarding_completed=bool(row[0]),
            onboarding_completed_at=row[1],
        )
    finally:
        conn.close()


@router.get("/context-status", response_model=ContextStatusResponse)
async def get_context_status_route(current_user: JWTUser = Depends(get_current_jwt_user)) -> ContextStatusResponse:
    """Expose onboarding completion and latest AI context summary."""
    summary = _build_ai_context_summary(current_user.tenant_id)
    return ContextStatusResponse(
        onboarding_completed=getattr(current_user, "onboarding_completed", False),
        last_context_update=summary.last_context_update,
        topics=summary.topics,
        summary=summary.summary,
    )


@router.get("/context/full", response_model=UserFullContextResponse)
async def get_full_context(current_user: JWTUser = Depends(get_current_jwt_user)) -> UserFullContextResponse:
    """Return full profile/context stack for current user."""
    tenant_settings = get_company_settings_by_tenant(current_user.tenant_id)
    company_response = _build_company_settings_response(tenant_settings)
    company_name = tenant_settings.company_name if tenant_settings else None

    ai_stack = _build_ai_stack(tenant_settings.company_id if tenant_settings else None)
    ai_context = _build_ai_context_summary(current_user.tenant_id)
    permissions = _derive_permissions(current_user.role)

    user_profile = UserProfileContext(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        company_id=tenant_settings.company_id if tenant_settings else getattr(current_user, "company_id", None),
        company_name=company_name,
        onboarding_completed=getattr(current_user, "onboarding_completed", False),
        onboarding_completed_at=getattr(current_user, "onboarding_completed_at", None),
    )

    return UserFullContextResponse(
        user=user_profile,
        permissions=permissions,
        company_settings=company_response,
        ai_stack=ai_stack,
        ai_context=ai_context,
    )


@router.get("/jwt/profile", response_model=UserProfile)
async def get_jwt_profile(current_user: JWTUser = Depends(get_current_jwt_user)) -> UserProfile:
    """Return JWT-based profile (multi-tenant flow)."""
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        employee_id=current_user.employee_id,
    )


@router.post("/jwt/logout")
async def jwt_logout(current_user: JWTUser = Depends(get_current_jwt_user)) -> dict:
    """Logout for JWT-based sessions."""
    return auth_services.jwt_logout(current_user)
