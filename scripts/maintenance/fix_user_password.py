#!/usr/bin/env python3
"""
Arreglar contraseña de usuario para evitar error de bcrypt
"""
import sqlite3
import bcrypt

def hash_password(password: str) -> str:
    """Hash password con bcrypt, truncando si es necesario"""
    # Truncate to 72 bytes if necessary
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')

    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def main():
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Nueva contraseña simple
    new_password = "admin123"
    email = "dgomezes96@gmail.com"

    print(f"🔄 Reseteando contraseña para {email}...")

    # Hash nueva contraseña
    hashed_password = hash_password(new_password)

    # Actualizar en base de datos
    cursor.execute("""
        UPDATE users
        SET password_hash = ?,
            failed_login_attempts = 0,
            locked_until = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE email = ?
    """, (hashed_password, email))

    if cursor.rowcount > 0:
        conn.commit()
        print(f"✅ Contraseña actualizada para {email}")
        print(f"📝 Nueva contraseña: {new_password}")
        print("🔐 Ahora puedes hacer login con esta contraseña")
    else:
        print(f"❌ Usuario {email} no encontrado")

    conn.close()

if __name__ == "__main__":
    main()