"""
Helpers to load company-level settings and fiscal policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import json
import logging
import sqlite3

from config.config import config

logger = logging.getLogger(__name__)


@dataclass
class CompanySettings:
    company_id: int
    company_name: Optional[str] = None
    regimen_fiscal_code: Optional[str] = None
    regimen_fiscal_desc: Optional[str] = None
    cfdi_required: bool = True
    iva_policy: str = "standard"  # standard | double_phase | no_iva
    payment_policy: str = "company_account"  # company_account | employee_reimbursed | mixed
    raw_config: Dict[str, Any] = None


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _load_company_row(company_id: int) -> Optional[sqlite3.Row]:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, company_name, regimen_fiscal_code, regimen_fiscal_desc, config
            FROM companies
            WHERE id = ?
            """,
            (company_id,),
        )
        return cursor.fetchone()
    except sqlite3.Error as exc:
        logger.error("Failed to load company settings for %s: %s", company_id, exc)
        return None
    finally:
        conn.close()


def get_company_settings(company_id: int) -> Optional[CompanySettings]:
    row = _load_company_row(company_id)
    if not row:
        return None

    raw_config: Dict[str, Any] = {}
    if row["config"]:
        try:
            raw_config = json.loads(row["config"])
            if not isinstance(raw_config, dict):
                raw_config = {}
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in companies.config for id=%s", company_id)

    fiscal_cfg = raw_config.get("fiscal_policy", {}) if isinstance(raw_config.get("fiscal_policy"), dict) else {}
    cash_cfg = raw_config.get("cash_policy", {}) if isinstance(raw_config.get("cash_policy"), dict) else {}

    settings = CompanySettings(
        company_id=company_id,
        company_name=row["company_name"],
        regimen_fiscal_code=row["regimen_fiscal_code"],
        regimen_fiscal_desc=row["regimen_fiscal_desc"],
        cfdi_required=_parse_bool(fiscal_cfg.get("cfdi_required"), True),
        iva_policy=fiscal_cfg.get("iva_policy", "standard"),
        payment_policy=cash_cfg.get("default_payment_mode", "company_account"),
        raw_config=raw_config,
    )
    return settings


def get_company_settings_by_tenant(tenant_id: int) -> Optional[CompanySettings]:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM companies
            WHERE tenant_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return get_company_settings(int(row["id"]))
    except sqlite3.Error as exc:
        logger.error("Failed to load company by tenant %s: %s", tenant_id, exc)
        return None
    finally:
        conn.close()
