"""
API de Confirmación de MSI
===========================
Endpoints para confirmar/gestionar facturas con Meses Sin Intereses (MSI)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

router = APIRouter(prefix="/msi", tags=["MSI Confirmation"])

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}


class MSIConfirmation(BaseModel):
    """Modelo para confirmar MSI"""
    es_msi: bool
    meses_msi: Optional[int] = None
    pago_mensual_msi: Optional[float] = None
    usuario_id: int


class MSIFactura(BaseModel):
    """Modelo de factura con información MSI"""
    id: int
    uuid: str
    fecha_emision: str
    nombre_emisor: str
    total: float
    es_msi: bool
    meses_msi: Optional[int]
    pago_mensual_msi: Optional[float]
    msi_confirmado: bool


@router.get("/pending", summary="Facturas pendientes de confirmación MSI")
def get_pending_msi_confirmations(
    company_id: int = Query(..., description="ID de la compañía")
):
    """
    Obtiene facturas que requieren confirmación de MSI
    (PUE + Tarjeta crédito + >$100 + No confirmadas)

    🎯 FILTRO INTELIGENTE: Solo muestra facturas de cuentas tipo 'credit_card'
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                ei.id,
                ei.uuid,
                ei.fecha_emision,
                ei.nombre_emisor,
                ei.total,
                ei.es_msi,
                ei.meses_msi,
                ei.pago_mensual_msi,
                ei.msi_confirmado,
                pa.account_name,
                pa.account_type,
                pa.bank_name
            FROM expense_invoices ei
            LEFT JOIN payment_accounts pa ON ei.payment_account_id = pa.id
            WHERE ei.company_id = %s
            AND ei.metodo_pago = 'PUE'
            AND ei.forma_pago = '04'
            AND ei.total > 100
            AND ei.sat_status = 'vigente'
            AND (ei.msi_confirmado = FALSE OR ei.msi_confirmado IS NULL)
            AND pa.account_type = 'credit_card'  -- ✅ FILTRO CRÍTICO: Solo tarjetas de crédito
            ORDER BY ei.fecha_emision DESC;
        """

        cursor.execute(query, [company_id])
        facturas = cursor.fetchall()

        result = []
        for factura in facturas:
            # Calcular posibles planes MSI
            total = float(factura['total'])
            posibles_planes = []

            for meses in [3, 6, 9, 12, 18, 24]:
                pago_mensual = total / meses
                posibles_planes.append({
                    'meses': meses,
                    'pago_mensual': round(pago_mensual, 2)
                })

            result.append({
                'id': factura['id'],
                'uuid': factura['uuid'],
                'fecha_emision': str(factura['fecha_emision']),
                'nombre_emisor': factura['nombre_emisor'],
                'total': total,
                'es_msi': factura['es_msi'] or False,
                'meses_msi': factura['meses_msi'],
                'pago_mensual_msi': float(factura['pago_mensual_msi']) if factura['pago_mensual_msi'] else None,
                'msi_confirmado': factura['msi_confirmado'] or False,
                'posibles_planes_msi': posibles_planes,
                # Información de la cuenta
                'cuenta': {
                    'nombre': factura.get('account_name'),
                    'tipo': factura.get('account_type'),
                    'banco': factura.get('bank_name')
                }
            })

        conn.close()

        return {
            'success': True,
            'total_pendientes': len(result),
            'facturas': result
        }

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm/{invoice_id}", summary="Confirmar estado MSI de una factura")
def confirm_msi_status(
    invoice_id: int,
    confirmation: MSIConfirmation
):
    """
    Confirma si una factura fue pagada a MSI o no
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        # Validaciones
        if confirmation.es_msi:
            if not confirmation.meses_msi:
                raise HTTPException(
                    status_code=400,
                    detail="Si es MSI, debes especificar el número de meses"
                )
            if confirmation.meses_msi not in [3, 6, 9, 12, 18, 24]:
                raise HTTPException(
                    status_code=400,
                    detail="Meses MSI debe ser 3, 6, 9, 12, 18 o 24"
                )
            if not confirmation.pago_mensual_msi:
                raise HTTPException(
                    status_code=400,
                    detail="Si es MSI, debes especificar el pago mensual"
                )

        # Actualizar factura
        update_query = """
            UPDATE expense_invoices
            SET
                es_msi = %s,
                meses_msi = %s,
                pago_mensual_msi = %s,
                msi_confirmado = TRUE,
                msi_confirmado_por = %s,
                msi_confirmado_fecha = NOW()
            WHERE id = %s
            RETURNING id, uuid, nombre_emisor, total, es_msi, meses_msi;
        """

        cursor.execute(update_query, [
            confirmation.es_msi,
            confirmation.meses_msi,
            confirmation.pago_mensual_msi,
            confirmation.usuario_id,
            invoice_id
        ])

        updated = cursor.fetchone()

        if not updated:
            conn.close()
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        conn.commit()
        conn.close()

        return {
            'success': True,
            'message': f"Factura confirmada como {'MSI' if confirmation.es_msi else 'pago completo'}",
            'factura': {
                'id': updated['id'],
                'uuid': updated['uuid'],
                'nombre_emisor': updated['nombre_emisor'],
                'total': float(updated['total']),
                'es_msi': updated['es_msi'],
                'meses_msi': updated['meses_msi']
            }
        }

    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", summary="Listar todas las facturas MSI confirmadas")
def list_msi_invoices(
    company_id: int = Query(..., description="ID de la compañía"),
    solo_msi: bool = Query(False, description="Mostrar solo facturas MSI")
):
    """
    Lista todas las facturas MSI confirmadas
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        where_clause = "WHERE company_id = %s AND msi_confirmado = TRUE"
        if solo_msi:
            where_clause += " AND es_msi = TRUE"

        query = f"""
            SELECT
                id,
                uuid,
                fecha_emision,
                nombre_emisor,
                total,
                es_msi,
                meses_msi,
                pago_mensual_msi,
                msi_confirmado_fecha
            FROM expense_invoices
            {where_clause}
            ORDER BY fecha_emision DESC;
        """

        cursor.execute(query, [company_id])
        facturas = cursor.fetchall()

        result = []
        for factura in facturas:
            result.append({
                'id': factura['id'],
                'uuid': factura['uuid'],
                'fecha_emision': str(factura['fecha_emision']),
                'nombre_emisor': factura['nombre_emisor'],
                'total': float(factura['total']),
                'es_msi': factura['es_msi'],
                'meses_msi': factura['meses_msi'],
                'pago_mensual_msi': float(factura['pago_mensual_msi']) if factura['pago_mensual_msi'] else None,
                'confirmado_fecha': str(factura['msi_confirmado_fecha']) if factura['msi_confirmado_fecha'] else None
            })

        conn.close()

        return {
            'success': True,
            'total': len(result),
            'facturas': result
        }

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates", summary="Candidatos MSI auto-detectados desde estados de cuenta")
def get_msi_candidates(
    company_id: int = Query(..., description="ID de la compañía"),
    min_confidence: float = Query(0.80, description="Confianza mínima (0.0-1.0)", ge=0.0, le=1.0)
):
    """
    Obtiene transacciones bancarias detectadas automáticamente como candidatos MSI

    💳 Auto-detectados por el parser de estados de cuenta
    Solo muestra transacciones de tarjetas de crédito con alta confianza
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                bt.id as transaction_id,
                bt.transaction_date,
                bt.description,
                bt.amount,
                bt.msi_months,
                bt.msi_confidence,
                bt.ai_model,
                bs.file_name as statement_file,
                bs.period_start,
                bs.period_end,
                pa.account_name,
                pa.bank_name,
                ei.id as invoice_id,
                ei.uuid as invoice_uuid,
                ei.nombre_emisor,
                ei.total as invoice_total,
                ei.fecha_emision,
                ei.es_msi as invoice_msi_confirmed,
                ei.meses_msi as invoice_msi_months
            FROM bank_transactions bt
            JOIN bank_statements bs ON bt.statement_id = bs.id
            JOIN payment_accounts pa ON bt.account_id = pa.id
            LEFT JOIN expense_invoices ei ON bt.msi_invoice_id = ei.id
            WHERE bs.company_id = %s
            AND bt.msi_candidate = TRUE
            AND bt.msi_confidence >= %s
            AND pa.account_type = 'credit_card'
            ORDER BY bt.msi_confidence DESC, bt.transaction_date DESC;
        """

        cursor.execute(query, [company_id, min_confidence])
        candidates = cursor.fetchall()

        result = []
        for candidate in candidates:
            result.append({
                'transaction_id': candidate['transaction_id'],
                'fecha_transaccion': str(candidate['transaction_date']),
                'descripcion': candidate['description'],
                'monto_transaccion': float(candidate['amount']),
                'msi_detection': {
                    'meses_detectados': candidate['msi_months'],
                    'confianza': float(candidate['msi_confidence']) if candidate['msi_confidence'] else 0.0,
                    'modelo_ai': candidate['ai_model']
                },
                'estado_cuenta': {
                    'archivo': candidate['statement_file'],
                    'periodo_inicio': str(candidate['period_start']) if candidate['period_start'] else None,
                    'periodo_fin': str(candidate['period_end']) if candidate['period_end'] else None
                },
                'cuenta': {
                    'nombre': candidate['account_name'],
                    'banco': candidate['bank_name']
                },
                'factura_asociada': {
                    'id': candidate['invoice_id'],
                    'uuid': candidate['invoice_uuid'],
                    'emisor': candidate['nombre_emisor'],
                    'total': float(candidate['invoice_total']) if candidate['invoice_total'] else None,
                    'fecha_emision': str(candidate['fecha_emision']) if candidate['fecha_emision'] else None,
                    'msi_confirmado': candidate['invoice_msi_confirmed'] or False,
                    'meses_confirmados': candidate['invoice_msi_months']
                } if candidate['invoice_id'] else None
            })

        conn.close()

        return {
            'success': True,
            'total_candidatos': len(result),
            'confianza_minima': min_confidence,
            'candidatos': result
        }

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", summary="Estadísticas de facturas MSI")
def get_msi_stats(
    company_id: int = Query(..., description="ID de la compañía")
):
    """
    Obtiene estadísticas sobre facturas MSI
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        # Total de facturas MSI
        query_msi = """
            SELECT
                COUNT(*) as total_msi,
                SUM(total) as monto_total_msi,
                AVG(meses_msi) as promedio_meses
            FROM expense_invoices
            WHERE company_id = %s
            AND es_msi = TRUE
            AND sat_status = 'vigente';
        """

        cursor.execute(query_msi, [company_id])
        stats_msi = cursor.fetchone()

        # Distribución por meses
        query_dist = """
            SELECT
                meses_msi,
                COUNT(*) as cantidad,
                SUM(total) as monto
            FROM expense_invoices
            WHERE company_id = %s
            AND es_msi = TRUE
            AND sat_status = 'vigente'
            GROUP BY meses_msi
            ORDER BY meses_msi;
        """

        cursor.execute(query_dist, [company_id])
        distribucion = cursor.fetchall()

        # Pendientes de confirmación (solo credit cards)
        query_pending = """
            SELECT COUNT(*) as pendientes
            FROM expense_invoices ei
            LEFT JOIN payment_accounts pa ON ei.payment_account_id = pa.id
            WHERE ei.company_id = %s
            AND ei.metodo_pago = 'PUE'
            AND ei.forma_pago = '04'
            AND ei.total > 100
            AND (ei.msi_confirmado = FALSE OR ei.msi_confirmado IS NULL)
            AND pa.account_type = 'credit_card';
        """

        cursor.execute(query_pending, [company_id])
        pendientes = cursor.fetchone()

        # Auto-detectados desde estados de cuenta
        query_auto_detected = """
            SELECT
                COUNT(*) as total_detectados,
                SUM(CASE WHEN bt.msi_confidence >= 0.95 THEN 1 ELSE 0 END) as alta_confianza,
                SUM(CASE WHEN bt.msi_confidence < 0.95 THEN 1 ELSE 0 END) as requiere_revision
            FROM bank_transactions bt
            JOIN bank_statements bs ON bt.statement_id = bs.id
            JOIN payment_accounts pa ON bt.account_id = pa.id
            WHERE bs.company_id = %s
            AND bt.msi_candidate = TRUE
            AND pa.account_type = 'credit_card';
        """

        cursor.execute(query_auto_detected, [company_id])
        auto_detected = cursor.fetchone()

        conn.close()

        return {
            'success': True,
            'resumen': {
                'total_facturas_msi': stats_msi['total_msi'] or 0,
                'monto_total_msi': float(stats_msi['monto_total_msi'] or 0),
                'promedio_meses': float(stats_msi['promedio_meses'] or 0),
                'pendientes_confirmacion': pendientes['pendientes'] or 0
            },
            'auto_deteccion': {
                'total_detectados': auto_detected['total_detectados'] or 0,
                'alta_confianza_95': auto_detected['alta_confianza'] or 0,
                'requiere_revision': auto_detected['requiere_revision'] or 0
            },
            'distribucion_por_meses': [
                {
                    'meses': row['meses_msi'],
                    'cantidad': row['cantidad'],
                    'monto': float(row['monto'])
                }
                for row in distribucion
            ]
        }

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
