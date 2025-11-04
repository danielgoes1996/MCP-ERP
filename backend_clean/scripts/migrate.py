#!/usr/bin/env python3
"""CLI para ejecutar migraciones del ERP interno."""

import argparse
import logging
import sqlite3
from datetime import datetime
from typing import List

from core.internal_db import _get_db_path, initialize_internal_database, SCHEMA_MIGRATIONS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def list_migrations(applied_only: bool = False) -> None:
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            initialize_internal_database()
            rows = connection.execute(
                "SELECT name, applied_at FROM schema_versions ORDER BY id"
            ).fetchall()
    except sqlite3.Error as exc:
        logger.error("No se pudo leer schema_versions: %s", exc)
        rows = []

    applied = {row['name']: row['applied_at'] for row in rows}

    for migration in SCHEMA_MIGRATIONS:
        name = migration['name']
        applied_at = applied.get(name)
        status = "✔" if applied_at else "✗"
        if applied_only and not applied_at:
            continue
        print(f"{status} {name}")
        if applied_at:
            print(f"    aplicado en {applied_at}")


def apply_migrations() -> None:
    logger.info("Aplicando migraciones pendientes")
    initialize_internal_database()
    logger.info("Migraciones aplicadas correctamente")


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(description="Migrador ERP interno")
    subparsers = parser.add_subparsers(dest='command')

    subparsers.add_parser('up', help='Aplica migraciones pendientes')

    list_parser = subparsers.add_parser('list', help='Listar migraciones')
    list_parser.add_argument('--applied', action='store_true', help='Sólo mostrar migraciones aplicadas')

    args = parser.parse_args(argv)

    if args.command == 'up':
        apply_migrations()
    elif args.command == 'list':
        list_migrations(applied_only=args.applied)
    else:
        parser.print_help()


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
