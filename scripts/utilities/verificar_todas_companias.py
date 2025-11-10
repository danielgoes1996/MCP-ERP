#!/usr/bin/env python3
"""
Verificación Automática de CFDIs - Todas las Compañías
======================================================
Este script verifica automáticamente los CFDIs de TODAS las compañías
en el sistema.

Uso:
    python3 verificar_todas_companias.py --verify-sat
    python3 verificar_todas_companias.py --dry-run  # Solo muestra qué haría
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import subprocess
import sys
import argparse
from datetime import datetime
import time
import os

# Agregar el directorio raíz al path para importar core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.notifications.email_service import EmailNotificationService, get_notification_recipients

# Configuración
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}


def get_active_companies():
    """Obtiene todas las compañías activas con CFDIs"""
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.id,
            c.name,
            c.rfc,
            COUNT(ei.id) as total_cfdis,
            COUNT(CASE WHEN ei.sat_status IS NULL THEN 1 END) as sin_verificar,
            COUNT(CASE WHEN ei.sat_status = 'vigente' THEN 1 END) as vigentes,
            COUNT(CASE WHEN ei.sat_status = 'cancelado' THEN 1 END) as cancelados,
            MAX(ei.sat_fecha_verificacion) as ultima_verificacion
        FROM companies c
        LEFT JOIN expense_invoices ei ON ei.company_id = c.id
        WHERE c.status = 'active'
        GROUP BY c.id, c.name, c.rfc
        HAVING COUNT(ei.id) > 0
        ORDER BY c.id;
    """)

    companies = cursor.fetchall()
    cursor.close()
    conn.close()

    return companies


def verify_company(company_id, verify_sat=False, dry_run=False):
    """Verifica los CFDIs de una compañía específica"""

    if dry_run:
        print(f"   [DRY-RUN] Se ejecutaría verificación para company_id={company_id}")
        return True

    # Construir comando
    cmd = [
        'python3',
        'scripts/utilities/reprocesar_cfdis_completo.py',
        '--company-id', str(company_id)
    ]

    if verify_sat:
        cmd.append('--verify-sat')

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos timeout
        )

        if result.returncode == 0:
            return True
        else:
            print(f"   ❌ Error: {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"   ⏱️  Timeout: La verificación tomó más de 10 minutos")
        return False
    except Exception as e:
        print(f"   ❌ Error ejecutando script: {e}")
        return False


def send_notification(results, stats, execution_date):
    """Envía notificación por email con el resumen completo"""
    recipients = get_notification_recipients()

    if not recipients:
        print("\n⚠️  No se encontraron destinatarios configurados (NOTIFICATION_EMAILS)")
        print("   Configurar variable de entorno NOTIFICATION_EMAILS para recibir notificaciones")
        return False

    print(f"\n📧 Enviando notificación a {len(recipients)} destinatario(s)...")

    # Preparar datos para la notificación
    notification_data = {
        'companies_success': results['success'],
        'companies_failed': results['failed'],
        'total_verificados': stats.get('total_cfdis', 0),
        'total_vigentes': stats.get('vigentes', 0),
        'total_cancelados': stats.get('cancelados', 0),
        'total_errores': len(results['failed']),
        'total_time': results['total_time']
    }

    # Enviar email
    email_service = EmailNotificationService()
    success = email_service.send_verification_complete(
        to_emails=recipients,
        results=notification_data,
        execution_date=execution_date
    )

    if success:
        print("   ✅ Notificación enviada exitosamente")
    else:
        print("   ❌ Error al enviar notificación (verificar configuración SMTP)")

    return success


def main():
    parser = argparse.ArgumentParser(
        description='Verifica CFDIs de todas las compañías automáticamente'
    )
    parser.add_argument('--verify-sat', action='store_true',
                       help='Verificar con SAT (si no, solo actualiza datos)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Modo prueba: muestra qué haría sin ejecutar')
    parser.add_argument('--notify', action='store_true',
                       help='Enviar notificación al finalizar')
    parser.add_argument('--yes', '-y', action='store_true',
                       help='Confirmar automáticamente (para cron jobs)')

    args = parser.parse_args()

    print("="*80)
    print("🔄 VERIFICACIÓN AUTOMÁTICA - TODAS LAS COMPAÑÍAS")
    print("="*80)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Verificar SAT: {'Sí' if args.verify_sat else 'No'}")
    print(f"Modo: {'DRY-RUN' if args.dry_run else 'PRODUCCIÓN'}")
    print()

    # Obtener compañías activas
    print("📋 Obteniendo compañías activas...")
    companies = get_active_companies()

    if not companies:
        print("⚠️  No se encontraron compañías activas con CFDIs")
        return

    print(f"✅ Encontradas {len(companies)} compañías con CFDIs\n")

    # Mostrar resumen
    print("="*80)
    print("📊 RESUMEN DE COMPAÑÍAS")
    print("="*80)

    total_cfdis = 0
    total_sin_verificar = 0

    for company in companies:
        total_cfdis += company['total_cfdis']
        total_sin_verificar += company['sin_verificar']

        print(f"\n{company['id']}. {company['name']}")
        print(f"   RFC: {company['rfc']}")
        print(f"   CFDIs: {company['total_cfdis']}")
        print(f"   Sin verificar: {company['sin_verificar']}")
        print(f"   Vigentes: {company['vigentes']}")
        print(f"   Cancelados: {company['cancelados']}")
        if company['ultima_verificacion']:
            print(f"   Última verificación: {company['ultima_verificacion']}")

    print(f"\n{'='*80}")
    print(f"TOTAL: {len(companies)} compañías | {total_cfdis} CFDIs | {total_sin_verificar} sin verificar")
    print("="*80)
    print()

    if args.dry_run:
        print("🔍 MODO DRY-RUN: No se ejecutarán cambios\n")

    # Confirmar
    if not args.dry_run and not args.yes:
        confirm = input("¿Deseas continuar con la verificación? (si/no): ")
        if confirm.lower() not in ['si', 's', 'yes', 'y']:
            print("❌ Operación cancelada")
            return
        print()

    # Procesar cada compañía
    execution_date = datetime.now()
    start_time = time.time()
    results = {
        'success': [],
        'failed': [],
        'total_time': 0
    }

    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}] Procesando: {company['name']} (ID: {company['id']})")
        print(f"   CFDIs a procesar: {company['total_cfdis']}")

        company_start = time.time()

        success = verify_company(
            company['id'],
            verify_sat=args.verify_sat,
            dry_run=args.dry_run
        )

        company_time = time.time() - company_start

        if success:
            print(f"   ✅ Completado en {company_time:.1f} segundos")
            results['success'].append({
                'id': company['id'],
                'name': company['name'],
                'verificados': company['total_cfdis'],
                'time': company_time
            })
        else:
            print(f"   ❌ Error en verificación")
            results['failed'].append({
                'id': company['id'],
                'name': company['name']
            })

        # Pequeña pausa entre compañías para no saturar
        if i < len(companies):
            time.sleep(1)

    total_time = time.time() - start_time
    results['total_time'] = total_time

    # Reporte Final
    print("\n" + "="*80)
    print("✅ VERIFICACIÓN COMPLETADA")
    print("="*80)
    print(f"\n📊 RESULTADOS:")
    print(f"   Compañías procesadas: {len(results['success'])}/{len(companies)}")
    print(f"   Compañías con errores: {len(results['failed'])}")
    print(f"   Tiempo total: {total_time/60:.1f} minutos")

    if results['success']:
        print(f"\n✅ Exitosas ({len(results['success'])}):")
        for r in results['success']:
            print(f"   - {r['name']}: {r['verificados']} CFDIs en {r['time']:.1f}s")

    if results['failed']:
        print(f"\n❌ Fallidas ({len(results['failed'])}):")
        for r in results['failed']:
            print(f"   - {r['name']} (ID: {r['id']})")

    # Estadísticas finales de BD
    stats = {}
    if not args.dry_run:
        print("\n" + "="*80)
        print("📈 ESTADÍSTICAS FINALES")
        print("="*80)

        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(DISTINCT company_id) as total_companies,
                COUNT(*) as total_cfdis,
                COUNT(CASE WHEN sat_status = 'vigente' THEN 1 END) as vigentes,
                COUNT(CASE WHEN sat_status = 'cancelado' THEN 1 END) as cancelados,
                COUNT(CASE WHEN sat_status IS NULL THEN 1 END) as sin_verificar
            FROM expense_invoices
            WHERE company_id IN (
                SELECT id FROM companies WHERE status = 'active'
            );
        """)

        stats = cursor.fetchone()

        print(f"\n   Compañías: {stats['total_companies']}")
        print(f"   CFDIs Totales: {stats['total_cfdis']}")
        print(f"   ├── Vigentes: {stats['vigentes']} ({stats['vigentes']/stats['total_cfdis']*100:.1f}%)")
        print(f"   ├── Cancelados: {stats['cancelados']}")
        print(f"   └── Sin verificar: {stats['sin_verificar']}")

        cursor.close()
        conn.close()

    print("\n" + "="*80)
    print(f"🎯 Próxima ejecución recomendada: {datetime.now().replace(day=1, month=datetime.now().month+1 if datetime.now().month < 12 else 1).strftime('%d de %B, %Y')}")
    print("="*80)
    print()

    # Enviar notificación si se solicitó
    if args.notify and not args.dry_run:
        send_notification(results, stats, execution_date)


if __name__ == '__main__':
    main()
