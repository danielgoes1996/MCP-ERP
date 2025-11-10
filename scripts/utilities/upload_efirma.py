#!/usr/bin/env python3
"""
Upload e.firma Certificates to Database
========================================
Script para subir certificados e.firma del SAT a la base de datos

IMPORTANTE: Necesitas los archivos de e.firma proporcionados por el SAT:
- certificado.cer (archivo público)
- llave_privada.key (archivo privado)
- contraseña de la llave privada

USO:
    python3 upload_efirma.py --company-id 2 --rfc POL210218264 \\
        --cert /path/to/certificado.cer \\
        --key /path/to/llave_privada.key \\
        --password "tu_password_aqui"
"""

import psycopg2
import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

# Configuración de PostgreSQL
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}


def read_file_as_base64(file_path):
    """Lee un archivo y lo convierte a base64"""
    import base64

    with open(file_path, 'rb') as f:
        content = f.read()

    return base64.b64encode(content).decode('utf-8')


def upload_efirma(company_id, rfc, cert_path, key_path, password):
    """
    Sube los certificados e.firma a la base de datos

    Args:
        company_id: ID de la compañía
        rfc: RFC de la compañía
        cert_path: Ruta al archivo .cer
        key_path: Ruta al archivo .key
        password: Contraseña de la llave privada
    """

    # Validar que los archivos existan
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Certificado no encontrado: {cert_path}")

    if not os.path.exists(key_path):
        raise FileNotFoundError(f"Llave privada no encontrada: {key_path}")

    print("📄 Leyendo certificados...")
    print(f"   Certificado: {cert_path}")
    print(f"   Llave: {key_path}")

    # Leer archivos y convertir a base64
    cert_b64 = read_file_as_base64(cert_path)
    key_b64 = read_file_as_base64(key_path)

    print(f"   Certificado: {len(cert_b64)} bytes (base64)")
    print(f"   Llave: {len(key_b64)} bytes (base64)")

    # Conectar a la base de datos
    print("\n🔌 Conectando a PostgreSQL...")
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    try:
        # Verificar si ya existe una credencial para esta compañía
        cursor.execute("""
            SELECT credential_id, is_active
            FROM sat_efirma_credentials
            WHERE company_id = %s AND rfc = %s;
        """, (company_id, rfc))

        existing = cursor.fetchone()

        if existing:
            credential_id, is_active = existing
            print(f"\n⚠️  Ya existe una credencial (ID: {credential_id}, Activa: {is_active})")
            print("   Actualizando credencial existente...")

            # Actualizar credencial existente
            cursor.execute("""
                UPDATE sat_efirma_credentials
                SET
                    certificate_data = %s,
                    private_key_data = %s,
                    key_password = %s,
                    is_active = true,
                    expires_at = %s,
                    updated_at = NOW()
                WHERE credential_id = %s
                RETURNING credential_id;
            """, (
                cert_b64,
                key_b64,
                password,
                datetime.now() + timedelta(days=365*4),  # e.firma válida por 4 años
                credential_id
            ))

            print(f"   ✅ Credencial actualizada: {credential_id}")

        else:
            print("\n✨ Creando nueva credencial...")

            # Insertar nueva credencial
            cursor.execute("""
                INSERT INTO sat_efirma_credentials (
                    company_id,
                    rfc,
                    certificate_data,
                    private_key_data,
                    key_password,
                    is_active,
                    expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING credential_id;
            """, (
                company_id,
                rfc,
                cert_b64,
                key_b64,
                password,
                True,
                datetime.now() + timedelta(days=365*4)
            ))

            credential_id = cursor.fetchone()[0]
            print(f"   ✅ Credencial creada: {credential_id}")

        # Commit
        conn.commit()

        print("\n" + "="*80)
        print("✅ CERTIFICADOS E.FIRMA INSTALADOS CORRECTAMENTE")
        print("="*80)
        print(f"\n📋 Detalles:")
        print(f"   Credential ID: {credential_id}")
        print(f"   Company ID: {company_id}")
        print(f"   RFC: {rfc}")
        print(f"   Estado: Activa ✓")
        print(f"   Expira: {(datetime.now() + timedelta(days=365*4)).strftime('%Y-%m-%d')}")

        print("\n🎯 Siguiente paso:")
        print("   Cambia use_mock=False en api/cfdi_api.py para activar verificación real")
        print("   Comando: python3 scripts/utilities/enable_production_mode.py")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error al subir certificados: {e}")
        raise

    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Sube certificados e.firma del SAT a la base de datos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  # Subir certificados para la compañía 2
  python3 upload_efirma.py --company-id 2 --rfc POL210218264 \\
      --cert ~/Downloads/certificado.cer \\
      --key ~/Downloads/llave_privada.key \\
      --password "mi_password_123"

  # Actualizar certificados existentes
  python3 upload_efirma.py --company-id 2 --rfc POL210218264 \\
      --cert /path/to/new_cert.cer \\
      --key /path/to/new_key.key \\
      --password "nuevo_password"

IMPORTANTE:
  - Los archivos .cer y .key los proporciona el SAT
  - El password es el que usaste al generar la e.firma
  - Los certificados se almacenan encriptados en base64
  - En producción, usa HashiCorp Vault para mayor seguridad
        """
    )

    parser.add_argument(
        '--company-id',
        type=int,
        required=True,
        help='ID de la compañía en la base de datos'
    )

    parser.add_argument(
        '--rfc',
        type=str,
        required=True,
        help='RFC de la compañía (12 o 13 caracteres)'
    )

    parser.add_argument(
        '--cert',
        type=str,
        required=True,
        help='Ruta al archivo certificado.cer del SAT'
    )

    parser.add_argument(
        '--key',
        type=str,
        required=True,
        help='Ruta al archivo llave_privada.key del SAT'
    )

    parser.add_argument(
        '--password',
        type=str,
        required=True,
        help='Contraseña de la llave privada'
    )

    args = parser.parse_args()

    # Validar RFC
    if len(args.rfc) not in [12, 13]:
        parser.error("RFC debe tener 12 o 13 caracteres")

    print("="*80)
    print("🔐 INSTALACIÓN DE CERTIFICADOS E.FIRMA")
    print("="*80)
    print(f"\nCompañía: {args.company_id}")
    print(f"RFC: {args.rfc}")
    print(f"Certificado: {args.cert}")
    print(f"Llave: {args.key}")
    print(f"Password: {'*' * len(args.password)}")

    # Confirmar
    confirm = input("\n¿Deseas continuar? (si/no): ")

    if confirm.lower() not in ['si', 's', 'yes', 'y']:
        print("❌ Operación cancelada")
        return

    # Subir certificados
    upload_efirma(
        company_id=args.company_id,
        rfc=args.rfc,
        cert_path=args.cert,
        key_path=args.key,
        password=args.password
    )


if __name__ == '__main__':
    main()
