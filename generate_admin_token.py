#!/usr/bin/env python3
"""
Generate JWT token for admin user (daniel@carretaverde.com)
Matches the exact format from core/auth/jwt.py
"""

from datetime import datetime, timedelta
import jwt
import os
import uuid

# Same secret as in core/auth/jwt.py
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mcp-development-secret-key-2025-contaflow")
ALGORITHM = "HS256"

def generate_admin_token(
    user_id: int = 11,
    tenant_id: int = 3,
    username: str = "daniel@carretaverde.com",
    role: str = "admin"
):
    """Generate a JWT token for Admin user matching core/auth/jwt.py format"""

    # Token expires in 30 days
    jti = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(days=30)

    # Match exact format from create_access_token() in core/auth/jwt.py
    payload = {
        "sub": str(user_id),  # JWT spec requires sub to be user_id as string
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "jti": jti,
        "exp": expire
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

if __name__ == "__main__":
    token = generate_admin_token()

    print("\n" + "="*80)
    print("🔑 ADMIN JWT TOKEN FOR DANIEL@CARRETAVERDE.COM")
    print("="*80)
    print(f"\nToken: {token}")
    print(f"\nUser ID: 11")
    print(f"Tenant ID: 3 (Carreta Verde)")
    print(f"Username: daniel@carretaverde.com")
    print(f"Role: admin")
    print(f"Expires: 30 days from now")
    print("\n" + "="*80)
    print("📋 COPY-PASTE THIS INTO BROWSER CONSOLE:")
    print("="*80)
    print(f"\nlocalStorage.setItem('auth_token', '{token}');")
    print(f"localStorage.setItem('refresh_token', '{token}');")
    print("\n" + "="*80)
    print("\n✅ Then refresh the page and navigate to /admin/users")
    print("\n" + "="*80)
    print("\n🧪 TEST THE TOKEN WITH CURL:")
    print("="*80)
    print(f'\ncurl -H "Authorization: Bearer {token}" http://localhost:8000/api/admin/users/')
    print("\n" + "="*80 + "\n")
