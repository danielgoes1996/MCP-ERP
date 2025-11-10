#!/usr/bin/env python3
"""
Configuración centralizada de base de datos
Evita errores de conexión y proporciona validación de esquema
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional

# Configuración de PostgreSQL
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
    "port": int(os.getenv("POSTGRES_PORT", 5433)),
    "database": os.getenv("POSTGRES_DB", "mcp_system"),
    "user": os.getenv("POSTGRES_USER", "mcp_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme")
}

# Esquema validado de tablas
TABLE_SCHEMAS = {
    "expense_invoices": {
        "id": "integer",
        "tenant_id": "integer",
        "company_id": "integer",
        "filename": "varchar(500)",
        "uuid": "varchar(36)",
        "rfc_emisor": "varchar(13)",
        "nombre_emisor": "varchar(500)",  # ✅ Correcto
        "rfc_receptor": "varchar(13)",
        "nombre_receptor": "varchar(500)",
        "fecha_emision": "timestamp",
        "fecha_timbrado": "timestamp",
        "subtotal": "double precision",
        "iva_amount": "double precision",
        "total": "double precision",
        "currency": "varchar(10)",
        "tipo_comprobante": "varchar(10)",
        "forma_pago": "varchar(50)",
        "metodo_pago": "varchar(50)",
        "uso_cfdi": "varchar(10)",
        # Campos de conciliación
        "linked_expense_id": "integer",  # ✅ -1=AMEX, >0=bank_tx, NULL=pendiente
        "match_confidence": "double precision",
        "match_method": "varchar(100)",  # ✅ MÁXIMO 100 caracteres
        "match_date": "timestamp",
        "raw_xml": "text",
    },
    "bank_transactions": {
        "id": "integer",
        "statement_id": "integer",
        "transaction_date": "date",
        "description": "text",
        "amount": "numeric",
        "balance": "numeric",
        "transaction_type": "varchar(50)",
        # Campos de conciliación
        "reconciled_invoice_id": "integer",
        "match_confidence": "double precision",
        "reconciliation_status": "varchar(50)",
        "reconciled_at": "timestamp",
    }
}

# Límites de longitud de campos
FIELD_LIMITS = {
    "expense_invoices.match_method": 100,
    "expense_invoices.nombre_emisor": 500,
    "expense_invoices.rfc_emisor": 13,
}


def get_connection(dict_cursor=False):
    """
    Obtener conexión a PostgreSQL con configuración validada

    Args:
        dict_cursor: Si True, usa RealDictCursor para resultados como diccionarios

    Returns:
        Conexión a PostgreSQL
    """
    try:
        if dict_cursor:
            conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
        else:
            conn = psycopg2.connect(**POSTGRES_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Error de conexión a PostgreSQL:")
        print(f"   Host: {POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}")
        print(f"   Database: {POSTGRES_CONFIG['database']}")
        print(f"   User: {POSTGRES_CONFIG['user']}")
        print(f"   Error: {e}")
        raise


def validate_column_exists(table: str, column: str) -> bool:
    """
    Validar que una columna existe en una tabla

    Args:
        table: Nombre de la tabla
        column: Nombre de la columna

    Returns:
        True si existe, False si no
    """
    if table in TABLE_SCHEMAS:
        return column in TABLE_SCHEMAS[table]

    # Si no está en el esquema, consultar la BD
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists


def get_table_columns(table: str) -> List[str]:
    """
    Obtener todas las columnas de una tabla

    Args:
        table: Nombre de la tabla

    Returns:
        Lista de nombres de columnas
    """
    if table in TABLE_SCHEMAS:
        return list(TABLE_SCHEMAS[table].keys())

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return columns


def truncate_field(table: str, field: str, value: str) -> str:
    """
    Truncar un campo al límite permitido

    Args:
        table: Nombre de la tabla
        field: Nombre del campo
        value: Valor a truncar

    Returns:
        Valor truncado si es necesario
    """
    key = f"{table}.{field}"
    if key in FIELD_LIMITS:
        limit = FIELD_LIMITS[key]
        if len(value) > limit:
            return value[:limit]
    return value


def safe_update_invoice_reconciliation(
    cursor,
    cfdi_id: int,
    linked_expense_id: Optional[int],
    match_method: str,
    match_confidence: float = 1.0
) -> bool:
    """
    Actualizar conciliación de CFDI de forma segura

    Args:
        cursor: Cursor de PostgreSQL
        cfdi_id: ID del CFDI
        linked_expense_id: ID de transacción bancaria (-1 para AMEX, >0 para banco)
        match_method: Descripción del método (se truncará a 100 caracteres)
        match_confidence: Nivel de confianza (0-1)

    Returns:
        True si se actualizó, False si no
    """
    # Truncar match_method a 100 caracteres
    match_method = truncate_field("expense_invoices", "match_method", match_method)

    cursor.execute("""
        UPDATE expense_invoices
        SET
            linked_expense_id = %s,
            match_confidence = %s,
            match_method = %s,
            match_date = NOW()
        WHERE id = %s
        AND linked_expense_id IS NULL
    """, (linked_expense_id, match_confidence, match_method, cfdi_id))

    return cursor.rowcount > 0


def safe_update_bank_reconciliation(
    cursor,
    bank_tx_id: int,
    cfdi_id: int,
    match_confidence: float = 0.95,
    reconciliation_status: str = 'auto'
) -> bool:
    """
    Actualizar conciliación de transacción bancaria de forma segura

    Args:
        cursor: Cursor de PostgreSQL
        bank_tx_id: ID de transacción bancaria
        cfdi_id: ID del CFDI
        match_confidence: Nivel de confianza (0-1)
        reconciliation_status: Estado ('auto' o 'manual')

    Returns:
        True si se actualizó, False si no
    """
    cursor.execute("""
        UPDATE bank_transactions
        SET
            reconciled_invoice_id = %s,
            match_confidence = %s,
            reconciliation_status = %s,
            reconciled_at = NOW()
        WHERE id = %s
        AND reconciled_invoice_id IS NULL
    """, (cfdi_id, match_confidence, reconciliation_status, bank_tx_id))

    return cursor.rowcount > 0


def get_reconciliation_summary(year: int, month: int) -> Dict:
    """
    Obtener resumen de conciliación para un mes

    Args:
        year: Año
        month: Mes (1-12)

    Returns:
        Diccionario con estadísticas de conciliación
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total_cfdis,
            COUNT(*) FILTER (WHERE linked_expense_id IS NOT NULL) as conciliados,
            SUM(total) as monto_total,
            SUM(total) FILTER (WHERE linked_expense_id IS NOT NULL) as monto_conciliado,
            COUNT(*) FILTER (WHERE linked_expense_id = -1) as pagos_amex,
            COUNT(*) FILTER (WHERE linked_expense_id > 0) as pagos_banco,
            SUM(total) FILTER (WHERE linked_expense_id = -1) as monto_amex,
            SUM(total) FILTER (WHERE linked_expense_id > 0) as monto_banco
        FROM expense_invoices
        WHERE EXTRACT(YEAR FROM fecha_emision) = %s
        AND EXTRACT(MONTH FROM fecha_emision) = %s
        AND tipo_comprobante = 'I'
    """, (year, month))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        total, conciliados, monto_total, monto_conciliado, pagos_amex, pagos_banco, monto_amex, monto_banco = result
        return {
            "total_cfdis": total or 0,
            "conciliados": conciliados or 0,
            "pendientes": (total or 0) - (conciliados or 0),
            "tasa_conciliacion": (conciliados / total * 100) if total else 0,
            "monto_total": float(monto_total or 0),
            "monto_conciliado": float(monto_conciliado or 0),
            "monto_pendiente": float((monto_total or 0) - (monto_conciliado or 0)),
            "pagos_amex": pagos_amex or 0,
            "pagos_banco": pagos_banco or 0,
            "monto_amex": float(monto_amex or 0),
            "monto_banco": float(monto_banco or 0),
        }

    return {}


# Validar al importar
if __name__ == "__main__":
    print("Validando configuración de base de datos...")

    try:
        conn = get_connection()
        print(f"✅ Conexión exitosa a {POSTGRES_CONFIG['database']}")

        # Validar columnas críticas
        for table, columns in TABLE_SCHEMAS.items():
            print(f"\n📋 Validando tabla: {table}")
            for column in columns.keys():
                if validate_column_exists(table, column):
                    print(f"  ✅ {column}")
                else:
                    print(f"  ❌ {column} NO EXISTE")

        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
