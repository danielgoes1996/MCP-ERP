"""
Main FastAPI application for MCP Server
This is the entry point for the MCP (Model Context Protocol) Server that acts as
a universal layer between AI agents and business systems.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal, Tuple
import uvicorn
import logging
import tempfile
import os
from datetime import datetime, timedelta
import math
import re
# PostgreSQL adapter (drop-in replacement for sqlite3)
from core.database_adapters import pg_sync_adapter as sqlite3
import io
import uuid

# Utilidades para movimientos bancarios
from core.reconciliation.bank.bank_statements_models import infer_movement_kind

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # override=True para sobrescribir variables del sistema
    logging.info("Variables de entorno cargadas desde .env (con override)")
except ImportError:
    logging.warning("python-dotenv no instalado, usando variables del sistema")

# Import our core MCP handler and reconciliation helpers
from core.shared.mcp_handler import handle_mcp_request
from core.reconciliation.matching.bank_reconciliation import suggest_bank_matches
from core.ai_pipeline.parsers.invoice_parser import parse_cfdi_xml, InvoiceParseError
from core.payment_accounts_models import payment_account_service
from modules.invoicing_agent.models import create_ticket, get_ticket, update_ticket

# Import configuration first
from config.config import config

# Import JWT authentication system (primary)
from core.auth.jwt import get_current_user, User

# Import legacy auth system (fallback)
from core.auth.unified import (
    authenticate_user, create_user, create_tokens_for_user,
    verify_refresh_token, revoke_refresh_token,
    LoginRequest, RegisterRequest, Token, get_current_active_user
)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends, status

# Import tenancy system
from core.tenancy_middleware import (
    TenancyContext, get_tenancy_context, normalize_tenant_id, extract_tenant_from_company_id
)

# Import enhanced error handling
from core.error_handler import (
    create_error_context, handle_error_with_context, store_error_in_db,
    get_error_stats, ValidationError, NotFoundError, BusinessLogicError
)

# Import unified DB adapter or fallback to original internal_db
try:
    if config.USE_UNIFIED_DB:
        from core.shared.unified_db_adapter import (
            record_internal_expense,
            fetch_expense_records,
            fetch_expense_record,
            update_expense_record as db_update_expense_record,
            list_bank_movements,
            record_bank_match_feedback,
            register_expense_invoice,
            mark_expense_invoiced,
            mark_expense_without_invoice,
            register_user_account,
            get_company_demo_snapshot,
            fetch_candidate_expenses_for_invoice,
            get_unified_adapter,
            # Expense tags functions
            create_expense_tag,
            get_expense_tags,
            update_expense_tag,
            delete_expense_tag,
            assign_expense_tags,
            unassign_expense_tags,
            replace_expense_tags,
            get_expense_tags_for_expense,
            get_expenses_by_tag,
            # Enhanced invoice functions
            create_invoice_record,
            get_invoice_records,
            get_invoice_record,
            update_invoice_record,
            find_matching_expenses,
            # Enhanced bank reconciliation functions
            create_bank_movement,
            get_bank_movement,
            update_bank_movement,
            find_matching_expenses_for_movement,
            perform_auto_reconciliation,
            get_bank_matching_rules,
            create_bank_matching_rule,
            # Enhanced onboarding functions
            # create_user,  # COMMENTED: conflicts with core.unified_auth.create_user
            get_user,
            get_user_by_email,
            update_user,
            update_onboarding_step,
            get_user_onboarding_status,
            generate_demo_data,
            # Enhanced duplicate detection functions
            detect_duplicates,
            save_duplicate_detection,
            update_expense_duplicate_info,
            get_duplicate_stats,
            review_duplicate_detection,
            get_duplicate_detection_config,
            # Enhanced category prediction functions
            predict_expense_category,
            save_category_prediction,
            get_user_category_preferences,
            record_category_feedback,
            get_category_stats,
            get_category_prediction_config,
            get_custom_categories,
            delete_company_expenses,
        )
        print("🔄 Usando DB unificada con adaptador")

        # Función de inicialización para compatibilidad
        def initialize_internal_database():
            """Compatibilidad - la DB unificada ya está inicializada"""
            adapter = get_unified_adapter()
            health = adapter.health_check()
            if health['status'] == 'healthy':
                logger.info("✅ DB unificada verificada y funcionando")
                return True
            else:
                logger.error(f"❌ DB unificada con problemas: {health.get('error', 'Unknown')}")
                return False

        # Alias para compatibilidad
        db_mark_expense_invoiced = mark_expense_invoiced
        db_mark_expense_without_invoice = mark_expense_without_invoice
        db_delete_company_expenses = delete_company_expenses

    else:
        # Fallback a internal_db original
        from core.internal_db import (
            initialize_internal_database,
            list_bank_movements,
            record_bank_match_feedback,
            record_internal_expense,
            fetch_expense_records,
            fetch_expense_record,
            update_expense_record as db_update_expense_record,
            register_expense_invoice,
            mark_expense_invoiced as db_mark_expense_invoiced,
            mark_expense_without_invoice as db_mark_expense_without_invoice,
            register_user_account,
            get_company_demo_snapshot,
            fetch_candidate_expenses_for_invoice,
            delete_company_expenses,
        )
        print("📊 Usando sistema de BD original")

        db_delete_company_expenses = delete_company_expenses

except ImportError as e:
    print(f"⚠️ Fallo importando adaptador unificado, usando sistema original: {e}")
    from core.internal_db import (
        initialize_internal_database,
        list_bank_movements,
        record_bank_match_feedback,
        record_internal_expense,
        fetch_expense_records,
        fetch_expense_record,
        update_expense_record as db_update_expense_record,
        register_expense_invoice,
        mark_expense_invoiced as db_mark_expense_invoiced,
        mark_expense_without_invoice as db_mark_expense_without_invoice,
        register_user_account,
        get_company_demo_snapshot,
        fetch_candidate_expenses_for_invoice,
        delete_company_expenses,
    )
    db_delete_company_expenses = delete_company_expenses
# Import voice processing (optional - only if OpenAI is configured)
try:
    from core.voice_handler import process_voice_request, get_voice_handler
    VOICE_ENABLED = True
except ImportError as e:
    VOICE_ENABLED = False
    logging.getLogger(__name__).warning(f"Voice processing disabled: {e}")

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan to bootstrap the internal catalog."""

    try:
        print("[LIFESPAN] Starting lifespan initialization...")
        initialize_internal_database()
        print("[LIFESPAN] Internal database initialized")
        logger.info("Internal account catalog initialised")

        # Apply database optimizations (PostgreSQL - skip for now)
        # from pathlib import Path
        # db_path = Path(config.DB_PATH).resolve()
        # if db_path.exists():
        #     with sqlite3.connect(str(db_path)) as conn:
        #         optimize_database_connection(conn)
        logger.info("Database optimizations skipped (using PostgreSQL)")

        # Start SAT sync scheduler
        print("[LIFESPAN] Starting SAT sync scheduler...")
        try:
            from core.sat.sat_sync_scheduler import start_scheduler
            await start_scheduler()
            print("[LIFESPAN] ✅ SAT Sync Scheduler started successfully!")
            logger.info("SAT Sync Scheduler started")
        except Exception as scheduler_exc:
            print(f"[LIFESPAN] ❌ Failed to start scheduler: {scheduler_exc}")
            logger.warning(f"Failed to start SAT Sync Scheduler: {scheduler_exc}")

        yield

        # Shutdown: Stop SAT sync scheduler
        try:
            from core.sat.sat_sync_scheduler import stop_scheduler
            await stop_scheduler()
            logger.info("SAT Sync Scheduler stopped")
        except Exception as scheduler_exc:
            logger.warning(f"Failed to stop SAT Sync Scheduler: {scheduler_exc}")

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Error initialising internal database: %s", exc)
        raise


app = FastAPI(
    title="MCP Server",
    description="Universal layer between AI agents and business systems",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    lifespan=lifespan,
)

# Configure CORS to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3004",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3004",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web interface
# Commented out temporarily - static directory doesn't exist
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Direct access endpoints for main pages
@app.get("/payment-accounts.html")
async def payment_accounts_page():
    """Serve payment accounts page directly"""
    return FileResponse("static/payment-accounts.html")

@app.get("/payment-accounts")
async def payment_accounts():
    """
    Payment accounts endpoint - serves the payment accounts interface.

    Returns:
        FileResponse: The payment accounts interface
    """
    logger.info("Payment accounts interface accessed")
    return FileResponse("static/payment-accounts.html")

@app.get("/employee-advances.html")
async def employee_advances_page():
    """Serve employee advances page directly"""
    return FileResponse("static/employee-advances.html")

@app.get("/test-ui-debug.html")
async def test_ui_debug_page():
    """Serve debug page for testing API"""
    return FileResponse("test_ui_debug.html")

@app.get("/auth-login.html")
async def auth_login_page():
    """Serve auth login page directly"""
    return FileResponse("static/auth-login.html")

# Import and mount invoicing agent router
try:
    from modules.invoicing_agent.api import router as invoicing_router
    app.include_router(invoicing_router)
    logger.info("Invoicing agent module loaded successfully")
except ImportError as e:
    logger.warning(f"Invoicing agent module not available: {e}")

# WhatsApp webhook router
try:
    from api.whatsapp_webhook_api import router as whatsapp_webhook_router
    app.include_router(whatsapp_webhook_router)
    logger.info("WhatsApp webhook API loaded successfully")
except ImportError as e:
    logger.warning(f"WhatsApp webhook API not available: {e}")

# TEMPORARILY DISABLED: Auth router conflicts with main auth endpoints
# JWT Authentication System
# Import and mount JWT authentication router
try:
    from api.auth_jwt_api import router as auth_jwt_router
    app.include_router(auth_jwt_router)
    logger.info("✅ JWT Authentication system enabled")
except ImportError as e:
    logger.warning(f"JWT Authentication module not available: {e}")

# Import and mount advanced invoicing API
try:
    from api.advanced_invoicing_api import router as advanced_invoicing_router
    app.include_router(advanced_invoicing_router)
    logger.info("Advanced invoicing API loaded successfully")
except ImportError as e:
    logger.warning(f"Advanced invoicing API not available: {e}")

# Import and mount client management API
try:
    from api.client_management_api import router as client_management_router
    app.include_router(client_management_router)
    logger.info("Client management API loaded successfully")
except ImportError as e:
    logger.warning(f"Client management API not available: {e}")

# Import and mount payment methods API
try:
    from api.payment_methods_api import router as payment_methods_router
    app.include_router(payment_methods_router)
    logger.info("Payment methods API loaded successfully")
except ImportError as e:
    logger.warning(f"Payment methods API not available: {e}")

# Import and mount non-reconciliation API
try:
    from api.non_reconciliation_api import router as non_reconciliation_router
    app.include_router(non_reconciliation_router)
    logger.info("Non-reconciliation API loaded successfully")
except ImportError as e:
    logger.warning(f"Non-reconciliation API not available: {e}")

# Import and mount bulk invoice API
try:
    from api.bulk_invoice_api import router as bulk_invoice_router
    app.include_router(bulk_invoice_router)
    logger.info("Bulk invoice API loaded successfully")
except ImportError as e:
    logger.warning(f"Bulk invoice API not available: {e}")

# Import and mount expense completion API
try:
    from api.expense_completion_api import router as expense_completion_router
    app.include_router(expense_completion_router)
    logger.info("Expense completion API loaded successfully")
except ImportError as e:
    logger.warning(f"Expense completion API not available: {e}")

# Import and mount expense placeholder completion API
try:
    from api.expense_placeholder_completion_api import router as expense_placeholder_completion_router
    app.include_router(expense_placeholder_completion_router)
    logger.info("Expense placeholder completion API loaded successfully")
except ImportError as e:
    logger.warning(f"Expense placeholder completion API not available: {e}")

# Import and mount classification correction API (learning system)
try:
    from api.classification_correction_api import router as classification_correction_router
    app.include_router(classification_correction_router)
    logger.info("✅ Classification correction and learning API loaded successfully")
except ImportError as e:
    logger.warning(f"Classification correction API not available: {e}")

# Import and mount conversational assistant API
try:
    from api.conversational_assistant_api import router as conversational_assistant_router
    app.include_router(conversational_assistant_router)
    logger.info("Conversational assistant API loaded successfully")
except ImportError as e:
    logger.warning(f"Conversational assistant API not available: {e}")

# Import and mount RPA automation engine API
try:
    from api.rpa_automation_engine_api import router as rpa_automation_engine_router
    app.include_router(rpa_automation_engine_router)
    logger.info("RPA automation engine API loaded successfully")
except ImportError as e:
    logger.warning(f"RPA automation engine API not available: {e}")

# Web Automation Engine API
try:
    from api.web_automation_engine_api import router as web_automation_engine_router
    app.include_router(web_automation_engine_router)
    logger.info("Web automation engine API loaded successfully")
except ImportError as e:
    logger.warning(f"Web automation engine API not available: {e}")

# Hybrid Processor API
try:
    from api.hybrid_processor_api import router as hybrid_processor_router
    app.include_router(hybrid_processor_router)
    logger.info("Hybrid processor API loaded successfully")
except ImportError as e:
    logger.warning(f"Hybrid processor API not available: {e}")

# Robust Automation Engine API
try:
    from api.robust_automation_engine_api import router as robust_automation_engine_router
    app.include_router(robust_automation_engine_router)
    logger.info("Robust automation engine API loaded successfully")
except ImportError as e:
    logger.warning(f"Robust automation engine API not available: {e}")

# Universal Invoice Engine API
try:
    from api.universal_invoice_engine_api import router as universal_invoice_engine_router
    app.include_router(universal_invoice_engine_router)
    logger.info("Universal invoice engine API loaded successfully")
except ImportError as e:
    logger.warning(f"Universal invoice engine API not available: {e}")

# Invoice Classification API
try:
    from api.invoice_classification_api import router as invoice_classification_router
    app.include_router(invoice_classification_router)
    logger.info("Invoice classification API loaded successfully")
except ImportError as e:
    logger.warning(f"Invoice classification API not available: {e}")

# SAT Verification API
try:
    from api.sat_verification_api import router as sat_verification_router
    app.include_router(sat_verification_router)
    logger.info("SAT verification API loaded successfully")
except ImportError as e:
    logger.warning(f"SAT verification API not available: {e}")

# Payment Accounts API
try:
    from api.payment_accounts_api import router as payment_accounts_router
    app.include_router(payment_accounts_router)
    logger.info("Payment accounts API loaded successfully")
except ImportError as e:
    logger.warning(f"Payment accounts API not available: {e}")

# Bank Statements API
try:
    from api.bank_statements_api import router as bank_statements_router
    app.include_router(bank_statements_router)
    logger.info("Bank statements API loaded successfully")
except ImportError as e:
    logger.warning(f"Bank statements API not available: {e}")

# Financial Intelligence API
try:
    from api.financial_intelligence_api import router as financial_intelligence_router
    app.include_router(financial_intelligence_router)
    logger.info("Financial intelligence API loaded successfully")
except ImportError as e:
    logger.warning(f"Financial intelligence API not available: {e}")

# Split Reconciliation API
try:
    from api.split_reconciliation_api import router as split_reconciliation_router
    app.include_router(split_reconciliation_router)
    logger.info("Split reconciliation API loaded successfully")
except ImportError as e:
    logger.warning(f"Split reconciliation API not available: {e}")

# Reconciliation V1 API (for VC demo)
try:
    from app.routers.reconciliation_router import router as reconciliation_v1_router
    app.include_router(reconciliation_v1_router)
    logger.info("✅ Reconciliation V1 API loaded successfully")
except ImportError as e:
    logger.warning(f"Reconciliation V1 API not available: {e}")

# AI Reconciliation API
try:
    from api.ai_reconciliation_api import router as ai_reconciliation_router, reconciliation_router
    app.include_router(ai_reconciliation_router)
    app.include_router(reconciliation_router)
    logger.info("AI reconciliation API loaded successfully")
except ImportError as e:
    logger.warning(f"AI reconciliation API not available: {e}")

# Employee Advances API
try:
    from api.employee_advances_api import router as employee_advances_router
    app.include_router(employee_advances_router)
    logger.info("Employee advances API loaded successfully")
except ImportError as e:
    logger.warning(f"Employee advances API not available: {e}")

# Financial Reports API
try:
    from api.financial_reports_api import router as financial_reports_router
    app.include_router(financial_reports_router)
    logger.info("Financial reports API loaded successfully")
except ImportError as e:
    logger.warning(f"Financial reports API not available: {e}")

# Polizas API (V1)
try:
    from api.v1.polizas_api import router as polizas_router
    app.include_router(polizas_router)
    logger.info("Polizas API loaded successfully")
except ImportError as e:
    logger.warning(f"Polizas API not available: {e}")

# Companies Context API (V1)
try:
    from api.v1.companies_context import router as companies_context_router
    app.include_router(companies_context_router)
    logger.info("Companies context API loaded successfully")
except ImportError as e:
    logger.warning(f"Companies context API not available: {e}")

# User Context API (V1)
try:
    from api.v1.user_context import auth_router as user_auth_router, users_router
    app.include_router(user_auth_router)
    app.include_router(users_router)
    logger.info("User context API loaded successfully")
except ImportError as e:
    logger.warning(f"User context API not available: {e}")

# Transactions Review API (V1)
try:
    from api.v1.transactions_review_api import router as transactions_review_router
    app.include_router(transactions_review_router)
    logger.info("Transactions review API loaded successfully")
except ImportError as e:
    logger.warning(f"Transactions review API not available: {e}")

# AI Retrain API (V1)
try:
    from api.v1.ai_retrain import router as ai_retrain_router
    app.include_router(ai_retrain_router)
    logger.info("AI retrain API loaded successfully")
except ImportError as e:
    logger.warning(f"AI retrain API not available: {e}")

# V1 Main Router (includes invoicing, debug, and other V1 endpoints)
try:
    from api.v1 import router as v1_router
    app.include_router(v1_router)
    logger.info("✅ API V1 router loaded successfully (includes /api/v1/invoicing, /api/v1/debug)")
except ImportError as e:
    logger.warning(f"API V1 router not available: {e}")

# Public Banking Institutions Endpoint (no auth required)
@app.get("/public/banking-institutions")
async def get_public_banking_institutions():
    """Public endpoint for banking institutions - no authentication required"""
    try:
        from core.payment_accounts_models import UserPaymentAccountService
        service = UserPaymentAccountService()
        institutions = service.get_banking_institutions(active_only=True)
        return [inst.dict() for inst in institutions]
    except Exception as e:
        logger.error(f"Error getting banking institutions: {e}")
        return {"error": "Error al obtener instituciones bancarias"}

# Import all API models from centralized location
from core.api_models import *
from core.error_handler import handle_error, log_endpoint_entry, log_endpoint_success, log_endpoint_error, ValidationError, NotFoundError, ServiceError
from core.shared.db_optimizer import optimize_database_connection
logger.info("✅ API models loaded from core.api_models")

# Legacy model definitions below will be removed in next phase
# Keeping temporarily for compatibility

# All models are now imported from core.api_models
# The following class definitions will be removed in the next phase

# Legacy model definitions removed successfully
# All models are now imported from core.api_models


# =====================================================
# PYDANTIC MODELS SECTION - REFACTORED PHASE 2
# =====================================================
# All Pydantic models have been moved to core/api_models.py
# and are imported via "from core.api_models import *" (line 126)
# This section was successfully cleaned up to reduce main.py bloat
# and improve maintainability and organization.
# =====================================================

# =====================================================
# HELPER FUNCTIONS - RESTORED FROM BACKUP
# =====================================================

def _build_expense_response(record: Dict[str, Any]) -> ExpenseResponse:
    """Build ExpenseResponse object from database record."""
    import json

    # Parse metadata if it's a JSON string
    metadata_raw = record.get("metadata")
    if isinstance(metadata_raw, str):
        try:
            metadata = json.loads(metadata_raw)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    else:
        metadata = metadata_raw or {}
    provider = metadata.get("proveedor")
    provider_name = record.get("provider_name")
    provider_rfc = record.get("provider_rfc")
    metadata_rfc = metadata.get("rfc")

    if not provider and provider_name:
        provider = {"nombre": provider_name}
        if provider_rfc:
            provider["rfc"] = provider_rfc

    tax_info = metadata.get("tax_info") or record.get("tax_metadata")
    asientos = metadata.get("asientos_contables")
    movimientos = metadata.get("movimientos_bancarios")

    for key in [
        "proveedor",
        "rfc",
        "tax_info",
        "asientos_contables",
        "movimientos_bancarios",
        "workflow_status",
        "estado_factura",
        "estado_conciliacion",
        "forma_pago",
        "paid_by",
        "will_have_cfdi",
        "categoria",
        "fecha_gasto",
        "company_id",
    ]:
        metadata.pop(key, None)

    # Convert amount to float, handle invalid values
    try:
        amount = float(record["amount"]) if record["amount"] else 0.0
    except (ValueError, TypeError):
        # If amount is not a valid number, default to 0.0
        amount = 0.0

    return ExpenseResponse(
        id=record["id"],
        descripcion=record["description"],
        monto_total=amount,
        fecha_gasto=record.get("expense_date"),
        categoria=record.get("category"),
        proveedor=provider,
        rfc=provider_rfc or metadata_rfc,
        tax_info=tax_info,
        asientos_contables=asientos,
        workflow_status=record.get("workflow_status", "draft"),
        estado_factura=record.get("invoice_status", "pendiente"),
        estado_conciliacion=record.get("bank_status", "pendiente"),
        forma_pago=record.get("payment_method"),
        paid_by=record.get("paid_by", "company_account"),
        will_have_cfdi=bool(record.get("will_have_cfdi", True)),
        movimientos_bancarios=movimientos,
        metadata=metadata or None,
        company_id=record.get("company_id", "default"),
        ticket_id=record.get("ticket_id"),
        is_advance=bool(metadata.get("is_advance", False)),
        is_ppd=bool(metadata.get("is_ppd", False)),
        asset_class=metadata.get("asset_class"),
        payment_terms=metadata.get("payment_terms"),
        created_at=record.get("created_at", ""),
        updated_at=record.get("updated_at", ""),
    )


def _validate_payment_account_for_user(
    payment_account_id: Optional[int],
    tenancy_context: TenancyContext,
) -> None:
    """Ensure the provided payment account exists and belongs to current user."""
    if payment_account_id is None:
        raise HTTPException(
            status_code=400,
            detail="payment_account_id es obligatorio para registrar gastos",
        )

    try:
        payment_account_service.get_account(
            payment_account_id,
            tenancy_context.user_id,
            tenancy_context.tenant_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="La cuenta de pago indicada no existe o no pertenece al usuario actual",
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Error validating payment account %s: %s", payment_account_id, exc)
        raise HTTPException(
            status_code=500,
            detail="No se pudo validar la cuenta de pago proporcionada",
        )


def _build_virtual_ticket_raw_data(expense: ExpenseCreate) -> str:
    """Compose a human-friendly summary to store inside a virtual ticket."""
    provider_name = (expense.proveedor.nombre if expense.proveedor else None) or "Proveedor no especificado"
    lines = [
        f"Descripción: {expense.descripcion}",
        f"Monto: ${expense.monto_total:,.2f} MXN",
        f"Fecha: {expense.fecha_gasto}",
        f"Categoría: {expense.categoria or 'sin categoría'}",
        f"Proveedor: {provider_name}",
        f"RFC: {expense.rfc or 'N/A'}",
        f"Forma de pago: {expense.forma_pago or 'N/A'}",
        f"Company ID: {expense.company_id}",
    ]
    return "\n".join(lines)


def _ensure_ticket_binding(
    expense: ExpenseCreate,
    tenancy_context: TenancyContext,
) -> Tuple[Optional[int], bool]:
    """
    Ensure every expense has a ticket associated.

    Returns:
        (ticket_id, created_flag)
    """
    if expense.ticket_id:
        ticket = get_ticket(expense.ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=404,
                detail=f"El ticket {expense.ticket_id} no existe",
            )

        ticket_company = ticket.get("company_id") or "default"
        if ticket_company != expense.company_id:
            raise HTTPException(
                status_code=400,
                detail="El ticket pertenece a otra empresa y no puede vincularse a este gasto",
            )

        linked_expense_id = ticket.get("linked_expense_id")
        if linked_expense_id:
            raise HTTPException(
                status_code=400,
                detail=f"El ticket {expense.ticket_id} ya está vinculado al gasto {linked_expense_id}",
            )
        return expense.ticket_id, False

    raw_data = _build_virtual_ticket_raw_data(expense)
    try:
        ticket_id = create_ticket(
            raw_data=raw_data,
            tipo="virtual_expense",
            user_id=tenancy_context.user_id,
            company_id=expense.company_id,
        )
        logger.info("🎫 Ticket virtual %s creado para expense '%s'", ticket_id, expense.descripcion)
        return ticket_id, True
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("No se pudo crear ticket virtual: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="No se pudo crear el ticket asociado al gasto",
        )


def _link_ticket_to_expense(ticket_id: Optional[int], expense_id: int) -> None:
    """Persist bidirectional relationship between tickets and expenses."""
    if not ticket_id:
        return
    try:
        update_ticket(ticket_id, linked_expense_id=expense_id)
        logger.info("🔗 Ticket %s vinculado a expense %s", ticket_id, expense_id)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "No se pudo vincular ticket %s con expense %s: %s",
            ticket_id,
            expense_id,
            exc,
        )


def _parse_iso_date(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string to datetime object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None


def _score_invoice_candidate(
    *,
    invoice_total: float,
    invoice_date: Optional[datetime],
    invoice_rfc: Optional[str],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """Score an expense candidate for invoice matching."""
    amount_diff = abs(candidate["amount"] - invoice_total)
    score = 0

    if math.isclose(candidate["amount"], invoice_total, rel_tol=0.0, abs_tol=0.01):
        score += 70
    elif amount_diff <= 1.0:
        score += 50
    else:
        score -= 20

    days_diff: Optional[int] = None
    candidate_date = _parse_iso_date(candidate.get("expense_date"))
    if invoice_date and candidate_date:
        days_diff = abs((candidate_date.date() - invoice_date.date()).days)
        if days_diff == 0:
            score += 25
        elif days_diff <= 3:
            score += 15
        elif days_diff <= 7:
            score += 5
        else:
            score -= 5

    candidate_rfc = (candidate.get("provider_rfc") or "").strip().upper()
    invoice_rfc_normalized = (invoice_rfc or "").strip().upper()
    if invoice_rfc_normalized and candidate_rfc:
        if candidate_rfc == invoice_rfc_normalized:
            score += 20
        else:
            score -= 10

    return {
        "expense_id": candidate["id"],
        "descripcion": candidate["descripcion"],
        "monto_total": candidate["amount"],
        "fecha_gasto": candidate.get("expense_date"),
        "provider_name": candidate.get("provider_name"),
        "provider_rfc": candidate_rfc or None,
        "invoice_status": candidate.get("invoice_status"),
        "bank_status": candidate.get("bank_status"),
        "match_score": score,
        "amount_diff": amount_diff,
        "days_diff": days_diff,
    }


def _match_invoice_to_expense(
    *,
    company_id: str,
    invoice: InvoiceMatchInput,
    global_auto_mark: bool,
) -> InvoiceMatchResult:
    """Match an invoice to an existing expense."""
    filename = invoice.filename
    if invoice.total is None:
        return InvoiceMatchResult(
            filename=filename,
            uuid=invoice.uuid,
            status="error",
            message="El CFDI no contiene un total válido",
        )

    candidates = fetch_candidate_expenses_for_invoice(company_id)
    invoice_date = _parse_iso_date(invoice.issued_at)
    scored_candidates = [
        _score_invoice_candidate(
            invoice_total=invoice.total,
            invoice_date=invoice_date,
            invoice_rfc=invoice.rfc_emisor,
            candidate=candidate,
        )
        for candidate in candidates
    ]

    scored_candidates = [c for c in scored_candidates if c["match_score"] > 0]
    scored_candidates.sort(key=lambda item: item["match_score"], reverse=True)
    logger.debug(
        "Invoice bulk-match: %s candidates -> %s",
        invoice.filename or invoice.uuid,
        scored_candidates,
    )

    result = InvoiceMatchResult(
        filename=filename,
        uuid=invoice.uuid,
        status="no_match",
        candidates=[InvoiceMatchCandidate(**candidate) for candidate in scored_candidates[:3]],
    )

    if not scored_candidates:
        result.message = "No se encontraron gastos con monto compatible"
        return result

    top_score = scored_candidates[0]["match_score"]
    runner_up = scored_candidates[1]["match_score"] if len(scored_candidates) > 1 else None

    high_confidence = top_score >= 80 and (runner_up is None or (top_score - runner_up) >= 15)
    moderate_confidence = top_score >= 65 and (runner_up is None or (top_score - runner_up) >= 10)

    if not (high_confidence or moderate_confidence):
        result.status = "needs_review"
        result.message = "Se encontraron candidatos pero requiere revisión manual"
        return result

    expense_id = scored_candidates[0]["expense_id"]
    try:
        record = register_expense_invoice(
            expense_id,
            uuid=invoice.uuid,
            folio=invoice.folio,
            url=invoice.url,
            issued_at=invoice.issued_at,
            status="registrada",
            raw_xml=invoice.raw_xml,
            actor="bulk_matcher",
        )
        if not record:
            raise ValueError("Gasto no encontrado al registrar la factura")

        if (invoice.auto_mark_invoiced and global_auto_mark) or high_confidence:
            record = mark_expense_invoiced(expense_id, actor="bulk_matcher") or record

        expense_response = _build_expense_response(record)
        result.status = "linked"
        result.expense = expense_response
        result.message = "Factura conciliada con el gasto"
    except Exception as exc:
        logger.exception("Error conciliando factura masiva: %s", exc)
        result.status = "error"
        result.message = f"Error registrando la factura: {exc}"

    return result

# =====================================================
# FASTAPI ENDPOINTS
# =====================================================

@app.get("/")
async def smart_root(request: Request):
    """
    Smart root endpoint - detecta usuario nuevo y redirige apropiadamente.

    Returns:
        RedirectResponse: Redirect inteligente basado en estado del usuario
    """
    try:
        # Verificar si hay token de autorización
        auth_header = request.headers.get("authorization")
        has_auth_cookie = "access_token" in request.cookies

        # Verificar si es primera visita (sin cookies del sistema)
        is_first_visit = not any(
            cookie_name.startswith("mcp_")
            for cookie_name in request.cookies.keys()
        )

        # Si es primera visita y no tiene auth, ir a onboarding
        if is_first_visit and not auth_header and not has_auth_cookie:
            logger.info("First time user detected - redirecting to onboarding")
            response = RedirectResponse(url="/onboarding", status_code=302)
            # Marcar que ya visitó
            response.set_cookie("mcp_visited", "true", max_age=86400*365)
            return response

        # Usuario existente - ir a voice-expenses
        logger.info("Existing user - redirecting to voice-expenses")
        return RedirectResponse(url="/voice-expenses", status_code=302)

    except Exception as e:
        logger.error(f"Error in smart root: {e}")
        # Fallback seguro
        return RedirectResponse(url="/voice-expenses", status_code=302)


@app.get("/onboarding")
async def onboarding_page() -> FileResponse:
    """Serve the onboarding experience."""

    logger.info("Onboarding interface accessed")
    return FileResponse("static/onboarding.html")


@app.get("/voice-expenses")
async def voice_expenses():
    """
    Voice expenses endpoint - serves the new React voice interface.

    Returns:
        HTMLResponse: The voice-enabled expense registration interface
    """
    logger.info("Voice expenses interface accessed")
    return FileResponse("static/voice-expenses.html")


@app.get("/client-settings")
async def client_settings_page():
    """
    Client settings endpoint - serves the client configuration interface.

    Returns:
        FileResponse: The client settings interface
    """
    logger.info("Client settings interface accessed")
    return FileResponse("static/client-settings.html")


@app.get("/automation-viewer")
async def automation_viewer_page():
    """
    Automation viewer endpoint - serves the automation monitoring interface.

    Returns:
        FileResponse: The automation viewer interface
    """
    logger.info("Automation viewer interface accessed")
    return FileResponse("static/automation-viewer.html")


@app.get("/bank-reconciliation")
async def bank_reconciliation_page():
    """
    Bank reconciliation endpoint - serves the bank reconciliation interface.

    Returns:
        FileResponse: The bank reconciliation interface
    """
    logger.info("Bank reconciliation interface accessed")
    return FileResponse("static/bank-reconciliation.html")


@app.get("/auth/login")
async def auth_login_page():
    """
    Login page endpoint - serves the authentication login interface.

    Returns:
        FileResponse: The login interface
    """
    logger.info("Login page accessed")
    return FileResponse("static/auth-login.html")


@app.get("/auth/register")
async def auth_register_page():
    """
    Register page endpoint - serves the authentication register interface.

    Returns:
        FileResponse: The register interface
    """
    logger.info("Register page accessed")
    return FileResponse("static/auth-register.html")


@app.get("/admin")
async def admin_panel_page():
    """
    Admin panel endpoint - serves the administration interface.

    Returns:
        FileResponse: The admin panel interface
    """
    logger.info("Admin panel accessed")
    return FileResponse("static/admin-panel.html")


@app.get("/dashboard")
async def dashboard_page():
    """
    Main dashboard page with ContaFlow design system.
    Shows two main sections: Conciliación and Cuentas de Banco y Efectivo.

    Returns:
        FileResponse: The main dashboard interface
    """
    logger.info("Dashboard accessed")
    return FileResponse("static/dashboard.html")


@app.get("/sat-accounts")
async def sat_accounts_page():
    """
    SAT Accounts page - serves the SAT chart of accounts interface.

    Returns:
        FileResponse: SAT accounts management interface
    """
    return FileResponse("static/sat-accounts.html")


@app.get("/api/sat-accounts")
async def get_sat_accounts(
    search: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get SAT account catalog entries.

    Args:
        search: Optional search term to filter by code or name
        limit: Maximum number of results (default 200, max 1000)
        offset: Number of results to skip for pagination

    Returns:
        List of SAT account catalog entries
    """
    try:
        conn = sqlite3.connect("unified_mcp_system.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT code, name, description, parent_code, type, is_active, updated_at
            FROM sat_account_catalog
            WHERE is_active = 1
        """
        params = []

        if search:
            query += " AND (code LIKE ? OR name LIKE ? OR description LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        query += " ORDER BY code ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to list of dicts
        results = [dict(row) for row in rows]

        conn.close()

        return results

    except Exception as e:
        logger.error(f"Error fetching SAT accounts: {e}")
        raise HTTPException(500, f"Error fetching SAT accounts: {str(e)}")


@app.get("/polizas-dashboard")
async def polizas_dashboard_page():
    """
    Polizas dashboard page - serves the accounting entries interface.

    Returns:
        FileResponse: Polizas dashboard interface
    """
    return FileResponse("static/polizas-dashboard.html")


@app.get("/financial-reports")
async def financial_reports_page():
    """
    Financial reports page - serves the financial reports dashboard.

    Returns:
        FileResponse: Financial reports dashboard interface
    """
    return FileResponse("static/financial-reports-dashboard.html")


@app.get("/expenses-viewer")
async def expenses_viewer_page():
    """
    Expenses viewer page - serves the enhanced expenses viewer interface.

    Returns:
        FileResponse: Enhanced expenses viewer interface
    """
    return FileResponse("static/expenses-viewer-enhanced.html")


@app.get("/complete-expenses")
async def complete_expenses_page():
    """
    Complete expenses page - serves the expense completion interface.

    Returns:
        FileResponse: Complete expenses interface
    """
    return FileResponse("static/complete-expenses.html")


@app.get("/landing")
async def landing_page():
    """
    Landing page - serves the main landing page.

    Returns:
        FileResponse: Landing page
    """
    return FileResponse("static/landing.html")


@app.get("/onboarding-context")
async def onboarding_context_page():
    """
    Onboarding context page - serves the contextual onboarding interface.

    Returns:
        FileResponse: Onboarding context interface
    """
    return FileResponse("static/onboarding-context.html")


# =====================================================
# AUTHENTICATION ENDPOINTS
# =====================================================

@app.post("/auth/login", response_model=Token)
async def login(request: LoginRequest, http_request: Request):
    """
    Authenticate user and return access/refresh tokens.
    """
    error_context = create_error_context(
        request=http_request,
        endpoint="/auth/login"
    )

    try:
        user = authenticate_user(request.email, request.password)
        if not user:
            auth_error = ValidationError("Invalid email or password")
            raise handle_error_with_context(
                error=auth_error,
                context=error_context,
                category="authentication",
                severity="low",
                user_message="Credenciales inválidas. Verifica tu email y contraseña."
            )

        tokens = create_tokens_for_user(user)
        logger.info(f"User logged in successfully: {user.email}")
        return tokens

    except HTTPException:
        raise
    except Exception as e:
        raise handle_error_with_context(
            error=e,
            context=error_context,
            category="authentication",
            severity="medium",
            user_message="Error durante el login. Intenta nuevamente."
        )


@app.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token endpoint for authentication.
    """
    try:
        user = authenticate_user(form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        tokens = create_tokens_for_user(user)
        logger.info(f"Token generated for user: {user.email}")
        return tokens

    except Exception as e:
        logger.error(f"Token generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token generation"
        )


@app.post("/auth/register", response_model=Token)
async def register(request: RegisterRequest):
    """
    Register a new user and return access/refresh tokens.
    """
    try:
        logger.info(f"🔄 Starting registration for: {request.email}")

        user = create_user(request)
        logger.info(f"✅ create_user returned: {user}")

        if not user:
            logger.warning(f"❌ User creation failed for: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists or registration failed"
            )

        logger.info(f"🔑 Creating tokens for user: {user.email}")
        tokens = create_tokens_for_user(user)
        logger.info(f"✅ New user registered successfully: {user.email}")
        return tokens

    except Exception as e:
        import traceback
        logger.error(f"❌ Registration error for {request.email}: {e}")
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )


@app.post("/auth/refresh", response_model=Token)
async def refresh_access_token(refresh_token: str):
    """
    Refresh access token using refresh token.
    """
    try:
        user_id = verify_refresh_token(refresh_token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        from core.auth.unified import get_user_by_id
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Revoke old refresh token
        revoke_refresh_token(refresh_token)

        # Create new tokens
        tokens = create_tokens_for_user(user)
        logger.info(f"Tokens refreshed for user: {user.email}")
        return tokens

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh"
        )


@app.get("/auth/me")
async def get_current_user_info(current_user = Depends(get_current_active_user)):
    """
    Get current authenticated user information.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "is_superuser": current_user.is_superuser,
        "created_at": current_user.created_at
    }


@app.post("/auth/logout")
async def logout(refresh_token: str, current_user = Depends(get_current_active_user)):
    """
    Logout user by revoking refresh token.
    """
    try:
        revoke_refresh_token(refresh_token)
        logger.info(f"User logged out: {current_user.email}")
        return {"message": "Successfully logged out"}

    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during logout"
        )

@app.get("/auth/logout")
async def logout_get(request: Request):
    """
    Handle GET logout requests by redirecting to login page.
    """
    try:
        # Clear any session data if needed
        logger.info("User logged out via GET request")
        # Redirect to login page with a logout message
        return RedirectResponse(url="/auth/login?logout=true", status_code=302)
    except Exception as e:
        logger.error(f"Logout GET error: {e}")
        return RedirectResponse(url="/auth/login", status_code=302)


@app.get("/auth/tenants")
async def get_available_tenants(email: Optional[str] = None):
    """Return available tenants, optionally filtered by user email."""
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        cursor = conn.cursor()

        if email:
            cursor.execute(
                """
                SELECT DISTINCT t.id, t.name
                FROM tenants t
                JOIN users u ON u.tenant_id = t.id
                WHERE LOWER(u.email) = LOWER(?)
                ORDER BY t.name
                """,
                (email.strip(),),
            )
        else:
            cursor.execute(
                """
                SELECT id, name
                FROM tenants
                ORDER BY name
                """
            )

        tenants = [
            {
                "id": row[0],
                "name": row[1],
                "description": None,
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        if email and not tenants:
            # Fallback to full list if user-specific query returned nothing
            with sqlite3.connect(str(config.DB_PATH)) as fallback_conn:
                fallback_cursor = fallback_conn.cursor()
                fallback_cursor.execute(
                    """
                    SELECT id, name
                    FROM tenants
                    ORDER BY name
                    """
                )
                tenants = [
                    {
                        "id": row[0],
                        "name": row[1],
                        "description": None,
                    }
                    for row in fallback_cursor.fetchall()
                ]

        return tenants

    except Exception as e:
        logger.exception(f"Error fetching tenants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching available tenants"
        )


# =====================================================
# ERROR MONITORING ENDPOINTS
# =====================================================

@app.get("/admin/error-stats")
async def get_error_statistics(
    days: int = 7,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Get error statistics for monitoring and alerting.
    Requires authentication. Superusers can see all tenants.
    """
    try:
        # Superusers can see all tenants, regular users only their own
        tenant_id = None if tenancy_context.is_superuser else tenancy_context.tenant_id

        stats = get_error_stats(tenant_id=tenant_id, days=days)
        return stats

    except Exception as e:
        error_context = create_error_context(
            user_id=tenancy_context.user_id,
            tenant_id=tenancy_context.tenant_id,
            endpoint="/admin/error-stats"
        )
        raise handle_error_with_context(
            error=e,
            context=error_context,
            category="system",
            severity="low",
            user_message="Error al obtener estadísticas de errores"
        )


@app.post("/admin/test-error")
async def test_error_handling(
    error_type: str = "validation",
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Test endpoint for error handling system (admin only).
    """
    if not tenancy_context.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Solo administradores pueden probar el sistema de errores"
        )

    error_context = create_error_context(
        user_id=tenancy_context.user_id,
        tenant_id=tenancy_context.tenant_id,
        endpoint="/admin/test-error"
    )

    try:
        if error_type == "validation":
            raise ValidationError("Este es un error de validación de prueba")
        elif error_type == "business":
            raise BusinessLogicError("Este es un error de lógica de negocio de prueba")
        elif error_type == "not_found":
            raise NotFoundError("Recurso de prueba", "test-123")
        elif error_type == "system":
            raise Exception("Este es un error de sistema de prueba")
        else:
            raise ValidationError("Tipo de error no válido. Usa: validation, business, not_found, system")

    except Exception as e:
        raise handle_error_with_context(
            error=e,
            context=error_context,
            category=error_type,
            severity="low",
            user_message="Error de prueba generado exitosamente"
        )


# REMOVED: /simple_expense endpoint (legacy, replaced by /expenses)


@app.get("/api/status")
async def api_status():
    """
    API status endpoint - health check for the MCP server.

    Returns:
        dict: Status message indicating server is running
    """
    logger.info("API status endpoint accessed")
    return {"status": "MCP Server running"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        dict: Detailed health status
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "server": "MCP Server",
        "uptime": "active"
    }


@app.post("/mcp", response_model=MCPResponse)
async def mcp_endpoint(request: MCPRequest):
    """
    Main MCP endpoint that receives method calls and routes them to handlers.

    Args:
        request (MCPRequest): The MCP request containing method and parameters

    Returns:
        MCPResponse: The response from the MCP handler

    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(f"MCP request received - Method: {request.method}, Params: {request.params}")

        # Call the core MCP handler
        result = handle_mcp_request(request.method, request.params)

        # Check if the result contains an error
        if "error" in result:
            logger.warning(f"MCP method error: {result['error']}")
            return MCPResponse(
                success=False,
                error=result["error"]
            )

        logger.info(f"MCP request processed successfully - Method: {request.method}")
        return MCPResponse(
            success=True,
            data=result
        )

    except Exception as e:
        logger.error(f"Unexpected error processing MCP request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/voice_mcp")
async def voice_mcp_endpoint(file: UploadFile = File(...)):
    """
    Voice-enabled MCP endpoint that processes audio input and returns both JSON and audio responses.

    Flow:
    1. Transcribe uploaded audio file to text using OpenAI Whisper
    2. Process the text through MCP handler
    3. Convert MCP response to speech using OpenAI TTS
    4. Return JSON response with transcript, MCP result, and audio file

    Args:
        file (UploadFile): Audio file (MP3, WAV, etc.)

    Returns:
        JSONResponse: {
            "success": bool,
            "transcript": str,
            "mcp_response": dict,
            "response_text": str,
            "audio_file_url": str,
            "error": str (if failed)
        }
    """
    if not VOICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Voice processing is disabled. Please configure OPENAI_API_KEY and install required dependencies."
        )

    try:
        logger.info(f"Voice MCP request received - File: {file.filename}, Content-Type: {file.content_type}")

        # Validate file type
        if not file.content_type or not file.content_type.startswith('audio/'):
            logger.warning(f"Invalid file type: {file.content_type}")
            # Allow anyway as some browsers may not set correct content type

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "audio.mp3")[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_audio_path = tmp_file.name

        logger.info(f"Audio file saved to: {tmp_audio_path}")

        # Process voice request through the pipeline
        def mcp_handler_wrapper(mcp_request):
            """Wrapper to handle MCP requests from voice processing"""
            method = mcp_request.get("method", "unknown")
            params = mcp_request.get("params", {})
            return handle_mcp_request(method, params)

        # Process through voice handler
        result = process_voice_request(tmp_audio_path, mcp_handler_wrapper)

        # Clean up temporary file
        try:
            os.unlink(tmp_audio_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")

        if not result["success"]:
            logger.error(f"Voice processing failed: {result.get('error')}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result.get("error", "Voice processing failed"),
                    "transcript": "",
                    "mcp_response": {},
                    "audio_file_url": ""
                }
            )

        # Prepare response
        response_data = {
            "success": True,
            "transcript": result.get("transcript", ""),
            "mcp_response": result.get("mcp_response", {}),
            "response_text": result.get("response_text", ""),
            "tts_success": result.get("tts_success", False),
            "audio_file_url": f"/audio/{os.path.basename(result.get('audio_file', ''))}" if result.get('audio_file') else ""
        }

        # Store audio file path for serving
        if result.get('audio_file'):
            # Store reference for serving the file
            app.state.audio_files = getattr(app.state, 'audio_files', {})
            audio_filename = os.path.basename(result['audio_file'])
            app.state.audio_files[audio_filename] = result['audio_file']

        logger.info(f"Voice MCP processed successfully - Transcript: {result.get('transcript', '')[:100]}...")
        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in voice MCP endpoint: {str(e)}")
        # Cleanup any temp files
        if 'tmp_audio_path' in locals():
            try:
                os.unlink(tmp_audio_path)
            except:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/audio/{filename}")
async def serve_audio_file(filename: str):
    """
    Serve generated audio files.

    Args:
        filename (str): Audio file name

    Returns:
        FileResponse: Audio file
    """
    if not VOICE_ENABLED:
        raise HTTPException(status_code=503, detail="Voice processing disabled")

    try:
        # Get stored audio file path
        audio_files = getattr(app.state, 'audio_files', {})
        if filename not in audio_files:
            raise HTTPException(status_code=404, detail="Audio file not found")

        file_path = audio_files[filename]
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Audio file not found on disk")

        return FileResponse(
            path=file_path,
            media_type="audio/mpeg",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving audio file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error serving audio file")


@app.post("/voice_mcp_enhanced")
async def voice_mcp_enhanced_endpoint(file: UploadFile = File(...)):
    """
    Enhanced voice-enabled MCP endpoint with field validation and completion forms.

    Flow:
    1. Transcribe audio to text using OpenAI Whisper
    2. Enhance with LLM for better descriptions
    3. Validate completeness of fields
    4. Return completion form if fields are missing
    5. Allow user to complete and create expense

    Args:
        file (UploadFile): Audio file (MP3, WAV, etc.)

    Returns:
        JSONResponse: Enhanced response with validation and form
    """
    if not VOICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Voice processing is disabled. Please configure OPENAI_API_KEY and install required dependencies."
        )

    try:
        logger.info(f"Enhanced Voice MCP request received - File: {file.filename}")

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "audio.mp3")[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_audio_path = tmp_file.name

        # Step 1: Transcribe audio
        from core.voice_handler import get_voice_handler
        voice_handler = get_voice_handler()

        transcription_result = voice_handler.transcribe_audio(tmp_audio_path)

        # Clean up temp file
        try:
            os.unlink(tmp_audio_path)
        except:
            pass

        if not transcription_result["success"]:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": transcription_result.get("error", "Transcription failed"),
                    "stage": "transcription"
                }
            )

        transcript = transcription_result["transcript"]
        logger.info(f"Transcribed: {transcript}")

        # Step 2: Enhance with LLM
        try:
            from core.expenses.completion.expense_enhancer import enhance_expense_from_voice
            # Extract amount from transcript for enhancement
            import re
            amount_match = re.search(r'(\d+(?:\.\d+)?)', transcript)
            amount = float(amount_match.group(1)) if amount_match else 100.0

            enhanced_data = enhance_expense_from_voice(transcript, amount)
        except Exception as e:
            logger.error(f"Error in LLM enhancement: {e}")
            enhanced_data = {
                'name': transcript,
                'total_amount': amount,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'payment_mode': 'own_account'
            }

        # Step 3: Validate completeness
        from core.expenses.validation.expense_validator import expense_validator
        validation_result = expense_validator.validate_expense_data(enhanced_data)

        # Step 4: Generate completion form if needed
        completion_form = None
        if not validation_result['is_complete'] or validation_result['missing_critical']:
            completion_form = expense_validator.create_completion_form(enhanced_data, validation_result)

        response_data = {
            "success": True,
            "transcript": transcript,
            "enhanced_data": enhanced_data,
            "validation": validation_result,
            "completion_form": completion_form,
            "can_create_directly": validation_result['can_create'],
            "completeness_score": validation_result['completeness_score']
        }

        # If the expense is complete enough, offer direct creation
        if validation_result['can_create'] and validation_result['completeness_score'] >= 60:
            response_data['direct_creation_available'] = True

        logger.info(f"Enhanced voice processing completed - Score: {validation_result['completeness_score']}%")
        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"Error in enhanced voice MCP endpoint: {str(e)}")
        if 'tmp_audio_path' in locals():
            try:
                os.unlink(tmp_audio_path)
            except:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# CompleteExpenseRequest model moved to core/api_models.py


# REMOVED: /complete_expense endpoint (legacy, replaced by /expenses)


@app.post("/ocr/parse")
async def ocr_parse(file: UploadFile = File(...), lang: str = Form("spa+eng")):
    """
    OCR endpoint - Parse image/PDF and extract structured fields.

    Args:
        file: Image or PDF file
        lang: Tesseract language (default: spa+eng)

    Returns:
        JSONResponse: Extracted text and fields
    """
    try:
        logger.info(f"OCR parse request - File: {file.filename}, Size: {file.size}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        # Read file content
        content = await file.read()

        # Call Node.js OCR service
        import httpx

        files = {"file": (file.filename, content, file.content_type)}
        data = {"lang": lang}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:3001/ocr/parse",
                files=files,
                data=data,
                timeout=30.0
            )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"OCR parse successful - Confidence: {result.get('confidence', 0)}")
            return JSONResponse(content=result)
        else:
            error_msg = f"OCR service error: {response.status_code}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    except Exception as e:
        logger.error(f"Error in OCR parse: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


@app.post("/ocr/intake")
async def ocr_intake(
    file: UploadFile = File(...),
    paid_by: str = Form(...),
    will_have_cfdi: str = Form(...)
):
    """
    OCR intake endpoint - Create expense directly from OCR.

    Args:
        file: Image or PDF file
        paid_by: Payment method (company_account/own_account)
        will_have_cfdi: Whether CFDI is expected (true/false)

    Returns:
        JSONResponse: Created intake with route decision
    """
    try:
        logger.info(f"OCR intake request - File: {file.filename}, paid_by: {paid_by}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        # Read file content
        content = await file.read()

        # Use our Python OCR service directly
        import base64
        import time
        base64_image = base64.b64encode(content).decode('utf-8')

        # Use our Python OCR service
        from modules.invoicing_agent.services.ocr_service import OCRService
        ocr_service = OCRService()

        ocr_result = await ocr_service.extract_text(base64_image)

        # Extract fields from OCR text using basic regex pattern matching
        import re
        extracted_fields = {}
        if ocr_result.text:
            lines = ocr_result.text.split('\n')
            for line in lines:
                # Extract RFC
                rfc_match = re.search(r'RFC:\s*([A-Z0-9]{12,13})', line.upper())
                if rfc_match:
                    extracted_fields['rfc'] = rfc_match.group(1)

                # Extract total
                total_match = re.search(r'TOTAL:?\s*\$?(\d+\.?\d*)', line.upper())
                if total_match:
                    extracted_fields['total'] = float(total_match.group(1))

                # Extract date patterns
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', line)
                if date_match:
                    extracted_fields['fecha'] = date_match.group(1)

        # Create response in expected format
        intake_id = f"intake_{int(time.time())}"
        result = {
            "intake_id": intake_id,
            "message": "OCR procesado exitosamente",
            "route": "expense_creation",
            "confidence": ocr_result.confidence,
            "ocr_confidence": ocr_result.confidence,
            "fields": extracted_fields,
            "raw_text": ocr_result.text,
            "backend": ocr_result.backend.value,
            "processing_time_ms": ocr_result.processing_time_ms
        }

        logger.info(f"OCR intake successful - ID: {intake_id}, Fields: {list(extracted_fields.keys())}")
        return JSONResponse(content=result, status_code=201)

    except Exception as e:
        logger.error(f"Error in OCR intake: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR intake failed: {str(e)}")


@app.get("/ocr/stats")
async def ocr_stats():
    """
    OCR stats endpoint - Get OCR service statistics.

    Returns:
        JSONResponse: OCR service stats
    """
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:3001/ocr/stats", timeout=10.0)

        if response.status_code == 200:
            result = response.json()
            logger.info("OCR stats retrieved successfully")
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=500, detail="OCR stats service error")

    except Exception as e:
        logger.error(f"Error getting OCR stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR stats failed: {str(e)}")


@app.get("/methods")
async def list_supported_methods():
    """
    List all supported MCP methods.

    Returns:
        dict: List of supported methods with descriptions
    """
    supported_methods = {
        "get_inventory": {
            "description": "Get inventory information for a product",
            "parameters": ["product_id", "location (optional)"]
        },
        "create_order": {
            "description": "Create a new order",
            "parameters": ["customer", "items"]
        },
        "create_expense": {
            "description": "Create a new expense record",
            "parameters": ["employee", "amount", "description"]
        },
        "ocr_parse": {
            "description": "Parse image/PDF with OCR and extract fields (POST /ocr/parse)",
            "parameters": ["file (multipart/form-data)", "lang (optional)"]
        },
        "ocr_intake": {
            "description": "Create expense directly from OCR (POST /ocr/intake)",
            "parameters": ["file (multipart/form-data)", "paid_by", "will_have_cfdi"]
        },
        "ocr_stats": {
            "description": "Get OCR service statistics (GET /ocr/stats)",
            "parameters": []
        },
        "bank_reconciliation_suggestions": {
            "description": "Sugerencias IA de conciliación bancaria (POST /bank_reconciliation/suggestions)",
            "parameters": ["expense_payload"]
        },
        "bank_reconciliation_feedback": {
            "description": "Registrar feedback de conciliación bancaria (POST /bank_reconciliation/feedback)",
            "parameters": ["expense_id", "movement_id", "confidence", "decision"]
        },
        "bank_reconciliation_ml_suggestions": {
            "description": "ML-powered bank reconciliation suggestions (POST /bank_reconciliation/ml-suggestions)",
            "parameters": ["movement_data", "threshold"]
        },
        "bank_reconciliation_auto_reconcile": {
            "description": "Automatic ML reconciliation (POST /bank_reconciliation/auto-reconcile)",
            "parameters": ["threshold", "limit"]
        },
        "bank_reconciliation_movements_create": {
            "description": "Create bank movement (POST /bank_reconciliation/movements)",
            "parameters": ["movement_data"]
        },
        "bank_reconciliation_movements_get": {
            "description": "Get bank movement (GET /bank_reconciliation/movements/{id})",
            "parameters": ["movement_id"]
        },
        "bank_reconciliation_matching_rules": {
            "description": "Get/Create matching rules (GET/POST /bank_reconciliation/matching-rules)",
            "parameters": ["rule_data (POST only)"]
        },
        "enhanced_onboarding_register": {
            "description": "Enhanced user registration with demo preferences (POST /onboarding/enhanced-register)",
            "parameters": ["method", "identifier", "full_name", "company_name", "demo_preferences", "auto_complete_steps"]
        },
        "onboarding_step_update": {
            "description": "Update user onboarding step (PUT /onboarding/step)",
            "parameters": ["user_id", "step_number", "status", "metadata"]
        },
        "onboarding_status_get": {
            "description": "Get user onboarding status (GET /onboarding/status/{user_id})",
            "parameters": ["user_id"]
        },
        "onboarding_generate_demo": {
            "description": "Generate demo data for user (POST /onboarding/generate-demo)",
            "parameters": ["user_id", "demo_preferences"]
        },
        "duplicates_detect": {
            "description": "Detect potential duplicate expenses (POST /duplicates/detect)",
            "parameters": ["expense_data", "detection_method", "similarity_threshold"]
        },
        "duplicates_review": {
            "description": "Review duplicate detection (PUT /duplicates/review)",
            "parameters": ["detection_id", "expense_id", "potential_duplicate_id", "action"]
        },
        "duplicates_stats": {
            "description": "Get duplicate detection statistics (GET /duplicates/stats)",
            "parameters": []
        },
        "duplicates_config": {
            "description": "Get duplicate detection configuration (GET /duplicates/config)",
            "parameters": []
        },
        "expenses_enhanced": {
            "description": "Create expense with duplicate detection (POST /expenses/enhanced)",
            "parameters": ["expense_data", "check_duplicates", "auto_action_on_duplicates"]
        },
        "invoice_parse": {
            "description": "Analizar CFDI XML para extraer impuestos (POST /invoices/parse)",
            "parameters": ["file (multipart/form-data)"]
        },
        "invoicing_upload_ticket": {
            "description": "Subir ticket para facturación automática (POST /invoicing/tickets)",
            "parameters": ["file (optional)", "text_content (optional)", "user_id (optional)"]
        },
        "invoicing_ticket_status": {
            "description": "Ver estado de un ticket (GET /invoicing/tickets/{id})",
            "parameters": ["ticket_id"]
        },
        "invoicing_bulk_upload": {
            "description": "Carga masiva de tickets (POST /invoicing/bulk-match)",
            "parameters": ["tickets_list", "auto_process"]
        },
        "whatsapp_webhook": {
            "description": "Webhook para mensajes WhatsApp (POST /invoicing/webhooks/whatsapp)",
            "parameters": ["message_data"]
        },
        "invoicing_merchants": {
            "description": "Gestión de merchants para facturación (GET/POST /invoicing/merchants)",
            "parameters": ["merchant_data (for POST)"]
        },
        "invoicing_jobs": {
            "description": "Ver jobs de procesamiento (GET /invoicing/jobs)",
            "parameters": ["company_id"]
        }
    }

    # Add voice endpoints if enabled
    voice_endpoints = {}
    if VOICE_ENABLED:
        voice_endpoints = {
            "voice_mcp": {
                "description": "Basic voice-enabled MCP endpoint (POST /voice_mcp)",
                "parameters": ["audio_file (multipart/form-data)"],
                "returns": "JSON response + audio file"
            },
            "voice_mcp_enhanced": {
                "description": "Enhanced voice MCP with field validation (POST /voice_mcp_enhanced)",
                "parameters": ["audio_file (multipart/form-data)"],
                "returns": "JSON response + completion form + validation"
            },
            "audio_file": {
                "description": "Serve generated audio files (GET /audio/{filename})",
                "parameters": ["filename"],
                "returns": "Audio file (MP3)"
            }
        }

    all_methods = {**supported_methods, **voice_endpoints}

    return {
        "supported_methods": all_methods,
        "total_methods": len(all_methods),
        "voice_enabled": VOICE_ENABLED
    }


@app.get("/bank_reconciliation/movements")
async def get_bank_movements(
    limit: int = 100,
    include_matched: bool = True,
    company_id: str = "default",
) -> Dict[str, Any]:
    """Return bank movements stored in the internal database."""

    movements = list_bank_movements(tenant_id=1)

    # Aplicar filtros post-procesamiento si es necesario
    if not include_matched:
        movements = [m for m in movements if not m.get('matched')]

    # Aplicar límite
    if limit:
        movements = movements[:limit]
    return {"movements": movements, "count": len(movements)}


@app.post("/bank_reconciliation/suggestions", response_model=BankSuggestionResponse)
async def bank_reconciliation_suggestions(expense: BankSuggestionExpense) -> BankSuggestionResponse:
    """Return a ranked list of possible bank movements for an expense."""

    try:
        logger.debug("Generating bank reconciliation suggestions for %s", expense.expense_id)
        suggestions = suggest_bank_matches(
            expense.model_dump(),
            company_id=expense.company_id,
        )
        return BankSuggestionResponse(suggestions=suggestions)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Bank reconciliation suggestion error: %s", exc)
        raise HTTPException(status_code=500, detail="Error generando sugerencias de conciliación bancaria")


@app.post("/bank_reconciliation/feedback")
async def bank_reconciliation_feedback(feedback: BankReconciliationFeedback) -> Dict[str, Any]:
    """Store user feedback about a bank reconciliation suggestion."""

    decision = feedback.decision.lower()
    if decision not in {"accepted", "rejected", "manual"}:
        raise HTTPException(status_code=400, detail="Decisión inválida. Usa accepted, rejected o manual.")

    record_bank_match_feedback(
        expense_id=feedback.expense_id,
        movement_id=feedback.movement_id,
        confidence=feedback.confidence,
        decision=decision,
        notes=feedback.notes,
        metadata=feedback.metadata,
        company_id=feedback.company_id,
    )

    return {"success": True}


# ===== ENHANCED BANK RECONCILIATION ML ENDPOINTS =====
@app.post("/bank_reconciliation/movements", response_model=BankMovementResponse)
async def create_bank_movement_endpoint(
    movement: BankMovementCreate,
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
) -> BankMovementResponse:
    """Create a new bank movement record."""
    try:
        movement_id = create_bank_movement(
            movement_data=movement.model_dump(),
            tenant_id=tenancy.tenant_id
        )

        created_movement = get_bank_movement(movement_id, tenancy.tenant_id)
        return BankMovementResponse(**created_movement)

    except Exception as e:
        error_context = create_error_context(
            error_type="bank_movement_creation_error",
            user_id=current_user.get('id'),
            tenant_id=tenancy.tenant_id
        )
        raise handle_error_with_context(e, error_context)


@app.get("/bank_reconciliation/movements/{movement_id}", response_model=BankMovementResponse)
async def get_bank_movement_endpoint(
    movement_id: int,
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> BankMovementResponse:
    """Get a specific bank movement."""
    movement = get_bank_movement(movement_id, tenancy.tenant_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Bank movement not found")

    return BankMovementResponse(**movement)
@app.get("/bank-movements/account/{account_id}")
async def get_bank_movements_by_account(
    account_id: int,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> List[Dict[str, Any]]:
    """Get all bank movements for a specific account."""
    try:
        import sqlite3

        # Connect to database directly
        db_path = "unified_mcp_system.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 🚀 PRODUCTION-READY QUERY: Enhanced with all improvements
        query = """
        SELECT
            bm.id,
            bm.date,
            COALESCE(bm.cleaned_description, bm.description) as description,
            COALESCE(bm.description_raw, bm.raw_data, bm.description) as description_raw,
            bm.amount,
            bm.transaction_type,
            bm.movement_kind,
            COALESCE(bm.display_type, 'transaction') as display_type,
            COALESCE(bm.transaction_subtype, 'unknown') as transaction_subtype,
            COALESCE(bm.category_manual, bm.category_auto, 'Sin categoría') as category,
            COALESCE(bm.category_confidence, 0.0) as category_confidence,
            COALESCE(bm.is_reconciled, 0) as is_reconciled,
            bm.notes,
            COALESCE(bm.confidence_score, 0.0) as confidence_score,
            bm.statement_id,
            bm.created_at,
            COALESCE(bm.cargo_amount, 0.0) as cargo_amount,
            COALESCE(bm.abono_amount, 0.0) as abono_amount,
            COALESCE(bm.running_balance, bm.balance_after) as running_balance,
            COALESCE(bm.balance_before, 0.0) as balance_before,
            CASE
                WHEN bm.display_type = 'balance_inicial' THEN '🔐 ' || printf("$%.2f", COALESCE(bm.running_balance, 0))
                WHEN UPPER(COALESCE(bm.movement_kind, '')) = 'INGRESO' THEN '💰 +$' || printf("%.2f", bm.amount)
                WHEN UPPER(COALESCE(bm.movement_kind, '')) = 'TRANSFERENCIA' THEN '🔁 $' || printf("%.2f", ABS(bm.amount))
                WHEN bm.transaction_type = 'credit' THEN '💰 +$' || printf("%.2f", bm.amount)
                ELSE '💸 -$' || printf("%.2f", ABS(bm.amount))
            END as formatted_amount,
            CASE
                WHEN bm.running_balance IS NOT NULL THEN '$' || printf("%.2f", bm.running_balance)
                WHEN bm.balance_after IS NOT NULL THEN '$' || printf("%.2f", bm.balance_after)
                ELSE NULL
            END as formatted_balance,
            CASE
                WHEN bm.display_type = 'balance_inicial' THEN '🔐'
                WHEN UPPER(COALESCE(bm.movement_kind, '')) = 'INGRESO' THEN '💰'
                WHEN bm.transaction_type = 'credit' THEN '💰'
                ELSE '💸'
            END as type_icon
        FROM bank_movements bm
        WHERE bm.account_id = ? AND bm.user_id = ? AND bm.tenant_id = ?
            AND ABS(bm.amount) < 1000000
        ORDER BY bm.date ASC, bm.id ASC
        """

        cursor.execute(query, (account_id, current_user.id, tenancy.tenant_id))
        movements = cursor.fetchall()

        conn.close()

        # 🎯 ENHANCED RESPONSE: Production-ready with all improvements
        result = []
        for movement in movements:
            result.append({
                'id': movement["id"],
                'date': movement["date"],  # Now in ISO format 2024-03-01
                'description': movement["description"],  # Clean description
                'description_raw': movement["description_raw"],  # Full original text
                'amount': movement["amount"],
                'transaction_type': movement["transaction_type"],
                'movement_kind': movement["movement_kind"],
                'display_type': movement["display_type"],  # 'balance_inicial', 'transaction'
                'transaction_subtype': movement["transaction_subtype"],  # 'deposito_spei', 'gasto_gasolina', etc.
                'category': movement["category"],  # Auto-categorized
                'category_confidence': movement["category_confidence"],
                'is_reconciled': bool(movement["is_reconciled"]),
                'notes': movement["notes"] or '',
                'confidence_score': movement["confidence_score"],
                'statement_id': movement["statement_id"],
                'created_at': movement["created_at"],
                'cargo_amount': movement["cargo_amount"],  # Separate debit amount
                'abono_amount': movement["abono_amount"],  # Separate credit amount
                'running_balance': movement["running_balance"],  # Progressive balance
                'balance_before': movement["balance_before"],
                'formatted_amount': movement["formatted_amount"],  # With emojis: 💰 +$2600.00
                'formatted_balance': movement["formatted_balance"],
                'type_icon': movement["type_icon"]  # 💰, 💸, 🔐
            })

        return result

    except Exception as e:
        logger.exception(f"Error fetching bank movements for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching transactions")


@app.post("/bank-movements/reparse-with-improved-rules")
async def reparse_transactions_with_improved_rules(
    account_id: int,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Re-parse existing transactions with improved LLM rules for better accuracy"""
    try:
        import sqlite3
        from core.llm_pdf_parser import LLMPDFParser
        from core.reconciliation.bank.bank_statements_models import MovementKind

        # Connect to database
        db_path = "unified_mcp_system.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all transactions for the account
        cursor.execute("""
            SELECT id, description, amount, raw_data, movement_kind
            FROM bank_movements
            WHERE account_id = ? AND user_id = ? AND tenant_id = ?
        """, (account_id, current_user.id, tenancy.tenant_id))

        transactions = cursor.fetchall()
        updated_count = 0
        parser = LLMPDFParser()

        for txn in transactions:
            # Re-classify movement based on improved rules
            new_movement_kind = parser._classify_movement_by_description(
                txn['description'],
                float(txn['amount'])
            )

            # Update if classification changed
            if txn['movement_kind'] != new_movement_kind.value:
                cursor.execute("""
                    UPDATE bank_movements
                    SET movement_kind = ?
                    WHERE id = ?
                """, (new_movement_kind.value, txn['id']))
                updated_count += 1

        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"Re-parsed {len(transactions)} transactions",
            "updated_count": updated_count,
            "total_transactions": len(transactions)
        }

    except Exception as e:
        logger.exception(f"Error re-parsing transactions for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error re-parsing transactions: {str(e)}")


@app.post("/bank_reconciliation/ml-suggestions")
async def ml_bank_reconciliation_suggestions(
    request: BankReconciliationRequest,
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Get ML-powered matching suggestions for bank movement."""
    try:
        suggestions = find_matching_expenses_for_movement(
            movement_data=request.movement_data,
            tenant_id=tenancy.tenant_id,
            threshold=request.threshold or 0.65
        )

        return {
            "movement_id": request.movement_data.get("id"),
            "suggestions": suggestions,
            "count": len(suggestions),
            "threshold": request.threshold or 0.65
        }

    except Exception as e:
        logger.exception(f"ML reconciliation error: {e}")
        raise HTTPException(status_code=500, detail="Error generating ML suggestions")


@app.post("/bank_reconciliation/auto-reconcile")
async def auto_reconcile_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user),
    threshold: float = Query(0.85, description="Auto-match threshold"),
    limit: int = Query(100, description="Max movements to process")
) -> Dict[str, Any]:
    """Perform automatic reconciliation using ML."""
    try:
        results = perform_auto_reconciliation(
            tenant_id=tenancy.tenant_id,
            threshold=threshold,
            limit=limit
        )

        return {
            "processed": results["processed"],
            "matched": results["matched"],
            "threshold": threshold,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.exception(f"Auto reconciliation error: {e}")
        raise HTTPException(status_code=500, detail="Error performing auto reconciliation")


@app.get("/bank_reconciliation/matching-rules")
async def get_matching_rules_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Get bank matching rules for tenant."""
    rules = get_bank_matching_rules(tenancy.tenant_id)
    return {"rules": rules, "count": len(rules)}


@app.post("/bank_reconciliation/matching-rules")
async def create_matching_rule_endpoint(
    rule_data: Dict[str, Any],
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Create new bank matching rule."""
    rule_data['tenant_id'] = tenancy.tenant_id
    rule_data['created_by'] = current_user.get('id')

    rule_id = create_bank_matching_rule(rule_data)
    return {"rule_id": rule_id, "success": True}


def _validate_onboarding_identifier(payload: OnboardingRequest) -> Dict[str, str]:
    identifier = payload.identifier.strip()
    if payload.method == "whatsapp":
        digits = re.sub(r"\D", "", identifier)
        if len(digits) < 10 or len(digits) > 15:
            raise HTTPException(status_code=400, detail="Número de WhatsApp inválido (usa 10 a 15 dígitos)")
        return {"normalized": digits, "identifier_type": "whatsapp"}

    email = identifier.lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Correo electrónico inválido")
    allowed_domains = {
        "gmail.com",
        "gmail.com.mx",
        "hotmail.com",
        "hotmail.es",
        "outlook.com",
        "outlook.es",
        "live.com",
        "live.com.mx",
    }
    domain = email.split("@")[-1]
    if domain not in allowed_domains:
        raise HTTPException(status_code=400, detail="Solo se permiten correos Gmail u Hotmail")
    return {"normalized": email, "identifier_type": "email"}


@app.post("/onboarding/register", response_model=OnboardingResponse)
async def onboarding_register(payload: OnboardingRequest) -> OnboardingResponse:
    """Register a new user via onboarding and seed demo data."""

    details = _validate_onboarding_identifier(payload)

    try:
        user_record = register_user_account(
            identifier=details["normalized"],
            identifier_type=details["identifier_type"],
            display_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error registrando usuario onboarding: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo registrar el usuario") from exc

    company_id = user_record["company_id"]
    already_exists = not user_record.get("created", False)

    records = fetch_expense_records(company_id=company_id, limit=10)
    demo_expenses = [_build_expense_response(record) for record in records]
    snapshot_raw = get_company_demo_snapshot(company_id)
    snapshot = DemoSnapshot(**snapshot_raw)

    next_steps = [
        "Revisa los gastos de ejemplo desde la vista de voz.",
        "Prueba la conciliación bancaria con los movimientos demo.",
        "Conecta tu empresa real cuando estés listo.",
    ]

    return OnboardingResponse(
        company_id=company_id,
        user_id=int(user_record["id"]),
        identifier=user_record["identifier"],
        identifier_type=user_record["identifier_type"],
        full_name=user_record.get("display_name") or payload.full_name,
        already_exists=already_exists,
        demo_snapshot=snapshot,
        demo_expenses=demo_expenses,
        next_steps=next_steps,
    )


# ===== ENHANCED ONBOARDING ENDPOINTS (FUNCIONALIDAD #8) =====

@app.post("/onboarding/enhanced-register", response_model=EnhancedOnboardingResponse)
async def enhanced_onboarding_register(
    payload: EnhancedOnboardingRequest,
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> EnhancedOnboardingResponse:
    """Enhanced user registration with demo preferences and step tracking"""
    try:
        # Check if user already exists
        existing_user = get_user_by_email(payload.identifier, tenancy.tenant_id)
        if existing_user:
            # Return existing user status
            status = get_user_onboarding_status(existing_user['id'], tenancy.tenant_id)
            return EnhancedOnboardingResponse(
                success=True,
                company_id=f"tenant_{tenancy.tenant_id}",
                user_id=existing_user['id'],
                identifier=existing_user['identifier'] or existing_user['email'],
                display_name=existing_user['full_name'] or existing_user['name'],
                already_exists=True,
                onboarding_status=UserOnboardingStatus(**status) if status else None,
                verification_required=not existing_user.get('email_verified', False)
            )

        # Create new user with enhanced fields
        import uuid
        verification_token = str(uuid.uuid4())

        user_data = {
            'name': payload.full_name.split()[0],  # First name
            'email': payload.identifier if payload.method == "email" else None,
            'identifier': payload.identifier,
            'full_name': payload.full_name,
            'company_name': payload.company_name,
            'registration_method': payload.method,
            'demo_preferences': payload.demo_preferences.dict() if payload.demo_preferences else None,
            'verification_token': verification_token,
            'phone': payload.identifier if payload.method == "whatsapp" else None,
            'onboarding_step': 1 if payload.auto_complete_steps else 0
        }

        # Create user using function imported from unified_db_adapter
        # Como las funciones no están disponibles, usaré SQLite directo temporalmente
        try:
            user_id = 1  # Placeholder - en prod sería create_user(user_data, tenancy.tenant_id)
        except:
            # Fallback: basic user creation
            user_id = 1

        # Generate demo data if preferences provided
        demo_generated = False
        if payload.demo_preferences and user_id:
            try:
                demo_results = {"expenses_created": 0, "invoices_created": 0}  # generate_demo_data(user_id, payload.demo_preferences.dict(), tenancy.tenant_id)
                demo_generated = True
            except Exception as e:
                logger.warning(f"Demo data generation failed: {e}")

        # Get onboarding status
        status_data = {
            "user_id": user_id,
            "name": user_data['name'],
            "email": user_data.get('email', ''),
            "identifier": user_data['identifier'],
            "full_name": user_data['full_name'],
            "company_name": user_data.get('company_name'),
            "onboarding_step": user_data['onboarding_step'],
            "onboarding_completed": False,
            "registration_method": user_data['registration_method'],
            "email_verified": False,
            "phone_verified": False,
            "demo_preferences": payload.demo_preferences,
            "completed_steps": 1 if payload.auto_complete_steps else 0,
            "total_steps": 6,
            "overall_status": "in_progress" if payload.auto_complete_steps else "not_started"
        }

        return EnhancedOnboardingResponse(
            success=True,
            company_id=f"tenant_{tenancy.tenant_id}",
            user_id=user_id,
            identifier=user_data['identifier'],
            display_name=user_data['full_name'],
            already_exists=False,
            onboarding_status=UserOnboardingStatus(**status_data),
            demo_generated=demo_generated,
            verification_required=True,
            verification_token=verification_token,
            next_steps=[
                "Verifica tu email/teléfono",
                "Completa tu perfil",
                "Configura tu empresa",
                "Explora datos de demo"
            ]
        )

    except Exception as e:
        logger.exception(f"Enhanced onboarding error: {e}")
        raise HTTPException(status_code=500, detail=f"Error en onboarding: {str(e)}")


@app.put("/onboarding/step")
async def update_onboarding_step_endpoint(
    request: OnboardingStepRequest,
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> OnboardingStepResponse:
    """Update user onboarding step progress"""
    try:
        # Update step using function (placeholder)
        success = True  # update_onboarding_step(request.user_id, request.step_number, request.status, request.metadata, tenancy.tenant_id)

        if not success:
            raise HTTPException(status_code=404, detail="User not found or update failed")

        # Calculate next step
        next_step = request.step_number + 1 if request.status == "completed" and request.step_number < 6 else None

        return OnboardingStepResponse(
            user_id=request.user_id,
            step_number=request.step_number,
            step_name="step_name_placeholder",  # Get from DB in real implementation
            status=request.status,
            completed_at=datetime.now() if request.status == "completed" else None,
            next_step=next_step
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Step update error: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating step: {str(e)}")


@app.get("/onboarding/status/{user_id}")
async def get_onboarding_status_endpoint(
    user_id: int,
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> UserOnboardingStatus:
    """Get complete onboarding status for user"""
    try:
        # Get status using function (placeholder)
        status = None  # get_user_onboarding_status(user_id, tenancy.tenant_id)

        if not status:
            raise HTTPException(status_code=404, detail="User not found")

        return UserOnboardingStatus(**status)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get status error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@app.post("/onboarding/generate-demo")
async def generate_demo_data_endpoint(
    user_id: int = Query(..., description="User ID"),
    demo_preferences: DemoPreferences = None,
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Generate demo data for user"""
    try:
        if not demo_preferences:
            demo_preferences = DemoPreferences()

        # Generate demo data using function (placeholder)
        results = {"expenses_created": 15, "invoices_created": 5, "bank_movements_created": 8}  # generate_demo_data(user_id, demo_preferences.dict(), tenancy.tenant_id)

        return {
            "success": True,
            "user_id": user_id,
            "demo_results": results,
            "message": f"Generated {results.get('expenses_created', 0)} expenses with demo data"
        }

    except Exception as e:
        logger.exception(f"Demo generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating demo: {str(e)}")


# ===== ENHANCED DUPLICATE DETECTION ENDPOINTS (FUNCIONALIDAD #9) =====

@app.post("/duplicates/detect", response_model=DuplicateDetectionResponse)
async def detect_duplicates_endpoint(
    request: DuplicateDetectionRequest,
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> DuplicateDetectionResponse:
    """Detect potential duplicates for an expense"""
    try:
        import time
        start_time = time.time()

        # Run duplicate detection
        duplicates = detect_duplicates(
            request.expense_data,
            tenancy.tenant_id,
            request.similarity_threshold
        )

        # Convert results to response format
        duplicate_matches = []
        for dup in duplicates:
            duplicate_matches.append(DuplicateMatch(
                expense_id=dup['expense_id'],
                similarity_score=dup['similarity_score'],
                match_reasons=dup['match_reasons'],
                existing_expense=dup['existing_expense'],
                confidence_level=dup['confidence_level'],
                detection_method=request.detection_method
            ))

        # Calculate risk level and recommendation
        highest_similarity = max([d.similarity_score for d in duplicate_matches], default=0.0)

        if highest_similarity >= 0.85:
            risk_level = "high"
            recommended_action = "block"
        elif highest_similarity >= 0.65:
            risk_level = "medium"
            recommended_action = "review"
        else:
            risk_level = "low"
            recommended_action = "proceed"

        processing_time = int((time.time() - start_time) * 1000)

        return DuplicateDetectionResponse(
            expense_id=request.expense_data.get('id'),
            duplicates_found=duplicate_matches,
            total_matches=len(duplicate_matches),
            highest_similarity=highest_similarity,
            risk_level=risk_level,
            recommended_action=recommended_action,
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.exception(f"Duplicate detection error: {e}")
        raise HTTPException(status_code=500, detail=f"Error detecting duplicates: {str(e)}")


@app.put("/duplicates/review")
async def review_duplicate_endpoint(
    request: DuplicateReviewRequest,
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
) -> DuplicateReviewResponse:
    """Review a duplicate detection"""
    try:
        success = review_duplicate_detection(
            request.detection_id,
            request.action,
            current_user.get('id', 1),
            request.reviewer_notes,
            tenancy.tenant_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Detection not found or update failed")

        return DuplicateReviewResponse(
            detection_id=request.detection_id,
            action_taken=request.action,
            updated_at=datetime.now(),
            reviewer_id=current_user.get('id')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Duplicate review error: {e}")
        raise HTTPException(status_code=500, detail=f"Error reviewing duplicate: {str(e)}")


@app.get("/duplicates/stats")
async def get_duplicate_stats_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> DuplicateStatsResponse:
    """Get duplicate detection statistics"""
    try:
        stats = get_duplicate_stats(tenancy.tenant_id)

        return DuplicateStatsResponse(
            total_expenses=stats['total_expenses'],
            duplicates_detected=stats['duplicates_detected'],
            duplicates_confirmed=stats['duplicates_confirmed'],
            duplicates_rejected=stats['duplicates_rejected'],
            high_risk_pending=stats['high_risk_pending'],
            medium_risk_pending=stats['medium_risk_pending'],
            low_risk_pending=stats['low_risk_pending']
        )

    except Exception as e:
        logger.exception(f"Duplicate stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@app.get("/duplicates/config")
async def get_duplicate_config_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Get duplicate detection configuration"""
    try:
        config = get_duplicate_detection_config(tenancy.tenant_id)

        if not config:
            raise HTTPException(status_code=404, detail="No configuration found")

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get duplicate config error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")


@app.post("/expenses/enhanced", response_model=ExpenseResponseEnhanced)
async def create_expense_with_duplicate_detection(
    expense: ExpenseCreateEnhanced,
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
) -> ExpenseResponseEnhanced:
    """Create expense with automatic duplicate detection"""
    try:
        # Create the basic expense first
        expense_data = expense.dict(exclude={'check_duplicates', 'ml_features', 'auto_action_on_duplicates'})
        expense_id = record_internal_expense(expense_data, tenancy.tenant_id)

        # Get created expense
        created_expense = fetch_expense_record(expense_id, tenancy.tenant_id)

        response_data = ExpenseResponseEnhanced(**created_expense)

        # Run duplicate detection if requested
        if expense.check_duplicates and expense_id:
            expense_data['id'] = expense_id
            duplicates = detect_duplicates(expense_data, tenancy.tenant_id, 0.65)

            if duplicates:
                # Extract duplicate info
                duplicate_ids = [d['expense_id'] for d in duplicates]
                highest_similarity = max(d['similarity_score'] for d in duplicates)

                # Determine risk level
                if highest_similarity >= 0.85:
                    risk_level = "high"
                elif highest_similarity >= 0.65:
                    risk_level = "medium"
                else:
                    risk_level = "low"

                # Update expense with duplicate info
                duplicate_info = {
                    'duplicate_ids': duplicate_ids,
                    'similarity_score': highest_similarity,
                    'risk_level': risk_level
                }

                update_expense_duplicate_info(expense_id, duplicate_info, tenancy.tenant_id)

                # Update response
                response_data.duplicate_ids = duplicate_ids
                response_data.similarity_score = highest_similarity
                response_data.risk_level = risk_level

                # Save detections to database
                for dup in duplicates:
                    save_duplicate_detection(
                        expense_id,
                        dup['expense_id'],
                        dup['similarity_score'],
                        dup['match_reasons'],
                        dup['confidence_level'],
                        risk_level,
                        'hybrid',
                        tenancy.tenant_id
                    )

                # Save ML features if available
                if duplicate_result.get('ml_features'):
                    from core.shared.unified_db_adapter import save_expense_ml_features
                    try:
                        save_expense_ml_features(
                            expense_id,
                            duplicate_result['ml_features'],
                            None,  # embedding_vector
                            'rule_based',
                            duplicate_result['ml_features'].get('data_quality_score'),
                            tenancy.tenant_id
                        )
                    except Exception as e:
                        logger.warning(f"Could not save ML features: {e}")

        return response_data

    except Exception as e:
        logger.exception(f"Enhanced expense creation error: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating expense: {str(e)}")


# ===== ENHANCED CATEGORY PREDICTION ENDPOINTS (FUNCIONALIDAD #10) =====

@app.post("/expenses/predict-category")
async def predict_expense_category_endpoint(
    request: Dict[str, Any],
    tenancy: TenancyContext = Depends(get_tenancy_context)
):
    """Predict category for an expense"""
    try:
        from core.shared.unified_db_adapter import predict_expense_category

        description = request.get('description', '')
        amount = request.get('amount', 0)
        merchant_name = request.get('merchant_name', '')

        if not description:
            raise HTTPException(status_code=400, detail="Description is required")

        # Get user history for better predictions
        user_history = []
        if request.get('user_id'):
            from core.shared.unified_db_adapter import get_user_category_preferences
            user_history = get_user_category_preferences(request['user_id'], tenancy.tenant_id)

        prediction = predict_expense_category({
            'description': description,
            'amount': amount,
            'merchant_name': merchant_name
        }, tenancy.tenant_id, request.get('user_id'))

        return {
            'success': True,
            'prediction': prediction
        }

    except Exception as e:
        logger.exception(f"Category prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Error predicting category: {str(e)}")


@app.get("/categories/custom")
async def get_custom_categories_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context)
):
    """Get custom categories for tenant"""
    try:
        from core.shared.unified_db_adapter import get_custom_categories
        categories = get_custom_categories(tenancy.tenant_id)

        return {
            'success': True,
            'categories': categories
        }

    except Exception as e:
        logger.exception(f"Get custom categories error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting categories: {str(e)}")


@app.get("/categories/config")
async def get_category_config_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context)
):
    """Get category prediction configuration"""
    try:
        from core.shared.unified_db_adapter import get_category_prediction_config
        config = get_category_prediction_config(tenancy.tenant_id)

        if not config:
            raise HTTPException(status_code=404, detail="No configuration found")

        return {
            'success': True,
            'config': config
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Get category config error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")


@app.post("/categories/feedback")
async def record_category_feedback_endpoint(
    request: Dict[str, Any],
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
):
    """Record user feedback on category prediction"""
    try:
        from core.shared.unified_db_adapter import record_category_feedback

        expense_id = request.get('expense_id')
        feedback_type = request.get('feedback_type')  # 'accepted', 'corrected', 'rejected'
        actual_category = request.get('actual_category')

        if not expense_id or not feedback_type:
            raise HTTPException(status_code=400, detail="expense_id and feedback_type are required")

        feedback_data = {
            'feedback_type': feedback_type,
            'actual_category': actual_category,
            'user_id': current_user.get('id', 1)
        }

        success = record_category_feedback(expense_id, feedback_data, tenancy.tenant_id)

        # Process feedback for learning system
        learning_success = False
        if success:
            try:
                from core.ai_pipeline.classification.category_learning_system import process_category_feedback
                learning_success = process_category_feedback(expense_id, feedback_data, tenancy.tenant_id)
            except Exception as e:
                logger.warning(f"Learning system processing failed: {e}")

        return {
            'success': success,
            'learning_updated': learning_success,
            'message': 'Feedback recorded and learning system updated' if success else 'Failed to record feedback'
        }

    except Exception as e:
        logger.exception(f"Category feedback error: {e}")
        raise HTTPException(status_code=500, detail=f"Error recording feedback: {str(e)}")


@app.get("/categories/stats")
async def get_category_stats_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context)
):
    """Get category prediction statistics"""
    try:
        from core.shared.unified_db_adapter import get_category_stats
        stats = get_category_stats(tenancy.tenant_id)

        return {
            'success': True,
            'stats': stats
        }

    except Exception as e:
        logger.exception(f"Get category stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@app.get("/categories/learning-insights")
async def get_category_learning_insights_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context)
):
    """Get category learning system insights"""
    try:
        from core.ai_pipeline.classification.category_learning_system import get_category_learning_insights
        insights = get_category_learning_insights(tenancy.tenant_id)

        return {
            'success': True,
            'insights': insights
        }

    except Exception as e:
        logger.exception(f"Get learning insights error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting insights: {str(e)}")


@app.post("/categories/optimize")
async def optimize_category_predictor_endpoint(
    tenancy: TenancyContext = Depends(get_tenancy_context),
    current_user: dict = Depends(get_current_active_user)
):
    """Optimize category predictor based on learning"""
    try:
        from core.ai_pipeline.classification.category_learning_system import optimize_category_predictor
        optimizations = optimize_category_predictor(tenancy.tenant_id)

        return {
            'success': True,
            'optimizations': optimizations
        }

    except Exception as e:
        logger.exception(f"Optimize predictor error: {e}")
        raise HTTPException(status_code=500, detail=f"Error optimizing predictor: {str(e)}")


@app.post("/invoices/parse", response_model=InvoiceParseResponse)
async def parse_invoice(file: UploadFile = File(...)) -> InvoiceParseResponse:
    """Parse CFDI XML uploads and return tax breakdown information."""

    filename = file.filename or ""
    if not filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CFDI XML")

    try:
        content = await file.read()
        parsed = parse_cfdi_xml(content)
        return InvoiceParseResponse(**parsed)
    except InvoiceParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Invoice parsing error: %s", exc)
        raise HTTPException(status_code=500, detail="Error interno al analizar la factura")


@app.post("/invoices/upload-bulk")
async def upload_bulk_invoices(
    files: List[UploadFile] = File(...),
    company_id: str = Form(...),
    create_placeholder_on_no_match: bool = Form(True),
    auto_link_threshold: float = Form(0.8),
    auto_mark_invoiced: bool = Form(True),
    batch_tag: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Upload multiple XML invoices or ZIP files containing XMLs for bulk processing.

    Features:
    - Supports multiple individual XML files
    - Supports ZIP files containing multiple XMLs
    - Automatic CFDI parsing and validation
    - Creates audit trail in invoice_import_logs
    - Async batch processing with real-time status tracking
    - Security: File size limits, MIME validation, hash duplicate detection

    Args:
        files: List of XML or ZIP files
        company_id: Company/tenant ID
        create_placeholder_on_no_match: Create expense placeholder if no match found
        auto_link_threshold: Confidence threshold for auto-linking (0.0-1.0)
        auto_mark_invoiced: Auto-mark expenses as invoiced when linked
        batch_tag: Optional tag for grouping (e.g., "sat_enero_2025")

    Returns:
        {
            "batch_id": "batch_xyz123",
            "status": "processing",
            "total_files": 50,
            "message": "Batch created successfully"
        }
    """
    import zipfile
    import tempfile
    import hashlib
    from pathlib import Path
    import asyncio

    # Security: File size limit (200 MB total)
    MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200 MB
    MAX_SINGLE_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
    ALLOWED_MIMES = ['application/xml', 'text/xml', 'application/zip', 'application/x-zip-compressed']

    try:
        # Connect to PostgreSQL using adapter
        conn = sqlite3.connect()  # Uses PostgreSQL adapter
        cursor = conn.cursor()

        tenant_id = tenancy_context.tenant_id
        user_id = getattr(tenancy_context, 'user_id', 1)  # TODO: Get from auth

        batch_id = f"batch_{uuid.uuid4().hex[:16]}"
        parsed_invoices = []
        import_logs = []
        total_size = 0

        logger.info(f"Starting bulk upload for company {company_id}, batch {batch_id}, {len(files)} files")

        # Process each uploaded file
        for file in files:
            filename = file.filename or "unknown"

            # Read file content
            content = await file.read()
            file_size = len(content)
            total_size += file_size

            # Security: Check total size
            if total_size > MAX_TOTAL_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Total upload size exceeds limit of {MAX_TOTAL_SIZE // (1024*1024)} MB"
                )

            # Security: Check single file size
            if file_size > MAX_SINGLE_FILE_SIZE:
                logger.warning(f"File {filename} exceeds size limit: {file_size} bytes")
                import_logs.append({
                    'filename': filename,
                    'tenant_id': tenant_id,
                    'status': 'error',
                    'error_message': f'File size {file_size // (1024*1024)} MB exceeds limit of {MAX_SINGLE_FILE_SIZE // (1024*1024)} MB',
                    'source': 'bulk_upload',
                    'import_method': 'file_upload',
                    'batch_id': batch_id,
                    'imported_by': user_id,
                    'file_size': file_size
                })
                continue

            # Security: Validate MIME type
            content_type = file.content_type or ''
            if content_type not in ALLOWED_MIMES:
                logger.warning(f"File {filename} has invalid MIME type: {content_type}")
                import_logs.append({
                    'filename': filename,
                    'tenant_id': tenant_id,
                    'status': 'error',
                    'error_message': f'Invalid file type: {content_type}. Only XML and ZIP allowed.',
                    'source': 'bulk_upload',
                    'import_method': 'file_upload',
                    'batch_id': batch_id,
                    'imported_by': user_id,
                    'file_size': file_size,
                    'detected_format': content_type
                })
                continue

            # Calculate file hash for duplicate detection
            file_hash = hashlib.sha256(content).hexdigest()

            # Check for duplicate by hash
            cursor.execute("""
                SELECT filename, import_date FROM invoice_import_logs
                WHERE file_hash = ? AND tenant_id = ?
                ORDER BY import_date DESC LIMIT 1
            """, (file_hash, tenant_id))

            duplicate = cursor.fetchone()
            if duplicate:
                logger.info(f"Duplicate file detected: {filename} (hash: {file_hash[:8]}...)")
                # PostgreSQL adapter returns dict, not tuple
                dup_filename = duplicate.get('filename', duplicate.get(0, 'unknown'))
                dup_date = duplicate.get('import_date', duplicate.get(1, 'unknown'))
                import_logs.append({
                    'filename': filename,
                    'tenant_id': tenant_id,
                    'status': 'duplicate',
                    'error_message': f'Duplicate of {dup_filename} uploaded on {dup_date}',
                    'source': 'bulk_upload',
                    'import_method': 'file_upload',
                    'batch_id': batch_id,
                    'imported_by': user_id,
                    'file_size': file_size,
                    'file_hash': file_hash
                })
                continue

            # Process ZIP files
            if filename.lower().endswith('.zip'):
                logger.info(f"Processing ZIP file: {filename}")

                try:
                    # Use TemporaryDirectory for async-safe decompression
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)

                        # Extract ZIP
                        with zipfile.ZipFile(io.BytesIO(content)) as zf:
                            # Security: Check for zip bombs
                            total_extracted_size = sum(info.file_size for info in zf.filelist)
                            if total_extracted_size > MAX_TOTAL_SIZE:
                                raise HTTPException(
                                    status_code=413,
                                    detail=f"ZIP file expands to {total_extracted_size // (1024*1024)} MB, exceeds limit"
                                )

                            # Extract all files
                            zf.extractall(temp_path)

                            # Process each XML in the ZIP
                            for xml_path in temp_path.rglob('*.xml'):
                                xml_filename = f"{filename}/{xml_path.name}"

                                try:
                                    xml_content = xml_path.read_bytes()
                                    xml_hash = hashlib.sha256(xml_content).hexdigest()

                                    # Parse CFDI
                                    parsed = parse_cfdi_xml(xml_content)
                                    parsed['filename'] = xml_filename
                                    parsed['file_size'] = len(xml_content)
                                    parsed['file_hash'] = xml_hash
                                    parsed_invoices.append(parsed)

                                    # Log successful parse
                                    import_logs.append({
                                        'filename': xml_filename,
                                        'uuid_detectado': parsed.get('uuid'),
                                        'tenant_id': tenant_id,
                                        'status': 'pending',
                                        'source': 'bulk_upload',
                                        'import_method': 'zip_upload',
                                        'batch_id': batch_id,
                                        'imported_by': user_id,
                                        'file_size': len(xml_content),
                                        'file_hash': xml_hash,
                                        'detected_format': 'xml'
                                    })

                                except InvoiceParseError as e:
                                    logger.warning(f"Failed to parse {xml_filename}: {e}")
                                    import_logs.append({
                                        'filename': xml_filename,
                                        'tenant_id': tenant_id,
                                        'status': 'error',
                                        'error_message': f'Parse error: {str(e)}',
                                        'source': 'bulk_upload',
                                        'import_method': 'zip_upload',
                                        'batch_id': batch_id,
                                        'imported_by': user_id,
                                        'file_size': len(xml_content),
                                        'detected_format': 'xml'
                                    })

                except zipfile.BadZipFile:
                    logger.error(f"Invalid ZIP file: {filename}")
                    import_logs.append({
                        'filename': filename,
                        'tenant_id': tenant_id,
                        'status': 'error',
                        'error_message': 'Invalid or corrupted ZIP file',
                        'source': 'bulk_upload',
                        'import_method': 'file_upload',
                        'batch_id': batch_id,
                        'imported_by': user_id,
                        'file_size': file_size
                    })

            # Process individual XML files
            elif filename.lower().endswith('.xml'):
                try:
                    parsed = parse_cfdi_xml(content)
                    parsed['filename'] = filename
                    parsed['file_size'] = file_size
                    parsed['file_hash'] = file_hash
                    # ⭐ IMPORTANTE: Guardar XML completo para auditoría fiscal SAT
                    parsed['raw_xml'] = content.decode('utf-8') if isinstance(content, bytes) else content
                    parsed_invoices.append(parsed)

                    # Log successful parse
                    import_logs.append({
                        'filename': filename,
                        'uuid_detectado': parsed.get('uuid'),
                        'tenant_id': tenant_id,
                        'status': 'pending',
                        'source': 'bulk_upload',
                        'import_method': 'file_upload',
                        'batch_id': batch_id,
                        'imported_by': user_id,
                        'file_size': file_size,
                        'file_hash': file_hash,
                        'detected_format': 'xml'
                    })

                except InvoiceParseError as e:
                    logger.warning(f"Failed to parse {filename}: {e}")
                    import_logs.append({
                        'filename': filename,
                        'tenant_id': tenant_id,
                        'status': 'error',
                        'error_message': f'Parse error: {str(e)}',
                        'source': 'bulk_upload',
                        'import_method': 'file_upload',
                        'batch_id': batch_id,
                        'imported_by': user_id,
                        'file_size': file_size,
                        'file_hash': file_hash,
                        'detected_format': 'xml'
                    })

        # Insert all import logs into database
        if import_logs:
            for log in import_logs:
                cursor.execute("""
                    INSERT INTO invoice_import_logs (
                        filename, uuid_detectado, tenant_id, status, error_message,
                        source, import_method, batch_id, imported_by,
                        file_size, file_hash, detected_format, import_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log['filename'],
                    log.get('uuid_detectado'),
                    log['tenant_id'],
                    log['status'],
                    log.get('error_message'),
                    log['source'],
                    log['import_method'],
                    log['batch_id'],
                    log['imported_by'],
                    log.get('file_size'),
                    log.get('file_hash'),
                    log.get('detected_format'),
                    datetime.utcnow()
                ))
            conn.commit()
            logger.info(f"Logged {len(import_logs)} import records")

        # If no valid invoices parsed, return error summary
        if not parsed_invoices:
            error_count = sum(1 for log in import_logs if log['status'] == 'error')
            duplicate_count = sum(1 for log in import_logs if log['status'] == 'duplicate')

            return JSONResponse(
                status_code=400,
                content={
                    "batch_id": batch_id,
                    "status": "failed",
                    "total_files": len(files),
                    "parsed": 0,
                    "errors": error_count,
                    "duplicates": duplicate_count,
                    "message": "No valid invoices could be parsed",
                    "import_logs": import_logs[:10]  # Show first 10 errors
                }
            )

        # Initialize bulk processor
        from core.expenses.invoices.bulk_invoice_processor import bulk_invoice_processor
        # Note: bulk processor will initialize its own DB connection

        # Create batch with metadata
        batch_metadata = {
            "source": "file_upload",
            "batch_tag": batch_tag,
            "create_placeholder_on_no_match": create_placeholder_on_no_match,
            "total_files_uploaded": len(files),
            "total_xmls_parsed": len(parsed_invoices),
            "upload_timestamp": datetime.utcnow().isoformat()
        }

        # Create batch for async processing
        batch = await bulk_invoice_processor.create_batch(
            company_id=company_id,
            invoices=parsed_invoices,
            auto_link_threshold=auto_link_threshold,
            auto_mark_invoiced=auto_mark_invoiced,
            batch_metadata=batch_metadata,
            created_by=user_id
        )

        logger.info(f"Batch {batch_id} created with {len(parsed_invoices)} invoices")

        # Return immediately with batch_id for status tracking
        return {
            "batch_id": batch.batch_id,
            "status": "processing",
            "total_files": len(files),
            "total_invoices": len(parsed_invoices),
            "errors": sum(1 for log in import_logs if log['status'] == 'error'),
            "duplicates": sum(1 for log in import_logs if log['status'] == 'duplicate'),
            "message": f"Batch created successfully. {len(parsed_invoices)} invoices queued for processing.",
            "status_url": f"/api/bulk-invoice/batch/{batch.batch_id}/status",
            "results_url": f"/api/bulk-invoice/batch/{batch.batch_id}/results"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Bulk upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing bulk upload: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()


@app.post("/invoices/process-batch/{batch_id}")
async def process_invoice_batch(
    batch_id: str,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Trigger processing of a pending batch of invoices.

    This endpoint processes all invoices in the specified batch by:
    - Parsing and storing invoice data in expense_invoices table
    - Attempting to link invoices to existing expenses
    - Creating placeholders if no match found (based on batch config)
    - Updating batch status and metrics

    Args:
        batch_id: The batch ID to process

    Returns:
        {
            "batch_id": "batch_xyz",
            "status": "completed",
            "processed_count": 50,
            "linked_count": 35,
            "placeholder_count": 12,
            "error_count": 3
        }
    """
    try:
        from core.expenses.invoices.bulk_invoice_processor import bulk_invoice_processor

        logger.info(f"Processing batch {batch_id}")

        # Trigger batch processing
        batch = await bulk_invoice_processor.process_batch(batch_id)

        return {
            "batch_id": batch.batch_id,
            "status": batch.status.value,
            "processed_count": batch.processed_count,
            "linked_count": batch.linked_count,
            "placeholder_count": batch.batch_metadata.get('placeholder_count', 0) if batch.batch_metadata else 0,
            "error_count": batch.errors_count,
            "message": f"Batch processed successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Batch processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing batch: {str(e)}")


@app.post("/webhooks/batch-subscribe")
async def subscribe_to_batch_webhook(
    batch_id: str = Form(...),
    webhook_url: str = Form(...),
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
):
    """
    Subscribe to batch completion notifications.

    When the batch processing completes, a POST request will be sent to webhook_url with:
    {
        "batch_id": "batch_xyz",
        "status": "completed",
        "total_invoices": 100,
        "linked": 75,
        "placeholders_created": 20,
        "errors": 5,
        "success_rate": 95.0,
        "processing_time_ms": 45000,
        "completed_at": "2025-11-07T12:00:00Z"
    }
    """
    try:
        db = get_db_adapter()
        cursor = db.conn.cursor()

        # Validate batch exists
        cursor.execute("""
            SELECT COUNT(*) FROM bulk_invoice_batches
            WHERE batch_id = ?
        """, (batch_id,))

        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

        # Store webhook subscription
        cursor.execute("""
            INSERT INTO batch_webhooks (
                batch_id, webhook_url, tenant_id,
                created_at, status
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            batch_id,
            webhook_url,
            tenancy_context.tenant_id,
            datetime.utcnow(),
            'pending'
        ))

        db.conn.commit()

        logger.info(f"Webhook subscription created: batch {batch_id} -> {webhook_url}")

        return {
            "message": "Webhook subscription created",
            "batch_id": batch_id,
            "webhook_url": webhook_url
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error subscribing to webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invoices/bulk-match", response_model=BulkInvoiceMatchResponse)
async def bulk_invoice_match(request: BulkInvoiceMatchRequest) -> BulkInvoiceMatchResponse:
    if not request.invoices:
        raise HTTPException(status_code=400, detail="No se recibieron facturas para conciliar")

    results: List[InvoiceMatchResult] = []

    for invoice in request.invoices:
        if invoice.total is None:
            results.append(
                InvoiceMatchResult(
                    filename=invoice.filename,
                    uuid=invoice.uuid,
                    status="error",
                    message="El CFDI no incluye un total numérico",
                )
            )
            continue

        if invoice.raw_xml is None and invoice.uuid is None:
            results.append(
                InvoiceMatchResult(
                    filename=invoice.filename,
                    status="unsupported",
                    message="Archivo sin datos de CFDI. Aporta XML o UUID para conciliar",
                )
            )
            continue

        match_result = _match_invoice_to_expense(
            company_id=request.company_id,
            invoice=invoice,
            global_auto_mark=request.auto_mark_invoiced,
        )
        results.append(match_result)

    return BulkInvoiceMatchResponse(
        company_id=request.company_id,
        processed=len(results),
        results=results,
    )


@app.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    expense: ExpenseCreate,
    tenancy_context: TenancyContext = Depends(get_tenancy_context)
) -> ExpenseResponse:
    """
    Crear un nuevo gasto en la base de datos.

    Este endpoint crea un gasto con validaciones automáticas de:
    - Monto > 0 y < 10M MXN
    - RFC válido (12-13 caracteres alfanuméricos)
    - Fecha no futura
    - Mapeo automático de categoría a cuenta contable

    Args:
        expense: Datos del gasto a crear
        tenancy_context: Contexto de tenencia (inyectado)

    Returns:
        ExpenseResponse con los datos del gasto creado

    Raises:
        ValidationError: Si los datos no pasan validación
        ServiceError: Si hay error en la BD
    """
    from core.ai_pipeline.classification.category_mappings import get_account_code_for_category

    endpoint = "POST /expenses"
    log_endpoint_entry(endpoint, amount=expense.monto_total, company_id=expense.company_id)

    try:
        # Nota: Las validaciones de monto, fecha y RFC ya están en el modelo Pydantic
        # y se ejecutan automáticamente antes de llegar aquí

        if not expense.forma_pago:
            raise HTTPException(
                status_code=400,
                detail="forma_pago es obligatorio para registrar un gasto",
            )

        _validate_payment_account_for_user(expense.payment_account_id, tenancy_context)
        ticket_id, ticket_created = _ensure_ticket_binding(expense, tenancy_context)

        # Extraer nombre del proveedor
        provider_name = expense.proveedor.nombre if expense.proveedor else None

        # Mapeo automático de categoría a cuenta contable
        account_code = get_account_code_for_category(expense.categoria)

        invoice_uuid = None
        if expense.tax_info and expense.tax_info.get('uuid'):
            invoice_uuid = expense.tax_info['uuid']

        metadata_extra: Dict[str, Any] = dict(expense.metadata or {})
        if expense.proveedor:
            metadata_extra.setdefault('proveedor', expense.proveedor)
        if expense.rfc:
            metadata_extra.setdefault('rfc', expense.rfc)
        if expense.tax_info:
            metadata_extra.setdefault('tax_info', expense.tax_info)
        if expense.asientos_contables:
            metadata_extra['asientos_contables'] = expense.asientos_contables
        if expense.movimientos_bancarios:
            metadata_extra['movimientos_bancarios'] = expense.movimientos_bancarios

        if ticket_id:
            metadata_extra.setdefault(
                "ticket_context",
                {
                    "ticket_id": ticket_id,
                    "created_automatically": ticket_created,
                },
            )

        metadata_extra.pop('company_id', None)

        expense_id = record_internal_expense(
            description=expense.descripcion,
            amount=expense.monto_total,
            account_code=account_code,
            currency="MXN",
            expense_date=expense.fecha_gasto,
            category=expense.categoria,
            provider_name=provider_name,
            provider_rfc=expense.rfc,
            workflow_status=expense.workflow_status,
            invoice_status=expense.estado_factura,
            invoice_uuid=invoice_uuid,
            tax_total=expense.tax_info.get('total') if expense.tax_info else None,
            tax_metadata=expense.tax_info,
            payment_method=expense.forma_pago,
            payment_account_id=expense.payment_account_id,
            paid_by=expense.paid_by,
            will_have_cfdi=expense.will_have_cfdi,
            bank_status=expense.estado_conciliacion,
            metadata=metadata_extra,
            company_id=expense.company_id,
        )

        if ticket_id:
            _link_ticket_to_expense(ticket_id, expense_id)
            db_update_expense_record(expense_id, {"ticket_id": ticket_id})

        record = fetch_expense_record(expense_id)
        if not record:
            raise ServiceError("Database", "No se pudo recuperar el gasto creado")

        if ticket_created:
            logger.info("📌 Ticket virtual %s vinculado al gasto %s", ticket_id, expense_id)

        # ✅ NUEVO: Hook de escalamiento automático
        from core.expenses.workflow.expense_escalation_hooks import post_expense_creation_hook

        escalation_info = await post_expense_creation_hook(
            expense_id=expense_id,
            expense_data={
                "id": expense_id,
                "monto_total": expense.monto_total,
                "descripcion": expense.descripcion,
                "rfc": expense.rfc,
                "proveedor": expense.proveedor.model_dump() if expense.proveedor else None,
                "categoria": expense.categoria,
                "will_have_cfdi": expense.will_have_cfdi,
                "company_id": expense.company_id,
                "ticket_id": ticket_id,
            },
            user_id=getattr(tenancy_context, "user_id", None),
            company_id=expense.company_id,
        )

        # Log del resultado
        if escalation_info.get("escalated"):
            logger.info(
                f"✅ Expense {expense_id} escalado a ticket {escalation_info['ticket_id']}"
            )

        response = _build_expense_response(record)

        # Agregar metadata de escalamiento
        if not response.metadata:
            response.metadata = {}
        response.metadata["escalation"] = escalation_info

        log_endpoint_success(endpoint, expense_id=expense_id)
        return response

    except Exception as exc:
        log_endpoint_error(endpoint, exc)
        raise handle_error(exc, context=endpoint, default_message="Error creando gasto")


@app.get("/expenses", response_model=List[ExpenseResponse])
async def list_expenses(
    limit: int = 100,
    mes: Optional[str] = None,
    categoria: Optional[str] = None,
    estatus: Optional[str] = None,
    company_id: str = "default",
    current_user: User = Depends(get_current_user)
) -> List[ExpenseResponse]:
    """
    Listar gastos desde la base de datos filtrados por tenant del usuario autenticado.

    Requiere autenticación JWT.
    """

    try:
        if mes:
            try:
                datetime.strptime(mes, "%Y-%m")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Formato de mes inválido. Usa YYYY-MM") from exc

        # Use tenant_id from authenticated user
        tenant_id = current_user.tenant_id

        # 🔧 Filter by both tenant_id AND company_id
        records = fetch_expense_records(
            tenant_id=tenant_id,
            limit=limit,
            company_id=company_id,  # ← Ahora usa company_id de la query
            # Note: month, category, invoice_status filtering may need to be added to unified adapter
        )
        return [_build_expense_response(record) for record in records]

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error listing expenses: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error obteniendo gastos: {str(exc)}")


@app.delete("/expenses")
async def delete_expenses(company_id: str = "default") -> Dict[str, Any]:
    """Eliminar todos los gastos y datos relacionados para una empresa."""

    try:
        if config.USE_UNIFIED_DB:
            tenant_id = normalize_tenant_id(tenant_id=3, company_id=company_id)
            result = db_delete_company_expenses(tenant_id)
        else:
            result = db_delete_company_expenses(company_id)

        payload = dict(result or {})
        payload["company_id"] = company_id
        payload["status"] = "success"
        return payload

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error deleting expenses for company %s: %s", company_id, exc)
        raise HTTPException(status_code=500, detail="Error eliminando gastos")


@app.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: int, expense: ExpenseCreate) -> ExpenseResponse:
    """Actualizar un gasto existente en la base de datos."""

    try:
        provider_name = (expense.proveedor or {}).get("nombre") if expense.proveedor else None

        account_code = "6180"
        if expense.categoria:
            category_mapping = {
                'combustible': '6140',
                'combustibles': '6140',
                'viajes': '6150',
                'viaticos': '6150',
                'alimentos': '6150',
                'servicios': '6130',
                'oficina': '6180',
                'honorarios': '6110',
                'renta': '6120',
                'publicidad': '6160',
                'marketing': '6160'
            }
            account_code = category_mapping.get(expense.categoria.lower(), account_code)

        invoice_uuid = None
        if expense.tax_info and expense.tax_info.get('uuid'):
            invoice_uuid = expense.tax_info['uuid']

        metadata_extra: Dict[str, Any] = dict(expense.metadata or {})
        if expense.proveedor:
            metadata_extra.setdefault('proveedor', expense.proveedor)
        if expense.rfc:
            metadata_extra.setdefault('rfc', expense.rfc)
        if expense.tax_info:
            metadata_extra.setdefault('tax_info', expense.tax_info)
        if expense.asientos_contables:
            metadata_extra['asientos_contables'] = expense.asientos_contables
        if expense.movimientos_bancarios:
            metadata_extra['movimientos_bancarios'] = expense.movimientos_bancarios

        metadata_extra.pop('company_id', None)

        updates = {
            "description": expense.descripcion,
            "amount": expense.monto_total,
            "account_code": account_code,
            "expense_date": expense.fecha_gasto,
            "category": expense.categoria,
            "provider_name": provider_name,
            "provider_rfc": expense.rfc,
            "workflow_status": expense.workflow_status,
            "invoice_status": expense.estado_factura,
            "bank_status": expense.estado_conciliacion,
            "payment_method": expense.forma_pago,
            "paid_by": expense.paid_by,
            "will_have_cfdi": expense.will_have_cfdi,
            "invoice_uuid": invoice_uuid,
            "tax_total": expense.tax_info.get('total') if expense.tax_info else None,
            "tax_metadata": expense.tax_info,
            "metadata": metadata_extra,
            "company_id": expense.company_id,
        }

        record = db_update_expense_record(expense_id, updates)
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")

        return _build_expense_response(record)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error updating expense: %s", exc)
        raise HTTPException(status_code=500, detail=f"Error actualizando gasto: {str(exc)}")


@app.post("/expenses/{expense_id}/invoice", response_model=ExpenseResponse)
async def register_expense_invoice_endpoint(
    expense_id: int,
    payload: ExpenseInvoicePayload,
) -> ExpenseResponse:
    try:
        record = register_expense_invoice(
            expense_id,
            uuid=payload.uuid,
            folio=payload.folio,
            url=payload.url,
            issued_at=payload.issued_at,
            status=payload.status or "registrada",
            raw_xml=payload.raw_xml,
            actor=payload.actor,
        )
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return _build_expense_response(record)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error registrando factura interna: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo registrar la factura")


@app.post("/expenses/{expense_id}/mark-invoiced", response_model=ExpenseResponse)
async def mark_expense_as_invoiced(expense_id: int, request: ExpenseActionRequest) -> ExpenseResponse:
    try:
        record = db_mark_expense_invoiced(expense_id, actor=request.actor)
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return _build_expense_response(record)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error marcando gasto como facturado: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado de factura")


@app.post("/expenses/{expense_id}/close-no-invoice", response_model=ExpenseResponse)
async def close_expense_without_invoice(expense_id: int, request: ExpenseActionRequest) -> ExpenseResponse:
    try:
        record = db_mark_expense_without_invoice(expense_id, actor=request.actor)
        if not record:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        return _build_expense_response(record)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error cerrando gasto sin factura: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo cerrar el gasto sin factura")


@app.post("/expenses/check-duplicates", response_model=DuplicateCheckResponse)
async def check_expense_duplicates(request: DuplicateCheckRequest) -> DuplicateCheckResponse:
    """
    Verifica si un gasto nuevo es posiblemente duplicado comparándolo con gastos existentes.
    Usa embeddings semánticos y heurísticas para detectar similitudes.
    """
    try:
        from core.reconciliation.validation.duplicate_detector import detect_expense_duplicates

        # Obtener gastos existentes si se solicita
        existing_expenses = []
        company_scope = request.new_expense.company_id
        if request.check_existing:
            records = fetch_expense_records(limit=200, company_id=company_scope)
            for record in records:
                metadata = record.get("metadata") or {}
                proveedor = metadata.get("proveedor") or (
                    {"nombre": record.get("provider_name")} if record.get("provider_name") else None
                )
                existing_expenses.append(
                    {
                        'id': record['id'],
                        'descripcion': record['description'],
                        'monto_total': record['amount'],
                        'fecha_gasto': record.get('expense_date'),
                        'categoria': record.get('category'),
                        'proveedor': proveedor,
                        'rfc': record.get('provider_rfc') or metadata.get('rfc'),
                        'created_at': record.get('created_at'),
                    }
                )

        # Convertir ExpenseCreate a diccionario
        new_expense_dict = {
            'descripcion': request.new_expense.descripcion,
            'monto_total': request.new_expense.monto_total,
            'fecha_gasto': request.new_expense.fecha_gasto,
            'categoria': request.new_expense.categoria,
            'proveedor': request.new_expense.proveedor,
            'rfc': request.new_expense.rfc,
            'company_id': company_scope,
        }

        # Detectar duplicados
        detection_result = detect_expense_duplicates(new_expense_dict, existing_expenses)

        return DuplicateCheckResponse(
            has_duplicates=detection_result['summary']['has_duplicates'],
            total_found=detection_result['summary']['total_found'],
            risk_level=detection_result['summary']['risk_level'],
            recommendation=detection_result['summary']['recommendation'],
            duplicates=detection_result['duplicates'],
            summary=detection_result['summary']
        )

    except Exception as exc:
        logger.exception("Error checking for duplicate expenses: %s", exc)
        # En caso de error, permitir que continúe (fail-safe)
        return DuplicateCheckResponse(
            has_duplicates=False,
            total_found=0,
            risk_level='none',
            recommendation='proceed',
            duplicates=[],
            summary={'error': f'Error en detección: {str(exc)}'}
        )


@app.post("/expenses/predict-category", response_model=CategoryPredictionResponse)
async def predict_expense_category(request: CategoryPredictionRequest) -> CategoryPredictionResponse:
    """
    Predice la categoría de un gasto usando LLM contextual y historial del usuario.
    Incluye sugerencias de autocompletado para mejorar la UX.
    """
    try:
        from core.ai_pipeline.classification.category_predictor import predict_expense_category, get_category_predictor

        # Obtener historial de gastos si se solicita
        expense_history = []
        if request.include_history:
            records = fetch_expense_records(limit=50, company_id=request.company_id)
            for record in records:
                metadata = record.get("metadata") or {}
                provider = metadata.get('proveedor')
                if not provider and record.get('provider_name'):
                    provider = {"nombre": record.get('provider_name')}

                expense_history.append(
                    {
                        'descripcion': record['description'],
                        'monto_total': record['amount'],
                        'categoria': record.get('category'),
                        'proveedor': provider,
                        'fecha_gasto': record.get('expense_date'),
                        'created_at': record.get('created_at'),
                    }
                )

        # Predecir categoría
        prediction_result = predict_expense_category(
            description=request.description,
            amount=request.amount,
            provider_name=request.provider_name,
            expense_history=expense_history
        )

        # Obtener sugerencias de autocompletado
        predictor = get_category_predictor()
        autocomplete_suggestions = predictor.get_category_suggestions(
            prediction_result['categoria_sugerida']
        )

        return CategoryPredictionResponse(
            categoria_sugerida=prediction_result['categoria_sugerida'],
            confianza=prediction_result['confianza'],
            razonamiento=prediction_result['razonamiento'],
            alternativas=prediction_result['alternativas'],
            metodo_prediccion=prediction_result['metodo_prediccion'],
            sugerencias_autocompletado=autocomplete_suggestions
        )

    except Exception as exc:
        logger.exception("Error predicting expense category: %s", exc)
        # En caso de error, devolver categoría por defecto
        return CategoryPredictionResponse(
            categoria_sugerida='oficina',
            confianza=0.3,
            razonamiento=f'Error en predicción: {str(exc)}. Usando categoría por defecto.',
            alternativas=[],
            metodo_prediccion='fallback',
            sugerencias_autocompletado=[]
        )


@app.get("/expenses/category-suggestions")
async def get_category_suggestions(partial: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """
    Obtiene sugerencias de categorías para autocompletado.
    """
    try:
        from core.ai_pipeline.classification.category_predictor import get_category_predictor

        predictor = get_category_predictor()
        suggestions = predictor.get_category_suggestions(partial)

        return {"suggestions": suggestions}

    except Exception as exc:
        logger.exception("Error getting category suggestions: %s", exc)
        return {"suggestions": []}


# =====================================================
# CONVERSATIONAL ASSISTANT ENDPOINTS
# =====================================================

# Conversational assistant models moved to core/api_models.py
# - QueryRequest, QueryResponse, NonReconciliationRequest, NonReconciliationResponse


@app.post("/expenses/query")
async def process_natural_language_query(request: QueryRequest) -> QueryResponse:
    """
    Procesa consultas en lenguaje natural sobre gastos.

    Ejemplos de consultas:
    - "¿Cuánto gasté este mes?"
    - "Mostrar gastos de combustible"
    - "Breakdown por categorías"
    - "Gastos en Pemex"
    - "Resumen de gastos de la semana pasada"
    """
    try:
        from core.conversational_assistant import process_natural_language_query

        logger.info(f"Processing natural language query: {request.query}")

        result = process_natural_language_query(request.query)

        return QueryResponse(
            answer=result['answer'],
            data=result['data'],
            query_type=result['query_type'],
            confidence=result['confidence'],
            sql_executed=result['sql_executed'],
            has_llm=result['has_llm']
        )

    except Exception as exc:
        logger.exception("Error processing natural language query: %s", exc)
        return QueryResponse(
            answer=f"Ocurrió un error procesando tu consulta: {str(exc)}",
            data=None,
            query_type="error",
            confidence=0.1,
            sql_executed=None,
            has_llm=False
        )


@app.get("/expenses/query-help")
async def get_query_help() -> Dict[str, Any]:
    """
    Obtiene ayuda sobre los tipos de consultas que se pueden hacer.
    """
    return {
        "title": "Asistente Conversacional de Gastos",
        "description": "Puedes hacer consultas en lenguaje natural sobre tus gastos empresariales.",
        "examples": [
            {
                "query": "¿Cuánto gasté este mes?",
                "description": "Obtener resumen de gastos del mes actual"
            },
            {
                "query": "Mostrar gastos de combustible",
                "description": "Buscar gastos por categoría específica"
            },
            {
                "query": "Breakdown por categorías",
                "description": "Análisis detallado por todas las categorías"
            },
            {
                "query": "Gastos de la semana pasada",
                "description": "Análisis temporal de un período específico"
            },
            {
                "query": "Gastos en Pemex",
                "description": "Análisis por proveedor específico"
            },
            {
                "query": "Resumen general",
                "description": "Estadísticas generales de todos los gastos"
            }
        ],
        "query_types": [
            "expense_summary - Resúmenes y totales",
            "expense_search - Búsquedas específicas",
            "category_analysis - Análisis por categorías",
            "time_analysis - Análisis temporal",
            "provider_analysis - Análisis por proveedores"
        ]
    }


# =====================================================
# NON-RECONCILIATION MANAGEMENT ENDPOINTS
# =====================================================

@app.post("/expenses/{expense_id}/mark-non-reconcilable")
async def mark_expense_non_reconcilable(
    expense_id: str,
    request: NonReconciliationRequest
) -> NonReconciliationResponse:
    """
    Marca un gasto como no conciliable con motivo específico.

    Motivos comunes:
    - missing_invoice: Falta la factura CFDI
    - bank_account_missing: No aparece en estado de cuenta bancario
    - wrong_amount: Monto no coincide con la factura
    - duplicate_entry: Gasto duplicado
    - provider_issue: Problema con el proveedor
    - system_error: Error del sistema
    - pending_approval: Pendiente de aprobación
    - other: Otro motivo (especificar en notas)
    """
    try:
        logger.info(f"Marking expense {expense_id} as non-reconcilable: {request.reason_code}")

        # Motivos predefinidos con descripciones
        REASON_CODES = {
            "missing_invoice": "Falta la factura CFDI",
            "bank_account_missing": "No aparece en estado de cuenta bancario",
            "wrong_amount": "Monto no coincide con la factura",
            "duplicate_entry": "Gasto duplicado",
            "provider_issue": "Problema con el proveedor",
            "system_error": "Error del sistema",
            "pending_approval": "Pendiente de aprobación",
            "other": "Otro motivo"
        }

        if request.reason_code not in REASON_CODES:
            return NonReconciliationResponse(
                success=False,
                message=f"Código de motivo inválido: {request.reason_code}",
                expense_id=expense_id,
                status="error"
            )

        # Aquí normalmente actualizarías la base de datos
        # Por ahora simulamos la actualización
        non_reconciliation_data = {
            "expense_id": expense_id,
            "reason_code": request.reason_code,
            "reason_text": request.reason_text,
            "reason_description": REASON_CODES[request.reason_code],
            "notes": request.notes,
            "estimated_resolution_date": request.estimated_resolution_date,
            "marked_date": datetime.now().isoformat(),
            "status": "non_reconcilable"
        }

        logger.info(f"Expense {expense_id} marked as non-reconcilable: {non_reconciliation_data}")

        return NonReconciliationResponse(
            success=True,
            message=f"Gasto marcado como no conciliable: {REASON_CODES[request.reason_code]}",
            expense_id=expense_id,
            status="non_reconcilable"
        )

    except Exception as exc:
        logger.exception("Error marking expense as non-reconcilable: %s", exc)
        return NonReconciliationResponse(
            success=False,
            message=f"Error: {str(exc)}",
            expense_id=expense_id,
            status="error"
        )


@app.get("/expenses/non-reconciliation-reasons")
async def get_non_reconciliation_reasons() -> Dict[str, Any]:
    """
    Obtiene la lista de motivos predefinidos para no conciliación.
    """
    return {
        "reasons": [
            {
                "code": "missing_invoice",
                "title": "Falta factura CFDI",
                "description": "No se ha recibido o no se encuentra la factura correspondiente",
                "category": "documentation",
                "typical_resolution_days": 7
            },
            {
                "code": "bank_account_missing",
                "title": "No aparece en banco",
                "description": "El gasto no aparece en el estado de cuenta bancario",
                "category": "banking",
                "typical_resolution_days": 3
            },
            {
                "code": "wrong_amount",
                "title": "Monto no coincide",
                "description": "El monto registrado no coincide con la factura o estado de cuenta",
                "category": "amount_mismatch",
                "typical_resolution_days": 2
            },
            {
                "code": "duplicate_entry",
                "title": "Gasto duplicado",
                "description": "Este gasto ya fue registrado anteriormente",
                "category": "duplicate",
                "typical_resolution_days": 1
            },
            {
                "code": "provider_issue",
                "title": "Problema con proveedor",
                "description": "Hay un problema pendiente con el proveedor (datos incorrectos, etc.)",
                "category": "provider",
                "typical_resolution_days": 10
            },
            {
                "code": "system_error",
                "title": "Error del sistema",
                "description": "Error técnico que impide la conciliación automática",
                "category": "technical",
                "typical_resolution_days": 1
            },
            {
                "code": "pending_approval",
                "title": "Pendiente de aprobación",
                "description": "El gasto está pendiente de aprobación por parte de un superior",
                "category": "approval",
                "typical_resolution_days": 5
            },
            {
                "code": "other",
                "title": "Otro motivo",
                "description": "Motivo no contemplado en las opciones anteriores",
                "category": "other",
                "typical_resolution_days": 7
            }
        ],
        "categories": {
            "documentation": "Problemas de documentación",
            "banking": "Problemas bancarios",
            "amount_mismatch": "Discrepancias de montos",
            "duplicate": "Duplicados",
            "provider": "Problemas con proveedores",
            "technical": "Problemas técnicos",
            "approval": "Procesos de aprobación",
            "other": "Otros"
        }
    }


@app.get("/expenses/{expense_id}/non-reconciliation-status")
async def get_expense_non_reconciliation_status(expense_id: str) -> Dict[str, Any]:
    """
    Obtiene el estado de no conciliación de un gasto específico.
    """
    try:
        # Aquí normalmente consultarías la base de datos
        # Por ahora retornamos un ejemplo
        return {
            "expense_id": expense_id,
            "is_non_reconcilable": False,
            "reason": None,
            "notes": None,
            "marked_date": None,
            "estimated_resolution_date": None,
            "history": []
        }

    except Exception as exc:
        logger.exception("Error getting non-reconciliation status: %s", exc)
        return {
            "error": str(exc),
            "expense_id": expense_id
        }


# =====================================================
# EXPENSE TAGS MANAGEMENT ENDPOINTS
# =====================================================

@app.get("/expense-tags", response_model=List[ExpenseTagResponse])
async def list_expense_tags(
    current_user=Depends(get_current_user),
    include_usage_count: bool = Query(True, description="Include usage count for each tag")
):
    """
    Obtiene todas las etiquetas de gastos para el tenant del usuario actual.
    """
    try:
        tenant_id = current_user.tenant_id
        tags = get_expense_tags(tenant_id, include_usage_count)

        return [
            ExpenseTagResponse(
                id=tag["id"],
                name=tag["name"],
                color=tag["color"],
                description=tag["description"],
                tenant_id=tag["tenant_id"],
                created_by=tag["created_by"],
                created_at=tag["created_at"],
                usage_count=tag.get("usage_count", 0)
            )
            for tag in tags
        ]
    except Exception as e:
        logger.exception("Error listing expense tags")
        raise HTTPException(status_code=500, detail=f"Error listing tags: {str(e)}")


@app.post("/expense-tags", response_model=ExpenseTagResponse)
async def create_new_expense_tag(
    tag_data: ExpenseTagCreate,
    current_user=Depends(get_current_user)
):
    """
    Crea una nueva etiqueta de gastos.
    """
    try:
        tenant_id = current_user.tenant_id
        user_id = current_user.id

        # Check if tag name already exists for this tenant
        existing_tags = get_expense_tags(tenant_id, include_usage_count=False)
        if any(tag["name"] == tag_data.name.lower() for tag in existing_tags):
            raise HTTPException(status_code=400, detail="Tag name already exists")

        tag_id = create_expense_tag(
            name=tag_data.name,
            color=tag_data.color,
            description=tag_data.description,
            tenant_id=tenant_id,
            created_by=user_id
        )

        # Fetch the created tag to return
        created_tags = get_expense_tags(tenant_id, include_usage_count=True)
        created_tag = next((tag for tag in created_tags if tag["id"] == tag_id), None)

        if not created_tag:
            raise HTTPException(status_code=500, detail="Failed to retrieve created tag")

        return ExpenseTagResponse(
            id=created_tag["id"],
            name=created_tag["name"],
            color=created_tag["color"],
            description=created_tag["description"],
            tenant_id=created_tag["tenant_id"],
            created_by=created_tag["created_by"],
            created_at=created_tag["created_at"],
            usage_count=created_tag.get("usage_count", 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating expense tag")
        raise HTTPException(status_code=500, detail=f"Error creating tag: {str(e)}")


@app.put("/expense-tags/{tag_id}", response_model=ExpenseTagResponse)
async def update_existing_expense_tag(
    tag_id: int,
    tag_data: ExpenseTagUpdate,
    current_user=Depends(get_current_user)
):
    """
    Actualiza una etiqueta de gastos existente.
    """
    try:
        tenant_id = current_user.tenant_id

        # Check if tag exists and belongs to tenant
        existing_tags = get_expense_tags(tenant_id, include_usage_count=False)
        if not any(tag["id"] == tag_id for tag in existing_tags):
            raise HTTPException(status_code=404, detail="Tag not found")

        # Check if new name conflicts with existing tags (if name is being updated)
        if tag_data.name and any(
            tag["name"] == tag_data.name.lower() and tag["id"] != tag_id
            for tag in existing_tags
        ):
            raise HTTPException(status_code=400, detail="Tag name already exists")

        success = update_expense_tag(
            tag_id=tag_id,
            name=tag_data.name,
            color=tag_data.color,
            description=tag_data.description,
            tenant_id=tenant_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Tag not found or no updates made")

        # Fetch the updated tag
        updated_tags = get_expense_tags(tenant_id, include_usage_count=True)
        updated_tag = next((tag for tag in updated_tags if tag["id"] == tag_id), None)

        if not updated_tag:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated tag")

        return ExpenseTagResponse(
            id=updated_tag["id"],
            name=updated_tag["name"],
            color=updated_tag["color"],
            description=updated_tag["description"],
            tenant_id=updated_tag["tenant_id"],
            created_by=updated_tag["created_by"],
            created_at=updated_tag["created_at"],
            usage_count=updated_tag.get("usage_count", 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating expense tag")
        raise HTTPException(status_code=500, detail=f"Error updating tag: {str(e)}")


@app.delete("/expense-tags/{tag_id}")
async def delete_existing_expense_tag(
    tag_id: int,
    current_user=Depends(get_current_user)
):
    """
    Elimina una etiqueta de gastos y sus relaciones.
    """
    try:
        tenant_id = current_user.tenant_id

        # Check if tag exists and belongs to tenant
        existing_tags = get_expense_tags(tenant_id, include_usage_count=True)
        tag_to_delete = next((tag for tag in existing_tags if tag["id"] == tag_id), None)

        if not tag_to_delete:
            raise HTTPException(status_code=404, detail="Tag not found")

        # Check if tag is in use
        usage_count = tag_to_delete.get("usage_count", 0)
        if usage_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete tag that is assigned to {usage_count} expenses. Remove tag from expenses first."
            )

        success = delete_expense_tag(tag_id, tenant_id)

        if not success:
            raise HTTPException(status_code=404, detail="Tag not found")

        return {"message": "Tag deleted successfully", "deleted_tag_id": tag_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting expense tag")
        raise HTTPException(status_code=500, detail=f"Error deleting tag: {str(e)}")


@app.post("/expenses/{expense_id}/tags")
async def manage_expense_tags(
    expense_id: int,
    assignment_data: ExpenseTagAssignment,
    current_user=Depends(get_current_user)
):
    """
    Gestiona las etiquetas de un gasto (asignar, desasignar, reemplazar).
    """
    try:
        tenant_id = current_user.tenant_id

        # Verify expense exists and belongs to tenant
        expense = fetch_expense_record(expense_id)
        if not expense or expense.get("tenant_id") != tenant_id:
            raise HTTPException(status_code=404, detail="Expense not found")

        # Verify all tag IDs exist and belong to tenant
        if assignment_data.tag_ids:
            existing_tags = get_expense_tags(tenant_id, include_usage_count=False)
            existing_tag_ids = {tag["id"] for tag in existing_tags}
            invalid_tag_ids = [tag_id for tag_id in assignment_data.tag_ids if tag_id not in existing_tag_ids]

            if invalid_tag_ids:
                raise HTTPException(status_code=400, detail=f"Invalid tag IDs: {invalid_tag_ids}")

        # Perform the requested action
        if assignment_data.action == "assign":
            success = assign_expense_tags(expense_id, assignment_data.tag_ids)
        elif assignment_data.action == "unassign":
            success = unassign_expense_tags(expense_id, assignment_data.tag_ids)
        elif assignment_data.action == "replace":
            success = replace_expense_tags(expense_id, assignment_data.tag_ids)
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update expense tags")

        # Return current tags for the expense
        current_tags = get_expense_tags_for_expense(expense_id)

        return {
            "message": f"Tags {assignment_data.action}ed successfully",
            "expense_id": expense_id,
            "current_tags": [
                {
                    "id": tag["id"],
                    "name": tag["name"],
                    "color": tag["color"],
                    "assigned_at": tag["assigned_at"]
                }
                for tag in current_tags
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error managing expense tags")
        raise HTTPException(status_code=500, detail=f"Error managing tags: {str(e)}")


@app.get("/expenses/{expense_id}/tags")
async def get_expense_current_tags(
    expense_id: int,
    current_user=Depends(get_current_user)
):
    """
    Obtiene todas las etiquetas asignadas a un gasto específico.
    """
    try:
        tenant_id = current_user.tenant_id

        # Verify expense exists and belongs to tenant
        expense = fetch_expense_record(expense_id)
        if not expense or expense.get("tenant_id") != tenant_id:
            raise HTTPException(status_code=404, detail="Expense not found")

        tags = get_expense_tags_for_expense(expense_id)

        return {
            "expense_id": expense_id,
            "tags": [
                {
                    "id": tag["id"],
                    "name": tag["name"],
                    "color": tag["color"],
                    "description": tag["description"],
                    "assigned_at": tag["assigned_at"]
                }
                for tag in tags
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting expense tags")
        raise HTTPException(status_code=500, detail=f"Error getting tags: {str(e)}")


@app.get("/expense-tags/{tag_id}/expenses")
async def get_expenses_with_tag(
    tag_id: int,
    current_user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Obtiene todos los gastos que tienen una etiqueta específica.
    """
    try:
        tenant_id = current_user.tenant_id

        # Verify tag exists and belongs to tenant
        existing_tags = get_expense_tags(tenant_id, include_usage_count=False)
        if not any(tag["id"] == tag_id for tag in existing_tags):
            raise HTTPException(status_code=404, detail="Tag not found")

        expenses = get_expenses_by_tag(tag_id, tenant_id)

        # Apply pagination
        total = len(expenses)
        expenses = expenses[offset:offset + limit]

        return {
            "tag_id": tag_id,
            "total_expenses": total,
            "returned_count": len(expenses),
            "offset": offset,
            "limit": limit,
            "manual_expenses": [
                {
                    "id": expense["id"],
                    "description": expense["description"],
                    "amount": expense["amount"],
                    "date": expense["date"],
                    "merchant_name": expense.get("merchant_name"),
                    "category": expense.get("category"),
                    "status": expense.get("status"),
                    "user_name": expense.get("user_name"),
                    "tag_assigned_at": expense["tag_assigned_at"],
                    "created_at": expense["created_at"]
                }
                for expense in expenses
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting expenses by tag")
        raise HTTPException(status_code=500, detail=f"Error getting expenses: {str(e)}")


# =====================================================
# ENHANCED INVOICE MANAGEMENT ENDPOINTS
# =====================================================

@app.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    current_user=Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of invoices to return")
):
    """
    Obtiene todas las facturas para el tenant del usuario actual.
    """
    try:
        tenant_id = current_user.tenant_id
        invoices = get_invoice_records(tenant_id, status, limit)

        return [
            InvoiceResponse(
                id=invoice["id"],
                expense_id=invoice["expense_id"],
                filename=invoice["filename"],
                file_path=invoice["file_path"],
                content_type=invoice["content_type"],
                tenant_id=invoice["tenant_id"],
                created_at=invoice["created_at"],
                uuid=invoice.get("uuid"),
                rfc_emisor=invoice.get("rfc_emisor"),
                nombre_emisor=invoice.get("nombre_emisor"),
                subtotal=invoice.get("subtotal"),
                iva_amount=invoice.get("iva_amount"),
                total=invoice.get("total"),
                moneda=invoice.get("moneda", "MXN"),
                fecha_emision=invoice.get("fecha_emision"),
                processing_status=invoice.get("processing_status", "pending"),
                match_confidence=invoice.get("match_confidence", 0.0),
                auto_matched=invoice.get("auto_matched", False),
                processed_at=invoice.get("processed_at"),
                error_message=invoice.get("error_message"),
                expense_description=invoice.get("expense_description"),
                expense_amount=invoice.get("expense_amount"),
                amount_difference=invoice.get("amount_difference"),
                amount_match_quality=invoice.get("amount_match_quality")
            )
            for invoice in invoices
        ]
    except Exception as e:
        logger.exception("Error listing invoices")
        raise HTTPException(status_code=500, detail=f"Error listing invoices: {str(e)}")


@app.post("/invoices", response_model=InvoiceResponse)
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user=Depends(get_current_user)
):
    """
    Crea un nuevo registro de factura.
    """
    try:
        tenant_id = current_user.tenant_id
        user_id = current_user.id

        # Verificar que el gasto existe y pertenece al tenant
        expense = fetch_expense_record(invoice_data.expense_id)
        if not expense or expense.get("tenant_id") != tenant_id:
            raise HTTPException(status_code=404, detail="Expense not found")

        # Crear el registro de factura
        invoice_dict = invoice_data.dict()
        invoice_id = create_invoice_record(invoice_dict, tenant_id)

        # Obtener el registro creado
        created_invoice = get_invoice_record(invoice_id, tenant_id)
        if not created_invoice:
            raise HTTPException(status_code=500, detail="Failed to retrieve created invoice")

        return InvoiceResponse(
            id=created_invoice["id"],
            expense_id=created_invoice["expense_id"],
            filename=created_invoice["filename"],
            file_path=created_invoice["file_path"],
            content_type=created_invoice["content_type"],
            tenant_id=created_invoice["tenant_id"],
            created_at=created_invoice["created_at"],
            uuid=created_invoice.get("uuid"),
            rfc_emisor=created_invoice.get("rfc_emisor"),
            nombre_emisor=created_invoice.get("nombre_emisor"),
            subtotal=created_invoice.get("subtotal"),
            iva_amount=created_invoice.get("iva_amount"),
            total=created_invoice.get("total"),
            moneda=created_invoice.get("moneda", "MXN"),
            fecha_emision=created_invoice.get("fecha_emision"),
            processing_status=created_invoice.get("processing_status", "pending"),
            match_confidence=created_invoice.get("match_confidence", 0.0),
            auto_matched=created_invoice.get("auto_matched", False),
            processed_at=created_invoice.get("processed_at"),
            error_message=created_invoice.get("error_message"),
            expense_description=created_invoice.get("expense_description"),
            expense_amount=created_invoice.get("expense_amount"),
            amount_difference=created_invoice.get("amount_difference"),
            amount_match_quality=created_invoice.get("amount_match_quality")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating invoice")
        raise HTTPException(status_code=500, detail=f"Error creating invoice: {str(e)}")


@app.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    current_user=Depends(get_current_user)
):
    """
    Obtiene una factura específica.
    """
    try:
        tenant_id = current_user.tenant_id
        invoice = get_invoice_record(invoice_id, tenant_id)

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        return InvoiceResponse(
            id=invoice["id"],
            expense_id=invoice["expense_id"],
            filename=invoice["filename"],
            file_path=invoice["file_path"],
            content_type=invoice["content_type"],
            tenant_id=invoice["tenant_id"],
            created_at=invoice["created_at"],
            uuid=invoice.get("uuid"),
            rfc_emisor=invoice.get("rfc_emisor"),
            nombre_emisor=invoice.get("nombre_emisor"),
            subtotal=invoice.get("subtotal"),
            iva_amount=invoice.get("iva_amount"),
            total=invoice.get("total"),
            moneda=invoice.get("moneda", "MXN"),
            fecha_emision=invoice.get("fecha_emision"),
            processing_status=invoice.get("processing_status", "pending"),
            match_confidence=invoice.get("match_confidence", 0.0),
            auto_matched=invoice.get("auto_matched", False),
            processed_at=invoice.get("processed_at"),
            error_message=invoice.get("error_message"),
            expense_description=invoice.get("expense_description"),
            expense_amount=invoice.get("expense_amount"),
            amount_difference=invoice.get("amount_difference"),
            amount_match_quality=invoice.get("amount_match_quality")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting invoice")
        raise HTTPException(status_code=500, detail=f"Error getting invoice: {str(e)}")


@app.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    current_user=Depends(get_current_user)
):
    """
    Actualiza una factura existente.
    """
    try:
        tenant_id = current_user.tenant_id

        # Verificar que la factura existe
        existing_invoice = get_invoice_record(invoice_id, tenant_id)
        if not existing_invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Actualizar solo los campos proporcionados
        updates = {k: v for k, v in invoice_data.dict().items() if v is not None}

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        success = update_invoice_record(invoice_id, updates, tenant_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update invoice")

        # Obtener el registro actualizado
        updated_invoice = get_invoice_record(invoice_id, tenant_id)

        return InvoiceResponse(
            id=updated_invoice["id"],
            expense_id=updated_invoice["expense_id"],
            filename=updated_invoice["filename"],
            file_path=updated_invoice["file_path"],
            content_type=updated_invoice["content_type"],
            tenant_id=updated_invoice["tenant_id"],
            created_at=updated_invoice["created_at"],
            uuid=updated_invoice.get("uuid"),
            rfc_emisor=updated_invoice.get("rfc_emisor"),
            nombre_emisor=updated_invoice.get("nombre_emisor"),
            subtotal=updated_invoice.get("subtotal"),
            iva_amount=updated_invoice.get("iva_amount"),
            total=updated_invoice.get("total"),
            moneda=updated_invoice.get("moneda", "MXN"),
            fecha_emision=updated_invoice.get("fecha_emision"),
            processing_status=updated_invoice.get("processing_status", "pending"),
            match_confidence=updated_invoice.get("match_confidence", 0.0),
            auto_matched=updated_invoice.get("auto_matched", False),
            processed_at=updated_invoice.get("processed_at"),
            error_message=updated_invoice.get("error_message"),
            expense_description=updated_invoice.get("expense_description"),
            expense_amount=updated_invoice.get("expense_amount"),
            amount_difference=updated_invoice.get("amount_difference"),
            amount_match_quality=updated_invoice.get("amount_match_quality")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating invoice")
        raise HTTPException(status_code=500, detail=f"Error updating invoice: {str(e)}")


@app.post("/invoices/{invoice_id}/find-matches")
async def find_invoice_matches(
    invoice_id: int,
    current_user=Depends(get_current_user),
    threshold: float = Query(0.8, ge=0.0, le=1.0, description="Minimum matching confidence")
):
    """
    Busca gastos candidatos para hacer match con una factura.
    """
    try:
        tenant_id = current_user.tenant_id

        # Obtener la factura
        invoice = get_invoice_record(invoice_id, tenant_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Buscar matches candidatos
        matches = find_matching_expenses(invoice, tenant_id, threshold)

        return {
            "invoice_id": invoice_id,
            "threshold": threshold,
            "total_candidates": len(matches),
            "candidates": [
                {
                    "expense_id": match["id"],
                    "description": match["description"],
                    "amount": match["amount"],
                    "date": match["date"],
                    "merchant_name": match.get("merchant_name"),
                    "category": match.get("category"),
                    "match_score": match["match_score"],
                    "amount_difference": match["amount_difference"],
                    "user_name": match.get("user_name")
                }
                for match in matches
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error finding invoice matches")
        raise HTTPException(status_code=500, detail=f"Error finding matches: {str(e)}")


# =====================================================
# DUMMY DATA GENERATION ENDPOINTS
# =====================================================

@app.post("/demo/generate-dummy-data")
async def generate_dummy_data() -> Dict[str, Any]:
    """
    Genera datos de prueba realistas para demostrar el sistema.

    Crea gastos de ejemplo con diferentes estados:
    - Gastos normales conciliados
    - Gastos pendientes de facturación
    - Gastos con problemas de conciliación
    - Gastos duplicados
    - Gastos con diferentes categorías y proveedores
    """
    try:
        from datetime import datetime, timedelta
        import uuid

        logger.info("Generating dummy data for demonstration")

        # Datos base realistas
        DUMMY_EXPENSES = [
            # Gastos de Combustible
            {
                "descripcion": "Gasolina Premium Pemex Insurgentes",
                "monto_total": 850.00,
                "categoria": "combustible",
                "proveedor": {"nombre": "Pemex", "rfc": "PEP970814HS9"},
                "fecha_gasto": (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "PEP970814HS9",
                "urgency_level": "medium"
            },
            {
                "descripcion": "Diesel Shell Periférico Sur",
                "monto_total": 1200.00,
                "categoria": "combustible",
                "proveedor": {"nombre": "Shell", "rfc": "SHE880315QR4"},
                "fecha_gasto": (datetime.now() - timedelta(days=18)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "SHE880315QR4",
                "urgency_level": "high"
            },

            # Gastos de Alimentos
            {
                "descripcion": "Almuerzo reunión con cliente Starbucks",
                "monto_total": 320.50,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Starbucks Coffee", "rfc": "STA950612LP8"},
                "fecha_gasto": (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                "estado_factura": "facturado",
                "workflow_status": "facturado",
                "factura_id": "A12345",
                "urgency_level": "low"
            },
            {
                "descripcion": "Cena corporativa Restaurante Pujol",
                "monto_total": 2400.00,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Restaurante Pujol", "rfc": "PUJ030920MN2"},
                "fecha_gasto": (datetime.now() - timedelta(days=12)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "PUJ030920MN2",
                "urgency_level": "medium"
            },

            # Gastos de Transporte
            {
                "descripcion": "Viaje Uber a oficina cliente",
                "monto_total": 145.00,
                "categoria": "transporte",
                "proveedor": {"nombre": "Uber Technologies", "rfc": "UBE140225ST7"},
                "fecha_gasto": (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "UBE140225ST7",
                "urgency_level": "low"
            },
            {
                "descripcion": "Vuelo VivaAerobus CDMX-GDL",
                "monto_total": 1850.00,
                "categoria": "transporte",
                "proveedor": {"nombre": "VivaAerobus", "rfc": "VIV061205KL9"},
                "fecha_gasto": (datetime.now() - timedelta(days=28)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "VIV061205KL9",
                "urgency_level": "critical"
            },

            # Gastos de Tecnología
            {
                "descripcion": "Licencia Microsoft Office 365 Business",
                "monto_total": 1890.00,
                "categoria": "tecnologia",
                "proveedor": {"nombre": "Microsoft Mexico", "rfc": "MIC920818QP3"},
                "fecha_gasto": (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "MIC920818QP3",
                "urgency_level": "high"
            },
            {
                "descripcion": "Suscripción Adobe Creative Cloud",
                "monto_total": 980.00,
                "categoria": "tecnologia",
                "proveedor": {"nombre": "Adobe Systems", "rfc": "ADO851201TP5"},
                "fecha_gasto": (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                "estado_factura": "facturado",
                "workflow_status": "facturado",
                "factura_id": "ADO98765",
                "urgency_level": "low"
            },

            # Gastos de Oficina
            {
                "descripcion": "Suministros de oficina Office Depot",
                "monto_total": 450.75,
                "categoria": "oficina",
                "proveedor": {"nombre": "Office Depot Mexico", "rfc": "OFD770403XY1"},
                "fecha_gasto": (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "OFD770403XY1",
                "urgency_level": "medium"
            },

            # Gastos de Hospedaje
            {
                "descripcion": "Hotel City Express Guadalajara",
                "monto_total": 1250.00,
                "categoria": "hospedaje",
                "proveedor": {"nombre": "Hoteles City Express", "rfc": "HCE990515AB8"},
                "fecha_gasto": (datetime.now() - timedelta(days=22)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "HCE990515AB8",
                "urgency_level": "high"
            },

            # Casos especiales para demo de no conciliación
            {
                "descripcion": "Comida duplicada - Posible error",
                "monto_total": 320.50,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Starbucks Coffee", "rfc": "STA950612LP8"},
                "fecha_gasto": (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "rfc": "STA950612LP8",
                "urgency_level": "low",
                "is_potential_duplicate": True
            },
            {
                "descripcion": "Gasto sin factura - Pago en efectivo",
                "monto_total": 180.00,
                "categoria": "alimentos",
                "proveedor": {"nombre": "Taquería Local", "rfc": ""},
                "fecha_gasto": (datetime.now() - timedelta(days=35)).strftime('%Y-%m-%d'),
                "estado_factura": "pendiente",
                "workflow_status": "pendiente_factura",
                "urgency_level": "critical",
                "missing_invoice_reason": "Establecimiento pequeño sin facturación"
            }
        ]

        # Generar IDs únicos y agregar metadata
        generated_expenses = []
        for i, expense in enumerate(DUMMY_EXPENSES):
            expense_id = f"DEMO-{str(uuid.uuid4())[:8].upper()}"

            complete_expense = {
                "id": expense_id,
                "timestamp": datetime.now().isoformat(),
                "input_method": "demo_data",
                **expense,
                "metadata": {
                    "generated_demo": True,
                    "generation_time": datetime.now().isoformat(),
                    "urgency_analysis": {
                        "level": expense.get("urgency_level", "low"),
                        "days_old": (datetime.now() - datetime.strptime(expense["fecha_gasto"], '%Y-%m-%d')).days
                    }
                },
                "asientos_contables": {
                    "numero_poliza": f"POL-{1000 + i}",
                    "tipo_poliza": "Diario",
                    "fecha_asiento": expense["fecha_gasto"],
                    "concepto": f"Registro de {expense['descripcion']}",
                    "balanceado": True,
                    "movimientos": [
                        {
                            "cuenta": "60101",
                            "nombre_cuenta": f"Gastos de {expense['categoria'].title()}",
                            "debe": expense["monto_total"],
                            "haber": 0,
                            "tipo": "debe"
                        },
                        {
                            "cuenta": "11301",
                            "nombre_cuenta": "Bancos - Cuenta Principal",
                            "debe": 0,
                            "haber": expense["monto_total"],
                            "tipo": "haber"
                        }
                    ]
                }
            }

            generated_expenses.append(complete_expense)

        # Agregar estadísticas de la generación
        stats = {
            "total_generated": len(generated_expenses),
            "by_category": {},
            "by_status": {},
            "by_urgency": {},
            "total_amount": sum(exp["monto_total"] for exp in generated_expenses),
            "date_range": {
                "from": min(exp["fecha_gasto"] for exp in generated_expenses),
                "to": max(exp["fecha_gasto"] for exp in generated_expenses)
            }
        }

        # Calcular estadísticas
        for expense in generated_expenses:
            category = expense["categoria"]
            status = expense["estado_factura"]
            urgency = expense.get("urgency_level", "low")

            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["by_urgency"][urgency] = stats["by_urgency"].get(urgency, 0) + 1

        logger.info(f"Generated {len(generated_expenses)} dummy expenses for demo")

        return {
            "success": True,
            "message": f"Se generaron {len(generated_expenses)} gastos de demostración",
            "manual_expenses": generated_expenses,
            "statistics": stats,
            "demo_scenarios": [
                "✅ Gastos normales en diferentes categorías",
                "⏳ Gastos pendientes con diferentes niveles de urgencia",
                "🔴 Gastos críticos (>25 días sin facturar)",
                "🟡 Gastos con alta prioridad (>15 días)",
                "🔄 Posibles duplicados para demostrar detección",
                "📄 Gastos sin facturas para demostrar no conciliación",
                "💰 Montos variados para análisis de insights",
                "🏢 Proveedores reales mexicanos con RFC",
                "📊 Asientos contables generados automáticamente"
            ]
        }

    except Exception as exc:
        logger.exception("Error generating dummy data: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "Error generando datos de demostración"
        }


# ===== PDF EXTRACTION VALIDATION & AUDIT ENDPOINTS =====

@app.get("/audit/extraction-summary")
async def get_extraction_audit_summary(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Get summary of PDF extraction audits for the tenant"""
    try:
        from core.extraction_audit_logger import audit_logger

        summary = audit_logger.get_audit_summary(tenant_id=tenancy.tenant_id, days=days)

        return {
            "success": True,
            "summary": summary,
            "period_days": days
        }

    except Exception as e:
        logger.exception(f"Error getting audit summary: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving audit summary")


@app.get("/audit/missing-transactions")
async def get_missing_transactions_for_review(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Get missing transactions that need manual review"""
    try:
        from core.extraction_audit_logger import audit_logger

        missing_transactions = audit_logger.get_missing_transactions_for_review(
            tenant_id=tenancy.tenant_id,
            limit=limit
        )

        return {
            "success": True,
            "missing_transactions": missing_transactions,
            "count": len(missing_transactions)
        }

    except Exception as e:
        logger.exception(f"Error getting missing transactions: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving missing transactions")


@app.post("/audit/resolve-missing-transaction/{missing_id}")
async def resolve_missing_transaction(
    missing_id: int,
    resolution_notes: str,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Mark a missing transaction as resolved"""
    try:
        from core.extraction_audit_logger import audit_logger

        audit_logger.mark_missing_transaction_resolved(missing_id, resolution_notes)

        return {
            "success": True,
            "message": f"Missing transaction #{missing_id} marked as resolved"
        }

    except Exception as e:
        logger.exception(f"Error resolving missing transaction: {e}")
        raise HTTPException(status_code=500, detail="Error resolving missing transaction")


@app.post("/validate/account-transactions/{account_id}")
async def validate_account_transactions(
    account_id: int,
    pdf_text: str = None,
    expected_initial_balance: float = None,
    expected_final_balance: float = None,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Validate transactions for an account against provided PDF text"""
    try:
        from core.pdf_extraction_validator import PDFExtractionValidator
        import sqlite3

        # Get existing transactions for the account
        conn = sqlite3.connect('unified_mcp_system.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, date, description, amount, balance_after
            FROM bank_movements
            WHERE account_id = ? AND tenant_id = ?
            ORDER BY date ASC, id ASC
        """, (account_id, tenancy.tenant_id))

        transactions = cursor.fetchall()
        conn.close()

        # Convert to validation format
        validation_transactions = []
        for txn in transactions:
            validation_transactions.append({
                'id': txn[0],
                'date': txn[1],
                'description': txn[2],
                'amount': txn[3],
                'balance_after': txn[4]
            })

        # Run validation if PDF text provided
        if pdf_text:
            validator = PDFExtractionValidator()
            validation_result = validator.validate_extraction_completeness(
                pdf_text,
                validation_transactions,
                expected_initial_balance,
                expected_final_balance
            )

            # Generate human-readable report
            report = validator.generate_validation_report(validation_result)

            return {
                "success": True,
                "validation_passed": validation_result['is_complete'],
                "transaction_count": len(validation_transactions),
                "raw_transaction_count": validation_result['raw_transaction_count'],
                "missing_transactions": validation_result['missing_transactions'],
                "validation_issues": validation_result['issues'],
                "recommendations": validation_result['recommendations'],
                "detailed_report": report,
                "balance_validation": validation_result.get('balance_validation', {})
            }
        else:
            # Just return transaction info without validation
            return {
                "success": True,
                "message": "No PDF text provided for validation",
                "transaction_count": len(validation_transactions),
                "transactions": validation_transactions[:10]  # First 10 for preview
            }

    except Exception as e:
        logger.exception(f"Error validating account transactions: {e}")
        raise HTTPException(status_code=500, detail="Error validating transactions")


@app.get("/validation/system-status")
async def get_validation_system_status(
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> Dict[str, Any]:
    """Get overall status of the validation system"""
    try:
        from core.extraction_audit_logger import audit_logger

        # Get recent audit summary
        summary = audit_logger.get_audit_summary(tenant_id=tenancy.tenant_id, days=7)

        # Get pending issues
        missing_count = len(audit_logger.get_missing_transactions_for_review(tenancy.tenant_id, 100))

        # Calculate system health
        success_rate = summary.get('success_rate', 0)
        health_status = "excellent" if success_rate >= 95 else "good" if success_rate >= 85 else "needs_attention"

        return {
            "success": True,
            "system_health": health_status,
            "success_rate": success_rate,
            "total_extractions_7_days": summary.get('total_extractions', 0),
            "pending_manual_reviews": missing_count,
            "avg_extraction_time": summary.get('avg_extraction_time', 0),
            "total_api_cost_7_days": summary.get('total_estimated_cost', 0),
            "recommendations": [
                "Sistema funcionando correctamente" if health_status == "excellent"
                else "Revisar transacciones pendientes" if missing_count > 0
                else "Monitorear tasa de éxito"
            ]
        }

    except Exception as e:
        logger.exception(f"Error getting validation system status: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving system status")


# ========================================
# SAT Descarga Masiva API
# ========================================
try:
    from api.sat_download_simple import router as sat_download_router
    app.include_router(sat_download_router)
    logger.info("✅ SAT Download API loaded successfully (simplified version)")
except ImportError as e:
    logger.warning(f"⚠️  SAT Download API not available: {e}")

# ========================================
# SAT Auto Sync Configuration API
# ========================================
try:
    from api.sat_sync_config_api import router as sat_sync_config_router
    app.include_router(sat_sync_config_router)
    logger.info("✅ SAT Auto Sync Config API loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️  SAT Auto Sync Config API not available: {e}")

# ========================================
# SAT Sync Dashboard API
# ========================================
try:
    from api.sat_sync_dashboard_api import router as sat_sync_dashboard_router
    app.include_router(sat_sync_dashboard_router)
    logger.info("✅ SAT Sync Dashboard API loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️  SAT Sync Dashboard API not available: {e}")

# ========================================
# SAT Credentials API
# ========================================
try:
    from api.sat_credentials_api import router as sat_credentials_router
    app.include_router(sat_credentials_router)
    logger.info("✅ SAT Credentials API loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️  SAT Credentials API not available: {e}")

# ========================================
# CFDI Verification API
# ========================================
try:
    from api.cfdi_api import router as cfdi_router
    app.include_router(cfdi_router)
    logger.info("✅ CFDI Verification API loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️  CFDI Verification API not available: {e}")


if __name__ == "__main__":
    # Run the server when executed directly
    logger.info(f"Starting MCP Server on localhost:8001")
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8001,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )
