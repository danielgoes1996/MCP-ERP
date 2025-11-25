"""
SAT Web Service SOAP Client
============================
Cliente para integración con el servicio de Descarga Masiva del SAT

Servicios implementados:
1. Autenticación (FIEL - Firma Electrónica)
2. Solicitar Descarga (Request CFDI download)
3. Verificar Solicitud (Check request status)
4. Descargar Paquete (Download ZIP package)

Referencias:
- SAT Web Service: https://www.sat.gob.mx/aplicacion/16660/presenta-tu-solicitud-de-descarga-masiva-de-xml
- Documentación técnica: http://omawww.sat.gob.mx/cifras_sat/Documents/Descarga_Masiva.pdf
"""

from zeep import Client
from zeep.wsse import utils
from zeep.wsse.signature import Signature
from lxml import etree
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import hashlib
import uuid as uuid_lib


class SATSignature(Signature):
    """
    Custom Signature class para SAT con Timestamp y sin verificación de respuesta

    El SAT requiere:
    1. Timestamp en el header de seguridad
    2. Firma digital con RSA-SHA1
    3. NO verificar la firma de la respuesta (el SAT tiene problemas con esto)
    """

    def apply(self, envelope, headers):
        """Override para agregar Timestamp antes de firmar"""
        # Primero agregar el timestamp
        security = utils.get_security_header(envelope)

        # Crear timestamp manualmente
        from zeep.wsse.utils import WSU
        WSU_NS = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'

        created = datetime.utcnow()
        expires = created + timedelta(minutes=5)

        timestamp = etree.Element(
            f"{{{WSU_NS}}}Timestamp",
            attrib={f"{{{WSU_NS}}}Id": "TS-1"}
        )
        created_elem = etree.SubElement(timestamp, f"{{{WSU_NS}}}Created")
        created_elem.text = created.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z'

        expires_elem = etree.SubElement(timestamp, f"{{{WSU_NS}}}Expires")
        expires_elem.text = expires.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z'

        security.insert(0, timestamp)

        # Ahora aplicar la firma (llamar al método padre)
        return super().apply(envelope, headers)

    def verify(self, envelope):
        """Override para deshabilitar verificación de firma en respuestas"""
        # No hacer nada - aceptar cualquier respuesta sin verificar firma
        pass
import tempfile
from pathlib import Path


class SATSOAPClient:
    """
    Cliente SOAP para el servicio de Descarga Masiva del SAT

    IMPORTANTE: Esta clase NO maneja las credenciales directamente.
    Las credenciales (.cer, .key) deben venir desde Vault/Secrets Manager.
    """

    # URLs de producción del SAT
    AUTENTICACION_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc?wsdl"
    SOLICITUD_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc?wsdl"
    VERIFICACION_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc?wsdl"
    DESCARGA_URL = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/DescargaMasivaService.svc?wsdl"

    def __init__(
        self,
        certificate_pem: str,
        private_key_pem: str,
        private_key_password: Optional[str] = None
    ):
        """
        Inicializa el cliente SAT SOAP

        Args:
            certificate_pem: Certificado .cer en formato PEM (str)
            private_key_pem: Llave privada .key en formato PEM (str)
            private_key_password: Contraseña de la llave privada (opcional)
        """
        self.certificate_pem = certificate_pem
        self.private_key_pem = private_key_pem
        self.private_key_password = private_key_password

        # Cargar certificado y llave
        self.certificate = x509.load_pem_x509_certificate(
            certificate_pem.encode() if isinstance(certificate_pem, str) else certificate_pem,
            default_backend()
        )

        self.private_key = serialization.load_pem_private_key(
            private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem,
            password=private_key_password.encode() if private_key_password else None,
            backend=default_backend()
        )

        # Token de autenticación (se obtiene con autenticar())
        self.token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    def _create_soap_client(self, wsdl_url: str, with_wsse: bool = True) -> Client:
        """
        Crea un cliente SOAP con zeep

        Args:
            wsdl_url: URL del WSDL
            with_wsse: Si True, agrega WS-Security con certificado

        Returns:
            Cliente SOAP configurado
        """
        if not with_wsse:
            return Client(wsdl_url)

        # Crear archivos temporales para certificado y llave
        # (zeep.wsse.Signature necesita archivos, no strings)
        cert_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
        key_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)

        try:
            # Escribir certificado
            cert_file.write(self.certificate_pem)
            cert_file.close()

            # Escribir llave privada
            key_file.write(self.private_key_pem)
            key_file.close()

            # Crear signature plugin para WS-Security
            wsse = Signature(
                key_file.name,
                cert_file.name,
                password=self.private_key_password
            )

            # Crear cliente con WS-Security
            client = Client(wsdl_url, wsse=wsse)

            return client

        except Exception as e:
            # Limpiar archivos temporales en caso de error
            try:
                Path(cert_file.name).unlink(missing_ok=True)
                Path(key_file.name).unlink(missing_ok=True)
            except:
                pass
            raise e

    def _sign_request(self, xml_data: str) -> str:
        """
        Firma digitalmente el XML request con FIEL

        Args:
            xml_data: XML a firmar

        Returns:
            XML firmado con firma digital
        """
        # TODO: Implementar firma XML-DSig para FIEL
        # Por ahora retorna el XML sin firmar (para desarrollo)
        # En producción debe firmarse con XMLDSig
        return xml_data

    def autenticar(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Autentica con el SAT usando FIEL (e.firma)

        El SAT usa WS-Security con firma digital en el header SOAP.
        La autenticación NO requiere parámetros - todo va en el header WS-Security.

        Returns:
            (success, token, error_message)
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info("[SAT_SOAP] autenticar() START")

        cert_file_path = None
        key_file_path = None

        try:
            # Crear archivos temporales para WS-Security
            logger.info("[SAT_SOAP] Creando archivos temporales...")
            cert_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
            key_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)

            cert_file.write(self.certificate_pem)
            cert_file.close()
            cert_file_path = cert_file.name

            key_file.write(self.private_key_pem)
            key_file.close()
            key_file_path = key_file.name
            logger.info(f"[SAT_SOAP] Archivos creados: cert={cert_file_path}, key={key_file_path}")

            # Crear WS-Security signature
            # Usamos SATSignature que NO verifica la firma de respuesta del SAT
            # (el SAT a veces tiene problemas con sus propias firmas de respuesta)
            # El SAT requiere algoritmos específicos: RSA-SHA1 y SHA1
            logger.info("[SAT_SOAP] Importando xmlsec...")
            import xmlsec
            logger.info("[SAT_SOAP] xmlsec importado correctamente")

            if self.private_key_password:
                wsse = SATSignature(
                    key_file_path,
                    cert_file_path,
                    password=self.private_key_password,
                    signature_method=xmlsec.constants.TransformRsaSha1,
                    digest_method=xmlsec.constants.TransformSha1
                )
            else:
                wsse = SATSignature(
                    key_file_path,
                    cert_file_path,
                    signature_method=xmlsec.constants.TransformRsaSha1,
                    digest_method=xmlsec.constants.TransformSha1
                )

            # Crear cliente con WS-Security
            client = Client(self.AUTENTICACION_URL, wsse=wsse)

            # Llamar servicio de autenticación SIN parámetros
            # La autenticación se hace mediante la firma digital en el header
            response = client.service.Autentica()

            # Limpiar archivos temporales
            try:
                Path(cert_file_path).unlink(missing_ok=True)
                Path(key_file_path).unlink(missing_ok=True)
            except:
                pass

            # Procesar respuesta
            # El SAT retorna el token como string directo
            if response and isinstance(response, str) and len(response) > 0:
                self.token = response
                self.token_expires_at = datetime.utcnow() + timedelta(minutes=5)  # SAT tokens duran 5 min
                return True, self.token, None
            else:
                return False, None, f"Respuesta inválida del SAT: {response}"

        except Exception as e:
            # Limpiar archivos temporales en caso de error
            try:
                if cert_file_path:
                    Path(cert_file_path).unlink(missing_ok=True)
                if key_file_path:
                    Path(key_file_path).unlink(missing_ok=True)
            except:
                pass

            # Log detallado del error
            import traceback
            error_detail = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            return False, None, f"Error en autenticación: {error_detail}"

    def solicitar_descarga(
        self,
        rfc_solicitante: str,
        fecha_inicial: datetime,
        fecha_final: datetime,
        tipo_solicitud: str = "CFDI",  # CFDI o Metadata
        rfc_emisor: Optional[str] = None,
        rfc_receptor: Optional[str] = None,
        tipo_comprobante: Optional[str] = None,  # I, E, P, N, T
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Solicita descarga masiva de CFDIs

        Args:
            rfc_solicitante: RFC de quien solicita
            fecha_inicial: Fecha inicial de búsqueda
            fecha_final: Fecha final de búsqueda
            tipo_solicitud: "CFDI" para XMLs completos, "Metadata" solo metadatos
            rfc_emisor: Filtrar por RFC emisor (opcional)
            rfc_receptor: Filtrar por RFC receptor (opcional)
            tipo_comprobante: Filtrar por tipo (I, E, P, N, T) (opcional)

        Returns:
            (success, request_uuid, error_message)
        """
        # Validar token
        if not self._is_token_valid():
            success, token, error = self.autenticar()
            if not success:
                return False, None, f"Error autenticación: {error}"

        try:
            client = self._create_soap_client(self.SOLICITUD_URL)

            # Preparar parámetros
            solicitud = {
                'RfcSolicitante': rfc_solicitante,
                'FechaInicial': fecha_inicial.strftime('%Y-%m-%dT%H:%M:%S'),
                'FechaFinal': fecha_final.strftime('%Y-%m-%dT%H:%M:%S'),
                'TipoSolicitud': tipo_solicitud,
            }

            # Filtros opcionales
            if rfc_emisor:
                solicitud['RfcEmisor'] = rfc_emisor
            if rfc_receptor:
                solicitud['RfcReceptor'] = rfc_receptor
            if tipo_comprobante:
                solicitud['TipoComprobante'] = tipo_comprobante

            # Llamar servicio
            response = client.service.SolicitaDescarga(
                token=self.token,
                solicitud=solicitud
            )

            # Procesar respuesta
            if hasattr(response, 'IdSolicitud'):
                request_uuid = response.IdSolicitud
                cod_estatus = getattr(response, 'CodEstatus', '')
                mensaje = getattr(response, 'Mensaje', '')

                if cod_estatus in ['5000', '5002', '5003', '5004', '5005']:
                    # Códigos de éxito
                    return True, request_uuid, mensaje
                else:
                    return False, None, f"SAT error {cod_estatus}: {mensaje}"
            else:
                return False, None, "Respuesta inválida del SAT"

        except Exception as e:
            return False, None, f"Error en solicitud: {str(e)}"

    def verificar_solicitud(
        self,
        rfc_solicitante: str,
        request_uuid: str
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verifica el estado de una solicitud de descarga

        Args:
            rfc_solicitante: RFC de quien solicitó
            request_uuid: UUID de la solicitud a verificar

        Returns:
            (success, status_info, error_message)

            status_info contiene:
            - estado_solicitud: 1=Aceptada, 2=En proceso, 3=Terminada, 5=Error
            - codigo_estado_solicitud: Código numérico
            - numero_cfdis: Cantidad de CFDIs encontrados
            - paquetes: Lista de UUIDs de paquetes disponibles
        """
        # Validar token
        if not self._is_token_valid():
            success, token, error = self.autenticar()
            if not success:
                return False, None, f"Error autenticación: {error}"

        try:
            client = self._create_soap_client(self.VERIFICACION_URL)

            response = client.service.VerificaSolicitudDescarga(
                token=self.token,
                rfcSolicitante=rfc_solicitante,
                idSolicitud=request_uuid
            )

            if hasattr(response, 'EstadoSolicitud'):
                status_info = {
                    'estado_solicitud': getattr(response, 'EstadoSolicitud', None),
                    'codigo_estado_solicitud': getattr(response, 'CodigoEstadoSolicitud', None),
                    'numero_cfdis': getattr(response, 'NumeroCFDIs', 0),
                    'mensaje': getattr(response, 'Mensaje', ''),
                    'paquetes': []
                }

                # Extraer IDs de paquetes si están disponibles
                if hasattr(response, 'IdsPaquetes'):
                    paquetes = response.IdsPaquetes
                    if hasattr(paquetes, 'string'):
                        # Puede ser una lista o un solo elemento
                        if isinstance(paquetes.string, list):
                            status_info['paquetes'] = paquetes.string
                        else:
                            status_info['paquetes'] = [paquetes.string]

                return True, status_info, None
            else:
                return False, None, "Respuesta inválida del SAT"

        except Exception as e:
            return False, None, f"Error en verificación: {str(e)}"

    def descargar_paquete(
        self,
        rfc_solicitante: str,
        package_uuid: str
    ) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Descarga un paquete ZIP con CFDIs

        Args:
            rfc_solicitante: RFC de quien solicita
            package_uuid: UUID del paquete a descargar

        Returns:
            (success, zip_content_bytes, error_message)
        """
        # Validar token
        if not self._is_token_valid():
            success, token, error = self.autenticar()
            if not success:
                return False, None, f"Error autenticación: {error}"

        try:
            client = self._create_soap_client(self.DESCARGA_URL)

            response = client.service.DescargaPaquete(
                token=self.token,
                rfcSolicitante=rfc_solicitante,
                idPaquete=package_uuid
            )

            if hasattr(response, 'Paquete'):
                # El paquete viene en base64
                zip_b64 = response.Paquete
                zip_bytes = base64.b64decode(zip_b64)
                return True, zip_bytes, None
            else:
                mensaje = getattr(response, 'Mensaje', 'Paquete no disponible')
                return False, None, mensaje

        except Exception as e:
            return False, None, f"Error en descarga: {str(e)}"

    # ========================================
    # Helper Methods
    # ========================================

    def _is_token_valid(self) -> bool:
        """Verifica si el token actual es válido"""
        if not self.token or not self.token_expires_at:
            return False
        return datetime.utcnow() < self.token_expires_at

    def _extract_rfc_from_certificate(self) -> str:
        """Extrae el RFC del certificado FIEL"""
        # Opción 1: Buscar en x500UniqueIdentifier (certificados SAT nuevos)
        for attribute in self.certificate.subject:
            if attribute.oid == x509.NameOID.X500_UNIQUE_IDENTIFIER:
                # Formato: "RFC_EMPRESA / RFC_PERSONA"
                unique_id = attribute.value
                if '/' in unique_id:
                    # El primer elemento es el RFC de la empresa
                    rfc = unique_id.split('/')[0].strip()
                    return rfc
                # Si no tiene '/', es el RFC directamente
                return unique_id.strip()

        # Opción 2: Buscar en Common Name (certificados SAT antiguos)
        for attribute in self.certificate.subject:
            if attribute.oid == x509.NameOID.COMMON_NAME:
                # CN formato: "Nombre del Contribuyente / RFC"
                cn = attribute.value
                if '/' in cn:
                    rfc = cn.split('/')[-1].strip()
                    return rfc

        raise ValueError("No se pudo extraer RFC del certificado")

    def _create_signature(self, data: str) -> str:
        """
        Crea firma digital de los datos

        Args:
            data: Datos a firmar

        Returns:
            Firma en base64
        """
        from cryptography.hazmat.primitives.asymmetric import padding

        signature = self.private_key.sign(
            data.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        return base64.b64encode(signature).decode()


# ========================================
# Mock Client (para desarrollo/testing)
# ========================================

class SATSOAPClientMock(SATSOAPClient):
    """
    Cliente MOCK para testing sin credenciales reales
    Simula las respuestas del SAT
    """

    def __init__(self):
        """Mock no requiere credenciales"""
        self.token = "MOCK_TOKEN_12345"
        self.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.mock_requests = {}  # Almacena solicitudes simuladas

    def autenticar(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Mock de autenticación"""
        self.token = f"MOCK_TOKEN_{uuid_lib.uuid4().hex[:8]}"
        self.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        return True, self.token, None

    def solicitar_descarga(
        self,
        rfc_solicitante: str,
        fecha_inicial: datetime,
        fecha_final: datetime,
        tipo_solicitud: str = "CFDI",
        rfc_emisor: Optional[str] = None,
        rfc_receptor: Optional[str] = None,
        tipo_comprobante: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Mock de solicitud"""
        request_uuid = str(uuid_lib.uuid4())

        # Guardar solicitud mock
        self.mock_requests[request_uuid] = {
            'rfc': rfc_solicitante,
            'fecha_inicial': fecha_inicial,
            'fecha_final': fecha_final,
            'tipo': tipo_solicitud,
            'status': 'processing',  # Simula que está procesando
            'paquetes': []
        }

        return True, request_uuid, "Solicitud aceptada (MOCK)"

    def verificar_solicitud(
        self,
        rfc_solicitante: str,
        request_uuid: str
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Mock de verificación"""
        if request_uuid not in self.mock_requests:
            return False, None, "Solicitud no encontrada (MOCK)"

        # Simular que la solicitud está completada con 1 paquete
        package_uuid = str(uuid_lib.uuid4())

        status_info = {
            'estado_solicitud': 3,  # 3 = Terminada
            'codigo_estado_solicitud': '5000',
            'numero_cfdis': 10,  # Mock: 10 CFDIs
            'mensaje': 'Solicitud procesada (MOCK)',
            'paquetes': [package_uuid]
        }

        # Actualizar mock
        self.mock_requests[request_uuid]['status'] = 'completed'
        self.mock_requests[request_uuid]['paquetes'] = [package_uuid]

        return True, status_info, None

    def descargar_paquete(
        self,
        rfc_solicitante: str,
        package_uuid: str
    ) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """Mock de descarga - retorna ZIP vacío"""
        # Crear un ZIP mock simple
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('README.txt', 'Mock SAT package - no real data')

        zip_bytes = zip_buffer.getvalue()
        return True, zip_bytes, None
