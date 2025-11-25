#!/usr/bin/env python3
"""
Upload real invoices to bulk endpoint
"""

import requests
import json
from pathlib import Path
import sys

# Configuration
API_BASE = "http://localhost:8000"
EMAIL = "daniel@contaflow.ai"
PASSWORD = "ContaFlow2025!"
TENANT_ID = 2
COMPANY_ID = 2

def login():
    """Get JWT token"""
    print("🔐 Logging in...")

    response = requests.post(
        f"{API_BASE}/auth/login",
        data={
            "username": EMAIL,
            "password": PASSWORD,
            "tenant_id": str(TENANT_ID)
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        sys.exit(1)

    token = response.json()["access_token"]
    print(f"✅ Token obtained: {token[:30]}...")
    return token


def upload_invoices(token):
    """Upload all XMLs in facturas_reales/"""

    xml_dir = Path("test_invoices/facturas_reales")
    xml_files = list(xml_dir.rglob("*.xml"))  # Recursive search

    if not xml_files:
        print("❌ No XML files found in test_invoices/facturas_reales/")
        sys.exit(1)

    print(f"\n📦 Found {len(xml_files)} XML files")
    print(f"📊 Uploading in batches...")

    # Upload in batches of 50 (to stay under size limits)
    batch_size = 50
    total_batches = (len(xml_files) + batch_size - 1) // batch_size

    results = []

    for i in range(0, len(xml_files), batch_size):
        batch_files = xml_files[i:i+batch_size]
        batch_num = (i // batch_size) + 1

        print(f"\n🔄 Batch {batch_num}/{total_batches} ({len(batch_files)} files)...")

        # Prepare files for upload
        files_data = []
        for xml_file in batch_files:
            files_data.append(
                ('files', (xml_file.name, open(xml_file, 'rb'), 'application/xml'))
            )

        # Upload
        response = requests.post(
            f"{API_BASE}/invoices/upload-bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=files_data,
            data={
                "company_id": str(COMPANY_ID),
                "create_placeholder_on_no_match": "true",
                "auto_link_threshold": "0.8",
                "batch_tag": f"facturas_reales_batch_{batch_num}"
            }
        )

        # Close file handles
        for _, file_tuple in files_data:
            file_tuple[1].close()

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Batch ID: {result.get('batch_id')}")
            print(f"   📊 Total invoices: {result.get('total_invoices')}")
            print(f"   🔗 Status URL: {result.get('status_url')}")
            results.append(result)
        else:
            print(f"   ❌ Error: {response.status_code}")
            print(f"   {response.text}")

    return results


def main():
    print("=" * 70)
    print("  🚀 CARGA MASIVA DE FACTURAS REALES")
    print("=" * 70)

    # Login
    token = login()

    # Upload
    results = upload_invoices(token)

    # Summary
    print("\n" + "=" * 70)
    print("  ✅ CARGA COMPLETADA")
    print("=" * 70)

    print(f"\n📊 Resumen:")
    print(f"   Batches creados: {len(results)}")
    print(f"   Total facturas: {sum(r.get('total_invoices', 0) for r in results)}")

    print(f"\n🔍 Batch IDs generados:")
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result.get('batch_id')}")

    print(f"\n📈 Monitorear progreso:")
    print(f"   1. API: {API_BASE}/api/bulk-invoice/batches")
    print(f"   2. DB:  sqlite3 unified_mcp_system.db \"SELECT status, COUNT(*) FROM invoice_import_logs GROUP BY status;\"")
    print()


if __name__ == "__main__":
    main()
