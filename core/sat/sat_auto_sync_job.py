"""
SAT Auto Sync Job
=================
Job de sincronización automática con el SAT que descarga facturas
y las alimenta al flujo de clasificación existente.

Este job se ejecuta periódicamente (configurable por compañía) y:
1. Descarga facturas del SAT (últimos N días)
2. Las envía al universal_invoice_engine (flujo existente)
3. Activa clasificación automática con IA
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import tempfile
import zipfile
import io

from sqlalchemy import text
from core.sat.sat_descarga_service import SATDescargaService
from core.database import get_db_session

logger = logging.getLogger(__name__)


class SATAutoSyncJob:
    """Job de sincronización automática con SAT"""

    def __init__(self):
        self.sat_service = None

    async def run_for_company(self, company_id: int) -> Tuple[bool, int, Optional[str]]:
        """
        Ejecuta sincronización SAT para una compañía

        Returns:
            (success, num_facturas, error_message)
        """
        logger.info(f"[SAT_AUTO_SYNC] Iniciando sync para company_id={company_id}")

        try:
            with get_db_session() as db:
                # 1. Obtener configuración de la compañía
                config = self._get_company_config(db, company_id)

                if not config or not config['enabled']:
                    logger.info(f"[SAT_AUTO_SYNC] Sync desactivado para company_id={company_id}")
                    return True, 0, "Sync desactivado"

                # 2. Calcular ventana de fechas
                fecha_fin = datetime.now()
                fecha_inicio = fecha_fin - timedelta(days=config['lookback_days'])

                logger.info(f"[SAT_AUTO_SYNC] Descargando desde {fecha_inicio.date()} hasta {fecha_fin.date()}")

                # 3. Solicitar descarga al SAT
                self.sat_service = SATDescargaService(db)

                success, request_id, error = await self.sat_service.solicitar_descarga(
                    company_id=company_id,
                    fecha_inicial=fecha_inicio,
                    fecha_final=fecha_fin,
                    tipo_solicitud="CFDI",
                    estado_comprobante="Vigente"
                )

                if not success:
                    self._update_sync_status(db, company_id, 'error', 0, error)
                    return False, 0, error

                # 4. Esperar y verificar solicitud
                max_retries = 20
                retry_delay = 30  # segundos

                for i in range(max_retries):
                    logger.info(f"[SAT_AUTO_SYNC] Verificando solicitud {request_id} (intento {i+1}/{max_retries})")

                    await asyncio.sleep(retry_delay)

                    success, status_info, error = await self.sat_service.verificar_solicitud(request_id)

                    if not success:
                        continue

                    estado = status_info.get('estado_solicitud', 0)

                    # Estado 3 = Terminada
                    if estado == 3:
                        paquetes = status_info.get('paquetes', [])
                        num_cfdis = status_info.get('numero_cfdis', 0)

                        logger.info(f"[SAT_AUTO_SYNC] Solicitud terminada: {num_cfdis} CFDIs en {len(paquetes)} paquetes")

                        # 5. Descargar y procesar paquetes
                        total_procesadas = 0

                        for paquete_id in paquetes:
                            facturas_procesadas = await self._process_package(
                                db, company_id, request_id, paquete_id
                            )
                            total_procesadas += facturas_procesadas

                        # 6. Actualizar estado
                        self._update_sync_status(db, company_id, 'success', total_procesadas, None)

                        logger.info(f"[SAT_AUTO_SYNC] ✅ Sync completado: {total_procesadas} facturas procesadas")
                        return True, total_procesadas, None

                    # Estado 4 = Error, Estado 5 = Rechazada
                    elif estado in [4, 5]:
                        mensaje = status_info.get('mensaje', 'Error desconocido')
                        self._update_sync_status(db, company_id, 'error', 0, mensaje)
                        return False, 0, mensaje

                # Timeout
                error_msg = "Timeout esperando respuesta del SAT"
                self._update_sync_status(db, company_id, 'error', 0, error_msg)
                return False, 0, error_msg

        except Exception as e:
            logger.error(f"[SAT_AUTO_SYNC] Error en sync: {e}", exc_info=True)
            try:
                with get_db_session() as db:
                    self._update_sync_status(db, company_id, 'error', 0, str(e))
            except:
                pass
            return False, 0, str(e)

    async def _process_package(
        self,
        db,
        company_id: int,
        request_id: int,
        package_uuid: str
    ) -> int:
        """
        Descarga y procesa un paquete de facturas

        Returns:
            Número de facturas procesadas
        """
        logger.info(f"[SAT_AUTO_SYNC] Procesando paquete {package_uuid}")

        try:
            # 1. Obtener RFC de la compañía
            cursor = db.execute(text("""
                SELECT rfc
                FROM sat_efirma_credentials
                WHERE company_id = :company_id AND is_active = true
                LIMIT 1
            """), {"company_id": company_id})

            row = cursor.fetchone()
            if not row:
                logger.error(f"[SAT_AUTO_SYNC] No se encontró RFC para company_id={company_id}")
                return 0

            rfc = row[0]

            # 2. Descargar paquete del SAT
            success, zip_bytes, error = self.sat_service.descargar_paquete(company_id, rfc, package_uuid)

            if not success:
                logger.error(f"[SAT_AUTO_SYNC] Error descargando paquete: {error}")
                return 0

            # 2. Extraer XMLs del ZIP
            xmls = self._extract_xmls_from_zip(zip_bytes)
            logger.info(f"[SAT_AUTO_SYNC] Extraídos {len(xmls)} XMLs del paquete")

            # 3. Enviar cada XML al universal_invoice_engine
            processed_count = 0

            for xml_filename, xml_content in xmls:
                try:
                    success = await self._send_to_invoice_engine(
                        db, company_id, xml_filename, xml_content
                    )

                    if success:
                        processed_count += 1

                except Exception as e:
                    logger.error(f"[SAT_AUTO_SYNC] Error procesando {xml_filename}: {e}")
                    continue

            return processed_count

        except Exception as e:
            logger.error(f"[SAT_AUTO_SYNC] Error procesando paquete: {e}", exc_info=True)
            return 0

    def _extract_xmls_from_zip(self, zip_bytes: bytes) -> List[Tuple[str, bytes]]:
        """Extrae archivos XML de un ZIP"""
        xmls = []

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for filename in zf.namelist():
                    if filename.lower().endswith('.xml'):
                        xml_content = zf.read(filename)
                        xmls.append((filename, xml_content))
        except Exception as e:
            logger.error(f"[SAT_AUTO_SYNC] Error extrayendo XMLs: {e}")

        return xmls

    async def _send_to_invoice_engine(
        self,
        db,
        company_id: int,
        filename: str,
        xml_content: bytes
    ) -> bool:
        """
        Guarda factura descargada del SAT en sat_invoices

        Marca origen como 'sat_auto_sync' para diferenciar de facturas manuales.
        """
        import os
        import hashlib
        import uuid as uuid_lib

        try:
            # 1. Generar session ID (como 'uis_...')
            session_id = f"uis_{uuid_lib.uuid4().hex}"

            # 2. Guardar XML en filesystem
            company_dir = f"uploads/invoices/company_{company_id}/sat_auto_sync"
            os.makedirs(company_dir, exist_ok=True)

            file_path = os.path.join(company_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(xml_content)

            # 3. Calcular hash del archivo
            file_hash = hashlib.sha256(xml_content).hexdigest()

            # 4. Insertar en sat_invoices (usando el formato PostgreSQL)
            db.execute(text("""
                INSERT INTO sat_invoices (
                    id, company_id, user_id, invoice_file_path, original_filename,
                    file_hash, source, status, created_at
                ) VALUES (:id, :company_id, :user_id, :file_path, :filename,
                         :file_hash, :source, :status, :created_at)
            """), {
                "id": session_id,
                "company_id": str(company_id),
                "user_id": None,  # Auto-sync, no user
                "file_path": file_path,
                "filename": filename,
                "file_hash": file_hash,
                "source": 'sat_auto_sync',  # ← Marca origen
                "status": 'pending',  # ← Pendiente de procesamiento
                "created_at": datetime.utcnow()
            })

            db.commit()

            logger.info(f"[SAT_AUTO_SYNC] ✅ Factura guardada: {session_id} ({filename})")
            return True

        except Exception as e:
            logger.error(f"[SAT_AUTO_SYNC] Error guardando factura: {e}", exc_info=True)
            return False

    def _get_company_config(self, db, company_id: int) -> Optional[Dict]:
        """Obtiene configuración de sync para una compañía"""
        try:
            cursor = db.execute(text("""
                SELECT enabled, lookback_days, auto_classify, notify_email, notify_threshold
                FROM sat_sync_config
                WHERE company_id = :company_id
            """), {"company_id": company_id})

            row = cursor.fetchone()

            if not row:
                return None

            return {
                'enabled': bool(row[0]),
                'lookback_days': row[1] or 10,
                'auto_classify': bool(row[2]),
                'notify_email': bool(row[3]),
                'notify_threshold': row[4] or 5
            }
        except Exception as e:
            logger.error(f"[SAT_AUTO_SYNC] Error obteniendo config: {e}")
            return None

    def _update_sync_status(
        self,
        db,
        company_id: int,
        status: str,
        count: int,
        error: Optional[str]
    ):
        """Actualiza estado de la última sincronización"""
        try:
            db.execute(text("""
                UPDATE sat_sync_config
                SET last_sync_at = :last_sync_at,
                    last_sync_status = :last_sync_status,
                    last_sync_count = :last_sync_count,
                    last_sync_error = :last_sync_error,
                    updated_at = :updated_at
                WHERE company_id = :company_id
            """), {
                "last_sync_at": datetime.utcnow(),
                "last_sync_status": status,
                "last_sync_count": count,
                "last_sync_error": error,
                "updated_at": datetime.utcnow(),
                "company_id": company_id
            })

            db.commit()
        except Exception as e:
            logger.error(f"[SAT_AUTO_SYNC] Error actualizando estado: {e}")


# Función de utilidad para ejecutar el job manualmente
async def run_sync_for_company(company_id: int) -> Tuple[bool, int, Optional[str]]:
    """
    Ejecuta sincronización para una compañía (útil para testing o ejecución manual)

    Example:
        success, count, error = await run_sync_for_company(company_id=2)
    """
    job = SATAutoSyncJob()
    return await job.run_for_company(company_id)


if __name__ == "__main__":
    # Test manual
    import sys

    if len(sys.argv) < 2:
        print("Uso: python sat_auto_sync_job.py <company_id>")
        sys.exit(1)

    company_id = int(sys.argv[1])

    success, count, error = asyncio.run(run_sync_for_company(company_id))

    if success:
        print(f"✅ Sync completado: {count} facturas procesadas")
    else:
        print(f"❌ Error en sync: {error}")
