#!/usr/bin/env python3
"""
Trigger processing for pending batches
"""

import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8000/auth/login",
    data={
        "username": "daniel@contaflow.ai",
        "password": "daniel123",
        "tenant_id": 2
    }
)

token = login_response.json()["access_token"]
print(f"✅ Logged in. Token: {token[:50]}...")

# Get batch ID (use the one from previous upload)
batch_id = "batch_e43cc56195264935"

# Trigger processing
print(f"\n🚀 Triggering processing for batch {batch_id}...")

headers = {"Authorization": f"Bearer {token}"}

response = requests.post(
    f"http://localhost:8000/invoices/process-batch/{batch_id}",
    headers=headers,
    timeout=300
)

print(f"\n📊 Status: {response.status_code}")

if response.status_code == 200:
    result = response.json()
    print("\n✅ Processing completed successfully!")
    print(json.dumps(result, indent=2))
else:
    print(f"\n❌ Error: {response.text}")
