"""
API endpoints para generación de reportes fiscales automáticos.
"""

import logging
from datetime import datetime
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Depends, Query, Response
from pydantic import BaseModel, Field

try:
    from core.financial_reports_generator import (
        FinancialReportsGenerator,
        ReportType
    )
except ImportError:
    # Usar versión simplificada si la completa no está disponible
    from core.reports.financial_reports_generator_simple import FinancialReportsGenerator
    from enum import Enum

    class ReportType(Enum):
        IVA_REPORT = "iva_report"
        POLIZA_ELECTRONICA = "poliza_electronica"
        GASTOS_REVISION = "gastos_revision"
        RESUMEN_FISCAL = "resumen_fiscal"
try:
    from core.tenancy_middleware import get_current_tenant
except ImportError:
    # Fallback si no existe get_current_tenant
    def get_current_tenant():
        return "1"  # Default tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


class ReportRequest(BaseModel):
    """Solicitud de generación de reporte."""
    year: int = Field(..., ge=2020, le=2030, description="Año del reporte")
    month: int = Field(..., ge=1, le=12, description="Mes del reporte")
    report_type: str = Field(..., description="Tipo de reporte")
    detailed: bool = Field(True, description="Incluir detalle completo")
    format: str = Field("json", description="Formato de salida (json, excel, xml)")
    tax_source: Optional[str] = Field(
        None,
        description="Filtrar por fuente fiscal (cfdi, rule, llm, manual)"
    )


class IVAReportResponse(BaseModel):
    """Respuesta del reporte de IVA."""
    periodo: dict
    resumen: dict
    detalle: Optional[list] = None
    tax_sources: Dict[str, dict] = Field(default_factory=dict)
    generado_en: str


class PolizaElectronicaResponse(BaseModel):
    """Respuesta de póliza electrónica."""
    Version: str
    RFC: str
    Mes: str
    Anio: int
    TipoSolicitud: str
    Polizas: dict


class GastosRevisionResponse(BaseModel):
    """Respuesta de gastos en revisión."""
    periodo: dict
    total_gastos_revision: int
    monto_total_revision: float
    razones_frecuentes: dict
    gastos: list
    generado_en: str


class ResumenFiscalResponse(BaseModel):
    """Respuesta del resumen fiscal."""
    periodo: dict
    totales: dict
    cfdi: dict
    categorias: list
    revision: dict
    alertas: list
    tax_sources: Dict[str, dict] = Field(default_factory=dict)
    generado_en: str


def _normalize_tax_source(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.lower()
    if normalized in {"all", "todos", "todo", "default", ""}:
        return None
    if normalized not in {"cfdi", "rule", "llm", "manual"}:
        return None
    return normalized


@router.post("/iva", response_model=IVAReportResponse)
async def generate_iva_report(
    request: ReportRequest,
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Genera reporte de IVA acreditable y no acreditable.

    Clasifica automáticamente el IVA según:
    - Categoría del gasto
    - Códigos SAT
    - Régimen fiscal del contribuyente
    """
    try:
        tax_source = _normalize_tax_source(request.tax_source)
        generator = FinancialReportsGenerator(tenant_id, tax_source)
        report = generator.generate_iva_report(
            year=request.year,
            month=request.month,
            detailed=request.detailed
        )

        if request.format == "excel":
            # TODO: Implementar exportación a Excel
            raise HTTPException(
                status_code=501,
                detail="Exportación a Excel pendiente de implementación"
            )

        return report

    except Exception as e:
        logger.error(f"Error generando reporte IVA: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poliza-electronica", response_model=PolizaElectronicaResponse)
async def generate_poliza_electronica(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tipo_poliza: str = Query("Dr", regex="^(Dr|Ig|Eg)$", description="Tipo de póliza: Dr=Diario, Ig=Ingresos, Eg=Egresos"),
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Genera póliza electrónica en formato Anexo 24 del SAT.

    La póliza incluye:
    - Asientos contables con cuentas SAT
    - Información de CFDI asociados
    - Estructura lista para firma electrónica
    """
    try:
        generator = FinancialReportsGenerator(tenant_id)
        poliza = generator.generate_poliza_electronica(
            year=year,
            month=month,
            tipo_poliza=tipo_poliza
        )

        return poliza

    except Exception as e:
        logger.error(f"Error generando póliza electrónica: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/poliza-electronica/xml")
async def download_poliza_xml(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tipo_poliza: str = Query("Dr"),
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Descarga póliza electrónica en formato XML.
    """
    try:
        generator = FinancialReportsGenerator(tenant_id)
        poliza = generator.generate_poliza_electronica(
            year=year,
            month=month,
            tipo_poliza=tipo_poliza
        )

        # TODO: Convertir a XML según especificación SAT
        # Por ahora retornamos JSON con headers XML

        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<PLZ:Polizas
    xmlns:PLZ="http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/PolizasPeriodo"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    Version="{poliza['Version']}"
    RFC="{poliza['RFC']}"
    Mes="{poliza['Mes']}"
    Anio="{poliza['Anio']}">
    <!-- Contenido pendiente de implementación completa -->
</PLZ:Polizas>"""

        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename=poliza_{year}_{month:02d}.xml"
            }
        )

    except Exception as e:
        logger.error(f"Error descargando póliza XML: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gastos-revision", response_model=GastosRevisionResponse)
async def get_gastos_revision(
    year: Optional[int] = Query(None, ge=2020, le=2030),
    month: Optional[int] = Query(None, ge=1, le=12),
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Obtiene gastos marcados para revisión fiscal.

    Incluye gastos que requieren atención por:
    - Categorías genéricas o ambiguas
    - Restricciones de régimen fiscal
    - Montos significativos sin CFDI
    """
    try:
        generator = FinancialReportsGenerator(tenant_id)
        report = generator.generate_gastos_revision_report(
            year=year,
            month=month
        )

        return report

    except Exception as e:
        logger.error(f"Error obteniendo gastos en revisión: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resumen-fiscal", response_model=ResumenFiscalResponse)
async def get_resumen_fiscal(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Genera resumen fiscal completo del periodo.

    Consolida información de:
    - IVA acreditable vs no acreditable
    - Gastos por categoría SAT
    - Cumplimiento de CFDI
    - Alertas y recomendaciones fiscales
    """
    try:
        # Intentar usar generador simplificado para evitar errores
        from core.reports.financial_reports_generator_simple import FinancialReportsGenerator as SimpleGenerator
        generator = SimpleGenerator(tenant_id)
        resumen = generator.generate_resumen_fiscal(
            year=year,
            month=month
        )

        return resumen

    except Exception as e:
        logger.error(f"Error generando resumen fiscal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categorias-sat/resumen")
async def get_categorias_sat_summary(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tenant_id: str = Depends(get_current_tenant)
):
    """
    Obtiene resumen de gastos agrupados por categorías SAT.
    """
    from core.internal_db import get_sqlite_connection
    from core.sat_catalog_seed import CATEGORY_SAT_MAPPING

    try:
        periodo_str = f"{year}-{str(month).zfill(2)}"

        with get_sqlite_connection() as conn:
            query = """
                SELECT
                    e.categoria_slug,
                    e.categoria_sat_account_code,
                    e.categoria_sat_product_service_code,
                    COUNT(*) as cantidad,
                    SUM(e.monto) as total,
                    SUM(e.subtotal) as subtotal,
                    SUM(e.iva) as iva,
                    SUM(CASE WHEN e.cfdi_uuid IS NOT NULL THEN 1 ELSE 0 END) as con_cfdi,
                    SUM(CASE WHEN e.categoria_needs_review = 1 THEN 1 ELSE 0 END) as con_revision
                FROM manual_expenses e
                WHERE e.tenant_id = ?
                AND strftime('%Y-%m', e.fecha_gasto) = ?
                AND e.estado != 'cancelado'
                GROUP BY e.categoria_slug, e.categoria_sat_account_code, e.categoria_sat_product_service_code
                ORDER BY total DESC
            """

            cursor = conn.execute(query, (tenant_id, periodo_str))

            categorias = []
            total_general = 0

            for row in cursor:
                categoria_info = CATEGORY_SAT_MAPPING.get(row[0], {})
                total = float(row[4]) if row[4] else 0
                total_general += total

                categorias.append({
                    'categoria': {
                        'slug': row[0],
                        'nombre': categoria_info.get('nombre', row[0]),
                        'sat_account_code': row[1],
                        'sat_product_service_code': row[2],
                        'descripcion': categoria_info.get('descripcion', '')
                    },
                    'estadisticas': {
                        'cantidad_gastos': row[3],
                        'total': total,
                        'subtotal': float(row[5]) if row[5] else 0,
                        'iva': float(row[6]) if row[6] else 0,
                        'con_cfdi': row[7],
                        'con_revision': row[8],
                        'porcentaje_cfdi': (row[7] / row[3] * 100) if row[3] > 0 else 0,
                        'porcentaje_revision': (row[8] / row[3] * 100) if row[3] > 0 else 0
                    }
                })

            # Calcular porcentajes del total
            for cat in categorias:
                cat['estadisticas']['porcentaje_total'] = (
                    (cat['estadisticas']['total'] / total_general * 100)
                    if total_general > 0 else 0
                )

        return {
            'periodo': {
                'año': year,
                'mes': month
            },
            'total_general': total_general,
            'total_categorias': len(categorias),
            'categorias': categorias,
            'generado_en': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error obteniendo resumen por categorías SAT: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/disponibles")
async def get_available_reports():
    """
    Lista los tipos de reportes disponibles.
    """
    return {
        'reportes': [
            {
                'tipo': 'iva',
                'nombre': 'Reporte de IVA',
                'descripcion': 'IVA acreditable y no acreditable, clasificación automática',
                'endpoint': '/api/v1/reports/iva',
                'parametros': ['year', 'month', 'detailed']
            },
            {
                'tipo': 'poliza_electronica',
                'nombre': 'Póliza Electrónica (Anexo 24)',
                'descripcion': 'Pólizas contables en formato SAT',
                'endpoint': '/api/v1/reports/poliza-electronica',
                'parametros': ['year', 'month', 'tipo_poliza'],
                'formatos': ['json', 'xml']
            },
            {
                'tipo': 'gastos_revision',
                'nombre': 'Gastos en Revisión',
                'descripcion': 'Gastos que requieren revisión fiscal',
                'endpoint': '/api/v1/reports/gastos-revision',
                'parametros': ['year', 'month']
            },
            {
                'tipo': 'resumen_fiscal',
                'nombre': 'Resumen Fiscal',
                'descripcion': 'Resumen consolidado fiscal del periodo',
                'endpoint': '/api/v1/reports/resumen-fiscal',
                'parametros': ['year', 'month']
            },
            {
                'tipo': 'categorias_sat',
                'nombre': 'Resumen por Categorías SAT',
                'descripcion': 'Gastos agrupados por categoría y código SAT',
                'endpoint': '/api/v1/reports/categorias-sat/resumen',
                'parametros': ['year', 'month']
            }
        ]
    }


@router.get("/health")
async def health_check():
    """Verifica el estado del servicio de reportes."""
    return {
        'status': 'healthy',
        'service': 'financial_reports',
        'timestamp': datetime.now().isoformat()
    }
