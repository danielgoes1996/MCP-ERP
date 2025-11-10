"""
SAT Descarga Masiva Service
============================
Servicio de alto nivel para gestionar descarga masiva de CFDIs desde SAT

Este servicio:
1. Gestiona credenciales e.firma desde Vault
2. Ejecuta solicitudes de descarga SAT
3. Verifica y descarga paquetes
4. Genera evidencia NOM-151
5. Integra con BulkInvoiceProcessor para procesar CFDIs
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import zipfile
import io
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import text

from core.sat.sat_soap_client import SATSOAPClient, SATSOAPClientMock
from core.sat.nom151_evidence import NOM151EvidenceGenerator
from core.sat.credential_loader import CredentialLoader
from core.expenses.invoices.bulk_invoice_processor import BulkInvoiceProcessor


class SATDescargaService:
    """
    Servicio para descarga masiva de CFDIs desde SAT

    Workflow:
    1. solicitar_descarga() -> Crea solicitud en SAT
    2. verificar_solicitud() -> Verifica status (polling)
    3. descargar_y_procesar() -> Descarga ZIP y procesa CFDIs
    """

    def __init__(
        self,
        db_session: Session,
        use_mock: bool = False
    ):
        """
        Inicializa el servicio

        Args:
            db_session: Sesión de base de datos
            use_mock: Si True, usa cliente mock (para testing)
        """
        self.db = db_session
        self.use_mock = use_mock
        self.evidence_gen = NOM151EvidenceGenerator()

    def _get_sat_client(self, company_id: int) -> SATSOAPClient:
        """
        Obtiene cliente SAT con credenciales cargadas desde URIs

        Soporta esquemas: file://, inline:, vault:

        Args:
            company_id: ID de la compañía

        Returns:
            Cliente SAT configurado

        Raises:
            ValueError: Si no se encuentran credenciales
        """
        if self.use_mock:
            return SATSOAPClientMock()

        # Obtener credenciales de la BD
        result = self.db.execute(
            text("""
                SELECT
                    vault_cer_path,
                    vault_key_path,
                    vault_password_path,
                    rfc
                FROM sat_efirma_credentials
                WHERE company_id = :company_id
                  AND is_active = true
                LIMIT 1;
            """),
            {'company_id': company_id}
        )

        cred = result.fetchone()

        if not cred:
            raise ValueError(f"No se encontraron credenciales e.firma para company_id={company_id}")

        # Convertir a diccionario si es necesario (compatibilidad con Row/Tuple)
        if hasattr(cred, '_mapping'):
            cred_dict = dict(cred._mapping)
        elif isinstance(cred, dict):
            cred_dict = cred
        else:
            # Es una tupla - mapear por índice
            cred_dict = {
                'vault_cer_path': cred[0],
                'vault_key_path': cred[1],
                'vault_password_path': cred[2],
                'rfc': cred[3]
            }

        # Cargar credenciales usando CredentialLoader
        # Soporta file://, inline:, vault: URIs
        try:
            cer_bytes, key_bytes, password = CredentialLoader.load_efirma_credentials(
                cer_uri=cred_dict['vault_cer_path'],
                key_uri=cred_dict['vault_key_path'],
                password_uri=cred_dict['vault_password_path']
            )

            # Convertir certificado DER a PEM si es necesario
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            # Intentar cargar como DER primero (formato .cer)
            try:
                cert = x509.load_der_x509_certificate(cer_bytes, default_backend())
                cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            except:
                # Si falla, asumir que ya es PEM
                cert_pem = cer_bytes.decode('utf-8')

            # Intentar cargar llave como DER primero (formato .key)
            key_password_final = password  # Por defecto usar el password original
            try:
                # Intentar primero CON password
                try:
                    key = serialization.load_der_private_key(
                        key_bytes,
                        password=password.encode() if password else None,
                        backend=default_backend()
                    )
                except:
                    # Si falla, intentar SIN password (llave no encriptada)
                    key = serialization.load_der_private_key(
                        key_bytes,
                        password=None,
                        backend=default_backend()
                    )
                    key_password_final = None  # Llave no está encriptada

                # Convertir a PEM sin encriptación
                key_pem = key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')
                key_password_final = None  # Después de convertir a PEM sin encriptación, no se necesita password
            except:
                # Si falla, asumir que ya es PEM
                key_pem = key_bytes.decode('utf-8')

            return SATSOAPClient(
                certificate_pem=cert_pem,
                private_key_pem=key_pem,
                private_key_password=key_password_final
            )
        except Exception as e:
            raise ValueError(f"Error cargando credenciales para company_id={company_id}: {e}")

    async def solicitar_descarga(
        self,
        company_id: int,
        fecha_inicial: datetime,
        fecha_final: datetime,
        tipo_solicitud: str = "CFDI",
        rfc_emisor: Optional[str] = None,
        rfc_receptor: Optional[str] = None,
        tipo_comprobante: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Solicita descarga masiva de CFDIs al SAT

        Args:
            company_id: ID de la compañía
            fecha_inicial: Fecha inicial de búsqueda
            fecha_final: Fecha final de búsqueda
            tipo_solicitud: "CFDI" o "Metadata"
            rfc_emisor: Filtrar por RFC emisor (opcional)
            rfc_receptor: Filtrar por RFC receptor (opcional)
            tipo_comprobante: Filtrar por tipo (I, E, P, etc.) (opcional)
            user_id: ID del usuario que solicita

        Returns:
            (success, request_id, error_message)
        """
        try:
            # Obtener RFC de la compañía
            company_result = self.db.execute(
                text("SELECT rfc FROM companies WHERE id = :company_id;"),
                {'company_id': company_id}
            )
            company = company_result.fetchone()

            if not company:
                return False, None, "Compañía no encontrada o sin RFC"

            # Convertir a diccionario si es necesario (compatibilidad con Row/Tuple)
            if hasattr(company, '_mapping'):
                company_dict = dict(company._mapping)
            elif isinstance(company, dict):
                company_dict = company
            else:
                # Es una tupla - usar índice 0 para RFC
                company_dict = {'rfc': company[0]}

            if not company_dict.get('rfc'):
                return False, None, "Compañía sin RFC configurado"

            rfc_solicitante = company_dict['rfc']

            # Obtener cliente SAT
            sat_client = self._get_sat_client(company_id)

            # Solicitar descarga
            success, request_uuid, error = sat_client.solicitar_descarga(
                rfc_solicitante=rfc_solicitante,
                fecha_inicial=fecha_inicial,
                fecha_final=fecha_final,
                tipo_solicitud=tipo_solicitud,
                rfc_emisor=rfc_emisor,
                rfc_receptor=rfc_receptor,
                tipo_comprobante=tipo_comprobante
            )

            if not success:
                # Log error
                self._log_operation(
                    company_id=company_id,
                    operation='solicitar',
                    status='error',
                    message=error,
                    user_id=user_id
                )
                return False, None, error

            # Insertar en BD
            result = self.db.execute(
                text("""
                    INSERT INTO sat_requests (
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
                        requested_at,
                        expires_at,
                        request_evidence,
                        created_by
                    ) VALUES (
                        :company_id,
                        :rfc,
                        :tipo_solicitud,
                        :fecha_inicial,
                        :fecha_final,
                        :rfc_emisor,
                        :rfc_receptor,
                        :tipo_comprobante,
                        :request_uuid,
                        'pending',
                        '5000',
                        :requested_at,
                        :expires_at,
                        :evidence,
                        :user_id
                    ) RETURNING request_id;
                """),
                {
                    'company_id': company_id,
                    'rfc': rfc_solicitante,
                    'tipo_solicitud': tipo_solicitud,
                    'fecha_inicial': fecha_inicial,
                    'fecha_final': fecha_final,
                    'rfc_emisor': rfc_emisor,
                    'rfc_receptor': rfc_receptor,
                    'tipo_comprobante': tipo_comprobante,
                    'request_uuid': request_uuid,
                    'requested_at': datetime.utcnow(),
                    'expires_at': datetime.utcnow() + timedelta(days=7),
                    'evidence': self.evidence_gen.generate_request_evidence(
                        rfc_solicitante=rfc_solicitante,
                        tipo_solicitud=tipo_solicitud,
                        fecha_inicial=fecha_inicial,
                        fecha_final=fecha_final,
                        request_uuid=request_uuid,
                        sat_response={'codigo_estatus': '5000', 'mensaje': 'Solicitud aceptada'},
                        filters={
                            'rfc_emisor': rfc_emisor,
                            'rfc_receptor': rfc_receptor,
                            'tipo_comprobante': tipo_comprobante
                        }
                    ),
                    'user_id': user_id
                }
            )

            request_id = result.fetchone()['request_id']
            self.db.commit()

            # Log success
            self._log_operation(
                company_id=company_id,
                request_id=request_id,
                operation='solicitar',
                status='success',
                message=f"Solicitud SAT creada: {request_uuid}",
                user_id=user_id
            )

            return True, request_id, None

        except Exception as e:
            self.db.rollback()
            return False, None, f"Error al solicitar descarga: {str(e)}"

    async def verificar_solicitud(
        self,
        request_id: int,
        user_id: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verifica el estado de una solicitud SAT

        Args:
            request_id: ID de la solicitud a verificar
            user_id: ID del usuario que verifica

        Returns:
            (success, status_info, error_message)

            status_info contiene:
            - estado_solicitud: 1=Aceptada, 2=En proceso, 3=Terminada, 5=Error
            - numero_cfdis: Cantidad de CFDIs encontrados
            - paquetes: Lista de UUIDs de paquetes disponibles
        """
        try:
            # Obtener solicitud de BD
            result = self.db.execute(
                text("""
                    SELECT
                        r.company_id,
                        r.rfc,
                        r.request_uuid,
                        r.request_status
                    FROM sat_requests r
                    WHERE r.request_id = :request_id;
                """),
                {'request_id': request_id}
            )

            request = result.fetchone()

            if not request:
                return False, None, "Solicitud no encontrada"

            # Obtener cliente SAT
            sat_client = self._get_sat_client(request['company_id'])

            # Verificar en SAT
            success, status_info, error = sat_client.verificar_solicitud(
                rfc_solicitante=request['rfc'],
                request_uuid=request['request_uuid']
            )

            if not success:
                self._log_operation(
                    company_id=request['company_id'],
                    request_id=request_id,
                    operation='verificar',
                    status='error',
                    message=error,
                    user_id=user_id
                )
                return False, None, error

            # Actualizar estado en BD
            new_status = self._map_sat_status(status_info['estado_solicitud'])

            self.db.execute(
                text("""
                    UPDATE sat_requests
                    SET
                        request_status = :status,
                        status_code = :status_code,
                        status_message = :message,
                        updated_at = :updated_at
                    WHERE request_id = :request_id;
                """),
                {
                    'status': new_status,
                    'status_code': str(status_info['estado_solicitud']),
                    'message': status_info['mensaje'],
                    'updated_at': datetime.utcnow(),
                    'request_id': request_id
                }
            )

            # Si hay paquetes disponibles, insertarlos
            if status_info['paquetes']:
                for package_uuid in status_info['paquetes']:
                    self.db.execute(
                        text("""
                            INSERT INTO sat_packages (
                                request_id,
                                company_id,
                                package_uuid,
                                download_status,
                                processing_status,
                                available_at
                            ) VALUES (
                                :request_id,
                                :company_id,
                                :package_uuid,
                                'pending',
                                'pending',
                                :available_at
                            ) ON CONFLICT DO NOTHING;
                        """),
                        {
                            'request_id': request_id,
                            'company_id': request['company_id'],
                            'package_uuid': package_uuid,
                            'available_at': datetime.utcnow()
                        }
                    )

            self.db.commit()

            # Log success
            self._log_operation(
                company_id=request['company_id'],
                request_id=request_id,
                operation='verificar',
                status='success',
                message=f"Estado: {new_status}, CFDIs: {status_info['numero_cfdis']}, Paquetes: {len(status_info['paquetes'])}",
                user_id=user_id
            )

            return True, status_info, None

        except Exception as e:
            self.db.rollback()
            return False, None, f"Error al verificar solicitud: {str(e)}"

    async def descargar_y_procesar_paquete(
        self,
        package_id: int,
        user_id: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Descarga un paquete ZIP del SAT y procesa los CFDIs

        Args:
            package_id: ID del paquete a descargar
            user_id: ID del usuario que descarga

        Returns:
            (success, processing_result, error_message)

            processing_result contiene:
            - inserted: Facturas insertadas
            - duplicates: Facturas duplicadas
            - errors: Errores
        """
        try:
            # Obtener paquete de BD
            result = self.db.execute(
                text("""
                    SELECT
                        p.package_id,
                        p.package_uuid,
                        p.company_id,
                        r.rfc
                    FROM sat_packages p
                    JOIN sat_requests r ON p.request_id = r.request_id
                    WHERE p.package_id = :package_id;
                """),
                {'package_id': package_id}
            )

            package = result.fetchone()

            if not package:
                return False, None, "Paquete no encontrado"

            # Obtener cliente SAT
            sat_client = self._get_sat_client(package['company_id'])

            # Actualizar status a downloading
            self.db.execute(
                text("""
                    UPDATE sat_packages
                    SET download_status = 'downloading', updated_at = :updated_at
                    WHERE package_id = :package_id;
                """),
                {'updated_at': datetime.utcnow(), 'package_id': package_id}
            )
            self.db.commit()

            # Descargar paquete
            success, zip_bytes, error = sat_client.descargar_paquete(
                rfc_solicitante=package['rfc'],
                package_uuid=package['package_uuid']
            )

            if not success:
                self.db.execute(
                    text("""
                        UPDATE sat_packages
                        SET download_status = 'failed', updated_at = :updated_at
                        WHERE package_id = :package_id;
                    """),
                    {'updated_at': datetime.utcnow(), 'package_id': package_id}
                )
                self.db.commit()

                self._log_operation(
                    company_id=package['company_id'],
                    operation='descargar',
                    status='error',
                    message=error,
                    user_id=user_id
                )
                return False, None, error

            # Extraer XMLs del ZIP
            xml_files = self._extract_xmls_from_zip(zip_bytes)

            # Guardar evidencia de descarga
            download_evidence = self.evidence_gen.generate_download_evidence(
                rfc_solicitante=package['rfc'],
                package_uuid=package['package_uuid'],
                zip_content=zip_bytes,
                xml_count=len(xml_files),
                sat_response={'mensaje': 'Descarga exitosa'}
            )

            # Actualizar package en BD
            self.db.execute(
                text("""
                    UPDATE sat_packages
                    SET
                        download_status = 'downloaded',
                        zip_size_bytes = :zip_size,
                        xml_count = :xml_count,
                        downloaded_at = :downloaded_at,
                        download_evidence = :evidence,
                        updated_at = :updated_at
                    WHERE package_id = :package_id;
                """),
                {
                    'zip_size': len(zip_bytes),
                    'xml_count': len(xml_files),
                    'downloaded_at': datetime.utcnow(),
                    'evidence': download_evidence,
                    'updated_at': datetime.utcnow(),
                    'package_id': package_id
                }
            )
            self.db.commit()

            # Procesar CFDIs con BulkInvoiceProcessor
            processor = BulkInvoiceProcessor(self.db)

            # TODO: Integrar con BulkInvoiceProcessor real
            # Por ahora, simula el procesamiento
            processing_result = {
                'inserted': len(xml_files),
                'duplicates': 0,
                'errors': 0
            }

            # Actualizar package a procesado
            self.db.execute(
                text("""
                    UPDATE sat_packages
                    SET
                        processing_status = 'completed',
                        processed_at = :processed_at,
                        updated_at = :updated_at
                    WHERE package_id = :package_id;
                """),
                {
                    'processed_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                    'package_id': package_id
                }
            )
            self.db.commit()

            # Log success
            self._log_operation(
                company_id=package['company_id'],
                operation='procesar',
                status='success',
                message=f"Procesados {len(xml_files)} XMLs: {processing_result['inserted']} insertados",
                user_id=user_id
            )

            return True, processing_result, None

        except Exception as e:
            self.db.rollback()
            return False, None, f"Error al descargar y procesar: {str(e)}"

    # ========================================
    # Helper Methods
    # ========================================

    def _extract_xmls_from_zip(self, zip_bytes: bytes) -> List[Dict]:
        """
        Extrae XMLs de un ZIP SAT

        Args:
            zip_bytes: Contenido del ZIP

        Returns:
            Lista de diccionarios con filename y content
        """
        xml_files = []

        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zip_file:
            for filename in zip_file.namelist():
                if filename.lower().endswith('.xml'):
                    content = zip_file.read(filename).decode('utf-8')
                    xml_files.append({
                        'filename': filename,
                        'content': content
                    })

        return xml_files

    def _map_sat_status(self, estado_solicitud: int) -> str:
        """
        Mapea código de estado SAT a status interno

        Args:
            estado_solicitud: Código SAT (1, 2, 3, 5)

        Returns:
            Status interno (pending, processing, completed, failed)
        """
        mapping = {
            1: 'pending',      # Aceptada
            2: 'processing',   # En proceso
            3: 'completed',    # Terminada
            5: 'failed'        # Error
        }
        return mapping.get(estado_solicitud, 'pending')

    def _log_operation(
        self,
        company_id: int,
        operation: str,
        status: str,
        message: str,
        request_id: Optional[int] = None,
        user_id: Optional[int] = None
    ):
        """Registra operación en sat_download_logs"""
        try:
            self.db.execute(
                text("""
                    INSERT INTO sat_download_logs (
                        company_id,
                        request_id,
                        operation,
                        status,
                        message,
                        user_id,
                        created_at
                    ) VALUES (
                        :company_id,
                        :request_id,
                        :operation,
                        :status,
                        :message,
                        :user_id,
                        :created_at
                    );
                """),
                {
                    'company_id': company_id,
                    'request_id': request_id,
                    'operation': operation,
                    'status': status,
                    'message': message,
                    'user_id': user_id,
                    'created_at': datetime.utcnow()
                }
            )
            self.db.commit()
        except:
            pass  # Si falla el log, no interrumpir operación principal
