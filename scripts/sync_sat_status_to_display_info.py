#!/usr/bin/env python3
"""
Sync SAT Status from sat_validation_status to display_info.sat_status

This script fixes the desynchronization between:
- sat_validation_status (database column)
- display_info->>'sat_status' (JSON field)

The frontend reads display_info.sat_status, so both must be in sync.
"""

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
import sys

POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
    'port': int(os.getenv('POSTGRES_PORT', '5433')),
    'database': os.getenv('POSTGRES_DB', 'mcp_system'),
    'user': os.getenv('POSTGRES_USER', 'mcp_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'changeme')
}

def main():
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    print("\n" + "="*80)
    print("Sincronización: sat_validation_status → display_info.sat_status")
    print("="*80 + "\n")

    # 1. Encontrar sesiones desincronizadas
    cursor.execute("""
        SELECT
            id,
            sat_validation_status,
            display_info->>'sat_status' as display_sat_status,
            display_info
        FROM sat_invoices
        WHERE sat_validation_status IS NOT NULL
          AND sat_validation_status != 'pending'
          AND (display_info->>'sat_status' IS NULL
               OR display_info->>'sat_status' != sat_validation_status)
        ORDER BY created_at DESC
    """)

    sessions = cursor.fetchall()

    print(f"📋 Sesiones desincronizadas encontradas: {len(sessions)}\n")

    if len(sessions) == 0:
        print("✅ Todos los estados SAT están sincronizados\n")
        cursor.close()
        conn.close()
        return

    # Mostrar muestra
    print("Muestra de cambios a aplicar:")
    print("-" * 80)
    for i, session in enumerate(sessions[:5], 1):
        current = session['display_sat_status'] or 'NULL'
        new = session['sat_validation_status']
        print(f"  {i}. {session['id']}")
        print(f"     Actual (display_info): {current}")
        print(f"     Nuevo (sat_validation): {new}")
        print()

    if len(sessions) > 5:
        print(f"  ... y {len(sessions) - 5} más\n")

    # Confirmar
    response = input(f"¿Actualizar {len(sessions)} sesiones? (yes/no): ")
    if response.lower() != 'yes':
        print("\n❌ Cancelado por el usuario\n")
        cursor.close()
        conn.close()
        return

    # 2. Actualizar todas las sesiones
    print("\n🔄 Actualizando...")
    updated_count = 0

    for session in sessions:
        session_id = session['id']
        sat_status = session['sat_validation_status']
        display_info = dict(session['display_info']) if session['display_info'] else {}

        # Actualizar sat_status en display_info
        display_info['sat_status'] = sat_status

        cursor.execute("""
            UPDATE sat_invoices
            SET display_info = %s,
                updated_at = now()
            WHERE id = %s
        """, (Json(display_info), session_id))

        updated_count += 1

        if updated_count % 10 == 0:
            print(f"  Progreso: {updated_count}/{len(sessions)}")

    conn.commit()

    print(f"\n✅ Sincronización completada")
    print(f"   Total actualizado: {updated_count} sesiones")
    print(f"\n" + "="*80 + "\n")

    # 3. Verificar resultados
    cursor.execute("""
        SELECT
            sat_validation_status,
            COUNT(*) as count
        FROM sat_invoices
        WHERE display_info IS NOT NULL
          AND sat_validation_status IS NOT NULL
        GROUP BY sat_validation_status
        ORDER BY count DESC
    """)

    results = cursor.fetchall()
    print("📊 Estado después de la sincronización:")
    print("-" * 80)
    for row in results:
        status = row['sat_validation_status']
        count = row['count']
        emoji = "✓" if status == "vigente" else "✗" if status == "cancelado" else "⚠"
        print(f"  {emoji} {status}: {count}")

    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
