#!/usr/bin/env python3
"""
Desbloquear cuenta de daniel@carretaverde.com
"""
import sqlite3
import bcrypt

def hash_password(password: str) -> str:
    """Hash password con bcrypt"""
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def main():
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Tu email
    email = "daniel@carretaverde.com"
    new_password = "Daniel2024!"  # Contraseña temporal

    print(f"🔓 Desbloqueando cuenta para {email}...")

    # Hash nueva contraseña
    hashed_password = hash_password(new_password)

    # Resetear bloqueo y contraseña
    cursor.execute("""
        UPDATE users
        SET password_hash = ?,
            failed_login_attempts = 0,
            lock_until = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE email = ?
    """, (hashed_password, email))

    if cursor.rowcount > 0:
        conn.commit()
        print(f"✅ ¡Cuenta desbloqueada exitosamente!")
        print(f"📧 Email: {email}")
        print(f"🔑 Nueva contraseña temporal: {new_password}")
        print(f"\n🎯 Ahora puedes:")
        print(f"   1. Ir a http://localhost:3001/login")
        print(f"   2. Usar email: {email}")
        print(f"   3. Usar password: {new_password}")
        print(f"   4. Cambiar tu contraseña después de login")
    else:
        print(f"❌ Usuario {email} no encontrado en la base de datos")
        print(f"\n📝 Verificando usuarios existentes...")
        cursor.execute("SELECT email FROM users LIMIT 5")
        users = cursor.fetchall()
        if users:
            print("Usuarios encontrados:")
            for (user_email,) in users:
                print(f"  - {user_email}")

    conn.close()

if __name__ == "__main__":
    main()
