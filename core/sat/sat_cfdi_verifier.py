"""
SAT CFDI Verifier - Consulta de Estatus de CFDI
================================================
Cliente SOAP para verificar el estatus de CFDIs en el SAT

Este módulo permite verificar si un CFDI está:
- Vigente: El CFDI es válido y puede usarse
- Cancelado: El CFDI fue cancelado por el emisor
- Sustituido: El CFDI fue sustituido por otro
- Por Cancelar: El CFDI tiene una solicitud de cancelación pendiente

Web Service SAT: ConsultaCFDIService.svc
Endpoint: https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl

Referencias:
- Guía de implementación: https://www.sat.gob.mx/consultas/91447/verifica-comprobantes
- Estados posibles: Vigente, Cancelado, No Encontrado
"""

from zeep import Client
from zeep.exceptions import Fault
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import uuid as uuid_lib
import logging

logger = logging.getLogger(__name__)


class SATCFDIVerifier:
    """
    Cliente SOAP para verificar estatus de CFDIs en el SAT

    El SAT proporciona un servicio web para consultar el estado de un CFDI
    utilizando su UUID, RFC del emisor, RFC del receptor y el total.
    """

    # URL del servicio SAT (Producción)
    WSDL_URL = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl"

    # Estados posibles del SAT
    STATUS_VIGENTE = "vigente"
    STATUS_CANCELADO = "cancelado"
    STATUS_SUSTITUIDO = "sustituido"
    STATUS_POR_CANCELAR = "por_cancelar"
    STATUS_NO_ENCONTRADO = "no_encontrado"
    STATUS_ERROR = "error"

    def __init__(self, use_mock: bool = False):
        """
        Inicializa el verificador de CFDIs

        Args:
            use_mock: Si True, usa respuestas mock sin conectar al SAT
        """
        self.use_mock = use_mock
        self.client = None

        if not use_mock:
            try:
                self.client = Client(self.WSDL_URL)
                logger.info(f"CFDI Verifier initialized with SAT WSDL: {self.WSDL_URL}")
            except Exception as e:
                logger.error(f"Error initializing SAT SOAP client: {e}")
                raise

    def check_cfdi_status(
        self,
        uuid: str,
        rfc_emisor: str,
        rfc_receptor: str,
        total: float
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verifica el estatus de un CFDI en el SAT

        Args:
            uuid: UUID del CFDI a verificar
            rfc_emisor: RFC del emisor
            rfc_receptor: RFC del receptor
            total: Monto total del comprobante

        Returns:
            (success, status_info, error_message)

            status_info contiene:
            - status: vigente, cancelado, sustituido, por_cancelar, no_encontrado
            - codigo_estatus: Código del SAT
            - es_cancelable: Si el CFDI puede cancelarse
            - estado: Estado detallado del SAT
            - fecha_consulta: Timestamp de la consulta
            - validacion_efos: Si el emisor está en lista EFOS (opcional)
        """
        if self.use_mock:
            return self._check_cfdi_status_mock(uuid, rfc_emisor, rfc_receptor, total)

        try:
            # Formatear total como string con 2 decimales
            total_str = f"{total:.2f}"

            # Llamar servicio SAT
            logger.info(f"Consultando CFDI {uuid} en SAT...")

            response = self.client.service.Consulta(
                expresionImpresa=f"?re={rfc_emisor}&rr={rfc_receptor}&tt={total_str}&id={uuid}"
            )

            # Parsear respuesta
            status_info = self._parse_sat_response(response)

            logger.info(f"CFDI {uuid}: {status_info['status']}")

            return True, status_info, None

        except Fault as e:
            # Error SOAP del SAT
            logger.error(f"SAT SOAP Fault: {e}")
            return False, None, f"Error del SAT: {e.message}"

        except Exception as e:
            # Error genérico
            logger.error(f"Error verificando CFDI: {e}")
            return False, None, f"Error al verificar CFDI: {str(e)}"

    def _parse_sat_response(self, response) -> Dict:
        """
        Parsea la respuesta del SAT y extrae el estatus

        Args:
            response: Respuesta SOAP del SAT

        Returns:
            Diccionario con información del estatus
        """
        # El SAT retorna un objeto con diferentes campos dependiendo del estatus
        status_info = {
            'fecha_consulta': datetime.utcnow(),
            'status': self.STATUS_ERROR,
            'codigo_estatus': None,
            'es_cancelable': None,
            'estado': None,
            'validacion_efos': None
        }

        try:
            # Extraer código de estatus
            codigo_estatus = getattr(response, 'CodigoEstatus', None)
            status_info['codigo_estatus'] = codigo_estatus

            # Extraer estado
            estado = getattr(response, 'Estado', None)
            status_info['estado'] = estado

            # Extraer es cancelable
            es_cancelable = getattr(response, 'EsCancelable', None)
            status_info['es_cancelable'] = es_cancelable == 'Cancelable'

            # Extraer validación EFOS (Empresas Facturadoras de Operaciones Simuladas)
            validacion_efos = getattr(response, 'EstatusCancelacion', None)
            status_info['validacion_efos'] = validacion_efos

            # Mapear estado del SAT a nuestros estados
            if estado:
                estado_lower = estado.lower()

                if 'vigente' in estado_lower:
                    status_info['status'] = self.STATUS_VIGENTE
                elif 'cancelado' in estado_lower:
                    # Verificar si es cancelación definitiva o pendiente
                    if 'proceso' in estado_lower or 'pendiente' in estado_lower:
                        status_info['status'] = self.STATUS_POR_CANCELAR
                    else:
                        status_info['status'] = self.STATUS_CANCELADO
                elif 'sustituido' in estado_lower:
                    status_info['status'] = self.STATUS_SUSTITUIDO
                elif 'no encontrado' in estado_lower:
                    status_info['status'] = self.STATUS_NO_ENCONTRADO
                else:
                    status_info['status'] = self.STATUS_ERROR

            # Si código de estatus indica problema
            if codigo_estatus and codigo_estatus != 'S':
                if codigo_estatus == 'N':
                    status_info['status'] = self.STATUS_NO_ENCONTRADO

        except Exception as e:
            logger.error(f"Error parsing SAT response: {e}")
            status_info['status'] = self.STATUS_ERROR

        return status_info

    def _check_cfdi_status_mock(
        self,
        uuid: str,
        rfc_emisor: str,
        rfc_receptor: str,
        total: float
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Versión MOCK para testing sin conectar al SAT

        Retorna diferentes estados basados en el UUID para testing
        """
        logger.info(f"[MOCK] Verificando CFDI {uuid}")

        # Simular diferentes estados basados en el último carácter del UUID
        last_char = uuid[-1].lower()

        if last_char in ['0', '1', '2', '3', '4', '5']:
            # 60% de CFDIs son vigentes
            status = self.STATUS_VIGENTE
            codigo_estatus = 'S'
            estado = 'Vigente'
            es_cancelable = True
        elif last_char in ['6', '7']:
            # 20% cancelados
            status = self.STATUS_CANCELADO
            codigo_estatus = 'S'
            estado = 'Cancelado'
            es_cancelable = False
        elif last_char == '8':
            # 10% por cancelar
            status = self.STATUS_POR_CANCELAR
            codigo_estatus = 'S'
            estado = 'Cancelado en proceso'
            es_cancelable = False
        elif last_char == '9':
            # 10% sustituidos
            status = self.STATUS_SUSTITUIDO
            codigo_estatus = 'S'
            estado = 'Sustituido'
            es_cancelable = False
        else:
            # No encontrado
            status = self.STATUS_NO_ENCONTRADO
            codigo_estatus = 'N'
            estado = 'No Encontrado'
            es_cancelable = None

        status_info = {
            'fecha_consulta': datetime.utcnow(),
            'status': status,
            'codigo_estatus': codigo_estatus,
            'es_cancelable': es_cancelable,
            'estado': estado,
            'validacion_efos': 'No aplica (MOCK)'
        }

        return True, status_info, None

    def verify_multiple_cfdis(
        self,
        cfdis: list
    ) -> Dict[str, Dict]:
        """
        Verifica el estatus de múltiples CFDIs

        Args:
            cfdis: Lista de diccionarios con uuid, rfc_emisor, rfc_receptor, total

        Returns:
            Diccionario mapeando UUID -> status_info
        """
        results = {}

        for cfdi in cfdis:
            uuid = cfdi['uuid']

            success, status_info, error = self.check_cfdi_status(
                uuid=uuid,
                rfc_emisor=cfdi['rfc_emisor'],
                rfc_receptor=cfdi['rfc_receptor'],
                total=cfdi['total']
            )

            if success:
                results[uuid] = status_info
            else:
                results[uuid] = {
                    'status': self.STATUS_ERROR,
                    'error': error,
                    'fecha_consulta': datetime.utcnow()
                }

        return results

    def should_retry(self, error: str) -> bool:
        """
        Determina si un error del SAT es retryable

        Args:
            error: Mensaje de error

        Returns:
            True si se debe reintentar
        """
        retryable_errors = [
            'timeout',
            'connection',
            'servicio no disponible',
            'temporalmente',
            '503',
            '502',
            '504'
        ]

        error_lower = error.lower()
        return any(err in error_lower for err in retryable_errors)


# ========================================
# Utility Functions
# ========================================

def format_cfdi_verification_url(
    uuid: str,
    rfc_emisor: str,
    rfc_receptor: str,
    total: float
) -> str:
    """
    Genera la URL de verificación del SAT para QR

    Args:
        uuid: UUID del CFDI
        rfc_emisor: RFC del emisor
        rfc_receptor: RFC del receptor
        total: Total del comprobante

    Returns:
        URL de verificación
    """
    total_str = f"{total:.6f}"
    return f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?id={uuid}&re={rfc_emisor}&rr={rfc_receptor}&tt={total_str}"


def get_status_display_name(status: str) -> str:
    """
    Retorna el nombre legible de un estatus

    Args:
        status: Status code

    Returns:
        Nombre legible en español
    """
    status_names = {
        SATCFDIVerifier.STATUS_VIGENTE: "Vigente",
        SATCFDIVerifier.STATUS_CANCELADO: "Cancelado",
        SATCFDIVerifier.STATUS_SUSTITUIDO: "Sustituido",
        SATCFDIVerifier.STATUS_POR_CANCELAR: "Por Cancelar",
        SATCFDIVerifier.STATUS_NO_ENCONTRADO: "No Encontrado",
        SATCFDIVerifier.STATUS_ERROR: "Error en Verificación"
    }

    return status_names.get(status, status)


def is_valid_for_deduction(status: str) -> bool:
    """
    Determina si un CFDI con este estatus es válido para deducción fiscal

    Args:
        status: Status del CFDI

    Returns:
        True si es válido para deducir
    """
    return status == SATCFDIVerifier.STATUS_VIGENTE
