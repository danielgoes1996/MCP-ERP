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
import os
from urllib.parse import urlparse

# Load .env before parsing config
try:
    from dotenv import load_dotenv
    import pathlib
    env_path = pathlib.Path('/app/.env')
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    pass

router = APIRouter(prefix="/sat", tags=["SAT Download"])

@router.get("/test-simple")
async def test_simple():
    """Simple test endpoint"""
    return {
        "status": "ok",
        "message": "SAT test endpoint working",
        "POSTGRES_CONFIG": POSTGRES_CONFIG,
        "CONFIG_ID": id(POSTGRES_CONFIG),
        "DATABASE_URL": os.getenv("DATABASE_URL", "NOT_SET")
    }

# Database configuration from DATABASE_URL or individual env vars
def _parse_db_config():
    """Parse database configuration from DATABASE_URL or individual env vars"""
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Parse DATABASE_URL (format: postgresql://user:password@host:port/database)
        parsed = urlparse(database_url)
        return {
            "host": parsed.hostname or "mcp-postgres",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip('/') or "mcp_system",
            "user": parsed.username or "mcp_user",
            "password": parsed.password or "changeme"
        }
    else:
        # Fallback to Docker defaults for mcp-server
        return {
            "host": os.getenv("POSTGRES_HOST", "mcp-postgres"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "mcp_system"),
            "user": os.getenv("POSTGRES_USER", "mcp_user"),
            "password": os.getenv("POSTGRES_PASSWORD", "changeme")
        }

POSTGRES_CONFIG = _parse_db_config()
print(f"[SAT_API] POSTGRES_CONFIG loaded: host={POSTGRES_CONFIG['host']}, db={POSTGRES_CONFIG['database']}, user={POSTGRES_CONFIG['user']} id={id(POSTGRES_CONFIG)}", flush=True)

def get_db_conn():
    """Get PostgreSQL connection using cached POSTGRES_CONFIG"""
    # Use cached config from module import time
    return psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)


# Request/Response Models
class DownloadInvoicesRequest(BaseModel):
    """Modelo simplificado para descarga automática"""
    company_id: int = Field(..., description="ID de la compañía")
    rfc: str = Field(..., description="RFC de la compañía")
    fecha_inicio: str = Field(..., description="Fecha inicio (YYYY-MM-DD)")
    fecha_fin: str = Field(..., description="Fecha fin (YYYY-MM-DD)")
    tipo: str = Field("recibidas", description="recibidas o emitidas")
    tipo_solicitud: str = Field("CFDI", description="'CFDI' para XMLs completos o 'Metadata' solo metadatos")
    rfc_emisor_filtro: Optional[str] = Field(None, description="Filtrar por RFC emisor específico")
    estado_comprobante: Optional[str] = Field("Vigente", description="'Vigente', 'Cancelado' o null para todos")
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
                    # Para recibidas: rfc_receptor=nosotros, rfc_emisor=filtro opcional
                    # Para emitidas: rfc_emisor=nosotros, rfc_receptor=filtro opcional
                    rfc_emisor_param = None
                    rfc_receptor_param = None

                    if request.tipo == "recibidas":
                        rfc_receptor_param = request.rfc  # Nosotros somos receptores
                        rfc_emisor_param = request.rfc_emisor_filtro  # Filtro opcional por emisor
                    else:
                        rfc_emisor_param = request.rfc  # Nosotros somos emisores

                    success, request_id, error = await sat_service.solicitar_descarga(
                        company_id=request.company_id,
                        fecha_inicial=fecha_inicial,
                        fecha_final=fecha_final,
                        tipo_solicitud=request.tipo_solicitud,
                        rfc_receptor=rfc_receptor_param,
                        rfc_emisor=rfc_emisor_param,
                        estado_comprobante=request.estado_comprobante
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
                import traceback
                import logging
                logging.error(f"SAT REAL ERROR: {type(e).__name__}: {e}")
                logging.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500,
                    detail=f"Error usando credenciales reales: {type(e).__name__}: {str(e)}"
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
def sat_health_check():
    """
    Verifica el estado del servicio SAT (sync version)
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
            "note": "Vault integration required for production mode",
            "config": {
                "host": POSTGRES_CONFIG['host'],
                "database": POSTGRES_CONFIG['database'],
                "user": POSTGRES_CONFIG['user']
            }
        }
    except Exception as e:
        db_url = os.getenv("DATABASE_URL", "NOT_SET")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)} | POSTGRES_CONFIG: host={POSTGRES_CONFIG['host']}, db={POSTGRES_CONFIG['database']} | DATABASE_URL={db_url[:50] if db_url else 'None'}...")


@router.post("/verify/{request_id}")
async def verify_sat_request(request_id: int, use_real_credentials: bool = False):
    """
    Verifica el estado de una solicitud SAT y obtiene el conteo de CFDIs

    Args:
        request_id: ID de la solicitud SAT a verificar
        use_real_credentials: Si True, verifica con SAT real. Si False, usa mock.

    Returns:
        Estado actual de la solicitud, conteo de CFDIs y paquetes disponibles
    """
    try:
        conn = get_db_conn()
        cursor = conn.cursor()

        # Obtener datos de la solicitud
        cursor.execute("""
            SELECT request_id, company_id, rfc, request_uuid, request_status,
                   tipo_solicitud, fecha_inicial, fecha_final,
                   status_code, status_message
            FROM sat_requests
            WHERE request_id = %s;
        """, (request_id,))
        request = cursor.fetchone()

        if not request:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Solicitud {request_id} no encontrada")

        cursor.close()
        conn.close()

        if use_real_credentials:
            # MODO REAL: Verificar con SAT
            try:
                from core.sat.sat_descarga_service import SATDescargaService
                from sqlalchemy.orm import sessionmaker
                from sqlalchemy import create_engine

                engine = create_engine(
                    f"postgresql://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}@"
                    f"{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
                )
                Session = sessionmaker(bind=engine)
                db_session = Session()

                try:
                    sat_service = SATDescargaService(db_session, use_mock=False)
                    success, status_info, error = await sat_service.verificar_solicitud(request_id)

                    if not success:
                        return {
                            "success": False,
                            "mode": "real",
                            "request_id": request_id,
                            "error": error,
                            "current_status": request['request_status']
                        }

                    return {
                        "success": True,
                        "mode": "real",
                        "request_id": request_id,
                        "request_uuid": str(request['request_uuid']),
                        "status": status_info['estado_solicitud'],
                        "numero_cfdis": status_info['numero_cfdis'],
                        "paquetes_disponibles": len(status_info['paquetes']),
                        "paquetes": status_info['paquetes'],
                        "mensaje": status_info.get('mensaje', ''),
                        "period": {
                            "inicio": str(request['fecha_inicial']),
                            "fin": str(request['fecha_final'])
                        }
                    }

                finally:
                    db_session.close()

            except Exception as e:
                import traceback
                import logging
                logging.error(f"SAT VERIFY ERROR: {type(e).__name__}: {e}")
                logging.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500,
                    detail=f"Error verificando con SAT: {type(e).__name__}: {str(e)}"
                )
        else:
            # MODO MOCK: Retornar estado actual de la BD
            return {
                "success": True,
                "mode": "mock",
                "request_id": request_id,
                "request_uuid": str(request['request_uuid']),
                "current_status": request['request_status'],
                "status_code": request['status_code'],
                "status_message": request['status_message'],
                "period": {
                    "inicio": str(request['fecha_inicial']),
                    "fin": str(request['fecha_final'])
                },
                "note": "Use ?use_real_credentials=true para verificar con SAT real"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en verificación: {str(e)}")


@router.post("/download-package/{package_id}")
async def download_and_analyze_package(package_id: int):
    """
    Descarga un paquete del SAT y analiza los XMLs

    Returns:
        Lista de facturas con información de clientes/proveedores
    """
    try:
        conn = get_db_conn()
        cursor = conn.cursor()

        # Obtener info del paquete
        cursor.execute("""
            SELECT p.package_id, p.package_uuid, p.company_id, p.request_id,
                   r.rfc, r.tipo_solicitud
            FROM sat_packages p
            JOIN sat_requests r ON p.request_id = r.request_id
            WHERE p.package_id = %s;
        """, (package_id,))
        package = cursor.fetchone()

        if not package:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Paquete {package_id} no encontrado")

        cursor.close()
        conn.close()

        # Descargar paquete del SAT
        from core.sat.sat_descarga_service import SATDescargaService
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine

        engine = create_engine(
            f"postgresql://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}@"
            f"{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
        )
        Session = sessionmaker(bind=engine)
        db_session = Session()

        try:
            sat_service = SATDescargaService(db_session, use_mock=False)

            # Obtener cliente SAT
            sat_client = sat_service._get_sat_client(package['company_id'])

            # Descargar paquete
            success, zip_bytes, error = sat_client.descargar_paquete(
                rfc_solicitante=package['rfc'],
                package_uuid=package['package_uuid']
            )

            if not success:
                return {
                    "success": False,
                    "error": error,
                    "package_id": package_id
                }

            # Extraer y analizar XMLs
            import zipfile
            import io
            from lxml import etree

            invoices = []
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zip_file:
                for filename in zip_file.namelist():
                    if filename.lower().endswith('.xml'):
                        xml_content = zip_file.read(filename).decode('utf-8')

                        # Parsear CFDI
                        try:
                            root = etree.fromstring(xml_content.encode('utf-8'))

                            # Namespace del CFDI
                            ns = {
                                'cfdi': 'http://www.sat.gob.mx/cfd/4',
                                'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
                            }

                            # Extraer datos principales
                            comprobante = root

                            # Datos del comprobante
                            fecha = comprobante.get('Fecha', '')
                            total = comprobante.get('Total', '0')
                            subtotal = comprobante.get('SubTotal', '0')
                            tipo_comprobante = comprobante.get('TipoDeComprobante', '')
                            moneda = comprobante.get('Moneda', 'MXN')

                            # Emisor
                            emisor = root.find('.//cfdi:Emisor', ns)
                            emisor_rfc = emisor.get('Rfc', '') if emisor is not None else ''
                            emisor_nombre = emisor.get('Nombre', '') if emisor is not None else ''

                            # Receptor
                            receptor = root.find('.//cfdi:Receptor', ns)
                            receptor_rfc = receptor.get('Rfc', '') if receptor is not None else ''
                            receptor_nombre = receptor.get('Nombre', '') if receptor is not None else ''

                            # UUID del timbre
                            tfd = root.find('.//tfd:TimbreFiscalDigital', ns)
                            uuid = tfd.get('UUID', '') if tfd is not None else ''

                            invoices.append({
                                'uuid': uuid,
                                'fecha': fecha,
                                'tipo': tipo_comprobante,
                                'emisor_rfc': emisor_rfc,
                                'emisor_nombre': emisor_nombre,
                                'receptor_rfc': receptor_rfc,
                                'receptor_nombre': receptor_nombre,
                                'subtotal': float(subtotal),
                                'total': float(total),
                                'moneda': moneda
                            })

                        except Exception as parse_error:
                            invoices.append({
                                'filename': filename,
                                'error': str(parse_error)
                            })

            # Agrupar por receptor (cliente)
            clientes = {}
            for inv in invoices:
                if 'receptor_rfc' in inv:
                    rfc = inv['receptor_rfc']
                    if rfc not in clientes:
                        clientes[rfc] = {
                            'rfc': rfc,
                            'nombre': inv['receptor_nombre'],
                            'facturas': 0,
                            'total': 0
                        }
                    clientes[rfc]['facturas'] += 1
                    clientes[rfc]['total'] += inv['total']

            return {
                "success": True,
                "package_id": package_id,
                "total_facturas": len(invoices),
                "clientes": list(clientes.values()),
                "facturas": invoices
            }

        finally:
            db_session.close()

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        import logging
        logging.error(f"DOWNLOAD ERROR: {type(e).__name__}: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error descargando paquete: {type(e).__name__}: {str(e)}")
