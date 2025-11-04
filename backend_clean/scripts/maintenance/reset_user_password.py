#!/usr/bin/env python3
"""
Script para resetear contraseña de usuario
"""

import sqlite3
import sys
from passlib.context import CryptContext

def reset_password(email: str, new_password: str):
    """Resetear contraseña de un usuario"""

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    db_path = "unified_mcp_system.db"

    try:
        # Hash de la nueva contraseña
        hashed_password = pwd_context.hash(new_password)

        # Actualizar en la base de datos
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Verificar que el usuario existe
            cursor.execute("SELECT id, email FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()

            if not user:
                print(f"❌ Usuario {email} no encontrado")
                return False

            # Actualizar contraseña
            cursor.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE email = ?",
                (hashed_password, email)
            )

            print(f"✅ Contraseña actualizada para {email}")
            print(f"   Nueva contraseña: {new_password}")
            print(f"   Hash: {hashed_password[:30]}...")

            return True

    except Exception as e:
        print(f"❌ Error resetando contraseña: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python reset_user_password.py <email> <nueva_contraseña>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    success = reset_password(email, password)
    sys.exit(0 if success else 1)