"""
SAT Client usando cfdiclient
============================
Implementación probada usando la librería cfdiclient para descarga masiva de CFDIs
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import logging
import base64

logger = logging.getLogger(__name__)


class SATCfdiClient:
    """
    Cliente SAT usando cfdiclient (librería probada)

    Esta implementación reemplaza la versión custom con zeep/xmlsec
    que tenía problemas con la firma WS-Security.
    """

    def __init__(
        self,
        cer_der: bytes,
        key_der: bytes,
        password: str
    ):
        """
        Inicializa el cliente SAT

        Args:
            cer_der: Certificado .cer en formato DER (bytes)
            key_der: Llave privada .key en formato DER (bytes)
            password: Contraseña de la llave privada
        """
        from cfdiclient import Fiel

        self.fiel = Fiel(cer_der, key_der, password)
        self.token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

        # Extraer RFC del certificado usando cryptography
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        cert = x509.load_der_x509_certificate(cer_der, default_backend())
        # El RFC está en el x500UniqueIdentifier del subject
        for attr in cert.subject:
            if attr.oid == x509.NameOID.X500_UNIQUE_IDENTIFIER:
                # Formato: "RFC_EMPRESA / RFC_PERSONA"
                self.rfc = attr.value.split('/')[0].strip()
                break
        else:
            self.rfc = "UNKNOWN"

        logger.info(f"[SAT_CFDI] Cliente inicializado para RFC: {self.rfc}")

    def _ensure_token(self) -> Tuple[bool, Optional[str]]:
        """Asegura que tengamos un token válido"""
        if self.token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return True, None

        try:
            from cfdiclient import Autenticacion

            auth = Autenticacion(self.fiel)
            self.token = auth.obtener_token()
            self.token_expires_at = datetime.utcnow() + timedelta(minutes=4)  # Token dura 5 min, renovamos a los 4

            logger.info(f"[SAT_CFDI] Token obtenido correctamente")
            return True, None

        except Exception as e:
            logger.error(f"[SAT_CFDI] Error obteniendo token: {e}")
            return False, f"Error de autenticación: {str(e)}"

    def solicitar_descarga(
        self,
        rfc_solicitante: str,
        fecha_inicial: datetime,
        fecha_final: datetime,
        tipo_solicitud: str = "CFDI",
        rfc_emisor: Optional[str] = None,
        rfc_receptor: Optional[str] = None,
        tipo_comprobante: Optional[str] = None,
        estado_comprobante: Optional[str] = "Vigente",
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
            estado_comprobante: "Vigente", "Cancelado" o None para todos (opcional)

        Returns:
            (success, request_uuid, error_message)
        """
        # Asegurar token
        success, error = self._ensure_token()
        if not success:
            return False, None, error

        try:
            from cfdiclient import SolicitaDescargaRecibidos, SolicitaDescargaEmitidos

            # Determinar tipo de solicitud
            # Si rfc_receptor == rfc_solicitante, son recibidas
            # Si rfc_emisor == rfc_solicitante, son emitidas
            es_recibidas = rfc_receptor == rfc_solicitante if rfc_receptor else True

            if es_recibidas:
                solicitud = SolicitaDescargaRecibidos(self.fiel)
            else:
                solicitud = SolicitaDescargaEmitidos(self.fiel)

            # Formatear fechas (pueden venir como datetime o str)

            if hasattr(fecha_inicial, 'strftime'):
                fecha_ini_str = fecha_inicial.strftime('%Y-%m-%dT00:00:00')
            else:
                fecha_ini_str = f"{fecha_inicial}T00:00:00" if 'T' not in str(fecha_inicial) else str(fecha_inicial)

            if hasattr(fecha_final, 'strftime'):
                fecha_fin_str = fecha_final.strftime('%Y-%m-%dT23:59:59')
            else:
                fecha_fin_str = f"{fecha_final}T23:59:59" if 'T' not in str(fecha_final) else str(fecha_final)

            # Asegurar que fecha_inicial y fecha_final son datetime objects
            from datetime import datetime as dt
            if isinstance(fecha_inicial, str):
                fecha_inicial_dt = dt.fromisoformat(fecha_inicial.replace('T', ' ').split('.')[0]) if 'T' in fecha_inicial else dt.strptime(fecha_inicial.split()[0], '%Y-%m-%d')
            else:
                fecha_inicial_dt = fecha_inicial

            if isinstance(fecha_final, str):
                fecha_final_dt = dt.fromisoformat(fecha_final.replace('T', ' ').split('.')[0]) if 'T' in fecha_final else dt.strptime(fecha_final.split()[0], '%Y-%m-%d')
            else:
                fecha_final_dt = fecha_final

            # Construir parámetros según documentación de cfdiclient
            # Para SolicitaDescargaRecibidos: RfcReceptor = el RFC del solicitante (nosotros recibimos las facturas)
            # Para SolicitaDescargaEmitidos: RfcEmisor = el RFC del solicitante (nosotros emitimos las facturas)
            if es_recibidas:
                rfc_emisor_param = rfc_emisor if rfc_emisor else None
                rfc_receptor_param = rfc_solicitante  # Nosotros somos los receptores
            else:
                rfc_emisor_param = rfc_solicitante  # Nosotros somos los emisores
                rfc_receptor_param = rfc_receptor if rfc_receptor else None

            # EstadoComprobante: 'Vigente', 'Cancelado' o None para todos
            print(f"[SAT_CFDI] Solicitando descarga: {fecha_inicial_dt} a {fecha_final_dt}, RFC={rfc_solicitante}", flush=True)
            print(f"[SAT_CFDI] Params: rfc_emisor={rfc_emisor_param}, rfc_receptor={rfc_receptor_param}, tipo={tipo_solicitud}, estado={estado_comprobante}", flush=True)

            # Construir kwargs para solicitud
            solicitud_kwargs = {
                'token': self.token,
                'rfc_solicitante': rfc_solicitante,
                'fecha_inicial': fecha_inicial_dt,
                'fecha_final': fecha_final_dt,
                'rfc_emisor': rfc_emisor_param,
                'rfc_receptor': rfc_receptor_param,
                'tipo_solicitud': tipo_solicitud,
            }
            # Solo agregar estado_comprobante si se especifica (None = todos)
            if estado_comprobante:
                solicitud_kwargs['estado_comprobante'] = estado_comprobante

            result = solicitud.solicitar_descarga(**solicitud_kwargs)
            print(f"[SAT_CFDI] Respuesta SAT: {result}", flush=True)

            # Procesar respuesta
            # result es un dict con: cod_estatus, mensaje, id_solicitud
            cod_estatus = result.get('cod_estatus', '')
            mensaje = result.get('mensaje', '')
            id_solicitud = result.get('id_solicitud', '')

            logger.info(f"[SAT_CFDI] Respuesta solicitud: cod={cod_estatus}, msg={mensaje}, id={id_solicitud}")

            if cod_estatus == '5000' and id_solicitud:
                return True, id_solicitud, mensaje
            else:
                return False, None, f"SAT error {cod_estatus}: {mensaje}"

        except Exception as e:
            import traceback
            print(f"[SAT_CFDI] ERROR en solicitud: {type(e).__name__}: {e}", flush=True)
            print(f"[SAT_CFDI] Traceback: {traceback.format_exc()}", flush=True)
            return False, None, f"Error en solicitud: {type(e).__name__}: {str(e)}"

    def verificar_solicitud(
        self,
        rfc_solicitante: str,
        request_uuid: str
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verifica el estado de una solicitud

        Returns:
            (success, status_info, error_message)
        """
        success, error = self._ensure_token()
        if not success:
            return False, None, error

        try:
            from cfdiclient import VerificaSolicitudDescarga

            verificador = VerificaSolicitudDescarga(self.fiel)
            result = verificador.verificar_descarga(
                self.token,
                rfc_solicitante,
                request_uuid
            )

            # result contiene: cod_estatus, estado_solicitud, numero_cfdis, paquetes
            cod_estatus = result.get('cod_estatus', '')
            estado = result.get('estado_solicitud', '')
            numero_cfdis = result.get('numero_cfdis', 0)
            paquetes = result.get('paquetes', [])
            mensaje = result.get('mensaje', '')

            logger.info(f"[SAT_CFDI] Verificación: estado={estado}, cfdis={numero_cfdis}, paquetes={len(paquetes)}")

            # Mapear estados SAT
            # 1=Aceptada, 2=En proceso, 3=Terminada, 4=Error, 5=Rechazada, 6=Vencida
            status_info = {
                'estado_solicitud': int(estado) if estado else 0,
                'codigo_estado_solicitud': cod_estatus,
                'numero_cfdis': int(numero_cfdis) if numero_cfdis else 0,
                'mensaje': mensaje,
                'paquetes': paquetes if paquetes else []
            }

            return True, status_info, None

        except Exception as e:
            logger.error(f"[SAT_CFDI] Error en verificación: {e}")
            return False, None, f"Error en verificación: {str(e)}"

    def descargar_paquete(
        self,
        rfc_solicitante: str,
        package_uuid: str
    ) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Descarga un paquete ZIP con CFDIs

        Returns:
            (success, zip_bytes, error_message)
        """
        success, error = self._ensure_token()
        if not success:
            return False, None, error

        try:
            from cfdiclient import DescargaMasiva

            descarga = DescargaMasiva(self.fiel)
            result = descarga.descargar_paquete(
                self.token,
                rfc_solicitante,
                package_uuid
            )

            # result contiene: cod_estatus, mensaje, paquete_b64
            cod_estatus = result.get('cod_estatus', '')
            paquete_b64 = result.get('paquete_b64', '')
            mensaje = result.get('mensaje', '')

            if cod_estatus == '5000' and paquete_b64:
                zip_bytes = base64.b64decode(paquete_b64)
                logger.info(f"[SAT_CFDI] Paquete descargado: {len(zip_bytes)} bytes")
                return True, zip_bytes, None
            else:
                return False, None, f"SAT error {cod_estatus}: {mensaje}"

        except Exception as e:
            logger.error(f"[SAT_CFDI] Error en descarga: {e}")
            return False, None, f"Error en descarga: {str(e)}"


class SATCfdiClientMock(SATCfdiClient):
    """Mock para testing sin credenciales reales"""

    def __init__(self):
        self.token = "MOCK_TOKEN"
        self.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.rfc = "XAXX010101000"
        self.mock_requests = {}

    def _ensure_token(self) -> Tuple[bool, Optional[str]]:
        return True, None

    def solicitar_descarga(self, *args, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        import uuid
        request_uuid = str(uuid.uuid4())
        self.mock_requests[request_uuid] = {'status': 'processing'}
        return True, request_uuid, "Solicitud aceptada (MOCK)"

    def verificar_solicitud(self, rfc_solicitante: str, request_uuid: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        import uuid
        package_uuid = str(uuid.uuid4())
        status_info = {
            'estado_solicitud': 3,  # Terminada
            'codigo_estado_solicitud': '5000',
            'numero_cfdis': 10,
            'mensaje': 'Solicitud procesada (MOCK)',
            'paquetes': [package_uuid]
        }
        return True, status_info, None

    def descargar_paquete(self, rfc_solicitante: str, package_uuid: str) -> Tuple[bool, Optional[bytes], Optional[str]]:
        import io
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('README.txt', 'Mock SAT package - no real data')

        return True, zip_buffer.getvalue(), None
