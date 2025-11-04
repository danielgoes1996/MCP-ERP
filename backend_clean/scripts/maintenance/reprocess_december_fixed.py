#!/usr/bin/env python3
"""
Reprocesar PDF de diciembre con el fix aplicado
"""
import requests

def reprocess_december():
    # Login
    login_url = "http://localhost:8004/auth/login"
    login_data = {
        "email": "dgomezes96@gmail.com",
        "password": "test123"
    }

    print("🔑 Logging in...")
    login_response = requests.post(login_url, json=login_data)

    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return

    # Get token
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload PDF
    pdf_path = "./uploads/statements/9_20250928_211924_Periodo_DIC 2024 (1).pdf"
    upload_url = "http://localhost:8004/bank-statements/accounts/7/upload"

    print("📄 Uploading December PDF...")

    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        upload_response = requests.post(upload_url, files=files, headers=headers)

    if upload_response.status_code == 201:
        print("✅ PDF uploaded and processed successfully!")
        result = upload_response.json()
        print(f"📊 Results: {result}")
    else:
        print(f"❌ Upload failed: {upload_response.status_code}")
        print(upload_response.text)

if __name__ == "__main__":
    reprocess_december()