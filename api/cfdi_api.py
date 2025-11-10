"""
CFDI Verification API
=====================
Endpoints para verificar el estatus de CFDIs en el SAT

Endpoints:
- POST /cfdi/{uuid}/verificar: Verificar un CFDI específico
- POST /cfdi/verificar-batch: Verificar múltiples CFDIs
- GET /cfdi/stats: Estadísticas de verificación
- GET /cfdi/invalidos: Listar CFDIs cancelados/sustituidos
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from core.sat.sat_cfdi_verifier import SATCFDIVerifier, get_status_display_name, is_valid_for_deduction

# ========================================
# Router Setup
# ========================================

router = APIRouter(prefix="/cfdi", tags=["CFDI Verification"])

# ========================================
# Database Connection
# ========================================

POSTGRES_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "database": "mcp_system",
    "user": "mcp_user",
    "password": "changeme"
}

def get_db_conn():
    """Get PostgreSQL connection"""
    return psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)


# ========================================
# Request/Response Models
# ========================================

class CFDIVerificationResponse(BaseModel):
    """Respuesta de verificación de CFDI"""
    uuid: str
    status: str
    status_display: str
    codigo_estatus: Optional[str]
    es_cancelable: Optional[bool]
    estado: Optional[str]
    validacion_efos: Optional[str]
    fecha_verificacion: datetime
    es_valido_deduccion: bool

    class Config:
        json_schema_extra = {
            "example": {
                "uuid": "5EBDC809-1986-40E9-B3DA-754B208A5AF8",
                "status": "vigente",
                "status_display": "Vigente",
                "codigo_estatus": "S",
                "es_cancelable": True,
                "estado": "Vigente",
                "validacion_efos": None,
                "fecha_verificacion": "2025-01-08T12:00:00",
                "es_valido_deduccion": True
            }
        }


class BatchVerificationRequest(BaseModel):
    """Request para verificación de múltiples CFDIs"""
    company_id: int = Field(..., description="ID de la compañía")
    limit: int = Field(100, description="Máximo de CFDIs a verificar", ge=1, le=500)
    only_unverified: bool = Field(True, description="Solo verificar CFDIs sin verificación previa")


class VerificationStatsResponse(BaseModel):
    """Estadísticas de verificación"""
    total_cfdis: int
    vigentes: int
    cancelados: int
    sustituidos: int
    por_cancelar: int
    no_encontrados: int
    sin_verificar: int
    porcentaje_vigentes: float


# ========================================
# Endpoints
# ========================================

@router.post("/{uuid}/verificar", response_model=CFDIVerificationResponse)
async def verificar_cfdi(uuid: str):
    """
    Verifica el estatus de un CFDI en el SAT

    Args:
        uuid: UUID del CFDI a verificar

    Returns:
        Información del estatus del CFDI

    Raises:
        404: Si el CFDI no existe en la base de datos
        500: Si hay error al verificar en el SAT
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        # Buscar CFDI en la base de datos
        cursor.execute("""
            SELECT
                id,
                uuid,
                rfc_emisor,
                rfc_receptor,
                total,
                company_id
            FROM expense_invoices
            WHERE uuid = %s
            LIMIT 1;
        """, (uuid,))

        cfdi = cursor.fetchone()

        if not cfdi:
            raise HTTPException(404, f"CFDI {uuid} no encontrado en la base de datos")

        # Verificar en el SAT (modo MOCK por ahora)
        verifier = SATCFDIVerifier(use_mock=False)

        success, status_info, error = verifier.check_cfdi_status(
            uuid=cfdi['uuid'],
            rfc_emisor=cfdi['rfc_emisor'],
            rfc_receptor=cfdi['rfc_receptor'],
            total=float(cfdi['total'])
        )

        if not success:
            raise HTTPException(500, f"Error al verificar CFDI en el SAT: {error}")

        # Actualizar en la base de datos
        cursor.execute("""
            UPDATE expense_invoices
            SET
                sat_status = %s,
                sat_codigo_estatus = %s,
                sat_es_cancelable = %s,
                sat_estado = %s,
                sat_validacion_efos = %s,
                sat_fecha_verificacion = %s,
                sat_verificacion_count = COALESCE(sat_verificacion_count, 0) + 1,
                updated_at = %s
            WHERE id = %s;
        """, (
            status_info['status'],
            status_info['codigo_estatus'],
            status_info['es_cancelable'],
            status_info['estado'],
            status_info['validacion_efos'],
            status_info['fecha_consulta'],
            datetime.utcnow(),
            cfdi['id']
        ))

        conn.commit()

        # Retornar respuesta
        return CFDIVerificationResponse(
            uuid=cfdi['uuid'],
            status=status_info['status'],
            status_display=get_status_display_name(status_info['status']),
            codigo_estatus=status_info['codigo_estatus'],
            es_cancelable=status_info['es_cancelable'],
            estado=status_info['estado'],
            validacion_efos=status_info['validacion_efos'],
            fecha_verificacion=status_info['fecha_consulta'],
            es_valido_deduccion=is_valid_for_deduction(status_info['status'])
        )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Error al procesar verificación: {str(e)}")
    finally:
        cursor.close()
        conn.close()


@router.post("/verificar-batch")
async def verificar_batch(
    request: BatchVerificationRequest,
    background_tasks: BackgroundTasks
):
    """
    Verifica múltiples CFDIs en batch

    Este endpoint puede tardar varios minutos dependiendo de la cantidad de CFDIs.
    Se recomienda usar solo_unverified=True para evitar re-verificar.

    Returns:
        Estado del proceso y cantidad de CFDIs a verificar
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        # Construir query para obtener CFDIs a verificar
        where_clause = "WHERE company_id = %s"
        params = [request.company_id]

        if request.only_unverified:
            where_clause += " AND (sat_status IS NULL OR sat_fecha_verificacion IS NULL)"

        query = f"""
            SELECT
                id,
                uuid,
                rfc_emisor,
                rfc_receptor,
                total
            FROM expense_invoices
            {where_clause}
            ORDER BY fecha_emision DESC
            LIMIT %s;
        """

        params.append(request.limit)

        cursor.execute(query, params)
        cfdis = cursor.fetchall()

        if not cfdis:
            return {
                "message": "No hay CFDIs para verificar",
                "total": 0
            }

        # Verificar CFDIs
        verifier = SATCFDIVerifier(use_mock=False)

        verified_count = 0
        errors = []

        for cfdi in cfdis:
            try:
                success, status_info, error = verifier.check_cfdi_status(
                    uuid=cfdi['uuid'],
                    rfc_emisor=cfdi['rfc_emisor'],
                    rfc_receptor=cfdi['rfc_receptor'],
                    total=float(cfdi['total'])
                )

                if success:
                    # Actualizar en BD
                    cursor.execute("""
                        UPDATE expense_invoices
                        SET
                            sat_status = %s,
                            sat_codigo_estatus = %s,
                            sat_es_cancelable = %s,
                            sat_estado = %s,
                            sat_validacion_efos = %s,
                            sat_fecha_verificacion = %s,
                            sat_verificacion_count = COALESCE(sat_verificacion_count, 0) + 1,
                            updated_at = %s
                        WHERE id = %s;
                    """, (
                        status_info['status'],
                        status_info['codigo_estatus'],
                        status_info['es_cancelable'],
                        status_info['estado'],
                        status_info['validacion_efos'],
                        status_info['fecha_consulta'],
                        datetime.utcnow(),
                        cfdi['id']
                    ))

                    verified_count += 1
                else:
                    errors.append({
                        'uuid': cfdi['uuid'],
                        'error': error
                    })

            except Exception as e:
                errors.append({
                    'uuid': cfdi['uuid'],
                    'error': str(e)
                })

        conn.commit()

        return {
            "message": "Verificación completada",
            "total": len(cfdis),
            "verified": verified_count,
            "errors": len(errors),
            "error_details": errors[:10]  # Mostrar solo primeros 10 errores
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Error en verificación batch: {str(e)}")
    finally:
        cursor.close()
        conn.close()


@router.get("/stats", response_model=VerificationStatsResponse)
async def get_verification_stats(company_id: Optional[int] = None):
    """
    Obtiene estadísticas de verificación de CFDIs

    Args:
        company_id: ID de la compañía (opcional, si no se proporciona retorna stats globales)

    Returns:
        Estadísticas de verificación
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT * FROM get_cfdi_verification_stats(%s);",
            (company_id,)
        )

        stats = cursor.fetchone()

        return VerificationStatsResponse(
            total_cfdis=stats['total_cfdis'] or 0,
            vigentes=stats['vigentes'] or 0,
            cancelados=stats['cancelados'] or 0,
            sustituidos=stats['sustituidos'] or 0,
            por_cancelar=stats['por_cancelar'] or 0,
            no_encontrados=stats['no_encontrados'] or 0,
            sin_verificar=stats['sin_verificar'] or 0,
            porcentaje_vigentes=float(stats['porcentaje_vigentes'] or 0)
        )

    finally:
        cursor.close()
        conn.close()


@router.get("/invalidos")
async def get_invalid_cfdis(
    company_id: Optional[int] = None,
    limit: int = 50
):
    """
    Lista CFDIs que no son válidos para deducción fiscal

    Args:
        company_id: Filtrar por compañía
        limit: Máximo de resultados

    Returns:
        Lista de CFDIs cancelados, sustituidos o no encontrados
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                id,
                uuid,
                filename,
                rfc_emisor,
                rfc_receptor,
                total,
                fecha_emision,
                sat_status,
                sat_estado,
                sat_fecha_verificacion,
                tipo_comprobante
            FROM vw_cfdis_invalidos
        """

        params = []

        if company_id:
            query += " WHERE company_id = %s"
            params.append(company_id)

        query += " LIMIT %s;"
        params.append(limit)

        cursor.execute(query, params)
        cfdis = cursor.fetchall()

        return {
            "total": len(cfdis),
            "cfdis": [dict(cfdi) for cfdi in cfdis]
        }

    finally:
        cursor.close()
        conn.close()


@router.get("/sin-verificar")
async def get_unverified_cfdis(
    company_id: Optional[int] = None,
    limit: int = 100
):
    """
    Lista CFDIs que necesitan verificación

    Incluye CFDIs que:
    - Nunca se han verificado
    - Su última verificación tiene más de 30 días

    Args:
        company_id: Filtrar por compañía
        limit: Máximo de resultados

    Returns:
        Lista de CFDIs pendientes de verificar
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                id,
                uuid,
                filename,
                rfc_emisor,
                rfc_receptor,
                total,
                fecha_emision,
                created_at
            FROM vw_cfdis_sin_verificar
        """

        params = []

        if company_id:
            query += " WHERE company_id = %s"
            params.append(company_id)

        query += " LIMIT %s;"
        params.append(limit)

        cursor.execute(query, params)
        cfdis = cursor.fetchall()

        return {
            "total": len(cfdis),
            "cfdis": [dict(cfdi) for cfdi in cfdis]
        }

    finally:
        cursor.close()
        conn.close()


@router.get("/health")
async def health_check():
    """
    Health check del servicio de verificación

    Returns:
        Estado del servicio
    """
    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        # Verificar conexión a BD
        cursor.execute("SELECT 1;")

        # Contar CFDIs sin verificar
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM expense_invoices
            WHERE sat_status IS NULL;
        """)

        unverified = cursor.fetchone()['count']

        return {
            "status": "healthy",
            "mode": "production",  # ✅ Modo producción activado
            "database": "connected",
            "unverified_cfdis": unverified
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

    finally:
        cursor.close()
        conn.close()
