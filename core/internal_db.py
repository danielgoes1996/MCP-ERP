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
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

import uuid

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
        "group_name": "Activo",
        "code": "1185",
        "name": "Gastos por comprobar",
        "description": "Anticipos o pagos pendientes de comprobación fiscal.",
        "sat_code": "118.05",
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
        "group_name": "Activo",
        "code": "1500",
        "name": "Activo fijo - Maquinaria",
        "description": "Inversiones en maquinaria productiva.",
        "sat_code": "125.01",
    },
    {
        "group_name": "Activo",
        "code": "1510",
        "name": "Activo fijo - Equipo",
        "description": "Equipo administrativo y operativo de larga duración.",
        "sat_code": "125.02",
    },
    {
        "group_name": "Activo",
        "code": "1520",
        "name": "Activo fijo - Cómputo",
        "description": "Hardware y equipo de cómputo.",
        "sat_code": "125.03",
    },
    {
        "group_name": "Activo",
        "code": "1530",
        "name": "Activo fijo - Mobiliario",
        "description": "Mobiliario y equipo de oficina.",
        "sat_code": "125.04",
    },
    {
        "group_name": "Activo",
        "code": "1590",
        "name": "Depreciación acumulada de activos fijos",
        "description": "Cuenta correctiva para reflejar depreciación acumulada.",
        "sat_code": "126.01",
    },
    {
        "group_name": "Gastos",
        "code": "6155",
        "name": "Gasto por depreciación",
        "description": "Reconocimiento periódico de depreciación de activos.",
        "sat_code": "703.01",
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
    {
        "name": "0003_multi_company_support",
        "statements": [
            """
            ALTER TABLE expense_records
                ADD COLUMN company_id TEXT NOT NULL DEFAULT 'default'
            """,
            """
            ALTER TABLE bank_movements
                ADD COLUMN company_id TEXT NOT NULL DEFAULT 'default'
            """,
            """
            ALTER TABLE expense_invoices
                ADD COLUMN company_id TEXT NOT NULL DEFAULT 'default'
            """,
            """
            ALTER TABLE expense_events
                ADD COLUMN company_id TEXT NOT NULL DEFAULT 'default'
            """,
            """
            ALTER TABLE expense_bank_links
                ADD COLUMN company_id TEXT NOT NULL DEFAULT 'default'
            """,
            """
            ALTER TABLE bank_match_feedback
                ADD COLUMN company_id TEXT NOT NULL DEFAULT 'default'
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_records_company
                ON expense_records(company_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bank_movements_company
                ON bank_movements(company_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_invoices_company
                ON expense_invoices(company_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_events_company
                ON expense_events(company_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_bank_links_company
                ON expense_bank_links(company_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bank_match_feedback_company
                ON bank_match_feedback(company_id)
            """,
            """
            UPDATE expense_invoices
               SET company_id = COALESCE(
                   (SELECT company_id FROM expense_records
                     WHERE expense_records.id = expense_invoices.expense_id),
                   company_id,
                   'default'
               )
             WHERE expense_id IS NOT NULL
            """,
            """
            UPDATE expense_events
               SET company_id = COALESCE(
                   (SELECT company_id FROM expense_records
                     WHERE expense_records.id = expense_events.expense_id),
                   company_id,
                   'default'
               )
             WHERE expense_id IS NOT NULL
            """,
            """
            UPDATE expense_bank_links
               SET company_id = COALESCE(
                   (SELECT company_id FROM expense_records
                     WHERE expense_records.id = expense_bank_links.expense_id),
                   company_id,
                   'default'
               )
             WHERE expense_id IS NOT NULL
            """,
            """
            UPDATE bank_match_feedback
               SET company_id = COALESCE(
                   (SELECT company_id FROM expense_records
                     WHERE expense_records.id = bank_match_feedback.expense_id),
                   company_id,
                   'default'
               )
             WHERE expense_id IS NOT NULL
            """,
        ],
    },
    {
        "name": "0004_user_onboarding",
        "statements": [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL UNIQUE,
                identifier_type TEXT NOT NULL,
                display_name TEXT,
                company_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_identifier_type
                ON users(identifier_type)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_company
                ON users(company_id)
            """,
        ],
    },
    {
        "name": "0005_expense_payments_and_flags",
        "statements": [
            """
            ALTER TABLE expense_records
                ADD COLUMN is_advance INTEGER NOT NULL DEFAULT 0
            """,
            """
            ALTER TABLE expense_records
                ADD COLUMN is_ppd INTEGER NOT NULL DEFAULT 0
            """,
            """
            ALTER TABLE expense_records
                ADD COLUMN asset_class TEXT
            """,
            """
            ALTER TABLE expense_records
                ADD COLUMN payment_terms TEXT
            """,
            """
            ALTER TABLE expense_records
                ADD COLUMN last_payment_date TEXT
            """,
            """
            ALTER TABLE expense_records
                ADD COLUMN total_paid REAL DEFAULT 0
            """,
            """
            CREATE TABLE IF NOT EXISTS expense_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_date TEXT NOT NULL,
                bank_movement_id INTEGER,
                metadata TEXT,
                company_id TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (expense_id) REFERENCES expense_records(id),
                FOREIGN KEY (bank_movement_id) REFERENCES bank_movements(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_payments_expense
                ON expense_payments(expense_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_payments_company
                ON expense_payments(company_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_expense_payments_date
                ON expense_payments(payment_date)
            """,
        ],
    },
    {
        "name": "0006_invoicing_agent_tables",
        "statements": [
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                raw_data TEXT NOT NULL,
                tipo TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                whatsapp_message_id TEXT,
                merchant_id INTEGER,
                merchant_name TEXT,
                category TEXT,
                confidence REAL,
                invoice_data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                company_id TEXT NOT NULL DEFAULT 'default',
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (merchant_id) REFERENCES merchants(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS merchants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                metodo_facturacion TEXT NOT NULL,
                metadata TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS invoicing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                merchant_id INTEGER,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                resultado TEXT,
                error_message TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                scheduled_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                company_id TEXT NOT NULL DEFAULT 'default',
                FOREIGN KEY (ticket_id) REFERENCES tickets(id),
                FOREIGN KEY (merchant_id) REFERENCES merchants(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_tickets_user_id
                ON tickets(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_tickets_estado
                ON tickets(estado)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_tickets_company_id
                ON tickets(company_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_merchants_metodo
                ON merchants(metodo_facturacion)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_invoicing_jobs_ticket_id
                ON invoicing_jobs(ticket_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_invoicing_jobs_estado
                ON invoicing_jobs(estado)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_invoicing_jobs_company_id
                ON invoicing_jobs(company_id)
            """,
        ],
    },
    {
        "name": "0007_add_llm_analysis_column",
        "statements": [
            """
            ALTER TABLE tickets ADD COLUMN llm_analysis TEXT
            """,
        ],
    },
    {
        "name": "0008_add_merchant_category_columns",
        "statements": [
            """
            ALTER TABLE tickets ADD COLUMN merchant_name TEXT
            """,
            """
            ALTER TABLE tickets ADD COLUMN category TEXT
            """,
            """
            ALTER TABLE tickets ADD COLUMN confidence REAL
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
            try:
                cursor.execute(statement)
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if "duplicate column name" in message:
                    logger.debug(
                        "Skipping existing column while applying %s: %s",
                        migration["name"],
                        statement.strip().split("\n", 1)[0],
                    )
                    continue
                raise
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
            entry.get("company_id", "default"),
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
                company_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            to_insert,
        )

    connection.commit()


DEMO_EXPENSE_BLUEPRINTS: List[Dict[str, Any]] = [
    {
        "key": "consultoria",
        "description": "Servicio de consultoría estratégica",
        "amount": 375.0,
        "days_ago": 7,
        "category": "servicios",
        "provider": {"nombre": "Consultores MX", "rfc": "CON200101AA1"},
        "workflow_status": "capturado",
        "invoice_status": "pendiente",
        "bank_status": "pendiente_bancaria",
        "payment_method": "transferencia",
        "paid_by": "company_account",
        "will_have_cfdi": True,
        "tax_metadata": {
            "subtotal": 323.28,
            "iva_amount": 51.72,
            "total": 375.0,
            "currency": "MXN",
            "taxes": [
                {
                    "type": "IVA",
                    "code": "002",
                    "kind": "traslado",
                    "rate": 0.16,
                    "amount": 51.72,
                }
            ],
        },
        "linked_movements": ["DEMO-SPLIT-001", "DEMO-SPLIT-002"],
        "invoice": {
            "uuid": "DEMO-UUID-001",
            "folio": "C-1001",
            "issued_at": None,
            "url": "https://demo-facturas.mx/C-1001",
            "status": "registrada",
        },
        "mark_invoiced": True,
        "metadata": {
            "demo": True,
            "scenario": "onboarding",
            "notas": "Consultoría mensual para estrategia comercial",
        },
    },
    {
        "key": "combustible",
        "description": "Carga de combustible flotilla",
        "amount": 845.32,
        "days_ago": 4,
        "category": "combustible",
        "provider": {"nombre": "Gasolinera Pemex", "rfc": "PEM970101TX3"},
        "workflow_status": "capturado",
        "invoice_status": "pendiente",
        "bank_status": "conciliado_banco",
        "payment_method": "tarjeta_empresa",
        "paid_by": "company_account",
        "will_have_cfdi": True,
        "tax_metadata": {
            "subtotal": 728.72,
            "iva_amount": 116.60,
            "total": 845.32,
            "currency": "MXN",
            "taxes": [
                {
                    "type": "IVA",
                    "code": "002",
                    "kind": "traslado",
                    "rate": 0.16,
                    "amount": 116.60,
                }
            ],
        },
        "linked_movements": ["DEMO-MOV-001"],
        "invoice": {
            "uuid": "DEMO-UUID-002",
            "folio": "GAS-2045",
            "issued_at": None,
            "url": "https://demo-facturas.mx/GAS-2045",
            "status": "registrada",
        },
        "mark_invoiced": True,
        "metadata": {
            "demo": True,
            "scenario": "onboarding",
            "notas": "Carga en estación corporativa",
        },
    },
    {
        "key": "viaticos",
        "description": "Viáticos equipo comercial",
        "amount": 1290.0,
        "days_ago": 12,
        "category": "viaticos",
        "provider": {"nombre": "Hotel Centro", "rfc": "HOT900101AA0"},
        "workflow_status": "pendiente_factura",
        "invoice_status": "pendiente",
        "bank_status": "pendiente_factura",
        "payment_method": "tarjeta_empresa",
        "paid_by": "company_account",
        "will_have_cfdi": True,
        "tax_metadata": None,
        "linked_movements": [],
        "metadata": {
            "demo": True,
            "scenario": "onboarding",
            "notas": "Reservación pendiente de factura",
        },
    },
    {
        "key": "reembolso",
        "description": "Reembolso taxi colaborador",
        "amount": 210.0,
        "days_ago": 3,
        "category": "transporte",
        "provider": {"nombre": "Taxi Ciudad"},
        "workflow_status": "capturado",
        "invoice_status": "sin_factura",
        "bank_status": "sin_factura",
        "payment_method": "efectivo",
        "paid_by": "own_account",
        "will_have_cfdi": False,
        "tax_metadata": None,
        "linked_movements": [],
        "metadata": {
            "demo": True,
            "scenario": "onboarding",
            "notas": "Gasto reportado por colaboradores para reembolso",
        },
    },
    {
        "key": "suscripcion",
        "description": "Suscripción software CRM",
        "amount": 520.0,
        "days_ago": 20,
        "category": "tecnologia",
        "provider": {"nombre": "SaaS CRM", "rfc": "SAA010203AA1"},
        "workflow_status": "capturado",
        "invoice_status": "pendiente",
        "bank_status": "conciliado_banco",
        "payment_method": "transferencia",
        "paid_by": "company_account",
        "will_have_cfdi": True,
        "tax_metadata": {
            "subtotal": 448.28,
            "iva_amount": 71.72,
            "total": 520.0,
            "currency": "MXN",
            "taxes": [
                {
                    "type": "IVA",
                    "code": "002",
                    "kind": "traslado",
                    "rate": 0.16,
                    "amount": 71.72,
                }
            ],
        },
        "linked_movements": ["DEMO-MOV-002"],
        "invoice": {
            "uuid": "DEMO-UUID-003",
            "folio": "SaaS-7781",
            "issued_at": None,
            "url": "https://demo-facturas.mx/SaaS-7781",
            "status": "registrada",
        },
        "mark_invoiced": True,
        "metadata": {
            "demo": True,
            "scenario": "onboarding",
            "notas": "Suscripción CRM mensual",
        },
    },
]


DEMO_BANK_MOVEMENTS: List[Dict[str, Any]] = [
    {
        "movement_id": "DEMO-SPLIT-001",
        "amount": 250.0,
        "days_ago": 6,
        "description": "Cargo BBVA - Consultores MX",
        "bank": "BBVA",
        "tags": ["tarjeta_empresa"],
        "linked_expense": "consultoria",
    },
    {
        "movement_id": "DEMO-SPLIT-002",
        "amount": 125.0,
        "days_ago": 5,
        "description": "Cargo BBVA - Consultores MX",
        "bank": "BBVA",
        "tags": ["tarjeta_empresa"],
        "linked_expense": "consultoria",
    },
    {
        "movement_id": "DEMO-MOV-001",
        "amount": 845.32,
        "days_ago": 4,
        "description": "Cargo corporativo Pemex",
        "bank": "BBVA",
        "tags": ["tarjeta_empresa", "combustible"],
        "linked_expense": "combustible",
    },
    {
        "movement_id": "DEMO-MOV-002",
        "amount": 520.0,
        "days_ago": 18,
        "description": "Transferencia SaaS CRM",
        "bank": "Santander",
        "tags": ["transferencia", "software"],
        "linked_expense": "suscripcion",
    },
]


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
    payment_account_id: Optional[int] = None,
    paid_by: str = "company_account",
    will_have_cfdi: bool = True,
    bank_status: str = "pendiente",
    external_reference: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    company_id: str = "default",
    is_advance: bool = False,
    is_ppd: bool = False,
    asset_class: Optional[str] = None,
    payment_terms: Optional[str] = None,
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
    normalized_company_id = company_id or "default"

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
                    payment_account_id,
                    paid_by,
                    will_have_cfdi,
                    bank_status,
                    company_id,
                    metadata,
                    is_advance,
                    is_ppd,
                    asset_class,
                    payment_terms,
                    last_payment_date,
                    total_paid,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    payment_account_id,
                    paid_by,
                    int(will_have_cfdi),
                    bank_status,
                    normalized_company_id,
                    metadata_json,
                    int(bool(is_advance)),
                    int(bool(is_ppd)),
                    asset_class,
                    payment_terms,
                    None,
                    0.0,
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
    data["company_id"] = data.get("company_id") or "default"
    data["is_advance"] = bool(data.get("is_advance", 0))
    data["is_ppd"] = bool(data.get("is_ppd", 0))
    data["asset_class"] = data.get("asset_class")
    data["payment_terms"] = data.get("payment_terms")
    data["last_payment_date"] = data.get("last_payment_date")
    data["total_paid"] = float(data.get("total_paid") or 0.0)
    return data


def fetch_expense_records(
    *,
    limit: int = 100,
    invoice_status: Optional[str] = None,
    category: Optional[str] = None,
    month: Optional[str] = None,
    company_id: Optional[str] = None,
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
    if company_id:
        conditions.append("company_id = ?")
        params.append(company_id)

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


def list_expense_payments(expense_id: int) -> List[Dict[str, Any]]:
    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT *
              FROM expense_payments
             WHERE expense_id = ?
             ORDER BY datetime(payment_date) ASC, id ASC
            """,
            (expense_id,),
        ).fetchall()

    payments: List[Dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["metadata"] = json.loads(payload["metadata"]) if payload.get("metadata") else {}
        payments.append(payload)
    return payments


def _fetch_expense_company(expense_id: int) -> Optional[str]:
    with sqlite3.connect(_get_db_path()) as connection:
        row = connection.execute(
            "SELECT company_id FROM expense_records WHERE id = ?",
            (expense_id,),
        ).fetchone()
        if not row:
            return None
        return row[0] or "default"


def create_expense_payment(
    expense_id: int,
    *,
    amount: float,
    payment_date: str,
    bank_movement_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    company_id = _fetch_expense_company(expense_id)
    if company_id is None:
        raise ValueError(f"Expense {expense_id} not found")

    now = datetime.utcnow().isoformat()
    metadata_json = json.dumps(metadata) if metadata else None

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            cursor = connection.execute(
                """
                INSERT INTO expense_payments (
                    expense_id,
                    amount,
                    payment_date,
                    bank_movement_id,
                    metadata,
                    company_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expense_id,
                    amount,
                    payment_date,
                    bank_movement_id,
                    metadata_json,
                    company_id,
                    now,
                    now,
                ),
            )

            connection.execute(
                """
                UPDATE expense_records
                   SET total_paid = COALESCE(total_paid, 0) + ?,
                       last_payment_date = ?
                 WHERE id = ?
                """,
                (amount, payment_date, expense_id),
            )

            connection.commit()
            payment_id = int(cursor.lastrowid)

    _log_expense_event(
        expense_id,
        event_type="payment_registered",
        payload={
            "amount": amount,
            "payment_date": payment_date,
            "bank_movement_id": bank_movement_id,
        },
        actor=actor,
    )

    payments = list_expense_payments(expense_id)
    for payment in payments:
        if payment["id"] == payment_id:
            return payment

    raise RuntimeError("Failed to retrieve stored payment")


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
        "company_id",
        "ticket_id",
        "is_advance",
        "is_ppd",
        "asset_class",
        "payment_terms",
        "last_payment_date",
        "total_paid",
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
        if key in {"is_advance", "is_ppd"} and value is not None:
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
            row = connection.execute(
                "SELECT company_id FROM expense_records WHERE id = ?",
                (expense_id,),
            ).fetchone()
            company_id = (row[0] if row else None) or "default"
            connection.execute(
                """
                INSERT INTO expense_events (
                    expense_id, company_id, event_type, payload, actor, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    expense_id,
                    company_id,
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
            row = connection.execute(
                "SELECT company_id FROM expense_records WHERE id = ?",
                (expense_id,),
            ).fetchone()
            if not row:
                return None
            company_id = row[0] or "default"
            connection.execute(
                """
                INSERT INTO expense_invoices (
                    expense_id, company_id, uuid, folio, url, issued_at, status, raw_xml, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (expense_id, company_id, uuid, folio, url, issued_at, status, raw_xml, now, now),
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


def fetch_candidate_expenses_for_invoice(
    company_id: str,
    *,
    include_statuses: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Return expenses that are eligible to be matched with an invoice."""

    statuses = tuple(include_statuses or ("pendiente", "registrada", "pendiente_factura"))

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, description, amount, expense_date, provider_name, provider_rfc,
                       invoice_status, bank_status, metadata, will_have_cfdi,
                       created_at, updated_at
                  FROM expense_records
                 WHERE company_id = ?
                   AND invoice_status IN ({placeholders})
                """.format(placeholders=",".join("?" for _ in statuses)),
                (company_id, *statuses),
            ).fetchall()

    candidates: List[Dict[str, Any]] = []
    for row in rows:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        metadata = metadata or {}

        candidate = {
            "id": row["id"],
            "descripcion": row["description"],
            "amount": float(row["amount"] or 0.0),
            "expense_date": row["expense_date"],
            "provider_name": row["provider_name"],
            "provider_rfc": row["provider_rfc"] or metadata.get("proveedor", {}).get("rfc"),
            "invoice_status": row["invoice_status"],
            "bank_status": row["bank_status"],
            "metadata": metadata,
            "will_have_cfdi": bool(row["will_have_cfdi"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        candidates.append(candidate)

    return candidates


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

def list_bank_movements(
    *,
    limit: int = 100,
    include_matched: bool = True,
    company_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return bank movements from the internal database."""

    query = (
        "SELECT id, movement_id, movement_date, description, amount, currency, bank, reference, "
        "tags, account, movement_type, balance, metadata, expense_id, company_id, created_at, updated_at "
        "FROM bank_movements"
    )
    clauses: List[str] = []
    if not include_matched:
        clauses.append(
            "movement_id NOT IN (SELECT movement_id FROM bank_match_feedback WHERE decision = 'accepted')"
        )
    if company_id:
        clauses.append("company_id = ?")

    params: List[Any] = []
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
        if company_id:
            params.append(company_id)
    query += " ORDER BY movement_date DESC LIMIT ?"

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(query, (*params, limit)).fetchall()
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
    company_id: str = "default",
) -> None:
    """Insert or update a bank movement."""

    payload_tags = json.dumps(tags) if tags else None
    payload_metadata = json.dumps(metadata) if metadata else None
    normalized_company_id = company_id or "default"
    now = datetime.utcnow().isoformat()

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute(
                """
                INSERT INTO bank_movements (
                    movement_id, movement_date, description, amount, currency,
                    bank, reference, tags, account, movement_type, balance, metadata,
                    expense_id, company_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    company_id = excluded.company_id,
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
                    normalized_company_id,
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
    company_id: str = "default",
) -> None:
    """Store feedback for a bank reconciliation suggestion."""

    now = datetime.utcnow().isoformat()
    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute(
                """
                INSERT INTO bank_match_feedback (
                    expense_id,
                    company_id,
                    movement_id,
                    confidence,
                    decision,
                    notes,
                    metadata,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expense_id,
                    company_id or "default",
                    movement_id,
                    confidence,
                    decision,
                    notes,
                    json.dumps(metadata) if metadata else None,
                    now,
                ),
            )
            connection.commit()


def get_user_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    """Return a user record matching the normalized identifier, if present."""

    normalized = (identifier or "").strip().lower()
    if not normalized:
        return None

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, identifier, identifier_type, display_name, company_id, created_at, updated_at"
            "  FROM users WHERE identifier = ?",
            (normalized,),
        ).fetchone()
        return dict(row) if row else None


def register_user_account(
    *,
    identifier: str,
    identifier_type: str,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a user if needed and seed demo data for their workspace."""

    normalized = (identifier or "").strip().lower()
    if not normalized:
        raise ValueError("Identifier must not be empty")

    user_record: Optional[Dict[str, Any]] = None
    created = False

    with _DB_LOCK:
        with sqlite3.connect(_get_db_path()) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.row_factory = sqlite3.Row

            existing = connection.execute(
                "SELECT id, identifier, identifier_type, display_name, company_id, created_at, updated_at"
                "  FROM users WHERE identifier = ?",
                (normalized,),
            ).fetchone()

            if existing:
                user_record = dict(existing)
            else:
                company_id = f"cmp_{uuid.uuid4().hex[:8]}"
                now = datetime.utcnow().isoformat()
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        identifier,
                        identifier_type,
                        display_name,
                        company_id,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (normalized, identifier_type, display_name, company_id, now, now),
                )
                connection.commit()

                user_record = {
                    "id": int(cursor.lastrowid),
                    "identifier": normalized,
                    "identifier_type": identifier_type,
                    "display_name": display_name,
                    "company_id": company_id,
                    "created_at": now,
                    "updated_at": now,
                }
                created = True

    if not user_record:
        raise RuntimeError("Failed to register user")

    if created:
        create_demo_workspace(user_record["company_id"])

    user_record["created"] = created
    return user_record


def create_demo_workspace(company_id: str) -> Dict[str, Any]:
    """Populate demo expenses and movements for a company workspace."""

    if not company_id:
        raise ValueError("company_id must be provided")

    existing = fetch_expense_records(company_id=company_id, limit=1)
    if existing:
        return {"created": False, "company_id": company_id}

    now = datetime.utcnow()
    expense_ids: Dict[str, int] = {}

    for blueprint in DEMO_EXPENSE_BLUEPRINTS:
        expense_date = (now - timedelta(days=blueprint.get("days_ago", 0))).date().isoformat()
        provider = blueprint.get("provider") or {}
        metadata_payload = dict(blueprint.get("metadata") or {})
        metadata_payload.setdefault("demo", True)
        metadata_payload.setdefault("scenario", "onboarding")
        if blueprint.get("linked_movements"):
            metadata_payload.setdefault(
                "movimientos_bancarios",
                [{"movement_id": movement_id} for movement_id in blueprint["linked_movements"]],
            )

        expense_id = record_internal_expense(
            description=blueprint["description"],
            amount=float(blueprint["amount"]),
            account_code=None,
            expense_date=expense_date,
            category=blueprint.get("category"),
            provider_name=provider.get("nombre"),
            provider_rfc=provider.get("rfc"),
            workflow_status=blueprint.get("workflow_status", "capturado"),
            invoice_status=blueprint.get("invoice_status", "pendiente"),
            bank_status=blueprint.get("bank_status", "pendiente"),
            payment_method=blueprint.get("payment_method"),
            paid_by=blueprint.get("paid_by", "company_account"),
            will_have_cfdi=blueprint.get("will_have_cfdi", True),
            tax_metadata=blueprint.get("tax_metadata"),
            invoice_uuid=(blueprint.get("invoice") or {}).get("uuid"),
            metadata=metadata_payload,
            company_id=company_id,
        )

        invoice_info = blueprint.get("invoice")
        if invoice_info:
            register_expense_invoice(
                expense_id,
                uuid=invoice_info.get("uuid"),
                folio=invoice_info.get("folio"),
                url=invoice_info.get("url"),
                issued_at=invoice_info.get("issued_at"),
                status=invoice_info.get("status", "registrada"),
                actor="onboarding",
            )
            if blueprint.get("mark_invoiced"):
                mark_expense_invoiced(expense_id, actor="onboarding")

        if blueprint.get("invoice_status") == "sin_factura":
            mark_expense_without_invoice(expense_id, actor="onboarding")

        expense_ids[blueprint["key"]] = expense_id

    for movement in DEMO_BANK_MOVEMENTS:
        movement_date = (now - timedelta(days=movement.get("days_ago", 0))).date().isoformat()
        linked_key = movement.get("linked_expense")
        record_bank_movement(
            movement_id=movement["movement_id"],
            movement_date=movement_date,
            description=movement.get("description", "Movimiento demo"),
            amount=float(movement.get("amount", 0.0)),
            bank=movement.get("bank", "DemoBank"),
            tags=movement.get("tags"),
            metadata={"demo": True, "scenario": "onboarding"},
            expense_id=expense_ids.get(linked_key),
            company_id=company_id,
        )

    return {"created": True, "company_id": company_id}


def get_company_demo_snapshot(company_id: str) -> Dict[str, Any]:
    """Return aggregated stats for a company workspace."""

    summary = {
        "total_expenses": 0,
        "total_amount": 0.0,
        "invoice_breakdown": {},
        "last_expense_date": None,
    }

    with sqlite3.connect(_get_db_path()) as connection:
        connection.row_factory = sqlite3.Row

        totals = connection.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(amount), 0) AS amount"
            "  FROM expense_records WHERE company_id = ?",
            (company_id,),
        ).fetchone()

        if totals:
            summary["total_expenses"] = int(totals["total"])
            summary["total_amount"] = float(totals["amount"] or 0.0)

        breakdown_rows = connection.execute(
            "SELECT invoice_status, COUNT(*) AS total"
            "  FROM expense_records WHERE company_id = ? GROUP BY invoice_status",
            (company_id,),
        ).fetchall()
        summary["invoice_breakdown"] = {
            (row["invoice_status"] or "pendiente"): int(row["total"])
            for row in breakdown_rows
        }

        last_row = connection.execute(
            "SELECT MAX(expense_date) AS last_date"
            "  FROM expense_records WHERE company_id = ?",
            (company_id,),
        ).fetchone()
        if last_row and last_row["last_date"]:
            summary["last_expense_date"] = last_row["last_date"]

    return summary


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
    "register_user_account",
    "get_user_by_identifier",
    "create_demo_workspace",
    "get_company_demo_snapshot",
]
