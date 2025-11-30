"""
Adaptador para la base de datos unificada
Mantiene compatibilidad con el código existente mientras usa la nueva DB
"""

import sqlite3
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Sequence, Tuple, Union

from config.config import config

try:
    import psycopg2  # type: ignore
    from psycopg2 import OperationalError as PostgresOperationalError  # type: ignore
    from psycopg2 import ProgrammingError as PostgresProgrammingError  # type: ignore
    from psycopg2.extras import RealDictConnection, RealDictCursor  # type: ignore
    from psycopg2 import errors as psycopg2_errors  # type: ignore
except ImportError:  # pragma: no cover - psycopg2 is optional unless Postgres is enabled
    psycopg2 = None  # type: ignore
    PostgresOperationalError = Exception  # type: ignore
    PostgresProgrammingError = Exception  # type: ignore
    psycopg2_errors = None  # type: ignore

from core.reconciliation.bank.bank_statements_models import MovementKind, infer_movement_kind
from core.sat_catalog_seed import (
    SAT_ACCOUNT_CATALOG_SEED,
    SAT_PRODUCT_SERVICE_CATALOG_SEED,
    validate_category_mapping_integrity,
)
from core.ai_pipeline.classification.classification_feedback import record_feedback

logger = logging.getLogger(__name__)

DatabaseOperationalError = (sqlite3.OperationalError, PostgresOperationalError)

if psycopg2_errors:
    IntegrityErrors = (
        sqlite3.IntegrityError,
        psycopg2_errors.UniqueViolation,
        psycopg2_errors.ForeignKeyViolation,
    )
else:
    IntegrityErrors = (sqlite3.IntegrityError,)

SQLITE_PLACEHOLDER_PATTERN = re.compile(r"\?")


def _convert_sqlite_placeholders(query: str) -> str:
    """Convierte parámetros estilo SQLite (?) a estilo psycopg2 (%s)."""
    return SQLITE_PLACEHOLDER_PATTERN.sub("%s", query)


class PostgresCompatCursor:
    """Cursor que emula la API de sqlite3 sobre psycopg2."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid: Optional[int] = None
        self._last_query_requires_returning = False

    def execute(self, query: str, params: Union[Sequence[Any], Tuple[Any, ...], None] = None):
        original_query = query
        params_tuple = tuple(params) if isinstance(params, list) else params

        # Psycopg2 no entiende PRAGMA: los ignoramos silenciosamente
        if query.lstrip().upper().startswith("PRAGMA"):
            logger.debug("Ignorando instrucción PRAGMA en PostgreSQL: %s", query.strip())
            self.lastrowid = None
            return self

        translated_query = _convert_sqlite_placeholders(query)
        need_returning = translated_query.lstrip().upper().startswith("INSERT ") and "RETURNING" not in translated_query.upper()

        if need_returning:
            translated_query = translated_query.rstrip().rstrip(";")
            translated_query = f"{translated_query} RETURNING *"
            self._last_query_requires_returning = True
        else:
            self._last_query_requires_returning = False

        try:
            self._cursor.execute(translated_query, params_tuple)
            if self._last_query_requires_returning:
                row = self._cursor.fetchone()
                if row is not None:
                    # RealDictCursor devuelve diccionarios
                    self.lastrowid = row.get("id", row.get(list(row.keys())[0] if row else None))
                else:
                    self.lastrowid = None
        except (PostgresOperationalError, PostgresProgrammingError) as exc:
            # Algunos inserts son sobre tablas sin columna id -> reintentar sin RETURNING
            if self._last_query_requires_returning and 'RETURNING' in str(exc):
                logger.debug("Reintentando INSERT sin RETURNING por error: %s", exc)
                self._cursor.execute(_convert_sqlite_placeholders(original_query), params_tuple)
                self.lastrowid = None
            else:
                raise

        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def __getattr__(self, item: str):
        return getattr(self._cursor, item)


class PostgresCompatConnection:
    """Conexión que emula sqlite3.Connection usando psycopg2."""

    def __init__(self, dsn: str):
        if psycopg2 is None:
            raise RuntimeError(
                "psycopg2 no está instalado. Instala psycopg2-binary para usar PostgreSQL."
            )
        # No usar RealDictConnection para mantener compatibilidad con acceso por índice
        self._conn = psycopg2.connect(dsn)
        self._row_factory = None

    def cursor(self):
        return PostgresCompatCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def execute(self, query: str, params: Union[Sequence[Any], Tuple[Any, ...], None] = None):
        cur = self.cursor()
        try:
            return cur.execute(query, params)
        finally:
            cur.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        # Se mantiene por compatibilidad con sqlite3, no se utiliza en PostgreSQL
        self._row_factory = value


class UnifiedDBAdapter:
    """Adaptador que mantiene compatibilidad con funciones existentes"""

    def __init__(self, db_path: str):
        self.use_postgres = config.USE_POSTGRESQL
        self.postgres_dsn = config.POSTGRES_DSN
        self.db_path = Path(db_path) if db_path else Path(config.DB_PATH)

        if self.use_postgres:
            logger.info("🔄 Conectando a PostgreSQL con DSN: %s", self.postgres_dsn)
        else:
            if not self.db_path.exists():
                raise FileNotFoundError(f"DB unificada no encontrada: {db_path}")
            logger.info(f"✅ Conectado a DB unificada: {db_path}")

        if not self.use_postgres:
            self._ensure_accounting_columns()
            self._ensure_sat_catalog_tables()
            self._seed_sat_catalogs()
            self._ensure_provider_rules_table()
            self._ensure_company_context_columns()

    def _normalize_expense_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        metadata = record.get('metadata')
        if isinstance(metadata, str):
            try:
                record['metadata'] = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                record['metadata'] = {}
        elif metadata is None:
            record['metadata'] = {}

        tax_meta = record.get('tax_metadata')
        if isinstance(tax_meta, str):
            try:
                record['tax_metadata'] = json.loads(tax_meta)
            except (json.JSONDecodeError, TypeError):
                record['tax_metadata'] = {}
        elif tax_meta is None:
            record['tax_metadata'] = {}

        record['will_have_cfdi'] = bool(record.get('will_have_cfdi', 0))
        record['moneda'] = record.get('moneda') or record.get('currency') or 'MXN'
        try:
            record['tipo_cambio'] = float(record.get('tipo_cambio') or 1.0)
        except (TypeError, ValueError):
            record['tipo_cambio'] = 1.0
        record['deducible_status'] = record.get('deducible_status') or 'pendiente'
        try:
            record['deducible_percent'] = float(record.get('deducible_percent') or 100.0)
        except (TypeError, ValueError):
            record['deducible_percent'] = 100.0
        record['iva_acreditable'] = bool(record.get('iva_acreditable', 1))
        record['periodo'] = record.get('periodo')
        record['company_id'] = record.get('company_id') or 'default'
        record['is_advance'] = bool(record.get('is_advance', 0))
        record['is_ppd'] = bool(record.get('is_ppd', 0))
        record['total_paid'] = float(record.get('total_paid') or 0.0)
        record['last_payment_date'] = record.get('last_payment_date')
        return record

    def _ensure_accounting_columns(self) -> None:
        """Garantiza columnas adicionales para normalización contable."""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(expense_records)")
                existing = {row[1] for row in cursor.fetchall()}

                def add_column(name: str, definition: str) -> None:
                    if name not in existing:
                        logger.info("🛠️ Añadiendo columna %s a expense_records", name)
                        cursor.execute(f"ALTER TABLE expense_records ADD COLUMN {name} {definition}")

                add_column("descripcion", "TEXT")
                add_column("descripcion_normalizada", "TEXT")
                add_column("descripcion_normalizada_fuente", "TEXT")
                add_column("proveedor_nombre", "TEXT")
                add_column("categoria_normalizada", "TEXT")
                add_column("categoria_slug", "TEXT")
                add_column("categoria_confianza", "REAL")
                add_column("categoria_fuente", "TEXT")
                add_column("categoria", "TEXT")
                add_column("sat_account_code", "TEXT")
                add_column("sat_product_service_code", "TEXT")
                add_column("monto_total", "REAL")
                add_column("needs_reclassification", "INTEGER DEFAULT 0")
                # Fiscal pipeline v1
                add_column("tax_source", "TEXT")
                add_column("explanation_short", "TEXT")
                add_column("explanation_detail", "TEXT")
                add_column("catalog_version", "TEXT DEFAULT 'v1'")
                add_column("classification_source", "TEXT")

                conn.commit()
        except DatabaseOperationalError as exc:
            logger.warning("No se pudieron asegurar columnas adicionales: %s", exc)

    def _ensure_sat_catalog_tables(self) -> None:
        """Garantiza la existencia de tablas para catálogos SAT básicos."""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sat_account_catalog (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        description TEXT,
                        parent_code TEXT,
                        type TEXT DEFAULT 'agrupador',
                        is_active INTEGER NOT NULL DEFAULT 1,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sat_account_catalog_code
                        ON sat_account_catalog(code)
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sat_product_service_catalog (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        description TEXT,
                        unit_key TEXT,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sat_product_service_catalog_code
                        ON sat_product_service_catalog(code)
                    """
                )
                conn.commit()
        except DatabaseOperationalError as exc:
            logger.warning("No se pudieron asegurar tablas SAT: %s", exc)

    def _seed_sat_catalogs(self) -> None:
        """Carga valores semilla mínimos para catálogos SAT."""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()

                existing_accounts = {
                    row[0] for row in cursor.execute("SELECT code FROM sat_account_catalog")
                }
                existing_products = {
                    row[0]
                    for row in cursor.execute(
                        "SELECT code FROM sat_product_service_catalog"
                    )
                }

                for entry in SAT_ACCOUNT_CATALOG_SEED:
                    if entry["code"] in existing_accounts:
                        continue
                    cursor.execute(
                        """
                        INSERT INTO sat_account_catalog (
                            code, name, description, parent_code, type, is_active, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry["code"],
                            entry["name"],
                            entry.get("description"),
                            entry.get("parent_code"),
                            entry.get("type", "agrupador"),
                            int(bool(entry.get("is_active", True))),
                            now,
                        ),
                    )

                for entry in SAT_PRODUCT_SERVICE_CATALOG_SEED:
                    if entry["code"] in existing_products:
                        continue
                    cursor.execute(
                        """
                        INSERT INTO sat_product_service_catalog (
                            code, name, description, unit_key, is_active, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry["code"],
                            entry["name"],
                            entry.get("description"),
                            entry.get("unit_key"),
                            int(bool(entry.get("is_active", True))),
                            now,
                        ),
                    )

                conn.commit()

                account_codes = {
                    row[0]
                    for row in cursor.execute("SELECT code FROM sat_account_catalog")
                }
                product_codes = {
                    row[0]
                    for row in cursor.execute(
                        "SELECT code FROM sat_product_service_catalog"
                    )
                }
                validate_category_mapping_integrity(
                    available_account_codes=account_codes,
                    available_product_service_codes=product_codes,
                )
        except DatabaseOperationalError as exc:
            logger.warning("No se pudieron sembrar catálogos SAT: %s", exc)

    def cleanup_legacy_expenses(
        self,
        *,
        delete: bool = False,
        confidence_threshold: float = 0.7,
        tenant_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, int]:
        """Elimina o marca gastos legacy capturados sin IA o con baja confianza."""

        self._ensure_accounting_columns()

        condition_parts = [
            "classification_source = 'manual_entry'",
            "COALESCE(categoria_confianza, 0) < ?",
        ]
        params: List[Any] = [confidence_threshold]

        where_clause = f"({' OR '.join(condition_parts)})"

        if tenant_id is not None:
            where_clause = f"{where_clause} AND tenant_id = ?"
            params.append(tenant_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM expense_records WHERE {where_clause}",
                params,
            )
            matches = cursor.fetchone()[0] if cursor else 0

            if dry_run:
                return {"matched_expenses": matches}

            if delete:
                cursor.execute(
                    f"DELETE FROM expense_records WHERE {where_clause}",
                    params,
                )
                affected = cursor.rowcount
                conn.commit()
                return {
                    "deleted_expenses": affected,
                    "matched_expenses": matches,
                }

            cursor.execute(
                f"""UPDATE expense_records
                       SET needs_reclassification = 1,
                           updated_at = CURRENT_TIMESTAMP
                     WHERE {where_clause}""",
                params,
            )
            affected = cursor.rowcount
            conn.commit()
            return {
                "marked_for_reclassification": affected,
                "matched_expenses": matches,
            }

    def _ensure_provider_rules_table(self) -> None:
        """Crea la tabla provider_rules si no existe."""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS provider_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tenant_id INTEGER REFERENCES tenants(id),
                        provider_name_normalized TEXT,
                        category_slug TEXT,
                        sat_account_code TEXT,
                        sat_product_service_code TEXT,
                        default_iva_rate REAL DEFAULT 0,
                        iva_tipo TEXT DEFAULT 'tasa_0',
                        confidence REAL DEFAULT 0.9,
                        last_confirmed_by INTEGER,
                        last_confirmed_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_provider_rules_lookup
                        ON provider_rules(tenant_id, provider_name_normalized)
                    """
                )
                conn.commit()
        except DatabaseOperationalError as exc:
            logger.warning("No se pudo asegurar provider_rules: %s", exc)

    def _ensure_company_context_columns(self) -> None:
        """Crea columnas opcionales para almacenar el perfil operativo de la empresa."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(companies)")
                existing = {row[1] for row in cursor.fetchall()}

                def add_column(name: str, definition: str) -> None:
                    if name not in existing:
                        logger.info("🛠️ Añadiendo columna %s a companies", name)
                        cursor.execute(f"ALTER TABLE companies ADD COLUMN {name} {definition}")
                        existing.add(name)

                add_column("giro", "TEXT")
                add_column("modelo_negocio", "TEXT")
                add_column("clientes_clave", "TEXT")
                add_column("proveedores_clave", "TEXT")
                add_column("canales_venta", "TEXT")
                add_column("frecuencia_operacion", "TEXT")
                add_column("descripcion_negocio", "TEXT")
                add_column("context_last_updated", "TIMESTAMP")
                add_column("context_profile", "TEXT")

                conn.commit()
        except DatabaseOperationalError as exc:
            logger.warning("No se pudieron asegurar columnas de contexto empresarial: %s", exc)

    def get_connection(self):
        """Obtiene una conexión a la DB unificada."""
        if self.use_postgres:
            return PostgresCompatConnection(self.postgres_dsn)

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def get_company_fiscal_profile(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve fiscal regime information for a tenant's company profile."""

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT regimen_fiscal_code, regimen_fiscal_desc
                      FROM companies
                     WHERE tenant_id = ? AND is_active = 1
                     ORDER BY id ASC
                     LIMIT 1
                    """,
                    (tenant_id,),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "regimen_fiscal_code": row[0],
                        "regimen_fiscal_desc": row[1],
                    }
        except DatabaseOperationalError as exc:
            logger.debug("No se pudo obtener perfil fiscal para tenant %s: %s", tenant_id, exc)
        return None

    # =================== COMPATIBILIDAD CON internal_db.py ===================

    def record_internal_expense(self, expense_data: Dict[str, Any], tenant_id: int = 1) -> int:
        """Crea un gasto interno con campos completos - Compatible con función existente"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            expense_payload = dict(expense_data)

            now_iso = datetime.utcnow().isoformat()

            expense_payload.setdefault('tax_source', expense_payload.get('tax_source') or 'manual')
            expense_payload.setdefault('classification_source', expense_payload.get('classification_source') or 'manual_entry')
            expense_payload.setdefault('catalog_version', expense_payload.get('catalog_version') or 'v1')
            expense_payload.setdefault('explanation_short', expense_payload.get('explanation_short') or 'Captura manual')
            expense_payload.setdefault('explanation_detail', expense_payload.get('explanation_detail') or 'Registrado manualmente por el usuario')
            expense_payload.setdefault('tipo_cambio', expense_payload.get('tipo_cambio') or 1.0)
            expense_payload.setdefault('deducible_status', expense_payload.get('deducible_status') or 'pendiente')
            expense_payload.setdefault('deducible_percent', expense_payload.get('deducible_percent') or 100.0)
            expense_payload.setdefault('iva_acreditable', expense_payload.get('iva_acreditable', True))

            if 'periodo' not in expense_payload or not expense_payload.get('periodo'):
                fecha_referencia = expense_payload.get('date') or now_iso
                expense_payload['periodo'] = (fecha_referencia or '')[:7] if fecha_referencia else None

            expense_payload.setdefault('currency', expense_payload.get('moneda', 'MXN'))
            expense_payload.setdefault('status', expense_payload.get('status', 'pending'))
            expense_payload.setdefault('user_id', expense_payload.get('user_id') or 1)
            expense_payload['tenant_id'] = tenant_id
            expense_payload.setdefault('created_at', now_iso)
            expense_payload.setdefault('updated_at', now_iso)
            if 'descripcion' not in expense_payload and expense_payload.get('description'):
                expense_payload['descripcion'] = expense_payload['description']
            if 'monto_total' not in expense_payload and expense_payload.get('amount') is not None:
                expense_payload['monto_total'] = expense_payload['amount']
            if 'proveedor_nombre' not in expense_payload and expense_payload.get('merchant_name'):
                expense_payload['proveedor_nombre'] = expense_payload['merchant_name']
            if 'categoria' not in expense_payload and expense_payload.get('category'):
                expense_payload['categoria'] = expense_payload['category']

            metadata_value = expense_payload.get('metadata') or {}
            if not isinstance(metadata_value, (str, bytes)):
                expense_payload['metadata'] = json.dumps(metadata_value, ensure_ascii=False)

            json_fields = [
                'tax_info', 'metadata', 'movimientos_bancarios', 'events', 'warnings',
                'category_alternatives', 'audit_trail', 'user_context', 'enhanced_data',
                'validation_errors'
            ]
            for field in json_fields:
                if field in expense_payload and isinstance(expense_payload[field], (dict, list)):
                    expense_payload[field] = json.dumps(expense_payload[field], ensure_ascii=False)

            # Map legacy keys to canonical column names
            key_aliases = {
                'monto_total': 'amount',
                'moneda': 'currency',
                'descripcion': 'description',
                'categoria': 'category',
                'provider_name': 'merchant_name',
                'expense_date': 'date',
                'account_code': 'sat_account_code',
            }
            keys_to_remove = []
            for legacy_key, canonical_key in key_aliases.items():
                if legacy_key in expense_payload:
                    if canonical_key not in expense_payload or expense_payload.get(canonical_key) is None:
                        expense_payload[canonical_key] = expense_payload[legacy_key]
                    keys_to_remove.append(legacy_key)
            for key in keys_to_remove:
                expense_payload.pop(key, None)

            columns = []
            values = []
            for key, value in expense_payload.items():
                if value is None:
                    continue
                columns.append(key)
                values.append(value)

            placeholders = ', '.join('?' for _ in columns)
            columns_sql = ', '.join(columns)

            cursor.execute(f"INSERT INTO expense_records ({columns_sql}) VALUES ({placeholders})", values)
            conn.commit()
            expense_id = cursor.lastrowid
            logger.info(f"✅ Gasto registrado ID: {expense_id} con columnas dinámicas")
            return expense_id

    def fetch_expense_records(self, tenant_id: int = 1, limit: int = 100, company_id: Optional[str] = None) -> List[Dict]:
        """Obtiene gastos con información de cuenta de pago, opcionalmente filtrados por company_id"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()

            # Build WHERE clause with optional company_id filter
            where_conditions = ["e.tenant_id = ?"]
            params = [tenant_id]

            if company_id:
                where_conditions.append("e.company_id = ?")
                params.append(company_id)

            where_clause = " AND ".join(where_conditions)
            params.append(limit)  # Add limit at the end

            query = f"""
                SELECT
                    e.*,
                    pa.nombre as payment_account_nombre,
                    pa.banco_nombre as payment_account_banco,
                    pa.tipo as payment_account_tipo,
                    pa.subtipo as payment_account_subtipo,
                    pa.numero_cuenta_enmascarado as payment_account_numero_enmascarado
                FROM expense_records e
                LEFT JOIN user_payment_accounts pa ON e.payment_account_id = pa.id
                WHERE {where_clause}
                ORDER BY e.created_at DESC
                LIMIT ?
            """

            cursor.execute(query, tuple(params))

            # Get column names for manual dictionary creation
            columns = [description[0] for description in cursor.description]
            records = []

            for row in cursor.fetchall():
                record_dict = {}
                for i, value in enumerate(row):
                    record_dict[columns[i]] = value
                records.append(self._normalize_expense_record(record_dict))

            logger.info(f"✅ Recuperados {len(records)} gastos")
            return records
        finally:
            conn.close()

    def fetch_expense_record(self, expense_id: int) -> Optional[Dict]:
        """Obtiene un gasto específico con información de cuenta de pago"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    e.*,
                    pa.nombre as payment_account_nombre,
                    pa.banco_nombre as payment_account_banco,
                    pa.tipo as payment_account_tipo,
                    pa.subtipo as payment_account_subtipo,
                    pa.numero_cuenta_enmascarado as payment_account_numero_enmascarado
                FROM expense_records e
                LEFT JOIN user_payment_accounts pa ON e.payment_account_id = pa.id
                WHERE e.id = ?
            """, (expense_id,))

            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()

            if row:
                record_dict = {}
                for i, value in enumerate(row):
                    record_dict[columns[i]] = value
                return self._normalize_expense_record(record_dict)
            return None
        finally:
            conn.close()

    def list_sat_account_catalog(
        self,
        *,
        search: Optional[str] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Obtiene el catálogo SAT de cuentas contables."""

        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT code, name, description, parent_code, type, is_active, updated_at "
                "FROM sat_account_catalog"
            )
            clauses: List[str] = []
            params: List[Any] = []

            if not include_inactive:
                clauses.append("is_active = 1")
            if search:
                like_value = f"%{search.strip().lower()}%"
                clauses.append(
                    "(LOWER(code) LIKE ? OR LOWER(name) LIKE ? OR LOWER(IFNULL(description, '')) LIKE ?)"
                )
                params.extend([like_value, like_value, like_value])

            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY code"
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def list_sat_product_service_catalog(
        self,
        *,
        search: Optional[str] = None,
        include_inactive: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Obtiene el catálogo SAT de productos y servicios CFDI."""

        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT code, name, description, unit_key, is_active, updated_at "
                "FROM sat_product_service_catalog"
            )
            clauses: List[str] = []
            params: List[Any] = []

            if not include_inactive:
                clauses.append("is_active = 1")
            if search:
                like_value = f"%{search.strip().lower()}%"
                clauses.append(
                    "(LOWER(code) LIKE ? OR LOWER(name) LIKE ? OR LOWER(IFNULL(description, '')) LIKE ?)"
                )
                params.extend([like_value, like_value, like_value])

            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY code"
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_expense_record(self, expense_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
        """Actualiza un gasto existente y devuelve el registro actualizado"""
        import json
        feedback_notes = updates.pop("__feedback_notes", None)

        if not updates:
            return None

        previous_record: Optional[Dict[str, Any]] = None
        try:
            previous_record = self.fetch_expense_record(expense_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to fetch previous expense record %s: %s", expense_id, exc)
            previous_record = None

        # Filtrar valores None y convertir tipos complejos
        clean_updates = {}
        for key, value in updates.items():
            if value is not None:
                # Convertir dict a JSON string para metadata
                if key == 'metadata' and isinstance(value, dict):
                    clean_updates[key] = json.dumps(value)
                # Convertir listas a JSON string
                elif isinstance(value, (list, dict)):
                    clean_updates[key] = json.dumps(value)
                else:
                    clean_updates[key] = value

        if not clean_updates:
            return None

        # Construir query dinámico
        set_clauses = []
        params = []
        for key, value in clean_updates.items():
            set_clauses.append(f"{key} = ?")
            params.append(value)
        params.append(expense_id)  # Para WHERE clause

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE expense_records
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """, params)
            conn.commit()

            # Devolver el registro actualizado
            if cursor.rowcount > 0:
                updated_record = self.fetch_expense_record(expense_id)

                if previous_record and updated_record:
                    old_sat = previous_record.get("sat_account_code")
                    new_sat = updated_record.get("sat_account_code")
                    if new_sat and new_sat != old_sat:
                        try:
                            descripcion = (
                                updated_record.get("description")
                                or previous_record.get("description")
                                or ""
                            )
                            tenant_id = (
                                updated_record.get("tenant_id")
                                or previous_record.get("tenant_id")
                                or 1
                            )
                            record_feedback(
                                conn,
                                tenant_id=int(tenant_id),
                                descripcion=str(descripcion),
                                confirmed_sat_code=str(new_sat),
                                suggested_sat_code=str(old_sat) if old_sat else None,
                                expense_id=expense_id,
                                notes=feedback_notes or "manual_update",
                            )
                        except Exception as exc:  # pragma: no cover - defensive logging
                            logger.warning(
                                "Unable to record classification feedback for expense %s: %s",
                                expense_id,
                                exc,
                            )

                return updated_record
            return None

    def list_bank_movements(self, tenant_id: int = 1) -> List[Dict]:
        """Lista movimientos bancarios"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM bank_movements
                WHERE tenant_id = ?
                ORDER BY date DESC
            """, (tenant_id,))

            return [dict(row) for row in cursor.fetchall()]

    def record_bank_match_feedback(self, movement_id: int, expense_id: int, feedback: str) -> bool:
        """Registra feedback de matching bancario"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bank_movements
                SET matched_expense_id = ?
                WHERE id = ?
            """, (expense_id, movement_id))
            conn.commit()
            return cursor.rowcount > 0

    # =================== COMPATIBILIDAD CON TICKETS ===================

    def create_ticket(self, title: str, description: str, tenant_id: int = 1, user_id: int = 1) -> int:
        """Crea un ticket de soporte"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tickets (title, description, status, tenant_id, user_id)
                VALUES (?, ?, 'open', ?, ?)
            """, (title, description, tenant_id, user_id))
            conn.commit()
            return cursor.lastrowid

    def get_tickets(self, tenant_id: int = 1, status: str = None) -> List[Dict]:
        """Obtiene tickets"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM tickets WHERE tenant_id = ?"
            params = [tenant_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # =================== COMPATIBILIDAD CON AUTOMATIZACIÓN ===================

    def create_automation_job(self, job_type: str, config: Dict, tenant_id: int = 1) -> int:
        """Crea un job de automatización"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO automation_jobs (job_type, status, config, tenant_id)
                VALUES (?, 'pending', ?, ?)
            """, (job_type, str(config), tenant_id))
            conn.commit()
            return cursor.lastrowid

    def get_automation_jobs(self, tenant_id: int = 1, status: str = None) -> List[Dict]:
        """Obtiene jobs de automatización"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM automation_jobs WHERE tenant_id = ?"
            params = [tenant_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # =================== COMPATIBILIDAD CON ANALYTICS ===================

    def log_gpt_usage(self, field_name: str, reason: str, tokens: int, cost: float,
                     confidence_before: float, confidence_after: float, success: bool,
                     merchant_type: str = None, ticket_id: str = None,
                     error_message: str = None, tenant_id: int = 1) -> int:
        """Registra uso de GPT"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gpt_usage_events
                (timestamp, field_name, reason, tokens_estimated, cost_estimated_usd,
                 confidence_before, confidence_after, success, merchant_type,
                 ticket_id, error_message, tenant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(), field_name, reason, tokens, cost,
                confidence_before, confidence_after, int(success), merchant_type,
                ticket_id, error_message, tenant_id
            ))
            conn.commit()
            return cursor.lastrowid

    def get_gpt_usage_stats(self, tenant_id: int = 1) -> Dict:
        """Obtiene estadísticas de uso de GPT"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_events,
                    SUM(tokens_estimated) as total_tokens,
                    SUM(cost_estimated_usd) as total_cost,
                    AVG(confidence_after) as avg_confidence,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_events
                FROM gpt_usage_events
                WHERE tenant_id = ?
            """, (tenant_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'total_events': row[0] or 0,
                    'total_tokens': row[1] or 0,
                    'total_cost': row[2] or 0.0,
                    'avg_confidence': row[3] or 0.0,
                    'successful_events': row[4] or 0,
                    'success_rate': (row[4] or 0) / max(row[0] or 1, 1) * 100
                }
            return {}

    # =================== FUNCIONES FALTANTES MIGRADAS ===================

    def register_expense_invoice(self, expense_id: int, filename: str, file_path: str,
                                content_type: str = "application/pdf", parsed_data: str = None,
                                tenant_id: int = 1, metadata: Optional[Dict[str, Any]] = None,
                                model_used: Optional[str] = None, processed_by: Optional[int] = None,
                                processing_source: Optional[str] = None) -> int:
        """Registra una factura asociada a un gasto"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expense_invoices
                (expense_id, filename, file_path, content_type, parsed_data, tenant_id,
                 processing_metadata, parser_used, processed_by, processing_source, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                expense_id,
                filename,
                file_path,
                content_type,
                parsed_data,
                tenant_id,
                json.dumps(metadata) if metadata else None,
                model_used,
                processed_by,
                processing_source,
            ))
            conn.commit()
            return cursor.lastrowid

    def mark_expense_invoiced(self, expense_id: int, invoice_id: int = None) -> bool:
        """Marca un gasto como facturado"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE expense_records
                SET status = 'invoiced', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (expense_id,))
            conn.commit()
            return cursor.rowcount > 0

    def mark_expense_without_invoice(self, expense_id: int, reason: str = "No facturable") -> bool:
        """Marca un gasto como no facturable"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE expense_records
                SET status = 'no_invoice', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (expense_id,))
            conn.commit()
            return cursor.rowcount > 0

    def register_user_account(self, name: str, email: str, tenant_id: int = 1, role: str = "user") -> int:
        """Registra una nueva cuenta de usuario"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (name, email, tenant_id, role)
                    VALUES (?, ?, ?, ?)
                """, (name, email, tenant_id, role))
                conn.commit()
                return cursor.lastrowid
            except IntegrityErrors:
                # Usuario ya existe
                cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                row = cursor.fetchone()
                return row[0] if row else None

    def get_company_demo_snapshot(self, tenant_id: int = 1) -> Dict:
        """Obtiene snapshot demo de la empresa"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Obtener datos del tenant
            cursor.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
            tenant = cursor.fetchone()

            if not tenant:
                return {}

            # Estadísticas básicas
            cursor.execute("""
                SELECT
                    (SELECT COUNT(*) FROM expense_records WHERE tenant_id = ?) as expenses,
                    (SELECT COUNT(*) FROM bank_movements WHERE tenant_id = ?) as movements,
                    (SELECT COUNT(*) FROM automation_jobs WHERE tenant_id = ?) as jobs,
                    (SELECT COUNT(*) FROM tickets WHERE tenant_id = ?) as tickets,
                    (SELECT SUM(amount) FROM expense_records WHERE tenant_id = ?) as total_expenses
            """, (tenant_id, tenant_id, tenant_id, tenant_id, tenant_id))

            stats = cursor.fetchone()

            return {
                'tenant': dict(tenant),
                'statistics': {
                    'manual_expenses': stats[0] or 0,
                    'bank_movements': stats[1] or 0,
                    'automation_jobs': stats[2] or 0,
                    'tickets': stats[3] or 0,
                    'total_expense_amount': stats[4] or 0.0
                },
                'last_updated': datetime.now().isoformat()
            }

    def delete_company_expenses(self, tenant_id: int) -> Dict[str, Any]:
        """Remove all expense data for a tenant, including dependent records."""

        with self.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM expense_records WHERE tenant_id = ?",
                (tenant_id,),
            )
            expense_ids = [row[0] for row in cursor.fetchall()]

            stats: Dict[str, Any] = {
                "tenant_id": tenant_id,
                "deleted_expenses": 0,
                "deleted_bank_movements": 0,
                "cleaned_tables": {},
            }

            if expense_ids:
                placeholders = ",".join(["?"] * len(expense_ids))

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                table_names = [row[0] for row in cursor.fetchall()]

                table_columns: Dict[str, List[str]] = {}
                for table in table_names:
                    try:
                        cursor.execute(f"PRAGMA table_info({table})")
                        table_columns[table] = [row[1] for row in cursor.fetchall()]
                    except DatabaseOperationalError:
                        table_columns[table] = []

                for table, columns in table_columns.items():
                    if table in {"expense_records", "bank_movements"}:
                        continue

                    if "expense_id" in columns:
                        params: List[Any]
                        query: str
                        if "tenant_id" in columns:
                            query = f"DELETE FROM {table} WHERE tenant_id = ?"
                            params = [tenant_id]
                        else:
                            query = f"DELETE FROM {table} WHERE expense_id IN ({placeholders})"
                            params = expense_ids
                        try:
                            cursor.execute(query, params)
                            stats["cleaned_tables"][table] = cursor.rowcount
                        except DatabaseOperationalError:
                            continue

                    dependent_columns = [
                        column
                        for column in columns
                        if column.endswith("expense_id") and column not in {"expense_id"}
                    ]
                    for column in dependent_columns:
                        try:
                            cursor.execute(
                                f"UPDATE {table} SET {column} = NULL WHERE {column} IN ({placeholders})",
                                expense_ids,
                            )
                        except DatabaseOperationalError:
                            continue

                cursor.execute(
                    f"DELETE FROM expense_records WHERE id IN ({placeholders})",
                    expense_ids,
                )
                stats["deleted_expenses"] = cursor.rowcount
            else:
                stats["cleaned_tables"] = {}

            cursor.execute(
                "DELETE FROM bank_movements WHERE tenant_id = ?",
                (tenant_id,),
            )
            stats["deleted_bank_movements"] = cursor.rowcount

            conn.commit()

        return stats

    def fetch_candidate_expenses_for_invoice(self, tenant_id: int = 1, status: str = "pending") -> List[Dict]:
        """Obtiene gastos candidatos para facturación"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, u.full_name AS user_full_name, u.username AS user_username, u.email AS user_email
                FROM expense_records e
                LEFT JOIN users u ON e.user_id = u.id
                WHERE e.tenant_id = ? AND e.status = ?
                ORDER BY e.created_at DESC
            """, (tenant_id, status))

            candidates = []
            for row in cursor.fetchall():
                expense = dict(row)
                if 'user_name' not in expense:
                    display_name = expense.get('user_full_name') or expense.get('user_username') or expense.get('user_email')
                    expense['user_name'] = display_name
                # Verificar si ya tiene factura
                cursor.execute("SELECT COUNT(*) FROM expense_invoices WHERE expense_id = ?", (expense['id'],))
                has_invoice = cursor.fetchone()[0] > 0

                expense['has_invoice'] = has_invoice
                expense['is_candidate'] = not has_invoice and expense['amount'] > 0

                candidates.append(expense)

            return candidates

    def create_tenant(self, name: str, company_name: str = None, config: Dict = None) -> int:
        """Crea un nuevo tenant"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            config_json = str(config or {})
            cursor.execute("""
                INSERT INTO tenants (name, config)
                VALUES (?, ?)
            """, (name, config_json))
            conn.commit()
            return cursor.lastrowid

    def get_tenants(self) -> List[Dict]:
        """Obtiene todos los tenants"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tenants ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def create_invoicing_job(self, tenant_id: int, job_config: Dict) -> int:
        """Crea un job de facturación automática"""
        return self.create_automation_job("invoicing", job_config, tenant_id)

    def get_invoice_attachments(self, expense_id: int) -> List[Dict]:
        """Obtiene archivos adjuntos de facturas"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM expense_invoices
                WHERE expense_id = ?
                ORDER BY created_at DESC
            """, (expense_id,))
            return [dict(row) for row in cursor.fetchall()]

    # =================== FUNCIONES DE UTILIDAD ===================

    def get_system_stats(self) -> Dict:
        """Obtiene estadísticas generales del sistema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Contar registros por tabla
            tables = ['tenants', 'users', 'expense_records', 'bank_movements',
                     'tickets', 'automation_jobs', 'gpt_usage_events']

            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[f'{table}_count'] = count

            return stats

    def health_check(self) -> Dict:
        """Verifica el estado de la DB"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM schema_versions")
                version_count = cursor.fetchone()[0]

                return {
                    'status': 'healthy',
                    'db_path': str(self.db_path),
                    'db_size': self.db_path.stat().st_size,
                    'schema_versions': version_count,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    # ===== EXPENSE TAGS MANAGEMENT =====

    def create_expense_tag(self, name: str, color: str = "#3498db", description: str = None, tenant_id: int = 1, created_by: int = None) -> int:
        """Crea una nueva etiqueta de gastos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expense_tags (name, color, description, tenant_id, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (name.lower().strip(), color, description, tenant_id, created_by))
            return cursor.lastrowid

    def get_expense_tags(self, tenant_id: int = 1, include_usage_count: bool = True) -> List[Dict]:
        """Obtiene todas las etiquetas de gastos para un tenant"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if include_usage_count:
                cursor.execute("""
                    SELECT t.*, COUNT(r.expense_id) as usage_count
                    FROM expense_tags t
                    LEFT JOIN expense_tag_relations r ON t.id = r.tag_id
                    WHERE t.tenant_id = ?
                    GROUP BY t.id, t.name, t.color, t.description, t.tenant_id, t.created_by, t.created_at
                    ORDER BY t.name
                """, (tenant_id,))
            else:
                cursor.execute("""
                    SELECT * FROM expense_tags
                    WHERE tenant_id = ?
                    ORDER BY name
                """, (tenant_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_expense_tag(self, tag_id: int, name: str = None, color: str = None, description: str = None, tenant_id: int = 1) -> bool:
        """Actualiza una etiqueta de gastos"""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name.lower().strip())
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if not updates:
            return False

        params.extend([tenant_id, tag_id])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE expense_tags
                SET {', '.join(updates)}
                WHERE tenant_id = ? AND id = ?
            """, params)
            return cursor.rowcount > 0

    def delete_expense_tag(self, tag_id: int, tenant_id: int = 1) -> bool:
        """Elimina una etiqueta de gastos (y sus relaciones)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # First delete relations
            cursor.execute("DELETE FROM expense_tag_relations WHERE tag_id = ?", (tag_id,))
            # Then delete the tag
            cursor.execute("DELETE FROM expense_tags WHERE id = ? AND tenant_id = ?", (tag_id, tenant_id))
            return cursor.rowcount > 0

    def assign_expense_tags(self, expense_id: int, tag_ids: List[int]) -> bool:
        """Asigna etiquetas a un gasto (agrega sin remover existentes)"""
        if not tag_ids:
            return True

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for tag_id in tag_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO expense_tag_relations (expense_id, tag_id, created_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (expense_id, tag_id))
            return True

    def unassign_expense_tags(self, expense_id: int, tag_ids: List[int]) -> bool:
        """Desasigna etiquetas de un gasto"""
        if not tag_ids:
            return True

        placeholders = ','.join(['?' for _ in tag_ids])
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                DELETE FROM expense_tag_relations
                WHERE expense_id = ? AND tag_id IN ({placeholders})
            """, [expense_id] + tag_ids)
            return True

    def replace_expense_tags(self, expense_id: int, tag_ids: List[int]) -> bool:
        """Reemplaza todas las etiquetas de un gasto"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Get tenant_id from expense
            row = cursor.execute(
                "SELECT tenant_id FROM expense_records WHERE id = ?",
                (expense_id,)
            ).fetchone()
            if not row:
                return False
            tenant_id = row[0]

            # Remove all existing tags
            cursor.execute("DELETE FROM expense_tag_relations WHERE expense_id = ?", (expense_id,))
            # Add new tags
            for tag_id in tag_ids:
                cursor.execute("""
                    INSERT INTO expense_tag_relations (expense_id, tag_id, tenant_id, created_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (expense_id, tag_id, tenant_id))
            return True

    def get_expense_tags_for_expense(self, expense_id: int) -> List[Dict]:
        """Obtiene todas las etiquetas de un gasto específico"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, r.created_at as assigned_at
                FROM expense_tags t
                JOIN expense_tag_relations r ON t.id = r.tag_id
                WHERE r.expense_id = ?
                ORDER BY t.name
            """, (expense_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_expenses_by_tag(self, tag_id: int, tenant_id: int = 1) -> List[Dict]:
        """Obtiene todos los gastos que tienen una etiqueta específica"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, u.name as user_name, r.created_at as tag_assigned_at
                FROM expense_records e
                JOIN expense_tag_relations r ON e.id = r.expense_id
                LEFT JOIN users u ON e.user_id = u.id
                WHERE r.tag_id = ? AND e.tenant_id = ?
                ORDER BY e.created_at DESC
            """, (tag_id, tenant_id))
            return [dict(row) for row in cursor.fetchall()]

    # ===== ENHANCED INVOICE MANAGEMENT =====

    def create_invoice_record(self, invoice_data: Dict[str, Any], tenant_id: int = 1) -> int:
        """Crea un registro de factura completo con todos los campos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expense_invoices
                (expense_id, filename, file_path, content_type, tenant_id,
                 uuid, rfc_emisor, nombre_emisor, subtotal, iva_amount, total,
                 moneda, fecha_emision, xml_content, pdf_content, parsed_data,
                 processing_status, match_confidence, auto_matched, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                invoice_data.get('expense_id'),
                invoice_data.get('filename'),
                invoice_data.get('file_path'),
                invoice_data.get('content_type', 'application/pdf'),
                tenant_id,
                invoice_data.get('uuid'),
                invoice_data.get('rfc_emisor'),
                invoice_data.get('nombre_emisor'),
                invoice_data.get('subtotal'),
                invoice_data.get('iva_amount'),
                invoice_data.get('total'),
                invoice_data.get('moneda', 'MXN'),
                invoice_data.get('fecha_emision'),
                invoice_data.get('xml_content'),
                invoice_data.get('pdf_content'),
                invoice_data.get('parsed_data'),
                invoice_data.get('processing_status', 'pending'),
                invoice_data.get('match_confidence', 0.0),
                invoice_data.get('auto_matched', False)
            ))
            return cursor.lastrowid

    def get_invoice_records(self, tenant_id: int = 1, status: str = None, limit: int = 100) -> List[Dict]:
        """Obtiene registros de facturas con información enriquecida"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT i.*, e.description as expense_description, e.amount as expense_amount,
                       u.name as user_name, u.email as user_email,
                       ABS(COALESCE(i.total, 0) - COALESCE(e.amount, 0)) as amount_difference,
                       CASE
                           WHEN i.total IS NOT NULL AND e.amount IS NOT NULL THEN
                               CASE
                                   WHEN ABS(i.total - e.amount) < 0.01 THEN 'exact'
                                   WHEN ABS(i.total - e.amount) < 1.0 THEN 'close'
                                   ELSE 'different'
                               END
                           ELSE 'unknown'
                       END as amount_match_quality
                FROM expense_invoices i
                LEFT JOIN expense_records e ON i.expense_id = e.id
                LEFT JOIN users u ON e.user_id = u.id
                WHERE i.tenant_id = ?
            """
            params = [tenant_id]

            if status:
                query += " AND i.processing_status = ?"
                params.append(status)

            query += " ORDER BY i.created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_invoice_record(self, invoice_id: int, tenant_id: int = 1) -> Optional[Dict]:
        """Obtiene un registro de factura específico"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, e.description as expense_description, e.amount as expense_amount,
                       u.name as user_name,
                       ABS(COALESCE(i.total, 0) - COALESCE(e.amount, 0)) as amount_difference,
                       CASE
                           WHEN i.total IS NOT NULL AND e.amount IS NOT NULL THEN
                               CASE
                                   WHEN ABS(i.total - e.amount) < 0.01 THEN 'exact'
                                   WHEN ABS(i.total - e.amount) < 1.0 THEN 'close'
                                   ELSE 'different'
                               END
                           ELSE 'unknown'
                       END as amount_match_quality
                FROM expense_invoices i
                LEFT JOIN expense_records e ON i.expense_id = e.id
                LEFT JOIN users u ON e.user_id = u.id
                WHERE i.id = ? AND i.tenant_id = ?
            """, (invoice_id, tenant_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_invoice_record(self, invoice_id: int, updates: Dict[str, Any], tenant_id: int = 1) -> bool:
        """Actualiza un registro de factura"""
        if not updates:
            return False

        # Construir query dinámico
        set_clauses = []
        params = []

        allowed_fields = [
            'uuid', 'rfc_emisor', 'nombre_emisor', 'subtotal', 'iva_amount', 'total',
            'moneda', 'fecha_emision', 'xml_content', 'parsed_data', 'processing_status',
            'match_confidence', 'auto_matched', 'error_message'
        ]

        for key, value in updates.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        params.extend([tenant_id, invoice_id])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE expense_invoices
                SET {', '.join(set_clauses)}
                WHERE tenant_id = ? AND id = ?
            """, params)
            return cursor.rowcount > 0

    def find_matching_expenses(self, invoice_data: Dict[str, Any], tenant_id: int = 1,
                              threshold: float = 0.8) -> List[Dict]:
        """Encuentra gastos candidatos para matching automático"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Construir criterios de búsqueda dinámicos
            conditions = ["e.tenant_id = ?"]
            params = [tenant_id]

            # Buscar por monto (con tolerancia)
            if invoice_data.get('total'):
                total = invoice_data['total']
                tolerance = total * 0.05  # 5% de tolerancia
                conditions.append("ABS(e.amount - ?) <= ?")
                params.extend([total, tolerance])

            # Buscar por RFC del proveedor
            if invoice_data.get('rfc_emisor'):
                conditions.append("e.rfc_proveedor = ?")
                params.append(invoice_data['rfc_emisor'])

            # Buscar por fecha (mismo mes)
            if invoice_data.get('fecha_emision'):
                conditions.append("date(e.date) = date(?)")
                params.append(invoice_data['fecha_emision'])

            # Solo gastos sin factura asignada
            conditions.append("e.id NOT IN (SELECT DISTINCT expense_id FROM expense_invoices WHERE expense_id IS NOT NULL)")

            query = f"""
                SELECT e.*, u.name as user_name,
                       ABS(COALESCE(e.amount, 0) - COALESCE(?, 0)) as amount_difference,
                       CASE
                           WHEN ? IS NOT NULL AND e.amount IS NOT NULL THEN
                               1.0 - (ABS(e.amount - ?) / GREATEST(e.amount, ?, 1))
                           ELSE 0.0
                       END as match_score
                FROM expense_records e
                LEFT JOIN users u ON e.user_id = u.id
                WHERE {' AND '.join(conditions)}
                ORDER BY match_score DESC
                LIMIT 20
            """

            total_param = invoice_data.get('total', 0)
            cursor.execute(query, [total_param, total_param, total_param, total_param] + params)

            results = [dict(row) for row in cursor.fetchall()]
            # Filtrar por threshold
            return [r for r in results if r['match_score'] >= threshold]

    # ===== ENHANCED BANK RECONCILIATION MANAGEMENT =====

    def create_bank_movement(self, movement_data: Dict[str, Any], tenant_id: int = 1) -> int:
        """Crea un movimiento bancario completo"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            movement_kind = movement_data.get('movement_kind')
            if not movement_kind:
                movement_kind = infer_movement_kind(
                    movement_data.get('transaction_type', 'debit'),
                    movement_data.get('description')
                )

            if isinstance(movement_kind, MovementKind):
                movement_kind_value = movement_kind.value
            else:
                movement_kind_value = str(movement_kind) if movement_kind else MovementKind.GASTO.value

            cursor.execute("""
                INSERT INTO bank_movements
                (amount, description, date, account, tenant_id, movement_id,
                 transaction_type, reference, balance_after, bank_metadata,
                 raw_data, processing_status, bank_account_id, category,
                 confidence, decision, auto_matched, movement_kind, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                movement_data.get('amount'),
                movement_data.get('description'),
                movement_data.get('date'),
                movement_data.get('account'),
                tenant_id,
                movement_data.get('movement_id'),
                movement_data.get('transaction_type', 'debit'),
                movement_data.get('reference'),
                movement_data.get('balance_after'),
                movement_data.get('bank_metadata'),
                movement_data.get('raw_data'),
                movement_data.get('processing_status', 'pending'),
                movement_data.get('bank_account_id'),
                movement_data.get('category'),
                movement_data.get('confidence', 0.0),
                movement_data.get('decision', 'pending'),
                movement_data.get('auto_matched', False),
                movement_kind_value
            ))
            return cursor.lastrowid

    def get_bank_movements(self, tenant_id: int = 1, status: str = None, limit: int = 100) -> List[Dict]:
        """Obtiene movimientos bancarios con información enriquecida"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT bm.*, e.description as expense_description, e.amount as expense_amount,
                       COALESCE(u.full_name, u.email) as user_name, u.email as user_email,
                       ABS(COALESCE(bm.amount, 0) - COALESCE(e.amount, 0)) as amount_difference,
                       CASE
                           WHEN bm.amount IS NOT NULL AND e.amount IS NOT NULL THEN
                               CASE
                                   WHEN ABS(bm.amount - e.amount) < 0.01 THEN 'exact'
                                   WHEN ABS(bm.amount - e.amount) < ABS(bm.amount) * 0.05 THEN 'close'
                                   ELSE 'different'
                               END
                           ELSE 'unknown'
                       END as amount_match_quality,
                       CASE
                           WHEN bm.matched_expense_id IS NOT NULL THEN 'matched'
                           WHEN bm.decision = 'rejected' THEN 'rejected'
                           WHEN bm.confidence >= 0.85 THEN 'high_confidence'
                           WHEN bm.confidence >= 0.65 THEN 'medium_confidence'
                           ELSE 'low_confidence'
                       END as reconciliation_status
                FROM bank_movements bm
                LEFT JOIN expense_records e ON bm.matched_expense_id = e.id
                LEFT JOIN users u ON e.user_id = u.id
                WHERE bm.tenant_id = ?
            """
            params = [tenant_id]

            if status:
                query += " AND bm.processing_status = ?"
                params.append(status)

            query += " ORDER BY bm.date DESC, bm.created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_bank_movement(self, movement_id: int, tenant_id: int = 1) -> Optional[Dict]:
        """Obtiene un movimiento bancario específico"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT bm.*, e.description as expense_description, e.amount as expense_amount,
                       COALESCE(u.full_name, u.email) as user_name,
                       ABS(COALESCE(bm.amount, 0) - COALESCE(e.amount, 0)) as amount_difference,
                       CASE
                           WHEN bm.amount IS NOT NULL AND e.amount IS NOT NULL THEN
                               CASE
                                   WHEN ABS(bm.amount - e.amount) < 0.01 THEN 'exact'
                                   WHEN ABS(bm.amount - e.amount) < ABS(bm.amount) * 0.05 THEN 'close'
                                   ELSE 'different'
                               END
                           ELSE 'unknown'
                       END as amount_match_quality,
                       CASE
                           WHEN bm.matched_expense_id IS NOT NULL THEN 'matched'
                           WHEN bm.decision = 'rejected' THEN 'rejected'
                           WHEN bm.confidence >= 0.85 THEN 'high_confidence'
                           WHEN bm.confidence >= 0.65 THEN 'medium_confidence'
                           ELSE 'low_confidence'
                       END as reconciliation_status
                FROM bank_movements bm
                LEFT JOIN expense_records e ON bm.matched_expense_id = e.id
                LEFT JOIN users u ON e.user_id = u.id
                WHERE bm.id = ? AND bm.tenant_id = ?
            """, (movement_id, tenant_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_bank_movement(self, movement_id: int, updates: Dict[str, Any], tenant_id: int = 1) -> bool:
        """Actualiza un movimiento bancario"""
        if not updates:
            return False

        set_clauses = []
        params = []

        allowed_fields = [
            'decision', 'confidence', 'matched_expense_id', 'processing_status',
            'reconciliation_notes', 'matched_by', 'auto_matched', 'bank_metadata',
            'transaction_type', 'movement_kind', 'category', 'category_manual',
            'display_type', 'display_name', 'ai_model', 'amount', 'cargo_amount',
            'abono_amount'
        ]

        for key, value in updates.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        params.extend([tenant_id, movement_id])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE bank_movements
                SET {', '.join(set_clauses)}
                WHERE tenant_id = ? AND id = ?
            """, params)
            return cursor.rowcount > 0

    def find_matching_expenses_for_movement(self, movement_data: Dict[str, Any], tenant_id: int = 1,
                                          threshold: float = 0.65) -> List[Dict]:
        """Encuentra gastos candidatos para matching con movimiento bancario usando ML"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Construir criterios de búsqueda inteligentes
            conditions = ["e.tenant_id = ?"]
            params = [tenant_id]

            # Solo gastos sin conciliación bancaria
            conditions.append("e.id NOT IN (SELECT DISTINCT matched_expense_id FROM bank_movements WHERE matched_expense_id IS NOT NULL)")

            # Criterio de monto con tolerancia variable
            amount = movement_data.get('amount', 0)
            if amount != 0:
                # Tolerancia del 5% o mínimo $1
                tolerance = max(abs(amount) * 0.05, 1.0)
                conditions.append("ABS(e.amount - ?) <= ?")
                params.extend([amount, tolerance])

            # Criterio de fecha (mismo día o dentro de 7 días)
            if movement_data.get('date'):
                conditions.append("(date(e.date) = date(?) OR ABS(julianday(e.date) - julianday(?)) <= 7)")
                params.extend([movement_data['date'], movement_data['date']])

            # Criterio por descripción (buscar palabras clave)
            description = movement_data.get('description', '').lower()
            if description:
                # Extraer palabras clave de la descripción bancaria
                keywords = [word for word in description.split() if len(word) > 3]
                if keywords:
                    keyword_conditions = []
                    for keyword in keywords[:3]:  # Máximo 3 keywords
                        keyword_conditions.append("LOWER(e.description) LIKE ?")
                        params.append(f"%{keyword}%")
                    if keyword_conditions:
                        conditions.append(f"({' OR '.join(keyword_conditions)})")

            query = f"""
                SELECT e.*, u.name as user_name,
                       ABS(COALESCE(e.amount, 0) - ?) as amount_difference,
                       -- Score de matching ML mejorado
                       (
                           -- Score de monto (peso 40%)
                           CASE
                               WHEN ABS(e.amount - ?) < 0.01 THEN 1.0
                               WHEN ABS(e.amount - ?) <= ? * 0.01 THEN 0.9
                               WHEN ABS(e.amount - ?) <= ? * 0.05 THEN 0.7
                               ELSE 0.0
                           END * 0.4 +

                           -- Score de fecha (peso 25%)
                           CASE
                               WHEN date(e.date) = date(?) THEN 1.0
                               WHEN ABS(julianday(e.date) - julianday(?)) <= 1 THEN 0.8
                               WHEN ABS(julianday(e.date) - julianday(?)) <= 3 THEN 0.6
                               WHEN ABS(julianday(e.date) - julianday(?)) <= 7 THEN 0.4
                               ELSE 0.0
                           END * 0.25 +

                           -- Score de descripción (peso 35%)
                           CASE
                               WHEN LOWER(e.description) LIKE ? THEN 1.0
                               WHEN LOWER(e.description) LIKE ? OR LOWER(e.description) LIKE ? THEN 0.7
                               ELSE 0.2
                           END * 0.35
                       ) as match_score
                FROM expense_records e
                LEFT JOIN users u ON e.user_id = u.id
                WHERE {' AND '.join(conditions)}
                ORDER BY match_score DESC
                LIMIT 10
            """

            # Parámetros para el score
            score_params = [
                amount,  # amount_difference
                amount, amount, tolerance, amount, tolerance,  # amount score params
                movement_data.get('date', ''), movement_data.get('date', ''),  # date score params
                movement_data.get('date', ''), movement_data.get('date', ''),
                f"%{description}%", f"%{description[:10]}%", f"%{description[-10:]}%"  # description score params
            ]

            cursor.execute(query, score_params + params)
            results = [dict(row) for row in cursor.fetchall()]

            # Filtrar por threshold
            return [r for r in results if r['match_score'] >= threshold]

    def create_reconciliation_feedback(self, feedback_data: Dict[str, Any], tenant_id: int = 1) -> int:
        """Registra feedback de conciliación"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bank_reconciliation_feedback
                (movement_id, expense_id, feedback_type, confidence, match_criteria,
                 user_decision, feedback_notes, created_by, tenant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback_data.get('movement_id'),
                feedback_data.get('expense_id'),
                feedback_data.get('feedback_type'),
                feedback_data.get('confidence', 0.0),
                feedback_data.get('match_criteria'),
                feedback_data.get('user_decision'),
                feedback_data.get('feedback_notes'),
                feedback_data.get('created_by'),
                tenant_id
            ))
            return cursor.lastrowid

    def get_ml_config(self, config_type: str, tenant_id: int = 1) -> Optional[Dict]:
        """Obtiene configuración ML"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM bank_ml_config
                WHERE config_type = ? AND tenant_id = ? AND active = TRUE
                ORDER BY created_at DESC LIMIT 1
            """, (config_type, tenant_id))
            row = cursor.fetchone()
            return dict(row) if row else None

    def perform_auto_reconciliation(self, tenant_id: int = 1, batch_size: int = 50) -> Dict[str, int]:
        """Ejecuta conciliación automática usando ML"""
        stats = {'processed': 0, 'matched': 0, 'skipped': 0}

        # Obtener configuración ML
        ml_config = self.get_ml_config('matching_threshold', tenant_id)
        if not ml_config:
            return stats

        import json
        thresholds = json.loads(ml_config['config_data'])
        auto_threshold = thresholds.get('auto_match', 0.85)

        # Obtener movimientos pendientes
        pending_movements = self.get_bank_movements(tenant_id, status='pending', limit=batch_size)

        for movement in pending_movements:
            stats['processed'] += 1

            # Buscar matches
            candidates = self.find_matching_expenses_for_movement(movement, tenant_id, auto_threshold)

            if candidates and len(candidates) == 1:  # Solo auto-match si hay exactamente 1 candidato
                best_match = candidates[0]
                if best_match['match_score'] >= auto_threshold:
                    # Auto-match
                    self.update_bank_movement(movement['id'], {
                        'matched_expense_id': best_match['id'],
                        'confidence': best_match['match_score'],
                        'decision': 'accepted',
                        'auto_matched': True,
                        'processing_status': 'processed'
                    }, tenant_id)

                    # Registrar feedback
                    self.create_reconciliation_feedback({
                        'movement_id': movement['id'],
                        'expense_id': best_match['id'],
                        'feedback_type': 'accepted',
                        'confidence': best_match['match_score'],
                        'match_criteria': '{"auto_match": true, "algorithm": "ml_weighted"}',
                        'user_decision': 'auto_accepted',
                        'feedback_notes': f'Auto-matched with confidence {best_match["match_score"]:.2f}'
                    }, tenant_id)

                    stats['matched'] += 1
                else:
                    stats['skipped'] += 1
            else:
                stats['skipped'] += 1

        return stats


# =================== FUNCIONES GLOBALES DE COMPATIBILIDAD ===================
# Estas funciones mantienen compatibilidad con el código existente

_global_adapter = None

def get_unified_adapter(db_path: str = None) -> UnifiedDBAdapter:
    """Obtiene el adaptador global (patrón singleton)"""
    global _global_adapter

    if _global_adapter is None:
        if db_path is None:
            from config.config import Config
            db_path = Config.UNIFIED_DB_PATH
        _global_adapter = UnifiedDBAdapter(db_path)

    return _global_adapter

# Funciones de compatibilidad directa
def record_internal_expense(expense_data: Dict[str, Any], tenant_id: int = 1) -> int:
    return get_unified_adapter().record_internal_expense(expense_data, tenant_id)

def fetch_expense_records(tenant_id: int = 1, limit: int = 100, company_id: Optional[str] = None) -> List[Dict]:
    return get_unified_adapter().fetch_expense_records(tenant_id, limit, company_id)

def fetch_expense_record(expense_id: int) -> Optional[Dict]:
    return get_unified_adapter().fetch_expense_record(expense_id)

def update_expense_record(expense_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    return get_unified_adapter().update_expense_record(expense_id, updates)


def cleanup_legacy_expenses(
    *,
    delete: bool = False,
    confidence_threshold: float = 0.7,
    tenant_id: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    return get_unified_adapter().cleanup_legacy_expenses(
        delete=delete,
        confidence_threshold=confidence_threshold,
        tenant_id=tenant_id,
        dry_run=dry_run,
    )


def list_sat_account_catalog(
    *,
    search: Optional[str] = None,
    include_inactive: bool = False,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return get_unified_adapter().list_sat_account_catalog(
        search=search, include_inactive=include_inactive, limit=limit
    )


def list_sat_product_service_catalog(
    *,
    search: Optional[str] = None,
    include_inactive: bool = False,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return get_unified_adapter().list_sat_product_service_catalog(
        search=search, include_inactive=include_inactive, limit=limit
    )


def get_company_fiscal_profile(tenant_id: int) -> Optional[Dict[str, Any]]:
    return get_unified_adapter().get_company_fiscal_profile(tenant_id)

def list_bank_movements(tenant_id: int = 1) -> List[Dict]:
    return get_unified_adapter().list_bank_movements(tenant_id)

def record_bank_match_feedback(movement_id: int, expense_id: int, feedback: str) -> bool:
    return get_unified_adapter().record_bank_match_feedback(movement_id, expense_id, feedback)

def register_expense_invoice(
    expense_id: int,
    filename: Optional[str] = None,
    file_path: Optional[str] = None,
    content_type: str = "application/pdf",
    parsed_data: str = None,
    tenant_id: int = 1,
    metadata: Optional[Dict[str, Any]] = None,
    model_used: Optional[str] = None,
    processed_by: Optional[int] = None,
    processing_source: Optional[str] = None,
    **legacy_kwargs,
) -> int:
    # Compatibilidad: permitir llamadas legacy con uuid/folio/url/raw_xml/etc.
    legacy_metadata = metadata.copy() if metadata else {}
    if legacy_kwargs:
        uuid_val = legacy_kwargs.get("uuid")
        folio_val = legacy_kwargs.get("folio")
        issued_at = legacy_kwargs.get("issued_at")
        raw_xml = legacy_kwargs.get("raw_xml")
        processing_source = processing_source or legacy_kwargs.get("processing_source") or legacy_kwargs.get("actor")

        if uuid_val and not filename:
            filename = f"{uuid_val}.xml"
        if raw_xml and not parsed_data:
            parsed_data = raw_xml

        legacy_metadata.setdefault("uuid", uuid_val)
        legacy_metadata.setdefault("folio", folio_val)
        legacy_metadata.setdefault("issued_at", issued_at)

    metadata_payload = legacy_metadata or metadata

    return get_unified_adapter().register_expense_invoice(
        expense_id,
        filename or "factura.xml",
        file_path,
        content_type,
        parsed_data,
        tenant_id,
        metadata_payload,
        model_used or (metadata_payload or {}).get("model_used"),
        processed_by,
        processing_source,
    )

def mark_expense_invoiced(expense_id: int, invoice_id: int = None) -> bool:
    return get_unified_adapter().mark_expense_invoiced(expense_id, invoice_id)

def mark_expense_without_invoice(expense_id: int, reason: str = "No facturable") -> bool:
    return get_unified_adapter().mark_expense_without_invoice(expense_id, reason)

def register_user_account(name: str, email: str, tenant_id: int = 1, role: str = "user") -> int:
    return get_unified_adapter().register_user_account(name, email, tenant_id, role)

def get_company_demo_snapshot(tenant_id: int = 1) -> Dict:
    return get_unified_adapter().get_company_demo_snapshot(tenant_id)

def delete_company_expenses(tenant_id: int) -> Dict[str, Any]:
    return get_unified_adapter().delete_company_expenses(tenant_id)

def fetch_candidate_expenses_for_invoice(tenant_id: int = 1, status: str = "pending") -> List[Dict]:
    return get_unified_adapter().fetch_candidate_expenses_for_invoice(tenant_id, status)

# ===== EXPENSE TAGS CONVENIENCE FUNCTIONS =====

def create_expense_tag(name: str, color: str = "#3498db", description: str = None, tenant_id: int = 1, created_by: int = None) -> int:
    return get_unified_adapter().create_expense_tag(name, color, description, tenant_id, created_by)

def get_expense_tags(tenant_id: int = 1, include_usage_count: bool = True) -> List[Dict]:
    return get_unified_adapter().get_expense_tags(tenant_id, include_usage_count)

def update_expense_tag(tag_id: int, name: str = None, color: str = None, description: str = None, tenant_id: int = 1) -> bool:
    return get_unified_adapter().update_expense_tag(tag_id, name, color, description, tenant_id)

def delete_expense_tag(tag_id: int, tenant_id: int = 1) -> bool:
    return get_unified_adapter().delete_expense_tag(tag_id, tenant_id)

def assign_expense_tags(expense_id: int, tag_ids: List[int]) -> bool:
    return get_unified_adapter().assign_expense_tags(expense_id, tag_ids)

def unassign_expense_tags(expense_id: int, tag_ids: List[int]) -> bool:
    return get_unified_adapter().unassign_expense_tags(expense_id, tag_ids)

def replace_expense_tags(expense_id: int, tag_ids: List[int]) -> bool:
    return get_unified_adapter().replace_expense_tags(expense_id, tag_ids)

def get_expense_tags_for_expense(expense_id: int) -> List[Dict]:
    return get_unified_adapter().get_expense_tags_for_expense(expense_id)

def get_expenses_by_tag(tag_id: int, tenant_id: int = 1) -> List[Dict]:
    return get_unified_adapter().get_expenses_by_tag(tag_id, tenant_id)

# ===== ENHANCED INVOICE CONVENIENCE FUNCTIONS =====

def create_invoice_record(invoice_data: Dict[str, Any], tenant_id: int = 1) -> int:
    return get_unified_adapter().create_invoice_record(invoice_data, tenant_id)

def get_invoice_records(tenant_id: int = 1, status: str = None, limit: int = 100) -> List[Dict]:
    return get_unified_adapter().get_invoice_records(tenant_id, status, limit)

def get_invoice_record(invoice_id: int, tenant_id: int = 1) -> Optional[Dict]:
    return get_unified_adapter().get_invoice_record(invoice_id, tenant_id)

def update_invoice_record(invoice_id: int, updates: Dict[str, Any], tenant_id: int = 1) -> bool:
    return get_unified_adapter().update_invoice_record(invoice_id, updates, tenant_id)

def find_matching_expenses(invoice_data: Dict[str, Any], tenant_id: int = 1, threshold: float = 0.8) -> List[Dict]:
    return get_unified_adapter().find_matching_expenses(invoice_data, tenant_id, threshold)


# =================== ONBOARDING EXPORT FUNCTIONS (FUNCIONALIDAD #8) ===================

def create_user(user_data: Dict[str, Any], tenant_id: int = 1) -> int:
    """Create new user with onboarding fields"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        # Serialize demo_preferences to JSON if exists
        demo_preferences_json = None
        if user_data.get('demo_preferences'):
            demo_preferences_json = json.dumps(user_data['demo_preferences'])

        cursor.execute("""
            INSERT INTO users (
                name, email, tenant_id, role, identifier, full_name, company_name,
                onboarding_step, demo_preferences, registration_method, phone,
                verification_token, email_verified, phone_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_data.get('name'),
            user_data.get('email'),
            tenant_id,
            user_data.get('role', 'user'),
            user_data.get('identifier'),
            user_data.get('full_name'),
            user_data.get('company_name'),
            user_data.get('onboarding_step', 0),
            demo_preferences_json,
            user_data.get('registration_method', 'email'),
            user_data.get('phone'),
            user_data.get('verification_token'),
            user_data.get('email_verified', False),
            user_data.get('phone_verified', False)
        ))

        user_id = cursor.lastrowid
        conn.commit()

        logger.info(f"✅ User created: {user_id} ({user_data.get('email')})")
        return user_id

    def get_user(self, user_id: int, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
        """Get user with onboarding data"""
        import json
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users WHERE id = ? AND tenant_id = ?
            """, (user_id, tenant_id))

            row = cursor.fetchone()
            if not row:
                return None

            user_data = dict(row)

            # Parse demo_preferences JSON
            if user_data.get('demo_preferences'):
                try:
                    user_data['demo_preferences'] = json.loads(user_data['demo_preferences'])
                except:
                    user_data['demo_preferences'] = None

            return user_data

    def get_user_by_email(self, email: str, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        import json
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users WHERE email = ? AND tenant_id = ?
            """, (email, tenant_id))

            row = cursor.fetchone()
            if not row:
                return None

            user_data = dict(row)

            # Parse demo_preferences JSON
            if user_data.get('demo_preferences'):
                try:
                    user_data['demo_preferences'] = json.loads(user_data['demo_preferences'])
                except:
                    user_data['demo_preferences'] = None

            return user_data

    def update_user(self, user_id: int, user_data: Dict[str, Any], tenant_id: int = 1) -> bool:
        """Update user data"""
        import json
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build dynamic UPDATE query
            fields = []
            values = []

            allowed_fields = [
                'name', 'full_name', 'company_name', 'onboarding_step',
                'email_verified', 'phone_verified', 'onboarding_completed'
            ]

            for field in allowed_fields:
                if field in user_data:
                    fields.append(f"{field} = ?")
                    values.append(user_data[field])

            # Handle demo_preferences specially
            if 'demo_preferences' in user_data:
                fields.append("demo_preferences = ?")
                values.append(json.dumps(user_data['demo_preferences']) if user_data['demo_preferences'] else None)

            if not fields:
                return False

            # Add completion timestamp if completing onboarding
            if user_data.get('onboarding_completed'):
                fields.append("onboarding_completed_at = ?")
                values.append(datetime.now().isoformat())

            values.extend([user_id, tenant_id])

            query = f"UPDATE users SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?"
            cursor.execute(query, values)

            success = cursor.rowcount > 0
            conn.commit()

            return success

    def update_onboarding_step(self, user_id: int, step_number: int, status: str = "completed",
                             metadata: Optional[Dict[str, Any]] = None, tenant_id: int = 1) -> bool:
        """Update user onboarding step progress"""
        import json
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Update main user table
            cursor.execute("""
                UPDATE users SET onboarding_step = ? WHERE id = ? AND tenant_id = ?
            """, (step_number, user_id, tenant_id))

            # Record step progress
            metadata_json = json.dumps(metadata) if metadata else None
            completed_at = datetime.now().isoformat() if status == "completed" else None

            if self.use_postgres:
                cursor.execute(
                    """
                    DELETE FROM user_onboarding_progress
                    WHERE user_id = ? AND step_id = ? AND tenant_id = ?
                    """,
                    (user_id, step_number, tenant_id),
                )
                insert_sql = """
                    INSERT INTO user_onboarding_progress
                    (user_id, step_id, status, completed_at, metadata, tenant_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
            else:
                insert_sql = """
                    INSERT OR REPLACE INTO user_onboarding_progress
                    (user_id, step_id, status, completed_at, metadata, tenant_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """

            cursor.execute(
                insert_sql,
                (user_id, step_number, status, completed_at, metadata_json, tenant_id),
            )

            conn.commit()
            return True

    def get_user_onboarding_status(self, user_id: int, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
        """Get complete onboarding status for user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM onboarding_status_view WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def generate_demo_data(self, user_id: int, demo_preferences: Dict[str, Any], tenant_id: int = 1) -> Dict[str, Any]:
        """Generate demo data based on user preferences"""
        import random
        import json
        from datetime import timedelta

        results = {
            "expenses_created": 0,
            "invoices_created": 0,
            "bank_movements_created": 0
        }

        prefs = demo_preferences
        amount_min = prefs.get("amount_range", {}).get("min", 100)
        amount_max = prefs.get("amount_range", {}).get("max", 5000)
        date_range_days = prefs.get("date_range_days", 30)
        merchants_count = prefs.get("merchants_count", 10)
        categories = prefs.get("categories", ["office_supplies", "travel", "meals", "software"])

        # Generate merchants
        merchants = [
            "Office Depot", "Amazon Business", "Uber", "Marriott Hotels", "Starbucks",
            "Microsoft Store", "Apple Store", "Best Buy", "Home Depot", "Walmart Business"
        ][:merchants_count]

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Generate expenses
            num_expenses = random.randint(10, 25)
            for i in range(num_expenses):
                expense_data = {
                    'amount': round(random.uniform(amount_min, amount_max), 2),
                    'currency': 'MXN',
                    'description': f"Demo expense {i+1}",
                    'category': random.choice(categories),
                    'merchant_name': random.choice(merchants),
                    'date': (datetime.now() - timedelta(days=random.randint(0, date_range_days))).isoformat(),
                    'user_id': user_id,
                    'tenant_id': tenant_id,
                    'status': 'approved'
                }

                expense_id = self.record_internal_expense(expense_data, tenant_id)
                results["expenses_created"] += 1

                # Generate some invoices
                if prefs.get("include_invoices") and random.random() < 0.3:
                    cursor.execute("""
                        INSERT INTO expense_invoices (expense_id, filename, tenant_id, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (expense_id, f"invoice_{i+1}.pdf", tenant_id, datetime.now().isoformat()))
                    results["invoices_created"] += 1

                # Generate some bank movements
                if prefs.get("include_bank_movements") and random.random() < 0.4:
                    cursor.execute("""
                        INSERT INTO bank_movements
                        (amount, description, date, tenant_id, matched_expense_id, processing_status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        -expense_data['amount'],  # Negative for debit
                        f"Payment to {expense_data['merchant_name']}",
                        expense_data['date'],
                        tenant_id,
                        expense_id,
                        'processed'
                    ))
                    results["bank_movements_created"] += 1

            # Update user demo config
            if self.use_postgres:
                cursor.execute(
                    """
                    DELETE FROM user_demo_config
                    WHERE user_id = ? AND demo_type = ? AND tenant_id = ?
                    """,
                    (user_id, 'complete_demo', tenant_id),
                )
                insert_demo_sql = """
                    INSERT INTO user_demo_config
                    (user_id, demo_type, config_data, generated_records, last_generated, tenant_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
            else:
                insert_demo_sql = """
                    INSERT OR REPLACE INTO user_demo_config
                    (user_id, demo_type, config_data, generated_records, last_generated, tenant_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """

            cursor.execute(
                insert_demo_sql,
                (
                    user_id,
                    'complete_demo',
                    json.dumps(demo_preferences),
                    results["expenses_created"],
                    datetime.now().isoformat(),
                    tenant_id,
                ),
            )

            conn.commit()

        logger.info(f"✅ Demo data generated for user {user_id}: {results}")
        return results


# =================== EXPORTS FOR MAIN.PY ===================

def create_user(user_data: Dict[str, Any], tenant_id: int = 1) -> int:
    """Create new user - Export function"""
    adapter = get_unified_adapter()
    return adapter.create_user(user_data, tenant_id)

def get_user(user_id: int, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Get user - Export function"""
    adapter = get_unified_adapter()
    return adapter.get_user(user_id, tenant_id)

def get_user_by_email(email: str, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Get user by email - Export function"""
    adapter = get_unified_adapter()
    return adapter.get_user_by_email(email, tenant_id)

def update_user(user_id: int, user_data: Dict[str, Any], tenant_id: int = 1) -> bool:
    """Update user - Export function"""
    adapter = get_unified_adapter()
    return adapter.update_user(user_id, user_data, tenant_id)

def update_onboarding_step(user_id: int, step_number: int, status: str = "completed",
                         metadata: Optional[Dict[str, Any]] = None, tenant_id: int = 1) -> bool:
    """Update onboarding step - Export function"""
    adapter = get_unified_adapter()
    return adapter.update_onboarding_step(user_id, step_number, status, metadata, tenant_id)

def get_user_onboarding_status(user_id: int, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Get onboarding status - Export function"""
    adapter = get_unified_adapter()
    return adapter.get_user_onboarding_status(user_id, tenant_id)

def generate_demo_data(user_id: int, demo_preferences: Dict[str, Any], tenant_id: int = 1) -> Dict[str, Any]:
    """Generate demo data - Export function"""
    adapter = get_unified_adapter()
    return adapter.generate_demo_data(user_id, demo_preferences, tenant_id)


# =================== DUPLICATE DETECTION EXPORT FUNCTIONS (FUNCIONALIDAD #9) ===================

def detect_duplicates(expense_data: Dict[str, Any], tenant_id: int = 1, threshold: float = 0.65) -> List[Dict[str, Any]]:
    """Detect potential duplicates for an expense"""
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        # Get existing expenses for comparison
        cursor.execute("""
            SELECT * FROM expense_records
            WHERE tenant_id = ? AND id != ?
            ORDER BY created_at DESC LIMIT 100
        """, (tenant_id, expense_data.get('id', -1)))

        existing_expenses = [dict(row) for row in cursor.fetchall()]

        # Use the optimized duplicate detector
        from .optimized_duplicate_detector import detect_expense_duplicates_optimized
        result = detect_expense_duplicates_optimized(expense_data, existing_expenses, {
            'similarity_thresholds': {'low': threshold}
        })

        return result.get('duplicates', [])

def save_duplicate_detection(expense_id: int, potential_duplicate_id: int,
                           similarity_score: float, match_reasons: List[str],
                           confidence_level: str, risk_level: str = "medium",
                           detection_method: str = "hybrid", tenant_id: int = 1) -> int:
    """Save duplicate detection to database"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO duplicate_detections (
                expense_id, potential_duplicate_id, similarity_score,
                risk_level, confidence_level, match_reasons,
                detection_method, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense_id, potential_duplicate_id, similarity_score,
            risk_level, confidence_level, json.dumps(match_reasons),
            detection_method, tenant_id
        ))

        detection_id = cursor.lastrowid
        conn.commit()
        return detection_id

def update_expense_duplicate_info(expense_id: int, duplicate_info: Dict[str, Any], tenant_id: int = 1) -> bool:
    """Update expense with duplicate detection info"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        # Build update query dynamically
        fields = []
        values = []

        if 'similarity_score' in duplicate_info:
            fields.append('similarity_score = ?')
            values.append(duplicate_info['similarity_score'])

        if 'risk_level' in duplicate_info:
            fields.append('risk_level = ?')
            values.append(duplicate_info['risk_level'])

        if 'is_duplicate' in duplicate_info:
            fields.append('is_duplicate = ?')
            values.append(duplicate_info['is_duplicate'])

        if 'duplicate_of' in duplicate_info:
            fields.append('duplicate_of = ?')
            values.append(duplicate_info['duplicate_of'])

        if 'duplicate_confidence' in duplicate_info:
            fields.append('duplicate_confidence = ?')
            values.append(duplicate_info['duplicate_confidence'])

        if 'ml_features_json' in duplicate_info:
            fields.append('ml_features_json = ?')
            values.append(json.dumps(duplicate_info['ml_features_json']) if duplicate_info['ml_features_json'] else None)

        if not fields:
            return False

        values.extend([expense_id, tenant_id])

        query = f"""
            UPDATE expense_records
            SET {', '.join(fields)}
            WHERE id = ? AND tenant_id = ?
        """

        cursor.execute(query, values)
        success = cursor.rowcount > 0
        conn.commit()

        return success

def get_duplicate_stats(tenant_id: int = 1) -> Dict[str, Any]:
    """Get duplicate detection statistics"""
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        # Total expenses
        cursor.execute("SELECT COUNT(*) FROM expense_records WHERE tenant_id = ?", (tenant_id,))
        total_expenses = cursor.fetchone()[0]

        # Duplicate detections
        cursor.execute("""
            SELECT
                COUNT(*) as total_detections,
                SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN confidence_level = 'high' AND status = 'pending' THEN 1 ELSE 0 END) as high_risk_pending,
                SUM(CASE WHEN confidence_level = 'medium' AND status = 'pending' THEN 1 ELSE 0 END) as medium_risk_pending,
                SUM(CASE WHEN confidence_level = 'low' AND status = 'pending' THEN 1 ELSE 0 END) as low_risk_pending
            FROM duplicate_detections
            WHERE tenant_id = ?
        """, (tenant_id,))

        stats_row = cursor.fetchone()
        stats = dict(stats_row) if stats_row else {}

        return {
            'total_expenses': total_expenses,
            'duplicates_detected': stats.get('total_detections', 0),
            'duplicates_confirmed': stats.get('confirmed', 0),
            'duplicates_rejected': stats.get('rejected', 0),
            'high_risk_pending': stats.get('high_risk_pending', 0),
            'medium_risk_pending': stats.get('medium_risk_pending', 0),
            'low_risk_pending': stats.get('low_risk_pending', 0)
        }

def review_duplicate_detection(detection_id: int, action: str, reviewer_id: int,
                             notes: Optional[str] = None, tenant_id: int = 1) -> bool:
    """Review and update duplicate detection"""
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE duplicate_detections
            SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
        """, (action, reviewer_id, detection_id, tenant_id))

        success = cursor.rowcount > 0
        conn.commit()

        return success

def get_duplicate_detection_config(tenant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Get duplicate detection configuration"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM duplicate_detection_config
            WHERE tenant_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (tenant_id,))

        row = cursor.fetchone()
        if not row:
            return None

        config = dict(row)

        # Parse JSON fields
        try:
            if config.get('features_config'):
                config['features_config'] = json.loads(config['features_config'])
            if config.get('ml_model_config'):
                config['ml_model_config'] = json.loads(config['ml_model_config'])
        except:
            pass

        return config

def save_expense_ml_features(expense_id: int, features: Dict[str, Any],
                           embedding_vector: Optional[List[float]] = None,
                           extraction_method: str = "rule_based",
                           feature_quality_score: Optional[float] = None,
                           tenant_id: int = 1) -> int:
    """Save ML features for an expense"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        if adapter.use_postgres:
            cursor.execute(
                """
                DELETE FROM expense_ml_features
                WHERE expense_id = ? AND tenant_id = ?
                """,
                (expense_id, tenant_id),
            )
            insert_features_sql = """
                INSERT INTO expense_ml_features (
                    expense_id, feature_vector, embedding_vector,
                    extraction_method, feature_quality_score, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?)
            """
        else:
            insert_features_sql = """
                INSERT OR REPLACE INTO expense_ml_features (
                    expense_id, feature_vector, embedding_vector,
                    extraction_method, feature_quality_score, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?)
            """

        cursor.execute(
            insert_features_sql,
            (
                expense_id,
                json.dumps(features),
                json.dumps(embedding_vector) if embedding_vector else None,
                extraction_method,
                feature_quality_score,
                tenant_id,
            ),
        )

        feature_id = cursor.lastrowid
        conn.commit()
        return feature_id

def get_expense_ml_features(expense_id: int, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Get ML features for an expense"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM expense_ml_features
            WHERE expense_id = ? AND tenant_id = ?
        """, (expense_id, tenant_id))

        row = cursor.fetchone()
        if not row:
            return None

        features = dict(row)

        # Parse JSON fields
        try:
            if features.get('feature_vector'):
                features['feature_vector'] = json.loads(features['feature_vector'])
            if features.get('embedding_vector'):
                features['embedding_vector'] = json.loads(features['embedding_vector'])
        except:
            pass

        return features


# =================== CATEGORY PREDICTION EXPORT FUNCTIONS (FUNCIONALIDAD #10) ===================

def predict_expense_category(expense_data: Dict[str, Any], tenant_id: int = 1,
                           user_id: Optional[int] = None) -> Dict[str, Any]:
    """Predict category for an expense using ML and rules"""
    from .category_predictor import CategoryPredictor

    predictor = CategoryPredictor()

    # Get user preferences if user_id provided
    user_history = []
    if user_id:
        user_history = get_user_category_preferences(user_id, tenant_id)

    prediction = predictor.predict_category(expense_data, user_history)

    return {
        'category': prediction.category,
        'confidence': prediction.confidence,
        'reasoning': prediction.reasoning,
        'alternatives': prediction.alternatives,
        'prediction_method': 'hybrid',
        'ml_model_version': '1.0'
    }

def save_category_prediction(expense_id: int, prediction_data: Dict[str, Any], tenant_id: int = 1) -> bool:
    """Save category prediction to expense record"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE expense_records
            SET categoria_sugerida = ?, confianza = ?, razonamiento = ?,
                ml_model_version = ?, prediction_method = ?, category_alternatives = ?,
                predicted_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
        """, (
            prediction_data.get('category'),
            prediction_data.get('confidence', 0.0),
            prediction_data.get('reasoning'),
            prediction_data.get('ml_model_version'),
            prediction_data.get('prediction_method', 'hybrid'),
            json.dumps(prediction_data.get('alternatives', [])),
            expense_id,
            tenant_id
        ))

        success = cursor.rowcount > 0
        conn.commit()

        # Save to prediction history
        if success:
            cursor.execute("""
                INSERT INTO category_prediction_history (
                    expense_id, predicted_category, confidence, reasoning,
                    alternatives, prediction_method, ml_model_version, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                expense_id,
                prediction_data.get('category'),
                prediction_data.get('confidence', 0.0),
                prediction_data.get('reasoning'),
                json.dumps(prediction_data.get('alternatives', [])),
                prediction_data.get('prediction_method', 'hybrid'),
                prediction_data.get('ml_model_version'),
                tenant_id
            ))
            conn.commit()

        return success

def get_user_category_preferences(user_id: int, tenant_id: int = 1) -> List[Dict[str, Any]]:
    """Get user's category preferences"""
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM user_category_preferences
            WHERE user_id = ? AND tenant_id = ? AND active = TRUE
            ORDER BY frequency DESC, last_used DESC
        """, (user_id, tenant_id))

        return [dict(row) for row in cursor.fetchall()]

def record_category_feedback(expense_id: int, feedback_data: Dict[str, Any], tenant_id: int = 1) -> bool:
    """Record user feedback on category prediction"""
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        # Update prediction history with feedback
        cursor.execute("""
            UPDATE category_prediction_history
            SET user_feedback = ?, corrected_category = ?, feedback_date = CURRENT_TIMESTAMP
            WHERE expense_id = ? AND tenant_id = ?
        """, (
            feedback_data.get('feedback_type'),
            feedback_data.get('actual_category'),
            expense_id,
            tenant_id
        ))

        # Update expense record if corrected
        if feedback_data.get('feedback_type') == 'corrected':
            cursor.execute("""
                UPDATE expense_records
                SET category = ?, category_confirmed = TRUE, category_corrected_by = ?
                WHERE id = ? AND tenant_id = ?
            """, (
                feedback_data.get('actual_category'),
                feedback_data.get('user_id'),
                expense_id,
                tenant_id
            ))

        success = cursor.rowcount > 0
        conn.commit()
        return success

def get_category_stats(tenant_id: int = 1) -> Dict[str, Any]:
    """Get category prediction statistics"""
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        # Get prediction stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_predictions,
                SUM(CASE WHEN user_feedback = 'accepted' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN user_feedback = 'corrected' THEN 1 ELSE 0 END) as corrected,
                AVG(confidence) as avg_confidence
            FROM category_prediction_history
            WHERE tenant_id = ?
        """, (tenant_id,))

        stats_row = cursor.fetchone()
        stats = dict(stats_row) if stats_row else {}

        # Get most common categories
        cursor.execute("""
            SELECT predicted_category, COUNT(*) as count
            FROM category_prediction_history
            WHERE tenant_id = ?
            GROUP BY predicted_category
            ORDER BY count DESC LIMIT 5
        """, (tenant_id,))

        common_categories = [dict(row) for row in cursor.fetchall()]

        # Get preference counts
        cursor.execute("SELECT COUNT(*) FROM user_category_preferences WHERE tenant_id = ?", (tenant_id,))
        preferences_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM custom_categories WHERE tenant_id = ?", (tenant_id,))
        custom_categories_count = cursor.fetchone()[0]

        total = stats.get('total_predictions', 0)
        accepted = stats.get('accepted', 0)

        return {
            'total_predictions': total,
            'predictions_accepted': accepted,
            'predictions_corrected': stats.get('corrected', 0),
            'accuracy_rate': accepted / total if total > 0 else 0.0,
            'avg_confidence': stats.get('avg_confidence', 0.0) or 0.0,
            'most_common_categories': common_categories,
            'user_preferences_count': preferences_count,
            'custom_categories_count': custom_categories_count
        }

def get_category_prediction_config(tenant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Get category prediction configuration"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM category_prediction_config
            WHERE tenant_id = ?
        """, (tenant_id,))

        row = cursor.fetchone()
        if not row:
            return None

        config = dict(row)

        # Parse JSON fields
        try:
            if config.get('categories_config'):
                config['categories_config'] = json.loads(config['categories_config'])
            if config.get('features_weights'):
                config['features_weights'] = json.loads(config['features_weights'])
        except:
            pass

        return config

def get_custom_categories(tenant_id: int = 1) -> List[Dict[str, Any]]:
    """Get custom categories for tenant"""
    import json
    adapter = get_unified_adapter()
    with adapter.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM custom_categories
            WHERE tenant_id = ? AND is_active = TRUE
            ORDER BY sort_order, category_name
        """, (tenant_id,))

        categories = []
        for row in cursor.fetchall():
            category = dict(row)
            # Parse JSON fields
            try:
                if category.get('keywords'):
                    category['keywords'] = json.loads(category['keywords'])
                if category.get('merchant_patterns'):
                    category['merchant_patterns'] = json.loads(category['merchant_patterns'])
            except:
                category['keywords'] = []
                category['merchant_patterns'] = []
            categories.append(category)

        return categories


if __name__ == "__main__":
    # Test del adaptador
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")

        # Test de funciones
        expenses = adapter.fetch_expense_records()
        print(f"✅ Gastos: {len(expenses)}")

        jobs = adapter.get_automation_jobs()
        print(f"✅ Jobs: {len(jobs)}")

        stats = adapter.get_system_stats()
        print(f"✅ Stats: {stats}")

        health = adapter.health_check()
        print(f"✅ Health: {health['status']}")

        print("🎉 Adaptador funcionando correctamente!")

    except Exception as e:
        print(f"❌ Error: {e}")

# =================== FUNCIONES INDEPENDIENTES PARA IMPORTACIÓN ===================

def create_bank_movement(movement_data: Dict[str, Any], tenant_id: int = 1) -> int:
    """Función independiente para crear movimientos bancarios"""
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")
        return adapter.create_bank_movement(movement_data, tenant_id)
    except Exception as e:
        logger.error(f"Error creando movimiento bancario: {e}")
        raise

def get_bank_movement(movement_id: int, tenant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Función independiente para obtener movimiento bancario"""
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")
        return adapter.get_bank_movement(movement_id, tenant_id)
    except Exception as e:
        logger.error(f"Error obteniendo movimiento bancario: {e}")
        raise

def update_bank_movement(movement_id: int, updates: Dict[str, Any], tenant_id: int = 1) -> bool:
    """Función independiente para actualizar movimiento bancario"""
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")
        return adapter.update_bank_movement(movement_id, updates, tenant_id)
    except Exception as e:
        logger.error(f"Error actualizando movimiento bancario: {e}")
        raise

def find_matching_expenses_for_movement(movement_data: Dict[str, Any], tenant_id: int = 1) -> List[Dict[str, Any]]:
    """Función independiente para encontrar gastos que coincidan con movimiento"""
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")
        return adapter.find_matching_expenses_for_movement(movement_data, tenant_id)
    except Exception as e:
        logger.error(f"Error buscando gastos coincidentes: {e}")
        return []

def perform_auto_reconciliation(parameters: Dict[str, Any], tenant_id: int = 1) -> Dict[str, Any]:
    """Función independiente para auto-reconciliación"""
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")
        return adapter.perform_auto_reconciliation(parameters, tenant_id)
    except Exception as e:
        logger.error(f"Error en auto-reconciliación: {e}")
        return {"status": "error", "message": str(e)}

def get_bank_matching_rules(tenant_id: int = 1) -> List[Dict[str, Any]]:
    """Función independiente para obtener reglas de matching bancario"""
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")
        return adapter.get_bank_matching_rules(tenant_id)
    except Exception as e:
        logger.error(f"Error obteniendo reglas bancarias: {e}")
        return []

def create_bank_matching_rule(rule_data: Dict[str, Any], tenant_id: int = 1) -> int:
    """Función independiente para crear regla de matching bancario"""
    try:
        adapter = get_unified_adapter("/Users/danielgoes96/Desktop/mcp-server/unified_mcp_system.db")
        return adapter.create_bank_matching_rule(rule_data, tenant_id)
    except Exception as e:
        logger.error(f"Error creando regla bancaria: {e}")
        raise


# =================== ROLES Y DEPARTAMENTOS - HELPERS ===================

def get_user_roles_with_details(user_id: int) -> List[Dict[str, Any]]:
    """
    Obtener todos los roles asignados a un usuario con detalles completos.

    Args:
        user_id: ID del usuario

    Returns:
        Lista de roles con información completa (name, display_name, level, permissions, etc.)
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                r.id,
                r.name,
                r.display_name,
                r.description,
                r.level,
                r.permissions,
                r.is_system,
                ur.assigned_at,
                ur.expires_at
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = ?
              AND r.is_active = TRUE
              AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
            ORDER BY r.level DESC
        """, (user_id,))

        roles = []
        for row in cursor.fetchall():
            roles.append({
                'id': row[0],
                'name': row[1],
                'display_name': row[2],
                'description': row[3],
                'level': row[4],
                'permissions': row[5],
                'is_system': row[6],
                'assigned_at': row[7],
                'expires_at': row[8]
            })

        conn.close()
        return roles

    except Exception as e:
        logger.error(f"Error obteniendo roles del usuario {user_id}: {e}")
        return []


def get_user_departments_with_details(user_id: int) -> List[Dict[str, Any]]:
    """
    Obtener todos los departamentos asignados a un usuario con detalles.

    Args:
        user_id: ID del usuario

    Returns:
        Lista de departamentos con información completa
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                d.id,
                d.tenant_id,
                d.name,
                d.code,
                d.parent_id,
                d.manager_user_id,
                d.description,
                d.cost_center,
                ud.is_primary,
                ud.assigned_at
            FROM user_departments ud
            JOIN departments d ON ud.department_id = d.id
            WHERE ud.user_id = ?
              AND d.is_active = TRUE
            ORDER BY ud.is_primary DESC, d.name ASC
        """, (user_id,))

        departments = []
        for row in cursor.fetchall():
            departments.append({
                'id': row[0],
                'tenant_id': row[1],
                'name': row[2],
                'code': row[3],
                'parent_id': row[4],
                'manager_user_id': row[5],
                'description': row[6],
                'cost_center': row[7],
                'is_primary': row[8],
                'assigned_at': row[9]
            })

        conn.close()
        return departments

    except Exception as e:
        logger.error(f"Error obteniendo departamentos del usuario {user_id}: {e}")
        return []


def get_department_users(department_id: int, include_subdepartments: bool = False) -> List[Dict[str, Any]]:
    """
    Obtener todos los usuarios asignados a un departamento.

    Args:
        department_id: ID del departamento
        include_subdepartments: Si True, incluye usuarios de subdepartamentos

    Returns:
        Lista de usuarios con información básica
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        if include_subdepartments:
            # Incluir subdepartamentos recursivamente
            cursor.execute("""
                WITH RECURSIVE dept_tree AS (
                    SELECT id FROM departments WHERE id = ?
                    UNION ALL
                    SELECT d.id FROM departments d
                    JOIN dept_tree dt ON d.parent_id = dt.id
                    WHERE d.is_active = TRUE
                )
                SELECT DISTINCT
                    u.id,
                    u.email,
                    u.full_name,
                    u.role,
                    u.tenant_id,
                    ud.is_primary,
                    ud.assigned_at
                FROM user_departments ud
                JOIN users u ON ud.user_id = u.id
                WHERE ud.department_id IN (SELECT id FROM dept_tree)
                  AND u.is_active = TRUE
                ORDER BY u.full_name ASC
            """, (department_id,))
        else:
            # Solo departamento específico
            cursor.execute("""
                SELECT
                    u.id,
                    u.email,
                    u.full_name,
                    u.role,
                    u.tenant_id,
                    ud.is_primary,
                    ud.assigned_at
                FROM user_departments ud
                JOIN users u ON ud.user_id = u.id
                WHERE ud.department_id = ?
                  AND u.is_active = TRUE
                ORDER BY u.full_name ASC
            """, (department_id,))

        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'email': row[1],
                'full_name': row[2],
                'role': row[3],
                'tenant_id': row[4],
                'is_primary': row[5],
                'assigned_at': row[6]
            })

        conn.close()
        return users

    except Exception as e:
        logger.error(f"Error obteniendo usuarios del departamento {department_id}: {e}")
        return []


def get_user_subordinates_hierarchy(user_id: int, include_indirect: bool = False) -> List[Dict[str, Any]]:
    """
    Obtener subordinados de un usuario en la jerarquía organizacional.

    Args:
        user_id: ID del supervisor
        include_indirect: Si True, incluye subordinados indirectos (subordinados de subordinados)

    Returns:
        Lista de subordinados con información completa
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        if include_indirect:
            # Subordinados directos e indirectos (recursivo)
            cursor.execute("""
                WITH RECURSIVE hierarchy AS (
                    -- Subordinados directos
                    SELECT
                        uh.user_id,
                        uh.supervisor_id,
                        uh.relationship_type,
                        uh.effective_from,
                        uh.effective_to,
                        1 as depth
                    FROM user_hierarchy uh
                    WHERE uh.supervisor_id = ?
                      AND (uh.effective_to IS NULL OR uh.effective_to > CURRENT_DATE)

                    UNION ALL

                    -- Subordinados indirectos
                    SELECT
                        uh.user_id,
                        uh.supervisor_id,
                        uh.relationship_type,
                        uh.effective_from,
                        uh.effective_to,
                        h.depth + 1
                    FROM user_hierarchy uh
                    JOIN hierarchy h ON uh.supervisor_id = h.user_id
                    WHERE (uh.effective_to IS NULL OR uh.effective_to > CURRENT_DATE)
                      AND h.depth < 10  -- Límite de profundidad para evitar loops
                )
                SELECT DISTINCT
                    u.id,
                    u.email,
                    u.full_name,
                    u.role,
                    u.tenant_id,
                    h.relationship_type,
                    h.depth
                FROM hierarchy h
                JOIN users u ON h.user_id = u.id
                WHERE u.is_active = TRUE
                ORDER BY h.depth ASC, u.full_name ASC
            """, (user_id,))
        else:
            # Solo subordinados directos
            cursor.execute("""
                SELECT
                    u.id,
                    u.email,
                    u.full_name,
                    u.role,
                    u.tenant_id,
                    uh.relationship_type,
                    1 as depth
                FROM user_hierarchy uh
                JOIN users u ON uh.user_id = u.id
                WHERE uh.supervisor_id = ?
                  AND (uh.effective_to IS NULL OR uh.effective_to > CURRENT_DATE)
                  AND u.is_active = TRUE
                ORDER BY u.full_name ASC
            """, (user_id,))

        subordinates = []
        for row in cursor.fetchall():
            subordinates.append({
                'id': row[0],
                'email': row[1],
                'full_name': row[2],
                'role': row[3],
                'tenant_id': row[4],
                'relationship_type': row[5],
                'depth': row[6]
            })

        conn.close()
        return subordinates

    except Exception as e:
        logger.error(f"Error obteniendo subordinados del usuario {user_id}: {e}")
        return []


def get_all_roles(tenant_id: Optional[int] = None, include_system: bool = True) -> List[Dict[str, Any]]:
    """
    Obtener todos los roles disponibles.

    Args:
        tenant_id: Si se especifica, incluye roles tenant-específicos. None = solo sistema
        include_system: Si True, incluye roles del sistema

    Returns:
        Lista de roles disponibles
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        if tenant_id is None:
            # Solo roles del sistema
            cursor.execute("""
                SELECT
                    id, name, display_name, description, level,
                    permissions, is_system, is_active
                FROM roles
                WHERE tenant_id IS NULL
                  AND is_active = TRUE
                ORDER BY level DESC, name ASC
            """)
        elif include_system:
            # Roles del sistema + tenant específicos
            cursor.execute("""
                SELECT
                    id, name, display_name, description, level,
                    permissions, is_system, is_active
                FROM roles
                WHERE (tenant_id IS NULL OR tenant_id = ?)
                  AND is_active = TRUE
                ORDER BY level DESC, name ASC
            """, (tenant_id,))
        else:
            # Solo roles tenant-específicos
            cursor.execute("""
                SELECT
                    id, name, display_name, description, level,
                    permissions, is_system, is_active
                FROM roles
                WHERE tenant_id = ?
                  AND is_active = TRUE
                ORDER BY level DESC, name ASC
            """, (tenant_id,))

        roles = []
        for row in cursor.fetchall():
            roles.append({
                'id': row[0],
                'name': row[1],
                'display_name': row[2],
                'description': row[3],
                'level': row[4],
                'permissions': row[5],
                'is_system': row[6],
                'is_active': row[7]
            })

        conn.close()
        return roles

    except Exception as e:
        logger.error(f"Error obteniendo roles: {e}")
        return []


def get_all_departments(tenant_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Obtener todos los departamentos de un tenant.

    Args:
        tenant_id: ID del tenant
        include_inactive: Si True, incluye departamentos inactivos

    Returns:
        Lista de departamentos
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        if include_inactive:
            cursor.execute("""
                SELECT
                    id, tenant_id, name, code, parent_id,
                    manager_user_id, description, cost_center,
                    is_active, created_at
                FROM departments
                WHERE tenant_id = ?
                ORDER BY name ASC
            """, (tenant_id,))
        else:
            cursor.execute("""
                SELECT
                    id, tenant_id, name, code, parent_id,
                    manager_user_id, description, cost_center,
                    is_active, created_at
                FROM departments
                WHERE tenant_id = ?
                  AND is_active = TRUE
                ORDER BY name ASC
            """, (tenant_id,))

        departments = []
        for row in cursor.fetchall():
            departments.append({
                'id': row[0],
                'tenant_id': row[1],
                'name': row[2],
                'code': row[3],
                'parent_id': row[4],
                'manager_user_id': row[5],
                'description': row[6],
                'cost_center': row[7],
                'is_active': row[8],
                'created_at': row[9]
            })

        conn.close()
        return departments

    except Exception as e:
        logger.error(f"Error obteniendo departamentos: {e}")
        return []
