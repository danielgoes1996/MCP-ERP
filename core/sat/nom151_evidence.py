"""
NOM-151 Evidence Generation System
===================================
Generación de evidencia digital para cumplimiento de NOM-151-SCFI-2016

La NOM-151 establece requisitos de conservación de mensajes de datos y digitalización
de documentos para efectos fiscales. Este módulo genera evidencia que demuestra:

1. Autenticidad: El documento es genuino y proviene de SAT
2. Integridad: El documento no ha sido alterado
3. Confiabilidad: El proceso de descarga es auditable
4. Disponibilidad: La evidencia puede presentarse ante auditorías

Referencias:
- NOM-151-SCFI-2016: https://www.dof.gob.mx/nota_detalle.php?codigo=5428455
- DOF 30/03/2016
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
import uuid


class NOM151EvidenceGenerator:
    """
    Generador de evidencia digital NOM-151

    Cada operación SAT (solicitud, descarga, procesamiento) genera evidencia
    que incluye:
    - Hash SHA-256 de los datos
    - Timestamp RFC 3339
    - Metadata del proceso
    - Firma digital (opcional)
    """

    @staticmethod
    def generate_request_evidence(
        rfc_solicitante: str,
        tipo_solicitud: str,
        fecha_inicial: datetime,
        fecha_final: datetime,
        request_uuid: str,
        sat_response: Dict[str, Any],
        filters: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Genera evidencia de una solicitud de descarga SAT

        Args:
            rfc_solicitante: RFC de quien solicita
            tipo_solicitud: CFDI o Metadata
            fecha_inicial: Fecha inicial de búsqueda
            fecha_final: Fecha final de búsqueda
            request_uuid: UUID asignado por SAT
            sat_response: Respuesta completa del SAT
            filters: Filtros aplicados (rfc_emisor, rfc_receptor, etc.)

        Returns:
            Diccionario con evidencia NOM-151
        """
        timestamp = datetime.utcnow()

        # Datos del request
        request_data = {
            'rfc_solicitante': rfc_solicitante,
            'tipo_solicitud': tipo_solicitud,
            'fecha_inicial': fecha_inicial.isoformat(),
            'fecha_final': fecha_final.isoformat(),
            'request_uuid': request_uuid,
            'timestamp': timestamp.isoformat(),
        }

        if filters:
            request_data['filters'] = filters

        # Hash de los datos
        data_string = json.dumps(request_data, sort_keys=True)
        data_hash = hashlib.sha256(data_string.encode()).hexdigest()

        # Evidencia completa
        evidence = {
            # Identificación
            'evidence_id': str(uuid.uuid4()),
            'evidence_type': 'SAT_DESCARGA_SOLICITUD',
            'norm': 'NOM-151-SCFI-2016',

            # Timestamp
            'created_at': timestamp.isoformat(),
            'timezone': 'UTC',

            # Datos del evento
            'event': {
                'operation': 'solicitar_descarga',
                'rfc_solicitante': rfc_solicitante,
                'tipo_solicitud': tipo_solicitud,
                'periodo': {
                    'inicio': fecha_inicial.isoformat(),
                    'fin': fecha_final.isoformat()
                },
                'filters': filters or {}
            },

            # Respuesta SAT
            'sat_response': {
                'request_uuid': request_uuid,
                'codigo_estatus': sat_response.get('codigo_estatus'),
                'mensaje': sat_response.get('mensaje'),
                'timestamp_sat': sat_response.get('timestamp')
            },

            # Integridad
            'integrity': {
                'algorithm': 'SHA-256',
                'hash': data_hash,
                'data_serialization': 'JSON'
            },

            # Metadata
            'metadata': {
                'system': 'ContaFlow Backend',
                'version': '3.1',
                'environment': 'production'
            }
        }

        return evidence

    @staticmethod
    def generate_download_evidence(
        rfc_solicitante: str,
        package_uuid: str,
        zip_content: bytes,
        xml_count: int,
        sat_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Genera evidencia de descarga de paquete SAT

        Args:
            rfc_solicitante: RFC de quien descarga
            package_uuid: UUID del paquete
            zip_content: Contenido del ZIP descargado
            xml_count: Número de XMLs en el paquete
            sat_response: Respuesta del SAT

        Returns:
            Diccionario con evidencia NOM-151
        """
        timestamp = datetime.utcnow()

        # Hash del ZIP completo
        zip_hash = hashlib.sha256(zip_content).hexdigest()

        # Hash SHA-256 del contenido (para verificar integridad)
        zip_size = len(zip_content)

        evidence = {
            # Identificación
            'evidence_id': str(uuid.uuid4()),
            'evidence_type': 'SAT_DESCARGA_PAQUETE',
            'norm': 'NOM-151-SCFI-2016',

            # Timestamp
            'created_at': timestamp.isoformat(),
            'timezone': 'UTC',

            # Datos del evento
            'event': {
                'operation': 'descargar_paquete',
                'rfc_solicitante': rfc_solicitante,
                'package_uuid': package_uuid,
                'xml_count': xml_count
            },

            # Archivo descargado
            'file': {
                'size_bytes': zip_size,
                'format': 'application/zip',
                'hash_algorithm': 'SHA-256',
                'hash': zip_hash
            },

            # Respuesta SAT
            'sat_response': {
                'package_uuid': package_uuid,
                'mensaje': sat_response.get('mensaje'),
                'timestamp_sat': sat_response.get('timestamp')
            },

            # Metadata
            'metadata': {
                'system': 'ContaFlow Backend',
                'version': '3.1',
                'environment': 'production'
            }
        }

        return evidence

    @staticmethod
    def generate_processing_evidence(
        package_id: int,
        package_uuid: str,
        xml_files: list,
        processing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Genera evidencia del procesamiento de XMLs de un paquete

        Args:
            package_id: ID interno del paquete
            package_uuid: UUID SAT del paquete
            xml_files: Lista de archivos XML procesados
            processing_result: Resultado del procesamiento

        Returns:
            Diccionario con evidencia NOM-151
        """
        timestamp = datetime.utcnow()

        # Generar hash de cada XML
        xml_hashes = []
        for xml_file in xml_files:
            xml_hash = hashlib.sha256(xml_file['content'].encode()).hexdigest()
            xml_hashes.append({
                'filename': xml_file['filename'],
                'uuid': xml_file.get('uuid'),
                'hash': xml_hash,
                'size': len(xml_file['content'])
            })

        evidence = {
            # Identificación
            'evidence_id': str(uuid.uuid4()),
            'evidence_type': 'SAT_PROCESAMIENTO_CFDI',
            'norm': 'NOM-151-SCFI-2016',

            # Timestamp
            'created_at': timestamp.isoformat(),
            'timezone': 'UTC',

            # Datos del evento
            'event': {
                'operation': 'procesar_paquete',
                'package_id': package_id,
                'package_uuid': package_uuid,
                'total_xmls': len(xml_files)
            },

            # XMLs procesados
            'cfdi_documents': xml_hashes,

            # Resultado del procesamiento
            'processing': {
                'inserted': processing_result.get('inserted', 0),
                'duplicates': processing_result.get('duplicates', 0),
                'errors': processing_result.get('errors', 0),
                'total': len(xml_files)
            },

            # Metadata
            'metadata': {
                'system': 'ContaFlow Backend',
                'version': '3.1',
                'environment': 'production'
            }
        }

        return evidence

    @staticmethod
    def generate_error_evidence(
        operation: str,
        error_type: str,
        error_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Genera evidencia de errores durante operaciones SAT

        Args:
            operation: Operación que falló (solicitar, verificar, descargar)
            error_type: Tipo de error
            error_message: Mensaje de error
            context: Contexto del error

        Returns:
            Diccionario con evidencia NOM-151
        """
        timestamp = datetime.utcnow()

        evidence = {
            # Identificación
            'evidence_id': str(uuid.uuid4()),
            'evidence_type': 'SAT_ERROR',
            'norm': 'NOM-151-SCFI-2016',

            # Timestamp
            'created_at': timestamp.isoformat(),
            'timezone': 'UTC',

            # Error
            'error': {
                'operation': operation,
                'type': error_type,
                'message': error_message,
                'context': context
            },

            # Metadata
            'metadata': {
                'system': 'ContaFlow Backend',
                'version': '3.1',
                'environment': 'production'
            }
        }

        return evidence

    @staticmethod
    def verify_evidence_integrity(evidence: Dict[str, Any], original_data: str) -> bool:
        """
        Verifica la integridad de una evidencia

        Args:
            evidence: Evidencia a verificar
            original_data: Datos originales (JSON string)

        Returns:
            True si la evidencia es válida
        """
        if 'integrity' not in evidence:
            return False

        integrity = evidence['integrity']
        algorithm = integrity.get('algorithm')

        if algorithm != 'SHA-256':
            return False

        # Recalcular hash
        calculated_hash = hashlib.sha256(original_data.encode()).hexdigest()
        stored_hash = integrity.get('hash')

        return calculated_hash == stored_hash

    @staticmethod
    def generate_audit_report(
        request_id: int,
        evidences: list
    ) -> Dict[str, Any]:
        """
        Genera reporte de auditoría con todas las evidencias

        Args:
            request_id: ID de la solicitud SAT
            evidences: Lista de evidencias generadas

        Returns:
            Reporte de auditoría completo
        """
        timestamp = datetime.utcnow()

        # Consolidar evidencias
        evidence_summary = {
            'total_evidences': len(evidences),
            'types': {}
        }

        for evidence in evidences:
            evidence_type = evidence.get('evidence_type', 'unknown')
            if evidence_type not in evidence_summary['types']:
                evidence_summary['types'][evidence_type] = 0
            evidence_summary['types'][evidence_type] += 1

        report = {
            'report_id': str(uuid.uuid4()),
            'report_type': 'NOM151_AUDIT_TRAIL',
            'generated_at': timestamp.isoformat(),

            # Solicitud SAT
            'sat_request': {
                'request_id': request_id,
                'total_evidences': len(evidences)
            },

            # Resumen
            'summary': evidence_summary,

            # Evidencias completas
            'evidences': evidences,

            # Firma del reporte
            'signature': {
                'algorithm': 'SHA-256',
                'hash': hashlib.sha256(
                    json.dumps(evidences, sort_keys=True).encode()
                ).hexdigest()
            },

            # Metadata
            'metadata': {
                'system': 'ContaFlow Backend',
                'version': '3.1',
                'norm': 'NOM-151-SCFI-2016',
                'purpose': 'Auditoría fiscal SAT'
            }
        }

        return report


# ========================================
# Utility Functions
# ========================================

def save_evidence_to_json(evidence: Dict[str, Any], filepath: str):
    """Guarda evidencia en archivo JSON"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)


def load_evidence_from_json(filepath: str) -> Dict[str, Any]:
    """Carga evidencia desde archivo JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
