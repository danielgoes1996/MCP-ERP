"""
Modelos Pydantic para gestión de estados de cuenta bancarios - PostgreSQL
Versión migrada de SQLite a PostgreSQL
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationInfo
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import logging
import os
import json
import hashlib
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# =====================================================
# CONFIGURACIÓN POSTGRESQL
# =====================================================

POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}


# =====================================================
# ENUMS (sin cambios)
# =====================================================

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


class MovementKind(str, Enum):
    """Clasificación de negocio para los movimientos bancarios"""
    INGRESO = "Ingreso"
    GASTO = "Gasto"
    TRANSFERENCIA = "Transferencia"


# =====================================================
# KEYWORDS Y HELPERS (sin cambios)
# =====================================================

TRANSFER_KEYWORDS = [
    "traspaso", "transferencia", "mov.banc", "transfer",
    "pago tarjeta", "pago tarjeta de credito", "card payment",
    "interbank", "spei propio", "cta propia", "propia", "pagotarjeta",
    "balance inicial", "saldo inicial", "saldo anterior",
    "payment thank you", "pago total", "pago mensual", "payment received",
]

SKIP_TRANSACTION_KEYWORDS = [
    "balance inicial", "saldo anterior", "saldo final",
    "saldo actual", "saldo promedio",
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


# =====================================================
# MODELOS PYDANTIC (sin cambios)
# =====================================================

class BankStatement(BaseModel):
    id: Optional[int] = None
    account_id: int
    tenant_id: int
    company_id: Optional[int] = None
    file_name: str
    file_path: Optional[str] = None
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
    tenant_id: int
    company_id: Optional[int] = None
    transaction_date: date  # Usar nombre de columna PostgreSQL
    description: str
    amount: float
    transaction_type: TransactionType
    category: Optional[str] = None
    reference: Optional[str] = None
    balance: Optional[float] = None  # balance_after en PostgreSQL

    # Reconciliación
    reconciled: bool = False
    reconciled_with_invoice_id: Optional[int] = None
    reconciled_at: Optional[datetime] = None

    # MSI Detection (NUEVO)
    msi_candidate: bool = False
    msi_invoice_id: Optional[int] = None
    msi_months: Optional[int] = None
    msi_confidence: Optional[float] = None

    # AI/Enrichment
    ai_model: Optional[str] = None
    confidence: float = 0.0

    # Legacy fields
    movement_kind: MovementKind = MovementKind.GASTO
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=(), populate_by_name=True)


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
    account_type: Optional[str] = None
    bank_name: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    transaction_count: int
    total_credits: float
    total_debits: float
    parsing_status: ParsingStatus
    uploaded_at: datetime
    parsed_transactions_count: int = 0
    msi_candidates_count: int = 0

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())


# =====================================================
# SERVICIO POSTGRESQL
# =====================================================

class BankStatementsServicePostgres:
    """
    Servicio para gestión de estados de cuenta - PostgreSQL
    Reemplaza la versión SQLite
    """

    def __init__(self):
        self.upload_dir = Path("uploads/statements")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.postgres_config = POSTGRES_CONFIG

    def _get_connection(self):
        """Obtener conexión a PostgreSQL"""
        return psycopg2.connect(**self.postgres_config)

    def create_statement(
        self,
        request: CreateBankStatementRequest,
        user_id: int,
        tenant_id: int,
        file_content: bytes
    ) -> BankStatement:
        """Crear nuevo statement y guardar archivo"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Obtener company_id de la cuenta
            cursor.execute("""
                SELECT company_id, bank_name
                FROM payment_accounts
                WHERE id = %s AND tenant_id = %s
            """, (request.account_id, tenant_id))

            account_info = cursor.fetchone()
            if not account_info:
                raise ValueError(f"Account {request.account_id} not found")

            company_id = account_info['company_id']
            bank_name = account_info['bank_name'] or ''
            bank_slug = re.sub(r'[^a-z0-9]+', '-', bank_name.lower()).strip('-')

            # Generar path único
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{user_id}_{timestamp}_{bank_slug}_{request.file_name}" if bank_slug else f"{user_id}_{timestamp}_{request.file_name}"
            file_path = self.upload_dir / safe_filename

            # Guardar archivo
            with open(file_path, 'wb') as f:
                f.write(file_content)

            file_size = len(file_content)

            # Insertar en PostgreSQL
            cursor.execute("""
                INSERT INTO bank_statements (
                    account_id, tenant_id, company_id, file_name, file_path,
                    file_size, file_type, period_start, period_end,
                    parsing_status, uploaded_at, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                request.account_id, tenant_id, company_id, request.file_name,
                str(file_path), file_size, request.file_type.value,
                request.period_start, request.period_end,
                ParsingStatus.PENDING.value, datetime.now(), datetime.now()
            ))

            statement_id = cursor.fetchone()['id']
            conn.commit()
            cursor.close()
            conn.close()

            # Obtener statement creado
            return self.get_statement(statement_id, tenant_id)

        except Exception as e:
            logger.error(f"Error creating statement: {e}")
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink()
            raise

    def get_statement(self, statement_id: int, tenant_id: int) -> BankStatement:
        """Obtener statement por ID"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM bank_statements
            WHERE id = %s AND tenant_id = %s
        """, (statement_id, tenant_id))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            raise ValueError(f"Statement {statement_id} not found")

        return self._row_to_statement(row)

    def get_user_statements(self, tenant_id: int, account_id: Optional[int] = None) -> List[BankStatementSummary]:
        """Obtener statements del tenant con resumen"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        where_clause = "WHERE tenant_id = %s"
        params = [tenant_id]

        if account_id:
            where_clause += " AND account_id = %s"
            params.append(account_id)

        cursor.execute(f"""
            SELECT * FROM bank_statements_summary
            {where_clause}
            ORDER BY uploaded_at DESC
        """, params)

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [self._row_to_summary(row) for row in rows]

    def get_statement_transactions(self, statement_id: int, tenant_id: int) -> List[BankTransaction]:
        """Obtener transacciones de un statement"""
        conn = self._get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT bt.* FROM bank_transactions bt
            JOIN bank_statements bs ON bt.statement_id = bs.id
            WHERE bs.id = %s AND bs.tenant_id = %s
            ORDER BY bt.transaction_date DESC, bt.id DESC
        """, (statement_id, tenant_id))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [self._row_to_transaction(row) for row in rows]

    def update_parsing_status(
        self,
        statement_id: int,
        status: ParsingStatus,
        error: Optional[str] = None,
        summary_data: Optional[Dict[str, Any]] = None
    ):
        """Actualizar estado de parsing"""
        conn = self._get_connection()
        cursor = conn.cursor()

        parsed_at = datetime.now() if status == ParsingStatus.COMPLETED else None

        if summary_data:
            cursor.execute("""
                UPDATE bank_statements
                SET parsing_status = %s, parsing_error = %s, parsed_at = %s,
                    total_credits = %s, total_debits = %s, transaction_count = %s,
                    opening_balance = %s, closing_balance = %s,
                    period_start = %s, period_end = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                status.value, error, parsed_at,
                summary_data.get('total_credits', 0),
                summary_data.get('total_debits', 0),
                summary_data.get('transaction_count', 0),
                summary_data.get('opening_balance', 0),
                summary_data.get('closing_balance', 0),
                summary_data.get('period_start'),
                summary_data.get('period_end'),
                statement_id
            ))
        else:
            cursor.execute("""
                UPDATE bank_statements
                SET parsing_status = %s, parsing_error = %s, parsed_at = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status.value, error, parsed_at, statement_id))

        conn.commit()
        cursor.close()
        conn.close()

    def clear_statement_transactions(self, statement_id: int):
        """Eliminar transacciones antes de reprocesar"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM bank_transactions WHERE statement_id = %s",
            (statement_id,)
        )

        conn.commit()
        cursor.close()
        conn.close()

    def add_transactions(self, statement_id: int, transactions: List[BankTransaction]):
        """Agregar transacciones parseadas a un statement"""
        if not transactions:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        for txn in transactions:
            # Verificar duplicados
            cursor.execute("""
                SELECT id FROM bank_transactions
                WHERE statement_id = %s
                AND transaction_date = %s
                AND ABS(amount - %s) < 0.01
                AND description = %s
                LIMIT 1
            """, (statement_id, txn.date, txn.amount, txn.description))

            if cursor.fetchone():
                logger.info(f"Duplicate transaction skipped: {txn.date} {txn.amount}")
                continue

            # Insertar transacción
            cursor.execute("""
                INSERT INTO bank_transactions (
                    statement_id, account_id, tenant_id, company_id,
                    transaction_date, description, amount, balance,
                    transaction_type, category, reference,
                    reconciled, msi_candidate, msi_invoice_id, msi_months, msi_confidence,
                    ai_model, confidence, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                statement_id, txn.account_id, txn.tenant_id, txn.company_id,
                txn.transaction_date, txn.description, txn.amount, txn.balance,
                txn.transaction_type.value, txn.category, txn.reference,
                txn.reconciled, txn.msi_candidate, txn.msi_invoice_id,
                txn.msi_months, txn.msi_confidence,
                txn.ai_model, txn.confidence
            ))

        conn.commit()
        cursor.close()
        conn.close()

    def delete_statement(self, statement_id: int, tenant_id: int) -> bool:
        """Eliminar statement (CASCADE eliminará transacciones)"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT file_path FROM bank_statements
                WHERE id = %s AND tenant_id = %s
            """, (statement_id, tenant_id))

            row = cursor.fetchone()
            if not row:
                return False

            file_path = row['file_path']

            cursor.execute("""
                DELETE FROM bank_statements
                WHERE id = %s AND tenant_id = %s
            """, (statement_id, tenant_id))

            conn.commit()
            cursor.close()
            conn.close()

            # Eliminar archivo físico
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)

            return True

        except Exception as e:
            logger.error(f"Error deleting statement {statement_id}: {e}")
            return False

    def _row_to_statement(self, row: dict) -> BankStatement:
        """Convertir row de PostgreSQL a BankStatement"""
        return BankStatement(
            id=row['id'],
            account_id=row['account_id'],
            tenant_id=row['tenant_id'],
            company_id=row['company_id'],
            file_name=row['file_name'],
            file_path=row['file_path'],
            file_size=row['file_size'],
            file_type=FileType(row['file_type']),
            period_start=row['period_start'],
            period_end=row['period_end'],
            opening_balance=float(row['opening_balance'] or 0.0),
            closing_balance=float(row['closing_balance'] or 0.0),
            total_credits=float(row['total_credits'] or 0.0),
            total_debits=float(row['total_debits'] or 0.0),
            transaction_count=row['transaction_count'] or 0,
            parsing_status=ParsingStatus(row['parsing_status']),
            parsing_error=row['parsing_error'],
            uploaded_at=row['uploaded_at'],
            parsed_at=row['parsed_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def _row_to_summary(self, row: dict) -> BankStatementSummary:
        """Convertir row de PostgreSQL a BankStatementSummary"""
        return BankStatementSummary(
            id=row['id'],
            file_name=row['file_name'],
            account_name=row['account_name'] or 'Cuenta',
            account_type=row['account_type'],
            bank_name=row['bank_name'],
            period_start=row['period_start'],
            period_end=row['period_end'],
            transaction_count=row['transaction_count'] or 0,
            total_credits=float(row['total_credits'] or 0.0),
            total_debits=float(row['total_debits'] or 0.0),
            parsing_status=ParsingStatus(row['parsing_status']),
            uploaded_at=row['uploaded_at'],
            parsed_transactions_count=row['parsed_transactions_count'] or 0,
            msi_candidates_count=row.get('msi_candidates_count', 0)
        )

    def _row_to_transaction(self, row: dict) -> BankTransaction:
        """Convertir row de PostgreSQL a BankTransaction"""
        return BankTransaction(
            id=row['id'],
            statement_id=row['statement_id'],
            account_id=row['account_id'],
            tenant_id=row['tenant_id'],
            company_id=row.get('company_id'),
            transaction_date=row['transaction_date'],
            description=row['description'] or '',
            amount=float(row['amount'] or 0.0),
            transaction_type=TransactionType(row['transaction_type']),
            category=row.get('category'),
            reference=row.get('reference'),
            balance=float(row['balance']) if row.get('balance') else None,
            reconciled=row.get('reconciled', False),
            reconciled_with_invoice_id=row.get('reconciled_with_invoice_id'),
            reconciled_at=row.get('reconciled_at'),
            msi_candidate=row.get('msi_candidate', False),
            msi_invoice_id=row.get('msi_invoice_id'),
            msi_months=row.get('msi_months'),
            msi_confidence=float(row['msi_confidence']) if row.get('msi_confidence') else None,
            ai_model=row.get('ai_model'),
            confidence=float(row.get('confidence', 0.0)),
            movement_kind=MovementKind.GASTO,  # Default
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )


# =====================================================
# INSTANCIA GLOBAL
# =====================================================

# Usar PostgreSQL service
bank_statements_service = BankStatementsServicePostgres()
