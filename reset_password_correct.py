#!/usr/bin/env python3
"""
Reset password for daniel@carretaverde.com using correct field name
"""

import sys
sys.path.insert(0, '/Users/danielgoes96/Desktop/mcp-server')

from core.auth.jwt import get_password_hash, get_db_connection

email = "daniel@carretaverde.com"
new_password = "test123"

# Hash the new password
password_hash = get_password_hash(new_password)

# Update in database
conn = get_db_connection()
cursor = conn.cursor()

try:
    # Use password_hash field
    cursor.execute("""
        UPDATE users
        SET password_hash = %s,
            failed_login_attempts = 0,
            locked_until = NULL,
            is_email_verified = TRUE,
            status = 'active'
        WHERE email = %s
        RETURNING id, email, name, role
    """, (password_hash, email))

    result = cursor.fetchone()
    conn.commit()

    if result:
        print(f"✅ Password reset successful!")
        print(f"   User ID: {result[0]}")
        print(f"   Email: {result[1]}")
        print(f"   Name: {result[2]}")
        print(f"   Role: {result[3]}")
        print(f"   New Password: {new_password}")
    else:
        print(f"❌ User {email} not found")

except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    conn.close()
