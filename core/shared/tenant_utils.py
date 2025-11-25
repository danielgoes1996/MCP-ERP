"""Canonical tenant/company ID mapping utilities.

This module provides the SINGLE source of truth for converting between:
- tenant_id (INTEGER): Used in expense_invoices, expenses, and most DB tables
- company_id (TEXT): Used in sat_invoices and API/UX layers

Created: 2025-01-13
Purpose: Centralize all tenant↔company conversions to avoid inconsistencies
"""

from typing import Tuple, Optional
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from core.shared.db_config import POSTGRES_CONFIG

logger = logging.getLogger(__name__)


class TenantMappingError(ValueError):
    """Raised when tenant/company mapping fails"""
    pass


def get_tenant_and_company(company_id_str: str) -> Tuple[int, str]:
    """
    Canonical way to map company_id string to tenant_id int.

    This is the ONLY function that should be used for company_id → tenant_id conversion.

    Args:
        company_id_str: Company identifier as string (e.g., "contaflow", "carreta_verde")

    Returns:
        Tuple of (tenant_id as int, company_id as string)

    Raises:
        TenantMappingError: If company_id is not found in tenants table

    Example:
        tenant_id, company_id = get_tenant_and_company("contaflow")
        # Returns: (2, "contaflow")
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, company_id
            FROM tenants
            WHERE company_id = %s
        """, (company_id_str,))

        row = cursor.fetchone()

        if not row:
            raise TenantMappingError(
                f"No tenant found for company_id='{company_id_str}'. "
                f"Please verify the company exists in the tenants table."
            )

        tenant_id = row['id']
        company_id = row['company_id']

        logger.debug(f"Mapped company_id='{company_id}' → tenant_id={tenant_id}")

        return (tenant_id, company_id)

    finally:
        conn.close()


def get_company_id_from_tenant(tenant_id: int) -> str:
    """
    Canonical way to map tenant_id int to company_id string.

    This is the ONLY function that should be used for tenant_id → company_id conversion.

    Args:
        tenant_id: Tenant identifier as integer (e.g., 2, 3)

    Returns:
        company_id as string (e.g., "contaflow")

    Raises:
        TenantMappingError: If tenant_id is not found in tenants table

    Example:
        company_id = get_company_id_from_tenant(2)
        # Returns: "contaflow"
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT company_id
            FROM tenants
            WHERE id = %s
        """, (tenant_id,))

        row = cursor.fetchone()

        if not row or not row['company_id']:
            raise TenantMappingError(
                f"No company_id found for tenant_id={tenant_id}. "
                f"Please verify the tenant exists in the tenants table."
            )

        company_id = row['company_id']

        logger.debug(f"Mapped tenant_id={tenant_id} → company_id='{company_id}'")

        return company_id

    finally:
        conn.close()


def validate_tenant_exists(tenant_id: int) -> bool:
    """
    Check if a tenant_id exists in the tenants table.

    Args:
        tenant_id: Tenant identifier as integer

    Returns:
        True if tenant exists, False otherwise
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT EXISTS(SELECT 1 FROM tenants WHERE id = %s)
        """, (tenant_id,))

        return cursor.fetchone()[0]

    finally:
        conn.close()


def validate_company_exists(company_id: str) -> bool:
    """
    Check if a company_id exists in the tenants table.

    Args:
        company_id: Company identifier as string

    Returns:
        True if company exists, False otherwise
    """
    conn = psycopg2.connect(**POSTGRES_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT EXISTS(SELECT 1 FROM tenants WHERE company_id = %s)
        """, (company_id,))

        return cursor.fetchone()[0]

    finally:
        conn.close()
