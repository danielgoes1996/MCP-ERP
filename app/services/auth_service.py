"""Service layer for authentication domain during refactor."""

from typing import List, Optional

from fastapi import HTTPException, status

from core.auth_system import (
    auth_service,
    LoginRequest,
    RegisterRequest,
    AuthResponse,
    User,
    UserRole,
    validate_password_strength,
)
from core.auth_jwt import (
    User as JWTUser,
    Token,
    authenticate_user,
    create_access_token,
    get_current_user as get_current_jwt_user,
    get_db_connection,
    ACCESS_TOKEN_EXPIRE_MINUTES as JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
)
from core.unified_auth import (
    RegisterRequest as UnifiedRegisterRequest,
    RegistrationError,
    UserInDB,
    create_tokens_for_user as unified_create_tokens,
    create_user as unified_create_user,
)


def login(request: LoginRequest) -> AuthResponse:
    return auth_service.login_user(request)


def _sync_legacy_user_cache(user: UserInDB, company_identifier: str, password_hash: str) -> None:
    """Mantiene compatibilidad con el cache in-memory de auth_service."""
    auth_service.users_db[user.email] = {
        "id": user.id,
        "email": user.email,
        "hashed_password": password_hash,
        "company_id": company_identifier,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "full_name": user.full_name,
    }


def register(request: RegisterRequest) -> AuthResponse:
    unified_request = UnifiedRegisterRequest(
        email=request.email,
        full_name=request.full_name,
        password=request.password,
        company_name=request.company_id,
    )

    try:
        created_user = unified_create_user(unified_request)
    except RegistrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    company_identifier = (
        request.company_id
        or (created_user.company_id and str(created_user.company_id))
        or f"tenant_{created_user.tenant_id}"
    )

    _sync_legacy_user_cache(created_user, company_identifier, created_user.password_hash)

    legacy_user = User(
        id=created_user.id,
        email=created_user.email,
        company_id=company_identifier,
        company_name=None,
        tenant_id=created_user.tenant_id,
        role=created_user.role,
        is_active=created_user.is_active,
        created_at=created_user.created_at,
        full_name=created_user.full_name,
    )

    tokens = unified_create_tokens(created_user)

    return AuthResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user=legacy_user,
    )


def refresh(refresh_token: str) -> AuthResponse:
    return auth_service.refresh_access_token(refresh_token)


def get_profile(current_user: User) -> User:
    return current_user


def change_password(current_user: User, current_password: str, new_password: str) -> dict:
    if not validate_password_strength(new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters with uppercase, lowercase and digit",
        )

    user_data = auth_service.get_user_by_email(current_user.email)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not auth_service.verify_password(current_password, user_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if auth_service.verify_password(new_password, user_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    new_hashed_password = auth_service.get_password_hash(new_password)

    # Persist for in-memory demo users
    auth_service.users_db[current_user.email] = {
        **user_data,
        "hashed_password": new_hashed_password,
    }

    return {"message": "Password changed successfully"}


def logout(_: User) -> dict:
    return {"message": "Logged out successfully"}


def verify(current_user: User) -> dict:
    return {
        "valid": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role,
            "company_id": current_user.company_id,
        },
    }


def list_users() -> dict:
    users = []
    for user_data in auth_service.users_db.values():
        users.append(
            {
                "id": user_data["id"],
                "email": user_data["email"],
                "full_name": user_data.get("full_name", ""),
                "company_id": user_data["company_id"],
                "role": user_data["role"],
                "is_active": user_data.get("is_active", True),
                "created_at": user_data["created_at"].isoformat() if user_data.get("created_at") else None,
            }
        )
    return {"users": users, "total": len(users)}


def get_available_tenants(email: Optional[str] = None) -> List[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if email:
            cursor.execute(
                """
                SELECT DISTINCT t.id, t.name
                FROM tenants t
                JOIN users u ON u.tenant_id = t.id
                WHERE LOWER(u.email) = LOWER(?)
                ORDER BY t.name
                """,
                (email.strip(),),
            )
            rows = cursor.fetchall()
            if not rows:
                cursor.execute(
                    """
                    SELECT id, name
                    FROM tenants
                    ORDER BY name
                    """
                )
                rows = cursor.fetchall()
        else:
            cursor.execute(
                """
                SELECT id, name
                FROM tenants
                ORDER BY name
                """
            )
            rows = cursor.fetchall()

        return [
            {"id": row["id"], "name": row["name"], "description": None}
            for row in rows
        ]
    finally:
        conn.close()


def jwt_login(username: str, password: str, tenant_id: Optional[int]) -> Token:
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id is required for login",
        )

    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT t.id, t.name
            FROM tenants t
            INNER JOIN users u ON u.tenant_id = t.id
            WHERE u.id = ? AND t.id = ?
            """,
            (user.id, tenant_id),
        )
        tenant_row = cursor.fetchone()
        if not tenant_row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this tenant",
            )

        user.tenant_id = tenant_id
        access_token = create_access_token(user)

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user,
            tenant={"id": tenant_row["id"], "name": tenant_row["name"], "description": None},
        )
    finally:
        conn.close()


def jwt_logout(current_user: JWTUser) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE user_sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (current_user.id,),
        )
        conn.commit()
    finally:
        conn.close()
    return {"success": True, "message": "Logout successful"}


def get_jwt_profile(current_user: JWTUser) -> JWTUser:
    return current_user


def get_auth_status(current_user: JWTUser) -> JWTUser:
    return current_user
