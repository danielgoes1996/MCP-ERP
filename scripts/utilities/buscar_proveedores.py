#!/usr/bin/env python3
"""
Búsqueda de Proveedores y sus Facturas
=======================================
Script para buscar proveedores por diferentes criterios
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import argparse

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}


def buscar_por_nombre(nombre_pattern, company_id=None):
    """Busca proveedores por nombre o parte del nombre"""

    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    where_clause = "WHERE LOWER(nombre_emisor) LIKE LOWER(%s)"
    params = [f"%{nombre_pattern}%"]

    if company_id:
        where_clause += " AND company_id = %s"
        params.append(company_id)

    query = f"""
        SELECT
            rfc_emisor,
            nombre_emisor,
            COUNT(*) as total_facturas,
            SUM(total) as monto_total,
            MIN(fecha_emision) as primera_factura,
            MAX(fecha_emision) as ultima_factura,
            COUNT(CASE WHEN sat_status = 'vigente' THEN 1 END) as vigentes,
            COUNT(CASE WHEN sat_status = 'cancelado' THEN 1 END) as canceladas
        FROM expense_invoices
        {where_clause}
        GROUP BY rfc_emisor, nombre_emisor
        ORDER BY monto_total DESC;
    """

    cursor.execute(query, params)
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return results


def buscar_por_rfc(rfc):
    """Busca un proveedor específico por RFC"""

    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    # Información del proveedor
    cursor.execute("""
        SELECT
            rfc_emisor,
            nombre_emisor,
            COUNT(*) as total_facturas,
            SUM(total) as monto_total,
            MIN(fecha_emision) as primera_factura,
            MAX(fecha_emision) as ultima_factura
        FROM expense_invoices
        WHERE rfc_emisor = %s
        GROUP BY rfc_emisor, nombre_emisor;
    """, (rfc.upper(),))

    proveedor = cursor.fetchone()

    if not proveedor:
        cursor.close()
        conn.close()
        return None, []

    # Facturas del proveedor
    cursor.execute("""
        SELECT
            uuid,
            filename,
            fecha_emision,
            total,
            sat_status,
            sat_fecha_verificacion,
            tipo_comprobante
        FROM expense_invoices
        WHERE rfc_emisor = %s
        ORDER BY fecha_emision DESC;
    """, (rfc.upper(),))

    facturas = cursor.fetchall()

    cursor.close()
    conn.close()

    return proveedor, facturas


def listar_top_proveedores(limit=10, company_id=None):
    """Lista los proveedores con mayor monto facturado"""

    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    where_clause = ""
    params = [limit]

    if company_id:
        where_clause = "WHERE company_id = %s"
        params = [company_id, limit]

    query = f"""
        SELECT
            rfc_emisor,
            nombre_emisor,
            COUNT(*) as total_facturas,
            SUM(total) as monto_total,
            AVG(total) as monto_promedio,
            COUNT(CASE WHEN sat_status = 'vigente' THEN 1 END) as vigentes,
            COUNT(CASE WHEN sat_status = 'cancelado' THEN 1 END) as canceladas,
            COUNT(CASE WHEN sat_status IS NULL THEN 1 END) as sin_verificar
        FROM expense_invoices
        {where_clause}
        GROUP BY rfc_emisor, nombre_emisor
        HAVING SUM(total) > 0
        ORDER BY monto_total DESC
        LIMIT {"$2" if company_id else "$1"};
    """

    cursor.execute(query, params)
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return results


def buscar_facturas_por_monto(monto_min, monto_max=None, company_id=None):
    """Busca facturas en un rango de montos"""

    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    where_clauses = ["total >= %s"]
    params = [monto_min]

    if monto_max:
        where_clauses.append("total <= %s")
        params.append(monto_max)

    if company_id:
        where_clauses.append("company_id = %s")
        params.append(company_id)

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT
            uuid,
            rfc_emisor,
            nombre_emisor,
            fecha_emision,
            total,
            sat_status,
            filename
        FROM expense_invoices
        WHERE {where_sql}
        ORDER BY total DESC;
    """

    cursor.execute(query, params)
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Busca proveedores y facturas en la base de datos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Buscar proveedores por nombre
  python3 buscar_proveedores.py --nombre "berisa"
  python3 buscar_proveedores.py --nombre "gasolinera"

  # Buscar por RFC específico
  python3 buscar_proveedores.py --rfc "DPR830516JTA"

  # Listar top 10 proveedores
  python3 buscar_proveedores.py --top 10

  # Buscar facturas por monto
  python3 buscar_proveedores.py --monto-min 1000 --monto-max 5000

  # Filtrar por compañía
  python3 buscar_proveedores.py --nombre "distribuidora" --company-id 2
        """
    )

    parser.add_argument('--nombre', help='Buscar por nombre del proveedor')
    parser.add_argument('--rfc', help='Buscar por RFC del proveedor')
    parser.add_argument('--top', type=int, help='Listar top N proveedores por monto')
    parser.add_argument('--monto-min', type=float, help='Monto mínimo de factura')
    parser.add_argument('--monto-max', type=float, help='Monto máximo de factura')
    parser.add_argument('--company-id', type=int, help='Filtrar por compañía')

    args = parser.parse_args()

    if args.nombre:
        print("="*80)
        print(f"🔍 BÚSQUEDA POR NOMBRE: '{args.nombre}'")
        print("="*80)

        results = buscar_por_nombre(args.nombre, args.company_id)

        if not results:
            print("\n❌ No se encontraron proveedores con ese nombre")
            return

        print(f"\n✅ Encontrados {len(results)} proveedores:\n")

        for i, prov in enumerate(results, 1):
            print(f"{i}. {prov['nombre_emisor'] or 'Sin nombre'}")
            print(f"   RFC: {prov['rfc_emisor'] or 'Sin RFC'}")
            print(f"   Facturas: {prov['total_facturas']}")
            print(f"   Monto Total: ${prov['monto_total']:,.2f}")
            print(f"   Vigentes: {prov['vigentes']} | Canceladas: {prov['canceladas']}")
            print(f"   Primera factura: {prov['primera_factura']}")
            print(f"   Última factura: {prov['ultima_factura']}")
            print()

    elif args.rfc:
        print("="*80)
        print(f"🔍 BÚSQUEDA POR RFC: {args.rfc}")
        print("="*80)

        proveedor, facturas = buscar_por_rfc(args.rfc)

        if not proveedor:
            print(f"\n❌ No se encontró el proveedor con RFC: {args.rfc}")
            return

        print(f"\n📋 PROVEEDOR:")
        print(f"   Nombre: {proveedor['nombre_emisor'] or 'Sin nombre'}")
        print(f"   RFC: {proveedor['rfc_emisor']}")
        print(f"   Total facturas: {proveedor['total_facturas']}")
        print(f"   Monto total: ${proveedor['monto_total']:,.2f}")
        print(f"   Período: {proveedor['primera_factura']} a {proveedor['ultima_factura']}")

        print(f"\n📑 FACTURAS ({len(facturas)}):")

        for i, fact in enumerate(facturas[:10], 1):  # Mostrar primeras 10
            print(f"\n{i}. UUID: {fact['uuid']}")
            print(f"   Fecha: {fact['fecha_emision']}")
            print(f"   Monto: ${fact['total']:,.2f}")
            print(f"   Status SAT: {fact['sat_status'] or 'Sin verificar'}")
            print(f"   Archivo: {fact['filename']}")

        if len(facturas) > 10:
            print(f"\n... y {len(facturas) - 10} facturas más")

    elif args.top:
        print("="*80)
        print(f"📊 TOP {args.top} PROVEEDORES POR MONTO")
        print("="*80)

        results = listar_top_proveedores(args.top, args.company_id)

        if not results:
            print("\n❌ No se encontraron proveedores")
            return

        print(f"\n✅ Top {len(results)} proveedores:\n")

        for i, prov in enumerate(results, 1):
            print(f"{i}. {prov['nombre_emisor'] or 'Sin nombre'}")
            print(f"   RFC: {prov['rfc_emisor'] or 'Sin RFC'}")
            print(f"   Facturas: {prov['total_facturas']}")
            print(f"   Monto Total: ${prov['monto_total']:,.2f}")
            print(f"   Monto Promedio: ${prov['monto_promedio']:,.2f}")
            print(f"   Vigentes: {prov['vigentes']} | Canceladas: {prov['canceladas']} | Sin verificar: {prov['sin_verificar']}")
            print()

    elif args.monto_min is not None:
        print("="*80)
        if args.monto_max:
            print(f"💰 BÚSQUEDA POR MONTO: ${args.monto_min:,.2f} - ${args.monto_max:,.2f}")
        else:
            print(f"💰 BÚSQUEDA POR MONTO: >= ${args.monto_min:,.2f}")
        print("="*80)

        results = buscar_facturas_por_monto(args.monto_min, args.monto_max, args.company_id)

        if not results:
            print("\n❌ No se encontraron facturas en ese rango")
            return

        print(f"\n✅ Encontradas {len(results)} facturas:\n")

        for i, fact in enumerate(results[:20], 1):  # Mostrar primeras 20
            print(f"{i}. {fact['nombre_emisor'] or 'Sin nombre'} (RFC: {fact['rfc_emisor'] or 'N/A'})")
            print(f"   UUID: {fact['uuid']}")
            print(f"   Fecha: {fact['fecha_emision']}")
            print(f"   Monto: ${fact['total']:,.2f}")
            print(f"   Status: {fact['sat_status'] or 'Sin verificar'}")
            print()

        if len(results) > 20:
            print(f"\n... y {len(results) - 20} facturas más")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
