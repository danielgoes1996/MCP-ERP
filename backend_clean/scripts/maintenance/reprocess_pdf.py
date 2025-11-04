#!/usr/bin/env python3
"""
Re-process PDF through the web interface endpoint
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

    # Try to find and use the PDF upload endpoint
    pdf_path = "/Users/danielgoes96/Desktop/mcp-server/uploads/statements/9_20250928_000304_Periodo_JUL 2025 (1).pdf"

    headers = {"Authorization": f"Bearer {token}"}

    # Try the bank reconciliation movements endpoint
    print("📄 Uploading PDF for processing...")

    try:
        with open(pdf_path, 'rb') as pdf_file:
            files = {'file': pdf_file}
            data = {'account_id': '5'}

            response = requests.post(
                "http://localhost:8001/bank_reconciliation/movements",
                headers=headers,
                files=files,
                data=data,
                timeout=300
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ PDF processed successfully: {result}")
            else:
                print(f"❌ PDF processing failed: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Error uploading PDF: {e}")

    # Check final transaction count
    print("\n📊 Checking final transaction count...")
    movements_response = requests.get(
        "http://localhost:8001/bank-movements/account/5",
        headers=headers
    )

    if movements_response.status_code == 200:
        transactions = movements_response.json()
        print(f"✅ Found {len(transactions)} transactions in database")

        # Show date range
        if transactions:
            dates = [t['date'] for t in transactions]
            print(f"📅 Date range: {min(dates)} to {max(dates)}")
    else:
        print(f"❌ Failed to check transactions: {movements_response.status_code}")

if __name__ == "__main__":
    main()