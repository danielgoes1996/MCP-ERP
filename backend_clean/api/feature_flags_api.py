"""
Feature Flags Management API
Provides endpoints to control feature flags for gradual rollout.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from core.feature_flags import (
    feature_flags,
    FeatureFlag,
    is_automation_enabled,
    enable_automation_for_company,
    disable_automation_globally
)

router = APIRouter(prefix="/api/v2/feature-flags", tags=["feature-flags"])

class FeatureFlagUpdate(BaseModel):
    """Request model for updating feature flags."""

    flag: str = Field(..., description="Feature flag key")
    value: Any = Field(..., description="Flag value (bool, int, str, or dict for rollout)")
    scope: str = Field("global", description="Scope: global, company, user")
    scope_id: Optional[str] = Field(None, description="Scope ID (company_id or user_id)")
    reason: Optional[str] = Field(None, description="Reason for the change")

class RolloutConfig(BaseModel):
    """Request model for rollout configuration."""

    percentage: int = Field(..., ge=0, le=100, description="Rollout percentage (0-100)")
    company_whitelist: Optional[list] = Field(None, description="Companies to include")
    company_blacklist: Optional[list] = Field(None, description="Companies to exclude")
    reason: Optional[str] = Field("API update", description="Reason for the change")

class FeatureFlagStatus(BaseModel):
    """Response model for feature flag status."""

    flag: str
    enabled: bool
    scope: str
    value_type: str
    rollout_info: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None

@router.get("/status")
async def get_all_feature_flags(
    company_id: str = Query("default", description="Company ID to check flags for")
):
    """
    Get status of all feature flags for a company.

    Returns the current status of all defined feature flags.
    """

    try:
        flags_status = feature_flags.get_all_flags(company_id)

        # Add detailed info for each flag
        detailed_status = {}

        for flag_name, status in flags_status.items():
            flag_enum = FeatureFlag[flag_name]
            rollout_info = feature_flags.get_rollout_info(flag_enum)

            detailed_status[flag_name] = {
                "enabled": status["enabled"],
                "key": status["key"],
                "description": status["description"],
                "rollout_info": rollout_info
            }

        return {
            "company_id": company_id,
            "flags": detailed_status,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get feature flags: {str(e)}")

@router.get("/check/{flag_key}")
async def check_feature_flag(
    flag_key: str,
    company_id: str = Query("default", description="Company ID"),
    user_id: Optional[int] = Query(None, description="User ID")
):
    """
    Check if a specific feature flag is enabled.

    Returns whether the flag is enabled for the given context.
    """

    try:
        # Find the flag enum
        flag_enum = None
        for flag in FeatureFlag:
            if flag.value == flag_key or flag.name == flag_key:
                flag_enum = flag
                break

        if not flag_enum:
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_key}' not found")

        enabled = feature_flags.is_enabled(flag_enum, company_id, user_id)
        rollout_info = feature_flags.get_rollout_info(flag_enum)

        return {
            "flag": flag_key,
            "enabled": enabled,
            "company_id": company_id,
            "user_id": user_id,
            "rollout_info": rollout_info,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check feature flag: {str(e)}")

@router.post("/update")
async def update_feature_flag(
    update_request: FeatureFlagUpdate,
    updated_by: str = Query("api_user", description="Who is making this change")
):
    """
    Update a feature flag value.

    Allows setting feature flags at different scopes with audit trail.
    """

    try:
        # Find the flag enum
        flag_enum = None
        for flag in FeatureFlag:
            if flag.value == update_request.flag or flag.name == update_request.flag:
                flag_enum = flag
                break

        if not flag_enum:
            raise HTTPException(status_code=404, detail=f"Feature flag '{update_request.flag}' not found")

        # Validate scope
        valid_scopes = ["global", "company", "user"]
        if update_request.scope not in valid_scopes:
            raise HTTPException(status_code=400, detail=f"Invalid scope. Must be one of: {valid_scopes}")

        # Validate scope_id requirements
        if update_request.scope in ["company", "user"] and not update_request.scope_id:
            raise HTTPException(status_code=400, detail=f"scope_id required for scope '{update_request.scope}'")

        # Update the flag
        success = feature_flags.set_flag(
            flag_enum,
            update_request.value,
            scope=update_request.scope,
            scope_id=update_request.scope_id,
            reason=update_request.reason,
            updated_by=updated_by
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update feature flag")

        return {
            "success": True,
            "flag": update_request.flag,
            "value": update_request.value,
            "scope": update_request.scope,
            "scope_id": update_request.scope_id,
            "updated_by": updated_by,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update feature flag: {str(e)}")

@router.post("/automation/enable-company")
async def enable_automation_for_company_endpoint(
    company_id: str = Body(..., description="Company ID to enable automation for"),
    reason: str = Body("Manual API enable", description="Reason for enabling")
):
    """
    Enable automation for a specific company.

    Convenience endpoint for enabling automation engine v2 for a company.
    """

    try:
        success = enable_automation_for_company(company_id, reason)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to enable automation")

        return {
            "success": True,
            "company_id": company_id,
            "automation_enabled": True,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable automation: {str(e)}")

@router.post("/automation/disable-global")
async def disable_automation_globally_endpoint(
    reason: str = Body("Manual API disable", description="Reason for disabling"),
    confirm: bool = Body(..., description="Confirmation required for global disable")
):
    """
    Disable automation globally (emergency stop).

    This will disable automation for all companies. Use with caution.
    """

    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required for global disable")

    try:
        success = disable_automation_globally(reason)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to disable automation")

        return {
            "success": True,
            "automation_enabled": False,
            "scope": "global",
            "reason": reason,
            "warning": "Automation disabled globally for all companies",
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disable automation: {str(e)}")

@router.post("/automation/set-rollout")
async def set_automation_rollout_endpoint(
    rollout_config: RolloutConfig
):
    """
    Configure automation rollout percentage.

    Sets up gradual rollout of automation engine v2.
    """

    try:
        # Build rollout configuration
        config = {
            "enabled": rollout_config.percentage > 0,
            "rollout_percentage": rollout_config.percentage,
            "rollout_seed": "automation_v2_rollout"
        }

        if rollout_config.company_whitelist:
            config["company_whitelist"] = rollout_config.company_whitelist

        if rollout_config.company_blacklist:
            config["company_blacklist"] = rollout_config.company_blacklist

        success = feature_flags.set_flag(
            FeatureFlag.AUTOMATION_ENGINE_V2,
            config,
            scope="global",
            reason=rollout_config.reason
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to set rollout configuration")

        return {
            "success": True,
            "rollout_percentage": rollout_config.percentage,
            "config": config,
            "reason": rollout_config.reason,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set rollout: {str(e)}")

@router.get("/automation/check")
async def check_automation_status(
    company_id: str = Query("default", description="Company ID"),
    user_id: Optional[int] = Query(None, description="User ID")
):
    """
    Check automation engine status for a company/user.

    Returns detailed information about automation enablement.
    """

    try:
        enabled = is_automation_enabled(company_id, user_id)
        rollout_info = feature_flags.get_rollout_info(FeatureFlag.AUTOMATION_ENGINE_V2)

        return {
            "company_id": company_id,
            "user_id": user_id,
            "automation_enabled": enabled,
            "rollout_info": rollout_info,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check automation status: {str(e)}")

@router.get("/audit/{flag_key}")
async def get_feature_flag_audit(
    flag_key: str,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of audit entries")
):
    """
    Get audit trail for a feature flag.

    Returns the history of changes for a specific feature flag.
    """

    try:
        from core.internal_db import _get_db_path
        import sqlite3

        with sqlite3.connect(_get_db_path()) as conn:
            conn.row_factory = sqlite3.Row

            # Get audit trail
            rows = conn.execute("""
                SELECT
                    key, value, value_type, scope, scope_id,
                    previous_value, updated_at, updated_by, change_reason
                FROM automation_config
                WHERE key = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (flag_key, limit)).fetchall()

            audit_entries = []
            for row in rows:
                entry = dict(row)
                audit_entries.append(entry)

            return {
                "flag": flag_key,
                "audit_entries": audit_entries,
                "total_entries": len(audit_entries),
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit trail: {str(e)}")