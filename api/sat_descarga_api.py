"""
SAT Descarga Masiva API Endpoints
==================================
Endpoints FastAPI para descarga masiva de CFDIs desde SAT

Endpoints:
- POST /sat/solicitar-descarga: Crear solicitud de descarga
- GET /sat/solicitudes: Listar solicitudes
- GET /sat/solicitudes/{id}: Obtener detalles de solicitud
- POST /sat/solicitudes/{id}/verificar: Verificar estado
- GET /sat/paquetes: Listar paquetes disponibles
- POST /sat/paquetes/{id}/descargar: Descargar y procesar paquete
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor

# Local imports
from core.sat.sat_descarga_service import SATDescargaService


# ========================================
# Router Setup
# ========================================

router = APIRouter(prefix="/sat", tags=["SAT Descarga Masiva"])


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
# Request Models
# ========================================

class SolicitarDescargaRequest(BaseModel):
    """Modelo para solicitar descarga masiva"""
    company_id: int = Field(..., description="ID de la compañía")
    fecha_inicial: date = Field(..., description="Fecha inicial (YYYY-MM-DD)")
    fecha_final: date = Field(..., description="Fecha final (YYYY-MM-DD)")
    tipo_solicitud: str = Field("CFDI", description="CFDI o Metadata")
    rfc_emisor: Optional[str] = Field(None, description="Filtrar por RFC emisor")
    rfc_receptor: Optional[str] = Field(None, description="Filtrar por RFC receptor")
    tipo_comprobante: Optional[str] = Field(None, description="Filtrar por tipo (I, E, P, N, T)")

    class Config:
        json_schema_extra = {
            "example": {
                "company_id": 2,
                "fecha_inicial": "2025-01-01",
                "fecha_final": "2025-01-31",
                "tipo_solicitud": "CFDI",
                "rfc_receptor": "POL210218264",
                "tipo_comprobante": "I"
            }
        }


class VerificarSolicitudResponse(BaseModel):
    """Respuesta al verificar solicitud"""
    request_id: int
    estado_solicitud: int
    numero_cfdis: int
    paquetes_disponibles: int
    mensaje: str


class DescargarPaqueteResponse(BaseModel):
    """Respuesta al descargar paquete"""
    package_id: int
    xml_count: int
    inserted: int
    duplicates: int
    errors: int


# ========================================
# Endpoints
# ========================================

@router.post("/solicitar-descarga")
async def solicitar_descarga(
    request: SolicitarDescargaRequest,
    db: Session = Depends(get_db)
):
    """
    Solicita descarga masiva de CFDIs al SAT

    Este endpoint:
    1. Valida las credenciales e.firma de la compañía
    2. Envía solicitud al servicio SAT
    3. Registra la solicitud en la BD
    4. Genera evidencia NOM-151

    Returns:
        {
            "success": true,
            "request_id": 1,
            "request_uuid": "123e4567-e89b-12d3-a456-426614174000",
            "message": "Solicitud creada exitosamente. Use /sat/solicitudes/{id}/verificar para ver el progreso."
        }
    """
    # Convertir dates a datetime
    fecha_inicial_dt = datetime.combine(request.fecha_inicial, datetime.min.time())
    fecha_final_dt = datetime.combine(request.fecha_final, datetime.max.time())

    # Validaciones
    if fecha_final_dt < fecha_inicial_dt:
        raise HTTPException(400, "fecha_final debe ser mayor o igual a fecha_inicial")

    if (fecha_final_dt - fecha_inicial_dt).days > 31:
        raise HTTPException(400, "El rango máximo de fechas es 31 días")

    # Usar servicio SAT (modo mock por ahora)
    service = SATDescargaService(db, use_mock=False)

    success, request_id, error = await service.solicitar_descarga(
        company_id=request.company_id,
        fecha_inicial=fecha_inicial_dt,
        fecha_final=fecha_final_dt,
        tipo_solicitud=request.tipo_solicitud,
        rfc_emisor=request.rfc_emisor,
        rfc_receptor=request.rfc_receptor,
        tipo_comprobante=request.tipo_comprobante,
        user_id=None  # TODO: Get from JWT
    )

    if not success:
        raise HTTPException(500, f"Error al solicitar descarga: {error}")

    # Obtener UUID de la solicitud
    result = db.execute(
        text("SELECT request_uuid FROM sat_requests WHERE request_id = :request_id;"),
        {'request_id': request_id}
    )
    request_uuid = result.fetchone()['request_uuid']

    return {
        "success": True,
        "request_id": request_id,
        "request_uuid": request_uuid,
        "message": f"Solicitud creada. Use GET /sat/solicitudes/{request_id} para ver detalles."
    }


@router.get("/solicitudes")
async def listar_solicitudes(
    company_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Lista solicitudes de descarga SAT

    Query params:
    - company_id: Filtrar por compañía
    - status: Filtrar por estado (pending, processing, completed, failed)
    - limit: Límite de resultados (default: 50)

    Returns:
        Lista de solicitudes con su estado actual
    """
    # Construir query dinámico
    where_clauses = []
    params = {'limit': limit}

    if company_id:
        where_clauses.append("company_id = :company_id")
        params['company_id'] = company_id

    if status:
        where_clauses.append("request_status = :status")
        params['status'] = status

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query = f"""
        SELECT
            request_id,
            company_id,
            rfc,
            tipo_solicitud,
            fecha_inicial,
            fecha_final,
            request_uuid,
            request_status,
            status_message,
            requested_at,
            completed_at,
            (SELECT COUNT(*) FROM sat_packages WHERE request_id = sat_requests.request_id) as paquetes_count
        FROM sat_requests
        {where_sql}
        ORDER BY requested_at DESC
        LIMIT :limit;
    """

    result = db.execute(text(query), params)
    solicitudes = result.fetchall()

    return {
        "total": len(solicitudes),
        "solicitudes": [dict(row) for row in solicitudes]
    }


@router.get("/solicitudes/{request_id}")
async def obtener_solicitud(
    request_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene detalles de una solicitud SAT

    Returns:
        Detalles completos de la solicitud incluyendo paquetes
    """
    # Obtener solicitud
    result = db.execute(
        text("""
            SELECT
                request_id,
                company_id,
                rfc,
                tipo_solicitud,
                fecha_inicial,
                fecha_final,
                rfc_emisor,
                rfc_receptor,
                tipo_comprobante,
                request_uuid,
                request_status,
                status_code,
                status_message,
                requested_at,
                completed_at,
                expires_at
            FROM sat_requests
            WHERE request_id = :request_id;
        """),
        {'request_id': request_id}
    )

    solicitud = result.fetchone()

    if not solicitud:
        raise HTTPException(404, "Solicitud no encontrada")

    # Obtener paquetes asociados
    paquetes_result = db.execute(
        text("""
            SELECT
                package_id,
                package_uuid,
                xml_count,
                download_status,
                processing_status,
                downloaded_at,
                processed_at
            FROM sat_packages
            WHERE request_id = :request_id
            ORDER BY package_id;
        """),
        {'request_id': request_id}
    )

    paquetes = paquetes_result.fetchall()

    return {
        "solicitud": dict(solicitud),
        "paquetes": [dict(p) for p in paquetes]
    }


@router.post("/solicitudes/{request_id}/verificar")
async def verificar_solicitud(
    request_id: int,
    db: Session = Depends(get_db)
):
    """
    Verifica el estado de una solicitud en el SAT

    Este endpoint:
    1. Consulta el SAT para obtener el estado actual
    2. Actualiza la BD con el nuevo estado
    3. Si hay paquetes disponibles, los registra

    Returns:
        Estado actualizado de la solicitud
    """
    service = SATDescargaService(db, use_mock=False)

    success, status_info, error = await service.verificar_solicitud(
        request_id=request_id,
        user_id=None  # TODO: Get from JWT
    )

    if not success:
        raise HTTPException(500, f"Error al verificar solicitud: {error}")

    return {
        "success": True,
        "request_id": request_id,
        "estado_solicitud": status_info['estado_solicitud'],
        "numero_cfdis": status_info['numero_cfdis'],
        "paquetes_disponibles": len(status_info['paquetes']),
        "mensaje": status_info['mensaje']
    }


@router.get("/paquetes")
async def listar_paquetes(
    company_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Lista paquetes SAT disponibles para descargar

    Query params:
    - company_id: Filtrar por compañía
    - status: Filtrar por estado de descarga
    - limit: Límite de resultados

    Returns:
        Lista de paquetes con su estado
    """
    where_clauses = []
    params = {'limit': limit}

    if company_id:
        where_clauses.append("p.company_id = :company_id")
        params['company_id'] = company_id

    if status:
        where_clauses.append("p.download_status = :status")
        params['status'] = status

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query = f"""
        SELECT
            p.package_id,
            p.package_uuid,
            p.request_id,
            p.company_id,
            p.xml_count,
            p.download_status,
            p.processing_status,
            p.available_at,
            p.downloaded_at,
            p.processed_at,
            r.tipo_solicitud,
            r.fecha_inicial,
            r.fecha_final
        FROM sat_packages p
        JOIN sat_requests r ON p.request_id = r.request_id
        {where_sql}
        ORDER BY p.available_at DESC
        LIMIT :limit;
    """

    result = db.execute(text(query), params)
    paquetes = result.fetchall()

    return {
        "total": len(paquetes),
        "paquetes": [dict(row) for row in paquetes]
    }


@router.post("/paquetes/{package_id}/descargar")
async def descargar_paquete(
    package_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Descarga y procesa un paquete SAT

    Este endpoint:
    1. Descarga el ZIP del SAT
    2. Extrae los XMLs
    3. Procesa cada CFDI con BulkInvoiceProcessor
    4. Genera evidencia NOM-151

    NOTA: Este proceso puede tardar varios minutos para paquetes grandes.
    Se ejecuta de forma sincrónica por ahora. En el futuro se implementará
    con Celery para ejecución asíncrona.

    Returns:
        Resultado del procesamiento
    """
    service = SATDescargaService(db, use_mock=False)

    success, result, error = await service.descargar_y_procesar_paquete(
        package_id=package_id,
        user_id=None  # TODO: Get from JWT
    )

    if not success:
        raise HTTPException(500, f"Error al descargar paquete: {error}")

    return {
        "success": True,
        "package_id": package_id,
        "xml_count": result['inserted'] + result['duplicates'],
        "inserted": result['inserted'],
        "duplicates": result['duplicates'],
        "errors": result['errors']
    }


@router.get("/logs")
async def obtener_logs(
    company_id: Optional[int] = None,
    operation: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Obtiene logs de operaciones SAT

    Query params:
    - company_id: Filtrar por compañía
    - operation: Filtrar por operación (solicitar, verificar, descargar, procesar)
    - limit: Límite de resultados

    Returns:
        Lista de logs de auditoría
    """
    where_clauses = []
    params = {'limit': limit}

    if company_id:
        where_clauses.append("company_id = :company_id")
        params['company_id'] = company_id

    if operation:
        where_clauses.append("operation = :operation")
        params['operation'] = operation

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query = f"""
        SELECT
            log_id,
            company_id,
            request_id,
            operation,
            status,
            message,
            error_code,
            created_at
        FROM sat_download_logs
        {where_sql}
        ORDER BY created_at DESC
        LIMIT :limit;
    """

    result = db.execute(text(query), params)
    logs = result.fetchall()

    return {
        "total": len(logs),
        "logs": [dict(row) for row in logs]
    }


# ========================================
# Endpoint Simplificado para Scripts
# ========================================

class DownloadInvoicesRequest(BaseModel):
    """Modelo simplificado para descarga automática"""
    company_id: int = Field(..., description="ID de la compañía")
    rfc: str = Field(..., description="RFC de la compañía")
    fecha_inicio: str = Field(..., description="Fecha inicio (YYYY-MM-DD)")
    fecha_fin: str = Field(..., description="Fecha fin (YYYY-MM-DD)")
    tipo: str = Field("recibidas", description="recibidas o emitidas")


@router.post("/download-invoices")
async def download_invoices_simplified(
    request: DownloadInvoicesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Endpoint simplificado para descarga automática de facturas

    Este endpoint integra el flujo completo:
    1. Solicita descarga al SAT
    2. Espera a que los paquetes estén disponibles
    3. Descarga y procesa automáticamente

    Diseñado para uso en scripts automatizados.

    Returns:
        {
            "success": true,
            "nuevas": 10,
            "existentes": 5,
            "errores": 0
        }
    """
    try:
        # Convertir fechas
        fecha_inicial_dt = datetime.strptime(request.fecha_inicio, '%Y-%m-%d')
        fecha_final_dt = datetime.strptime(request.fecha_fin, '%Y-%m-%d')

        # Determinar RFC receptor según tipo
        rfc_receptor = request.rfc if request.tipo == "recibidas" else None
        rfc_emisor = request.rfc if request.tipo == "emitidas" else None

        # Paso 1: Solicitar descarga
        # TODO: Cambiar a use_mock=False cuando Vault esté configurado
        service = SATDescargaService(db, use_mock=True)

        success, request_id, error = await service.solicitar_descarga(
            company_id=request.company_id,
            fecha_inicial=fecha_inicial_dt,
            fecha_final=fecha_final_dt,
            tipo_solicitud="CFDI",
            rfc_emisor=rfc_emisor,
            rfc_receptor=rfc_receptor,
            tipo_comprobante="I",  # Solo facturas de ingreso
            user_id=None
        )

        if not success:
            return {
                "success": False,
                "nuevas": 0,
                "existentes": 0,
                "errores": 1,
                "error": error
            }

        # Paso 2: Verificar inmediatamente (en mock siempre está listo)
        import asyncio
        await asyncio.sleep(2)  # Pequeña espera

        success, status_info, error = await service.verificar_solicitud(
            request_id=request_id,
            user_id=None
        )

        if not success or len(status_info.get('paquetes', [])) == 0:
            return {
                "success": True,
                "nuevas": 0,
                "existentes": 0,
                "errores": 0,
                "message": "No hay paquetes disponibles aún. Intente más tarde."
            }

        # Paso 3: Descargar todos los paquetes
        total_nuevas = 0
        total_existentes = 0
        total_errores = 0

        for paquete_uuid in status_info['paquetes']:
            # Obtener package_id
            pkg_result = db.execute(
                text("SELECT package_id FROM sat_packages WHERE package_uuid = :uuid;"),
                {'uuid': paquete_uuid}
            )
            pkg_row = pkg_result.fetchone()

            if not pkg_row:
                continue

            package_id = pkg_row['package_id']

            # Descargar y procesar
            success, result, error = await service.descargar_y_procesar_paquete(
                package_id=package_id,
                user_id=None
            )

            if success:
                total_nuevas += result.get('inserted', 0)
                total_existentes += result.get('duplicates', 0)
                total_errores += result.get('errors', 0)

        return {
            "success": True,
            "nuevas": total_nuevas,
            "existentes": total_existentes,
            "errores": total_errores
        }

    except Exception as e:
        return {
            "success": False,
            "nuevas": 0,
            "existentes": 0,
            "errores": 1,
            "error": str(e)
        }


# ========================================
# Health Check
# ========================================

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Verifica el estado del servicio SAT

    Returns:
        Estado de tablas y configuración
    """
    # Contar credenciales activas
    cred_result = db.execute(
        text("SELECT COUNT(*) as count FROM sat_efirma_credentials WHERE is_active = true;")
    )
    active_credentials = cred_result.fetchone()['count']

    # Contar solicitudes pendientes
    pending_result = db.execute(
        text("SELECT COUNT(*) as count FROM sat_requests WHERE request_status = 'pending';")
    )
    pending_requests = pending_result.fetchone()['count']

    # Contar paquetes pendientes
    packages_result = db.execute(
        text("SELECT COUNT(*) as count FROM sat_packages WHERE download_status = 'pending';")
    )
    pending_packages = packages_result.fetchone()['count']

    return {
        "status": "healthy",
        "mode": "mock",  # Cambiar a "production" cuando se integre Vault
        "active_credentials": active_credentials,
        "pending_requests": pending_requests,
        "pending_packages": pending_packages
    }
