"""User context endpoints for onboarding status and contextual memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.auth.jwt import (
    User as JWTUser,
    get_current_user,
    get_db_connection,
)
from core.ai.ai_context_memory_service import (
    get_company_id_for_tenant,
    get_latest_context_for_company,
)
from core.ai import get_ai_provider_stack
from core.config.company_settings import get_company_settings_by_tenant, CompanySettings


auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth Context"])
users_router = APIRouter(prefix="/api/v1/users", tags=["User Context"])


class AuthStatusResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    tenant_id: int
    onboarding_completed: bool
    onboarding_completed_at: Optional[str] = None
    last_context_update: Optional[str] = None
    topics: List[str] = []
    summary: Optional[str] = None


class CompanySettingsResponse(BaseModel):
    company_name: Optional[str] = None
    regimen_fiscal_code: Optional[str] = None
    regimen_fiscal_desc: Optional[str] = None
    cfdi_required: bool
    iva_policy: str
    payment_policy: str


class AIStackResponse(BaseModel):
    categorization_model: Dict[str, Any]
    invoice_parser: Dict[str, Any]
    bank_matcher: Dict[str, Any]
    company_id: Optional[int] = None


class AIContextSummary(BaseModel):
    summary: Optional[str] = None
    topics: List[str] = []
    last_context_update: Optional[str] = None


class PermissionContext(BaseModel):
    role: str
    capabilities: List[str]


class UserProfileContext(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    tenant_id: int
    company_id: Optional[int]
    company_name: Optional[str]
    onboarding_completed: bool
    onboarding_completed_at: Optional[str]


class UserFullContextResponse(BaseModel):
    user: UserProfileContext
    permissions: PermissionContext
    company_settings: Optional[CompanySettingsResponse]
    ai_stack: AIStackResponse
    ai_context: AIContextSummary


ROLE_PERMISSION_MATRIX: Dict[str, List[str]] = {
    """
    DEPRECATED: Legacy permission matrix for backward compatibility.
    New code should use _derive_permissions_from_roles() which queries
    the database for dynamic JSONB permissions.
    """
    "admin": [
        "expenses:create",
        "expenses:view_all",
        "expenses:approve",
        "expenses:categorize",
        "reports:view",
        "settings:manage",
    ],
    "contador": [
        "expenses:view_all",
        "expenses:categorize",
        "expenses:tax",
        "expenses:reconcile",
        "reports:view",
        "invoices:classify",
        "invoices:approve",
        "invoices:reject",
        "polizas:view",
    ],
    "accountant": [
        "expenses:view_all",
        "expenses:approve",
        "invoices:view",
        "invoices:update",
        "bank_reconciliation:view",
    ],
    "manager": [
        "expenses:create",
        "expenses:view_all",
        "expenses:approve",
        "expenses:reject",
        "reports:view",
        "employee_advances:view",
        "employee_advances:approve",
    ],
    "supervisor": [
        "expenses:view_department",
        "expenses:approve",
        "invoices:view_department",
    ],
    "company_admin": [
        "expenses:create",
        "expenses:view_team",
        "expenses:approve",
        "reports:view",
    ],
    "viewer": [
        "expenses:view_own",
        "invoices:view_own",
        "reports:view_own",
    ],
    "empleado": [
        "expenses:create",
        "expenses:view_own",
        "expenses:update_own",
        "invoices:create",
        "invoices:view_own",
    ],
    "user": [
        "expenses:create",
        "expenses:view_self",
    ],
}


def _derive_permissions_from_roles(user_roles: List[str], user_id: int) -> PermissionContext:
    """
    Derive permissions dynamically from user's assigned roles.

    This function queries the roles table for JSONB permissions and converts
    them into capability strings (e.g., "expenses:create", "invoices:approve").

    Args:
        user_roles: List of role names assigned to the user
        user_id: User ID (for database queries)

    Returns:
        PermissionContext with combined capabilities from all roles
    """
    if not user_roles:
        # Fallback to empleado permissions if user has no roles
        return PermissionContext(role="empleado", capabilities=ROLE_PERMISSION_MATRIX.get("empleado", []))

    all_capabilities: set[str] = set()
    highest_role = user_roles[0]  # Already sorted by level DESC

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query permissions from roles table for all user's roles
        placeholders = ",".join("?" * len(user_roles))
        cursor.execute(
            f"""
            SELECT r.name, r.permissions
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = ?
              AND r.is_active = TRUE
              AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
            ORDER BY r.level DESC
            """,
            (user_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            role_name = row[0]
            permissions_json = row[1] if row[1] else {}

            # Convert JSONB permissions to capability strings
            resources = permissions_json.get("resources", [])
            actions = permissions_json.get("actions", [])

            # Handle wildcard permissions (admin)
            if "*" in resources and "*" in actions:
                all_capabilities.update(ROLE_PERMISSION_MATRIX.get("admin", []))
                continue

            # Generate capability strings from resource:action combinations
            for resource in resources:
                if resource == "*":
                    # Add all capabilities for all resources
                    for action in actions:
                        if action != "*":
                            all_capabilities.add(f"*:{action}")
                else:
                    for action in actions:
                        if action == "*":
                            # Add all actions for this resource
                            all_capabilities.add(f"{resource}:*")
                        else:
                            all_capabilities.add(f"{resource}:{action}")

        # If no dynamic permissions found, fall back to hardcoded matrix
        if not all_capabilities:
            for role_name in user_roles:
                role_caps = ROLE_PERMISSION_MATRIX.get(role_name, [])
                all_capabilities.update(role_caps)

    except Exception as e:
        # Fallback to hardcoded matrix on error
        for role_name in user_roles:
            role_caps = ROLE_PERMISSION_MATRIX.get(role_name, [])
            all_capabilities.update(role_caps)

    return PermissionContext(role=highest_role, capabilities=sorted(list(all_capabilities)))


def _derive_permissions(role: str) -> PermissionContext:
    """
    DEPRECATED: Legacy single-role permission derivation.

    Use _derive_permissions_from_roles() for multi-role support.
    Maintained for backward compatibility only.
    """
    normalized = (role or "empleado").lower().strip()
    capabilities = ROLE_PERMISSION_MATRIX.get(normalized)
    if capabilities is None:
        capabilities = ROLE_PERMISSION_MATRIX.get("empleado", [])
    return PermissionContext(role=normalized, capabilities=capabilities)


def _build_company_settings_response(settings: Optional[CompanySettings]) -> Optional[CompanySettingsResponse]:
    if not settings:
        return None
    return CompanySettingsResponse(
        company_name=settings.company_name,
        regimen_fiscal_code=settings.regimen_fiscal_code,
        regimen_fiscal_desc=settings.regimen_fiscal_desc,
        cfdi_required=settings.cfdi_required,
        iva_policy=settings.iva_policy,
        payment_policy=settings.payment_policy,
    )


def _build_ai_context_summary(tenant_id: int) -> AIContextSummary:
    company_id = get_company_id_for_tenant(tenant_id)
    context = None
    if company_id:
        context = get_latest_context_for_company(company_id)

    topics: List[str] = []
    summary: Optional[str] = None
    last_context_update: Optional[str] = None
    if context:
        summary = context.get("summary")
        last_context_update = context.get("created_at")
        raw_topics = context.get("topics")
        if isinstance(raw_topics, list):
            topics = [str(topic) for topic in raw_topics]

    return AIContextSummary(summary=summary, topics=topics, last_context_update=last_context_update)


def _build_ai_stack(company_id: Optional[int]) -> AIStackResponse:
    stack = get_ai_provider_stack(company_id)
    return AIStackResponse(
        categorization_model=stack.get("categorization_model", {}),
        invoice_parser=stack.get("invoice_parser", {}),
        bank_matcher=stack.get("bank_matcher", {}),
        company_id=stack.get("company_id"),
    )

@auth_router.get("/me", response_model=AuthStatusResponse)
def get_auth_status(current_user: JWTUser = Depends(get_current_user)) -> AuthStatusResponse:
    """Return authenticated user information with onboarding and context metadata."""
    context_summary = _build_ai_context_summary(current_user.tenant_id)

    return AuthStatusResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        onboarding_completed=getattr(current_user, "onboarding_completed", False),
        onboarding_completed_at=getattr(current_user, "onboarding_completed_at", None),
        last_context_update=context_summary.last_context_update,
        topics=context_summary.topics,
        summary=context_summary.summary,
    )


class MarkOnboardingResponse(BaseModel):
    onboarding_completed: bool
    onboarding_completed_at: Optional[str]


@users_router.post("/mark_onboarding", response_model=MarkOnboardingResponse)
def mark_onboarding_completed(current_user: JWTUser = Depends(get_current_user)) -> MarkOnboardingResponse:
    """Mark the current user as having completed the onboarding flow."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET onboarding_completed = 1,
                onboarding_completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (current_user.id,),
        )
        conn.commit()

        cursor.execute(
            """
            SELECT onboarding_completed, onboarding_completed_at
            FROM users
            WHERE id = ?
            """,
            (current_user.id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        completed = bool(row[0])
        completed_at = row[1]
        return MarkOnboardingResponse(
            onboarding_completed=completed,
            onboarding_completed_at=completed_at,
        )
    finally:
        conn.close()


class ContextStatusResponse(BaseModel):
    onboarding_completed: bool
    last_context_update: Optional[str] = None
    topics: List[str] = []
    summary: Optional[str] = None


@users_router.get("/context-status", response_model=ContextStatusResponse)
def get_context_status(current_user: JWTUser = Depends(get_current_user)) -> ContextStatusResponse:
    """Return onboarding flag and latest context summary for the current user."""
    summary = _build_ai_context_summary(current_user.tenant_id)

    return ContextStatusResponse(
        onboarding_completed=getattr(current_user, "onboarding_completed", False),
        last_context_update=summary.last_context_update,
        topics=summary.topics,
        summary=summary.summary,
    )


@auth_router.get("/context/full", response_model=UserFullContextResponse)
def get_full_user_context(current_user: JWTUser = Depends(get_current_user)) -> UserFullContextResponse:
    company_settings = get_company_settings_by_tenant(current_user.tenant_id)
    company_settings_response = _build_company_settings_response(company_settings)

    ai_stack = _build_ai_stack(company_settings.company_id if company_settings else None)
    ai_context = _build_ai_context_summary(current_user.tenant_id)
    permissions = _derive_permissions(current_user.role)

    user_profile = UserProfileContext(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        company_id=getattr(current_user, "company_id", None),
        company_name=company_settings.company_name if company_settings else None,
        onboarding_completed=getattr(current_user, "onboarding_completed", False),
        onboarding_completed_at=getattr(current_user, "onboarding_completed_at", None),
    )

    return UserFullContextResponse(
        user=user_profile,
        permissions=permissions,
        company_settings=company_settings_response,
        ai_stack=ai_stack,
        ai_context=ai_context,
    )
