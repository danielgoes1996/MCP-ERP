"""
SAT Download Simple API
=======================
Endpoint simplificado para descarga automática de facturas del SAT.
Diseñado para uso en scripts de automatización.

NO usa SQLAlchemy - usa psycopg2 directo para máxima compatibilidad.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter(prefix="/sat", tags=["SAT Download"])

# Database configuration
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


# Request/Response Models
class DownloadInvoicesRequest(BaseModel):
    """Modelo simplificado para descarga automática"""
    company_id: int = Field(..., description="ID de la compañía")
    rfc: str = Field(..., description="RFC de la compañía")
    fecha_inicio: str = Field(..., description="Fecha inicio (YYYY-MM-DD)")
    fecha_fin: str = Field(..., description="Fecha fin (YYYY-MM-DD)")
    tipo: str = Field("recibidas", description="recibidas o emitidas")
    use_real_credentials: bool = Field(False, description="Usar credenciales reales (no mock)")


@router.post("/download-invoices")
async def download_invoices_simplified(request: DownloadInvoicesRequest):
    """
    Endpoint simplificado para descarga automática de facturas

    Soporta dos modos:
    - **MOCK MODE** (default): Retorna datos simulados para testing
    - **REAL MODE**: Usa credenciales reales para descargar del SAT

    Para usar modo real, enviar `use_real_credentials: true` en el request

    Este endpoint ejecuta el flujo completo:
    1. Solicita descarga al SAT
    2. Espera a que los paquetes estén disponibles
    3. Descarga y procesa automáticamente

    Returns:
        {
            "success": true,
            "nuevas": 10,
            "existentes": 5,
            "errores": 0,
            "message": "Descarga completada",
            "mode": "mock" o "real"
        }
    """
    try:
        # Validar fechas
        try:
            fecha_inicial = datetime.strptime(request.fecha_inicio, '%Y-%m-%d')
            fecha_final = datetime.strptime(request.fecha_fin, '%Y-%m-%d')
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Formato de fecha inválido: {e}")

        # Validar compañía existe
        conn = get_db_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, rfc FROM companies WHERE id = %s AND status = 'active';",
            (request.company_id,)
        )
        company = cursor.fetchone()

        if not company:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Compañía {request.company_id} no encontrada o inactiva")

        # Verificar que tiene credenciales SAT
        cursor.execute(
            "SELECT is_active FROM sat_efirma_credentials WHERE company_id = %s AND is_active = true;",
            (request.company_id,)
        )
        credentials = cursor.fetchone()

        if not credentials:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"La compañía {request.company_id} no tiene credenciales SAT activas"
            )

        cursor.close()
        conn.close()

        # Determinar modo de operación
        if request.use_real_credentials:
            # MODO REAL: Usar SATDescargaService con credenciales reales
            try:
                from core.sat.sat_descarga_service import SATDescargaService
                from sqlalchemy.orm import sessionmaker
                from sqlalchemy import create_engine

                # Crear sesión SQLAlchemy temporal para el servicio
                engine = create_engine(
                    f"postgresql://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}@"
                    f"{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
                )
                Session = sessionmaker(bind=engine)
                db_session = Session()

                try:
                    # Crear servicio con credenciales REALES
                    sat_service = SATDescargaService(db_session, use_mock=False)

                    # Ejecutar descarga real
                    success, request_id, error = await sat_service.solicitar_descarga(
                        company_id=request.company_id,
                        fecha_inicial=fecha_inicial,
                        fecha_final=fecha_final,
                        rfc_receptor=request.rfc if request.tipo == "recibidas" else None,
                        rfc_emisor=request.rfc if request.tipo == "emitidas" else None
                    )

                    if not success:
                        raise HTTPException(status_code=500, detail=f"Error en SAT: {error}")

                    return {
                        "success": True,
                        "mode": "real",
                        "message": "Solicitud enviada al SAT exitosamente",
                        "sat_request_id": request_id,
                        "company": {
                            "id": company['id'],
                            "name": company['name'],
                            "rfc": company['rfc']
                        },
                        "period": {
                            "inicio": request.fecha_inicio,
                            "fin": request.fecha_fin
                        },
                        "tipo": request.tipo,
                        "note": "La descarga se procesará en background. Usar /sat/status/{request_id} para verificar estado"
                    }

                finally:
                    db_session.close()

            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error usando credenciales reales: {str(e)}"
                )
        else:
            # MODO MOCK: Retornar datos simulados
            import random
            mock_nuevas = random.randint(0, 15)
            mock_existentes = random.randint(0, 5)

            return {
                "success": True,
                "mode": "mock",
                "nuevas": mock_nuevas,
                "existentes": mock_existentes,
                "errores": 0,
                "message": f"Descarga completada (MOCK MODE) - {mock_nuevas} nuevas facturas simuladas",
                "company": {
                    "id": company['id'],
                    "name": company['name'],
                    "rfc": company['rfc']
                },
                "period": {
                    "inicio": request.fecha_inicio,
                    "fin": request.fecha_fin
                },
                "tipo": request.tipo
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en descarga: {str(e)}")


@router.get("/health")
async def sat_health_check():
    """
    Verifica el estado del servicio SAT
    """
    try:
        conn = get_db_conn()
        cursor = conn.cursor()

        # Contar credenciales activas
        cursor.execute("SELECT COUNT(*) as count FROM sat_efirma_credentials WHERE is_active = true;")
        active_credentials = cursor.fetchone()['count']

        cursor.close()
        conn.close()

        return {
            "status": "healthy",
            "mode": "mock",
            "message": "SAT download service is running in MOCK mode",
            "active_credentials": active_credentials,
            "note": "Vault integration required for production mode"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
