"""
API endpoints para gestión de estados de cuenta bancarios
Incluye upload de archivos, parsing automático y gestión de transacciones
"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, BackgroundTasks
from typing import List, Optional, Any
from datetime import datetime, date
import logging
import asyncio
from pathlib import Path
import os

from core.auth.unified import get_current_active_user, User
from core.reconciliation.bank.bank_statements_models import (
    BankStatement,
    BankTransaction,
    CreateBankStatementRequest,
    BankStatementResponse,
    BankStatementSummary,
    ParsingStatus,
    FileType,
    bank_statements_service
)
from core.reconciliation.bank.bank_file_parser import bank_file_parser

logger = logging.getLogger(__name__)

# Router para endpoints de estados de cuenta
router = APIRouter(prefix="/bank-statements", tags=["Bank Statements"])


@router.post("/accounts/{account_id}/upload", response_model=BankStatementResponse, status_code=status.HTTP_201_CREATED)
async def upload_bank_statement(
    account_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Subir estado de cuenta para una cuenta específica

    Soporta archivos PDF, Excel (.xlsx, .xls) y CSV
    El parsing se ejecuta en background y se notifica cuando esté listo

    Parámetros:
    - account_id: ID de la cuenta de pago
    - file: Archivo del estado de cuenta

    Retorna:
    - Statement creado con status 'pending'
    - El parsing se ejecutará en background
    """
    try:
        logger.info(f"Uploading bank statement for account {account_id}, user: {current_user.email}")

        # Validar tipo de archivo
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nombre de archivo requerido"
            )

        file_extension = Path(file.filename).suffix.lower()
        valid_extensions = {'.pdf', '.xlsx', '.xls', '.csv'}

        if file_extension not in valid_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de archivo no soportado. Soportados: {', '.join(valid_extensions)}"
            )

        # Mapear extensión a FileType
        file_type_mapping = {
            '.pdf': FileType.PDF,
            '.xlsx': FileType.XLSX,
            '.xls': FileType.XLS,
            '.csv': FileType.CSV
        }

        file_type = file_type_mapping[file_extension]

        # Validar tamaño (máximo 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        file_content = await file.read()

        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archivo demasiado grande. Máximo 50MB permitido"
            )

        # Crear request
        create_request = CreateBankStatementRequest(
            account_id=account_id,
            file_name=file.filename,
            file_type=file_type
        )

        # Crear statement en BD
        statement = bank_statements_service.create_statement(
            create_request, current_user.id, current_user.tenant_id, file_content
        )

        # Programar parsing en background
        background_tasks.add_task(
            parse_statement_background,
            statement.id,
            statement.file_path,
            file_type.value if hasattr(file_type, 'value') else file_type,
            account_id,
            current_user.id,
            current_user.tenant_id
        )

        logger.info(f"Bank statement uploaded: {statement.id} for account {account_id}")

        return BankStatementResponse(
            statement=statement,
            transactions=[],
            summary={
                "status": "pending",
                "message": "Archivo subido exitosamente. El parsing se ejecutará en background."
            }
        )

    except ValueError as e:
        logger.warning(f"Validation error uploading statement: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading bank statement for account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al subir estado de cuenta"
        )


@router.get("/accounts/{account_id}", response_model=List[BankStatementSummary])
async def get_account_statements(
    account_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtener todos los estados de cuenta de una cuenta específica

    Parámetros:
    - account_id: ID de la cuenta de pago

    Retorna:
    - Lista de estados de cuenta con resumen
    """
    try:
        logger.info(f"Getting statements for account {account_id}, user: {current_user.email}")

        statements = bank_statements_service.get_user_statements(
            current_user.id, current_user.tenant_id, account_id
        )

        logger.info(f"Found {len(statements)} statements for account {account_id}")
        return statements

    except Exception as e:
        logger.error(f"Error getting statements for account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estados de cuenta"
        )


@router.get("/{statement_id}", response_model=BankStatementResponse)
async def get_statement_details(
    statement_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtener detalles completos de un estado de cuenta

    Parámetros:
    - statement_id: ID del estado de cuenta

    Retorna:
    - Statement con todas sus transacciones
    """
    try:
        logger.info(f"Getting statement {statement_id} details for user: {current_user.email}")

        # Obtener statement
        statement = bank_statements_service.get_statement(
            statement_id, current_user.id, current_user.tenant_id
        )

        # Obtener transacciones
        transactions = bank_statements_service.get_statement_transactions(
            statement_id, current_user.id, current_user.tenant_id
        )

        # Calcular resumen
        summary = {
            "total_transactions": len(transactions),
            "total_credits": sum(txn.amount for txn in transactions if txn.transaction_type.value == "credit"),
            "total_debits": sum(txn.amount for txn in transactions if txn.transaction_type.value == "debit"),
            "period_start": statement.period_start,
            "period_end": statement.period_end,
            "parsing_status": statement.parsing_status.value
        }

        return BankStatementResponse(
            statement=statement,
            transactions=transactions,
            summary=summary
        )

    except ValueError as e:
        logger.warning(f"Statement {statement_id} not found for user {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estado de cuenta no encontrado"
        )
    except Exception as e:
        logger.error(f"Error getting statement {statement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estado de cuenta"
        )


@router.delete("/{statement_id}")
async def delete_statement(
    statement_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    Eliminar estado de cuenta y sus transacciones

    Parámetros:
    - statement_id: ID del estado de cuenta

    Retorna:
    - Confirmación de eliminación
    """
    try:
        logger.info(f"Deleting statement {statement_id} for user: {current_user.email}")

        success = bank_statements_service.delete_statement(
            statement_id, current_user.id, current_user.tenant_id
        )

        if success:
            logger.info(f"Statement deleted: {statement_id} for user {current_user.email}")
            return {"message": "Estado de cuenta eliminado exitosamente"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo eliminar el estado de cuenta"
            )

    except ValueError as e:
        logger.warning(f"Statement {statement_id} not found for user {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estado de cuenta no encontrado"
        )
    except Exception as e:
        logger.error(f"Error deleting statement {statement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar estado de cuenta"
        )


@router.get("/", response_model=List[BankStatementSummary])
async def get_user_statements(
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtener todos los estados de cuenta del usuario

    Retorna:
    - Lista de todos los estados de cuenta del usuario
    """
    try:
        logger.info(f"Getting all statements for user: {current_user.email}")

        statements = bank_statements_service.get_user_statements(
            current_user.id, current_user.tenant_id
        )

        logger.info(f"Found {len(statements)} statements for user {current_user.email}")
        return statements

    except Exception as e:
        logger.error(f"Error getting statements for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estados de cuenta"
        )


@router.post("/{statement_id}/reparse")
async def reparse_statement(
    statement_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Re-parsear un estado de cuenta existente

    Útil si el parsing inicial falló o se mejoraron los algoritmos

    Parámetros:
    - statement_id: ID del estado de cuenta

    Retorna:
    - Confirmación de que el re-parsing iniciará
    """
    try:
        logger.info(f"Re-parsing statement {statement_id} for user: {current_user.email}")

        # Verificar que el statement existe
        statement = bank_statements_service.get_statement(
            statement_id, current_user.id, current_user.tenant_id
        )

        # Actualizar status a processing
        bank_statements_service.update_parsing_status(
            statement_id, ParsingStatus.PROCESSING
        )

        # Programar re-parsing en background
        background_tasks.add_task(
            parse_statement_background,
            statement.id,
            statement.file_path,
            statement.file_type.value if hasattr(statement.file_type, 'value') else statement.file_type,
            statement.account_id,
            statement.user_id,
            statement.tenant_id,
            is_reparse=True
        )

        return {"message": "Re-parsing iniciado en background"}

    except ValueError as e:
        logger.warning(f"Statement {statement_id} not found for user {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estado de cuenta no encontrado"
        )
    except Exception as e:
        logger.error(f"Error re-parsing statement {statement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al re-parsear estado de cuenta"
        )


# Background task para parsing
async def parse_statement_background(
    statement_id: int,
    file_path: str,
    file_type: str,
    account_id: int,
    user_id: int,
    tenant_id: int,
    is_reparse: bool = False
):
    """
    Parsear estado de cuenta en background

    Esta función se ejecuta de forma asíncrona después del upload
    """
    try:
        logger.info(f"🔄 Starting {'re-' if is_reparse else ''}parsing for statement {statement_id}")

        # Actualizar status a processing
        bank_statements_service.update_parsing_status(
            statement_id, ParsingStatus.PROCESSING
        )

        # Si es re-parse, limpiar transacciones existentes para evitar duplicados
        if is_reparse:
            bank_statements_service.clear_statement_transactions(statement_id)

        # Parsear archivo
        transactions, summary = bank_file_parser.parse_file(
            file_path, file_type, account_id, user_id, tenant_id
        )

        opening_balance = summary.get('opening_balance') if isinstance(summary, dict) else None
        closing_balance = summary.get('closing_balance') if isinstance(summary, dict) else None
        enrichment_model = None
        enrichment_confidence = None
        if transactions:
            enrichment_model = transactions[0].ai_model or None
            enrichment_confidence = transactions[0].confidence
        enrichment_model = enrichment_model or os.getenv("GEMINI_TRANSACTION_MODEL") or os.getenv("CLAUDE_TRANSACTION_MODEL") or os.getenv("CLAUDE_MODEL") or "gemini-2.5-flash"
        if enrichment_confidence is None:
            enrichment_confidence = 1.0

        def _coerce_summary_date(value: Any) -> Optional[date]:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value).date()
                except ValueError:
                    try:
                        return datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        return None
            return None

        balance_date = None
        if transactions:
            balance_date = min((txn.date for txn in transactions if getattr(txn, 'date', None)), default=None)
        if isinstance(summary, dict):
            period_start = _coerce_summary_date(summary.get('period_start'))
            if period_start and (balance_date is None or period_start < balance_date):
                balance_date = period_start
            elif balance_date is None:
                balance_date = _coerce_summary_date(summary.get('period_end'))

        if opening_balance is not None:
            bank_statements_service.upsert_initial_balance(
                statement_id,
                account_id,
                user_id,
                tenant_id,
                opening_balance,
                balance_date,
                ai_model=enrichment_model,
                confidence=enrichment_confidence,
                display_name="Balance inicial",
            )

        closing_date = None
        if transactions:
            closing_date = max((txn.date for txn in transactions if getattr(txn, 'date', None)), default=None)
        if isinstance(summary, dict):
            period_end = _coerce_summary_date(summary.get('period_end'))
            if period_end and (closing_date is None or period_end > closing_date):
                closing_date = period_end
            elif closing_date is None:
                closing_date = balance_date

        if closing_balance is not None:
            bank_statements_service.upsert_closing_balance(
                statement_id,
                account_id,
                user_id,
                tenant_id,
                closing_balance,
                closing_date,
                ai_model=enrichment_model,
                confidence=enrichment_confidence,
                display_name="Balance final",
            )

        # Guardar transacciones
        bank_statements_service.add_transactions(statement_id, transactions)

        # Actualizar status y resumen
        bank_statements_service.update_parsing_status(
            statement_id, ParsingStatus.COMPLETED, summary_data=summary
        )

        logger.info(f"✅ Successfully {'re-' if is_reparse else ''}parsed statement {statement_id}: {len(transactions)} transactions")

    except Exception as e:
        logger.error(f"❌ Error {'re-' if is_reparse else ''}parsing statement {statement_id}: {e}")

        # Actualizar status a failed
        bank_statements_service.update_parsing_status(
            statement_id, ParsingStatus.FAILED, error=str(e)
        )


# Health check específico para bank statements
@router.get("/health/check")
async def bank_statements_health():
    """
    Health check del sistema de estados de cuenta
    """
    try:
        # Test básico de conectividad
        service = bank_statements_service

        # Verificar directorio de uploads
        upload_dir = Path("uploads/statements")
        upload_dir_exists = upload_dir.exists()

        # Intentar obtener statements de un usuario de prueba
        test_statements = service.get_user_statements(9, 3)

        return {
            "status": "healthy",
            "service": "bank_statements",
            "database_connected": True,
            "upload_directory_exists": upload_dir_exists,
            "test_statements_found": len(test_statements),
            "supported_formats": ["PDF", "Excel (.xlsx, .xls)", "CSV"],
            "max_file_size": "50MB",
            "version": "1.0.0"
        }

    except Exception as e:
        logger.error(f"Bank statements health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "bank_statements",
            "error": str(e)
        }
