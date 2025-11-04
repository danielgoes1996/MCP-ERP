#!/usr/bin/env python3
"""Utility to import SAT catalog CSV files into the local SQLite database.

Usage examples:

    python scripts/import_sat_catalogs.py \
        --db unified_mcp_system.db \
        --accounts-csv data/sat_catalog/accounts.csv \
        --products-csv data/sat_catalog/products.csv \
        --deactivate-missing

The script assumes UTF-8 encoded CSV files and will upsert rows based on
SAT codes. When --deactivate-missing is provided, any code not present in
the new dataset will be marked as inactive instead of being deleted.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
import unicodedata
from typing import Dict, Iterable, List, Optional, Tuple

ACCOUNT_COLUMNS = {
    "code": {"code", "codigo", "código", "codigo_agrupador", "código_agrupador"},
    "name": {
        "name",
        "nombre",
        "nombre_de_la_cuenta_y_o_subcuenta",
        "nombre_de_la_cuenta",
    },
    "description": {"description", "descripcion", "descripción"},
    "parent_code": {"parent_code", "codigo_padre", "código_padre"},
    "type": {"type", "tipo", "nivel"},
    "is_active": {"is_active", "activo"},
}

PRODUCT_COLUMNS = {
    "code": {"code", "clave", "clave_prodserv", "claveprodserv"},
    "name": {"name", "descripcion", "description", "descripción"},
    "description": {"description", "descripcion", "descripción"},
    "unit_key": {"unit_key", "clave_unidad", "unidad"},
    "is_active": {"is_active", "activo"},
}


def _normalize_header(header: str) -> str:
    normalized = unicodedata.normalize('NFKD', header).encode('ascii', 'ignore').decode('ascii')
    normalized = normalized.strip().lower()
    for char in (" ", "/", "-", ".", "(", ")"):
        normalized = normalized.replace(char, "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _build_alias_lookup(headers: Iterable[str]) -> Dict[str, str]:
    return {_normalize_header(h): h for h in headers}


def _extract(row: Dict[str, str], lookup: Dict[str, str], aliases: Iterable[str]) -> Optional[str]:
    for alias in aliases:
        key = _normalize_header(alias)
        source = lookup.get(key)
        if source is not None:
            value = row.get(source)
            if value is not None and value != "":
                return value.strip()
    return None


def _read_irregular_csv(handle) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    reader = csv.reader(handle)
    header: Optional[List[str]] = None

    for raw_row in reader:
        cells = [cell.strip() for cell in raw_row]
        if not any(cells):
            continue
        lower = [cell.lower() for cell in cells]
        if cells and lower[0].startswith("nivel") and len(cells) >= 2 and "código" in lower[1]:
            header = cells
            break

    if header is None:
        raise ValueError("No se encontró encabezado válido en el CSV proporcionado")

    fieldnames: List[str] = []
    for idx, name in enumerate(header):
        value = name.strip() or f"col_{idx}"
        fieldnames.append(value)

    rows: List[Dict[str, str]] = []
    for raw_row in reader:
        if not any(cell.strip() for cell in raw_row):
            continue
        values: Dict[str, str] = {}
        for idx, field in enumerate(fieldnames):
            cell = raw_row[idx].strip() if idx < len(raw_row) else ""
            values[field] = cell
        rows.append(values)

    lookup = _build_alias_lookup(fieldnames)
    return rows, lookup


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    if normalized in {"0", "false", "no", "inactive", "inactivo"}:
        return False
    return True


def _import_catalog(
    conn: sqlite3.Connection,
    csv_path: Path,
    column_map: Dict[str, Iterable[str]],
    table: str,
    deactivate_missing: bool,
) -> Tuple[int, int]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        use_regular = (
            reader.fieldnames
            and len(reader.fieldnames) > 1
            and None not in reader.fieldnames
            and any(fn.strip() for fn in reader.fieldnames)
        )

        if use_regular:
            lookup = _build_alias_lookup(reader.fieldnames)
            rows_iter: Iterable[Dict[str, str]] = reader
        else:
            handle.seek(0)
            rows_list, lookup = _read_irregular_csv(handle)
            rows_iter = rows_list

        seen_codes = set()
        inserted = 0
        updated = 0

        for raw_row in rows_iter:
            row = {key: (value.strip() if isinstance(value, str) else value) for key, value in raw_row.items()}

            code = _extract(row, lookup, column_map["code"])
            name = _extract(row, lookup, column_map["name"])
            if not code or not name:
                continue  # skip incomplete rows

            description = _extract(row, lookup, column_map.get("description", []))
            parent_code = _extract(row, lookup, column_map.get("parent_code", []))
            entry_type = _extract(row, lookup, column_map.get("type", [])) or "agrupador"
            unit_key = _extract(row, lookup, column_map.get("unit_key", []))
            is_active = _parse_bool(_extract(row, lookup, column_map.get("is_active", [])))

            # Derive parent code if missing and code looks hierarchical
            if not parent_code and "." in code:
                parent_code = ".".join(code.split('.')[:-1]) or code.split('.')[0]

            # Normalize entry type using level info when possible
            if entry_type and entry_type.isdigit():
                entry_type = "agrupador" if entry_type == "1" else "subcuenta"

            seen_codes.add(code)
            if table == "sat_account_catalog":
                cursor = conn.execute(
                    """
                    INSERT INTO sat_account_catalog (
                        code, name, description, parent_code, type, is_active, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(code) DO UPDATE SET
                        name=excluded.name,
                        description=excluded.description,
                        parent_code=excluded.parent_code,
                        type=excluded.type,
                        is_active=excluded.is_active,
                        updated_at=datetime('now')
                    """,
                    (
                        code,
                        name,
                        description,
                        parent_code,
                        entry_type,
                        int(is_active),
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO sat_product_service_catalog (
                        code, name, description, unit_key, is_active, updated_at
                    ) VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(code) DO UPDATE SET
                        name=excluded.name,
                        description=excluded.description,
                        unit_key=excluded.unit_key,
                        is_active=excluded.is_active,
                        updated_at=datetime('now')
                    """,
                    (
                        code,
                        name,
                        description,
                        unit_key,
                        int(is_active),
                    ),
                )

            if cursor.rowcount == 1 and cursor.lastrowid:
                inserted += 1
            else:
                updated += 1

    if deactivate_missing and seen_codes:
        placeholders = ",".join(["?"] * len(seen_codes))
        conn.execute(
            f"UPDATE {table} SET is_active = 0, updated_at = datetime('now') "
            f"WHERE code NOT IN ({placeholders})",
            tuple(seen_codes),
        )

    return inserted, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa catálogos SAT a SQLite")
    parser.add_argument("--db", default="unified_mcp_system.db", help="Ruta a la base SQLite")
    parser.add_argument("--accounts-csv", help="CSV del catálogo de cuentas SAT")
    parser.add_argument("--products-csv", help="CSV del catálogo de productos/servicios CFDI")
    parser.add_argument(
        "--deactivate-missing",
        action="store_true",
        help="Marcar como inactivos los códigos no presentes en la importación",
    )

    args = parser.parse_args()

    if not args.accounts_csv and not args.products_csv:
        parser.error("Debes proporcionar al menos --accounts-csv o --products-csv")

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        parser.error(f"La base de datos {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    try:
        inserted_total = 0
        updated_total = 0

        if args.accounts_csv:
            accounts_path = Path(args.accounts_csv).expanduser()
            if not accounts_path.exists():
                parser.error(f"El archivo {accounts_path} no existe")
            ins, upd = _import_catalog(
                conn,
                accounts_path,
                ACCOUNT_COLUMNS,
                "sat_account_catalog",
                args.deactivate_missing,
            )
            inserted_total += ins
            updated_total += upd
            print(f"Cuenta SAT: {ins} insertados, {upd} actualizados")

        if args.products_csv:
            products_path = Path(args.products_csv).expanduser()
            if not products_path.exists():
                parser.error(f"El archivo {products_path} no existe")
            ins, upd = _import_catalog(
                conn,
                products_path,
                PRODUCT_COLUMNS,
                "sat_product_service_catalog",
                args.deactivate_missing,
            )
            inserted_total += ins
            updated_total += upd
            print(f"Productos/Servicios SAT: {ins} insertados, {upd} actualizados")

        conn.commit()
        print(f"Importación completada. Total insertados={inserted_total}, actualizados={updated_total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
