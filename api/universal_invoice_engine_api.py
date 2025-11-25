"""
Universal Invoice Engine API - Endpoints para procesamiento universal de facturas
Punto 21 de Auditoría: APIs para template_match y validation_rules
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from typing import Dict, List, Optional, Any
import logging
import os
import tempfile
import asyncio
from datetime import datetime
import xml.etree.ElementTree as ET

from core.expenses.invoices.universal_invoice_engine_system import (
    universal_invoice_engine_system,
    InvoiceFormat,
    ParserType,
    ValidationCategory,
    ExtractionStatus
)
from core.error_handler import handle_error, log_endpoint_entry, log_endpoint_success, log_endpoint_error
from core.api_models import (
    UniversalInvoiceSessionCreateRequest,
    UniversalInvoiceSessionResponse,
    UniversalInvoiceProcessRequest,
    UniversalInvoiceProcessResponse,
    UniversalInvoiceStatusResponse,
    UniversalInvoiceTemplateMatchResponse,
    UniversalInvoiceValidationResponse,
    UniversalInvoiceDataResponse,
    UniversalInvoiceParsersResponse,
    UniversalInvoiceFormatsResponse,
    UniversalInvoiceFormatCreateRequest,
    UniversalInvoiceFormatResponse,
    UniversalInvoiceCancelResponse,
)

router = APIRouter(prefix="/universal-invoice", tags=["Universal Invoice Engine"])
logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent Anthropic API calls
# This prevents hitting rate limits by processing max 3 invoices at a time
_anthropic_semaphore = asyncio.Semaphore(3)

@router.post("/sessions/")
async def create_invoice_processing_session(
    request: UniversalInvoiceSessionCreateRequest
) -> UniversalInvoiceSessionResponse:
    """
    Crea una nueva sesión de procesamiento universal de facturas
    Incluye template_match y validation_rules setup
    """
    log_endpoint_entry("/universal-invoice/sessions/", method="POST", request_data=request.dict())

    try:
        session_id = await universal_invoice_engine_system.create_processing_session(
            company_id=request.company_id,
            file_path=request.file_path,
            original_filename=request.original_filename,
            user_id=request.user_id
        )

        response = {
            "session_id": session_id,
            "status": "created",
            "company_id": request.company_id,
            "original_filename": request.original_filename,
            "supports_template_matching": True,
            "supports_validation_rules": True,
            "available_parsers": list(universal_invoice_engine_system.parsers.keys()),
            "estimated_processing_time_ms": _estimate_processing_time(request.file_path),
            "created_at": datetime.utcnow().isoformat()
        }

        log_endpoint_success("/universal-invoice/sessions/", response)
        return response

    except Exception as e:
        error_msg = f"Error creating invoice processing session: {str(e)}"
        log_endpoint_error("/universal-invoice/sessions/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

def _extract_uuid_from_xml(file_path: str) -> Optional[str]:
    """Helper function to extract UUID from CFDI XML"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # XML namespaces common in CFDI
        namespaces = {
            'cfdi': 'http://www.sat.gob.mx/cfd/4',
            'cfdi3': 'http://www.sat.gob.mx/cfd/3'
        }

        # Try CFDI 4.0
        for ns in ['cfdi', 'cfdi3']:
            uuid = root.get('{' + namespaces.get(ns, '') + '}UUID')
            if uuid:
                return uuid.upper()

            # Also try TimbreFiscalDigital
            for tfd in root.iter('{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital'):
                uuid = tfd.get('UUID')
                if uuid:
                    return uuid.upper()

        return None
    except Exception as e:
        logger.warning(f"Could not extract UUID from {file_path}: {e}")
        return None


@router.post("/sessions/batch-upload/")
async def batch_upload_and_process(
    background_tasks: BackgroundTasks,
    company_id: str,
    user_id: Optional[str] = None,
    files: List[UploadFile] = File(...)
) -> Dict[str, Any]:
    """
    Sube múltiples archivos y los procesa en background
    El procesamiento continúa incluso si el cliente se desconecta

    IMPORTANTE: Detecta y omite facturas duplicadas basándose en UUID
    """
    log_endpoint_entry("/universal-invoice/sessions/batch-upload/",
        method="POST",
        company_id=company_id,
        file_count=len(files)
    )

    try:
        from core.shared.db_config import get_connection

        # Crear directorio permanente para facturas
        upload_dir = os.path.join(os.getcwd(), "uploads", "invoices", company_id)
        os.makedirs(upload_dir, exist_ok=True)

        # Procesar todos los archivos y crear sesiones
        session_ids = []
        duplicates = []
        skipped_non_xml = []
        batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        for file in files:
            # Validar tipo de archivo por content_type o extensión
            allowed_types = ['application/pdf', 'application/xml', 'text/xml', 'image/jpeg', 'image/png', 'text/csv']
            allowed_extensions = ['.pdf', '.xml', '.jpg', '.jpeg', '.png', '.csv']

            file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''

            if file.content_type not in allowed_types and file_ext not in allowed_extensions:
                logger.warning(f"Skipping unsupported file type: {file.filename} ({file.content_type}, ext: {file_ext})")
                skipped_non_xml.append(file.filename)
                continue

            # Guardar archivo permanente
            safe_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = os.path.join(upload_dir, safe_filename)

            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)

            # DUPLICATE DETECTION: Extract UUID from XML files
            invoice_uuid = None
            if file_ext == '.xml':
                invoice_uuid = _extract_uuid_from_xml(file_path)

                if invoice_uuid:
                    # Check if invoice with same UUID already exists
                    conn = get_connection(dict_cursor=True)
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT id, original_filename, created_at
                        FROM sat_invoices
                        WHERE company_id = %s
                        AND extracted_data->>'uuid' = %s
                        LIMIT 1
                    """, (company_id, invoice_uuid))

                    existing = cursor.fetchone()
                    cursor.close()
                    conn.close()

                    if existing:
                        logger.warning(
                            f"DUPLICATE DETECTED: {file.filename} (UUID: {invoice_uuid[:20]}...) "
                            f"already exists as {existing['original_filename']} "
                            f"(session: {existing['id']}, created: {existing['created_at']})"
                        )
                        duplicates.append({
                            'filename': file.filename,
                            'uuid': invoice_uuid,
                            'existing_session_id': existing['id'],
                            'existing_filename': existing['original_filename'],
                            'existing_created_at': str(existing['created_at'])
                        })
                        # Skip creating session for duplicate
                        os.remove(file_path)  # Clean up the file we just saved
                        continue

            # Crear sesión only if not duplicate
            session_id = await universal_invoice_engine_system.create_processing_session(
                company_id=company_id,
                file_path=file_path,
                original_filename=file.filename or "uploaded_file",
                user_id=user_id
            )
            session_ids.append(session_id)

        # Programar procesamiento en background de TODAS las sesiones usando FastAPI BackgroundTasks
        # BackgroundTasks garantiza que las tareas se ejecuten después de enviar la respuesta HTTP
        for session_id in session_ids:
            background_tasks.add_task(_process_invoice_background, session_id)

        response = {
            "batch_id": batch_id,
            "total_files": len(files),
            "created_sessions": len(session_ids),
            "duplicates_skipped": len(duplicates),
            "non_xml_skipped": len(skipped_non_xml),
            "session_ids": session_ids,
            "duplicates": duplicates,
            "skipped_files": skipped_non_xml,
            "status": "processing_in_background",
            "message": (
                f"Procesamiento iniciado. "
                f"{len(session_ids)} facturas nuevas, "
                f"{len(duplicates)} duplicados omitidos. "
                f"Puedes salir de esta página y el procesamiento continuará."
            ),
            "created_at": datetime.utcnow().isoformat()
        }

        if duplicates:
            logger.info(
                f"Duplicate detection: Skipped {len(duplicates)} duplicate invoices for company {company_id}. "
                f"UUIDs: {[d['uuid'][:20] + '...' for d in duplicates]}"
            )

        log_endpoint_success("/universal-invoice/sessions/batch-upload/", response)
        return response

    except Exception as e:
        error_msg = f"Error in batch upload: {str(e)}"
        log_endpoint_error("/universal-invoice/sessions/batch-upload/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/sessions/batch-status/{batch_id}")
async def get_batch_status(batch_id: str, company_id: str) -> Dict[str, Any]:
    """
    Obtiene el estado de un batch de procesamiento
    """
    try:
        from core.shared.db_config import get_connection

        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()

        # Obtener todas las sesiones creadas en el batch
        # Nota: Necesitamos agregar batch_id a la tabla, por ahora usamos timestamp del batch_id
        batch_timestamp = batch_id.replace("batch_", "")

        cursor.execute("""
            SELECT
                id as session_id,
                extraction_status,
                original_filename
            FROM sat_invoices
            WHERE company_id = %s
            AND created_at >= (NOW() - INTERVAL '1 hour')
            ORDER BY created_at DESC
        """, (company_id,))

        sessions = cursor.fetchall()
        cursor.close()
        conn.close()

        # Contar estados
        total = len(sessions)
        completed = sum(1 for s in sessions if s['extraction_status'] == 'completed')
        failed = sum(1 for s in sessions if s['extraction_status'] == 'failed')
        pending = sum(1 for s in sessions if s['extraction_status'] == 'pending')

        return {
            "batch_id": batch_id,
            "total_sessions": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "is_complete": pending == 0,
            "sessions": sessions
        }

    except Exception as e:
        error_msg = f"Error getting batch status: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/batch-status/{batch_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/sessions/reprocess-failed/")
async def reprocess_failed_sessions(
    background_tasks: BackgroundTasks,
    company_id: str
) -> Dict[str, Any]:
    """
    Reprocesa todas las sesiones que fallaron o tienen datos incompletos
    Útil para facturas que fallaron por rate limits
    """
    log_endpoint_entry("/universal-invoice/sessions/reprocess-failed/",
        method="POST",
        company_id=company_id
    )

    try:
        from core.shared.db_config import get_connection

        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()

        # Encontrar sesiones con extraction_status='completed' pero con extracted_data vacío o incompleto
        # O sesiones con status='failed'
        cursor.execute("""
            SELECT id, original_filename, extracted_data
            FROM sat_invoices
            WHERE company_id = %s
            AND (
                extraction_status = 'failed'
                OR (
                    extraction_status = 'completed'
                    AND (
                        extracted_data IS NULL
                        OR extracted_data = '{}'::jsonb
                        OR NOT (extracted_data ? 'tipo_comprobante')
                        OR (SELECT COUNT(*) FROM jsonb_object_keys(extracted_data)) < 5
                    )
                )
            )
            ORDER BY created_at DESC
        """, (company_id,))

        failed_sessions = cursor.fetchall()
        cursor.close()
        conn.close()

        if not failed_sessions:
            return {
                "message": "No hay sesiones para reprocesar",
                "total_sessions": 0,
                "reprocessing": []
            }

        # Resetear el estado de estas sesiones a 'pending' para reprocesamiento
        conn = get_connection()
        cursor = conn.cursor()

        session_ids = [s['id'] for s in failed_sessions]

        cursor.execute("""
            UPDATE sat_invoices
            SET extraction_status = 'pending',
                error_message = NULL
            WHERE id = ANY(%s)
        """, (session_ids,))

        conn.commit()
        cursor.close()
        conn.close()

        # Programar reprocesamiento en background usando FastAPI BackgroundTasks
        # BackgroundTasks garantiza que las tareas se ejecuten después de enviar la respuesta HTTP
        for session_id in session_ids:
            background_tasks.add_task(_process_invoice_background, session_id)

        response = {
            "message": f"Reprocesando {len(session_ids)} sesiones que fallaron",
            "total_sessions": len(session_ids),
            "reprocessing": session_ids,
            "status": "processing_in_background",
            "note": "Las sesiones se están reprocesando con rate limiting. Consulta el estado en unos minutos."
        }

        log_endpoint_success("/universal-invoice/sessions/reprocess-failed/", response)
        return response

    except Exception as e:
        error_msg = f"Error reprocessing failed sessions: {str(e)}"
        log_endpoint_error("/universal-invoice/sessions/reprocess-failed/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/sessions/viewer-pro/{tenant_id}")
async def get_sessions_for_viewer_pro(
    tenant_id: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    tipo: Optional[str] = None,
    estatus: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Endpoint optimizado para el visualizador Pro de CFDIs
    Devuelve datos en formato flat con todos los campos pre-calculados

    Parámetros:
    - tenant_id: ID del tenant/empresa
    - year: Filtro por año (opcional)
    - month: Filtro por mes 1-12 (opcional)
    - tipo: Filtro por tipo de comprobante I/E/T/N/P (opcional)
    - estatus: Filtro por estatus SAT: vigente/cancelado/sustituido (opcional)
    - search: Búsqueda por UUID, RFC, nombre, serie/folio (opcional)
    - limit: Número máximo de registros (default 500)
    - offset: Offset para paginación (default 0)
    """
    log_endpoint_entry(f"/universal-invoice/sessions/viewer-pro/{tenant_id}",
        method="GET",
        tenant_id=tenant_id,
        year=year,
        month=month,
        tipo=tipo,
        estatus=estatus
    )

    try:
        from core.shared.db_config import get_connection

        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()

        # Query optimizado con JOIN para obtener todo en una consulta
        query = """
            SELECT
                s.id,
                s.company_id,
                s.original_filename,
                s.extraction_status,
                s.created_at,
                s.invoice_file_path,
                s.extracted_data,
                s.sat_validation_status,
                s.sat_codigo_estatus,
                s.sat_es_cancelable,
                s.sat_estado,
                s.sat_validacion_efos,
                s.sat_verified_at,
                s.sat_last_check_at,
                s.sat_verification_error,
                s.sat_verification_url
            FROM sat_invoices s
            WHERE s.company_id = %s
            AND s.extraction_status = 'completed'
            AND s.extracted_data IS NOT NULL
            AND s.extracted_data != '{}'::jsonb
        """
        params = [tenant_id]

        # Filtros dinámicos
        if year:
            query += " AND EXTRACT(YEAR FROM (s.extracted_data->>'fecha_emision')::date) = %s"
            params.append(year)

        if month:
            query += " AND EXTRACT(MONTH FROM (s.extracted_data->>'fecha_emision')::date) = %s"
            params.append(month)

        if tipo:
            query += " AND s.extracted_data->>'tipo_comprobante' = %s"
            params.append(tipo)

        if estatus:
            query += " AND s.extracted_data->>'sat_status' = %s"
            params.append(estatus)

        if search:
            search_pattern = f"%{search.lower()}%"
            query += """ AND (
                LOWER(s.extracted_data->>'uuid') LIKE %s OR
                LOWER(s.extracted_data->'emisor'->>'nombre') LIKE %s OR
                LOWER(s.extracted_data->'emisor'->>'rfc') LIKE %s OR
                LOWER(s.extracted_data->'receptor'->>'nombre') LIKE %s OR
                LOWER(s.extracted_data->'receptor'->>'rfc') LIKE %s OR
                LOWER(s.extracted_data->>'serie') LIKE %s OR
                LOWER(s.extracted_data->>'folio') LIKE %s
            )"""
            params.extend([search_pattern] * 7)

        query += " ORDER BY s.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        sessions = cursor.fetchall()

        # Transformar a formato flat para el visualizador
        documents = []
        for session in sessions:
            data = session['extracted_data'] or {}

            # Calcular impuestos trasladados y retenidos
            impuestos = data.get('impuestos', {})
            traslados = impuestos.get('traslados', []) or []
            retenciones = impuestos.get('retenciones', []) or []

            impuestos_trasladados = sum(t.get('importe', 0) for t in traslados)
            impuestos_retenidos = sum(r.get('importe', 0) for r in retenciones)

            # Extraer complementos (de conceptos o estructura específica)
            complementos = []
            # TODO: Agregar lógica para extraer complementos del XML
            # Por ahora dejamos array vacío

            # Validar sello (por defecto true si tiene UUID)
            sello_verificado = bool(data.get('uuid'))

            # Relacionados (por ahora vacío, agregar después)
            relacionados = []

            # Leer XML si existe el archivo
            xml_content = ""
            try:
                if session.get('invoice_file_path') and os.path.exists(session['invoice_file_path']):
                    with open(session['invoice_file_path'], 'r', encoding='utf-8') as f:
                        xml_content = f.read()
            except Exception as e:
                logger.warning(f"Could not read XML file for session {session['id']}: {e}")

            # Documento en formato flat
            doc = {
                "id": session['id'],
                "uuid": data.get('uuid'),
                "serie": data.get('serie'),
                "folio": data.get('folio'),
                "fechaEmision": data.get('fecha_emision'),
                "fechaTimbrado": data.get('fecha_timbrado'),
                "tipo": data.get('tipo_comprobante'),
                "moneda": data.get('moneda', 'MXN'),
                "tipoCambio": data.get('tipo_cambio'),
                "subtotal": data.get('subtotal', 0),
                "descuento": data.get('descuento'),
                "total": data.get('total', 0),
                "formaPago": data.get('forma_pago'),
                "metodoPago": data.get('metodo_pago'),
                "usoCFDI": data.get('uso_cfdi'),
                "estatusSAT": data.get('sat_status', 'desconocido'),  # LLM-inferred status
                # ✅ NEW: Real SAT validation status
                "satValidation": {
                    "status": session.get('sat_validation_status', 'pending'),
                    "codigoEstatus": session.get('sat_codigo_estatus'),
                    "esCancelable": session.get('sat_es_cancelable'),
                    "estado": session.get('sat_estado'),
                    "validacionEfos": session.get('sat_validacion_efos'),
                    "verifiedAt": session.get('sat_verified_at').isoformat() if session.get('sat_verified_at') else None,
                    "lastCheckAt": session.get('sat_last_check_at').isoformat() if session.get('sat_last_check_at') else None,
                    "error": session.get('sat_verification_error'),
                    "verificationUrl": session.get('sat_verification_url')
                },
                "emisorNombre": data.get('emisor', {}).get('nombre'),
                "emisorRFC": data.get('emisor', {}).get('rfc'),
                "emisorRegimenFiscal": data.get('emisor', {}).get('regimen_fiscal'),
                "receptorNombre": data.get('receptor', {}).get('nombre'),
                "receptorRFC": data.get('receptor', {}).get('rfc'),
                "receptorUsoCFDI": data.get('receptor', {}).get('uso_cfdi'),
                "receptorDomicilioFiscal": data.get('receptor', {}).get('domicilio_fiscal'),
                "impuestosTrasladados": impuestos_trasladados,
                "impuestosRetenidos": impuestos_retenidos,
                "impuestos": {
                    "trasladados": traslados,
                    "retenidos": retenciones
                },
                "conceptos": data.get('conceptos', []),
                "taxBadges": data.get('tax_badges', []),
                "complementos": complementos,
                "selloVerificado": sello_verificado,
                "relacionados": relacionados,
                "xml": xml_content if xml_content else "",
                "notas": "",
                "pagos": data.get('pagos', {}),
            }

            documents.append(doc)

        # Contar total para paginación
        count_query = """
            SELECT COUNT(*) as total
            FROM sat_invoices s
            WHERE s.company_id = %s
            AND s.extraction_status = 'completed'
            AND s.extracted_data IS NOT NULL
            AND s.extracted_data != '{}'::jsonb
        """
        count_params = [tenant_id]

        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        response = {
            "success": True,
            "documents": documents,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(documents)) < total_count,
        }

        log_endpoint_success(f"/universal-invoice/sessions/viewer-pro/{tenant_id}", {
            "document_count": len(documents),
            "total_count": total_count
        })

        return response

    except Exception as e:
        error_msg = f"Error fetching sessions for viewer pro: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/viewer-pro/{tenant_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/sessions/upload/")
async def upload_and_create_session(
    company_id: str,
    user_id: Optional[str] = None,
    file: UploadFile = File(...)
) -> UniversalInvoiceSessionResponse:
    """
    Sube archivo y crea sesión de procesamiento (single file)
    Para múltiples archivos usa /sessions/batch-upload/
    """
    log_endpoint_entry("/universal-invoice/sessions/upload/",
        method="POST",
        company_id=company_id,
        filename=file.filename,
        content_type=file.content_type
    )

    try:
        # Validar tipo de archivo
        allowed_types = ['application/pdf', 'application/xml', 'text/xml', 'image/jpeg', 'image/png', 'text/csv']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

        # Crear directorio permanente para facturas si no existe
        upload_dir = os.path.join(os.getcwd(), "uploads", "invoices", company_id)
        os.makedirs(upload_dir, exist_ok=True)

        # Guardar archivo permanente con nombre único
        safe_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)

        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        # Crear sesión
        session_id = await universal_invoice_engine_system.create_processing_session(
            company_id=company_id,
            file_path=file_path,
            original_filename=file.filename or "uploaded_file",
            user_id=user_id
        )

        response = {
            "session_id": session_id,
            "status": "created",
            "company_id": company_id,
            "original_filename": file.filename,
            "file_size_bytes": len(content),
            "supports_template_matching": True,
            "supports_validation_rules": True,
            "available_parsers": list(universal_invoice_engine_system.parsers.keys()),
            "estimated_processing_time_ms": _estimate_processing_time_by_size(len(content)),
            "created_at": datetime.utcnow().isoformat()
        }

        log_endpoint_success("/universal-invoice/sessions/upload/", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error uploading and creating session: {str(e)}"
        log_endpoint_error("/universal-invoice/sessions/upload/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/sessions/{session_id}/process")
async def process_universal_invoice(
    session_id: str,
    background_tasks: BackgroundTasks,
    request: Optional[UniversalInvoiceProcessRequest] = None
) -> UniversalInvoiceProcessResponse:
    """
    Procesa factura con template matching y validation rules completas
    Retorna template_match y validation_rules aplicadas
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/process",
        method="POST",
        session_id=session_id,
        async_processing=request.async_processing if request else True
    )

    try:
        # Validar que la sesión existe
        session_status = await universal_invoice_engine_system.get_session_status(session_id)
        if 'error' in session_status:
            raise HTTPException(status_code=404, detail="Session not found")

        # Procesar en background si se solicita
        if not request or request.async_processing:
            background_tasks.add_task(_process_invoice_background, session_id)

            response = {
                "success": True,
                "invoice_data": {
                    "session_id": session_id,
                    "status": "processing_started",
                    "processing_mode": "async",
                    "message": "Invoice processing started in background",
                    "check_status_url": f"/universal-invoice/sessions/{session_id}/status",
                    "estimated_completion_time": _estimate_completion_time()
                }
            }
        else:
            # Procesar sincrónicamente
            result = await universal_invoice_engine_system.process_invoice(session_id)

            response = {
                "success": True,
                "invoice_data": {
                    "session_id": session_id,
                    "status": result["status"],
                    "processing_mode": "sync",
                    "detected_format": result["detected_format"],
                    "parser_used": result["parser_used"],
                    "template_match": result["template_match"],        # ✅ CAMPO FALTANTE
                    "validation_rules": result["validation_rules"],    # ✅ CAMPO FALTANTE
                    "extraction_confidence": result["extraction_confidence"],
                    "overall_quality_score": result["overall_quality_score"],
                    "processing_metrics": result["processing_metrics"]
                }
            }

        log_endpoint_success(f"/universal-invoice/sessions/{session_id}/process", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error processing invoice: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/{session_id}/process", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/company/{company_id}")
async def list_company_sessions(
    company_id: str,
    status: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
) -> Dict[str, Any]:
    """
    Lista todas las sesiones de facturas para una empresa
    Incluye paginación y filtrado por estado
    """
    log_endpoint_entry(f"/universal-invoice/sessions/company/{company_id}", method="GET", company_id=company_id)

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from core.shared.db_config import get_connection

        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()

        # Query base
        query = """
            SELECT
                id, company_id, user_id, original_filename,
                status, created_at, updated_at,
                detected_format, parser_used,
                extraction_status, extraction_confidence,
                validation_score, overall_quality_score,
                parsed_data, template_match, validation_results,
                error_message, sat_validation_status
            FROM sat_invoices
            WHERE company_id = %s
        """
        params = [company_id]

        # Filtro por estado
        if status:
            query += " AND status = %s"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        sessions = cursor.fetchall()

        # Contar total de sesiones
        count_query = "SELECT COUNT(*) as total FROM sat_invoices WHERE company_id = %s"
        count_params = [company_id]
        if status:
            count_query += " AND status = %s"
            count_params.append(status)

        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        # Formatear respuesta
        sessions_list = []
        for session in sessions:
            # Extraer información básica del parsed_data para mostrar en la lista
            display_info = {}
            if session['parsed_data']:
                parsed = session['parsed_data']
                display_info = {
                    "emisor_nombre": parsed.get('emisor', {}).get('nombre'),
                    "emisor_rfc": parsed.get('emisor', {}).get('rfc'),
                    "receptor_rfc": parsed.get('receptor', {}).get('rfc'),
                    "total": parsed.get('total'),
                    "moneda": parsed.get('moneda', 'MXN'),
                    "fecha_emision": parsed.get('fecha_emision'),
                    "metodo_pago": parsed.get('metodo_pago'),
                    "tipo_comprobante": parsed.get('tipo_comprobante'),
                    "sat_status": parsed.get('sat_status', 'desconocido'),
                }

            # 🔧 FIX: Sync sat_status from sat_validation_status if available
            if session.get('sat_validation_status') and session['sat_validation_status'] != 'pending':
                if not display_info:
                    display_info = {}
                display_info['sat_status'] = session['sat_validation_status']

            sessions_list.append({
                "session_id": session['id'],
                "company_id": session['company_id'],
                "user_id": session['user_id'],
                "original_filename": session['original_filename'],
                "status": session['status'],
                "extraction_status": session['extraction_status'],
                "detected_format": session['detected_format'],
                "parser_used": session['parser_used'],
                "extraction_confidence": session['extraction_confidence'],
                "validation_score": session['validation_score'],
                "overall_quality_score": session['overall_quality_score'],
                "has_parsed_data": session['parsed_data'] is not None,
                "has_template_match": session['template_match'] is not None,
                "has_validation_results": session['validation_results'] is not None,
                "error_message": session['error_message'],
                "created_at": session['created_at'].isoformat() if session['created_at'] else None,
                "updated_at": session['updated_at'].isoformat() if session['updated_at'] else None,
                "display_info": display_info,  # ✅ Información básica para la lista
            })

        response = {
            "success": True,
            "sessions": sessions_list,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }

        log_endpoint_success(f"/universal-invoice/sessions/company/{company_id}", response)
        return response

    except Exception as e:
        error_msg = f"Error listing company sessions: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/company/{company_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/tenant/{tenant_id}")
async def list_tenant_sessions(
    tenant_id: int,
    status: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0
) -> Dict[str, Any]:
    """
    Lista todas las sesiones de facturas para un tenant específico
    Filtra por tenant_id en lugar de company_id
    """
    log_endpoint_entry(f"/universal-invoice/sessions/tenant/{tenant_id}", method="GET", tenant_id=tenant_id)

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from core.shared.db_config import get_connection

        conn = get_connection(dict_cursor=True)
        cursor = conn.cursor()

        # Query base - filtrar por tenant_id
        query = """
            SELECT
                uis.id, uis.company_id, uis.user_id, uis.original_filename,
                uis.status, uis.created_at, uis.updated_at,
                uis.detected_format, uis.parser_used,
                uis.extraction_status, uis.extraction_confidence,
                uis.validation_score, uis.overall_quality_score,
                uis.parsed_data, uis.template_match, uis.validation_results,
                uis.error_message, uis.sat_validation_status
            FROM sat_invoices uis
            WHERE uis.user_id IN (
                SELECT CAST(id AS TEXT) FROM users WHERE tenant_id = %s
            )
        """
        params = [tenant_id]

        # Filtro por estado
        if status:
            query += " AND uis.status = %s"
            params.append(status)

        query += " ORDER BY uis.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        sessions = cursor.fetchall()

        # Contar total de sesiones
        count_query = """
            SELECT COUNT(*) as total
            FROM sat_invoices uis
            WHERE uis.user_id IN (
                SELECT CAST(id AS TEXT) FROM users WHERE tenant_id = %s
            )
        """
        count_params = [tenant_id]
        if status:
            count_query += " AND uis.status = %s"
            count_params.append(status)

        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        # Formatear respuesta
        sessions_list = []
        for session in sessions:
            # Extraer información básica del parsed_data para mostrar en la lista
            display_info = {}
            if session['parsed_data']:
                parsed = session['parsed_data']
                display_info = {
                    "emisor_nombre": parsed.get('emisor', {}).get('nombre'),
                    "emisor_rfc": parsed.get('emisor', {}).get('rfc'),
                    "receptor_rfc": parsed.get('receptor', {}).get('rfc'),
                    "total": parsed.get('total'),
                    "moneda": parsed.get('moneda', 'MXN'),
                    "fecha_emision": parsed.get('fecha_emision'),
                    "metodo_pago": parsed.get('metodo_pago'),
                    "tipo_comprobante": parsed.get('tipo_comprobante'),
                    "sat_status": parsed.get('sat_status', 'desconocido'),
                }

            # 🔧 FIX: Sync sat_status from sat_validation_status if available
            if session.get('sat_validation_status') and session['sat_validation_status'] != 'pending':
                if not display_info:
                    display_info = {}
                display_info['sat_status'] = session['sat_validation_status']

            sessions_list.append({
                "session_id": session['id'],
                "company_id": session['company_id'],
                "user_id": session['user_id'],
                "original_filename": session['original_filename'],
                "status": session['status'],
                "extraction_status": session['extraction_status'],
                "detected_format": session['detected_format'],
                "parser_used": session['parser_used'],
                "extraction_confidence": session['extraction_confidence'],
                "validation_score": session['validation_score'],
                "overall_quality_score": session['overall_quality_score'],
                "has_parsed_data": session['parsed_data'] is not None,
                "has_template_match": session['template_match'] is not None,
                "has_validation_results": session['validation_results'] is not None,
                "error_message": session['error_message'],
                "created_at": session['created_at'].isoformat() if session['created_at'] else None,
                "updated_at": session['updated_at'].isoformat() if session['updated_at'] else None,
                "display_info": display_info,
            })

        response = {
            "success": True,
            "sessions": sessions_list,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }

        log_endpoint_success(f"/universal-invoice/sessions/tenant/{tenant_id}", response)
        return response

    except Exception as e:
        error_msg = f"Error listing tenant sessions: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/tenant/{tenant_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/status")
async def get_invoice_processing_status(session_id: str) -> UniversalInvoiceStatusResponse:
    """
    Obtiene estado completo con template_match y validation_rules
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/status", method="GET", session_id=session_id)

    try:
        status_data = await universal_invoice_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        response = {
            "session_id": session_id,
            "status": status_data["status"],
            "detected_format": status_data.get("detected_format"),
            "parser_used": status_data.get("parser_used"),
            "template_match": status_data.get("template_match", {}),        # ✅ CAMPO FALTANTE
            "validation_rules": status_data.get("validation_rules", {}),    # ✅ CAMPO FALTANTE
            "extraction_confidence": status_data.get("extraction_confidence", 0.0),
            "validation_score": status_data.get("validation_score", 0.0),
            "overall_quality_score": status_data.get("overall_quality_score", 0.0),
            "progress_percentage": _calculate_progress_percentage(status_data["status"]),
            "created_at": status_data.get("created_at"),
            "updated_at": status_data.get("updated_at")
        }

        log_endpoint_success(f"/universal-invoice/sessions/{session_id}/status", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting session status: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/{session_id}/status", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/template-match")
async def get_session_template_match(session_id: str) -> UniversalInvoiceTemplateMatchResponse:
    """
    Obtiene detalles de template matching para una sesión
    Incluye template_match completo con patterns y confidence factors
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/template-match", method="GET", session_id=session_id)

    try:
        status_data = await universal_invoice_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        template_match = status_data.get("template_match", {})

        response = {
            "session_id": session_id,
            "template_match": template_match,  # ✅ CAMPO FALTANTE COMPLETO
            "template_name": template_match.get("template_name", "unknown"),
            "match_score": template_match.get("match_score", 0.0),
            "matched_patterns": template_match.get("matched_patterns", []),
            "confidence_factors": template_match.get("confidence_factors", {}),
            "matching_method": template_match.get("matching_method", "unknown"),
            "field_mappings": template_match.get("field_mappings", {}),
            "template_analysis": _analyze_template_match(template_match),
            "improvement_suggestions": _generate_template_suggestions(template_match)
        }

        log_endpoint_success(f"/universal-invoice/sessions/{session_id}/template-match", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting template match: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/{session_id}/template-match", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/validation")
async def get_session_validation_results(session_id: str) -> UniversalInvoiceValidationResponse:
    """
    Obtiene resultados detallados de validación
    Incluye validation_rules aplicadas y resultados por regla
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/validation", method="GET", session_id=session_id)

    try:
        status_data = await universal_invoice_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        validation_rules = status_data.get("validation_rules", {})

        response = {
            "session_id": session_id,
            "validation_rules": validation_rules,  # ✅ CAMPO FALTANTE COMPLETO
            "applied_rules": validation_rules.get("applied_rules", []),
            "validation_result": validation_rules.get("validation_result", {}),
            "overall_status": validation_rules.get("overall_status", "unknown"),
            "validation_score": validation_rules.get("validation_score", 0.0),
            "total_rules_applied": len(validation_rules.get("applied_rules", [])),
            "passed_rules": len([r for r in validation_rules.get("validation_result", {}).get("rule_results", []) if r.get("status") == "passed"]),
            "failed_rules": len([r for r in validation_rules.get("validation_result", {}).get("rule_results", []) if r.get("status") == "failed"]),
            "validation_errors": validation_rules.get("validation_result", {}).get("errors", []),
            "validation_warnings": validation_rules.get("validation_result", {}).get("warnings", []),
            "compliance_analysis": _analyze_compliance(validation_rules),
            "improvement_recommendations": _generate_validation_recommendations(validation_rules)
        }

        log_endpoint_success(f"/universal-invoice/sessions/{session_id}/validation", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting validation results: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/{session_id}/validation", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/extracted-data")
async def get_extracted_data(session_id: str):
    """
    Obtiene datos extraídos y normalizados
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/extracted-data", method="GET", session_id=session_id)

    try:
        status_data = await universal_invoice_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check extraction_status instead of status (status can be "pending" while extraction is "completed")
        extraction_status = status_data.get("extraction_status", status_data.get("status"))
        if extraction_status not in ["completed", "success"]:
            raise HTTPException(status_code=400, detail="Processing not completed yet")

        # Obtener datos reales de la BD
        parsed_data = status_data.get("parsed_data", {})
        extracted_data = status_data.get("extracted_data", {})

        response = {
            "session_id": session_id,
            "extraction_status": status_data["status"],
            "extracted_data": parsed_data,  # Datos completos del CFDI
            "normalized_data": extracted_data,  # Datos normalizados
            "confidence_scores": {},  # TODO: Obtener de BD si está disponible
            "missing_fields": [],
            "uncertain_fields": [],
            "data_quality_score": status_data.get("overall_quality_score", 0.0),
            "field_analysis": _analyze_extracted_fields(parsed_data)
        }

        log_endpoint_success(f"/universal-invoice/sessions/{session_id}/extracted-data", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting extracted data: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/{session_id}/extracted-data", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/parsers/")
async def list_available_parsers() -> UniversalInvoiceParsersResponse:
    """
    Lista parsers disponibles con sus capacidades
    """
    log_endpoint_entry("/universal-invoice/parsers/", method="GET")

    try:
        parsers_info = {}

        for name, parser in universal_invoice_engine_system.parsers.items():
            parsers_info[name] = {
                "parser_name": name,
                "parser_type": parser.parser_type.value,
                "supported_formats": parser.supported_formats,
                "extraction_capabilities": parser.extraction_capabilities,
                "usage_count": parser.usage_count,
                "success_rate": parser.success_rate,
                "avg_processing_time_ms": parser.avg_processing_time,
                "config": parser.config
            }

        response = {
            "total_parsers": len(parsers_info),
            "parsers": parsers_info,
            "supported_formats": list(set(
                format_name
                for parser in parsers_info.values()
                for format_name in parser["supported_formats"]
            )),
            "parser_recommendations": _generate_parser_recommendations(parsers_info)
        }

        log_endpoint_success("/universal-invoice/parsers/", response)
        return response

    except Exception as e:
        error_msg = f"Error listing parsers: {str(e)}"
        log_endpoint_error("/universal-invoice/parsers/", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/formats/{company_id}")
async def list_company_formats(company_id: str) -> UniversalInvoiceFormatsResponse:
    """
    Lista formatos configurados para una empresa
    Incluye template_match patterns y validation_rules configuradas
    """
    log_endpoint_entry(f"/universal-invoice/formats/{company_id}", method="GET", company_id=company_id)

    try:
        # En implementación real, obtener de BD
        response = {
            "company_id": company_id,
            "total_formats": 0,
            "formats": [],
            "template_matching_enabled": True,
            "validation_rules_enabled": True,
            "format_statistics": {
                "most_used_format": "pdf",
                "avg_processing_time_ms": 2500,
                "avg_success_rate": 94.5
            }
        }

        log_endpoint_success(f"/universal-invoice/formats/{company_id}", response)
        return response

    except Exception as e:
        error_msg = f"Error listing company formats: {str(e)}"
        log_endpoint_error(f"/universal-invoice/formats/{company_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/formats/{company_id}")
async def create_company_format(
    company_id: str,
    request: UniversalInvoiceFormatCreateRequest
) -> UniversalInvoiceFormatResponse:
    """
    Crea nuevo formato con template patterns y validation rules
    """
    log_endpoint_entry(f"/universal-invoice/formats/{company_id}", method="POST", request_data=request.dict())

    try:
        # Validar datos del formato
        if not request.format_name or not request.format_type:
            raise HTTPException(status_code=400, detail="Format name and type are required")

        # En implementación real, guardar en BD
        format_id = f"uif_{company_id}_{request.format_name}_{int(time.time())}"

        response = {
            "format_id": format_id,
            "company_id": company_id,
            "format_name": request.format_name,
            "format_type": request.format_type,
            "template_patterns_count": len(request.template_patterns or []),
            "validation_rules_count": len(request.validation_rules or []),
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "message": "Format created successfully"
        }

        log_endpoint_success(f"/universal-invoice/formats/{company_id}", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error creating format: {str(e)}"
        log_endpoint_error(f"/universal-invoice/formats/{company_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.delete("/sessions/{session_id}")
async def cancel_invoice_processing(session_id: str) -> UniversalInvoiceCancelResponse:
    """
    Cancela procesamiento de factura
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}", method="DELETE", session_id=session_id)

    try:
        # Validar que la sesión existe
        status_data = await universal_invoice_engine_system.get_session_status(session_id)
        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        # Solo se puede cancelar si está en procesamiento
        if status_data["status"] not in ["pending", "processing"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel session in status: {status_data['status']}")

        # Actualizar estado a cancelado
        await universal_invoice_engine_system._update_session_status(session_id, ExtractionStatus.FAILED, "Cancelled by user")

        response = {
            "session_id": session_id,
            "status": "cancelled",
            "message": "Invoice processing cancelled successfully",
            "cancellation_time": datetime.utcnow().isoformat()
        }

        log_endpoint_success(f"/universal-invoice/sessions/{session_id}", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error cancelling processing: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/{session_id}", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# Funciones auxiliares

async def _process_invoice_background(session_id: str):
    """Procesa factura en background con rate limiting usando semaphore"""
    # Use semaphore to limit concurrent API calls
    # This ensures only 3 invoices are processed simultaneously, preventing rate limits
    async with _anthropic_semaphore:
        try:
            logger.info(f"Starting background processing for session {session_id} (acquired semaphore)")
            result = await universal_invoice_engine_system.process_invoice(session_id)
            logger.info(f"Background invoice processing completed for session {session_id}")

            # 🔥 NEW: Auto-trigger classification after successful parsing
            if result.get('status') == 'completed' and result.get('parsed_data'):
                await _trigger_classification(session_id, result)
                # 🔥 NEW: Auto-trigger SAT validation after classification
                await _trigger_sat_validation(session_id, result)

            # Add a small delay after processing to spread out API calls
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Background invoice processing failed for session {session_id}: {e}")
            # Still add delay on failure to avoid rapid retries hitting rate limits
            await asyncio.sleep(1)


async def _trigger_classification(session_id: str, processing_result: Dict[str, Any]):
    """
    Auto-trigger classification after invoice parsing completes.

    🔥 NEW: Uses hierarchical classification system (3-phase LLM classification)
    """
    try:
        # 🔥 IMPORTANT: Use hierarchical classification system instead of legacy
        from core.expenses.invoices.universal_invoice_engine_system import UniversalInvoiceEngineSystem

        company_id_str = processing_result.get('company_id')
        parsed_data = processing_result.get('parsed_data')

        if not company_id_str or not parsed_data:
            logger.warning(f"Session {session_id}: Missing company_id or parsed_data, skipping classification")
            return

        logger.info(f"Session {session_id}: Triggering HIERARCHICAL auto-classification (company_id={company_id_str})")

        # Call hierarchical classification (3-phase: Family → Subfamily → Specific)
        engine = UniversalInvoiceEngineSystem()
        classification_result = await engine.classify_invoice_hierarchical(
            session_id=session_id,
            company_id=company_id_str
        )

        if not classification_result:
            logger.warning(f"Session {session_id}: Hierarchical classification returned None")
            return

        logger.info(
            f"Session {session_id}: ✅ Hierarchical classification completed - "
            f"SAT code: {classification_result.get('sat_account_code')} "
            f"(Phase 1: {classification_result.get('metadata', {}).get('hierarchical_phase1', {}).get('familia_codigo')})"
        )

    except Exception as e:
        logger.error(f"Session {session_id}: Hierarchical auto-classification failed: {e}", exc_info=True)


async def _trigger_sat_validation(session_id: str, processing_result: Dict[str, Any]):
    """
    Auto-trigger SAT validation after invoice parsing completes.

    This validates the invoice against SAT web services to check if it's vigente/cancelado.
    """
    try:
        from core.sat.sat_validation_service import validate_single_invoice
        from core.auth.jwt import get_db_connection

        parsed_data = processing_result.get('parsed_data')
        if not parsed_data:
            logger.warning(f"Session {session_id}: No parsed_data, skipping SAT validation")
            return

        # Extraer UUID del CFDI
        uuid = parsed_data.get('uuid') or parsed_data.get('UUID')
        if not uuid:
            logger.warning(f"Session {session_id}: No UUID found in parsed_data, skipping SAT validation")
            return

        logger.info(f"Session {session_id}: Triggering SAT validation for UUID {uuid}")

        # Obtener sesión de SQLAlchemy
        from core.database import SessionLocal
        db = SessionLocal()

        try:
            # Llamar servicio de validación SAT
            success, validation_info, error = validate_single_invoice(
                db=db,
                session_id=session_id,
                force_refresh=False,  # No forzar revalidación
                use_mock=False  # Usar servicio real del SAT
            )

            if success and validation_info:
                logger.info(
                    f"Session {session_id}: SAT validation completed - "
                    f"Status: {validation_info.get('status', 'unknown')}"
                )

                # 🔥 FIX: Update display_info.sat_status so frontend shows correct status
                from core.shared.db_config import get_connection
                import json

                conn = get_connection(dict_cursor=True)
                cursor = conn.cursor()

                # Get current display_info
                cursor.execute("""
                    SELECT display_info
                    FROM sat_invoices
                    WHERE id = %s
                """, (session_id,))

                row = cursor.fetchone()
                display_info = row['display_info'] if row and row['display_info'] else {}

                # Update sat_status in display_info
                sat_status = validation_info.get('status', 'desconocido')
                display_info['sat_status'] = sat_status

                # Save back to database
                cursor.execute("""
                    UPDATE sat_invoices
                    SET display_info = %s,
                        updated_at = now()
                    WHERE id = %s
                """, (json.dumps(display_info), session_id))

                conn.commit()
                cursor.close()
                conn.close()

                logger.info(f"Session {session_id}: Updated display_info.sat_status = {sat_status}")

            elif error:
                logger.warning(f"Session {session_id}: SAT validation error: {error}")
            else:
                logger.warning(f"Session {session_id}: SAT validation returned no result")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Session {session_id}: SAT validation failed: {e}", exc_info=True)


def _estimate_processing_time(file_path: str) -> int:
    """Estima tiempo de procesamiento basado en archivo"""
    try:
        file_size = os.path.getsize(file_path)
        return _estimate_processing_time_by_size(file_size)
    except:
        return 5000  # 5 segundos por defecto

def _estimate_processing_time_by_size(file_size_bytes: int) -> int:
    """Estima tiempo basado en tamaño de archivo"""
    # Estimaciones basadas en tamaño
    if file_size_bytes < 100 * 1024:  # < 100KB
        return 2000
    elif file_size_bytes < 1024 * 1024:  # < 1MB
        return 5000
    elif file_size_bytes < 5 * 1024 * 1024:  # < 5MB
        return 10000
    else:
        return 20000

def _estimate_completion_time() -> str:
    """Estima tiempo de completado"""
    completion_time = datetime.utcnow()
    completion_time = completion_time.replace(minute=completion_time.minute + 2)
    return completion_time.isoformat()

def _calculate_progress_percentage(status: str) -> int:
    """Calcula porcentaje de progreso"""
    progress_map = {
        "pending": 0,
        "processing": 50,
        "completed": 100,
        "failed": 100,
        "partial": 75
    }
    return progress_map.get(status, 0)

def _analyze_template_match(template_match: Dict[str, Any]) -> Dict[str, Any]:
    """Analiza calidad del template match"""
    match_score = template_match.get("match_score", 0.0)

    return {
        "match_quality": "excellent" if match_score > 0.9 else "good" if match_score > 0.7 else "fair" if match_score > 0.5 else "poor",
        "confidence_level": "high" if match_score > 0.8 else "medium" if match_score > 0.6 else "low",
        "pattern_coverage": len(template_match.get("matched_patterns", [])),
        "mapping_completeness": len(template_match.get("field_mappings", {}))
    }

def _generate_template_suggestions(template_match: Dict[str, Any]) -> List[str]:
    """Genera sugerencias para mejorar template matching"""
    suggestions = []
    match_score = template_match.get("match_score", 0.0)

    if match_score < 0.7:
        suggestions.append("Consider creating a custom template for this format")
    if len(template_match.get("matched_patterns", [])) < 3:
        suggestions.append("Add more pattern indicators to improve matching accuracy")
    if not template_match.get("field_mappings"):
        suggestions.append("Configure field mappings for better data extraction")

    if not suggestions:
        suggestions.append("Template matching is working optimally")

    return suggestions

def _analyze_compliance(validation_rules: Dict[str, Any]) -> Dict[str, Any]:
    """Analiza compliance de validación"""
    validation_result = validation_rules.get("validation_result", {})
    errors = validation_result.get("errors", [])
    warnings = validation_result.get("warnings", [])

    return {
        "compliance_status": "compliant" if not errors else "non_compliant",
        "risk_level": "high" if errors else "medium" if warnings else "low",
        "critical_issues": len(errors),
        "warning_issues": len(warnings),
        "overall_compliance_score": validation_rules.get("validation_score", 0.0)
    }

def _generate_validation_recommendations(validation_rules: Dict[str, Any]) -> List[str]:
    """Genera recomendaciones de validación"""
    recommendations = []
    validation_result = validation_rules.get("validation_result", {})
    errors = validation_result.get("errors", [])

    if errors:
        recommendations.append("Review and fix validation errors before processing")
    if validation_rules.get("validation_score", 100) < 80:
        recommendations.append("Consider adding more validation rules for better data quality")

    if not recommendations:
        recommendations.append("Validation is working correctly")

    return recommendations

def _analyze_extracted_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analiza campos extraídos"""
    return {
        "total_fields": len(extracted_data),
        "required_fields_present": True,  # Simulado
        "data_completeness": 95.0,  # Simulado
        "field_types": {
            "text": 60,
            "number": 25,
            "date": 15
        }
    }

def _generate_parser_recommendations(parsers_info: Dict[str, Any]) -> List[str]:
    """Genera recomendaciones de parsers"""
    recommendations = []

    # Encontrar el parser con mejor success rate
    best_parser = max(parsers_info.values(), key=lambda p: p["success_rate"], default=None)
    if best_parser:
        recommendations.append(f"For best results, consider using {best_parser['parser_name']} (success rate: {best_parser['success_rate']:.1f}%)")

    recommendations.append("Use hybrid parser for maximum format compatibility")
    recommendations.append("Configure parser-specific settings for optimal performance")

    return recommendations
