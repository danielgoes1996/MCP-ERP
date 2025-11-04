"""
Authentication and authorization module
Implements JWT-based authentication with FastAPI
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import logging

from config.settings import settings
from core.database import get_db

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# Pydantic models
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: str


class UserInDB(UserBase):
    id: int
    hashed_password: str


class User(UserBase):
    id: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")

        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return TokenData(email=email, user_id=user_id)

    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Mock user storage (replace with database queries)
fake_users_db = {
    "admin@mcp.com": {
        "id": 1,
        "email": "admin@mcp.com",
        "full_name": "Admin User",
        "hashed_password": get_password_hash("admin123"),
        "is_active": True,
        "is_superuser": True,
    },
    "user@mcp.com": {
        "id": 2,
        "email": "user@mcp.com",
        "full_name": "Regular User",
        "hashed_password": get_password_hash("user123"),
        "is_active": True,
        "is_superuser": False,
    }
}


def get_user(email: str) -> Optional[UserInDB]:
    """Get a user by email (mock implementation)"""
    if email in fake_users_db:
        user_dict = fake_users_db[email]
        return UserInDB(**user_dict)
    return None


def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
    """Authenticate a user"""
    user = get_user(email)

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


# Dependency functions
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Get the current authenticated user"""
    token_data = decode_token(token)
    user = get_user(email=token_data.email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """Get the current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return current_user


async def get_current_superuser(current_user: UserInDB = Depends(get_current_active_user)) -> UserInDB:
    """Get the current superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    return current_user


# Optional: API Key authentication for backwards compatibility
class APIKeyAuth:
    """Simple API key authentication"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "default-api-key"

    def __call__(self, api_key: str = Depends(oauth2_scheme)) -> bool:
        """Validate API key"""
        if api_key != self.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        return True


# Create login endpoint function
def create_tokens(user: UserInDB) -> Token:
    """Create access and refresh tokens for a user"""
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email, "user_id": user.id}
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


if __name__ == "__main__":
    # Test password hashing
    test_password = "test123"
    hashed = get_password_hash(test_password)
    print(f"Password hash: {hashed}")
    print(f"Verify: {verify_password(test_password, hashed)}")

    # Test token creation
    test_data = {"sub": "test@example.com", "user_id": 1}
    token = create_access_token(test_data)
    print(f"Token: {token}")

    # Test token decode
    decoded = decode_token(token)
    print(f"Decoded: {decoded}")