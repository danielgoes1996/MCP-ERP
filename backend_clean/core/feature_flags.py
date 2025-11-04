"""
Feature Flag System for MCP Automation Engine v2
Provides dynamic feature control with rollout capabilities.
"""

import sqlite3
import json
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from core.internal_db import _get_db_path, _DB_LOCK

class FeatureFlag(Enum):
    """Defined feature flags for the automation engine."""

    # Core automation features
    AUTOMATION_ENGINE_V2 = "automation_engine_enabled"
    SELENIUM_GRID = "selenium_grid_enabled"
    CAPTCHA_SOLVER = "captcha_service_enabled"
    REAL_TIME_LOGS = "real_time_logs_enabled"

    # Advanced features
    OCR_BACKEND_ADVANCED = "ocr_backend_advanced"
    AUTO_RETRY_FAILED_JOBS = "auto_retry_failed_jobs"
    SCREENSHOT_ANALYSIS = "screenshot_analysis_enabled"
    WEBHOOK_NOTIFICATIONS = "webhook_notifications_enabled"

class FeatureFlagManager:
    """Manages feature flags with rollout control."""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache TTL

    def is_enabled(
        self,
        flag: FeatureFlag,
        company_id: str = "default",
        user_id: Optional[int] = None
    ) -> bool:
        """
        Check if a feature flag is enabled for the given context.

        Args:
            flag: The feature flag to check
            company_id: Company ID for tenant-specific flags
            user_id: User ID for user-specific flags

        Returns:
            bool: True if feature is enabled, False otherwise
        """

        cache_key = f"{flag.value}:{company_id}:{user_id or ''}"

        # Check cache first
        if cache_key in self.cache:
            cached_result, cached_time = self.cache[cache_key]
            if (datetime.now().timestamp() - cached_time) < self.cache_ttl:
                return cached_result

        try:
            result = self._check_flag(flag, company_id, user_id)

            # Cache the result
            self.cache[cache_key] = (result, datetime.now().timestamp())

            return result

        except Exception:
            # Fail safe - return False for unknown flags
            return False

    def _check_flag(
        self,
        flag: FeatureFlag,
        company_id: str,
        user_id: Optional[int]
    ) -> bool:
        """Internal method to check flag status."""

        with sqlite3.connect(_get_db_path()) as conn:
            conn.row_factory = sqlite3.Row

            # 1. Check for company-specific override
            company_override = conn.execute("""
                SELECT value, value_type FROM automation_config
                WHERE key = ? AND scope = 'company' AND scope_id = ? AND is_active = 1
            """, (flag.value, company_id)).fetchone()

            if company_override:
                return self._parse_boolean_value(
                    company_override['value'],
                    company_override['value_type']
                )

            # 2. Check for user-specific override
            if user_id:
                user_override = conn.execute("""
                    SELECT value, value_type FROM automation_config
                    WHERE key = ? AND scope = 'user' AND scope_id = ? AND is_active = 1
                """, (flag.value, str(user_id))).fetchone()

                if user_override:
                    return self._parse_boolean_value(
                        user_override['value'],
                        user_override['value_type']
                    )

            # 3. Check global setting
            global_setting = conn.execute("""
                SELECT value, value_type FROM automation_config
                WHERE key = ? AND scope = 'global' AND is_active = 1
            """, (flag.value,)).fetchone()

            if not global_setting:
                return False

            # Check if it's a simple boolean
            if global_setting['value_type'] == 'boolean':
                return self._parse_boolean_value(
                    global_setting['value'],
                    global_setting['value_type']
                )

            # Check if it's a rollout configuration
            if global_setting['value_type'] == 'json':
                try:
                    rollout_config = json.loads(global_setting['value'])
                    return self._check_rollout(rollout_config, company_id, user_id)
                except (json.JSONDecodeError, KeyError):
                    return False

            return False

    def _parse_boolean_value(self, value: str, value_type: str) -> bool:
        """Parse a boolean value from string."""
        if value_type == 'boolean':
            return value.lower() in ('true', '1', 'yes', 'on')
        return False

    def _check_rollout(
        self,
        rollout_config: Dict[str, Any],
        company_id: str,
        user_id: Optional[int]
    ) -> bool:
        """Check rollout configuration for gradual feature deployment."""

        # Global killswitch
        if not rollout_config.get("enabled", False):
            return False

        # Company whitelist
        company_whitelist = rollout_config.get("company_whitelist", [])
        if company_whitelist and company_id in company_whitelist:
            return True

        # Company blacklist
        company_blacklist = rollout_config.get("company_blacklist", [])
        if company_blacklist and company_id in company_blacklist:
            return False

        # Percentage rollout
        rollout_percentage = rollout_config.get("rollout_percentage", 0)
        if rollout_percentage == 0:
            return False
        elif rollout_percentage >= 100:
            return True

        # Hash-based consistent rollout
        hash_input = f"{rollout_config.get('rollout_seed', 'default')}:{company_id}:{user_id or ''}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
        hash_percentage = (hash_value % 100) + 1

        return hash_percentage <= rollout_percentage

    def set_flag(
        self,
        flag: FeatureFlag,
        value: Any,
        scope: str = "global",
        scope_id: Optional[str] = None,
        reason: Optional[str] = None,
        updated_by: str = "system"
    ) -> bool:
        """
        Set a feature flag value.

        Args:
            flag: The feature flag to set
            value: The value to set (bool, str, dict for rollout config)
            scope: Scope of the setting (global, company, user)
            scope_id: ID for the scope (company_id, user_id)
            reason: Reason for the change
            updated_by: Who made the change

        Returns:
            bool: True if successfully set, False otherwise
        """

        try:
            with _DB_LOCK:
                with sqlite3.connect(_get_db_path()) as conn:
                    now = datetime.now().isoformat()

                    # Determine value type and serialize value
                    if isinstance(value, bool):
                        value_type = "boolean"
                        value_str = "true" if value else "false"
                    elif isinstance(value, dict):
                        value_type = "json"
                        value_str = json.dumps(value)
                    elif isinstance(value, int):
                        value_type = "integer"
                        value_str = str(value)
                    else:
                        value_type = "string"
                        value_str = str(value)

                    # Get current value for audit trail
                    current = conn.execute("""
                        SELECT value FROM automation_config
                        WHERE key = ? AND scope = ? AND scope_id IS ?
                    """, (flag.value, scope, scope_id)).fetchone()

                    previous_value = current['value'] if current else None

                    # Insert or update
                    conn.execute("""
                        INSERT OR REPLACE INTO automation_config (
                            key, value, value_type, scope, scope_id,
                            description, category, is_active, is_readonly,
                            previous_value, updated_at, updated_by, change_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        flag.value, value_str, value_type, scope, scope_id,
                        f"Feature flag: {flag.name}", "feature_flags", True, False,
                        previous_value, now, updated_by, reason
                    ))

                    conn.commit()

                    # Clear cache for this flag
                    self._clear_flag_cache(flag)

                    return True

        except Exception:
            return False

    def _clear_flag_cache(self, flag: FeatureFlag):
        """Clear cache entries for a specific flag."""
        keys_to_remove = [key for key in self.cache.keys() if key.startswith(f"{flag.value}:")]
        for key in keys_to_remove:
            del self.cache[key]

    def get_all_flags(self, company_id: str = "default") -> Dict[str, Any]:
        """Get status of all feature flags for a company."""

        flags_status = {}

        for flag in FeatureFlag:
            flags_status[flag.name] = {
                "enabled": self.is_enabled(flag, company_id),
                "key": flag.value,
                "description": flag.name.replace("_", " ").title()
            }

        return flags_status

    def get_rollout_info(self, flag: FeatureFlag) -> Dict[str, Any]:
        """Get detailed rollout information for a flag."""

        try:
            with sqlite3.connect(_get_db_path()) as conn:
                conn.row_factory = sqlite3.Row

                result = conn.execute("""
                    SELECT value, value_type, updated_at, updated_by FROM automation_config
                    WHERE key = ? AND scope = 'global' AND is_active = 1
                """, (flag.value,)).fetchone()

                if not result:
                    return {"status": "not_configured"}

                info = {
                    "status": "configured",
                    "value_type": result['value_type'],
                    "updated_at": result['updated_at'],
                    "updated_by": result['updated_by']
                }

                if result['value_type'] == 'boolean':
                    info["enabled"] = self._parse_boolean_value(
                        result['value'],
                        result['value_type']
                    )
                elif result['value_type'] == 'json':
                    try:
                        rollout_config = json.loads(result['value'])
                        info["rollout_config"] = rollout_config
                        info["rollout_percentage"] = rollout_config.get("rollout_percentage", 0)
                        info["enabled_globally"] = rollout_config.get("enabled", False)
                    except json.JSONDecodeError:
                        info["status"] = "invalid_config"

                return info

        except Exception:
            return {"status": "error"}

# Global instance
feature_flags = FeatureFlagManager()

# Convenience functions
def is_automation_enabled(company_id: str = "default", user_id: Optional[int] = None) -> bool:
    """Check if automation engine v2 is enabled."""
    return feature_flags.is_enabled(FeatureFlag.AUTOMATION_ENGINE_V2, company_id, user_id)

def enable_automation_for_company(company_id: str, reason: str = "Manual override") -> bool:
    """Enable automation for a specific company."""
    return feature_flags.set_flag(
        FeatureFlag.AUTOMATION_ENGINE_V2,
        True,
        scope="company",
        scope_id=company_id,
        reason=reason
    )

def disable_automation_globally(reason: str = "Emergency stop") -> bool:
    """Disable automation globally (emergency stop)."""
    return feature_flags.set_flag(
        FeatureFlag.AUTOMATION_ENGINE_V2,
        False,
        scope="global",
        reason=reason
    )

def set_automation_rollout(percentage: int, reason: str = "Gradual rollout") -> bool:
    """Set automation rollout percentage."""
    rollout_config = {
        "enabled": True,
        "rollout_percentage": percentage,
        "rollout_seed": "automation_v2_rollout"
    }

    return feature_flags.set_flag(
        FeatureFlag.AUTOMATION_ENGINE_V2,
        rollout_config,
        scope="global",
        reason=reason
    )