"""
Modelos Pydantic para gestión de estados de cuenta bancarios
Incluye parsing de archivos PDF/Excel y extracción de transacciones
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationInfo
import sqlite3
import logging
import os
import json
import hashlib
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class FileType(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"


class ParsingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TransactionType(str, Enum):
    CREDIT = "credit"  # Abono/Ingreso
    DEBIT = "debit"    # Cargo/Gasto
    TRANSFER = "transfer"  # Transferencia


class MovementKind(str, Enum):
    """Clasificación de negocio para los movimientos bancarios"""

    INGRESO = "Ingreso"
    GASTO = "Gasto"
    TRANSFERENCIA = "Transferencia"


TRANSFER_KEYWORDS = [
    "traspaso",
    "transferencia",
    "mov.banc",
    "transfer",
    "pago tarjeta",
    "pago tarjeta de credito",
    "card payment",
    "interbank",
    "spei propio",
    "cta propia",
    "propia",
    "pagotarjeta",
    "balance inicial",
    "saldo inicial",
    "saldo anterior",
    "payment thank you",
    "pago total",
    "pago mensual",
    "payment received",
]

SKIP_TRANSACTION_KEYWORDS = [
    "balance inicial",
    "saldo anterior",
    "saldo final",
    "saldo actual",
    "saldo promedio",
]


def infer_movement_kind(
    transaction_type: Union[TransactionType, str],
    description: Optional[str] = None,
) -> MovementKind:
    """Determina si el movimiento es Ingreso, Gasto o Transferencia."""

    description = (description or "").lower()

    if isinstance(transaction_type, str):
        try:
            transaction_type = TransactionType(transaction_type)
        except ValueError:
            transaction_type = TransactionType.DEBIT

    if any(keyword in description for keyword in TRANSFER_KEYWORDS):
        return MovementKind.TRANSFERENCIA

    if transaction_type == TransactionType.CREDIT:
        return MovementKind.INGRESO

    return MovementKind.GASTO


def should_skip_transaction(description: Optional[str]) -> bool:
    """Determina si una transacción detectada corresponde a un saldo."""
    desc_lower = (description or "").lower().strip()
    if not desc_lower:
        return False

    if desc_lower.isdigit() or desc_lower in {"|", "-", "--"}:
        return True

    desc_lower = desc_lower.replace('()', '').strip()

    return any(keyword in desc_lower for keyword in SKIP_TRANSACTION_KEYWORDS)


def normalize_description(description: Optional[str]) -> str:
    if not description:
        return ""

    desc = description.lower()
    desc = re.sub(r'\(\s*\)', '', desc)
    desc = re.sub(r'\s+', ' ', desc)
    desc = desc.strip()

    if desc in {"|", "", "-", "--"}:
        return ""

    return desc


def _infer_category_from_description(
    description: Optional[str],
    movement_kind: MovementKind,
    amount: float
) -> Tuple[str, float]:
    """Inferir categoría heurística según la descripción del movimiento."""

    desc = (description or '').upper()

    if not desc:
        fallback = {
            MovementKind.INGRESO: 'Ingresos',
            MovementKind.TRANSFERENCIA: 'Transferencias',
        }.get(movement_kind, 'Gastos generales')
        return fallback, 0.4

    keyword_map = [
        (('COMISION', 'MANEJO DE CUENTA'), 'Comisiones bancarias'),
        (('IVA COMISION',), 'Impuestos bancarios'),
        (('INTERESES GANADOS', 'INTERES'), 'Intereses bancarios'),
        (('DEPOSITO SPEI', 'SPEI'), 'Transferencias recibidas'),
        (('TRASPASO', 'TRANSFERENCIA'), 'Transferencias internas'),
        (('MERCADO PAGO', 'STRIPE', 'PAYPAL'), 'Pagos a proveedores'),
        (('OPENAI', 'CHATGPT', 'GOOGLE', 'NETFLIX', 'SPOTIFY', 'APPLE'), 'Servicios digitales'),
        (('GASOLINERA', 'PEMEX', 'GASOL'), 'Combustible'),
        (('OXXO', 'WALMART', 'COSTCO'), 'Compras generales'),
    ]

    for keywords, category in keyword_map:
        if any(keyword in desc for keyword in keywords):
            return category, 0.9

    if movement_kind == MovementKind.TRANSFERENCIA:
        return 'Transferencias', 0.7
    if movement_kind == MovementKind.INGRESO:
        if amount >= 50000:
            return 'Ingresos extraordinarios', 0.6
        return 'Ingresos', 0.6

    if 'IVA' in desc:
        return 'Impuestos', 0.6
    if 'FACTURA' in desc or 'PROVEEDOR' in desc:
        return 'Pagos a proveedores', 0.6

    return 'Gastos generales', 0.3


def _suggest_category_with_llm(description: str, amount: float) -> Optional[Tuple[str, float]]:
    """Placeholder para futura integración con LLM."""
    return None


class BankStatement(BaseModel):
    id: Optional[int] = None
    account_id: int
    user_id: int
    tenant_id: int
    file_name: str
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    file_type: FileType
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    opening_balance: float = 0.0
    closing_balance: float = 0.0
    total_credits: float = 0.0
    total_debits: float = 0.0
    transaction_count: int = 0
    parsing_status: ParsingStatus = ParsingStatus.PENDING
    parsing_error: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    parsed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


class BankTransaction(BaseModel):
    id: Optional[int] = None
    statement_id: Optional[int] = None
    account_id: int
    user_id: int
    tenant_id: int
    date: date
    description: str
    amount: float
    transaction_type: TransactionType
    category: Optional[str] = None
    reference: Optional[str] = None
    balance_after: Optional[float] = None
    is_deductible: bool = False
    status: str = "unmatched"  # matched/unmatched
    matched_expense_id: Optional[int] = None
    confidence: float = 0.0
    raw_data: Optional[str] = None
    created_at: Optional[datetime] = None
    movement_kind: MovementKind = MovementKind.GASTO
    context_used: Optional[str] = None
    ai_model: Optional[str] = None
    context_confidence: Optional[float] = None
    context_version: Optional[int] = None
    display_name: Optional[str] = None

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v, info: ValidationInfo):
        if v == 0:
            description = ''
            if info.data:
                description = (info.data.get('description') or '').lower()
            if any(keyword in description for keyword in ('balance inicial', 'saldo inicial')):
                return v
            raise ValueError("Amount cannot be zero")
        return v
    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


class CreateBankStatementRequest(BaseModel):
    account_id: int
    file_name: str
    file_type: FileType
    period_start: Optional[date] = None
    period_end: Optional[date] = None

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


class BankStatementResponse(BaseModel):
    statement: BankStatement
    transactions: List[BankTransaction] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


class BankStatementSummary(BaseModel):
    id: int
    file_name: str
    account_name: str
    account_type: str
    banco_nombre: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    transaction_count: int
    total_credits: float
    total_debits: float
    parsing_status: ParsingStatus
    uploaded_at: datetime
    parsed_transactions: int = 0

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


class BankStatementsService:
    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path
        self.upload_dir = Path("uploads/statements")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._bank_movement_columns: set[str] = set()
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Garantiza que la tabla bank_movements tenga las columnas requeridas."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(bank_movements)")
                columns = {row[1] for row in cursor.fetchall()}
                self._bank_movement_columns = columns

                if columns:
                    missing_context_columns = [
                        col
                        for col in [
                            "context_used",
                            "ai_model",
                            "context_confidence",
                            "context_version",
                        ]
                        if col not in columns
                    ]
                    if missing_context_columns:
                        logger.debug(
                            "bank_movements missing contextual columns: %s",
                            ", ".join(missing_context_columns),
                        )

                if "movement_kind" not in columns:
                    cursor.execute(
                        "ALTER TABLE bank_movements ADD COLUMN movement_kind TEXT DEFAULT 'Gasto'"
                    )
                    cursor.execute(
                        """
                        UPDATE bank_movements
                        SET movement_kind = CASE
                            WHEN transaction_type = 'credit' THEN 'Ingreso'
                            WHEN transaction_type = 'transfer' THEN 'Transferencia'
                            ELSE 'Gasto'
                        END
                        WHERE movement_kind IS NULL OR movement_kind = ''
                        """
                    )
                conn.commit()

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='bank_statements'"
                )
                has_bank_statements = cursor.fetchone() is not None

                if has_bank_statements:
                    cursor.execute("PRAGMA table_info(bank_statements)")
                    statement_columns = {row[1] for row in cursor.fetchall()}

                    if "file_hash" not in statement_columns:
                        cursor.execute(
                            "ALTER TABLE bank_statements ADD COLUMN file_hash TEXT"
                        )
                        conn.commit()
        except sqlite3.OperationalError as exc:
            logger.warning(f"No se pudo asegurar el esquema de bank_movements: {exc}")
        except Exception as exc:
            logger.error(f"Error asegurando esquema de bank_movements: {exc}")

    def create_statement(
        self,
        request: CreateBankStatementRequest,
        user_id: int,
        tenant_id: int,
        file_content: bytes
    ) -> BankStatement:
        """Crear nuevo statement y guardar archivo"""
        try:
            # Determinar banco para mejorar detección posterior
            bank_slug = ""
            try:
                with self._get_connection() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT banco_nombre FROM user_payment_accounts WHERE id = ?",
                        (request.account_id,)
                    )
                    row = cursor.fetchone()
                    if row and row['banco_nombre']:
                        slug = re.sub(r'[^a-z0-9]+', '-', row['banco_nombre'].lower())
                        bank_slug = slug.strip('-')
            except Exception as exc:  # pragma: no cover - best effort hint
                logger.debug("Could not fetch bank name for statement upload: %s", exc)

            # Generar path único para el archivo (incluir banco para hints de parsing)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{user_id}_{timestamp}_{request.file_name}"
            if bank_slug:
                safe_filename = f"{user_id}_{timestamp}_{bank_slug}_{request.file_name}"
            file_path = self.upload_dir / safe_filename

            # Guardar archivo
            with open(file_path, 'wb') as f:
                f.write(file_content)

            file_size = len(file_content)
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Crear registro en BD
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Verificar si el mismo archivo ya existe para esta cuenta específica
                cursor.execute(
                    """
                    SELECT id FROM bank_statements
                    WHERE account_id = ? AND user_id = ? AND tenant_id = ? AND file_hash = ?
                    """,
                    (request.account_id, user_id, tenant_id, file_hash)
                )

                existing_same_account = cursor.fetchone()
                if existing_same_account:
                    raise ValueError("Este estado de cuenta ya fue subido previamente para esta cuenta")

                # Verificar si el mismo archivo existe en otras cuentas (para logging/advertencia)
                cursor.execute(
                    """
                    SELECT bs.id, pa.nombre, pa.banco_nombre FROM bank_statements bs
                    LEFT JOIN user_payment_accounts pa ON bs.account_id = pa.id
                    WHERE bs.user_id = ? AND bs.tenant_id = ? AND bs.file_hash = ? AND bs.account_id != ?
                    """,
                    (user_id, tenant_id, file_hash, request.account_id)
                )

                existing_other_accounts = cursor.fetchall()
                if existing_other_accounts:
                    other_accounts = ", ".join([f"{row[1]} ({row[2] or 'banco desconocido'})" for row in existing_other_accounts])
                    logger.warning(f"⚠️ El mismo archivo ya fue procesado para otras cuentas: {other_accounts}")
                    logger.info("ℹ️ Permitiendo el upload pero el resultado puede ser incompatible si los bancos no coinciden")

                cursor.execute("""
                    INSERT INTO bank_statements (
                        account_id, user_id, tenant_id, file_name, file_path,
                        file_hash, file_size, file_type, period_start, period_end,
                        parsing_status, uploaded_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    request.account_id, user_id, tenant_id, request.file_name,
                    str(file_path), file_hash, file_size, request.file_type.value if hasattr(request.file_type, 'value') else request.file_type,
                    request.period_start, request.period_end,
                    ParsingStatus.PENDING.value, datetime.now(), datetime.now()
                ))

                statement_id = cursor.lastrowid
                conn.commit()

                # Obtener statement creado
                return self.get_statement(statement_id, user_id, tenant_id)

        except Exception as e:
            logger.error(f"Error creating statement: {e}")
            # Limpiar archivo si hubo error
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink()
            raise

    def get_statement(self, statement_id: int, user_id: int, tenant_id: int) -> BankStatement:
        """Obtener statement por ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM bank_statements
                WHERE id = ? AND user_id = ? AND tenant_id = ?
            """, (statement_id, user_id, tenant_id))

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Statement {statement_id} not found")

            return self._row_to_statement(row)

    def get_user_statements(self, user_id: int, tenant_id: int, account_id: Optional[int] = None) -> List[BankStatementSummary]:
        """Obtener statements del usuario con resumen"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            where_clause = "WHERE bs.user_id = ? AND bs.tenant_id = ?"
            params = [user_id, tenant_id]

            if account_id:
                where_clause += " AND bs.account_id = ?"
                params.append(account_id)

            cursor.execute(f"""
                SELECT * FROM bank_statements_summary
                {where_clause}
                ORDER BY uploaded_at DESC
            """, params)

            return [self._row_to_summary(row) for row in cursor.fetchall()]

    def get_statement_transactions(self, statement_id: int, user_id: int, tenant_id: int) -> List[BankTransaction]:
        """Obtener transacciones de un statement"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT bm.* FROM bank_movements bm
                JOIN bank_statements bs ON bm.statement_id = bs.id
                WHERE bs.id = ? AND bs.user_id = ? AND bs.tenant_id = ?
                ORDER BY bm.date DESC, bm.id DESC
            """, (statement_id, user_id, tenant_id))

            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def update_parsing_status(
        self,
        statement_id: int,
        status: ParsingStatus,
        error: Optional[str] = None,
        summary_data: Optional[Dict[str, Any]] = None
    ):
        """Actualizar estado de parsing"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            parsed_at = datetime.now() if status == ParsingStatus.COMPLETED else None

            # Actualizar campos de resumen si se proporcionan
            if summary_data:
                cursor.execute("""
                    UPDATE bank_statements
                    SET parsing_status = ?, parsing_error = ?, parsed_at = ?,
                        total_credits = ?, total_debits = ?, transaction_count = ?,
                        opening_balance = ?, closing_balance = ?,
                        period_start = ?, period_end = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    status.value, error, parsed_at,
                    summary_data.get('total_credits', 0),
                    summary_data.get('total_debits', 0),
                    summary_data.get('transaction_count', 0),
                    summary_data.get('opening_balance', 0),
                    summary_data.get('closing_balance', 0),
                    summary_data.get('period_start'),
                    summary_data.get('period_end'),
                    datetime.now(), statement_id
                ))
            else:
                cursor.execute("""
                    UPDATE bank_statements
                    SET parsing_status = ?, parsing_error = ?, parsed_at = ?, updated_at = ?
                    WHERE id = ?
                """, (status.value, error, parsed_at, datetime.now(), statement_id))

            conn.commit()

    def clear_statement_transactions(self, statement_id: int):
        """Eliminar movimientos asociados a un statement antes de reprocesar."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM bank_movements WHERE statement_id = ?",
                (statement_id,)
            )
            conn.commit()

    def add_transactions(self, statement_id: int, transactions: List[BankTransaction]):
        """Agregar transacciones parseadas a un statement"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            seen_keys = set()

            for txn in transactions:
                account_id_str = str(txn.account_id)
                txn_user_id = txn.user_id if txn.user_id is not None else 0
                movement_kind_value = (
                    txn.movement_kind.value if hasattr(txn.movement_kind, 'value') else txn.movement_kind
                )
                if not movement_kind_value:
                    movement_kind_value = MovementKind.GASTO.value

                normalized_description = normalize_description(txn.description)

                category_value = txn.category
                category_confidence = 1.0 if category_value else 0.0
                if not category_value:
                    category_value, category_confidence = _infer_category_from_description(
                        txn.description,
                        txn.movement_kind if isinstance(txn.movement_kind, MovementKind) else infer_movement_kind(
                            txn.transaction_type,
                            txn.description,
                        ),
                        txn.amount or 0.0,
                    )

                llm_suggestion = None
                if category_confidence < 0.6:
                    llm_suggestion = _suggest_category_with_llm(normalized_description, txn.amount or 0.0)
                    if llm_suggestion:
                        category_value, category_confidence = llm_suggestion

                txn_key = (
                    txn.date.isoformat() if isinstance(txn.date, date) else str(txn.date),
                    round(float(txn.amount or 0.0), 2),
                    txn.transaction_type.value if hasattr(txn.transaction_type, 'value') else txn.transaction_type,
                    movement_kind_value,
                    normalized_description,
                )

                if txn_key in seen_keys:
                    logger.debug("Skipping duplicate transaction in batch: %s", txn_key)
                    continue

                seen_keys.add(txn_key)

                cursor.execute(
                    """
                    SELECT id, reference FROM bank_movements
                    WHERE account_id = ? AND user_id = ? AND tenant_id = ?
                      AND date = ? AND ABS(amount - ?) < 0.01
                      AND COALESCE(cleaned_description, '') = ?
                      AND COALESCE(transaction_type, '') = ?
                      AND COALESCE(movement_kind, '') = ?
                    LIMIT 1
                    """,
                    (
                        account_id_str,
                        txn_user_id,
                        txn.tenant_id,
                        txn.date,
                        txn.amount,
                        normalized_description,
                        txn.transaction_type.value if hasattr(txn.transaction_type, 'value') else txn.transaction_type,
                        movement_kind_value,
                    )
                )

                existing = cursor.fetchone()
                if existing:
                    existing_id, existing_reference = existing
                    if txn.reference and not existing_reference:
                        cursor.execute(
                            "UPDATE bank_movements SET reference = ? WHERE id = ?",
                            (txn.reference, existing_id)
                        )
                    logger.info(
                        "⚠️ Movimiento duplicado detectado para cuenta %s el %s - se omite inserción",
                        txn.account_id,
                        txn.date,
                    )
                    continue

                base_columns = [
                    "statement_id",
                    "account",
                    "amount",
                    "description",
                    "cleaned_description",
                    "date",
                    "transaction_type",
                    "category",
                    "category_auto",
                    "category_confidence",
                    "reference",
                    "balance_after",
                    "raw_data",
                    "confidence",
                    "confidence_score",
                    "tenant_id",
                    "created_at",
                    "processing_status",
                    "bank_account_id",
                    "account_id",
                    "user_id",
                    "movement_kind",
                ]

                base_values = [
                    statement_id,
                    account_id_str,
                    txn.amount,
                    txn.description,
                    normalized_description,
                    txn.date,
                    txn.transaction_type.value if hasattr(txn.transaction_type, 'value') else txn.transaction_type,
                    category_value,
                    category_value,
                    category_confidence,
                    txn.reference,
                    txn.balance_after,
                    txn.raw_data,
                    txn.confidence if txn.confidence is not None else 0.0,
                    txn.confidence if txn.confidence is not None else 0.0,
                    txn.tenant_id,
                    datetime.now(),
                    'pending',
                    account_id_str,
                    txn.account_id,
                    txn_user_id,
                    movement_kind_value,
                ]

                optional_columns: List[str] = []
                optional_values: List[Any] = []

                if "context_used" in self._bank_movement_columns:
                    context_value = txn.context_used
                    if isinstance(context_value, (dict, list)):
                        context_value = json.dumps(context_value, ensure_ascii=False)
                    optional_columns.append("context_used")
                    optional_values.append(context_value)

                if "ai_model" in self._bank_movement_columns:
                    optional_columns.append("ai_model")
                    optional_values.append(txn.ai_model)

                if "context_confidence" in self._bank_movement_columns:
                    optional_columns.append("context_confidence")
                    optional_values.append(txn.context_confidence)

                if "context_version" in self._bank_movement_columns:
                    optional_columns.append("context_version")
                    optional_values.append(txn.context_version)

                if "display_name" in self._bank_movement_columns:
                    optional_columns.append("display_name")
                    optional_values.append(
                        txn.display_name or txn.description
                    )

                columns_sql = ", ".join(base_columns + optional_columns)
                placeholders = ", ".join(["?"] * (len(base_values) + len(optional_values)))

                cursor.execute(
                    f"INSERT INTO bank_movements ({columns_sql}) VALUES ({placeholders})",
                    base_values + optional_values,
                )

            conn.commit()

    def upsert_initial_balance(
        self,
        statement_id: int,
        account_id: int,
        user_id: int,
        tenant_id: int,
        opening_balance: Optional[float],
        balance_date: Optional[date],
        ai_model: Optional[str] = None,
        confidence: Optional[float] = None,
        display_name: Optional[str] = "Balance inicial",
    ) -> None:
        """Ensure a balance inicial row exists for a statement."""

        if opening_balance is None:
            return

        balance_date = balance_date or date.today()
        ai_model = ai_model or "gemini-2.5-flash"
        confidence_value = confidence if confidence is not None else 1.0
        display_name = (display_name or "Balance inicial").strip() or "Balance inicial"
        account_str = str(account_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM bank_movements
                WHERE statement_id = ? AND COALESCE(display_type, '') = 'balance_inicial'
                LIMIT 1
                """,
                (statement_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE bank_movements
                    SET balance_after = ?, running_balance = ?, updated_at = CURRENT_TIMESTAMP,
                        ai_model = ?, confidence = ?, display_name = ?
                    WHERE id = ?
                    """,
                    (opening_balance, opening_balance, ai_model, confidence_value, display_name, existing[0])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO bank_movements (
                        statement_id, account, amount, description, cleaned_description, date,
                        transaction_type, category, reference, balance_after, raw_data,
                        tenant_id, created_at, processing_status, bank_account_id, account_id,
                        user_id, movement_kind, display_type, transaction_subtype,
                        running_balance, balance_before, cargo_amount, abono_amount, is_reconciled,
                        ai_model, confidence, display_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        statement_id,
                        account_str,
                        0.0,
                        'Balance inicial',
                        'balance inicial',
                        balance_date,
                        TransactionType.TRANSFER.value,
                        None,
                        None,
                        opening_balance,
                        'Saldo inicial generado automáticamente',
                        tenant_id,
                        'completed',
                        account_str,
                        account_id,
                        user_id,
                        MovementKind.TRANSFERENCIA.value,
                        'balance_inicial',
                        'balance_inicial',
                        opening_balance,
                        None,
                        0.0,
                        0.0,
                        0,
                        ai_model,
                        confidence_value,
                        display_name,
                    )
                )

            conn.commit()

    def upsert_closing_balance(
        self,
        statement_id: int,
        account_id: int,
        user_id: int,
        tenant_id: int,
        closing_balance: Optional[float],
        balance_date: Optional[date],
        ai_model: Optional[str] = None,
        confidence: Optional[float] = None,
        display_name: Optional[str] = "Balance final",
    ) -> None:
        """Ensure a balance final row exists for a statement."""

        if closing_balance is None:
            return

        balance_date = balance_date or date.today()
        ai_model = ai_model or "gemini-2.5-flash"
        confidence_value = confidence if confidence is not None else 1.0
        display_name = (display_name or "Balance final").strip() or "Balance final"
        account_str = str(account_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM bank_movements
                WHERE statement_id = ? AND COALESCE(display_type, '') = 'balance_final'
                LIMIT 1
                """,
                (statement_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    """
                    UPDATE bank_movements
                    SET balance_after = ?, running_balance = ?, updated_at = CURRENT_TIMESTAMP,
                        ai_model = ?, confidence = ?, display_name = ?
                    WHERE id = ?
                    """,
                    (closing_balance, closing_balance, ai_model, confidence_value, display_name, existing[0])
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO bank_movements (
                        statement_id, account, amount, description, cleaned_description, date,
                        transaction_type, category, reference, balance_after, raw_data,
                        tenant_id, created_at, processing_status, bank_account_id, account_id,
                        user_id, movement_kind, display_type, transaction_subtype,
                        running_balance, balance_before, cargo_amount, abono_amount, is_reconciled,
                        ai_model, confidence, display_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        statement_id,
                        account_str,
                        0.0,
                        'Balance final',
                        'balance final',
                        balance_date,
                        TransactionType.TRANSFER.value,
                        None,
                        None,
                        closing_balance,
                        'Saldo final generado automáticamente',
                        tenant_id,
                        'completed',
                        account_str,
                        account_id,
                        user_id,
                        MovementKind.TRANSFERENCIA.value,
                        'balance_final',
                        'balance_final',
                        closing_balance,
                        None,
                        0.0,
                        0.0,
                        0,
                        ai_model,
                        confidence_value,
                        display_name,
                    )
                )

            conn.commit()

    def delete_statement(self, statement_id: int, user_id: int, tenant_id: int) -> bool:
        """Eliminar statement y sus transacciones"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Verificar ownership
                cursor.execute("""
                    SELECT file_path FROM bank_statements
                    WHERE id = ? AND user_id = ? AND tenant_id = ?
                """, (statement_id, user_id, tenant_id))

                row = cursor.fetchone()
                if not row:
                    return False

                file_path = row['file_path']

                # Eliminar transacciones relacionadas
                cursor.execute("""
                    DELETE FROM bank_movements
                    WHERE statement_id = ?
                """, (statement_id,))

                # Eliminar statement
                cursor.execute("""
                    DELETE FROM bank_statements
                    WHERE id = ? AND user_id = ? AND tenant_id = ?
                """, (statement_id, user_id, tenant_id))

                conn.commit()

                # Eliminar archivo físico
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)

                return True

        except Exception as e:
            logger.error(f"Error deleting statement {statement_id}: {e}")
            return False

    def _row_to_statement(self, row: sqlite3.Row) -> BankStatement:
        return BankStatement(
            id=row['id'],
            account_id=row['account_id'],
            user_id=row['user_id'],
            tenant_id=row['tenant_id'],
            file_name=row['file_name'],
            file_path=row['file_path'],
            file_hash=row['file_hash'] if 'file_hash' in row.keys() else None,
            file_size=row['file_size'],
            file_type=FileType(row['file_type']),
            period_start=date.fromisoformat(row['period_start']) if row['period_start'] else None,
            period_end=date.fromisoformat(row['period_end']) if row['period_end'] else None,
            opening_balance=row['opening_balance'] or 0.0,
            closing_balance=row['closing_balance'] or 0.0,
            total_credits=row['total_credits'] or 0.0,
            total_debits=row['total_debits'] or 0.0,
            transaction_count=row['transaction_count'] or 0,
            parsing_status=ParsingStatus(row['parsing_status']),
            parsing_error=row['parsing_error'],
            uploaded_at=datetime.fromisoformat(row['uploaded_at']) if row['uploaded_at'] else None,
            parsed_at=datetime.fromisoformat(row['parsed_at']) if row['parsed_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

    def _row_to_summary(self, row: sqlite3.Row) -> BankStatementSummary:
        return BankStatementSummary(
            id=row['id'],
            file_name=row['file_name'],
            account_name=row['account_name'] or 'Cuenta',
            account_type=row['account_type'] or 'bancaria',
            banco_nombre=row['banco_nombre'],
            period_start=date.fromisoformat(row['period_start']) if row['period_start'] else None,
            period_end=date.fromisoformat(row['period_end']) if row['period_end'] else None,
            transaction_count=row['transaction_count'] or 0,
            total_credits=row['total_credits'] or 0.0,
            total_debits=row['total_debits'] or 0.0,
            parsing_status=ParsingStatus(row['parsing_status']),
            uploaded_at=datetime.fromisoformat(row['uploaded_at']),
            parsed_transactions=row['parsed_transactions'] or 0
        )

    def _row_to_transaction(self, row: sqlite3.Row) -> BankTransaction:
        row_keys = row.keys()
        context_used = row['context_used'] if 'context_used' in row_keys else None
        ai_model = row['ai_model'] if 'ai_model' in row_keys else None
        context_confidence = row['context_confidence'] if 'context_confidence' in row_keys else None
        context_version = row['context_version'] if 'context_version' in row_keys else None
        display_name = row['display_name'] if 'display_name' in row_keys else None

        return BankTransaction(
            id=row['id'],
            statement_id=row['statement_id'],
            account_id=int(row['account']) if row['account'] else 0,
            user_id=row['user_id'] if 'user_id' in row.keys() and row['user_id'] is not None else 0,
            tenant_id=row['tenant_id'],
            date=date.fromisoformat(row['date']) if row['date'] else date.today(),
            description=row['description'] or '',
            amount=row['amount'] or 0.0,
            transaction_type=TransactionType(row['transaction_type']) if row['transaction_type'] else TransactionType.DEBIT,
            category=row['category'],
            reference=row['reference'],
            balance_after=row['balance_after'],
            status=row['processing_status'] or 'unmatched',
            matched_expense_id=row['matched_expense_id'],
            confidence=row['confidence'] or 0.0,
            raw_data=row['raw_data'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            movement_kind=MovementKind(row['movement_kind']) if row['movement_kind'] else infer_movement_kind(row['transaction_type'], row['description']),
            context_used=context_used,
            ai_model=ai_model,
            context_confidence=context_confidence,
            context_version=context_version,
            display_name=display_name,
        )


# Instancia global del servicio
bank_statements_service = BankStatementsService()
