#!/usr/bin/env python3
"""
Import Full SAT Product/Service Catalog from Official Anexo 20

This script imports the complete SAT c_ClaveProdServ catalog (~52,000 codes) from:
1. Excel file (.xlsx/.xls) from SAT's Anexo 20 CFDI 4.0
2. CSV export of the catalog

Official source: http://www.sat.gob.mx/tramitesyservicios/Paginas/anexo_20_version3-3.htm

Usage:
    python3 import_full_sat_catalog.py --file path/to/c_ClaveProdServ.xlsx
    python3 import_full_sat_catalog.py --file path/to/c_ClaveProdServ.csv
    python3 import_full_sat_catalog.py --download  # Auto-download from SAT (if available)
"""

import sys
import os
import argparse
import requests
from pathlib import Path
from typing import List, Tuple, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import psycopg2
from config.config import config

try:
    import pandas as pd
except ImportError:
    print("❌ Error: pandas library required")
    print("   Install with: pip install pandas openpyxl")
    sys.exit(1)


def get_db_connection():
    """Get PostgreSQL connection."""
    password_part = f" password={config.PG_PASSWORD}" if config.PG_PASSWORD else ""
    dsn = f"host={config.PG_HOST} port={config.PG_PORT} dbname={config.PG_DB} user={config.PG_USER}{password_part}"
    return psycopg2.connect(dsn)


def download_sat_catalog(output_path: str) -> bool:
    """
    Attempt to download SAT catalog from official source.

    Note: The SAT website may require manual download.
    This function attempts common endpoints.
    """
    print("\n📥 Attempting to download SAT catalog from official source...")

    # Try different known URLs for the catalog
    urls = [
        "http://omawww.sat.gob.mx/tramitesyservicios/Paginas/documentos/catCFDI.xls",
        "http://www.sat.gob.mx/sitio_internet/cfd/catalogos/catCFDI.xls",
        "https://www.sat.gob.mx/consultas/92764/catalogo-de-productos-y-servicios",
    ]

    for url in urls:
        try:
            print(f"   Trying: {url}")
            response = requests.get(url, timeout=30, allow_redirects=True)

            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"   ✅ Downloaded to {output_path}")
                return True
            else:
                print(f"   ⚠️  HTTP {response.status_code}")

        except Exception as e:
            print(f"   ⚠️  Failed: {e}")
            continue

    print("\n⚠️  Auto-download failed. Please download manually from:")
    print("   https://www.sat.gob.mx/consultas/53693/catalogo-de-productos-y-servicios")
    print("   Look for 'Anexo 20' → 'c_ClaveProdServ' tab in Excel\n")
    return False


def parse_excel_catalog(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    Parse SAT catalog from Excel file (Anexo 20 format).

    Expected columns in c_ClaveProdServ sheet:
    - c_ClaveProdServ (8-digit code)
    - Descripción (official name)
    - Palabras similares (optional keywords)
    - Fecha_inicio_vigencia / Fecha_fin_vigencia (optional)

    Returns:
        List of tuples: (code, name, description, family_hint)
    """
    print(f"\n📖 Parsing Excel file: {file_path}")

    try:
        # Try to read from 'c_ClaveProdServ' sheet (common in Anexo 20)
        df = pd.read_excel(file_path, sheet_name='c_ClaveProdServ')
    except ValueError:
        # If sheet doesn't exist, try first sheet
        print("   Sheet 'c_ClaveProdServ' not found, using first sheet")
        df = pd.read_excel(file_path, sheet_name=0)

    print(f"   Found {len(df)} rows")

    # Identify columns (SAT uses Spanish names)
    code_col = None
    name_col = None

    for col in df.columns:
        col_lower = str(col).lower()
        if 'clave' in col_lower or 'codigo' in col_lower:
            code_col = col
        elif 'descripcion' in col_lower or 'nombre' in col_lower:
            name_col = col

    if not code_col or not name_col:
        raise ValueError(
            f"Could not identify required columns in file.\n"
            f"   Available columns: {list(df.columns)}\n"
            f"   Expected: 'c_ClaveProdServ' or similar for code, 'Descripción' for name"
        )

    print(f"   Using columns: code='{code_col}', name='{name_col}'")

    # Parse rows
    catalog_entries = []
    skipped = 0

    for idx, row in df.iterrows():
        try:
            code = str(row[code_col]).strip()
            name = str(row[name_col]).strip()

            # Validate code format (should be 8 digits)
            if not code or len(code) != 8 or not code.isdigit():
                skipped += 1
                continue

            # Extract family hint (first 3 digits)
            family_hint = code[:3]

            # Use name as description (can be enhanced later)
            description = name

            catalog_entries.append((code, name, description, family_hint))

        except Exception as e:
            skipped += 1
            continue

    print(f"   ✅ Parsed {len(catalog_entries)} valid codes ({skipped} skipped)")
    return catalog_entries


def parse_csv_catalog(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    Parse SAT catalog from CSV file.

    Expected format:
    code,name,description (optional)
    15101514,"Gasolina Magna","Gasolina de octanaje regular"
    """
    print(f"\n📖 Parsing CSV file: {file_path}")

    df = pd.read_csv(file_path)
    print(f"   Found {len(df)} rows")

    # Identify columns
    code_col = df.columns[0]  # Assume first column is code
    name_col = df.columns[1]  # Second column is name
    desc_col = df.columns[2] if len(df.columns) > 2 else name_col

    catalog_entries = []
    skipped = 0

    for idx, row in df.iterrows():
        try:
            code = str(row[code_col]).strip()
            name = str(row[name_col]).strip()
            description = str(row[desc_col]).strip() if desc_col else name

            # Validate code format
            if not code or len(code) != 8 or not code.isdigit():
                skipped += 1
                continue

            family_hint = code[:3]
            catalog_entries.append((code, name, description, family_hint))

        except Exception as e:
            skipped += 1
            continue

    print(f"   ✅ Parsed {len(catalog_entries)} valid codes ({skipped} skipped)")
    return catalog_entries


def import_catalog_to_db(catalog_entries: List[Tuple[str, str, str, str]], batch_size: int = 1000):
    """
    Import catalog entries into PostgreSQL database.

    Args:
        catalog_entries: List of (code, name, description, family_hint) tuples
        batch_size: Number of records to insert per batch (default 1000)
    """
    print(f"\n💾 Importing {len(catalog_entries)} codes to PostgreSQL...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'sat_product_service_catalog'
            );
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            print("\n❌ Error: Table 'sat_product_service_catalog' does not exist")
            print("   Please run migration first:")
            print("   psql $DATABASE_URL < migrations/2025_11_16_create_sat_product_service_catalog.sql")
            return False

        # Check existing records
        cursor.execute("SELECT COUNT(*) FROM sat_product_service_catalog")
        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            print(f"\n⚠️  Found {existing_count} existing records in catalog")
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

            for code, name, description, family_hint in batch:
                try:
                    cursor.execute("""
                        INSERT INTO sat_product_service_catalog
                            (code, name, description, family_hint)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            family_hint = EXCLUDED.family_hint,
                            updated_at = NOW()
                    """, (code, name, description, family_hint))

                    if cursor.rowcount == 1:
                        inserted += 1
                    else:
                        updated += 1

                except Exception as e:
                    print(f"   ⚠️  Error loading code {code}: {e}")
                    continue

            # Commit batch
            conn.commit()

            # Progress report
            progress = min(i + batch_size, len(catalog_entries))
            print(f"   Progress: {progress}/{len(catalog_entries)} codes ({progress/len(catalog_entries)*100:.1f}%)")

        print(f"\n✅ Import complete:")
        print(f"   Inserted: {inserted} new codes")
        print(f"   Updated: {updated} existing codes")

        # Show summary by family
        cursor.execute("""
            SELECT family_hint, COUNT(*) as count
            FROM sat_product_service_catalog
            GROUP BY family_hint
            ORDER BY family_hint
            LIMIT 20
        """)

        print(f"\n📊 Top 20 families by count:")
        for family, count in cursor.fetchall():
            print(f"   {family}: {count} codes")

        # Total count
        cursor.execute("SELECT COUNT(*) FROM sat_product_service_catalog")
        total_count = cursor.fetchone()[0]
        print(f"\n📈 Total codes in database: {total_count}")

        return True

    except Exception as e:
        print(f"\n❌ Error importing catalog: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Import full SAT Product/Service Catalog (~52,000 codes)'
    )
    parser.add_argument(
        '--file',
        type=str,
        help='Path to Excel (.xlsx/.xls) or CSV file with SAT catalog'
    )
    parser.add_argument(
        '--download',
        action='store_true',
        help='Attempt to auto-download catalog from SAT website'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of records to insert per batch (default: 1000)'
    )

    args = parser.parse_args()

    print("=" * 80)
    print("IMPORTING FULL SAT PRODUCT/SERVICE CATALOG")
    print("=" * 80)

    # Determine file path
    file_path = None

    if args.download:
        download_path = "/tmp/sat_catalog_anexo20.xls"
        if download_sat_catalog(download_path):
            file_path = download_path
        else:
            print("\n❌ Auto-download failed. Please use --file option with manual download")
            return 1

    elif args.file:
        file_path = args.file
        if not Path(file_path).exists():
            print(f"❌ Error: File not found: {file_path}")
            return 1

    else:
        print("❌ Error: Must specify --file or --download")
        print("\nUsage:")
        print("  python3 import_full_sat_catalog.py --file path/to/c_ClaveProdServ.xlsx")
        print("  python3 import_full_sat_catalog.py --download")
        print("\nManual download:")
        print("  https://www.sat.gob.mx/consultas/53693/catalogo-de-productos-y-servicios")
        print("  Look for 'Anexo 20' → 'c_ClaveProdServ' tab\n")
        return 1

    # Parse file
    file_ext = Path(file_path).suffix.lower()

    if file_ext in ['.xlsx', '.xls']:
        catalog_entries = parse_excel_catalog(file_path)
    elif file_ext == '.csv':
        catalog_entries = parse_csv_catalog(file_path)
    else:
        print(f"❌ Error: Unsupported file type: {file_ext}")
        print("   Supported: .xlsx, .xls, .csv")
        return 1

    if not catalog_entries:
        print("❌ No valid codes found in file")
        return 1

    # Import to database
    success = import_catalog_to_db(catalog_entries, batch_size=args.batch_size)

    if success:
        print("\n" + "=" * 80)
        print("✅ FULL SAT CATALOG IMPORT COMPLETE")
        print("=" * 80)
        print("\nYour system now has the complete SAT catalog!")
        print("Ready to compete with CONTPAQ and Bind ERP 🚀\n")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
