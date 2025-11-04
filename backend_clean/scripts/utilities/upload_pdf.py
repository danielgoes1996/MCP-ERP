#!/usr/bin/env python3
"""
Upload PDF using the API and parse with corrected date logic
"""
import requests

def main():
    # Login first
    login_url = "http://localhost:8001/auth/login"
    login_data = {"email": "dgomezes96@gmail.com", "password": "temp123"}

    print("🔑 Logging in...")
    login_response = requests.post(login_url, json=login_data)

    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.text}")
        return

    token = login_response.json()["access_token"]
    print("✅ Login successful")

    # Re-parse existing transactions
    reparse_url = "http://localhost:8001/bank-movements/reparse-with-improved-rules"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"account_id": 5}

    print("🔄 Re-parsing transactions with corrected date logic...")
    reparse_response = requests.post(reparse_url, headers=headers, params=params)

    if reparse_response.status_code == 200:
        result = reparse_response.json()
        print(f"✅ Re-parsed successfully: {result}")
    else:
        print(f"❌ Re-parse failed: {reparse_response.status_code} - {reparse_response.text}")

if __name__ == "__main__":
    main()