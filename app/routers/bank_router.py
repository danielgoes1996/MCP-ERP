"""Banking and reconciliation core endpoints."""

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
import logging

from core.auth.unified import get_current_active_user, User
from core.reconciliation.bank.bank_statements_models import (
    BankStatementResponse,
    BankStatementSummary,
    CreateBankStatementRequest,
    FileType,
    ParsingStatus,
    bank_statements_service,
)

router = APIRouter(prefix="/bank", tags=["banking"])
logger = logging.getLogger(__name__)


@router.post("/accounts/{account_id}/statements", response_model=BankStatementResponse, status_code=status.HTTP_201_CREATED)
async def upload_bank_statement(
    account_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
) -> BankStatementResponse:
    try:
        from pathlib import Path

        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de archivo requerido")

        file_extension = Path(file.filename).suffix.lower()
        valid_extensions = {".pdf", ".xlsx", ".xls", ".csv"}
        if file_extension not in valid_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de archivo no soportado. Soportados: {', '.join(valid_extensions)}",
            )

        file_type_mapping = {
            ".pdf": FileType.PDF,
            ".xlsx": FileType.XLSX,
            ".xls": FileType.XLS,
            ".csv": FileType.CSV,
        }
        file_type = file_type_mapping[file_extension]

        file_content = await file.read()
        max_size = 50 * 1024 * 1024
        if len(file_content) > max_size:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo demasiado grande. Máximo 50MB permitido")

        create_request = CreateBankStatementRequest(
            account_id=account_id,
            file_name=file.filename,
            file_type=file_type,
        )

        statement = bank_statements_service.create_statement(
            create_request, current_user.id, current_user.tenant_id, file_content
        )

        background_tasks.add_task(
            parse_statement_background,
            statement.id,
            statement.file_path,
            file_type.value if hasattr(file_type, "value") else file_type,
            account_id,
            current_user.id,
            current_user.tenant_id,
        )

        return BankStatementResponse(
            statement=statement,
            transactions=[],
            summary={
                "status": "pending",
                "message": "Archivo subido exitosamente. El parsing se ejecutará en background.",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("Error uploading bank statement: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al subir estado de cuenta")


@router.get("/accounts/{account_id}/statements", response_model=List[BankStatementSummary])
async def list_account_statements(account_id: int, current_user: User = Depends(get_current_active_user)) -> List[BankStatementSummary]:
    try:
        return bank_statements_service.get_user_statements(current_user.id, current_user.tenant_id, account_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting statements for account %s: %s", account_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al obtener estados de cuenta")


@router.get("/statements", response_model=List[BankStatementSummary])
async def list_user_statements(current_user: User = Depends(get_current_active_user)) -> List[BankStatementSummary]:
    try:
        return bank_statements_service.get_user_statements(current_user.id, current_user.tenant_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting user statements: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al obtener estados de cuenta")


@router.get("/statements/{statement_id}", response_model=BankStatementResponse)
async def get_statement(statement_id: int, current_user: User = Depends(get_current_active_user)) -> BankStatementResponse:
    try:
        statement = bank_statements_service.get_statement(statement_id, current_user.id, current_user.tenant_id)
        transactions = bank_statements_service.get_statement_transactions(statement_id, current_user.id, current_user.tenant_id)
        summary = {
            "total_transactions": len(transactions),
            "total_credits": sum(txn.amount for txn in transactions if txn.transaction_type.value == "credit"),
            "total_debits": sum(txn.amount for txn in transactions if txn.transaction_type.value == "debit"),
            "period_start": statement.period_start,
            "period_end": statement.period_end,
            "parsing_status": statement.parsing_status.value,
        }
        return BankStatementResponse(statement=statement, transactions=transactions, summary=summary)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de cuenta no encontrado")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error getting statement %s: %s", statement_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al obtener estado de cuenta")


@router.post("/statements/{statement_id}/reparse")
async def reparse_statement(
    statement_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    try:
        statement = bank_statements_service.get_statement(statement_id, current_user.id, current_user.tenant_id)
        bank_statements_service.update_parsing_status(statement_id, ParsingStatus.PROCESSING)
        background_tasks.add_task(
            parse_statement_background,
            statement.id,
            statement.file_path,
            statement.file_type.value if hasattr(statement.file_type, "value") else statement.file_type,
            statement.account_id,
            statement.user_id,
            statement.tenant_id,
            True,
        )
        return {"message": "Re-parsing iniciado en background"}
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estado de cuenta no encontrado")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error re-parsing statement %s: %s", statement_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al re-parsear estado de cuenta")


@router.get("/health")
async def bank_health_check() -> dict:
    return {"status": "healthy", "service": "bank"}


async def parse_statement_background(
    statement_id: int,
    file_path: str,
    file_type: str,
    account_id: int,
    user_id: int,
    tenant_id: int,
    is_reparse: bool = False,
) -> None:
    """Background parsing task reused from legacy implementation."""
    try:
        from core.reconciliation.bank.bank_file_parser import bank_file_parser

        logger.info("Parsing bank statement %s in background", statement_id)
        transactions = await bank_file_parser.parse_file_async(file_path, file_type)
        bank_statements_service.save_parsed_transactions(
            statement_id,
            transactions,
            account_id,
            user_id,
            tenant_id,
            is_reparse=is_reparse,
        )
        bank_statements_service.update_parsing_status(statement_id, ParsingStatus.COMPLETED)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error parsing statement %s: %s", statement_id, exc)
        bank_statements_service.update_parsing_status(statement_id, ParsingStatus.FAILED, str(exc))
