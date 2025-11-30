#!/usr/bin/env python3
"""
Reset password for daniel@carretaverde.com to a known value
"""
import os
import sys

# Add the current directory to the path so we can import bcrypt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bcrypt

def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def main():
    # New password for Daniel
    new_password = "Daniel2025!"
    email = "daniel@carretaverde.com"

    print(f"🔐 Reseteando contraseña para {email}...")

    # Hash the password
    hashed_password = hash_password(new_password)

    # Import psycopg2 for PostgreSQL
    import psycopg2

    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB", "mcp_system"),
        user=os.getenv("POSTGRES_USER", "mcp_user"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme")
    )
    cursor = conn.cursor()

    # Update password and unlock account
    cursor.execute("""
        UPDATE users
        SET password = %s,
            failed_login_attempts = 0,
            locked_until = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE email = %s
    """, (hashed_password, email))

    if cursor.rowcount > 0:
        conn.commit()
        print(f"\n✅ ¡Contraseña actualizada exitosamente!")
        print(f"\n📧 Email: {email}")
        print(f"🔑 Nueva contraseña: {new_password}")
        print(f"\n🎯 Ahora puedes:")
        print(f"   1. Ir a http://localhost:3001/login")
        print(f"   2. Usar email: {email}")
        print(f"   3. Usar password: {new_password}")
        print(f"   4. ✅ Login funcionará permanentemente\n")
    else:
        print(f"\n❌ Usuario {email} no encontrado")

    conn.close()

if __name__ == "__main__":
    main()
