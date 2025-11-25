#!/usr/bin/env python3
"""
Import SAT Product/Service Catalog from bambucode JSON
Source: https://github.com/bambucode/catalogos_sat_JSON

This script imports 52,514+ SAT product/service codes from bambucode's
maintained JSON catalog into PostgreSQL.

Usage:
    python3 scripts/migration/import_bambucode_catalog.py [--yes]
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import urllib.request
import psycopg2

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.shared.db_config import POSTGRES_CONFIG


BAMBUCODE_URL = "https://raw.githubusercontent.com/bambucode/catalogos_sat_JSON/refs/heads/master/c_ClaveProdServ.json"


def download_catalog() -> List[Dict[str, Any]]:
    """
    Download catalog JSON from bambucode GitHub.

    Returns:
        List of catalog entries
    """
    print(f"\n📥 Downloading catalog from bambucode...")
    print(f"   URL: {BAMBUCODE_URL}")

    try:
        with urllib.request.urlopen(BAMBUCODE_URL) as response:
            data = json.loads(response.read().decode('utf-8'))

        print(f"   ✅ Downloaded {len(data)} codes")
        return data

    except Exception as e:
        print(f"   ❌ Error downloading catalog: {e}")
        sys.exit(1)


def parse_catalog(data: List[Dict[str, Any]]) -> List[tuple]:
    """
    Parse bambucode JSON catalog into tuples for database insertion.

    Args:
        data: Raw JSON data from bambucode

    Returns:
        List of (code, name, description, family_hint) tuples
    """
    print(f"\n🔍 Parsing catalog entries...")

    catalog_entries = []
    skipped = 0

    for item in data:
        code = item.get('id', '').strip()
        descripcion = item.get('descripcion', '').strip()

        if not code or not descripcion:
            skipped += 1
            continue

        # Extract family hint from code (first 3 digits for most codes)
        # Example: 84111506 → family_hint = "841"
        family_hint = code[:3] if len(code) >= 3 else code

        # Use descripcion for both name and description
        # (bambucode doesn't separate them like phpcfdi)
        name = descripcion
        description = descripcion

        # Add palabrasSimilares if available (for future semantic search)
        palabras = item.get('palabrasSimilares', '').strip()
        if palabras:
            description = f"{descripcion} | Palabras: {palabras}"

        catalog_entries.append((code, name, description, family_hint))

    print(f"   ✅ Parsed {len(catalog_entries)} valid codes ({skipped} skipped)")
    return catalog_entries


def import_catalog_to_db(catalog_entries: List[tuple], batch_size: int = 1000, auto_yes: bool = False) -> bool:
    """
    Import catalog entries into PostgreSQL database.

    Args:
        catalog_entries: List of (code, name, description, family_hint) tuples
        batch_size: Number of records to insert per batch (default 1000)
        auto_yes: Automatically clear existing data without prompting

    Returns:
        True if successful, False otherwise
    """
    print(f"\n💾 Importing {len(catalog_entries)} codes to PostgreSQL...")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    try:
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'sat_product_service_catalog'
            )
        """)

        if not cursor.fetchone()[0]:
            print("   ❌ Table 'sat_product_service_catalog' does not exist")
            print("   Please run database migrations first")
            return False

        # Check existing records
        cursor.execute("SELECT COUNT(*) FROM sat_product_service_catalog")
        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            print(f"\n⚠️  Found {existing_count} existing records in catalog")
            if auto_yes:
                print("   Auto-clearing existing data...")
                cursor.execute("TRUNCATE TABLE sat_product_service_catalog")
                conn.commit()
                print("   ✅ Cleared existing data")
            else:
                response = input("   Clear existing data and reload? (y/N): ")
                if response.lower() == 'y':
                    cursor.execute("TRUNCATE TABLE sat_product_service_catalog")
                    conn.commit()
                    print("   ✅ Cleared existing data")
                else:
                    print("   Using UPSERT (will update existing codes)")

        # Batch insert
        inserted = 0
        updated = 0

        for i in range(0, len(catalog_entries), batch_size):
            batch = catalog_entries[i:i + batch_size]

            # Use UPSERT to handle duplicates
            cursor.executemany("""
                INSERT INTO sat_product_service_catalog
                    (code, name, description, family_hint)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    family_hint = EXCLUDED.family_hint,
                    updated_at = NOW()
            """, batch)

            inserted += len(batch)

            # Progress indicator
            progress = (i + len(batch)) / len(catalog_entries) * 100
            print(f"   Progress: {progress:.1f}% ({i + len(batch)}/{len(catalog_entries)})", end='\r')

        conn.commit()

        print(f"\n   ✅ Inserted/Updated {inserted} records")

        # Verify final count
        cursor.execute("SELECT COUNT(*) FROM sat_product_service_catalog")
        final_count = cursor.fetchone()[0]
        print(f"   📊 Total records in database: {final_count}")

        return True

    except Exception as e:
        print(f"\n   ❌ Error importing catalog: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def show_sample_codes(catalog_entries: List[tuple], count: int = 5):
    """Show sample codes from catalog."""
    print(f"\n📋 Sample codes (first {count}):")
    for i, (code, name, description, family_hint) in enumerate(catalog_entries[:count], 1):
        print(f"   {i}. {code}: {name[:60]}")
        if description != name:
            print(f"      Description: {description[:80]}")


def main():
    parser = argparse.ArgumentParser(
        description='Import SAT Product/Service Catalog from bambucode JSON'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of records to insert per batch (default: 1000)'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Automatically clear existing data without prompting'
    )
    parser.add_argument(
        '--sample-only',
        action='store_true',
        help='Only download and show sample, do not import'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("IMPORTING SAT CATALOG FROM BAMBUCODE JSON")
    print("=" * 80)
    print(f"\nSource: {BAMBUCODE_URL}")
    print("Maintained by: bambucode (GitHub)")

    # Download catalog
    data = download_catalog()

    # Parse catalog
    catalog_entries = parse_catalog(data)

    # Show sample
    show_sample_codes(catalog_entries)

    if args.sample_only:
        print("\n✅ Sample downloaded successfully (use without --sample-only to import)")
        return 0

    # Import to database
    success = import_catalog_to_db(
        catalog_entries,
        batch_size=args.batch_size,
        auto_yes=args.yes
    )

    if success:
        print("\n" + "=" * 80)
        print("✅ BAMBUCODE SAT CATALOG IMPORT COMPLETE")
        print("=" * 80)
        print(f"\nYour system now has {len(catalog_entries)} SAT product/service codes!")
        print("Includes codes missing in other catalogs (like 84111506)")
        print("Ready to classify invoices with complete SAT coverage 🚀\n")
        return 0
    else:
        print("\n❌ Import failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
