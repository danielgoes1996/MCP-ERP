#!/usr/bin/env python3
"""
Script para resetear la contraseña de un usuario en ContaFlow
"""
import sqlite3
import bcrypt
import sys

def reset_password(email: str, new_password: str):
    """Resetea la contraseña de un usuario"""

    # Generar el hash de la nueva contraseña
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')

    # Conectar a la base de datos
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    try:
        # Verificar que el usuario existe
        cursor.execute("SELECT id, name, email FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            print(f"❌ Usuario con email '{email}' no encontrado")
            return False

        print(f"✅ Usuario encontrado:")
        print(f"   ID: {user[0]}")
        print(f"   Nombre: {user[1]}")
        print(f"   Email: {user[2]}")
        print()

        # Actualizar la contraseña
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (password_hash, email)
        )
        conn.commit()

        print(f"✅ Contraseña actualizada exitosamente para {email}")
        print(f"   Nueva contraseña: {new_password}")
        return True

    except Exception as e:
        print(f"❌ Error al resetear contraseña: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def verify_password(email: str, password: str):
    """Verifica si una contraseña es correcta para un usuario"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT password_hash FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()

        if not result:
            print(f"❌ Usuario con email '{email}' no encontrado")
            return False

        password_hash = result[0]

        if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            print(f"✅ La contraseña es correcta para {email}")
            return True
        else:
            print(f"❌ La contraseña es incorrecta para {email}")
            return False

    except Exception as e:
        print(f"❌ Error al verificar contraseña: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso:")
        print("  Resetear contraseña:")
        print("    python reset_password.py reset <email> <nueva_contraseña>")
        print()
        print("  Verificar contraseña:")
        print("    python reset_password.py verify <email> <contraseña>")
        print()
        print("Ejemplo:")
        print("    python reset_password.py reset daniel@contaflow.ai MiNuevaContraseña123")
        print("    python reset_password.py verify daniel@contaflow.ai MiNuevaContraseña123")
        sys.exit(1)

    action = sys.argv[1]

    if action == "reset":
        if len(sys.argv) != 4:
            print("❌ Uso: python reset_password.py reset <email> <nueva_contraseña>")
            sys.exit(1)
        email = sys.argv[2]
        new_password = sys.argv[3]
        reset_password(email, new_password)

    elif action == "verify":
        if len(sys.argv) != 4:
            print("❌ Uso: python reset_password.py verify <email> <contraseña>")
            sys.exit(1)
        email = sys.argv[2]
        password = sys.argv[3]
        verify_password(email, password)

    else:
        print(f"❌ Acción desconocida: {action}")
        print("   Usa 'reset' o 'verify'")
        sys.exit(1)
