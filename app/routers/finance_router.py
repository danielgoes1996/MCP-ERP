"""Financial reports router consolidating legacy endpoints."""

from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
import logging

try:
    from core.financial_reports_generator import FinancialReportsGenerator, ReportType
except ImportError:  # pragma: no cover - fallback
    from core.reports.financial_reports_generator_simple import FinancialReportsGenerator
    from enum import Enum

    class ReportType(Enum):
        IVA_REPORT = "iva_report"
        POLIZA_ELECTRONICA = "poliza_electronica"
        GASTOS_REVISION = "gastos_revision"
        RESUMEN_FISCAL = "resumen_fiscal"

try:
    from core.tenancy_middleware import get_current_tenant
except ImportError:  # pragma: no cover
    def get_current_tenant():  # type: ignore
        return "1"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/finance", tags=["finance"])


class ReportRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2030)
    month: int = Field(..., ge=1, le=12)
    report_type: str
    detailed: bool = True
    format: str = Field("json", description="Formato de salida (json, excel, xml)")
    tax_source: Optional[str] = Field(None, description="Filtrar por fuente fiscal (cfdi, rule, llm, manual)")


class IVAReportResponse(BaseModel):
    periodo: dict
    resumen: dict
    detalle: Optional[list] = None
    tax_sources: Dict[str, dict] = Field(default_factory=dict)
    generado_en: str


class PolizaElectronicaResponse(BaseModel):
    Version: str
    RFC: str
    Mes: str
    Anio: int
    TipoSolicitud: str
    Polizas: dict


class GastosRevisionResponse(BaseModel):
    periodo: dict
    total_gastos_revision: int
    monto_total_revision: float
    razones_frecuentes: dict
    gastos: list
    generado_en: str


class ResumenFiscalResponse(BaseModel):
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


@router.post("/reports/iva", response_model=IVAReportResponse)
async def generate_iva_report(request: ReportRequest, tenant_id: str = Depends(get_current_tenant)):
    try:
        tax_source = _normalize_tax_source(request.tax_source)
        generator = FinancialReportsGenerator(tenant_id, tax_source)
        report = generator.generate_iva_report(year=request.year, month=request.month, detailed=request.detailed)
        if request.format == "excel":
            raise HTTPException(status_code=501, detail="Exportación a Excel pendiente de implementación")
        return report
    except Exception as exc:  # pragma: no cover
        logger.exception("Error generando reporte IVA: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/reports/poliza-electronica", response_model=PolizaElectronicaResponse)
async def generate_poliza_electronica(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tipo_poliza: str = Query("Dr", pattern="^(Dr|Ig|Eg)$"),
    tenant_id: str = Depends(get_current_tenant),
):
    try:
        generator = FinancialReportsGenerator(tenant_id)
        return generator.generate_poliza_electronica(year=year, month=month, tipo_poliza=tipo_poliza)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error generando póliza electrónica: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/reports/poliza-electronica/xml")
async def download_poliza_xml(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tipo_poliza: str = Query("Dr"),
    tenant_id: str = Depends(get_current_tenant),
) -> Response:
    try:
        generator = FinancialReportsGenerator(tenant_id)
        poliza = generator.generate_poliza_electronica(year=year, month=month, tipo_poliza=tipo_poliza)
        xml_content = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<PLZ:Polizas
    xmlns:PLZ=\"http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/PolizasPeriodo\"
    xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"
    Version=\"{poliza['Version']}\"
    RFC=\"{poliza['RFC']}\"
    Mes=\"{poliza['Mes']}\"
    Anio=\"{poliza['Anio']}\">\n    <!-- Contenido pendiente de implementación completa -->\n</PLZ:Polizas>"""
        return Response(content=xml_content, media_type="application/xml")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error generando XML de póliza: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/reports/gastos-revision", response_model=GastosRevisionResponse)
async def get_gastos_revision(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tenant_id: str = Depends(get_current_tenant),
):
    try:
        generator = FinancialReportsGenerator(tenant_id)
        return generator.get_gastos_revision(year=year, month=month)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error obteniendo gastos en revisión: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/reports/resumen-fiscal", response_model=ResumenFiscalResponse)
async def get_resumen_fiscal(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    tenant_id: str = Depends(get_current_tenant),
):
    try:
        generator = FinancialReportsGenerator(tenant_id)
        return generator.get_resumen_fiscal(year=year, month=month)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error obteniendo resumen fiscal: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/reports/disponibles")
async def get_available_reports(tenant_id: str = Depends(get_current_tenant)) -> dict:
    generator = FinancialReportsGenerator(tenant_id)
    return generator.list_available_reports()


@router.get("/health")
async def finance_health_check() -> dict:
    return {"status": "healthy", "service": "finance"}
