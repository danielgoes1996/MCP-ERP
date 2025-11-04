usa"""Apply conciliation/SAT schema enhancements on legacy SQLite (pre-3.35).

Executes the changes from `2025_10_20_conciliation_enhancements.sql`, but guards
column additions manually using PRAGMA checks so it works even when SQLite does
not support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("unified_mcp_system.db")

# Columns to add per table (name -> SQL fragment)
COLUMN_MAP = {
    "expense_records": {
        "moneda": "TEXT DEFAULT 'MXN'",
        "tipo_cambio": "REAL DEFAULT 1.0",
        "deducible_status": "TEXT DEFAULT 'pendiente'",antes 
        "deducible_percent": "REAL DEFAULT 100.0",
        "iva_acreditable": "BOOLEAN DEFAULT 1",
        "periodo": "TEXT",
    },
    "expense_invoices": {
        "metodo_pago": "TEXT",
        "forma_pago": "TEXT",
        "uso_cfdi": "TEXT",
        "tipo_comprobante": "TEXT",
        "tipo_cambio": "REAL DEFAULT 1.0",
        "relacionado_con_uuid": "TEXT",
        "status": "TEXT DEFAULT 'vigente'",
    },
    "bank_movements": {
        "moneda": "TEXT DEFAULT 'MXN'",
        "tipo_cambio": "REAL DEFAULT 1.0",
        "bank_import_fingerprint": "TEXT",
        "context_confidence": "REAL",
        "bank_context": "TEXT",
        "extra_data": "TEXT",
    },
    "polizas_contables": {
        "estatus": "TEXT DEFAULT 'draft'",
        "version": "INTEGER DEFAULT 1",
        "replaces_poliza_id": "INTEGER",
        "fecha": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "periodo": "TEXT",
        "tipo": "TEXT",
    },
    "polizas_detalle": {
        "uuid_cfdi": "TEXT",
        "rfc_tercero": "TEXT",
        "forma_pago": "TEXT",
        "metodo_pago": "TEXT",
        "moneda": "TEXT DEFAULT 'MXN'",
        "tipo_cambio": "REAL DEFAULT 1.0",
        "codigo_agrupador_sat": "TEXT",
    },
}

NEW_TABLES = {
    "bank_match_links": """
        CREATE TABLE bank_match_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_movement_id INTEGER NOT NULL REFERENCES bank_movements(id) ON DELETE CASCADE,
            expense_id INTEGER REFERENCES expense_records(id),
            cfdi_uuid TEXT REFERENCES expense_invoices(uuid),
            monto_asignado REAL NOT NULL,
            score REAL,
            source TEXT CHECK (source IN ('regla','ia','manual')),
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            tenant_id INTEGER,
            UNIQUE (bank_movement_id, expense_id, cfdi_uuid)
        )
    """,
    "cfdi_payments": """
        CREATE TABLE cfdi_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid_pago TEXT NOT NULL UNIQUE,
            fecha_pago TIMESTAMP NOT NULL,
            moneda TEXT DEFAULT 'MXN',
            tipo_cambio REAL DEFAULT 1.0,
            tenant_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "payment_applications": """
        CREATE TABLE payment_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid_pago TEXT NOT NULL REFERENCES cfdi_payments(uuid_pago) ON DELETE CASCADE,
            cfdi_uuid TEXT NOT NULL REFERENCES expense_invoices(uuid),
            no_parcialidad INTEGER NOT NULL,
            monto_pagado REAL NOT NULL,
            saldo_insoluto REAL NOT NULL,
            moneda TEXT DEFAULT 'MXN',
            tipo_cambio REAL DEFAULT 1.0,
            fecha_pago TIMESTAMP NOT NULL,
            tenant_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (uuid_pago, cfdi_uuid, no_parcialidad)
        )
    """,
}

INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_records_cfdi_uuid_unique ON expense_records(cfdi_uuid)",
    "CREATE INDEX IF NOT EXISTS idx_expense_records_periodo ON expense_records(periodo, tenant_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_invoices_uuid_unique ON expense_invoices(uuid)",
    "CREATE INDEX IF NOT EXISTS idx_expense_invoices_rfc_total_fecha ON expense_invoices(rfc_emisor, total, fecha_emision)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_bank_movements_fingerprint ON bank_movements(bank_import_fingerprint)",
    "CREATE INDEX IF NOT EXISTS idx_bank_movements_fecha_monto ON bank_movements(date, amount)",
    "CREATE INDEX IF NOT EXISTS idx_polizas_detalle_order ON polizas_detalle(poliza_id, orden)",
    "CREATE INDEX IF NOT EXISTS idx_bank_match_links_movement ON bank_match_links(bank_movement_id)",
    "CREATE INDEX IF NOT EXISTS idx_bank_match_links_cfdi ON bank_match_links(cfdi_uuid)",
    "CREATE INDEX IF NOT EXISTS idx_payment_applications_cfdi ON payment_applications(cfdi_uuid)",
)


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def add_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    if not column_exists(cursor, table, column):
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        cursor.execute(sql)


def create_table_if_missing(cursor: sqlite3.Cursor, table: str, ddl: str) -> None:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    if cursor.fetchone() is None:
        cursor.execute(ddl)


def run_updates(cursor: sqlite3.Cursor) -> None:
    cursor.execute("UPDATE expense_records SET moneda = COALESCE(moneda, currency)")
    cursor.execute("UPDATE expense_records SET tipo_cambio = COALESCE(tipo_cambio, 1.0)")
    cursor.execute("UPDATE expense_records SET deducible_status = COALESCE(deducible_status, 'pendiente')")
    cursor.execute("UPDATE expense_records SET deducible_percent = COALESCE(deducible_percent, 100.0)")
    cursor.execute("UPDATE expense_records SET iva_acreditable = COALESCE(iva_acreditable, 1)")
    cursor.execute("UPDATE expense_invoices SET status = COALESCE(status, 'vigente')")
    cursor.execute("UPDATE expense_invoices SET tipo_cambio = COALESCE(tipo_cambio, 1.0)")
    cursor.execute("UPDATE bank_movements SET moneda = COALESCE(moneda, 'MXN')")
    cursor.execute("UPDATE bank_movements SET tipo_cambio = COALESCE(tipo_cambio, 1.0)")
    cursor.execute("UPDATE polizas_detalle SET moneda = COALESCE(moneda, 'MXN')")
    cursor.execute("UPDATE polizas_detalle SET tipo_cambio = COALESCE(tipo_cambio, 1.0)")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        for table, columns in COLUMN_MAP.items():
            for column, definition in columns.items():
                add_column(cursor, table, column, definition)

        for table, ddl in NEW_TABLES.items():
            create_table_if_missing(cursor, table, ddl)

        for index_sql in INDEXES:
            cursor.execute(index_sql)

        run_updates(cursor)
        conn.commit()

        print("✅ Conciliation enhancements applied successfully")


if __name__ == "__main__":
    main()
