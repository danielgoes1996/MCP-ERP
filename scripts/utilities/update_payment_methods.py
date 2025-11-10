#!/usr/bin/env python3
"""
Actualizar Métodos y Formas de Pago
====================================
Este script:
1. Lee todos los XMLs existentes
2. Extrae metodo_pago y forma_pago
3. Actualiza la tabla expenses

Uso:
    python3 update_payment_methods.py --company-id 2
    python3 update_payment_methods.py --company-id 2 --dry-run  # Solo ver qué haría
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import xml.etree.ElementTree as ET
import os
import sys
import argparse
from pathlib import Path

# Configuración
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

# Namespaces CFDI
NAMESPACES = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'cfdi3': 'http://www.sat.gob.mx/cfd/3',
}


def extract_payment_info(xml_path):
    """
    Extrae metodo_pago y forma_pago de un XML
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Obtener directamente del root (atributos del Comprobante)
        metodo_pago = root.get('MetodoPago')
        forma_pago = root.get('FormaPago')

        return metodo_pago, forma_pago

    except Exception as e:
        print(f"    ⚠️  Error parseando XML: {e}")
        return None, None


def find_xml_for_uuid(uuid, search_paths):
    """
    Busca el archivo XML correspondiente a un UUID
    """
    uuid_lower = uuid.lower()
    uuid_upper = uuid.upper()

    for search_path in search_paths:
        for uuid_variant in [uuid_lower, uuid_upper, uuid]:
            xml_path = Path(search_path) / f"{uuid_variant}.xml"
            if xml_path.exists():
                return str(xml_path)

    # Búsqueda recursiva
    for search_path in search_paths:
        for xml_path in Path(search_path).rglob(f"*{uuid_lower}*.xml"):
            return str(xml_path)

    return None


def main():
    parser = argparse.ArgumentParser(
        description='Actualiza metodo_pago y forma_pago en facturas existentes'
    )

    parser.add_argument('--company-id', type=int, default=2, help='ID de la compañía')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar qué se haría')
    parser.add_argument('--limit', type=int, help='Limitar cantidad de facturas')

    args = parser.parse_args()

    print("="*80)
    print("💳 ACTUALIZACIÓN DE MÉTODOS Y FORMAS DE PAGO")
    print("="*80)
    print(f"\nCompañía: {args.company_id}")
    print(f"Modo: {'DRY-RUN (solo simulación)' if args.dry_run else 'ACTUALIZACIÓN REAL'}")
    print()

    # Conectar a BD
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    # Obtener facturas a actualizar
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""

    cursor.execute(f"""
        SELECT id, uuid, raw_xml as xml_content
        FROM expense_invoices
        WHERE company_id = %s
        AND (metodo_pago IS NULL OR forma_pago IS NULL)
        ORDER BY fecha_emision DESC
        {limit_clause};
    """, [args.company_id])

    expenses = cursor.fetchall()

    total = len(expenses)
    print(f"📋 Facturas a actualizar: {total}\n")

    if total == 0:
        print("✅ Todas las facturas ya tienen métodos de pago")
        return

    # Rutas de búsqueda de XMLs
    search_paths = [
        './test_invoices/facturas_reales',
        './uploads/expense_invoices',
        './uploads/company_2',
        './test_invoices'
    ]

    stats = {
        'actualizadas': 0,
        'xml_no_encontrado': 0,
        'sin_datos': 0,
        'errores': 0
    }

    # Distribución de métodos de pago
    metodo_distribution = {}
    forma_distribution = {}

    for i, expense in enumerate(expenses, 1):
        uuid = expense['uuid']
        expense_id = expense['id']

        print(f"[{i}/{total}] UUID: {uuid[:20]}...")

        # Intentar obtener del xml_content si existe
        metodo_pago = None
        forma_pago = None

        if expense.get('xml_content'):
            try:
                root = ET.fromstring(expense['xml_content'])
                metodo_pago = root.get('MetodoPago')
                forma_pago = root.get('FormaPago')
                print(f"    ✓ Datos del XML en BD")
            except:
                pass

        # Si no está en BD, buscar archivo XML
        if not metodo_pago and not forma_pago:
            xml_path = find_xml_for_uuid(uuid, search_paths)

            if xml_path:
                print(f"    ✓ XML encontrado: {Path(xml_path).parent.name}/{Path(xml_path).name}")
                metodo_pago, forma_pago = extract_payment_info(xml_path)
            else:
                print(f"    ⚠️  XML no encontrado")
                stats['xml_no_encontrado'] += 1
                continue

        if metodo_pago or forma_pago:
            print(f"    → MetodoPago: {metodo_pago or 'N/A'}")
            print(f"    → FormaPago: {forma_pago or 'N/A'}")

            # Contar distribución
            if metodo_pago:
                metodo_distribution[metodo_pago] = metodo_distribution.get(metodo_pago, 0) + 1
            if forma_pago:
                forma_distribution[forma_pago] = forma_distribution.get(forma_pago, 0) + 1

            if not args.dry_run:
                try:
                    cursor.execute("""
                        UPDATE expense_invoices
                        SET metodo_pago = %s, forma_pago = %s, updated_at = NOW()
                        WHERE id = %s
                    """, [metodo_pago, forma_pago, expense_id])
                    conn.commit()
                    stats['actualizadas'] += 1
                    print(f"    ✅ Actualizada")
                except Exception as e:
                    print(f"    ❌ Error: {e}")
                    stats['errores'] += 1
            else:
                stats['actualizadas'] += 1
                print(f"    🔸 [DRY-RUN] Se actualizaría")
        else:
            print(f"    ⚠️  Sin datos de pago")
            stats['sin_datos'] += 1

        print()

    # Reporte final
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    print(f"\nTotal facturas: {total}")
    print(f"Actualizadas: {stats['actualizadas']}")
    print(f"XML no encontrado: {stats['xml_no_encontrado']}")
    print(f"Sin datos: {stats['sin_datos']}")
    print(f"Errores: {stats['errores']}")

    if metodo_distribution:
        print("\n📈 DISTRIBUCIÓN POR MÉTODO DE PAGO:")
        for metodo, count in sorted(metodo_distribution.items()):
            pct = (count / stats['actualizadas'] * 100) if stats['actualizadas'] > 0 else 0
            print(f"  {metodo}: {count} ({pct:.1f}%)")

    if forma_distribution:
        print("\n💰 DISTRIBUCIÓN POR FORMA DE PAGO:")
        # Diccionario de formas de pago
        forma_names = {
            '01': 'Efectivo',
            '02': 'Cheque',
            '03': 'Transferencia',
            '04': 'Tarjeta crédito',
            '28': 'Tarjeta débito',
            '99': 'Por definir'
        }
        for forma, count in sorted(forma_distribution.items()):
            pct = (count / stats['actualizadas'] * 100) if stats['actualizadas'] > 0 else 0
            forma_name = forma_names.get(forma, f'Forma {forma}')
            print(f"  {forma} ({forma_name}): {count} ({pct:.1f}%)")

    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN - No se realizaron cambios reales")
        print("Ejecuta sin --dry-run para aplicar los cambios")

    print("\n" + "="*80)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
