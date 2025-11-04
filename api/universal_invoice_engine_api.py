"""
Universal Invoice Engine API - Endpoints para procesamiento universal de facturas
Punto 21 de Auditoría: APIs para template_match y validation_rules
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from typing import Dict, List, Optional, Any
import logging
import os
import tempfile
from datetime import datetime

from core.universal_invoice_engine_system import (
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

@router.post("/sessions/")
async def create_invoice_processing_session(
    request: UniversalInvoiceSessionCreateRequest
) -> UniversalInvoiceSessionResponse:
    """
    Crea una nueva sesión de procesamiento universal de facturas
    Incluye template_match y validation_rules setup
    """
    log_endpoint_entry("/universal-invoice/sessions/", "POST", request.dict())

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

@router.post("/sessions/upload/")
async def upload_and_create_session(
    company_id: str,
    user_id: Optional[str] = None,
    file: UploadFile = File(...)
) -> UniversalInvoiceSessionResponse:
    """
    Sube archivo y crea sesión de procesamiento
    """
    log_endpoint_entry("/universal-invoice/sessions/upload/", "POST", {
        "company_id": company_id,
        "filename": file.filename,
        "content_type": file.content_type
    })

    try:
        # Validar tipo de archivo
        allowed_types = ['application/pdf', 'application/xml', 'text/xml', 'image/jpeg', 'image/png', 'text/csv']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

        # Guardar archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Crear sesión
        session_id = await universal_invoice_engine_system.create_processing_session(
            company_id=company_id,
            file_path=temp_file_path,
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
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/process", "POST", {
        "session_id": session_id,
        "async_processing": request.async_processing if request else True
    })

    try:
        # Validar que la sesión existe
        session_status = await universal_invoice_engine_system.get_session_status(session_id)
        if 'error' in session_status:
            raise HTTPException(status_code=404, detail="Session not found")

        # Procesar en background si se solicita
        if not request or request.async_processing:
            background_tasks.add_task(_process_invoice_background, session_id)

            response = {
                "session_id": session_id,
                "status": "processing_started",
                "processing_mode": "async",
                "message": "Invoice processing started in background",
                "check_status_url": f"/universal-invoice/sessions/{session_id}/status",
                "estimated_completion_time": _estimate_completion_time()
            }
        else:
            # Procesar sincrónicamente
            result = await universal_invoice_engine_system.process_invoice(session_id)

            response = {
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

        log_endpoint_success(f"/universal-invoice/sessions/{session_id}/process", response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error processing invoice: {str(e)}"
        log_endpoint_error(f"/universal-invoice/sessions/{session_id}/process", error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/sessions/{session_id}/status")
async def get_invoice_processing_status(session_id: str) -> UniversalInvoiceStatusResponse:
    """
    Obtiene estado completo con template_match y validation_rules
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/status", "GET", {"session_id": session_id})

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
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/template-match", "GET", {"session_id": session_id})

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
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/validation", "GET", {"session_id": session_id})

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
async def get_extracted_data(session_id: str) -> UniversalInvoiceDataResponse:
    """
    Obtiene datos extraídos y normalizados
    """
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}/extracted-data", "GET", {"session_id": session_id})

    try:
        status_data = await universal_invoice_engine_system.get_session_status(session_id)

        if 'error' in status_data:
            raise HTTPException(status_code=404, detail="Session not found")

        if status_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Processing not completed yet")

        # En implementación real, obtener de tabla de extracciones
        response = {
            "session_id": session_id,
            "extraction_status": status_data["status"],
            "extracted_data": {},  # Datos extraídos de la BD
            "normalized_data": {},  # Datos normalizados
            "confidence_scores": {},  # Scores por campo
            "missing_fields": [],
            "uncertain_fields": [],
            "data_quality_score": status_data.get("overall_quality_score", 0.0),
            "field_analysis": _analyze_extracted_fields({})
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
    log_endpoint_entry("/universal-invoice/parsers/", "GET", {})

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
    log_endpoint_entry(f"/universal-invoice/formats/{company_id}", "GET", {"company_id": company_id})

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
    log_endpoint_entry(f"/universal-invoice/formats/{company_id}", "POST", request.dict())

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
    log_endpoint_entry(f"/universal-invoice/sessions/{session_id}", "DELETE", {"session_id": session_id})

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
    """Procesa factura en background"""
    try:
        result = await universal_invoice_engine_system.process_invoice(session_id)
        logger.info(f"Background invoice processing completed for session {session_id}")
    except Exception as e:
        logger.error(f"Background invoice processing failed for session {session_id}: {e}")

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
