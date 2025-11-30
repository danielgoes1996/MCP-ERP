#!/usr/bin/env python3
"""
Generate JWT token for daniel@carretaverde.com
"""

from datetime import datetime, timedelta
import jwt
import os

# Same secret as in core/auth/jwt.py
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mcp-development-secret-key-2025-contaflow")
ALGORITHM = "HS256"

def generate_token(
    user_id: int = 11,
    tenant_id: int = 3,
    email: str = "daniel@carretaverde.com",
    role: str = "user"
):
    """Generate a JWT token for Daniel"""

    # Token expires in 30 days
    expire = datetime.utcnow() + timedelta(days=30)

    payload = {
        "sub": email,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
        "type": "access"
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

if __name__ == "__main__":
    token = generate_token()

    print("\n" + "="*80)
    print("🔑 JWT TOKEN FOR DANIEL@CARRETAVERDE.COM")
    print("="*80)
    print(f"\nToken: {token}")
    print(f"\nUser ID: 11")
    print(f"Tenant ID: 3 (Carreta Verde)")
    print(f"Email: daniel@carretaverde.com")
    print(f"Role: user")
    print(f"Expires: 30 days from now")
    print("\n" + "="*80)
    print("📋 COPY-PASTE THIS INTO BROWSER CONSOLE:")
    print("="*80)
    print(f"\nlocalStorage.setItem('token', '{token}');")
    print("\n" + "="*80)
    print("\n✅ Then refresh the page and you'll be logged in!")
    print("\n" + "="*80 + "\n")
