#!/usr/bin/env python3
"""
Extracción Automática de Facturas del SAT
==========================================
Este script descarga automáticamente las facturas nuevas desde el SAT
para todas las compañías activas.

Uso:
    python3 extraer_facturas_nuevas.py --ultimos-7-dias
    python3 extraer_facturas_nuevas.py --mes-anterior
    python3 extraer_facturas_nuevas.py --desde 2025-11-01 --hasta 2025-11-08
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import argparse
from datetime import datetime, timedelta
import time
import sys
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

API_BASE_URL = "http://localhost:8000"


def get_active_companies():
    """Obtiene todas las compañías activas con configuración SAT"""
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.id,
            c.name,
            c.rfc,
            ec.is_active as has_credentials
        FROM companies c
        LEFT JOIN sat_efirma_credentials ec ON ec.company_id = c.id
        WHERE c.status = 'active'
        AND ec.is_active = true
        ORDER BY c.id;
    """)

    companies = cursor.fetchall()
    cursor.close()
    conn.close()

    return companies


def download_invoices_from_sat(company_id, rfc, fecha_inicio, fecha_fin, dry_run=False, use_real_credentials=False):
    """
    Descarga facturas desde el SAT para una compañía específica
    """
    mode_label = "REAL" if use_real_credentials else "MOCK"
    print(f"\n📥 Descargando facturas del SAT [{mode_label}]...")
    print(f"   RFC: {rfc}")
    print(f"   Rango: {fecha_inicio} a {fecha_fin}")

    if dry_run:
        print(f"   [DRY-RUN] Se descargarían facturas para company_id={company_id} (modo: {mode_label})")
        return {
            'success': True,
            'nuevas': 0,
            'existentes': 0,
            'errores': 0,
            'mode': mode_label.lower()
        }

    try:
        # Llamar al endpoint de descarga del SAT
        response = requests.post(
            f"{API_BASE_URL}/sat/download-invoices",
            json={
                "company_id": company_id,
                "rfc": rfc,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "tipo": "recibidas",  # Facturas recibidas (gastos)
                "use_real_credentials": use_real_credentials  # Usar credenciales reales
            },
            timeout=300  # 5 minutos timeout
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Descarga completada")
            print(f"      Nuevas: {result.get('nuevas', 0)}")
            print(f"      Existentes: {result.get('existentes', 0)}")
            print(f"      Errores: {result.get('errores', 0)}")
            return result
        else:
            print(f"   ❌ Error HTTP {response.status_code}: {response.text}")
            return {
                'success': False,
                'nuevas': 0,
                'existentes': 0,
                'errores': 1
            }

    except requests.exceptions.Timeout:
        print(f"   ⏱️  Timeout: La descarga tomó más de 5 minutos")
        return {
            'success': False,
            'nuevas': 0,
            'existentes': 0,
            'errores': 1
        }
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {
            'success': False,
            'nuevas': 0,
            'existentes': 0,
            'errores': 1
        }


def main():
    parser = argparse.ArgumentParser(
        description='Extrae facturas nuevas del SAT automáticamente'
    )
    parser.add_argument('--ultimos-7-dias', action='store_true',
                       help='Extraer facturas de los últimos 7 días')
    parser.add_argument('--mes-anterior', action='store_true',
                       help='Extraer facturas del mes anterior completo')
    parser.add_argument('--desde', type=str,
                       help='Fecha inicio (YYYY-MM-DD)')
    parser.add_argument('--hasta', type=str,
                       help='Fecha fin (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Modo prueba: muestra qué haría sin ejecutar')
    parser.add_argument('--yes', '-y', action='store_true',
                       help='Confirmar automáticamente (para cron jobs)')
    parser.add_argument('--notify', action='store_true',
                       help='Enviar notificación por email al finalizar')
    parser.add_argument('--real-credentials', action='store_true',
                       help='Usar credenciales reales del SAT (no mock)')

    args = parser.parse_args()

    print("="*80)
    print("📥 EXTRACCIÓN AUTOMÁTICA DE FACTURAS - SAT")
    print("="*80)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Calcular rango de fechas
    if args.ultimos_7_dias:
        fecha_fin = datetime.now().date()
        fecha_inicio = fecha_fin - timedelta(days=7)
        print(f"📅 Modo: Últimos 7 días")
    elif args.mes_anterior:
        hoy = datetime.now().date()
        primer_dia_mes_actual = hoy.replace(day=1)
        fecha_fin = primer_dia_mes_actual - timedelta(days=1)  # Último día del mes anterior
        fecha_inicio = fecha_fin.replace(day=1)  # Primer día del mes anterior
        print(f"📅 Modo: Mes anterior completo")
    elif args.desde and args.hasta:
        fecha_inicio = datetime.strptime(args.desde, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(args.hasta, '%Y-%m-%d').date()
        print(f"📅 Modo: Rango personalizado")
    else:
        print("❌ Error: Debes especificar un rango de fechas")
        print("   Opciones: --ultimos-7-dias, --mes-anterior, o --desde/--hasta")
        sys.exit(1)

    print(f"   Desde: {fecha_inicio}")
    print(f"   Hasta: {fecha_fin}")
    print()

    # Obtener compañías activas
    print("📋 Obteniendo compañías activas...")
    companies = get_active_companies()

    if not companies:
        print("⚠️  No se encontraron compañías activas con certificados SAT")
        return

    print(f"✅ Encontradas {len(companies)} compañías con acceso al SAT")
    print()

    # Mostrar resumen
    print("="*80)
    print("📊 COMPAÑÍAS A PROCESAR")
    print("="*80)

    for company in companies:
        print(f"\n{company['id']}. {company['name']}")
        print(f"   RFC: {company['rfc']}")
        print(f"   Certificado: {'✅ Configurado' if company['has_credentials'] else '❌ No configurado'}")

    print("\n" + "="*80)
    print()

    if args.dry_run:
        print("🔍 MODO DRY-RUN: No se descargarán facturas\n")

    # Confirmar
    if not args.dry_run and not args.yes:
        confirm = input("¿Deseas continuar con la descarga? (si/no): ")
        if confirm.lower() not in ['si', 's', 'yes', 'y']:
            print("❌ Operación cancelada")
            return
        print()

    # Procesar cada compañía
    execution_date = datetime.now()
    start_time = time.time()
    results = {
        'total_nuevas': 0,
        'total_existentes': 0,
        'total_errores': 0,
        'companies_success': [],
        'companies_failed': []
    }

    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}] Procesando: {company['name']} (ID: {company['id']})")

        company_start = time.time()

        result = download_invoices_from_sat(
            company['id'],
            company['rfc'],
            fecha_inicio.strftime('%Y-%m-%d'),
            fecha_fin.strftime('%Y-%m-%d'),
            dry_run=args.dry_run,
            use_real_credentials=args.real_credentials
        )

        company_time = time.time() - company_start

        if result.get('success', False) or result.get('nuevas', 0) > 0:
            print(f"   ✅ Completado en {company_time:.1f} segundos")
            results['companies_success'].append({
                'id': company['id'],
                'name': company['name'],
                'nuevas': result.get('nuevas', 0),
                'time': company_time
            })
            results['total_nuevas'] += result.get('nuevas', 0)
            results['total_existentes'] += result.get('existentes', 0)
        else:
            print(f"   ❌ Error en descarga")
            results['companies_failed'].append({
                'id': company['id'],
                'name': company['name']
            })
            results['total_errores'] += 1

        # Pequeña pausa entre compañías
        if i < len(companies):
            time.sleep(2)

    total_time = time.time() - start_time
    results['total_time'] = total_time

    # Reporte Final
    print("\n" + "="*80)
    print("✅ EXTRACCIÓN COMPLETADA")
    print("="*80)
    print(f"\n📊 RESULTADOS:")
    print(f"   Compañías procesadas: {len(results['companies_success'])}/{len(companies)}")
    print(f"   Facturas nuevas: {results['total_nuevas']}")
    print(f"   Facturas existentes: {results['total_existentes']}")
    print(f"   Errores: {results['total_errores']}")
    print(f"   Tiempo total: {total_time/60:.1f} minutos")

    if results['companies_success']:
        print(f"\n✅ Exitosas ({len(results['companies_success'])}):")
        for r in results['companies_success']:
            print(f"   - {r['name']}: {r['nuevas']} nuevas en {r['time']:.1f}s")

    if results['companies_failed']:
        print(f"\n❌ Fallidas ({len(results['companies_failed'])}):")
        for r in results['companies_failed']:
            print(f"   - {r['name']} (ID: {r['id']})")

    print("\n" + "="*80)
    print(f"🎯 Próxima extracción recomendada: {(datetime.now() + timedelta(days=7)).strftime('%d de %B, %Y')}")
    print("="*80)
    print()

    # Enviar notificación si se solicitó
    if args.notify and not args.dry_run:
        recipients = get_notification_recipients()

        if not recipients:
            print("⚠️  No se encontraron destinatarios configurados (NOTIFICATION_EMAILS)")
            print("   Configurar variable de entorno NOTIFICATION_EMAILS para recibir notificaciones")
        else:
            print(f"\n📧 Enviando notificación a {len(recipients)} destinatario(s)...")

            email_service = EmailNotificationService()
            success = email_service.send_extraction_complete(
                to_emails=recipients,
                results=results,
                execution_date=execution_date,
                date_range=(fecha_inicio, fecha_fin)
            )

            if success:
                print("   ✅ Notificación enviada exitosamente")
            else:
                print("   ❌ Error al enviar notificación (verificar configuración SMTP)")


if __name__ == '__main__':
    main()
