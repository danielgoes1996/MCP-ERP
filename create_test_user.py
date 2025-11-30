#!/usr/bin/env python3
"""Create test user for manual expense testing"""
import sys
import psycopg2
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash a simple password
password = "test123"
hashed = pwd_context.hash(password)

# Connect to PostgreSQL
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5433,
    database="mcp_system",
    user="mcp_user",
    password="changeme"
)

cursor = conn.cursor()

# Delete existing test user if exists
cursor.execute("DELETE FROM users WHERE email = 'test@test.com'")

# Insert new test user
cursor.execute("""
    INSERT INTO users (
        email, username, password_hash, is_active, is_email_verified, tenant_id, created_at
    ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
    RETURNING id
""", ("test@test.com", "test@test.com", hashed, True, True, 2))

user_id = cursor.fetchone()[0]
conn.commit()

print(f"✅ Test user created successfully!")
print(f"   Email: test@test.com")
print(f"   Password: test123")
print(f"   User ID: {user_id}")
print(f"   Tenant ID: 1")

conn.close()
