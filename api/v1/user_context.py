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
    ],
    "company_admin": [
        "expenses:create",
        "expenses:view_team",
        "expenses:approve",
        "reports:view",
    ],
    "viewer": [
        "expenses:view_all",
        "reports:view",
    ],
    "user": [
        "expenses:create",
        "expenses:view_self",
    ],
}


def _derive_permissions(role: str) -> PermissionContext:
    normalized = (role or "user").lower().strip()
    capabilities = ROLE_PERMISSION_MATRIX.get(normalized)
    if capabilities is None:
        capabilities = ROLE_PERMISSION_MATRIX["user"]
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
