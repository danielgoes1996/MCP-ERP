"""
Security Middleware for Enhanced Automation System

Implements:
- RBAC (Role-Based Access Control)
- Multi-tenant isolation
- Credential encryption
- Audit logging
- Rate limiting
- CFDI security
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from functools import wraps
from cryptography.fernet import Fernet
import jwt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# ===================================================================
# ENCRYPTION & CREDENTIAL MANAGEMENT
# ===================================================================

class CredentialManager:
    """Secure credential management for automation services."""

    def __init__(self, encryption_key: Optional[bytes] = None):
        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            # Generate new key (should be stored securely in production)
            self.cipher = Fernet(Fernet.generate_key())

    def encrypt_credential(self, credential: str) -> str:
        """Encrypt sensitive credential."""
        try:
            encrypted = self.cipher.encrypt(credential.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Error encrypting credential: {e}")
            raise

    def decrypt_credential(self, encrypted_credential: str) -> str:
        """Decrypt credential for use."""
        try:
            decrypted = self.cipher.decrypt(encrypted_credential.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Error decrypting credential: {e}")
            raise

    def store_merchant_credentials(
        self,
        merchant_id: int,
        credentials: Dict[str, str],
        company_id: str
    ):
        """Store encrypted merchant credentials."""
        try:
            from modules.invoicing_agent.models import get_merchant, update_merchant_metadata

            merchant = get_merchant(merchant_id)
            if not merchant:
                raise ValueError(f"Merchant {merchant_id} not found")

            # Encrypt each credential
            encrypted_creds = {}
            for key, value in credentials.items():
                if value:  # Only encrypt non-empty values
                    encrypted_creds[f"encrypted_{key}"] = self.encrypt_credential(value)

            # Update merchant metadata
            metadata = merchant.get("metadata", {})
            metadata["credentials"] = encrypted_creds
            metadata["credentials_updated"] = datetime.utcnow().isoformat()

            update_merchant_metadata(merchant_id, metadata)

            # Audit log
            self._audit_log("credential_stored", {
                "merchant_id": merchant_id,
                "company_id": company_id,
                "credential_keys": list(credentials.keys())
            })

        except Exception as e:
            logger.error(f"Error storing merchant credentials: {e}")
            raise

    def get_merchant_credentials(
        self,
        merchant_id: int,
        company_id: str
    ) -> Dict[str, str]:
        """Get decrypted merchant credentials."""
        try:
            from modules.invoicing_agent.models import get_merchant

            merchant = get_merchant(merchant_id)
            if not merchant:
                return {}

            credentials = merchant.get("metadata", {}).get("credentials", {})
            decrypted_creds = {}

            for key, encrypted_value in credentials.items():
                if key.startswith("encrypted_"):
                    original_key = key.replace("encrypted_", "")
                    try:
                        decrypted_creds[original_key] = self.decrypt_credential(encrypted_value)
                    except Exception as e:
                        logger.warning(f"Could not decrypt credential {original_key}: {e}")

            return decrypted_creds

        except Exception as e:
            logger.error(f"Error getting merchant credentials: {e}")
            return {}

    def _audit_log(self, action: str, details: Dict[str, Any]):
        """Log security-related actions."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details
        }
        logger.info(f"SECURITY_AUDIT: {json.dumps(log_entry)}")

# ===================================================================
# RBAC (Role-Based Access Control)
# ===================================================================

class Permission:
    """Permission constants."""
    READ_TICKETS = "read_tickets"
    WRITE_TICKETS = "write_tickets"
    READ_AUTOMATION = "read_automation"
    WRITE_AUTOMATION = "write_automation"
    READ_SCREENSHOTS = "read_screenshots"
    ADMIN_SYSTEM = "admin_system"
    MANAGE_MERCHANTS = "manage_merchants"
    VIEW_COSTS = "view_costs"
    BULK_OPERATIONS = "bulk_operations"

class Role:
    """Role definitions with permissions."""
    VIEWER = {
        "name": "viewer",
        "permissions": [Permission.READ_TICKETS, Permission.READ_AUTOMATION]
    }

    OPERATOR = {
        "name": "operator",
        "permissions": [
            Permission.READ_TICKETS, Permission.WRITE_TICKETS,
            Permission.READ_AUTOMATION, Permission.WRITE_AUTOMATION,
            Permission.READ_SCREENSHOTS
        ]
    }

    ADMIN = {
        "name": "admin",
        "permissions": [
            Permission.READ_TICKETS, Permission.WRITE_TICKETS,
            Permission.READ_AUTOMATION, Permission.WRITE_AUTOMATION,
            Permission.READ_SCREENSHOTS, Permission.ADMIN_SYSTEM,
            Permission.MANAGE_MERCHANTS, Permission.VIEW_COSTS,
            Permission.BULK_OPERATIONS
        ]
    }

class RBACManager:
    """Role-based access control manager."""

    def __init__(self):
        self.roles = {
            "viewer": Role.VIEWER,
            "operator": Role.OPERATOR,
            "admin": Role.ADMIN
        }

    def check_permission(
        self,
        user_role: str,
        required_permission: str,
        company_id: str,
        user_company_id: str
    ) -> bool:
        """Check if user has required permission."""
        # Multi-tenant check
        if company_id != user_company_id:
            logger.warning(f"Cross-tenant access attempt: {user_company_id} -> {company_id}")
            return False

        # Role permission check
        role = self.roles.get(user_role)
        if not role:
            return False

        return required_permission in role["permissions"]

    def require_permission(self, permission: str):
        """Decorator to require specific permission."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user context from request
                # This would integrate with your auth system
                user_context = self._get_user_context()

                if not self.check_permission(
                    user_context["role"],
                    permission,
                    kwargs.get("company_id", "default"),
                    user_context["company_id"]
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission denied: {permission} required"
                    )

                return await func(*args, **kwargs)
            return wrapper
        return decorator

    def _get_user_context(self) -> Dict[str, str]:
        """Get user context from request (placeholder)."""
        # TODO: Integrate with your authentication system
        return {
            "user_id": "default_user",
            "role": "admin",  # Default for now
            "company_id": "default"
        }

# ===================================================================
# CFDI SECURITY
# ===================================================================

class CFDISecurityManager:
    """Security manager for CFDI files and sensitive data."""

    def __init__(self, credential_manager: CredentialManager):
        self.credential_manager = credential_manager

    def secure_cfdi_storage(
        self,
        cfdi_content: bytes,
        ticket_id: int,
        company_id: str
    ) -> str:
        """Securely store CFDI with encryption."""
        try:
            import os
            import uuid

            # Generate secure filename
            secure_filename = f"{company_id}_{ticket_id}_{uuid.uuid4().hex}.xml.enc"
            storage_path = f"secure_storage/cfdis/{company_id}/{secure_filename}"

            # Ensure directory exists
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)

            # Encrypt CFDI content
            encrypted_content = self.credential_manager.cipher.encrypt(cfdi_content)

            # Write encrypted file
            with open(storage_path, 'wb') as f:
                f.write(encrypted_content)

            # Audit log
            self.credential_manager._audit_log("cfdi_stored", {
                "ticket_id": ticket_id,
                "company_id": company_id,
                "file_size": len(cfdi_content),
                "storage_path": storage_path
            })

            return storage_path

        except Exception as e:
            logger.error(f"Error securing CFDI storage: {e}")
            raise

    def retrieve_cfdi(
        self,
        storage_path: str,
        company_id: str,
        user_company_id: str
    ) -> bytes:
        """Retrieve and decrypt CFDI."""
        try:
            # Multi-tenant check
            if company_id != user_company_id:
                raise HTTPException(status_code=403, detail="Cross-tenant access denied")

            # Verify path belongs to company
            if f"/{company_id}/" not in storage_path:
                raise HTTPException(status_code=403, detail="Invalid file access")

            # Read encrypted file
            with open(storage_path, 'rb') as f:
                encrypted_content = f.read()

            # Decrypt content
            decrypted_content = self.credential_manager.cipher.decrypt(encrypted_content)

            # Audit log
            self.credential_manager._audit_log("cfdi_retrieved", {
                "storage_path": storage_path,
                "company_id": company_id,
                "user_company_id": user_company_id
            })

            return decrypted_content

        except Exception as e:
            logger.error(f"Error retrieving CFDI: {e}")
            raise

# ===================================================================
# RATE LIMITING
# ===================================================================

class RateLimiter:
    """Rate limiter for API endpoints."""

    def __init__(self):
        self.requests = {}  # {company_id: {endpoint: [(timestamp, count)]}}

    def check_rate_limit(
        self,
        company_id: str,
        endpoint: str,
        limit: int = 100,
        window_seconds: int = 3600
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limit."""
        try:
            now = time.time()
            cutoff = now - window_seconds

            # Initialize tracking
            if company_id not in self.requests:
                self.requests[company_id] = {}
            if endpoint not in self.requests[company_id]:
                self.requests[company_id][endpoint] = []

            # Clean old requests
            self.requests[company_id][endpoint] = [
                (ts, count) for ts, count in self.requests[company_id][endpoint]
                if ts > cutoff
            ]

            # Count current requests
            current_count = sum(count for _, count in self.requests[company_id][endpoint])

            # Check limit
            if current_count >= limit:
                return False, {
                    "limit": limit,
                    "current": current_count,
                    "window_seconds": window_seconds,
                    "reset_time": int(now + window_seconds)
                }

            # Add current request
            self.requests[company_id][endpoint].append((now, 1))

            return True, {
                "limit": limit,
                "current": current_count + 1,
                "remaining": limit - current_count - 1
            }

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True, {}  # Allow on error

    def rate_limit(self, endpoint: str, limit: int = 100, window_seconds: int = 3600):
        """Decorator for rate limiting."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                company_id = kwargs.get("company_id", "default")

                allowed, info = self.check_rate_limit(company_id, endpoint, limit, window_seconds)

                if not allowed:
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded",
                        headers={
                            "X-RateLimit-Limit": str(limit),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(info["reset_time"])
                        }
                    )

                return await func(*args, **kwargs)
            return wrapper
        return decorator

# ===================================================================
# GLOBAL SECURITY MANAGER
# ===================================================================

class SecurityManager:
    """Global security manager."""

    def __init__(self, encryption_key: Optional[bytes] = None):
        self.credential_manager = CredentialManager(encryption_key)
        self.rbac_manager = RBACManager()
        self.cfdi_manager = CFDISecurityManager(self.credential_manager)
        self.rate_limiter = RateLimiter()

    def get_security_middleware(self):
        """Get FastAPI middleware for security."""
        # TODO: Implement middleware that integrates with your auth system
        pass

# Global instance
security_manager = SecurityManager()

# Convenience functions
def get_credential_manager() -> CredentialManager:
    return security_manager.credential_manager

def get_rbac_manager() -> RBACManager:
    return security_manager.rbac_manager

def get_cfdi_manager() -> CFDISecurityManager:
    return security_manager.cfdi_manager

def get_rate_limiter() -> RateLimiter:
    return security_manager.rate_limiter

# Security decorators
def require_permission(permission: str):
    """Require specific permission."""
    return security_manager.rbac_manager.require_permission(permission)

def rate_limit(endpoint: str, limit: int = 100, window_seconds: int = 3600):
    """Apply rate limiting."""
    return security_manager.rate_limiter.rate_limit(endpoint, limit, window_seconds)