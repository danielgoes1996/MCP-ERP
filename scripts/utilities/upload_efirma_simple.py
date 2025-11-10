#!/usr/bin/env python3
"""
Upload e.firma Certificates - Simple Version
===========================================
Script simplificado para guardar rutas de certificados e.firma

NOTA: La tabla actual usa Vault paths. Este script guarda
las rutas de los archivos locales como workaround temporal.
"""

import psycopg2
import sys
from datetime import datetime, timedelta

# Configuración de PostgreSQL
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

def upload_efirma_simple(company_id, rfc, cert_path, key_path, password):
    """
    Guarda las rutas de certificados e.firma en la base de datos

    NOTA: Este es un workaround temporal. En producción se debe usar HashiCorp Vault.
    """

    print("🔌 Conectando a PostgreSQL...")
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    try:
        # Verificar si ya existe
        cursor.execute("""
            SELECT id, is_active
            FROM sat_efirma_credentials
            WHERE company_id = %s AND rfc = %s;
        """, (company_id, rfc))

        existing = cursor.fetchone()

        # Calcular fecha de expiración (4 años desde hoy)
        expires_at = datetime.now() + timedelta(days=365*4)

        if existing:
            cred_id, is_active = existing
            print(f"\n⚠️  Ya existe una credencial (ID: {cred_id}, Activa: {is_active})")
            print("   Actualizando credencial existente...")

            cursor.execute("""
                UPDATE sat_efirma_credentials
                SET
                    vault_cer_path = %s,
                    vault_key_path = %s,
                    vault_password_path = %s,
                    certificate_valid_until = %s,
                    is_active = true,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
            """, (
                f"file://{cert_path}",  # Guardar como file:// path
                f"file://{key_path}",
                f"inline:{password}",   # Password inline (temporal)
                expires_at,
                cred_id
            ))

            print(f"   ✅ Credencial actualizada: {cred_id}")

        else:
            print("\n✨ Creando nueva credencial...")

            cursor.execute("""
                INSERT INTO sat_efirma_credentials (
                    company_id,
                    rfc,
                    vault_cer_path,
                    vault_key_path,
                    vault_password_path,
                    certificate_valid_until,
                    is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                company_id,
                rfc,
                f"file://{cert_path}",
                f"file://{key_path}",
                f"inline:{password}",
                expires_at,
                True
            ))

            cred_id = cursor.fetchone()[0]
            print(f"   ✅ Credencial creada: {cred_id}")

        conn.commit()

        print("\n" + "="*80)
        print("✅ CERTIFICADOS E.FIRMA REGISTRADOS CORRECTAMENTE")
        print("="*80)
        print(f"\n📋 Detalles:")
        print(f"   Credential ID: {cred_id}")
        print(f"   Company ID: {company_id}")
        print(f"   RFC: {rfc}")
        print(f"   Certificado: {cert_path}")
        print(f"   Llave: {key_path}")
        print(f"   Estado: Activa ✓")
        print(f"   Expira: {expires_at.strftime('%Y-%m-%d')}")

        print("\n⚠️  NOTA:")
        print("   Los certificados se guardan como rutas de archivo locales.")
        print("   En producción, configura HashiCorp Vault para mayor seguridad.")

        print("\n🎯 Siguiente paso:")
        print("   Ejecuta: python3 scripts/utilities/enable_production_mode.py")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        return False

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) != 6:
        print("Uso: python3 upload_efirma_simple.py <company_id> <rfc> <cert_path> <key_path> <password>")
        sys.exit(1)

    company_id = int(sys.argv[1])
    rfc = sys.argv[2]
    cert_path = sys.argv[3]
    key_path = sys.argv[4]
    password = sys.argv[5]

    print("="*80)
    print("🔐 REGISTRO DE CERTIFICADOS E.FIRMA")
    print("="*80)
    print(f"\nCompañía: {company_id}")
    print(f"RFC: {rfc}")
    print(f"Certificado: {cert_path}")
    print(f"Llave: {key_path}")
    print(f"Password: {'*' * len(password)}")

    success = upload_efirma_simple(company_id, rfc, cert_path, key_path, password)

    sys.exit(0 if success else 1)
