#!/usr/bin/env python3
"""
Generate a test JWT token for frontend testing
"""

from datetime import datetime, timedelta
import jwt

# Same secret as in core/auth/jwt.py
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"

def generate_test_token(
    user_id: int = 17,
    tenant_id: int = 2,
    email: str = "test@test.com",
    role: str = "user"
):
    """Generate a test JWT token"""

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
    token = generate_test_token()

    print("\n" + "="*80)
    print("🔑 TEST JWT TOKEN GENERATED")
    print("="*80)
    print(f"\nToken: {token}")
    print(f"\nUser ID: 17")
    print(f"Tenant ID: 2")
    print(f"Email: test@test.com")
    print(f"Expires: 30 days from now")
    print("\n" + "="*80)
    print("📋 INSTRUCTIONS:")
    print("="*80)
    print("\n1. Copy the token above")
    print("2. Open browser console (F12)")
    print("3. Run: localStorage.setItem('token', 'YOUR_TOKEN_HERE')")
    print("4. Refresh the page")
    print("\nAlternatively, run:")
    print(f"  localStorage.setItem('token', '{token}')")
    print("\n" + "="*80 + "\n")
