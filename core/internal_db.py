"""Internal database utilities for MCP Server.

This module encapsulates the internal persistence layer used to keep
application-specific data that complements external ERP systems.  It
initialises a lightweight SQLite database with a standard chart of
accounts so that new deployments start with sensible defaults.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional

from config.config import config

logger = logging.getLogger(__name__)

_DB_LOCK = Lock()


def _get_db_path() -> Path:
    """Resolve the filesystem path for the internal SQLite database."""

    db_path = Path(config.INTERNAL_DB_PATH)
    if not db_path.is_absolute():
        base_dir = Path(config.DATA_DIR)
        db_path = (base_dir / db_path).resolve()
    return db_path


def _ensure_storage_path(path: Path) -> None:
    """Make sure the directory for the database exists."""

    path.parent.mkdir(parents=True, exist_ok=True)


ACCOUNT_CATALOG: List[Dict[str, str]] = [
    {
        "group_name": "Activo",
        "code": "1100",
        "name": "Caja chica",
        "description": "Efectivo disponible para gastos menores inmediatos.",
        "sat_code": "110.01",
    },
    {
        "group_name": "Activo",
        "code": "1110",
        "name": "Bancos",
        "description": "Saldos en cuentas bancarias operativas.",
        "sat_code": "111.01",
    },
    {
        "group_name": "Activo",
        "code": "1120",
        "name": "Clientes",
        "description": "Cuentas por cobrar a clientes por ventas a crédito.",
        "sat_code": "113.01",
    },
    {
        "group_name": "Activo",
        "code": "1130",
        "name": "Inventarios",
        "description": "Mercancías y materias primas disponibles para la venta.",
        "sat_code": "115.01",
    },
    {
        "group_name": "Activo",
        "code": "1140",
        "name": "Anticipos a proveedores",
        "description": "Pagos adelantados a proveedores pendientes de aplicar.",
        "sat_code": "118.01",
    },
    {
        "group_name": "Pasivo",
        "code": "2100",
        "name": "Proveedores",
        "description": "Obligaciones con proveedores por compras a crédito.",
        "sat_code": "201.01",
    },
    {
        "group_name": "Pasivo",
        "code": "2110",
        "name": "Acreedores diversos",
        "description": "Deudas con terceros distintos a proveedores habituales.",
        "sat_code": "203.01",
    },
    {
        "group_name": "Pasivo",
        "code": "2120",
        "name": "IVA pendiente de pago",
        "description": "IVA cobrado pendiente de enterar a la autoridad.",
        "sat_code": "208.01",
    },
    {
        "group_name": "Pasivo",
        "code": "2130",
        "name": "IVA retenido por pagar",
        "description": "IVA retenido a proveedores que falta por pagar al SAT.",
        "sat_code": "208.02",
    },
    {
        "group_name": "Pasivo",
        "code": "2140",
        "name": "Préstamos / Créditos bancarios",
        "description": "Financiamientos bancarios vigentes por pagar.",
        "sat_code": "206.01",
    },
    {
        "group_name": "Capital",
        "code": "3100",
        "name": "Capital social",
        "description": "Aportaciones de los socios registradas en el capital.",
        "sat_code": "301.01",
    },
    {
        "group_name": "Capital",
        "code": "3110",
        "name": "Resultados acumulados",
        "description": "Utilidades o pérdidas acumuladas de ejercicios previos.",
        "sat_code": "302.01",
    },
    {
        "group_name": "Capital",
        "code": "3120",
        "name": "Utilidad o pérdida del ejercicio",
        "description": "Resultado del ejercicio en curso en espera de aplicación.",
        "sat_code": "302.02",
    },
    {
        "group_name": "Ingresos",
        "code": "4100",
        "name": "Ventas nacionales (0%)",
        "description": "Ventas de bienes o servicios exentas de IVA.",
        "sat_code": "401.01",
    },
    {
        "group_name": "Ingresos",
        "code": "4110",
        "name": "Ventas gravadas (16%)",
        "description": "Ventas sujetas a la tarifa general de IVA.",
        "sat_code": "401.02",
    },
    {
        "group_name": "Ingresos",
        "code": "4120",
        "name": "Otros ingresos",
        "description": "Ingresos diversos distintos a la actividad principal.",
        "sat_code": "403.01",
    },
    {
        "group_name": "Costos",
        "code": "5100",
        "name": "Costo de ventas",
        "description": "Costo directo de mercancías o servicios vendidos.",
        "sat_code": "501.01",
    },
    {
        "group_name": "Gastos",
        "code": "6100",
        "name": "Sueldos y salarios",
        "description": "Nómina y prestaciones al personal.",
        "sat_code": "601.01",
    },
    {
        "group_name": "Gastos",
        "code": "6110",
        "name": "Honorarios profesionales",
        "description": "Pagos a profesionistas independientes.",
        "sat_code": "603.01",
    },
    {
        "group_name": "Gastos",
        "code": "6120",
        "name": "Renta de local u oficina",
        "description": "Pagos por arrendamiento de inmuebles.",
        "sat_code": "605.01",
    },
    {
        "group_name": "Gastos",
        "code": "6130",
        "name": "Servicios básicos (luz, agua, internet)",
        "description": "Servicios indispensables para operar la empresa.",
        "sat_code": "606.01",
    },
    {
        "group_name": "Gastos",
        "code": "6140",
        "name": "Combustibles y lubricantes",
        "description": "Gastos de combustible y mantenimiento vehicular.",
        "sat_code": "607.01",
    },
    {
        "group_name": "Gastos",
        "code": "6150",
        "name": "Viáticos y viajes",
        "description": "Viáticos, hospedaje y transporte de personal en viaje.",
        "sat_code": "608.01",
    },
    {
        "group_name": "Gastos",
        "code": "6160",
        "name": "Publicidad y marketing",
        "description": "Promoción, campañas y materiales publicitarios.",
        "sat_code": "609.01",
    },
    {
        "group_name": "Gastos",
        "code": "6170",
        "name": "Gastos financieros (comisiones, intereses)",
        "description": "Cargos financieros por créditos y servicios bancarios.",
        "sat_code": "610.01",
    },
    {
        "group_name": "Gastos",
        "code": "6180",
        "name": "Papelería y misceláneos",
        "description": "Materiales de oficina y suministros generales.",
        "sat_code": "611.01",
    },
    {
        "group_name": "Gastos",
        "code": "6190",
        "name": "Gastos no deducibles",
        "description": "Pagos que no cumplen requisitos fiscales de deducibilidad.",
        "sat_code": "612.01",
    },
    {
        "group_name": "IVA",
        "code": "1190",
        "name": "IVA acreditable pendiente",
        "description": "IVA pagado a proveedores pendiente de acreditar.",
        "sat_code": "118.02",
    },
    {
        "group_name": "IVA",
        "code": "1195",
        "name": "IVA acreditable pagado",
        "description": "IVA acreditado por compras con comprobantes válidos.",
        "sat_code": "118.03",
    },
    {
        "group_name": "IVA",
        "code": "2190",
        "name": "IVA trasladado en ventas",
        "description": "IVA cobrado a clientes por ventas gravadas.",
        "sat_code": "208.03",
    },
]


SCHEMA_MIGRATIONS: List[Dict[str, Any]] = [
    {
        "name": "0001_initial",
        "statements": [
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                group_name TEXT NOT NULL,
                sat_code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expense_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_reference TEXT,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'MXN',
                account_code TEXT NOT NULL,
                has_invoice INTEGER NOT NULL DEFAULT 0,
                invoice_uuid TEXT,
                sat_document_type TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (account_code) REFERENCES accounts(code)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_records_account_code
                ON expense_records(account_code)
            """,
            """
            CREATE TABLE IF NOT EXISTS bank_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movement_id TEXT NOT NULL UNIQUE,
                movement_date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'MXN',
                bank TEXT NOT NULL,
                reference TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bank_match_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id TEXT NOT NULL,
                movement_id TEXT NOT NULL,
                confidence REAL NOT NULL,
                decision TEXT NOT NULL,
                notes TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bank_match_feedback_movement
                ON bank_match_feedback(movement_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bank_match_feedback_expense
                ON bank_match_feedback(expense_id)
            """,
        ],
    },
    {
        "name": "0002_expense_extended",
        "statements": [
            """
            ALTER TABLE expense_records RENAME TO expense_records_legacy
            """,
            """
            CREATE TABLE expense_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_reference TEXT,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'MXN',
                expense_date TEXT,
                category TEXT,
                provider_name TEXT,
                provider_rfc TEXT,
                workflow_status TEXT NOT NULL DEFAULT 'draft',
                invoice_status TEXT NOT NULL DEFAULT 'pendiente',
                invoice_uuid TEXT,
                invoice_folio TEXT,
                invoice_url TEXT,
                tax_total REAL,
                tax_metadata TEXT,
                payment_method TEXT,
                paid_by TEXT NOT NULL DEFAULT 'company_account',
                will_have_cfdi INTEGER NOT NULL DEFAULT 1,
                bank_status TEXT NOT NULL DEFAULT 'pendiente',
                account_code TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (account_code) REFERENCES accounts(code)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_records_account_code
                ON expense_records(account_code)
            """,
            """
            INSERT INTO expense_records (
                id,
                external_reference,
                description,
                amount,
                currency,
                account_code,
                metadata,
                created_at,
                updated_at,
                invoice_status,
                workflow_status,
                invoice_uuid,
                will_have_cfdi
            )
            SELECT
                id,
                external_reference,
                description,
                amount,
                currency,
                account_code,
                metadata,
                created_at,
                updated_at,
                CASE WHEN has_invoice = 1 THEN 'facturado' ELSE 'pendiente' END,
                'draft',
                invoice_uuid,
                has_invoice
            FROM expense_records_legacy
            """,
            """
            DROP TABLE expense_records_legacy
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_records_date
                ON expense_records(expense_date)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_records_status
                ON expense_records(invoice_status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_records_bank_status
                ON expense_records(bank_status)
            """,
            """
            CREATE TABLE IF NOT EXISTS expense_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                uuid TEXT,
                folio TEXT,
                url TEXT,
                issued_at TEXT,
                status TEXT NOT NULL DEFAULT 'registrada',
                raw_xml TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (expense_id) REFERENCES expense_records(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expense_bank_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                bank_movement_id INTEGER NOT NULL,
                link_type TEXT NOT NULL DEFAULT 'suggested',
                confidence REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (expense_id) REFERENCES expense_records(id),
                FOREIGN KEY (bank_movement_id) REFERENCES bank_movements(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS expense_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                actor TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (expense_id) REFERENCES expense_records(id)
            )
            """,
            """
            ALTER TABLE bank_movements ADD COLUMN account TEXT
            """,
            """
            ALTER TABLE bank_movements ADD COLUMN movement_type TEXT
            """,
            """
            ALTER TABLE bank_movements ADD COLUMN balance REAL
            """,
            """
            ALTER TABLE bank_movements ADD COLUMN metadata TEXT
            """,
            """
            ALTER TABLE bank_movements ADD COLUMN expense_id INTEGER
            """,
        ],
    },
]


def _apply_migrations(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_versions'"
    )
    exists = cursor.fetchone() is not None
    if not exists:
        cursor.execute(
            """
            CREATE TABLE schema_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.commit()

    cursor.execute("SELECT name FROM schema_versions")
    applied = {row[0] for row in cursor.fetchall()}

    for migration in SCHEMA_MIGRATIONS:
        if migration["name"] in applied:
            continue

        logger.info("Applying migration %s", migration["name"])
        for statement in migration["statements"]:
            cursor.execute(statement)
        cursor.execute(
            "INSERT INTO schema_versions (name, applied_at) VALUES (?, ?)",
            (migration["name"], datetime.utcnow().isoformat()),
        )
        connection.commit()

def initialize_internal_database() -> None:
    """Ensure the internal database exists, tables are created and seeded."""

    db_path = _get_db_path()
    _ensure_storage_path(db_path)

    with _DB_LOCK:
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            _apply_migrations(connection)
            _seed_account_catalog(connection, ACCOUNT_CATALOG)
            _seed_bank_movements(connection, BANK_MOVEMENTS_SEED)


def _seed_account_catalog(
    connection: sqlite3.Connection,
    catalog: Iterable[Dict[str, str]],
) -> None:
    """Populate the account catalog if entries are missing."""

    existing_codes = {
        row[0]
        for row in connection.execute("SELECT code FROM accounts")
    }

    now = datetime.utcnow().isoformat()
    to_insert = [
        (
            entry["code"],
            entry["name"],
            entry["description"],
            entry["group_name"],
            entry["sat_code"],
            now,
            now,
        )
        for entry in catalog
        if entry["code"] not in existing_codes
    ]

    if to_insert:
        logger.info("Seeding %s missing accounts into internal catalog", len(to_insert))
        connection.executemany(
            """
            INSERT INTO accounts (
                code, name, description, group_name, sat_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            to_insert,
        )

    # Keep catalogue information up to date for existing accounts
    for entry in catalog:
        connection.execute(
            """
            UPDATE accounts
               SET name = ?,
                   description = ?,
                   group_name = ?,
                   sat_code = ?,
                   updated_at = ?
             WHERE code = ?
            """,
            (
                entry["name"],
                entry["description"],
                entry["group_name"],
                entry["sat_code"],
                now,
                entry["code"],
            ),
        )

    connection.commit()


BANK_MOVEMENTS_SEED: List[Dict[str, Any]] = [
    {
        "movement_id": "MOV-001",
        "bank": "BBVA",
        "amount": 845.32,
        "currency": "MXN",
        "movement_date": "2024-09-01",
        "description": "Cargo Tarjeta Empresarial - Pemex",
        "reference": "BBVA-PMX-0901",
        "tags": ["combustible", "tarjeta_empresa"],
    },
    {
        "movement_id": "MOV-002",
        "bank": "Santander",
        "amount": 562.10,
        "currency": "MXN",
        "movement_date": "2024-09-02",
        "description": "Cargo Tarjeta Empresarial - Restaurante",
        "reference": "SANT-REST-0902",
        "tags": ["alimentos", "tarjeta_empresa"],
    },
    {
        "movement_id": "MOV-003",
        "bank": "Banorte",
        "amount": 2100.00,
        "currency": "MXN",
        "movement_date": "2024-09-03",
        "description": "Transferencia a proveedor ACME",
        "reference": "BAN-TRF-ACME",
        "tags": ["proveedor", "transferencia"],
    },
    {
        "movement_id": "MOV-004",
        "bank": "HSBC",
        "amount": 152.75,
        "currency": "MXN",
        "movement_date": "2024-09-05",
        "description": "Cargo Uber Business",
        "reference": "HSBC-UBER-0905",
        "tags": ["transporte", "tarjeta_empresa"],
    },
]


def _seed_bank_movements(
    connection: sqlite3.Connection,
    seed_data: Iterable[Dict[str, Any]],
) -> None:
    existing_ids = {
        row[0]
        for row in connection.execute("SELECT movement_id FROM bank_movements")
    }

    now = datetime.utcnow().isoformat()
    to_insert = [
        (
            entry["movement_id"],
            entry["movement_date"],
            entry["description"],
            float(entry["amount"]),
            entry.get("currency", "MXN"),
            entry.get("bank", "Desconocido"),
            entry.get("reference"),
            json.dumps(entry.get("tags", [])) if entry.get("tags") else None,
            now,
            now,
        )
        for entry in seed_data
        if entry["movement_id"] not in existing_ids
    ]

    if to_insert:
        logger.info("Seeding %s bank movements into internal database", len(to_insert))
        connection.executemany(
            """
            INSERT INTO bank_movements (
                movement_id,
                movement_date,
                description,
                amount,
                currency,
                bank,
                reference,
                tags,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            to_insert,
        )

    connection.commit()


def get_account_catalog() -> List[Dict[str, str]]:
    """Fetch the account catalog from the internal database."""

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT code, name, description, group_name, sat_code FROM accounts ORDER BY code"
        ).fetchall()
        return [dict(row) for row in rows]


def record_internal_expense(
    *,
    description: str,
    amount: float,
    account_code: Optional[str] = None,
    currency: str = "MXN",
    expense_date: Optional[str] = None,
    category: Optional[str] = None,
    provider_name: Optional[str] = None,
    provider_rfc: Optional[str] = None,
    workflow_status: str = "draft",
    invoice_status: str = "pendiente",
    invoice_uuid: Optional[str] = None,
    invoice_folio: Optional[str] = None,
    invoice_url: Optional[str] = None,
    tax_total: Optional[float] = None,
    tax_metadata: Optional[Dict[str, Any]] = None,
    payment_method: Optional[str] = None,
    paid_by: str = "company_account",
    will_have_cfdi: bool = True,
    bank_status: str = "pendiente",
    external_reference: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    # Backwards compatibility flags
    has_invoice: Optional[bool] = None,
    sat_document_type: Optional[str] = None,
) -> int:
    """Persist an expense record for future reconciliation workflows."""

    payload: Dict[str, Any] = dict(metadata or {})
    if sat_document_type:
        payload.setdefault("sat_document_type", sat_document_type)
    now = datetime.utcnow().isoformat()

    if has_invoice is not None and invoice_status in (None, "pendiente"):
        invoice_status = "facturado" if has_invoice else "pendiente"
    if invoice_status is None:
        invoice_status = "pendiente"
    if bank_status is None:
        bank_status = "pendiente"

    tax_metadata_json = json.dumps(tax_metadata) if tax_metadata else None
    metadata_json = json.dumps(payload) if payload else None

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            cursor = connection.execute(
                """
                INSERT INTO expense_records (
                    external_reference,
                    description,
                    amount,
                    currency,
                    expense_date,
                    category,
                    provider_name,
                    provider_rfc,
                    workflow_status,
                    invoice_status,
                    account_code,
                    invoice_uuid,
                    invoice_folio,
                    invoice_url,
                    tax_total,
                    tax_metadata,
                    payment_method,
                    paid_by,
                    will_have_cfdi,
                    bank_status,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_reference,
                    description,
                    amount,
                    currency,
                    expense_date,
                    category,
                    provider_name,
                    provider_rfc,
                    workflow_status,
                    invoice_status,
                    account_code,
                    invoice_uuid,
                    invoice_folio,
                    invoice_url,
                    tax_total,
                    tax_metadata_json,
                    payment_method,
                    paid_by,
                    int(will_have_cfdi),
                    bank_status,
                    metadata_json,
                    now,
                    now,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)


def _row_to_expense_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
    data["tax_metadata"] = json.loads(data["tax_metadata"]) if data.get("tax_metadata") else {}
    data["will_have_cfdi"] = bool(data.get("will_have_cfdi", 0))
    return data


def fetch_expense_records(
    *,
    limit: int = 100,
    invoice_status: Optional[str] = None,
    category: Optional[str] = None,
    month: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve expense records applying optional filters."""

    conditions: List[str] = []
    params: List[Any] = []

    if invoice_status:
        conditions.append("invoice_status = ?")
        params.append(invoice_status)
    if category:
        conditions.append("LOWER(IFNULL(category, '')) = LOWER(?)")
        params.append(category)
    if month:
        conditions.append("substr(COALESCE(expense_date, created_at), 1, 7) = ?")
        params.append(month)

    query = "SELECT * FROM expense_records"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY datetime(created_at) DESC LIMIT ?"
    params.append(limit)

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, params).fetchall()
        expenses = []
        for row in rows:
            expense = _row_to_expense_dict(row)
            expense["invoices"] = fetch_expense_invoices(expense["id"], _connection=connection)
            expenses.append(expense)
        return expenses


def fetch_expense_record(expense_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single expense record by id."""

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM expense_records WHERE id = ?", (expense_id,)
        ).fetchone()
        if not row:
            return None
        expense = _row_to_expense_dict(row)
        expense["invoices"] = fetch_expense_invoices(expense_id, _connection=connection)
        return expense


def fetch_expense_invoices(
    expense_id: int,
    *,
    _connection: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    owns_connection = False
    if _connection is None:
        owns_connection = True
        _connection = sqlite3.connect(_get_db_path())
        _connection.row_factory = sqlite3.Row

    rows = _connection.execute(
        """
        SELECT id, uuid, folio, url, issued_at, status, raw_xml, created_at, updated_at
          FROM expense_invoices
         WHERE expense_id = ?
         ORDER BY datetime(created_at) DESC
        """,
        (expense_id,),
    ).fetchall()

    invoices = [dict(row) for row in rows]

    if owns_connection:
        _connection.close()

    return invoices


def update_expense_record(expense_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Apply updates to an expense record and return the refreshed struct."""

    if not updates:
        return fetch_expense_record(expense_id)

    allowed_fields = {
        "description",
        "amount",
        "currency",
        "expense_date",
        "category",
        "provider_name",
        "provider_rfc",
        "workflow_status",
        "invoice_status",
        "invoice_uuid",
        "invoice_folio",
        "invoice_url",
        "tax_total",
        "tax_metadata",
        "payment_method",
        "paid_by",
        "will_have_cfdi",
        "bank_status",
        "account_code",
        "metadata",
    }

    set_clauses: List[str] = []
    values: List[Any] = []

    for key, value in updates.items():
        if key not in allowed_fields:
            continue

        if key in {"metadata", "tax_metadata"} and value is not None:
            value = json.dumps(value)
        if key == "will_have_cfdi" and value is not None:
            value = int(bool(value))

        set_clauses.append(f"{key} = ?")
        values.append(value)

    if not set_clauses:
        return fetch_expense_record(expense_id)

    values.append(datetime.utcnow().isoformat())
    values.append(expense_id)

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.execute(
                f"UPDATE expense_records SET {', '.join(set_clauses)}, updated_at = ? WHERE id = ?",
                values,
            )
            connection.commit()

    return fetch_expense_record(expense_id)


def _log_expense_event(
    expense_id: int,
    *,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    actor: Optional[str] = None,
) -> None:
    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute(
                """
                INSERT INTO expense_events (expense_id, event_type, payload, actor, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    expense_id,
                    event_type,
                    json.dumps(payload or {}),
                    actor or "system",
                    datetime.utcnow().isoformat(),
                ),
            )
            connection.commit()


def register_expense_invoice(
    expense_id: int,
    *,
    uuid: Optional[str],
    folio: Optional[str],
    url: Optional[str],
    issued_at: Optional[str] = None,
    status: str = "registrada",
    raw_xml: Optional[str] = None,
    actor: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.execute(
                """
                INSERT INTO expense_invoices (
                    expense_id, uuid, folio, url, issued_at, status, raw_xml, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (expense_id, uuid, folio, url, issued_at, status, raw_xml, now, now),
            )
            connection.execute(
                """
                UPDATE expense_records
                   SET invoice_status = ?,
                       invoice_uuid = ?,
                       invoice_folio = ?,
                       invoice_url = ?,
                       will_have_cfdi = 1,
                       updated_at = ?
                 WHERE id = ?
                """,
                (status, uuid, folio, url, now, expense_id),
            )
            connection.commit()

    _log_expense_event(
        expense_id,
        event_type="invoice_registered",
        payload={"uuid": uuid, "folio": folio, "status": status},
        actor=actor,
    )

    return fetch_expense_record(expense_id)


def mark_expense_invoiced(
    expense_id: int,
    *,
    actor: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute(
                """
                UPDATE expense_records
                   SET invoice_status = 'facturado',
                       bank_status = CASE
                           WHEN bank_status = 'pendiente' THEN 'pendiente_bancaria'
                           ELSE bank_status
                       END,
                       updated_at = ?
                 WHERE id = ?
                """,
                (now, expense_id),
            )
            connection.commit()

    _log_expense_event(
        expense_id,
        event_type="invoice_marked_as_invoiced",
        actor=actor,
    )

    return fetch_expense_record(expense_id)


def mark_expense_without_invoice(
    expense_id: int,
    *,
    actor: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute(
                """
                UPDATE expense_records
                   SET invoice_status = 'sin_factura',
                       will_have_cfdi = 0,
                       invoice_uuid = NULL,
                       invoice_folio = NULL,
                       invoice_url = NULL,
                       bank_status = CASE
                           WHEN bank_status = 'pendiente' THEN 'sin_factura'
                           ELSE bank_status
                       END,
                       updated_at = ?
                 WHERE id = ?
                """,
                (now, expense_id),
            )
            connection.commit()

    _log_expense_event(
        expense_id,
        event_type="invoice_marked_as_not_required",
        actor=actor,
    )

    return fetch_expense_record(expense_id)

def list_bank_movements(*, limit: int = 100, include_matched: bool = True) -> List[Dict[str, Any]]:
    """Return bank movements from the internal database."""

    query = (
        "SELECT id, movement_id, movement_date, description, amount, currency, bank, reference, "
        "tags, account, movement_type, balance, metadata, expense_id, created_at, updated_at "
        "FROM bank_movements"
    )
    if not include_matched:
        query += " WHERE movement_id NOT IN (SELECT movement_id FROM bank_match_feedback WHERE decision = 'accepted')"
    query += " ORDER BY movement_date DESC LIMIT ?"

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, (limit,)).fetchall()
        return [
            {
                **dict(row),
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            }
            for row in rows
        ]


def record_bank_movement(
    *,
    movement_id: str,
    movement_date: str,
    description: str,
    amount: float,
    currency: str = "MXN",
    bank: str = "",
    reference: Optional[str] = None,
    tags: Optional[List[str]] = None,
    account: Optional[str] = None,
    movement_type: Optional[str] = None,
    balance: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    expense_id: Optional[int] = None,
) -> None:
    """Insert or update a bank movement."""

    payload_tags = json.dumps(tags) if tags else None
    payload_metadata = json.dumps(metadata) if metadata else None
    now = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute(
                """
                INSERT INTO bank_movements (
                    movement_id, movement_date, description, amount, currency,
                    bank, reference, tags, account, movement_type, balance, metadata,
                    expense_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(movement_id) DO UPDATE SET
                    movement_date = excluded.movement_date,
                    description = excluded.description,
                    amount = excluded.amount,
                    currency = excluded.currency,
                    bank = excluded.bank,
                    reference = excluded.reference,
                    tags = excluded.tags,
                    account = excluded.account,
                    movement_type = excluded.movement_type,
                    balance = excluded.balance,
                    metadata = excluded.metadata,
                    expense_id = excluded.expense_id,
                    updated_at = excluded.updated_at
                """,
                (
                    movement_id,
                    movement_date,
                    description,
                    amount,
                    currency,
                    bank,
                    reference,
                    payload_tags,
                    account,
                    movement_type,
                    balance,
                    payload_metadata,
                    expense_id,
                    now,
                    now,
                ),
            )
            connection.commit()


def record_bank_match_feedback(
    *,
    expense_id: str,
    movement_id: str,
    confidence: float,
    decision: str,
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Store feedback for a bank reconciliation suggestion."""

    now = datetime.utcnow().isoformat()
    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute(
                """
                INSERT INTO bank_match_feedback (
                    expense_id,
                    movement_id,
                    confidence,
                    decision,
                    notes,
                    metadata,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expense_id,
                    movement_id,
                    confidence,
                    decision,
                    notes,
                    json.dumps(metadata) if metadata else None,
                    now,
                ),
            )
            connection.commit()


__all__ = [
    "initialize_internal_database",
    "get_account_catalog",
    "record_internal_expense",
    "fetch_expense_records",
    "fetch_expense_record",
    "fetch_expense_invoices",
    "update_expense_record",
    "register_expense_invoice",
    "mark_expense_invoiced",
    "mark_expense_without_invoice",
    "ACCOUNT_CATALOG",
    "list_bank_movements",
    "record_bank_movement",
    "record_bank_match_feedback",
]
