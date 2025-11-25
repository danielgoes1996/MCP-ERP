#!/usr/bin/env python3
"""
Script para resetear contraseñas de usuarios de prueba
"""

import sqlite3
import bcrypt

DB_PATH = "unified_mcp_system.db"

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def reset_user_passwords():
    """Reset passwords for test users"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Test users with passwords
    test_users = [
        ("admin", "admin123"),
        ("daniel", "daniel123"),
    ]

    print("🔐 Reseteando contraseñas de usuarios de prueba...\n")

    for username, password in test_users:
        # Check if user exists
        cursor.execute("SELECT id, username, tenant_id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user:
            user_id, user_name, tenant_id = user
            password_hash = hash_password(password)

            cursor.execute(
                "UPDATE users SET password_hash = ?, is_active = 1, email_verified = 1 WHERE id = ?",
                (password_hash, user_id)
            )

            print(f"✅ Usuario '{user_name}' actualizado:")
            print(f"   - ID: {user_id}")
            print(f"   - Tenant ID: {tenant_id}")
            print(f"   - Password: {password}")
            print()
        else:
            print(f"⚠️  Usuario '{username}' no encontrado, creándolo...")
            password_hash = hash_password(password)

            cursor.execute("""
                INSERT INTO users (username, name, email, password_hash, tenant_id, role, is_active, email_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                username.capitalize(),
                f"{username}@contaflow.ai",
                password_hash,
                2 if username == "daniel" else 1,
                "admin",
                1,
                1
            ))

            print(f"✅ Usuario '{username}' creado con password: {password}\n")

    conn.commit()
    conn.close()

    print("\n🎉 Contraseñas actualizadas exitosamente!")
    print("\n📝 Usuarios de prueba disponibles:")
    print("   - Username: admin    | Password: admin123    | Tenant: 1")
    print("   - Username: daniel   | Password: daniel123   | Tenant: 2")

if __name__ == "__main__":
    reset_user_passwords()
