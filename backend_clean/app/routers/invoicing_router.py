"""Invoicing router (core endpoints migrated from legacy modules)."""

from datetime import datetime
from typing import Optional, Dict, Any

import asyncio
import inspect
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request, Body
import logging

from core.api_models import ExpenseResponse, ExpenseStatusEnum
from modules.invoicing_agent.models import list_tickets as list_tickets_model, get_ticket as get_ticket_model
from dashboard_stats_calculator import calculate_dashboard_stats

router = APIRouter(prefix="/invoicing", tags=["invoicing"])

logger = logging.getLogger(__name__)


@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses():
    """Stub endpoint that returns realistic demo expenses."""
    now = datetime.utcnow().isoformat()
    return [
        ExpenseResponse(
            id=1,
            descripcion="Taxi aeropuerto",
            monto_total=450.0,
            fecha_gasto="2024-10-18",
            moneda="MXN",
            status=ExpenseStatusEnum.open,
            invoice_status="pending",
            bank_status="pending",
            approval_status="pending",
            company_id="demo-co",
            metadata={"source": "stub", "demo": True, "category": "transport"},
            tags=["transport", "demo"],
            created_at=now,
            updated_at=now,
        ),
        ExpenseResponse(
            id=2,
            descripcion="Factura proveedor recurrente",
            monto_total=12500.0,
            fecha_gasto="2024-10-10",
            moneda="MXN",
            status=ExpenseStatusEnum.closed,
            invoice_status="invoiced",
            bank_status="bank_reconciled",
            approval_status="approved",
            company_id="demo-co",
            metadata={"source": "stub", "demo": True, "category": "services"},
            tags=["services", "monthly"],
            created_at=now,
            updated_at=now,
        ),
    ]


@router.get("/tickets")
async def list_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    merchant: Optional[str] = Query(None, description="Filter by merchant"),
    company_id: str = Query("default", description="Company identifier"),
) -> Dict[str, Any]:
    try:
        tickets = list_tickets_model(
            company_id=company_id,
            estado=status,
            limit=page_size,
        )
        return {
            "success": True,
            "total": len(tickets),
            "tickets": tickets,
            "filters": {
                "company_id": company_id,
                "estado": status,
                "limit": page_size,
                "page": page,
            },
        }
    except Exception as exc:  # pragma: no cover
        logger.exception("Error listing tickets: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


@router.post("/tickets")
async def create_ticket(request: Request, file: Optional[UploadFile] = File(None)):
    """Compatibility endpoint that supports both file uploads and JSON payloads."""
    try:
        from modules.invoicing_agent.api import upload_ticket as legacy_upload_ticket

        content_type = request.headers.get("content-type", "")
        merchant_name: Optional[str] = None
        text_content: Optional[str] = None
        user_id: Optional[int] = None
        company_id: str = "default"
        auto_process: bool = True
        priority: str = "normal"

        if "application/json" in content_type:
            payload = await request.json()
            text_content = payload.get("text_content") or payload.get("raw_data") or payload.get("text")
            merchant_name = payload.get("merchant_name")
            user_id = payload.get("user_id")
            company_id = payload.get("company_id", company_id)
            auto_process = payload.get("auto_process", auto_process)
            priority = payload.get("priority", priority)
        else:
            form = await request.form()
            text_content = form.get("text_content")
            merchant_name = form.get("merchant_name")
            user_id = form.get("user_id")
            company_id = form.get("company_id", company_id)
            auto_process = form.get("auto_process", str(auto_process)).lower() not in {"false", "0", ""}
            priority = form.get("priority", priority)

        if not file and not text_content:
            raise HTTPException(status_code=422, detail="Debe proporcionar un archivo o contenido de texto")

        if file and (file.filename or "").lower().endswith(".exe"):
            raise HTTPException(status_code=400, detail="Tipo de archivo no soportado")

        result = await _maybe_await(
            legacy_upload_ticket(
                request=request,
                file=file,
                text_content=text_content,
                user_id=user_id,
                company_id=company_id,
            )
        )

        if isinstance(result, dict):
            result.setdefault("company_id", company_id)
            if merchant_name:
                result.setdefault("merchant_name", merchant_name)
            result.setdefault("auto_process", auto_process)
            result.setdefault("priority", priority)
        return result
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("Error creating ticket: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    try:
        result = get_ticket_model(ticket_id)
        if not result:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/tickets/{ticket_id}/process")
async def process_ticket(ticket_id: int):
    try:
        from modules.invoicing_agent.api import manual_process_ticket

        return await manual_process_ticket(ticket_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error processing ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs")
async def list_jobs(company_id: str = Query("default"), limit: int = Query(50, ge=1, le=200)):
    try:
        from modules.invoicing_agent.api import list_jobs_endpoint

        return await list_jobs_endpoint(company_id=company_id, limit=limit)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error listing jobs: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/jobs/{job_id}/process")
async def process_job(job_id: int):
    try:
        from modules.invoicing_agent.api import process_job_manually

        return await process_job_manually(job_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error processing job %s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tickets/{ticket_id}/invoice-status")
async def get_ticket_invoice_status(ticket_id: int):
    """Compatibility wrapper around legacy invoice-status endpoint."""
    try:
        from modules.invoicing_agent.api import get_ticket_invoice_status as legacy_invoice_status

        data = await legacy_invoice_status(ticket_id)
        if isinstance(data, dict) and "invoice_status" not in data:
            invoice_data = data.get("invoice_data") or {}
            data["invoice_status"] = invoice_data.get("status")
        return data
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting invoice status for ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tickets/{ticket_id}/image")
async def get_ticket_image(ticket_id: int):
    """Proxy to legacy image-serving endpoint."""
    try:
        from modules.invoicing_agent.api import get_ticket_image as legacy_image

        return await legacy_image(ticket_id)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting ticket image %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tickets/{ticket_id}/ocr-text")
async def get_ticket_ocr_text(ticket_id: int):
    """Proxy to legacy OCR endpoint."""
    try:
        from modules.invoicing_agent.api import get_ticket_ocr_text as legacy_ocr

        return await legacy_ocr(ticket_id)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting ticket OCR %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test-playwright-simple/{ticket_id}")
async def test_playwright_simple(ticket_id: int):
    try:
        from modules.invoicing_agent.playwright_simple_engine import PlaywrightLitromilEngine

        engine = PlaywrightLitromilEngine(ticket_id)
        if asyncio.iscoroutine(engine):
            engine = await engine

        if not hasattr(engine, "initialize"):
            raise HTTPException(status_code=501, detail="Playwright engine not available")

        result: Dict[str, Any] = {}
        try:
            initialized = await _maybe_await(engine.initialize())
            automation_result = await _maybe_await(engine.automate_litromil_invoice())
            result.update(automation_result or {})
            result.setdefault("success", (initialized is None or initialized) and result.get("success", True))
        finally:
            cleanup = getattr(engine, "cleanup", None)
            if callable(cleanup):
                await _maybe_await(cleanup())

        return result
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail="Playwright simple engine not available")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error executing simple Playwright engine: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-playwright-complete/{ticket_id}")
async def test_playwright_complete(ticket_id: int):
    try:
        from modules.invoicing_agent.playwright_automation_engine import PlaywrightAutomationEngine

        engine = PlaywrightAutomationEngine(ticket_id)
        if asyncio.iscoroutine(engine):
            engine = await engine

        if not hasattr(engine, "process_ticket"):
            raise HTTPException(status_code=501, detail="Playwright automation engine not available")

        result = engine.process_ticket(ticket_id)
        return result or {"success": False}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail="Playwright automation engine not available")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error executing Playwright automation engine: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/universal-invoice-generator/{ticket_id}")
async def universal_invoice_generator(ticket_id: int, payload: Dict[str, Any] = Body(default={})):  # type: ignore[assignment]
    try:
        from modules.invoicing_agent.universal_invoice_engine import UniversalInvoiceEngine

        engine = UniversalInvoiceEngine(ticket_id)
        if asyncio.iscoroutine(engine):
            engine = await engine

        if not hasattr(engine, "generate_invoice_from_any_portal"):
            raise HTTPException(status_code=501, detail="Universal engine not available")

        result = await _maybe_await(engine.generate_invoice_from_any_portal(**payload))
        return result or {"success": False}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail="Universal invoice engine not available")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error executing universal invoice engine: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-any-portal")
async def test_any_portal(payload: Dict[str, Any] = Body(...)):  # type: ignore[assignment]
    portal_url = payload.get("portal_url")
    if not portal_url:
        raise HTTPException(status_code=400, detail="portal_url es requerido")

    # Implementación pendiente; responder 501 para compatibilidad con tests.
    raise HTTPException(status_code=501, detail="Portal testing not implemented")


@router.post("/test-intelligent-agent/{ticket_id}")
async def test_intelligent_agent(ticket_id: int):
    try:
        from modules.invoicing_agent.models import get_ticket_by_id
        from modules.invoicing_agent.robust_automation_engine import RobustAutomationEngine

        ticket = get_ticket_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        engine = RobustAutomationEngine()
        result = engine.process_ticket(ticket)
        return result or {"success": False}
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(status_code=501, detail="Robust automation engine not available")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error executing intelligent agent for ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/merchants")
async def list_merchants():
    try:
        from modules.invoicing_agent.models import list_merchants as list_merchants_model

        merchants = list_merchants_model()
        return {"success": True, "merchants": merchants}
    except Exception as exc:  # pragma: no cover
        logger.exception("Error listing merchants: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
async def get_processing_stats(company_id: str = Query("default", description="Company identifier")):
    try:
        stats = calculate_dashboard_stats(company_id)
        return {
            "total_tickets": stats.get("total_tickets", 0),
            "by_status": stats.get("tickets_by_status", {}),
            "success_rate": stats.get("success_rate", 0),
            "auto_invoiced": stats.get("auto_invoiced", 0),
            "top_merchants": stats.get("top_merchants", []),
        }
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting stats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0", "api": "invoicing"}
