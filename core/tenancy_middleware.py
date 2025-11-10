"""
Multi-tenancy middleware for MCP Server
Ensures all database operations are isolated by tenant
"""

from fastapi import Request, HTTPException, Depends
from typing import Optional
import logging

from core.auth.unified import get_current_active_user, UserInDB
from config.config import config

try:
    from core.shared.unified_db_adapter import get_unified_adapter
except Exception:  # pragma: no cover - fallback when adapter not available
    get_unified_adapter = None

logger = logging.getLogger(__name__)


PF_REGIME_CODES = {
    "605",  # Sueldos y salarios e ingresos asimilados
    "606",  # Arrendamiento
    "608",  # Demás ingresos
    "610",  # Actividades profesionales
    "611",  # Ingresos por intereses
    "612",  # Actividades primarias
    "614",  # Dividendos
    "615",  # Personas físicas con actividades empresariales y profesionales
    "616",  # Sin obligaciones fiscales
    "621",  # Incorporación fiscal
    "622",
    "623",
    "624",
    "625",
}
RESICO_REGIME_CODES = {"626"}


def _map_fiscal_regime_group(
    regime_code: Optional[str],
    regime_desc: Optional[str],
) -> str:
    """Map SAT regime code/description to simplified groups used for rules."""

    if regime_code:
        normalized_code = regime_code.strip()
        if normalized_code in RESICO_REGIME_CODES:
            return "RESICO"
        if normalized_code in PF_REGIME_CODES:
            return "PF"
        if normalized_code == "601":
            return "PM_GENERAL"
        if normalized_code == "603":
            return "PM_GENERAL"

    if regime_desc:
        normalized_desc = regime_desc.strip().lower()
        if "resico" in normalized_desc or "simplificado de confianza" in normalized_desc:
            return "RESICO"
        if "persona física" in normalized_desc or "personas físicas" in normalized_desc:
            return "PF"

    return "PM_GENERAL"

class TenancyContext:
    """Context object that holds tenant information for the current request"""

    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        user: UserInDB,
        fiscal_regime_code: Optional[str] = None,
        fiscal_regime_desc: Optional[str] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user = user
        self.is_superuser = user.is_superuser
        self.fiscal_regime_code = fiscal_regime_code
        self.fiscal_regime_desc = fiscal_regime_desc
        self.fiscal_regime_group = _map_fiscal_regime_group(fiscal_regime_code, fiscal_regime_desc)

    def can_access_tenant(self, target_tenant_id: int) -> bool:
        """Check if current user can access data from target tenant"""
        # Superusers can access any tenant
        if self.is_superuser:
            return True

        # Regular users can only access their own tenant
        return self.tenant_id == target_tenant_id

    def enforce_tenant_isolation(self, target_tenant_id: Optional[int] = None) -> int:
        """Enforce tenant isolation and return the tenant_id to use"""
        if target_tenant_id is None:
            # No specific tenant requested, use user's tenant
            return self.tenant_id

        if not self.can_access_tenant(target_tenant_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to tenant {target_tenant_id}"
            )

        return target_tenant_id

    @property
    def fiscal_regime(self) -> str:
        """Convenience accessor for normalized fiscal regime group."""
        return self.fiscal_regime_group

async def get_tenancy_context(current_user: UserInDB = Depends(get_current_active_user)) -> TenancyContext:
    """
    Dependency to get tenancy context for the current request.
    This should be used in all endpoints that need tenant isolation.
    """

    fiscal_regime_code: Optional[str] = None
    fiscal_regime_desc: Optional[str] = None

    if config.USE_UNIFIED_DB and get_unified_adapter is not None:
        try:
            profile = get_unified_adapter().get_company_fiscal_profile(current_user.tenant_id)
            if profile:
                fiscal_regime_code = profile.get("regimen_fiscal_code")
                fiscal_regime_desc = profile.get("regimen_fiscal_desc")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug(
                "Unable to fetch fiscal profile for tenant %s: %s",
                current_user.tenant_id,
                exc,
            )

    return TenancyContext(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        user=current_user,
        fiscal_regime_code=fiscal_regime_code,
        fiscal_regime_desc=fiscal_regime_desc,
    )

def get_optional_tenancy_context(request: Request) -> Optional[TenancyContext]:
    """
    Get tenancy context if available, without enforcing authentication.
    Useful for public endpoints that may optionally use tenancy.
    """
    # This would be implemented if we had session middleware
    # For now, return None to indicate no tenant context
    return None

class TenantIsolatedDBMixin:
    """
    Mixin for database adapters to enforce tenant isolation
    """

    def ensure_tenant_access(self, context: TenancyContext, tenant_id: Optional[int] = None) -> int:
        """Ensure the user can access the specified tenant"""
        return context.enforce_tenant_isolation(tenant_id)

    def get_user_tenant(self, context: TenancyContext) -> int:
        """Get the user's tenant ID"""
        return context.tenant_id

    def add_tenant_filter(self, query: str, context: TenancyContext, tenant_id: Optional[int] = None) -> tuple[str, int]:
        """Add tenant filter to a SQL query"""
        effective_tenant_id = self.ensure_tenant_access(context, tenant_id)

        if "WHERE" in query.upper():
            filtered_query = f"{query} AND tenant_id = ?"
        else:
            filtered_query = f"{query} WHERE tenant_id = ?"

        return filtered_query, effective_tenant_id

# Utility functions for backward compatibility
def extract_tenant_from_company_id(company_id: str) -> int:
    """
    Convert legacy company_id to tenant_id.
    For now, we map 'default' to tenant 1, others to their numeric value.
    """
    if company_id == "default" or not company_id:
        return 1

    try:
        return int(company_id)
    except ValueError:
        # If company_id is not numeric, hash it to a tenant ID
        # This is a temporary solution - in production, you'd have a proper mapping
        hash_val = abs(hash(company_id)) % 1000 + 1  # Map to range 1-1000
        logger.warning(f"Converting non-numeric company_id '{company_id}' to tenant_id {hash_val}")
        return hash_val

def normalize_tenant_id(tenant_id: Optional[int], company_id: Optional[str] = None) -> int:
    """
    Normalize tenant_id from various possible inputs.
    Priority: tenant_id > company_id > default (1)
    """
    if tenant_id is not None:
        return tenant_id

    if company_id is not None:
        return extract_tenant_from_company_id(company_id)

    return 1  # Default tenant

# Decorator for endpoints that need tenant isolation
def tenant_isolated(func):
    """
    Decorator to automatically inject tenant isolation into endpoint functions.
    The decorated function will receive a 'tenancy_context' parameter.
    """
    async def wrapper(*args, **kwargs):
        # Check if tenancy_context is already provided
        if 'tenancy_context' in kwargs:
            return await func(*args, **kwargs)

        # Try to get tenancy context from dependencies
        # This would require more complex dependency injection setup
        # For now, we'll rely on explicit dependency injection in endpoints
        raise NotImplementedError(
            "tenant_isolated decorator requires explicit dependency injection. "
            "Use 'tenancy_context: TenancyContext = Depends(get_tenancy_context)' in your endpoint."
        )

    return wrapper

if __name__ == "__main__":
    # Test utility functions
    print("🏢 Testing tenancy utilities:")

    # Test company_id conversion
    test_cases = [
        ("default", 1),
        ("1", 1),
        ("2", 2),
        ("company_abc", None)  # Will be hashed
    ]

    for company_id, expected in test_cases:
        result = extract_tenant_from_company_id(company_id)
        if expected is not None:
            assert result == expected, f"Expected {expected}, got {result}"
            print(f"✅ '{company_id}' -> {result}")
        else:
            print(f"✅ '{company_id}' -> {result} (hashed)")

    print("🎉 Tenancy utilities test completed!")
