#!/usr/bin/env python3
"""
Import SAT Catalog from phpcfdi/resources-sat-catalogs SQL file

This script converts the SQLite INSERT statements from the GitHub repo
to PostgreSQL format and imports ~48,000 SAT product/service codes.

Source: https://github.com/phpcfdi/resources-sat-catalogs
File format: INSERT INTO ccp_20_productos_servicios VALUES('code','name','keywords','active','date','');

Our table: sat_product_service_catalog (code, name, description, family_hint)

Usage:
    python3 import_sat_catalog_from_sql.py --file /path/to/ccp_20_productos_servicios.sql
"""

import sys
import os
import argparse
import re
from pathlib import Path
from typing import List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import psycopg2
from config.config import config


def get_db_connection():
    """Get PostgreSQL connection."""
    password_part = f" password={config.PG_PASSWORD}" if config.PG_PASSWORD else ""
    dsn = f"host={config.PG_HOST} port={config.PG_PORT} dbname={config.PG_DB} user={config.PG_USER}{password_part}"
    return psycopg2.connect(dsn)


def parse_sql_file(file_path: str) -> List[Tuple[str, str, str, str]]:
    """
    Parse SQLite INSERT statements from phpcfdi SQL file.

    Expected format:
    INSERT INTO ccp_20_productos_servicios VALUES('01010101','No existe en el catálogo','Fondos y Valores','0,1','2022-01-01','');

    Columns:
    - Column 1: code (8 digits)
    - Column 2: name (official SAT name)
    - Column 3: keywords (comma-separated synonyms) - use as description
    - Column 4: active flag (0 or 1)
    - Column 5: start date
    - Column 6: end date (usually empty)

    Returns:
        List of tuples: (code, name, description, family_hint)
    """
    print(f"\n📖 Parsing SQL file: {file_path}")

    catalog_entries = []
    skipped = 0
    pattern = re.compile(r"INSERT INTO ccp_20_productos_servicios VALUES\((.*?)\);")

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            # Skip PRAGMA, BEGIN, COMMIT, etc.
            if not line.startswith('INSERT'):
                continue

            try:
                match = pattern.search(line)
                if not match:
                    skipped += 1
                    continue

                # Extract values string
                values_str = match.group(1)

                # Parse quoted values (handles commas inside quotes)
                values = []
                current_value = ""
                in_quotes = False

                for char in values_str:
                    if char == "'" and (not current_value or current_value[-1] != '\\'):
                        if in_quotes:
                            # End of quoted value
                            values.append(current_value)
                            current_value = ""
                            in_quotes = False
                        else:
                            # Start of quoted value
                            in_quotes = True
                    elif char == ',' and not in_quotes:
                        # Skip commas outside quotes (field separators)
                        continue
                    elif in_quotes:
                        current_value += char

                # Map to our table structure
                if len(values) < 3:
                    skipped += 1
                    continue

                code = values[0].strip()
                name = values[1].strip()
                keywords = values[2].strip() if len(values) > 2 else ""

                # Validate code format (should be 8 digits)
                if not code or len(code) != 8 or not code.isdigit():
                    skipped += 1
                    continue

                # Extract family hint (first 3 digits)
                family_hint = code[:3]

                # Use keywords as description if available, otherwise use name
                description = keywords if keywords else name

                catalog_entries.append((code, name, description, family_hint))

            except Exception as e:
                print(f"   ⚠️  Error parsing line {line_num}: {e}")
                skipped += 1
                continue

    print(f"   ✅ Parsed {len(catalog_entries)} valid codes ({skipped} skipped)")
    return catalog_entries


def import_catalog_to_db(catalog_entries: List[Tuple[str, str, str, str]], batch_size: int = 1000, auto_yes: bool = False):
    """
    Import catalog entries into PostgreSQL database.

    Args:
        catalog_entries: List of (code, name, description, family_hint) tuples
        batch_size: Number of records to insert per batch (default 1000)
        auto_yes: Automatically clear existing data without prompting
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
        print(f"\n📈 Total codes in database: {total_count:,}")

        # Show some examples
        cursor.execute("""
            SELECT code, name
            FROM sat_product_service_catalog
            ORDER BY code
            LIMIT 10
        """)
        print(f"\n📋 Sample codes:")
        for code, name in cursor.fetchall():
            print(f"   {code}: {name}")

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
        description='Import SAT catalog from phpcfdi/resources-sat-catalogs SQL file'
    )
    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Path to ccp_20_productos_servicios.sql file'
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

    args = parser.parse_args()

    print("=" * 80)
    print("IMPORTING FULL SAT CATALOG FROM PHPCFDI SQL")
    print("=" * 80)

    # Validate file exists
    if not Path(args.file).exists():
        print(f"❌ Error: File not found: {args.file}")
        return 1

    # Parse SQL file
    catalog_entries = parse_sql_file(args.file)

    if not catalog_entries:
        print("❌ No valid codes found in file")
        return 1

    # Import to database
    success = import_catalog_to_db(catalog_entries, batch_size=args.batch_size, auto_yes=args.yes)

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
