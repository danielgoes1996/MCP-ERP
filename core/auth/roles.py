"""
Role definitions and role-based access control utilities

This module provides the single source of truth for role definitions,
role hierarchy, and permission mappings.

All role-related logic should reference this module to ensure consistency.
"""

from enum import Enum
from typing import Dict, List, Set, Optional


class SystemRole(str, Enum):
    """
    System-defined roles (cannot be deleted)

    These roles are seeded in the database during migration 041
    and provide the foundation for role-based access control.
    """
    ADMIN = "admin"              # Level 100 - Full system access
    CONTADOR = "contador"        # Level 80 - Tax/accounting professional
    ACCOUNTANT = "accountant"    # Level 80 - General accountant
    MANAGER = "manager"          # Level 60 - Department manager
    SUPERVISOR = "supervisor"    # Level 50 - Team supervisor
    EMPLEADO = "empleado"        # Level 0 - Standard employee
    VIEWER = "viewer"            # Level 0 - Read-only access


class PermissionScope(str, Enum):
    """Permission scopes for role-based access control"""
    OWN = "own"              # User can only access their own resources
    DEPARTMENT = "department"  # User can access their department's resources
    TENANT = "tenant"        # User can access all resources in their tenant
    ALL = "all"              # User can access everything (admin only)


class ResourceType(str, Enum):
    """Resource types that can be protected by permissions"""
    ALL = "*"                      # All resources
    EXPENSES = "expenses"
    INVOICES = "invoices"
    CLASSIFICATIONS = "classifications"
    POLIZAS = "polizas"
    REPORTS = "reports"
    USERS = "users"
    DEPARTMENTS = "departments"
    ROLES = "roles"
    BANK_RECONCILIATION = "bank_reconciliation"
    EMPLOYEE_ADVANCES = "employee_advances"


class ActionType(str, Enum):
    """Action types for permissions"""
    ALL = "*"           # All actions
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    CLASSIFY = "classify"
    EXPORT = "export"


# Role hierarchy levels (higher = more permissions)
ROLE_HIERARCHY: Dict[str, int] = {
    SystemRole.ADMIN: 100,
    SystemRole.CONTADOR: 80,
    SystemRole.ACCOUNTANT: 80,
    SystemRole.MANAGER: 60,
    SystemRole.SUPERVISOR: 50,
    SystemRole.EMPLEADO: 0,
    SystemRole.VIEWER: 0,
}


# Default permissions for each system role
# These match the JSONB permissions in roles table
DEFAULT_ROLE_PERMISSIONS: Dict[str, Dict[str, any]] = {
    SystemRole.ADMIN: {
        "resources": [ResourceType.ALL],
        "actions": [ActionType.ALL],
        "scope": PermissionScope.ALL,
    },
    SystemRole.CONTADOR: {
        "resources": [
            ResourceType.INVOICES,
            ResourceType.CLASSIFICATIONS,
            ResourceType.POLIZAS,
            ResourceType.EXPENSES,
        ],
        "actions": [
            ActionType.READ,
            ActionType.CLASSIFY,
            ActionType.APPROVE,
            ActionType.REJECT,
        ],
        "scope": PermissionScope.TENANT,
    },
    SystemRole.ACCOUNTANT: {
        "resources": [
            ResourceType.INVOICES,
            ResourceType.EXPENSES,
            ResourceType.BANK_RECONCILIATION,
        ],
        "actions": [
            ActionType.READ,
            ActionType.UPDATE,
            ActionType.APPROVE,
        ],
        "scope": PermissionScope.TENANT,
    },
    SystemRole.MANAGER: {
        "resources": [
            ResourceType.EXPENSES,
            ResourceType.INVOICES,
            ResourceType.REPORTS,
            ResourceType.EMPLOYEE_ADVANCES,
        ],
        "actions": [
            ActionType.READ,
            ActionType.APPROVE,
            ActionType.REJECT,
        ],
        "scope": PermissionScope.ALL,
    },
    SystemRole.SUPERVISOR: {
        "resources": [
            ResourceType.EXPENSES,
            ResourceType.INVOICES,
        ],
        "actions": [
            ActionType.READ,
            ActionType.APPROVE,
        ],
        "scope": PermissionScope.DEPARTMENT,
    },
    SystemRole.EMPLEADO: {
        "resources": [
            ResourceType.EXPENSES,
            ResourceType.INVOICES,
        ],
        "actions": [
            ActionType.READ,
            ActionType.CREATE,
            ActionType.UPDATE,
        ],
        "scope": PermissionScope.OWN,
    },
    SystemRole.VIEWER: {
        "resources": [
            ResourceType.EXPENSES,
            ResourceType.INVOICES,
            ResourceType.REPORTS,
        ],
        "actions": [
            ActionType.READ,
        ],
        "scope": PermissionScope.OWN,
    },
}


# Role display names for UI
ROLE_DISPLAY_NAMES: Dict[str, str] = {
    SystemRole.ADMIN: "Administrador",
    SystemRole.CONTADOR: "Contador",
    SystemRole.ACCOUNTANT: "Contador General",
    SystemRole.MANAGER: "Gerente",
    SystemRole.SUPERVISOR: "Supervisor",
    SystemRole.EMPLEADO: "Empleado",
    SystemRole.VIEWER: "Visor",
}


# Role descriptions
ROLE_DESCRIPTIONS: Dict[str, str] = {
    SystemRole.ADMIN: "Administrador del sistema con acceso completo",
    SystemRole.CONTADOR: "Contador profesional con acceso a clasificación contable y validación de pólizas",
    SystemRole.ACCOUNTANT: "Contador con permisos generales de contabilidad",
    SystemRole.MANAGER: "Gerente con acceso amplio a reportes y aprobaciones",
    SystemRole.SUPERVISOR: "Supervisor de departamento con acceso a su equipo",
    SystemRole.EMPLEADO: "Usuario estándar con acceso a sus propios gastos",
    SystemRole.VIEWER: "Usuario de solo lectura",
}


def get_role_level(role_name: str) -> int:
    """
    Get the hierarchy level of a role

    Args:
        role_name: Name of the role (e.g., 'admin', 'contador')

    Returns:
        int: Hierarchy level (0-100, higher = more permissions)
    """
    return ROLE_HIERARCHY.get(role_name, 0)


def is_system_role(role_name: str) -> bool:
    """
    Check if a role is a system-defined role

    Args:
        role_name: Name of the role

    Returns:
        bool: True if it's a system role
    """
    try:
        SystemRole(role_name)
        return True
    except ValueError:
        return False


def get_highest_role(role_names: List[str]) -> Optional[str]:
    """
    Get the highest-level role from a list of role names

    Args:
        role_names: List of role names

    Returns:
        str: Name of the highest-level role, or None if list is empty
    """
    if not role_names:
        return None

    return max(role_names, key=lambda r: get_role_level(r))


def get_role_permissions(role_name: str) -> Dict[str, any]:
    """
    Get the default permissions for a role

    Args:
        role_name: Name of the role

    Returns:
        dict: Permission configuration with resources, actions, and scope
    """
    return DEFAULT_ROLE_PERMISSIONS.get(
        role_name,
        {
            "resources": [],
            "actions": [ActionType.READ],
            "scope": PermissionScope.OWN,
        }
    )


def can_access_resource(
    user_roles: List[str],
    resource: str,
    action: str,
    scope_required: Optional[str] = None
) -> bool:
    """
    Check if a user with given roles can access a resource

    Args:
        user_roles: List of role names assigned to the user
        resource: Resource type (e.g., 'expenses', 'invoices')
        action: Action type (e.g., 'read', 'create')
        scope_required: Optional scope requirement

    Returns:
        bool: True if user has permission
    """
    for role_name in user_roles:
        perms = get_role_permissions(role_name)

        # Check if role has wildcard access
        if ResourceType.ALL in perms.get("resources", []):
            return True

        # Check if role has access to this specific resource
        if resource in perms.get("resources", []):
            # Check if role can perform this action
            actions = perms.get("actions", [])
            if ActionType.ALL in actions or action in actions:
                # Check scope if specified
                if scope_required:
                    return perms.get("scope") == scope_required or perms.get("scope") == PermissionScope.ALL
                return True

    return False


def has_role(user_roles: List[str], required_role: str) -> bool:
    """
    Check if user has a specific role

    Args:
        user_roles: List of role names assigned to the user
        required_role: Role name to check for

    Returns:
        bool: True if user has the role
    """
    return required_role in user_roles


def has_any_role(user_roles: List[str], required_roles: List[str]) -> bool:
    """
    Check if user has any of the required roles

    Args:
        user_roles: List of role names assigned to the user
        required_roles: List of role names to check for

    Returns:
        bool: True if user has at least one of the required roles
    """
    return any(role in user_roles for role in required_roles)


def get_role_display_name(role_name: str) -> str:
    """
    Get the display name for a role

    Args:
        role_name: Internal role name

    Returns:
        str: Display name for UI
    """
    return ROLE_DISPLAY_NAMES.get(role_name, role_name.title())


def get_role_description(role_name: str) -> str:
    """
    Get the description for a role

    Args:
        role_name: Internal role name

    Returns:
        str: Role description
    """
    return ROLE_DESCRIPTIONS.get(role_name, "")


# Backward compatibility: map old role names to new ones
ROLE_MAPPING: Dict[str, str] = {
    "user": SystemRole.EMPLEADO,       # Old 'user' → new 'empleado'
    "employee": SystemRole.EMPLEADO,   # Alternative
    "admin": SystemRole.ADMIN,         # Keep as-is
    "contador": SystemRole.CONTADOR,   # Keep as-is
    "accountant": SystemRole.ACCOUNTANT,  # Keep as-is
    "manager": SystemRole.MANAGER,     # Keep as-is
    "supervisor": SystemRole.SUPERVISOR,  # Keep as-is
    "viewer": SystemRole.VIEWER,       # Keep as-is
}


def normalize_role_name(role_name: str) -> str:
    """
    Normalize a role name to the standard system role

    Args:
        role_name: Role name (may be legacy or alternative spelling)

    Returns:
        str: Normalized role name
    """
    return ROLE_MAPPING.get(role_name.lower(), role_name.lower())
