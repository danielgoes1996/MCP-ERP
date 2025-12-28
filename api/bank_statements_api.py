"""
API endpoints para gestión de estados de cuenta bancarios
Incluye upload de archivos, parsing automático y gestión de transacciones
"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, BackgroundTasks, Request, Query, Form
from typing import List, Optional, Any
from datetime import datetime, date
import logging
import asyncio
from pathlib import Path
import os
from psycopg2.extras import RealDictCursor

from core.auth.unified import get_current_active_user, User, decode_token, get_user_by_id
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
from core.payment_accounts_models import (
    CreateUserPaymentAccountRequest,
    TipoCuenta,
    SubtipoCuenta,
    UserPaymentAccountService
)

logger = logging.getLogger(__name__)

# Router para endpoints de estados de cuenta
router = APIRouter(prefix="/bank-statements", tags=["Bank Statements"])


async def get_user_from_token_or_query(
    request: Request,
    token: Optional[str] = Query(None)
) -> User:
    """
    Obtener usuario autenticado desde Authorization header O query parameter ?token=

    Útil para endpoints que necesitan funcionar en iframes que no pueden enviar headers
    """
    from core.auth.unified import get_user_by_id
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

    auth_token = None

    # Try to get token from Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        auth_token = auth_header.replace("Bearer ", "")
    # Otherwise, try query parameter
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Decode token and get user
        token_data = decode_token(auth_token)
        user_id = token_data.user_id

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/auto-detect-account")
async def auto_detect_account(
    file: UploadFile = File(...),
    auto_create: bool = Form(False),
    current_user: User = Depends(get_current_active_user)
):
    """
    Auto-detect which payment account matches a bank statement PDF

    This endpoint:
    1. Extracts metadata from PDF using Gemini Vision (CLABE, RFC, bank name, last 4 digits)
    2. Runs hierarchical account matching algorithm
    3. (Optional) Auto-creates account if no match found and auto_create=true
    4. Returns match results with confidence scores

    **Parameters:**
    - file: Bank statement PDF file
    - auto_create: If true, automatically creates account when no match is found (default: false)

    **Use case:** Call this BEFORE uploading to suggest which account to use

    **Returns:**
    - confidence: 0-100 confidence score
    - action: "confirm_once" | "confirm" | "user_select" | "create_new"
    - account_id: Matched account ID (if found or created)
    - candidates: List of candidate accounts (if multiple matches)
    - extracted_data: Metadata extracted from PDF
    - created_account: True if account was auto-created (only when auto_create=true)
    """
    try:
        import tempfile
        import psycopg2
        from core.ai_pipeline.parsers.ai_bank_statement_parser import get_ai_parser
        from core.reconciliation.bank.account_matcher import get_account_matcher
        from core.reconciliation.bank.bank_statements_models import POSTGRES_CONFIG
        from psycopg2.extras import RealDictCursor

        logger.info(f"Auto-detecting account for user: {current_user.email}")

        # Validate file type
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename required"
            )

        file_extension = Path(file.filename).suffix.lower()
        if file_extension != '.pdf':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported for auto-detection"
            )

        # Read file content
        file_content = await file.read()

        # Save to temp file for Gemini processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name

        try:
            # STEP 1: Extract metadata using Gemini
            logger.info("📄 Step 1/2: Extracting metadata with Gemini Vision...")
            ai_parser = get_ai_parser()
            statement_data = ai_parser.parse_pdf(tmp_file_path)

            extracted_data = {
                "bank_info": {
                    "clabe": statement_data.metadata.get("clabe"),
                    "rfc_receptor": statement_data.metadata.get("rfc_receptor"),
                    "bank_name": statement_data.bank_name,
                    "last_4_digits": statement_data.account_number[-4:] if statement_data.account_number and len(statement_data.account_number) >= 4 else None,
                    "account_number": statement_data.account_number,
                    "account_type": statement_data.account_type,
                    "titular": statement_data.metadata.get("titular"),
                    "period_start": statement_data.period_start.isoformat() if statement_data.period_start else None,
                    "period_end": statement_data.period_end.isoformat() if statement_data.period_end else None
                },
                "summary": {
                    "opening_balance": statement_data.opening_balance,
                    "closing_balance": statement_data.closing_balance,
                    "total_credits": statement_data.total_credits,
                    "total_debits": statement_data.total_debits
                },
                "metadata": {
                    "confidence": statement_data.confidence,
                    "total_transactions": len(statement_data.transactions)
                }
            }

            logger.info(f"✅ Extracted: Bank={statement_data.bank_name}, CLABE={extracted_data['bank_info']['clabe']}, RFC={extracted_data['bank_info']['rfc_receptor']}")

            # STEP 2: Get company RFC for validation
            conn = psycopg2.connect(**POSTGRES_CONFIG)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT rfc
                FROM tenants
                WHERE id = %s
                LIMIT 1
            """, (current_user.tenant_id,))

            tenant_row = cursor.fetchone()
            company_rfc = tenant_row['rfc'] if tenant_row else None

            # STEP 3: Run account matching
            logger.info("🔍 Step 2/2: Running hierarchical account matching...")
            matcher = get_account_matcher(cursor)

            match_result = matcher.match_account(
                extracted_data,
                current_user.tenant_id,
                company_rfc
            )

            logger.info(f"✅ Match result: confidence={match_result.confidence}%, action={match_result.action}, method={match_result.match_method}")

            # STEP 4: Auto-create account if requested and no match found
            created_account = False
            if auto_create and match_result.action.value == "create_new":
                logger.info("🔨 Auto-creating payment account from extracted data...")

                bank_info = extracted_data.get("bank_info", {})
                summary = extracted_data.get("summary", {})

                # Determine account type and subtype
                account_type_raw = bank_info.get("account_type", "checking")
                tipo = TipoCuenta.BANCARIA

                if account_type_raw in ["credit_card"]:
                    subtipo = SubtipoCuenta.CREDITO
                else:
                    subtipo = SubtipoCuenta.DEBITO

                # Generate account name
                titular = bank_info.get("titular") or "Cuenta Auto-detectada"
                bank_name = bank_info.get("bank_name") or "Banco"
                last_4 = bank_info.get("last_4_digits") or ""
                account_name = f"{titular[:50]} - {bank_name} {last_4}".strip()

                # Create account request
                create_request = CreateUserPaymentAccountRequest(
                    nombre=account_name,
                    tipo=tipo,
                    subtipo=subtipo,
                    moneda="MXN",
                    saldo_inicial=summary.get("opening_balance", 0.0),
                    banco_nombre=bank_name,
                    clabe=bank_info.get("clabe"),
                    numero_cuenta=bank_info.get("account_number"),
                    numero_cuenta_enmascarado=f"****{last_4}" if last_4 else None,
                    numero_tarjeta=last_4 if last_4 else None
                )

                # Create account using service
                payment_account_service = UserPaymentAccountService()
                new_account = payment_account_service.create_account(
                    create_request,
                    current_user.id,
                    current_user.tenant_id
                )

                match_result.account_id = new_account.id
                created_account = True
                logger.info(f"✅ Auto-created account ID: {new_account.id} - {account_name}")

            cursor.close()
            conn.close()

            # Build response
            response = {
                "confidence": match_result.confidence,
                "action": match_result.action.value,
                "match_method": match_result.match_method,
                "extracted_data": extracted_data,
                "details": match_result.details,
                "created_account": created_account
            }

            if match_result.account_id:
                response["account_id"] = match_result.account_id

            if match_result.candidates:
                response["candidates"] = match_result.candidates

            return response

        finally:
            # Clean up temp file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    except ValueError as e:
        # RFC validation error or other validation errors
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in auto-detect: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detecting account: {str(e)}"
        )


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

        # ==========================================
        # 🔴 DETECCIÓN DE DUPLICADOS (File Hash)
        # ==========================================
        # Fix para Vulnerabilidad Mortal 2: Prevenir que el mismo archivo se suba múltiples veces
        import hashlib
        file_hash = hashlib.md5(file_content).hexdigest()

        # Verificar si el archivo ya fue subido antes para esta cuenta
        existing_statement = bank_statements_service.get_statement_by_file_hash(
            file_hash, account_id, current_user.tenant_id
        )

        if existing_statement:
            logger.warning(f"Duplicate file detected: hash={file_hash}, existing_statement_id={existing_statement.id}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Este archivo ya fue subido anteriormente (Statement ID: {existing_statement.id}, subido el {existing_statement.uploaded_at})"
            )

        # Crear request
        create_request = CreateBankStatementRequest(
            account_id=account_id,
            file_name=file.filename,
            file_type=file_type
        )

        # Crear statement en BD con file_hash
        statement = bank_statements_service.create_statement(
            create_request, current_user.id, current_user.tenant_id, file_content, file_hash=file_hash
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
            statement_id, current_user.tenant_id
        )

        # Obtener transacciones
        transactions = bank_statements_service.get_statement_transactions(
            statement_id, current_user.tenant_id
        )

        # Calcular resumen
        def get_value(obj):
            return obj.value if hasattr(obj, 'value') else obj

        summary = {
            "total_transactions": len(transactions),
            "total_credits": sum(txn.amount for txn in transactions if get_value(txn.transaction_type) == "credit"),
            "total_debits": sum(txn.amount for txn in transactions if get_value(txn.transaction_type) == "debit"),
            "period_start": statement.period_start,
            "period_end": statement.period_end,
            "parsing_status": get_value(statement.parsing_status)
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

        # 🔒 SECURITY: First verify ownership of the statement
        statement = bank_statements_service.get_statement(
            statement_id, current_user.tenant_id
        )

        # Validate that the statement belongs to the current user (not just the tenant)
        if hasattr(statement, 'user_id') and statement.user_id != current_user.id:
            logger.warning(
                f"SECURITY: User {current_user.email} (id={current_user.id}) "
                f"attempted to delete statement {statement_id} owned by user_id={statement.user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Not authorized to delete this statement"
            )

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
            statement_id, current_user.tenant_id
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
            current_user.id,
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
            balance_date = min((txn.transaction_date for txn in transactions if getattr(txn, 'transaction_date', None)), default=None)
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
            closing_date = max((txn.transaction_date for txn in transactions if getattr(txn, 'transaction_date', None)), default=None)
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


@router.get("/transactions/search")
async def search_transactions(
    transaction_class: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    is_recurring: Optional[bool] = None,
    vendor_normalized: Optional[str] = None,
    manually_corrected: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Buscar transacciones bancarias con filtros avanzados

    Filtros disponibles:
    - transaction_class: ingreso, gasto, transferencia
    - category: categoria principal (software_saas, transporte, etc.)
    - start_date/end_date: rango de fechas
    - min_amount/max_amount: rango de montos
    - is_recurring: solo gastos recurrentes
    - vendor_normalized: nombre normalizado del proveedor
    - manually_corrected: transacciones con clasificación manual

    Retorna lista de transacciones enriquecidas
    """
    try:
        logger.info(f"Searching transactions for user {current_user.email} with filters")

        transactions = bank_statements_service.search_transactions(
            tenant_id=current_user.tenant_id,
            transaction_class=transaction_class,
            category=category,
            start_date=start_date,
            end_date=end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            is_recurring=is_recurring,
            vendor_normalized=vendor_normalized,
            manually_corrected=manually_corrected
        )

        return transactions

    except Exception as e:
        logger.error(f"Error searching transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al buscar transacciones"
        )


@router.patch("/transactions/{transaction_id}/classify")
async def manually_classify_transaction(
    transaction_id: int,
    transaction_class: str,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    vendor_normalized: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    Clasificar manualmente una transacción

    Permite sobrescribir la clasificación de IA cuando hay incertidumbre
    Marca la transacción como manually_corrected para future training

    Parámetros:
    - transaction_id: ID de la transacción
    - transaction_class: ingreso, gasto, transferencia (requerido)
    - category: categoría opcional
    - subcategory: subcategoría opcional
    - vendor_normalized: nombre normalizado opcional
    """
    try:
        logger.info(f"Manual classification of transaction {transaction_id} by {current_user.email}")

        # Validar transaction_class
        valid_classes = ["ingreso", "gasto", "transferencia", "traspaso_interno"]
        if transaction_class not in valid_classes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"transaction_class debe ser uno de: {', '.join(valid_classes)}"
            )

        success = bank_statements_service.update_transaction_classification(
            transaction_id=transaction_id,
            tenant_id=current_user.tenant_id,
            transaction_class=transaction_class,
            category=category,
            subcategory=subcategory,
            vendor_normalized=vendor_normalized,
            manually_corrected=True
        )

        if success:
            return {
                "message": "Clasificación actualizada exitosamente",
                "transaction_id": transaction_id,
                "new_classification": {
                    "transaction_class": transaction_class,
                    "category": category,
                    "subcategory": subcategory,
                    "vendor_normalized": vendor_normalized
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transacción no encontrada"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating transaction classification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar clasificación"
        )


@router.get("/{statement_id}/pdf")
async def get_statement_pdf(
    statement_id: int,
    request: Request,
    token: Optional[str] = Query(None),
    current_user: User = Depends(get_user_from_token_or_query)
):
    """
    Obtener el archivo PDF original del estado de cuenta

    Parámetros:
    - statement_id: ID del estado de cuenta
    - token: Token de autenticación opcional (para iframes que no pueden enviar headers)

    Retorna el archivo PDF para visualización

    Nota: Acepta autenticación via Authorization header O via query parameter ?token=
    """
    try:
        from fastapi.responses import FileResponse

        logger.info(f"Getting PDF for statement {statement_id}")

        # Verificar que el statement existe y pertenece al usuario
        statement = bank_statements_service.get_statement(
            statement_id, current_user.tenant_id
        )

        # Verificar que el archivo existe
        if not statement.file_path or not Path(statement.file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Archivo PDF no encontrado"
            )

        # Verificar que es un PDF
        if statement.file_type not in [FileType.PDF, "pdf"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no es un PDF"
            )

        # Return PDF with inline disposition to display in iframe
        # instead of triggering download
        response = FileResponse(
            path=statement.file_path,
            media_type="application/pdf"
        )
        response.headers["Content-Disposition"] = f'inline; filename="{statement.file_name}"'
        return response

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estado de cuenta no encontrado"
        )
    except Exception as e:
        logger.error(f"Error getting PDF for statement {statement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener PDF"
        )


@router.get("/statements/list")
async def list_bank_statements(
    current_user: User = Depends(get_current_active_user)
):
    """
    Listar estados de cuenta disponibles con periodos calculados

    Retorna todos los estados de cuenta del usuario con:
    - Nombre del banco (extraído del file_path)
    - Periodo calculado desde las transacciones
    - Saldos de apertura y cierre
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import os

        # PostgreSQL connection config
        POSTGRES_CONFIG = {
            "host": os.getenv("POSTGRES_HOST", "db"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "database": os.getenv("POSTGRES_DB", "mcp_system"),
            "user": os.getenv("POSTGRES_USER", "mcp_user"),
            "password": os.getenv("POSTGRES_PASSWORD", "changeme")
        }

        conn = psycopg2.connect(**POSTGRES_CONFIG)

        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Query usando period_start y period_end de la tabla
            query = """
                SELECT
                    bs.id,
                    bs.file_name,
                    bs.file_path,
                    bs.opening_balance,
                    bs.closing_balance,
                    bs.total_credits,
                    bs.total_debits,
                    bs.uploaded_at,
                    bs.period_start,
                    bs.period_end,
                    COUNT(bt.id) as transaction_count
                FROM bank_statements bs
                LEFT JOIN bank_transactions bt ON bs.id = bt.statement_id
                WHERE bs.tenant_id = %s
                GROUP BY bs.id, bs.period_start, bs.period_end
                ORDER BY bs.period_start DESC NULLS LAST
            """

            cursor.execute(query, (current_user.tenant_id,))
            statements = cursor.fetchall()

            result = []
            for stmt in statements:
                # Extraer nombre del banco desde file_path
                bank_name = "Desconocido"
                if stmt['file_path']:
                    parts = stmt['file_path'].split('_')
                    if len(parts) >= 4:
                        bank_name = parts[3].capitalize()

                result.append({
                    "id": stmt['id'],
                    "bank_name": bank_name,
                    "file_name": stmt['file_name'],
                    "period_start": str(stmt['period_start']) if stmt['period_start'] else None,
                    "period_end": str(stmt['period_end']) if stmt['period_end'] else None,
                    "opening_balance": float(stmt['opening_balance']) if stmt['opening_balance'] else 0,
                    "closing_balance": float(stmt['closing_balance']) if stmt['closing_balance'] else 0,
                    "total_credits": float(stmt['total_credits']) if stmt['total_credits'] else 0,
                    "total_debits": float(stmt['total_debits']) if stmt['total_debits'] else 0,
                    "transaction_count": stmt['transaction_count'],
                    "uploaded_at": str(stmt['uploaded_at']) if stmt['uploaded_at'] else None
                })

            cursor.close()
            return result

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error listing bank statements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al listar estados de cuenta"
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


# ============================================================================
# FASE 1: SSE STREAMING ENDPOINTS
# ============================================================================

@router.post("/upload-with-progress")
async def upload_with_progress(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auto_create: bool = Form(True),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload bank statement with real-time progress streaming

    Returns task_id for SSE stream connection

    Usage:
        1. POST this endpoint with file
        2. Get {task_id}
        3. Connect to GET /stream/{task_id} with EventSource
        4. Watch progress events in real-time
    """
    import uuid
    from core.shared.progress_queue import get_progress_queue, ProgressEventType, ValidationLevel

    logger.info(f"Upload with progress for user: {current_user.email}")

    # Validate file
    if not file.filename:
        raise HTTPException(400, "Filename required")

    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ['.pdf', '.xlsx', '.xls', '.csv']:
        raise HTTPException(400, f"Unsupported file type: {file_extension}")

    # Read content
    file_content = await file.read()

    # Generate unique task ID
    task_id = str(uuid.uuid4())

    # Create task in progress queue
    progress_queue = get_progress_queue()
    progress_queue.create_task(task_id)

    # Launch background processing
    background_tasks.add_task(
        process_with_progress,
        task_id=task_id,
        file_content=file_content,
        filename=file.filename,
        file_type=file_extension,
        auto_create=auto_create,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id
    )

    logger.info(f"Created task {task_id} for user {current_user.email}")

    return {
        "task_id": task_id,
        "status": "processing",
        "stream_url": f"/bank-statements/stream/{task_id}"
    }


@router.get("/stream/{task_id}")
async def stream_progress(
    task_id: str,
    request: Request,
    token: str = None  # Query parameter for EventSource auth
):
    """
    Server-Sent Events stream for task progress

    Usage:
        const eventSource = new EventSource(`/api/bank-statements/stream/${task_id}?token=YOUR_TOKEN`);
        eventSource.onmessage = (e) => {
            const event = JSON.parse(e.data);
            console.log(event.message);
        };

    Note: EventSource doesn't support custom headers, so auth is via query param
    """
    import json
    from fastapi.responses import StreamingResponse
    from core.shared.progress_queue import get_progress_queue

    # Validate token from query parameter (EventSource can't send headers)
    if not token:
        raise HTTPException(401, "Token required in query parameter")

    try:
        from jose import jwt, JWTError
        from core.auth.jwt import SECRET_KEY, ALGORITHM

        # Decode and validate JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")  # JWT standard uses "sub" for user ID
        if not user_id:
            raise HTTPException(401, "Invalid token - no user_id in payload")
    except JWTError as e:
        logger.error(f"JWT validation failed: {e}")
        raise HTTPException(401, "Invalid or expired token")
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        raise HTTPException(401, "Token validation error")

    progress_queue = get_progress_queue()

    async def event_generator():
        """Generator que emite eventos SSE"""
        last_index = 0

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from task {task_id}")
                    break

                # Get new events
                events = await progress_queue.subscribe(task_id, from_index=last_index)

                # Emit each event
                for event in events:
                    event_data = {
                        "type": event.event_type.value,
                        "message": event.message,
                        "details": event.details,
                        "validation_level": event.validation_level.value,
                        "progress_percent": event.progress_percent,
                        "timestamp": event.timestamp.isoformat()
                    }

                    # SSE format
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_index += 1

                # If task completed, close stream
                if progress_queue.is_task_completed(task_id):
                    logger.info(f"Task {task_id} completed, closing stream")
                    break

                # Wait before next poll
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            error_data = {
                "type": "error",
                "message": str(e),
                "validation_level": "error"
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


# Background processor
async def process_with_progress(
    task_id: str,
    file_content: bytes,
    filename: str,
    file_type: str,
    auto_create: bool,
    user_id: int,
    tenant_id: int
):
    """
    Process bank statement in background with progress updates

    Publishes events to ProgressQueue for SSE streaming
    """
    import tempfile
    from core.shared.progress_queue import get_progress_queue, ProgressEventType, ValidationLevel
    from core.ai_pipeline.parsers.ai_bank_statement_parser import get_ai_parser
    from core.reconciliation.bank.account_matcher import get_account_matcher
    from core.shared.statement_cache import get_statement_cache

    progress = get_progress_queue()
    cache = get_statement_cache()

    try:
        # STEP 1: File received
        progress.publish(
            task_id,
            ProgressEventType.UPLOAD,
            "📄 Archivo recibido",
            details={
                "filename": filename,
                "size_kb": round(len(file_content) / 1024, 2)
            },
            validation_level=ValidationLevel.SUCCESS
        )

        # STEP 1.5: Check cache for duplicate PDF (FASE A: Idempotencia)
        file_hash = cache.compute_file_hash(file_content)
        cached_result = cache.get(file_hash, tenant_id)

        if cached_result:
            # Cache HIT - retornar resultado inmediatamente
            logger.info(
                f"💰 CACHE HIT - Skipping Gemini processing for duplicate PDF "
                f"(hash: {file_hash[:8]}, statement_id: {cached_result.statement_id})"
            )

            progress.publish(
                task_id,
                ProgressEventType.UPLOAD,
                f"♻️ PDF ya procesado anteriormente ({cached_result.bank_name})",
                details={
                    "cached": True,
                    "original_processing_time": str(cached_result.processed_at),
                    "statement_id": cached_result.statement_id,
                    "account_id": cached_result.account_id,
                    "transactions": cached_result.transactions_count,
                    "cost_saved": "~$0.03 USD (Gemini Vision call avoided)"
                },
                validation_level=ValidationLevel.SUCCESS,
                progress_percent=50
            )

            # Publicar evento de completado con datos cacheados
            progress.publish(
                task_id,
                ProgressEventType.COMPLETE,
                "✅ Procesamiento completado (desde caché)",
                details={
                    "statement_id": cached_result.statement_id,
                    "account_id": cached_result.account_id,
                    "transactions": cached_result.transactions_count,
                    "cached": True
                },
                validation_level=ValidationLevel.SUCCESS,
                progress_percent=100
            )

            return  # Salir temprano, no procesar de nuevo

        # Cache MISS - continuar con procesamiento normal
        logger.info(
            f"🔍 Cache MISS - Processing new PDF (hash: {file_hash[:8]})"
        )

        # STEP 2: Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_type) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        # ==========================================
        # STEP 2.5: RFC VALIDATION FIRST (FASE B)
        # ==========================================
        # Quick RFC extraction BEFORE expensive Gemini Vision call
        # Cost: ~$0.001 USD (Gemini Flash) vs $0.03 USD (full Vision)
        # Savings: 97% if RFC doesn't match
        progress.publish(
            task_id,
            ProgressEventType.RFC_VALIDATION,
            "🔍 Validando RFC del documento...",
            validation_level=ValidationLevel.INFO,
            progress_percent=15
        )

        # Get tenant RFC from database
        from psycopg2.extras import RealDictCursor
        import psycopg2
        from core.reconciliation.bank.bank_statements_models import POSTGRES_CONFIG

        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute("SELECT rfc FROM tenants WHERE id = %s", (tenant_id,))
            tenant_row = cursor.fetchone()
            company_rfc = tenant_row['rfc'] if tenant_row else None

            # Quick RFC extraction (cheap Gemini Flash call)
            # FASE B: RFC Validation First
            ai_parser = get_ai_parser()
            statement_rfc = ai_parser.extract_rfc_only(tmp_path)

            # RFC VALIDATION GATE
            if statement_rfc and company_rfc and statement_rfc != company_rfc:
                # CRITICAL MISMATCH - STOP PROCESSING
                logger.warning(
                    f"❌ RFC MISMATCH - Stopping processing early\n"
                    f"   PDF RFC: {statement_rfc}\n"
                    f"   Company RFC: {company_rfc}\n"
                    f"   Cost saved: $0.029 USD (full parsing avoided)"
                )

                progress.publish(
                    task_id,
                    ProgressEventType.RFC_VALIDATION,
                    "❌ RFC no coincide - Procesamiento detenido",
                    details={
                        "pdf_rfc": statement_rfc,
                        "company_rfc": company_rfc,
                        "cost_saved": "$0.029 USD (full parsing avoided)",
                        "recommendation": "Verifica que subiste el PDF correcto"
                    },
                    validation_level=ValidationLevel.ERROR
                )

                progress.publish(
                    task_id,
                    ProgressEventType.ERROR,
                    f"RFC del PDF ({statement_rfc}) no coincide con RFC de tu empresa ({company_rfc})",
                    validation_level=ValidationLevel.ERROR
                )

                cursor.close()
                conn.close()
                os.unlink(tmp_path)  # Cleanup temp file
                return  # STOP HERE - Don't waste Gemini Vision call

            elif statement_rfc and company_rfc and statement_rfc == company_rfc:
                logger.info(f"✅ RFC validation passed: {statement_rfc}")
                progress.publish(
                    task_id,
                    ProgressEventType.RFC_VALIDATION,
                    "✓ RFC validado - Continuando procesamiento",
                    details={"rfc": statement_rfc},
                    validation_level=ValidationLevel.SUCCESS,
                    progress_percent=20
                )

            elif statement_rfc == "XAXX010101000":
                # RFC genérico - continuar con warning
                logger.warning(f"⚠️ Generic RFC detected: {statement_rfc}")
                progress.publish(
                    task_id,
                    ProgressEventType.RFC_VALIDATION,
                    "⚠ RFC genérico detectado - Continuando con precaución",
                    details={
                        "rfc": statement_rfc,
                        "warning": "RFC genérico (puede ser PDF de prueba)"
                    },
                    validation_level=ValidationLevel.WARNING,
                    progress_percent=20
                )

            else:
                # RFC no encontrado o no coincide exactamente - continuar con warning
                logger.warning(f"⚠️ RFC extraction inconclusive - continuing with full parsing")
                progress.publish(
                    task_id,
                    ProgressEventType.RFC_VALIDATION,
                    "⚠ RFC no detectado - Continuando con análisis completo",
                    details={
                        "statement_rfc": statement_rfc,
                        "company_rfc": company_rfc
                    },
                    validation_level=ValidationLevel.WARNING,
                    progress_percent=20
                )

        finally:
            cursor.close()
            conn.close()

        # STEP 3: Gemini analysis (ONLY if RFC passed or inconclusive)
        progress.publish(
            task_id,
            ProgressEventType.ANALYSIS,
            "🔍 Analizando PDF con Gemini Vision...",
            validation_level=ValidationLevel.INFO,
            progress_percent=30
        )

        # Run blocking call in thread to avoid blocking event loop
        import asyncio
        statement_data = await asyncio.to_thread(ai_parser.parse_pdf, tmp_path)

        # STEP 4: Metadata extracted
        bank_name = statement_data.bank_name
        clabe = statement_data.metadata.get("clabe")
        last_4 = statement_data.account_number[-4:] if statement_data.account_number else None

        progress.publish(
            task_id,
            ProgressEventType.METADATA,
            f"✓ Metadatos extraídos: {bank_name}",
            details={
                "banco": bank_name,
                "clabe": clabe,
                "last_4": last_4,
                "transactions": len(statement_data.transactions)
            },
            validation_level=ValidationLevel.SUCCESS,
            progress_percent=40
        )

        # STEP 4.5: RFC Validation (FASE 2)
        from psycopg2.extras import RealDictCursor
        import psycopg2
        from core.reconciliation.bank.bank_statements_models import POSTGRES_CONFIG

        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get tenant RFC
        cursor.execute("SELECT rfc FROM tenants WHERE id = %s", (tenant_id,))
        tenant_row = cursor.fetchone()
        company_rfc = tenant_row['rfc'] if tenant_row else None

        # Extract RFC from statement metadata
        statement_rfc = statement_data.metadata.get("rfc") or statement_data.metadata.get("RFC")

        # Validate RFC
        if statement_rfc == "XAXX010101000":
            progress.publish(
                task_id,
                ProgressEventType.RFC_VALIDATION,
                "⚠ RFC genérico detectado",
                details={
                    "rfc": statement_rfc,
                    "issue": "Este es un RFC de prueba/genérico",
                    "recommendation": "Verifica que el PDF sea correcto"
                },
                validation_level=ValidationLevel.WARNING,
                progress_percent=45
            )
        elif statement_rfc and company_rfc and statement_rfc != company_rfc:
            progress.publish(
                task_id,
                ProgressEventType.RFC_VALIDATION,
                "⚠ RFC no coincide con tu empresa",
                details={
                    "pdf_rfc": statement_rfc,
                    "company_rfc": company_rfc,
                    "issue": "El RFC del PDF no pertenece a tu empresa",
                    "recommendation": "¿Subiste el PDF correcto?"
                },
                validation_level=ValidationLevel.WARNING,
                progress_percent=45
            )
        elif statement_rfc and company_rfc and statement_rfc == company_rfc:
            progress.publish(
                task_id,
                ProgressEventType.RFC_VALIDATION,
                "✓ RFC validado correctamente",
                details={
                    "rfc": statement_rfc,
                    "status": "RFC coincide con tu empresa"
                },
                validation_level=ValidationLevel.SUCCESS,
                progress_percent=45
            )
        elif not statement_rfc:
            progress.publish(
                task_id,
                ProgressEventType.RFC_VALIDATION,
                "⚠ RFC no encontrado en el PDF",
                details={
                    "issue": "El PDF no contiene información de RFC",
                    "recommendation": "Verifica que sea un estado de cuenta válido"
                },
                validation_level=ValidationLevel.WARNING,
                progress_percent=45
            )

        # STEP 5: Account matching
        progress.publish(
            task_id,
            ProgressEventType.MATCHING,
            "🔎 Buscando cuenta similar...",
            validation_level=ValidationLevel.INFO,
            progress_percent=50
        )

        # Get matcher and match account (reusing connection from RFC validation)
        matcher = get_account_matcher(cursor)
        extracted_data = {
            "bank_info": {
                "clabe": clabe,
                "bank_name": bank_name,
                "last_4_digits": last_4,
                "account_number": statement_data.account_number
            }
        }

        match_result = matcher.match_account(extracted_data, tenant_id, company_rfc)

        # STEP 6: Create or match account
        if match_result.action.value == "create_new" and auto_create:
            progress.publish(
                task_id,
                ProgressEventType.ACCOUNT_CREATE,
                "🔨 Creando cuenta nueva...",
                details={"banco": bank_name, "last_4": last_4},
                validation_level=ValidationLevel.WARNING,
                progress_percent=60
            )

            # Create account
            payment_account_service = UserPaymentAccountService()
            create_request = CreateUserPaymentAccountRequest(
                nombre=f"{bank_name} •••• {last_4}",
                tipo=TipoCuenta.BANCARIA,
                subtipo=SubtipoCuenta.DEBITO,
                moneda="MXN",
                saldo_inicial=statement_data.opening_balance or 0.0,
                banco_nombre=bank_name,
                clabe=clabe,
                numero_cuenta=statement_data.account_number
            )

            new_account = payment_account_service.create_account(
                create_request,
                user_id,
                tenant_id
            )

            account_id = new_account.id

            progress.publish(
                task_id,
                ProgressEventType.ACCOUNT_CREATED,
                f"✓ Cuenta creada: {new_account.nombre}",
                details={"account_id": account_id},
                validation_level=ValidationLevel.SUCCESS,
                progress_percent=70
            )
        else:
            account_id = match_result.account_id
            progress.publish(
                task_id,
                ProgressEventType.ACCOUNT_MATCHED,
                f"✓ Cuenta encontrada (ID: {account_id})",
                details={"account_id": account_id, "confidence": match_result.confidence},
                validation_level=ValidationLevel.SUCCESS,
                progress_percent=70
            )

        # STEP 7: Save statement
        progress.publish(
            task_id,
            ProgressEventType.SAVING,
            "💾 Guardando estado de cuenta...",
            validation_level=ValidationLevel.INFO,
            progress_percent=80
        )

        statement = bank_statements_service.create_statement(
            CreateBankStatementRequest(
                account_id=account_id,
                file_name=filename,
                file_type=FileType.PDF
            ),
            user_id,
            tenant_id,
            file_content
        )

        # STEP 8: Parse transactions
        total_txns = len(statement_data.transactions)
        progress.publish(
            task_id,
            ProgressEventType.PARSING,
            f"📊 Procesando {total_txns} transacciones...",
            details={"total": total_txns},
            validation_level=ValidationLevel.INFO,
            progress_percent=85
        )

        # Use TransactionIngestionService for safe, validated transaction saving
        from core.services.transaction_ingestion_service import get_transaction_ingestion_service

        ingestion_service = get_transaction_ingestion_service()
        ingestion_result = ingestion_service.ingest(
            statement_id=statement.id,
            account_id=account_id,
            tenant_id=tenant_id,
            transactions=statement_data.transactions,
            metadata={
                'model': statement_data.metadata.get('model', 'gemini-2.0-flash-exp'),
                'confidence': statement_data.confidence
            }
        )

        # Log ingestion results for monitoring
        if ingestion_result.skipped_duplicates > 0:
            logger.info(
                f"Skipped {ingestion_result.skipped_duplicates} duplicate transactions "
                f"for statement {statement.id}"
            )

        progress.publish(
            task_id,
            ProgressEventType.PARSING,
            f"📊 Transacciones guardadas: {total_txns}",
            validation_level=ValidationLevel.INFO,
            progress_percent=90
        )

        # STEP 9: Store in cache (FASE A: Idempotencia)
        cache.set(
            file_hash=file_hash,
            statement_id=statement.id,
            account_id=account_id,
            transactions_count=total_txns,
            bank_name=bank_name,
            tenant_id=tenant_id,
            user_id=user_id,
            metadata={
                "clabe": clabe,
                "last_4": last_4,
                "rfc": statement_rfc
            }
        )

        # STEP 10: Complete
        progress.publish(
            task_id,
            ProgressEventType.COMPLETE,
            "✅ Procesamiento completado",
            details={
                "statement_id": statement.id,
                "account_id": account_id,
                "transactions": total_txns
            },
            validation_level=ValidationLevel.SUCCESS,
            progress_percent=100
        )

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
        progress.publish(
            task_id,
            ProgressEventType.ERROR,
            f"❌ Error: {str(e)}",
            details={"error": str(e)},
            validation_level=ValidationLevel.ERROR
        )

    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
