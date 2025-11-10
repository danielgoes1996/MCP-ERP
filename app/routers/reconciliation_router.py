"""
API Router para Conciliación Bancaria
Endpoints críticos para la presentación del VC
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.shared.db_config import get_connection

router = APIRouter(prefix="/api/v1", tags=["reconciliation"])


# ==================== MODELS ====================

class ReconciliationStats(BaseModel):
    """Estadísticas de conciliación"""
    tasa_conciliacion: float = Field(..., description="Porcentaje de conciliación")
    cfdis_conciliados: int = Field(..., description="Número de CFDIs conciliados")
    cfdis_pendientes: int = Field(..., description="Número de CFDIs pendientes")
    monto_conciliado: float = Field(..., description="Monto total conciliado")
    monto_pendiente: float = Field(..., description="Monto total pendiente")


class PendingCFDI(BaseModel):
    """CFDI pendiente de conciliar"""
    id: int
    nombre_emisor: str
    total: float
    fecha_emision: str
    serie: Optional[str]
    folio: Optional[str]


class PendingCFDIsResponse(BaseModel):
    """Respuesta de CFDIs pendientes"""
    total: int
    monto_pendiente: float
    cfdis: List[PendingCFDI]


class MatchSuggestion(BaseModel):
    """Sugerencia de match CFDI ↔ Bank"""
    cfdi_id: int
    bank_tx_id: int
    score: float
    cfdi_emisor: str
    tx_description: str
    amount_diff: float


class MatchSuggestionsResponse(BaseModel):
    """Respuesta de sugerencias de matches"""
    total_sugerencias: int
    sugerencias: List[MatchSuggestion]


class ApplyMatchRequest(BaseModel):
    """Request para aplicar conciliación"""
    cfdi_id: int
    bank_tx_id: int


class MSIPayment(BaseModel):
    """Pago diferido MSI"""
    cfdi_id: int
    comercio: str
    monto_original: float
    total_meses: int
    pagos_realizados: int
    saldo_pendiente: float
    proxima_cuota: str


# ==================== ENDPOINTS ====================

@router.get("/reconciliation/stats", response_model=ReconciliationStats)
async def get_reconciliation_stats(
    mes: int = Query(1, description="Mes (1-12)"),
    año: int = Query(2025, description="Año")
):
    """
    📊 Obtener estadísticas de conciliación

    Retorna métricas clave:
    - Tasa de conciliación (%)
    - CFDIs conciliados vs pendientes
    - Montos conciliados vs pendientes
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # CFDIs totales
        cursor.execute("""
            SELECT COUNT(*), SUM(total)
            FROM expense_invoices
            WHERE EXTRACT(YEAR FROM fecha_emision) = %s
            AND EXTRACT(MONTH FROM fecha_emision) = %s
        """, (año, mes))
        total_cfdis, monto_total = cursor.fetchone()

        if total_cfdis == 0:
            return ReconciliationStats(
                tasa_conciliacion=0,
                cfdis_conciliados=0,
                cfdis_pendientes=0,
                monto_conciliado=0,
                monto_pendiente=0
            )

        # CFDIs conciliados
        cursor.execute("""
            SELECT COUNT(*), SUM(total)
            FROM expense_invoices
            WHERE EXTRACT(YEAR FROM fecha_emision) = %s
            AND EXTRACT(MONTH FROM fecha_emision) = %s
            AND linked_expense_id IS NOT NULL
        """, (año, mes))
        conciliados, monto_conciliado = cursor.fetchone()

        conciliados = conciliados or 0
        monto_conciliado = float(monto_conciliado or 0)
        monto_total = float(monto_total or 0)

        tasa = (conciliados / total_cfdis * 100) if total_cfdis > 0 else 0

        return ReconciliationStats(
            tasa_conciliacion=round(tasa, 1),
            cfdis_conciliados=conciliados,
            cfdis_pendientes=total_cfdis - conciliados,
            monto_conciliado=monto_conciliado,
            monto_pendiente=monto_total - monto_conciliado
        )

    finally:
        cursor.close()
        conn.close()


@router.get("/cfdis/pending", response_model=PendingCFDIsResponse)
async def get_pending_cfdis(
    mes: int = Query(1, description="Mes (1-12)"),
    año: int = Query(2025, description="Año"),
    limit: int = Query(50, description="Máximo de resultados")
):
    """
    📄 Listar CFDIs sin conciliar

    Retorna CFDIs que aún no están conciliados con transacciones bancarias
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                nombre_emisor,
                total,
                fecha_emision,
                serie,
                folio
            FROM expense_invoices
            WHERE EXTRACT(YEAR FROM fecha_emision) = %s
            AND EXTRACT(MONTH FROM fecha_emision) = %s
            AND linked_expense_id IS NULL
            ORDER BY total DESC
            LIMIT %s
        """, (año, mes, limit))

        rows = cursor.fetchall()

        cfdis = []
        monto_total = 0

        for row in rows:
            cfdi = PendingCFDI(
                id=row[0],
                nombre_emisor=row[1],
                total=float(row[2]),
                fecha_emision=row[3].strftime('%Y-%m-%d') if row[3] else None,
                serie=row[4],
                folio=row[5]
            )
            cfdis.append(cfdi)
            monto_total += cfdi.total

        return PendingCFDIsResponse(
            total=len(cfdis),
            monto_pendiente=monto_total,
            cfdis=cfdis
        )

    finally:
        cursor.close()
        conn.close()


@router.get("/reconciliation/suggestions", response_model=MatchSuggestionsResponse)
async def get_match_suggestions(
    threshold: float = Query(0.85, description="Score mínimo de confianza"),
    limit: int = Query(20, description="Máximo de sugerencias")
):
    """
    🎯 Obtener sugerencias de matches automáticos

    Usa embeddings y fuzzy matching para sugerir conciliaciones
    con alta confianza (> threshold)
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Por ahora retorna sugerencias basadas en montos exactos
        # TODO: Integrar con embedding_matcher.py para scoring real

        cursor.execute("""
            SELECT
                ei.id as cfdi_id,
                bt.id as bank_tx_id,
                ei.nombre_emisor,
                bt.description,
                ei.total,
                bt.amount,
                ABS(ei.total - ABS(bt.amount)) as diff
            FROM expense_invoices ei
            CROSS JOIN bank_transactions bt
            WHERE ei.linked_expense_id IS NULL
            AND bt.reconciled_invoice_id IS NULL
            AND ABS(ei.total - ABS(bt.amount)) < 1.0
            AND EXTRACT(YEAR FROM ei.fecha_emision) = EXTRACT(YEAR FROM bt.transaction_date)
            AND EXTRACT(MONTH FROM ei.fecha_emision) = EXTRACT(MONTH FROM bt.transaction_date)
            ORDER BY diff ASC
            LIMIT %s
        """, (limit,))

        rows = cursor.fetchall()

        sugerencias = []
        for row in rows:
            # Simple scoring basado en diferencia de monto
            # Entre más cercano el monto, mayor el score
            diff = float(row[6])
            score = max(0.85, 1.0 - (diff / 100.0))  # 1.0 si diff=0, 0.85+ si diff pequeño

            sugerencia = MatchSuggestion(
                cfdi_id=row[0],
                bank_tx_id=row[1],
                cfdi_emisor=row[2],
                tx_description=row[3],
                score=round(score, 2),
                amount_diff=diff
            )
            sugerencias.append(sugerencia)

        return MatchSuggestionsResponse(
            total_sugerencias=len(sugerencias),
            sugerencias=sugerencias
        )

    finally:
        cursor.close()
        conn.close()


@router.post("/reconciliation/apply")
async def apply_reconciliation(request: ApplyMatchRequest):
    """
    ✅ Aplicar conciliación manualmente

    Vincula un CFDI con una transacción bancaria
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Verificar que CFDI existe y no está conciliado
        cursor.execute("""
            SELECT id, nombre_emisor, total, linked_expense_id
            FROM expense_invoices
            WHERE id = %s
        """, (request.cfdi_id,))

        cfdi = cursor.fetchone()
        if not cfdi:
            raise HTTPException(status_code=404, detail=f"CFDI {request.cfdi_id} no encontrado")

        if cfdi[3] is not None:
            raise HTTPException(status_code=400, detail=f"CFDI {request.cfdi_id} ya está conciliado")

        # Verificar que transacción existe y no está conciliada
        cursor.execute("""
            SELECT id, description, amount, reconciled_invoice_id
            FROM bank_transactions
            WHERE id = %s
        """, (request.bank_tx_id,))

        tx = cursor.fetchone()
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transacción {request.bank_tx_id} no encontrada")

        if tx[3] is not None:
            raise HTTPException(status_code=400, detail=f"Transacción {request.bank_tx_id} ya está conciliada")

        # Aplicar conciliación en ambas direcciones
        cursor.execute("""
            UPDATE expense_invoices
            SET
                linked_expense_id = %s,
                match_confidence = 1.0,
                match_method = %s,
                match_date = NOW()
            WHERE id = %s
        """, (request.bank_tx_id, f"Manual: Bank TX #{request.bank_tx_id}", request.cfdi_id))

        cursor.execute("""
            UPDATE bank_transactions
            SET
                reconciled_invoice_id = %s,
                match_confidence = 1.0,
                reconciliation_status = 'reconciled',
                reconciled_at = NOW()
            WHERE id = %s
        """, (request.cfdi_id, request.bank_tx_id))

        conn.commit()

        return {
            "success": True,
            "message": f"CFDI {request.cfdi_id} conciliado con transacción {request.bank_tx_id}",
            "cfdi_id": request.cfdi_id,
            "bank_tx_id": request.bank_tx_id
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al aplicar conciliación: {str(e)}")
    finally:
        cursor.close()
        conn.close()


@router.get("/msi/active", response_model=List[MSIPayment])
async def get_active_msi():
    """
    💳 Obtener pagos diferidos (MSI) activos

    Retorna pagos a meses sin intereses que aún tienen saldo pendiente
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Verificar si tabla existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'deferred_payments'
            )
        """)

        tabla_existe = cursor.fetchone()[0]

        if not tabla_existe:
            return []

        cursor.execute("""
            SELECT
                dp.cfdi_id,
                ei.nombre_emisor,
                dp.total_amount,
                dp.meses_sin_intereses,
                dp.pagos_realizados,
                dp.saldo_pendiente,
                dp.primer_pago_fecha,
                dp.ultimo_pago_fecha
            FROM deferred_payments dp
            JOIN expense_invoices ei ON ei.id = dp.cfdi_id
            WHERE dp.status = 'activo'
            ORDER BY dp.total_amount DESC
        """)

        rows = cursor.fetchall()

        pagos = []
        for row in rows:
            # Calcular próxima cuota
            primer_pago = row[6]
            pagos_realizados = row[4]

            # Próxima cuota = primer_pago + (pagos_realizados * 30 días)
            from datetime import timedelta
            proxima_cuota = primer_pago + timedelta(days=30 * pagos_realizados)

            pago = MSIPayment(
                cfdi_id=row[0],
                comercio=row[1],
                monto_original=float(row[2]),
                total_meses=row[3],
                pagos_realizados=pagos_realizados,
                saldo_pendiente=float(row[5]),
                proxima_cuota=proxima_cuota.strftime('%Y-%m-%d')
            )
            pagos.append(pago)

        return pagos

    finally:
        cursor.close()
        conn.close()
