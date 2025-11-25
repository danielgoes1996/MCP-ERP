#!/usr/bin/env python3
"""
Load SAT Product/Service Catalog into PostgreSQL

This script loads the official SAT c_ClaveProdServ catalog into the database.
For now, it loads a curated subset of common codes used in the system.

TODO: Replace with full catalog loader from official SAT Excel file when available.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import psycopg2
from config.config import config


# Curated subset of common SAT codes used in the system
# TODO: Replace with full catalog (~55,000 codes) from official SAT Excel
COMMON_SAT_CODES = [
    # Combustibles y lubricantes (151)
    ("15101514", "Gasolina Magna", "Gasolina de octanaje regular para vehículos automotores", "151"),
    ("15101515", "Gasolina Premium", "Gasolina de octanaje alto para vehículos automotores", "151"),
    ("15101516", "Diesel", "Combustible diesel para vehículos y maquinaria", "151"),
    ("15101517", "Gas LP", "Gas licuado de petróleo para uso automotor", "151"),

    # Alimentos y bebidas (50)
    ("50192403", "Miel natural", "Miel de abeja natural sin procesar", "501"),
    ("50202300", "Alimentos preparados", "Comidas y alimentos listos para consumo", "502"),
    ("50202301", "Alimentos enlatados", "Productos alimenticios envasados en latas", "502"),

    # Equipo de cómputo y tecnología (43)
    ("43211500", "Computadoras personales", "Equipos de cómputo tipo PC", "432"),
    ("43211503", "Computadoras portátiles", "Laptops y notebooks", "432"),
    ("43211507", "Tabletas electrónicas", "Dispositivos tipo tablet", "432"),
    ("43232600", "Monitores y pantallas", "Displays para computadoras", "432"),

    # Servicios profesionales (80-86)
    ("80101500", "Servicios de consultoría", "Consultoría profesional y asesoría", "801"),
    ("80111500", "Servicios de contabilidad", "Servicios contables y fiscales", "801"),
    ("80141600", "Servicios de facturación", "Procesamiento y emisión de facturas electrónicas", "801"),
    ("80141628", "Comisiones por servicios", "Comisiones por servicios financieros o comerciales", "801"),
    ("81141601", "Servicios de almacenamiento", "Almacenamiento y bodegaje de mercancías", "811"),
    ("81111500", "Servicios de transporte terrestre", "Transporte de carga o pasajeros por carretera", "811"),

    # Materiales y suministros (55)
    ("55121600", "Material de empaque y embalaje", "Etiquetas, cajas, envases para productos", "551"),
    ("55101500", "Material de papelería", "Papel, sobres, carpetas para oficina", "551"),

    # Servicios de mantenimiento y reparación (78)
    ("78181500", "Servicios de reparación de vehículos", "Mantenimiento y reparación automotriz", "781"),
    ("78101800", "Servicios de limpieza", "Servicios de limpieza y aseo", "781"),

    # Servicios de publicidad y marketing (60)
    ("60131600", "Servicios de publicidad", "Publicidad y promoción de productos", "601"),
    ("60141500", "Servicios de diseño gráfico", "Diseño de materiales publicitarios", "601"),

    # Servicios de telecomunicaciones (43)
    ("43232100", "Servicios de internet", "Conectividad y acceso a internet", "432"),
    ("43232000", "Servicios de telefonía", "Servicios telefónicos fijos y móviles", "432"),

    # Software y licencias (43)
    ("43232900", "Software y aplicaciones", "Licencias de software y programas", "432"),
    ("43233000", "Suscripciones digitales", "Suscripciones a plataformas y servicios digitales", "432"),

    # Servicios financieros (80)
    ("80141500", "Servicios bancarios", "Comisiones y servicios de instituciones financieras", "801"),
    ("80141600", "Servicios de procesamiento de pagos", "Procesamiento de transacciones", "801"),

    # Hospedaje y viajes (70)
    ("70101500", "Servicios de hospedaje", "Alojamiento en hoteles y establecimientos", "701"),
    ("70102000", "Servicios de alimentación", "Alimentos y bebidas en establecimientos", "701"),

    # Equipo y mobiliario de oficina (56)
    ("56101500", "Mobiliario de oficina", "Escritorios, sillas, archiveros", "561"),
    ("56102000", "Equipo de oficina", "Impresoras, copiadoras, escáneres", "561"),

    # Seguros (53)
    ("53101600", "Seguros de vida", "Pólizas de seguro de vida", "531"),
    ("53101700", "Seguros de salud", "Seguros médicos y de gastos médicos", "531"),
    ("53101800", "Seguros de automóvil", "Pólizas de seguro para vehículos", "531"),

    # Energía eléctrica y agua (26)
    ("26101500", "Energía eléctrica", "Suministro de electricidad", "261"),
    ("26111500", "Agua potable", "Suministro de agua para consumo", "261"),

    # Construcción y mantenimiento de edificios (72)
    ("72101500", "Servicios de construcción", "Construcción de edificios e instalaciones", "721"),
    ("72102000", "Servicios de mantenimiento de edificios", "Mantenimiento y reparación de inmuebles", "721"),
]


def get_db_connection():
    """Get PostgreSQL connection."""
    password_part = f" password={config.PG_PASSWORD}" if config.PG_PASSWORD else ""
    dsn = f"host={config.PG_HOST} port={config.PG_PORT} dbname={config.PG_DB} user={config.PG_USER}{password_part}"
    return psycopg2.connect(dsn)


def load_sat_catalog():
    """Load SAT product/service catalog into database."""
    print("=" * 80)
    print("LOADING SAT PRODUCT/SERVICE CATALOG")
    print("=" * 80)

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
                print("   Skipping load")
                return True

        # Insert SAT codes
        print(f"\n📥 Loading {len(COMMON_SAT_CODES)} SAT codes...")

        inserted = 0
        for code, name, description, family_hint in COMMON_SAT_CODES:
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
                inserted += 1

                if inserted % 10 == 0:
                    print(f"   Progress: {inserted}/{len(COMMON_SAT_CODES)} codes loaded...")

            except Exception as e:
                print(f"   ⚠️  Error loading code {code}: {e}")
                continue

        conn.commit()

        print(f"\n✅ Successfully loaded {inserted} SAT codes")

        # Show summary by family
        cursor.execute("""
            SELECT family_hint, COUNT(*) as count
            FROM sat_product_service_catalog
            GROUP BY family_hint
            ORDER BY family_hint
        """)

        print("\n📊 Codes by family:")
        for family, count in cursor.fetchall():
            print(f"   {family}: {count} codes")

        # Show some examples
        cursor.execute("""
            SELECT code, name FROM sat_product_service_catalog
            ORDER BY code
            LIMIT 5
        """)

        print("\n📋 Sample codes:")
        for code, name in cursor.fetchall():
            print(f"   {code} - {name}")

        print("\n" + "=" * 80)
        print("✅ SAT CATALOG LOAD COMPLETE")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ Error loading SAT catalog: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    success = load_sat_catalog()
    sys.exit(0 if success else 1)
