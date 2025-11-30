"""
Admin API for Role Management

Endpoints for managing roles and permissions.
Only accessible by admin users.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import json

from core.auth.jwt import User, require_role
from core.shared.unified_db_adapter import get_unified_adapter, get_all_roles

router = APIRouter(prefix="/api/admin/roles", tags=["Admin - Roles"])
logger = logging.getLogger(__name__)


# =================== REQUEST/RESPONSE MODELS ===================

class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    level: int
    permissions: Dict[str, Any]
    is_system: bool
    is_active: bool
    tenant_id: Optional[int] = None


class CreateRoleRequest(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    level: int = 0
    permissions: Dict[str, Any] = {}


class UpdateRoleRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    level: Optional[int] = None
    permissions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


# =================== ENDPOINTS ===================

@router.get("/", response_model=List[RoleResponse])
async def list_roles(
    include_system: bool = True,
    current_user: User = Depends(require_role(['admin']))
) -> List[RoleResponse]:
    """
    List all available roles (system + tenant-specific).

    🔐 Requires: admin role
    """
    try:
        roles = get_all_roles(
            tenant_id=current_user.tenant_id,
            include_system=include_system
        )

        return [RoleResponse(
            id=r['id'],
            name=r['name'],
            display_name=r['display_name'],
            description=r.get('description'),
            level=r['level'],
            permissions=r['permissions'] if isinstance(r['permissions'], dict) else {},
            is_system=r['is_system'],
            is_active=r['is_active'],
            tenant_id=None if r['is_system'] else current_user.tenant_id
        ) for r in roles]

    except Exception as e:
        logger.error(f"Error listing roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system", response_model=List[RoleResponse])
async def list_system_roles(
    current_user: User = Depends(require_role(['admin']))
) -> List[RoleResponse]:
    """
    List only system-defined roles.

    🔐 Requires: admin role
    """
    try:
        roles = get_all_roles(tenant_id=None, include_system=True)

        return [RoleResponse(
            id=r['id'],
            name=r['name'],
            display_name=r['display_name'],
            description=r.get('description'),
            level=r['level'],
            permissions=r['permissions'] if isinstance(r['permissions'], dict) else {},
            is_system=r['is_system'],
            is_active=r['is_active'],
            tenant_id=None
        ) for r in roles]

    except Exception as e:
        logger.error(f"Error listing system roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    current_user: User = Depends(require_role(['admin']))
) -> RoleResponse:
    """
    Get detailed information about a specific role.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, name, display_name, description, level,
                permissions, is_system, is_active, tenant_id
            FROM roles
            WHERE id = ?
              AND (tenant_id IS NULL OR tenant_id = ?)
        """, (role_id, current_user.tenant_id))

        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Role not found")

        permissions = row[5]
        if isinstance(permissions, str):
            permissions = json.loads(permissions)

        return RoleResponse(
            id=row[0],
            name=row[1],
            display_name=row[2],
            description=row[3],
            level=row[4],
            permissions=permissions if isinstance(permissions, dict) else {},
            is_system=bool(row[6]),
            is_active=bool(row[7]),
            tenant_id=row[8]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_role(
    request: CreateRoleRequest,
    current_user: User = Depends(require_role(['admin']))
) -> RoleResponse:
    """
    Create a custom tenant-specific role.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Check if role name already exists in tenant
        cursor.execute("""
            SELECT id FROM roles
            WHERE name = ? AND tenant_id = ?
        """, (request.name, current_user.tenant_id))

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"Role '{request.name}' already exists in this tenant"
            )

        # Insert new role
        permissions_json = json.dumps(request.permissions)

        cursor.execute("""
            INSERT INTO roles (
                tenant_id, name, display_name, description,
                level, permissions, is_system, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, FALSE, ?)
        """, (
            current_user.tenant_id,
            request.name,
            request.display_name,
            request.description,
            request.level,
            permissions_json,
            current_user.id
        ))

        role_id = cursor.lastrowid
        conn.commit()

        # Fetch created role
        cursor.execute("""
            SELECT
                id, name, display_name, description, level,
                permissions, is_system, is_active, tenant_id
            FROM roles
            WHERE id = ?
        """, (role_id,))

        row = cursor.fetchone()
        conn.close()

        permissions = row[5]
        if isinstance(permissions, str):
            permissions = json.loads(permissions)

        return RoleResponse(
            id=row[0],
            name=row[1],
            display_name=row[2],
            description=row[3],
            level=row[4],
            permissions=permissions if isinstance(permissions, dict) else {},
            is_system=bool(row[6]),
            is_active=bool(row[7]),
            tenant_id=row[8]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    request: UpdateRoleRequest,
    current_user: User = Depends(require_role(['admin']))
) -> RoleResponse:
    """
    Update a custom role. System roles cannot be modified.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Verify role exists and is not a system role
        cursor.execute("""
            SELECT id, is_system, tenant_id FROM roles
            WHERE id = ?
        """, (role_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Role not found")

        if row[1]:  # is_system
            raise HTTPException(
                status_code=400,
                detail="System roles cannot be modified"
            )

        if row[2] != current_user.tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify roles from other tenants"
            )

        # Build update query
        updates = []
        params = []

        if request.display_name is not None:
            updates.append("display_name = ?")
            params.append(request.display_name)

        if request.description is not None:
            updates.append("description = ?")
            params.append(request.description)

        if request.level is not None:
            updates.append("level = ?")
            params.append(request.level)

        if request.permissions is not None:
            updates.append("permissions = ?")
            params.append(json.dumps(request.permissions))

        if request.is_active is not None:
            updates.append("is_active = ?")
            params.append(request.is_active)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(role_id)

        cursor.execute(f"""
            UPDATE roles
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)

        conn.commit()

        # Fetch updated role
        cursor.execute("""
            SELECT
                id, name, display_name, description, level,
                permissions, is_system, is_active, tenant_id
            FROM roles
            WHERE id = ?
        """, (role_id,))

        row = cursor.fetchone()
        conn.close()

        permissions = row[5]
        if isinstance(permissions, str):
            permissions = json.loads(permissions)

        return RoleResponse(
            id=row[0],
            name=row[1],
            display_name=row[2],
            description=row[3],
            level=row[4],
            permissions=permissions if isinstance(permissions, dict) else {},
            is_system=bool(row[6]),
            is_active=bool(row[7]),
            tenant_id=row[8]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Soft delete a custom role. System roles cannot be deleted.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Verify role exists and is not a system role
        cursor.execute("""
            SELECT is_system, tenant_id FROM roles
            WHERE id = ?
        """, (role_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Role not found")

        if row[0]:  # is_system
            raise HTTPException(
                status_code=400,
                detail="System roles cannot be deleted"
            )

        if row[1] != current_user.tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete roles from other tenants"
            )

        # Soft delete (mark as inactive)
        cursor.execute("""
            UPDATE roles
            SET is_active = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (role_id,))

        conn.commit()
        conn.close()

        return {"message": "Role deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting role: {e}")
        raise HTTPException(status_code=500, detail=str(e))
