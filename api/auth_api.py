"""
API endpoints para autenticación JWT
Proporciona endpoints de login, registro, refresh token y logout
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from typing import Dict, Any, Optional
import logging

from core.auth.system import (
    auth_service,
    get_current_user,
    LoginRequest,
    RegisterRequest,
    AuthResponse,
    User,
    UserRole,
    validate_password_strength,
    security,
    require_role,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

logger = logging.getLogger(__name__)

# Router para endpoints de auth
router = APIRouter(prefix="/auth", tags=["Authentication"])


class ChangePasswordRequest(BaseModel):
    """Request para cambiar contraseña"""
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        if not validate_password_strength(v):
            raise ValueError('Password must be at least 8 characters with uppercase, lowercase and digit')
        return v


class UserProfileResponse(BaseModel):
    """Response del perfil de usuario"""
    id: int
    email: str
    full_name: str
    company_id: str
    company_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: str


@router.post("/login", response_model=AuthResponse)
async def login(request: Request):
    """
    Login de usuario con email y contraseña

    Retorna:
    - access_token: Token JWT para autenticación (30 min)
    - refresh_token: Token para renovar acceso (7 días)
    - user: Información del usuario autenticado
    """
    try:
        payload: Dict[str, Any]

        content_type = request.headers.get("content-type", "").lower()

        if "application/json" in content_type:
            payload = await request.json()
        elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            payload = {key: form.get(key) for key in form.keys()}
        else:
            payload = await request.json()

        email = payload.get("email") or payload.get("username") or ""
        password = payload.get("password") or ""
        company_id = payload.get("company_id") or payload.get("tenant_id")

        login_request = LoginRequest(email=email, password=password, company_id=company_id)

        logger.info(f"Login attempt for email: {login_request.email}")

        # Validar email
        if "@" not in login_request.email or len(login_request.email) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

        # Validar password
        if len(login_request.password) < 3:  # Mínimo básico para demo
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password too short"
            )

        response = auth_service.login_user(login_request)

        logger.info(f"Login successful for: {response.user.email}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """
    Registro de nuevo usuario

    Requiere:
    - email: Email único del usuario
    - password: Contraseña (mínimo 8 caracteres con mayúscula, minúscula y número)
    - full_name: Nombre completo
    - company_id: ID de empresa (opcional, se genera automáticamente)

    Retorna:
    - Tokens de autenticación y datos del usuario creado
    """
    try:
        logger.info(f"Registration attempt for email: {request.email}")

        # Validaciones adicionales
        if "@" not in request.email or len(request.email) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )

        if not validate_password_strength(request.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters with uppercase, lowercase and digit"
            )

        if len(request.full_name.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name must be at least 2 characters"
            )

        # Crear usuario
        user = auth_service.register_user(request)

        # Login automático después del registro
        login_request = LoginRequest(
            email=request.email,
            password=request.password,
            company_id=user.company_id
        )

        response = auth_service.login_user(login_request)

        logger.info(f"Registration successful for: {response.user.email}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error for {request.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Renovar access token usando refresh token

    Headers requeridos:
    - Authorization: Bearer <refresh_token>

    Retorna:
    - Nuevo access token
    - Mismo refresh token (hasta su expiración)
    """
    try:
        refresh_token = credentials.credentials

        response = auth_service.refresh_access_token(refresh_token)

        logger.info(f"Token refreshed for user: {response.user.email}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Obtener perfil del usuario autenticado

    Headers requeridos:
    - Authorization: Bearer <access_token>

    Retorna:
    - Información completa del perfil del usuario
    """
    try:
        logger.info(f"Profile requested for user: {current_user.email}")

        return UserProfileResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name or "No name",
            company_id=current_user.company_id,
            company_name=current_user.company_name,
            role=current_user.role,
            is_active=current_user.is_active,
            created_at=current_user.created_at.isoformat()
        )

    except Exception as e:
        logger.error(f"Profile error for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Cambiar contraseña del usuario autenticado

    Headers requeridos:
    - Authorization: Bearer <access_token>

    Body:
    - current_password: Contraseña actual
    - new_password: Nueva contraseña (debe cumplir criterios de seguridad)
    """
    try:
        logger.info(f"Password change attempt for user: {current_user.email}")

        # Verificar contraseña actual
        user_data = auth_service.get_user_by_email(current_user.email)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not auth_service.verify_password(request.current_password, user_data["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        # Verificar que la nueva contraseña sea diferente
        if auth_service.verify_password(request.new_password, user_data["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password"
            )

        # Actualizar contraseña
        new_hashed_password = auth_service.get_password_hash(request.new_password)
        auth_service.users_db[current_user.email]["hashed_password"] = new_hashed_password

        logger.info(f"Password changed successfully for user: {current_user.email}")

        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout del usuario (invalidar token)

    Headers requeridos:
    - Authorization: Bearer <access_token>

    Nota: En implementación completa, se agregaría el token a una blacklist
    """
    try:
        logger.info(f"User logged out: {current_user.email}")

        # En una implementación completa, aquí se agregaría el token a una blacklist
        # Por ahora, solo retornamos éxito

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/verify")
async def verify_token(current_user: User = Depends(get_current_user)):
    """
    Verificar validez del token

    Headers requeridos:
    - Authorization: Bearer <access_token>

    Retorna:
    - Información básica del usuario si el token es válido
    """
    try:
        return {
            "valid": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "role": current_user.role,
                "company_id": current_user.company_id
            }
        }

    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token verification failed"
        )


@router.get("/users", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def list_users(current_user: User = Depends(get_current_user)):
    """
    Listar usuarios (solo admin)

    Headers requeridos:
    - Authorization: Bearer <access_token> (debe ser admin)

    Retorna:
    - Lista de todos los usuarios del sistema
    """
    try:
        users = []
        for email, user_data in auth_service.users_db.items():
            users.append({
                "id": user_data["id"],
                "email": user_data["email"],
                "full_name": user_data.get("full_name", ""),
                "company_id": user_data["company_id"],
                "role": user_data["role"],
                "is_active": user_data["is_active"],
                "created_at": user_data["created_at"].isoformat()
            })

        logger.info(f"User list requested by admin: {current_user.email}")

        return {
            "users": users,
            "total": len(users)
        }

    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


# Endpoint de health check específico para auth
@router.get("/health")
async def auth_health():
    """
    Health check del sistema de autenticación
    """
    try:
        # Test básico de funcionalidad
        from datetime import datetime
        test_token = auth_service.create_access_token(User(
            id=1,
            email="test@test.com",
            company_id="test",
            role=UserRole.USER,
            is_active=True,
            created_at=datetime.utcnow()
        ))

        # Verificar que se puede decodificar
        token_data = auth_service.verify_token(test_token)

        return {
            "status": "healthy",
            "service": "authentication",
            "jwt_functional": token_data is not None,
            "users_registered": len(auth_service.users_db),
            "version": "1.0.0"
        }

    except Exception as e:
        logger.error(f"Auth health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "authentication",
            "error": str(e)
        }


# Información del sistema de auth
@router.get("/info")
async def auth_info():
    """
    Información del sistema de autenticación (público)
    """
    return {
        "service": "MCP Server Authentication",
        "version": "1.0.0",
        "features": [
            "JWT Authentication",
            "Role-based Access Control",
            "Token Refresh",
            "Password Security"
        ],
        "token_expiry": {
            "access_token": f"{ACCESS_TOKEN_EXPIRE_MINUTES} minutes",
            "refresh_token": f"{REFRESH_TOKEN_EXPIRE_DAYS} days"
        },
        "supported_roles": UserRole.get_all_roles(),
        "endpoints": {
            "login": "POST /auth/login",
            "register": "POST /auth/register",
            "refresh": "POST /auth/refresh",
            "profile": "GET /auth/profile",
            "logout": "POST /auth/logout"
        }
    }


if __name__ == "__main__":
    # Test básico del router
    print("✅ Auth API router configured successfully")
    print(f"✅ Available endpoints: {len(router.routes)}")
