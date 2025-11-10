#!/usr/bin/env python3
"""
Dashboard de Análisis de Métodos y Formas de Pago
Genera reportes visuales de clasificación PUE/PPD y formas de pago.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuración PostgreSQL
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

# Catálogos SAT
METODO_PAGO_DESC = {
    'PUE': 'Pago en Una Exhibición',
    'PPD': 'Pago en Parcialidades o Diferido',
    'PIP': 'Pago Inicial y Parcialidades'
}

FORMA_PAGO_DESC = {
    '01': 'Efectivo',
    '02': 'Cheque nominativo',
    '03': 'Transferencia electrónica',
    '04': 'Tarjeta de crédito',
    '05': 'Monedero electrónico',
    '06': 'Dinero electrónico',
    '08': 'Vales de despensa',
    '12': 'Dación en pago',
    '13': 'Pago por subrogación',
    '14': 'Pago por consignación',
    '15': 'Condonación',
    '17': 'Compensación',
    '23': 'Novación',
    '24': 'Confusión',
    '25': 'Remisión de deuda',
    '26': 'Prescripción o caducidad',
    '27': 'A satisfacción del acreedor',
    '28': 'Tarjeta de débito',
    '29': 'Tarjeta de servicios',
    '30': 'Aplicación de anticipos',
    '31': 'Intermediario pagos',
    '99': 'Por definir'
}

# Catálogo Uso CFDI (c_UsoCFDI)
USO_CFDI_DESC = {
    'G01': 'Adquisición de mercancías',
    'G02': 'Devoluciones, descuentos o bonificaciones',
    'G03': 'Gastos en general',
    'I01': 'Construcciones',
    'I02': 'Mobiliario y equipo de oficina por inversiones',
    'I03': 'Equipo de transporte',
    'I04': 'Equipo de cómputo y accesorios',
    'I05': 'Dados, troqueles, moldes, matrices y herramental',
    'I06': 'Comunicaciones telefónicas',
    'I07': 'Comunicaciones satelitales',
    'I08': 'Otra maquinaria y equipo',
    'D01': 'Honorarios médicos, dentales y gastos hospitalarios',
    'D02': 'Gastos médicos por incapacidad o discapacidad',
    'D03': 'Gastos funerales',
    'D04': 'Donativos',
    'D05': 'Intereses reales efectivamente pagados por créditos hipotecarios',
    'D06': 'Aportaciones voluntarias al SAR',
    'D07': 'Primas por seguros de gastos médicos',
    'D08': 'Gastos de transportación escolar obligatoria',
    'D09': 'Depósitos en cuentas para el ahorro',
    'D10': 'Pagos por servicios educativos',
    'P01': 'Por definir',
    'CP01': 'Pagos (Complemento de pago)',
    'CN01': 'Nómina',
    'S01': 'Sin efectos fiscales'
}

def format_currency(amount: float) -> str:
    """Formatear cantidad como moneda mexicana"""
    if amount is None:
        return "$0.00"
    return f"${amount:,.2f}"

def format_percentage(value: float, total: float) -> str:
    """Calcular y formatear porcentaje"""
    if total == 0:
        return "0.0%"
    pct = (value / total) * 100
    return f"{pct:.1f}%"

def calculate_payment_stats(
    company_id: int,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcular estadísticas completas de métodos y formas de pago.

    Args:
        company_id: ID de la empresa
        fecha_inicio: Fecha inicio en formato YYYY-MM-DD (opcional)
        fecha_fin: Fecha fin en formato YYYY-MM-DD (opcional)

    Returns:
        Dict con todas las estadísticas calculadas
    """
    # Conectar a PostgreSQL
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Construir filtros de fecha
    fecha_filter = ""
    params = [company_id]

    if fecha_inicio:
        fecha_filter += " AND fecha_emision >= %s"
        params.append(fecha_inicio)

    if fecha_fin:
        fecha_filter += " AND fecha_emision <= %s"
        params.append(fecha_fin)

    stats = {
        "company_id": company_id,
        "periodo": {
            "inicio": fecha_inicio or "Sin límite",
            "fin": fecha_fin or "Sin límite"
        },
        "resumen_general": {},
        "metodos_pago": [],
        "formas_pago": [],
        "uso_cfdi": [],
        "flujo_efectivo": {},
        "ppd_pendientes": [],
        "tendencias_mensuales": [],
        "top_proveedores_ppd": [],
        "distribucion_combinada": [],
        "gastos_por_categoria": [],
        "alertas": []
    }

    try:
        # 1. Resumen General
        query = f"""
            SELECT
                COUNT(*) as total_facturas,
                SUM(total) as monto_total,
                AVG(total) as promedio_factura,
                COUNT(DISTINCT rfc_emisor) as total_proveedores
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            {fecha_filter}
        """

        cursor.execute(query, tuple(params))
        result = cursor.fetchone()
        if result:
            stats["resumen_general"] = {
                "total_facturas": result['total_facturas'] or 0,
                "monto_total": float(result['monto_total'] or 0),
                "promedio_factura": float(result['promedio_factura'] or 0),
                "total_proveedores": result['total_proveedores'] or 0
            }

        # 2. Distribución por Método de Pago
        query = f"""
            SELECT
                metodo_pago,
                COUNT(*) as cantidad,
                SUM(total) as monto_total,
                AVG(total) as promedio
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND metodo_pago IS NOT NULL
            {fecha_filter}
            GROUP BY metodo_pago
            ORDER BY monto_total DESC
        """

        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        total_facturas = stats["resumen_general"]["total_facturas"]
        total_monto = stats["resumen_general"]["monto_total"]

        for row in results:
            metodo = row['metodo_pago']
            cantidad = row['cantidad']
            monto = float(row['monto_total'] or 0)

            stats["metodos_pago"].append({
                "metodo": metodo,
                "descripcion": METODO_PAGO_DESC.get(metodo, metodo),
                "cantidad": cantidad,
                "monto": monto,
                "promedio": float(row['promedio'] or 0),
                "porcentaje_cantidad": format_percentage(cantidad, total_facturas),
                "porcentaje_monto": format_percentage(monto, total_monto)
            })

        # 3. Distribución por Forma de Pago
        query = f"""
            SELECT
                forma_pago,
                COUNT(*) as cantidad,
                SUM(total) as monto_total,
                AVG(total) as promedio
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND forma_pago IS NOT NULL
            {fecha_filter}
            GROUP BY forma_pago
            ORDER BY monto_total DESC
        """

        cursor.execute(query, tuple(params))

        results = cursor.fetchall()

        for row in results:
            forma = row['forma_pago']
            cantidad = row['cantidad']
            monto = float(row['monto_total'] or 0)

            stats["formas_pago"].append({
                "forma": forma,
                "descripcion": FORMA_PAGO_DESC.get(forma, f"Código {forma}"),
                "cantidad": cantidad,
                "monto": monto,
                "promedio": float(row['promedio'] or 0),
                "porcentaje_cantidad": format_percentage(cantidad, total_facturas),
                "porcentaje_monto": format_percentage(monto, total_monto)
            })

        # 3.5. Distribución por Uso CFDI (Tipo de Gasto)
        query = f"""
            SELECT
                uso_cfdi,
                COUNT(*) as cantidad,
                SUM(total) as monto_total,
                AVG(total) as promedio
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND uso_cfdi IS NOT NULL
            AND uso_cfdi != 'CP01'
            {fecha_filter}
            GROUP BY uso_cfdi
            ORDER BY monto_total DESC
        """

        cursor.execute(query, tuple(params))
        results = cursor.fetchall()

        for row in results:
            uso = row['uso_cfdi']
            cantidad = row['cantidad']
            monto = float(row['monto_total'] or 0)

            # Clasificar en categorías
            if uso.startswith('G'):
                categoria = 'Gastos'
            elif uso.startswith('I'):
                categoria = 'Inversiones'
            elif uso.startswith('D'):
                categoria = 'Deducciones Personales'
            elif uso == 'P01':
                categoria = 'Por definir'
            else:
                categoria = 'Otros'

            stats["uso_cfdi"].append({
                "uso": uso,
                "descripcion": USO_CFDI_DESC.get(uso, f"Código {uso}"),
                "categoria": categoria,
                "cantidad": cantidad,
                "monto": monto,
                "promedio": float(row['promedio'] or 0),
                "porcentaje_cantidad": format_percentage(cantidad, total_facturas),
                "porcentaje_monto": format_percentage(monto, total_monto)
            })

        # 3.6. Gastos por Categoría (Agrupado)
        gastos_categorias = {}
        for item in stats["uso_cfdi"]:
            cat = item["categoria"]
            if cat not in gastos_categorias:
                gastos_categorias[cat] = {"cantidad": 0, "monto": 0}
            gastos_categorias[cat]["cantidad"] += item["cantidad"]
            gastos_categorias[cat]["monto"] += item["monto"]

        for categoria, datos in gastos_categorias.items():
            stats["gastos_por_categoria"].append({
                "categoria": categoria,
                "cantidad": datos["cantidad"],
                "monto": datos["monto"],
                "porcentaje_cantidad": format_percentage(datos["cantidad"], total_facturas),
                "porcentaje_monto": format_percentage(datos["monto"], total_monto)
            })

        # Ordenar por monto
        stats["gastos_por_categoria"].sort(key=lambda x: x["monto"], reverse=True)

        # 4. Análisis de Flujo de Efectivo
        query = f"""
            SELECT
                SUM(CASE WHEN metodo_pago = 'PUE' THEN total ELSE 0 END) as flujo_real,
                COUNT(CASE WHEN metodo_pago = 'PUE' THEN 1 END) as facturas_real,
                SUM(CASE WHEN metodo_pago = 'PPD' THEN total ELSE 0 END) as flujo_proyectado,
                COUNT(CASE WHEN metodo_pago = 'PPD' THEN 1 END) as facturas_proyectado,
                SUM(CASE WHEN metodo_pago = 'PIP' THEN total ELSE 0 END) as flujo_mixto,
                COUNT(CASE WHEN metodo_pago = 'PIP' THEN 1 END) as facturas_mixto
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            {fecha_filter}
        """

        cursor.execute(query, tuple(params))
        result = cursor.fetchone()
        if result:
            row = result
            flujo_real = float(row['flujo_real'] or 0)
            flujo_proyectado = float(row['flujo_proyectado'] or 0)
            flujo_mixto = float(row['flujo_mixto'] or 0)

            stats["flujo_efectivo"] = {
                "real": {
                    "monto": flujo_real,
                    "facturas": row['facturas_real'] or 0,
                    "descripcion": "Ya pagado/cobrado (PUE)"
                },
                "proyectado": {
                    "monto": flujo_proyectado,
                    "facturas": row['facturas_proyectado'] or 0,
                    "descripcion": "Por pagar/cobrar (PPD)"
                },
                "mixto": {
                    "monto": flujo_mixto,
                    "facturas": row['facturas_mixto'] or 0,
                    "descripcion": "Pago inicial + parcialidades (PIP)"
                },
                "total": flujo_real + flujo_proyectado + flujo_mixto
            }

        # 5. Facturas PPD Pendientes (Cuentas por Cobrar/Pagar)
        query = f"""
            SELECT
                uuid,
                fecha_emision as fecha,
                nombre_emisor,
                rfc_emisor,
                total,
                forma_pago,
                CURRENT_DATE - fecha_emision::date as dias_desde_emision
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND metodo_pago = 'PPD'
            {fecha_filter}
            ORDER BY fecha_emision DESC
            LIMIT 20
        """

        cursor.execute(query, tuple(params))

        results = cursor.fetchall()

        for row in results:
            stats["ppd_pendientes"].append({
                "uuid": row['uuid'],
                "fecha": str(row['fecha']),
                "emisor": row['nombre_emisor'],
                "rfc": row['rfc_emisor'],
                "monto": float(row['total']),
                "forma_pago": FORMA_PAGO_DESC.get(row['forma_pago'], row['forma_pago']),
                "dias_desde_emision": row['dias_desde_emision']
            })

        # 6. Tendencias Mensuales (últimos 6 meses)
        query = f"""
            SELECT
                TO_CHAR(fecha_emision, 'YYYY-MM') as mes,
                COUNT(*) as total_facturas,
                SUM(CASE WHEN metodo_pago = 'PUE' THEN total ELSE 0 END) as pue_monto,
                COUNT(CASE WHEN metodo_pago = 'PUE' THEN 1 END) as pue_cantidad,
                SUM(CASE WHEN metodo_pago = 'PPD' THEN total ELSE 0 END) as ppd_monto,
                COUNT(CASE WHEN metodo_pago = 'PPD' THEN 1 END) as ppd_cantidad
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND fecha_emision >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY mes
            ORDER BY mes DESC
        """

        cursor.execute(query, [company_id])

        results = cursor.fetchall()

        for row in results:
            stats["tendencias_mensuales"].append({
                "mes": row['mes'],
                "total_facturas": row['total_facturas'],
                "pue": {
                    "monto": float(row['pue_monto'] or 0),
                    "cantidad": row['pue_cantidad'] or 0
                },
                "ppd": {
                    "monto": float(row['ppd_monto'] or 0),
                    "cantidad": row['ppd_cantidad'] or 0
                }
            })

        # 7. Top Proveedores con PPD
        query = f"""
            SELECT
                nombre_emisor,
                rfc_emisor,
                COUNT(*) as facturas_ppd,
                SUM(total) as monto_ppd
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND metodo_pago = 'PPD'
            {fecha_filter}
            GROUP BY nombre_emisor, rfc_emisor
            ORDER BY monto_ppd DESC
            LIMIT 10
        """

        cursor.execute(query, tuple(params))

        results = cursor.fetchall()

        for row in results:
            stats["top_proveedores_ppd"].append({
                "nombre": row['nombre_emisor'],
                "rfc": row['rfc_emisor'],
                "facturas": row['facturas_ppd'],
                "monto": float(row['monto_ppd'])
            })

        # 8. Distribución Combinada (Método + Forma)
        query = f"""
            SELECT
                metodo_pago,
                forma_pago,
                COUNT(*) as cantidad,
                SUM(total) as monto
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND metodo_pago IS NOT NULL
            AND forma_pago IS NOT NULL
            {fecha_filter}
            GROUP BY metodo_pago, forma_pago
            ORDER BY monto DESC
            LIMIT 15
        """

        cursor.execute(query, tuple(params))

        results = cursor.fetchall()

        for row in results:
            stats["distribucion_combinada"].append({
                "metodo": row['metodo_pago'],
                "metodo_desc": METODO_PAGO_DESC.get(row['metodo_pago'], row['metodo_pago']),
                "forma": row['forma_pago'],
                "forma_desc": FORMA_PAGO_DESC.get(row['forma_pago'], row['forma_pago']),
                "cantidad": row['cantidad'],
                "monto": float(row['monto'])
            })

        # 9. Generar Alertas
        alertas = []

        # Alerta: Alto monto en PPD
        if stats["flujo_efectivo"].get("proyectado", {}).get("monto", 0) > 0:
            monto_ppd = stats["flujo_efectivo"]["proyectado"]["monto"]
            monto_total = stats["flujo_efectivo"]["total"]
            porcentaje_ppd = (monto_ppd / monto_total * 100) if monto_total > 0 else 0

            if porcentaje_ppd > 30:
                alertas.append({
                    "tipo": "warning",
                    "titulo": "Alto porcentaje de PPD",
                    "mensaje": f"{porcentaje_ppd:.1f}% del monto total está en PPD (por cobrar/pagar)",
                    "recomendacion": "Revisar antigüedad de saldos pendientes"
                })

        # Alerta: Facturas PPD antiguas
        facturas_antiguas = [f for f in stats["ppd_pendientes"] if f["dias_desde_emision"] > 90]
        if facturas_antiguas:
            alertas.append({
                "tipo": "danger",
                "titulo": "Facturas PPD antiguas",
                "mensaje": f"{len(facturas_antiguas)} facturas PPD con más de 90 días",
                "recomendacion": "Gestionar cobro/pago de facturas vencidas"
            })

        # Alerta: Sin clasificación
        query = f"""
            SELECT COUNT(*) as sin_clasificar
            FROM expense_invoices
            WHERE company_id = %s
            AND sat_status = 'vigente'
            AND (metodo_pago IS NULL OR forma_pago IS NULL)
            {fecha_filter}
        """

        cursor.execute(query, tuple(params))
        result = cursor.fetchone()
        if result and result['sin_clasificar'] > 0:
            alertas.append({
                "tipo": "info",
                "titulo": "Facturas sin clasificar",
                "mensaje": f"{result['sin_clasificar']} facturas sin método/forma de pago",
                "recomendacion": "Ejecutar script de actualización: update_payment_methods.py"
            })

        stats["alertas"] = alertas

        # Metadata
        stats["metadata"] = {
            "generado_en": datetime.now().isoformat(),
            "version": "1.0"
        }

        # Cerrar conexión
        conn.close()

    except Exception as e:
        stats["error"] = str(e)
        import traceback
        stats["traceback"] = traceback.format_exc()
        # Intentar cerrar conexión en caso de error
        try:
            conn.close()
        except:
            pass

    return stats

def print_dashboard(stats: Dict[str, Any]):
    """
    Imprimir dashboard en consola con formato visual.
    """
    print("\n" + "=" * 80)
    print("💳 DASHBOARD DE MÉTODOS Y FORMAS DE PAGO")
    print("=" * 80)

    # Periodo
    print(f"\n📅 Periodo: {stats['periodo']['inicio']} → {stats['periodo']['fin']}")
    print(f"🏢 Company ID: {stats['company_id']}")

    # Resumen General
    print("\n" + "─" * 80)
    print("📊 RESUMEN GENERAL")
    print("─" * 80)
    resumen = stats["resumen_general"]
    print(f"  Total Facturas:     {resumen['total_facturas']:,}")
    print(f"  Monto Total:        {format_currency(resumen['monto_total'])}")
    print(f"  Promedio/Factura:   {format_currency(resumen['promedio_factura'])}")
    print(f"  Total Proveedores:  {resumen['total_proveedores']:,}")

    # Flujo de Efectivo
    print("\n" + "─" * 80)
    print("💰 ANÁLISIS DE FLUJO DE EFECTIVO")
    print("─" * 80)
    flujo = stats["flujo_efectivo"]

    print(f"\n  ✅ FLUJO REAL (PUE - Ya pagado/cobrado)")
    print(f"     Monto:     {format_currency(flujo['real']['monto'])}")
    print(f"     Facturas:  {flujo['real']['facturas']}")

    print(f"\n  ⏳ FLUJO PROYECTADO (PPD - Por pagar/cobrar)")
    print(f"     Monto:     {format_currency(flujo['proyectado']['monto'])}")
    print(f"     Facturas:  {flujo['proyectado']['facturas']}")

    if flujo['mixto']['facturas'] > 0:
        print(f"\n  🔀 FLUJO MIXTO (PIP - Inicial + Parcialidades)")
        print(f"     Monto:     {format_currency(flujo['mixto']['monto'])}")
        print(f"     Facturas:  {flujo['mixto']['facturas']}")

    # Distribución por Método
    print("\n" + "─" * 80)
    print("🎯 DISTRIBUCIÓN POR MÉTODO DE PAGO (¿CUÁNDO?)")
    print("─" * 80)
    print(f"\n  {'Método':<7} {'Descripción':<35} {'Facturas':>10} {'Monto':>15} {'%'}")
    print("  " + "-" * 78)

    for metodo in stats["metodos_pago"]:
        print(f"  {metodo['metodo']:<7} {metodo['descripcion']:<35} "
              f"{metodo['cantidad']:>10,} {format_currency(metodo['monto']):>15} "
              f"{metodo['porcentaje_monto']}")

    # Distribución por Forma
    print("\n" + "─" * 80)
    print("💵 DISTRIBUCIÓN POR FORMA DE PAGO (¿CÓMO?)")
    print("─" * 80)
    print(f"\n  {'Forma':<5} {'Descripción':<30} {'Facturas':>10} {'Monto':>15} {'%'}")
    print("  " + "-" * 70)

    for forma in stats["formas_pago"][:10]:  # Top 10
        print(f"  {forma['forma']:<5} {forma['descripcion']:<30} "
              f"{forma['cantidad']:>10,} {format_currency(forma['monto']):>15} "
              f"{forma['porcentaje_monto']}")

    # Distribución por Uso CFDI
    if stats["uso_cfdi"]:
        print("\n" + "─" * 80)
        print("📝 DISTRIBUCIÓN POR USO CFDI (TIPO DE FACTURA)")
        print("─" * 80)
        print(f"\n  {'Código':<6} {'Descripción':<40} {'Facturas':>10} {'Monto':>15} {'%'}")
        print("  " + "-" * 82)

        for uso in stats["uso_cfdi"][:15]:  # Top 15
            print(f"  {uso['uso']:<6} {uso['descripcion'][:40]:<40} "
                  f"{uso['cantidad']:>10,} {format_currency(uso['monto']):>15} "
                  f"{uso['porcentaje_monto']}")

    # Gastos por Categoría
    if stats["gastos_por_categoria"]:
        print("\n" + "─" * 80)
        print("🏷️  GASTOS POR CATEGORÍA")
        print("─" * 80)
        print(f"\n  {'Categoría':<25} {'Facturas':>10} {'Monto':>15} {'%'}")
        print("  " + "-" * 60)

        for categoria in stats["gastos_por_categoria"]:
            print(f"  {categoria['categoria']:<25} "
                  f"{categoria['cantidad']:>10,} {format_currency(categoria['monto']):>15} "
                  f"{categoria['porcentaje_monto']}")

    # PPD Pendientes
    if stats["ppd_pendientes"]:
        print("\n" + "─" * 80)
        print(f"📋 FACTURAS PPD PENDIENTES (Top 10)")
        print("─" * 80)
        print(f"\n  {'Fecha':<12} {'Emisor':<30} {'Monto':>15} {'Días':>6}")
        print("  " + "-" * 70)

        for factura in stats["ppd_pendientes"][:10]:
            print(f"  {factura['fecha']:<12} {factura['emisor'][:30]:<30} "
                  f"{format_currency(factura['monto']):>15} {factura['dias_desde_emision']:>6}")

    # Top Proveedores PPD
    if stats["top_proveedores_ppd"]:
        print("\n" + "─" * 80)
        print(f"🏪 TOP PROVEEDORES CON PPD")
        print("─" * 80)
        print(f"\n  {'Proveedor':<40} {'Facturas':>10} {'Monto':>15}")
        print("  " + "-" * 70)

        for proveedor in stats["top_proveedores_ppd"][:5]:
            print(f"  {proveedor['nombre'][:40]:<40} "
                  f"{proveedor['facturas']:>10,} {format_currency(proveedor['monto']):>15}")

    # Tendencias Mensuales
    if stats["tendencias_mensuales"]:
        print("\n" + "─" * 80)
        print(f"📈 TENDENCIAS MENSUALES (Últimos 6 meses)")
        print("─" * 80)
        print(f"\n  {'Mes':<10} {'Total':>8} {'PUE Monto':>15} {'PPD Monto':>15}")
        print("  " + "-" * 70)

        for mes in stats["tendencias_mensuales"]:
            print(f"  {mes['mes']:<10} {mes['total_facturas']:>8,} "
                  f"{format_currency(mes['pue']['monto']):>15} "
                  f"{format_currency(mes['ppd']['monto']):>15}")

    # Alertas
    if stats["alertas"]:
        print("\n" + "─" * 80)
        print(f"⚠️  ALERTAS Y RECOMENDACIONES")
        print("─" * 80)

        for alerta in stats["alertas"]:
            simbolo = {"warning": "⚠️", "danger": "🚨", "info": "ℹ️"}.get(alerta['tipo'], "•")
            print(f"\n  {simbolo} {alerta['titulo']}")
            print(f"     {alerta['mensaje']}")
            print(f"     💡 {alerta['recomendacion']}")

    print("\n" + "=" * 80)
    print(f"✅ Dashboard generado: {stats['metadata']['generado_en']}")
    print("=" * 80 + "\n")

def export_to_json(stats: Dict[str, Any], output_file: str):
    """
    Exportar estadísticas a archivo JSON.
    """
    import json

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False, default=str)

    print(f"✅ Estadísticas exportadas a: {output_file}")

def main():
    """
    Función principal
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Dashboard de Análisis de Métodos y Formas de Pago'
    )
    parser.add_argument(
        '--company-id',
        type=int,
        required=True,
        help='ID de la empresa'
    )
    parser.add_argument(
        '--fecha-inicio',
        help='Fecha inicio (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--fecha-fin',
        help='Fecha fin (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--export-json',
        help='Exportar a archivo JSON'
    )
    parser.add_argument(
        '--ultimos-30-dias',
        action='store_true',
        help='Últimos 30 días'
    )
    parser.add_argument(
        '--mes-actual',
        action='store_true',
        help='Mes actual'
    )

    args = parser.parse_args()

    # Calcular fechas automáticas
    fecha_inicio = args.fecha_inicio
    fecha_fin = args.fecha_fin

    if args.ultimos_30_dias:
        fecha_inicio = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        fecha_fin = datetime.now().strftime('%Y-%m-%d')

    if args.mes_actual:
        now = datetime.now()
        fecha_inicio = now.replace(day=1).strftime('%Y-%m-%d')
        fecha_fin = now.strftime('%Y-%m-%d')

    # Calcular estadísticas
    print("🔄 Calculando estadísticas...")
    stats = calculate_payment_stats(
        company_id=args.company_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )

    # Verificar errores
    if "error" in stats:
        print(f"\n❌ Error: {stats['error']}")
        if "traceback" in stats:
            print(f"\n{stats['traceback']}")
        sys.exit(1)

    # Mostrar dashboard
    print_dashboard(stats)

    # Exportar si se solicitó
    if args.export_json:
        export_to_json(stats, args.export_json)

if __name__ == "__main__":
    main()
