"""
API de Consultas por Método y Forma de Pago
============================================
Endpoints para análisis de facturas por método y forma de pago
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter(prefix="/payment-methods", tags=["Payment Methods"])

# Configuración BD
POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}


class PaymentMethodSummary(BaseModel):
    """Resumen por método de pago"""
    metodo_pago: str
    descripcion: str
    cantidad: int
    total_monto: float
    promedio: float


class PaymentFormSummary(BaseModel):
    """Resumen por forma de pago"""
    forma_pago: str
    descripcion: str
    cantidad: int
    total_monto: float
    promedio: float


class InvoicePaymentDetail(BaseModel):
    """Detalle de factura con info de pago"""
    id: int
    uuid: str
    fecha: date
    emisor_nombre: str
    emisor_rfc: str
    total: float
    metodo_pago: Optional[str]
    forma_pago: Optional[str]
    sat_status: Optional[str]


@router.get("/summary")
async def get_payment_summary(
    company_id: int = Query(..., description="ID de la compañía"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)")
):
    """
    Resumen general de métodos y formas de pago

    Returns:
        - metodos_pago: Distribución por método (PUE/PPD/PIP)
        - formas_pago: Distribución por forma (01-99)
        - totales: Montos totales
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        # Construir WHERE clause
        where_clauses = ["company_id = %s"]
        params = [company_id]

        if fecha_inicio:
            where_clauses.append("fecha >= %s")
            params.append(fecha_inicio)

        if fecha_fin:
            where_clauses.append("fecha <= %s")
            params.append(fecha_fin)

        where_sql = " AND ".join(where_clauses)

        # Resumen por método de pago
        cursor.execute(f"""
            SELECT
                metodo_pago,
                COUNT(*) as cantidad,
                SUM(total) as total_monto,
                AVG(total) as promedio
            FROM expenses
            WHERE {where_sql} AND metodo_pago IS NOT NULL
            GROUP BY metodo_pago
            ORDER BY cantidad DESC;
        """, params)

        metodos = cursor.fetchall()

        # Descripciones de métodos
        metodo_descripciones = {
            'PUE': 'Pago en Una Exhibición',
            'PPD': 'Pago en Parcialidades o Diferido',
            'PIP': 'Pago Inicial y Parcialidades'
        }

        metodos_summary = [
            {
                "metodo_pago": m['metodo_pago'],
                "descripcion": metodo_descripciones.get(m['metodo_pago'], 'Desconocido'),
                "cantidad": m['cantidad'],
                "total_monto": float(m['total_monto']) if m['total_monto'] else 0,
                "promedio": float(m['promedio']) if m['promedio'] else 0
            }
            for m in metodos
        ]

        # Resumen por forma de pago
        cursor.execute(f"""
            SELECT
                forma_pago,
                COUNT(*) as cantidad,
                SUM(total) as total_monto,
                AVG(total) as promedio
            FROM expenses
            WHERE {where_sql} AND forma_pago IS NOT NULL
            GROUP BY forma_pago
            ORDER BY cantidad DESC;
        """, params)

        formas = cursor.fetchall()

        # Descripciones de formas
        forma_descripciones = {
            '01': 'Efectivo',
            '02': 'Cheque nominativo',
            '03': 'Transferencia electrónica',
            '04': 'Tarjeta de crédito',
            '05': 'Monedero electrónico',
            '28': 'Tarjeta de débito',
            '99': 'Por definir',
        }

        formas_summary = [
            {
                "forma_pago": f['forma_pago'],
                "descripcion": forma_descripciones.get(f['forma_pago'], f"Forma {f['forma_pago']}"),
                "cantidad": f['cantidad'],
                "total_monto": float(f['total_monto']) if f['total_monto'] else 0,
                "promedio": float(f['promedio']) if f['promedio'] else 0
            }
            for f in formas
        ]

        # Totales generales
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_facturas,
                SUM(total) as total_monto,
                COUNT(CASE WHEN metodo_pago = 'PUE' THEN 1 END) as pue_count,
                COUNT(CASE WHEN metodo_pago = 'PPD' THEN 1 END) as ppd_count,
                SUM(CASE WHEN metodo_pago = 'PUE' THEN total ELSE 0 END) as pue_monto,
                SUM(CASE WHEN metodo_pago = 'PPD' THEN total ELSE 0 END) as ppd_monto
            FROM expenses
            WHERE {where_sql};
        """, params)

        totales = cursor.fetchone()

        cursor.close()
        conn.close()

        return {
            "success": True,
            "company_id": company_id,
            "periodo": {
                "inicio": fecha_inicio,
                "fin": fecha_fin
            },
            "metodos_pago": metodos_summary,
            "formas_pago": formas_summary,
            "totales": {
                "facturas": totales['total_facturas'],
                "monto_total": float(totales['total_monto']) if totales['total_monto'] else 0,
                "pagado_inmediato": {
                    "cantidad": totales['pue_count'],
                    "monto": float(totales['pue_monto']) if totales['pue_monto'] else 0
                },
                "por_pagar": {
                    "cantidad": totales['ppd_count'],
                    "monto": float(totales['ppd_monto']) if totales['ppd_monto'] else 0
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/ppd-pending")
async def get_ppd_pending(
    company_id: int = Query(..., description="ID de la compañía"),
    limit: int = Query(100, description="Límite de resultados")
):
    """
    Facturas PPD (Pago Diferido) pendientes de pago

    Útil para ver cuentas por cobrar/pagar
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                uuid,
                fecha,
                emisor_nombre,
                emisor_rfc,
                total,
                metodo_pago,
                forma_pago,
                sat_status
            FROM expenses
            WHERE company_id = %s
            AND metodo_pago = 'PPD'
            AND sat_status = 'vigente'
            ORDER BY fecha DESC
            LIMIT %s;
        """, [company_id, limit])

        facturas = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "success": True,
            "company_id": company_id,
            "total": len(facturas),
            "monto_total": sum(f['total'] for f in facturas),
            "facturas": [dict(f) for f in facturas]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/by-method/{metodo}")
async def get_by_method(
    metodo: str,
    company_id: int = Query(..., description="ID de la compañía"),
    limit: int = Query(100, description="Límite de resultados")
):
    """
    Listar facturas por método de pago específico

    metodo: PUE, PPD, o PIP
    """
    if metodo not in ['PUE', 'PPD', 'PIP']:
        raise HTTPException(status_code=400, detail="Método debe ser PUE, PPD o PIP")

    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                uuid,
                fecha,
                emisor_nombre,
                emisor_rfc,
                receptor_nombre,
                total,
                metodo_pago,
                forma_pago,
                sat_status
            FROM expenses
            WHERE company_id = %s
            AND metodo_pago = %s
            ORDER BY fecha DESC
            LIMIT %s;
        """, [company_id, metodo, limit])

        facturas = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "success": True,
            "company_id": company_id,
            "metodo_pago": metodo,
            "total": len(facturas),
            "monto_total": sum(f['total'] for f in facturas),
            "facturas": [dict(f) for f in facturas]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/cash-flow")
async def get_cash_flow_analysis(
    company_id: int = Query(..., description="ID de la compañía"),
    fecha_inicio: Optional[str] = Query(None, description="Fecha inicio"),
    fecha_fin: Optional[str] = Query(None, description="Fecha fin")
):
    """
    Análisis de flujo de efectivo basado en métodos de pago

    - PUE: Dinero ya pagado/cobrado (flujo real)
    - PPD: Dinero por pagar/cobrar (flujo proyectado)
    """
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        where_clauses = ["company_id = %s"]
        params = [company_id]

        if fecha_inicio:
            where_clauses.append("fecha >= %s")
            params.append(fecha_inicio)

        if fecha_fin:
            where_clauses.append("fecha <= %s")
            params.append(fecha_fin)

        where_sql = " AND ".join(where_clauses)

        cursor.execute(f"""
            SELECT
                SUM(CASE WHEN metodo_pago = 'PUE' THEN total ELSE 0 END) as flujo_real,
                SUM(CASE WHEN metodo_pago = 'PPD' THEN total ELSE 0 END) as flujo_proyectado,
                SUM(total) as total_general,
                COUNT(CASE WHEN metodo_pago = 'PUE' THEN 1 END) as facturas_pue,
                COUNT(CASE WHEN metodo_pago = 'PPD' THEN 1 END) as facturas_ppd
            FROM expenses
            WHERE {where_sql};
        """, params)

        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return {
            "success": True,
            "company_id": company_id,
            "periodo": {
                "inicio": fecha_inicio,
                "fin": fecha_fin
            },
            "flujo_efectivo": {
                "real": {
                    "monto": float(result['flujo_real']) if result['flujo_real'] else 0,
                    "facturas": result['facturas_pue'],
                    "descripcion": "Dinero ya pagado/cobrado (PUE)"
                },
                "proyectado": {
                    "monto": float(result['flujo_proyectado']) if result['flujo_proyectado'] else 0,
                    "facturas": result['facturas_ppd'],
                    "descripcion": "Dinero por pagar/cobrar (PPD)"
                },
                "total": float(result['total_general']) if result['total_general'] else 0
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
