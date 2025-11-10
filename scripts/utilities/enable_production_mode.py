#!/usr/bin/env python3
"""
Enable Production Mode - SAT Verification
==========================================
Script para activar el modo de producción (use_mock=False)

Este script:
1. Verifica que existan credenciales e.firma activas
2. Cambia use_mock=True a use_mock=False en los archivos necesarios
3. Reinicia el servidor API

IMPORTANTE: Solo ejecutar después de subir certificados e.firma
"""

import psycopg2
import re
from pathlib import Path

# Configuración de PostgreSQL
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

# Archivos a modificar
FILES_TO_UPDATE = [
    "api/cfdi_api.py",
    "api/sat_descarga_api.py"
]


def check_credentials():
    """Verifica que existan credenciales e.firma activas"""
    print("🔍 Verificando credenciales e.firma...")

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            company_id,
            rfc,
            is_active,
            certificate_valid_until
        FROM sat_efirma_credentials
        WHERE is_active = true
          AND (certificate_valid_until IS NULL OR certificate_valid_until > NOW());
    """)

    credentials = cursor.fetchall()
    cursor.close()
    conn.close()

    if not credentials:
        print("\n❌ ERROR: No hay credenciales e.firma activas en la base de datos")
        print("\n📋 Pasos para activar:")
        print("   1. Obtén tus certificados e.firma del SAT")
        print("   2. Ejecuta: python3 scripts/utilities/upload_efirma.py --help")
        print("   3. Vuelve a ejecutar este script")
        return False

    print(f"   ✅ Encontradas {len(credentials)} credenciales activas:")
    for cred in credentials:
        cred_id, company_id, rfc, is_active, expires_at = cred
        expire_str = expires_at.strftime('%Y-%m-%d') if expires_at else 'N/A'
        print(f"      - ID {cred_id}: Company {company_id}, RFC {rfc}, Expira: {expire_str}")

    return True


def update_file(file_path, dry_run=False):
    """
    Actualiza un archivo cambiando use_mock=True a use_mock=False

    Args:
        file_path: Ruta del archivo a actualizar
        dry_run: Si True, solo muestra los cambios sin aplicarlos
    """
    if not Path(file_path).exists():
        print(f"   ⚠️  Archivo no encontrado: {file_path}")
        return False

    with open(file_path, 'r') as f:
        content = f.read()

    # Buscar patrones use_mock=True
    pattern = r'use_mock\s*=\s*True'
    matches = list(re.finditer(pattern, content))

    if not matches:
        print(f"   ℹ️  {file_path}: Ya está en modo producción (use_mock=False)")
        return True

    print(f"\n   📝 {file_path}:")
    print(f"      Encontrados {len(matches)} cambios necesarios")

    if dry_run:
        print("      [DRY RUN] No se aplicarán cambios")
        return True

    # Reemplazar use_mock=True por use_mock=False
    new_content = re.sub(pattern, 'use_mock=False', content)

    # Guardar archivo
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"      ✅ Archivo actualizado")
    return True


def main():
    print("="*80)
    print("🚀 ACTIVAR MODO PRODUCCIÓN - VERIFICACIÓN SAT REAL")
    print("="*80)
    print("\nEste script activará la verificación real con el SAT")
    print("cambiando use_mock=True a use_mock=False en los archivos de API.\n")

    # Paso 1: Verificar credenciales
    if not check_credentials():
        return

    print("\n" + "="*80)
    print("📝 ARCHIVOS A ACTUALIZAR")
    print("="*80)

    # Dry run primero
    print("\nPrevisualizando cambios...\n")
    for file_path in FILES_TO_UPDATE:
        update_file(file_path, dry_run=True)

    # Confirmar
    print("\n" + "="*80)
    confirm = input("\n¿Deseas aplicar estos cambios? (si/no): ")

    if confirm.lower() not in ['si', 's', 'yes', 'y']:
        print("❌ Operación cancelada")
        return

    # Aplicar cambios
    print("\n📝 Aplicando cambios...\n")
    for file_path in FILES_TO_UPDATE:
        update_file(file_path, dry_run=False)

    # Resumen
    print("\n" + "="*80)
    print("✅ MODO PRODUCCIÓN ACTIVADO")
    print("="*80)
    print("\n🎯 Siguiente paso:")
    print("   Reinicia el servidor API:")
    print("   $ pkill -f uvicorn")
    print("   $ python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print("\n⚠️  IMPORTANTE:")
    print("   - Las verificaciones ahora usarán el servicio real del SAT")
    print("   - Puede haber latencia de red (1-3 segundos por CFDI)")
    print("   - El SAT puede tener límites de tasa (rate limits)")
    print("   - Monitorea los logs para detectar errores")
    print("\n📊 Prueba el sistema:")
    print("   $ curl -X POST http://localhost:8000/cfdi/{uuid}/verificar")


if __name__ == '__main__':
    main()
