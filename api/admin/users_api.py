"""
Admin API for User Management

Endpoints for managing users, roles, and department assignments.
Only accessible by admin users.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from core.auth.jwt import User, get_current_user, require_role
from core.shared.unified_db_adapter import (
    get_unified_adapter,
    get_user_roles_with_details,
    get_user_departments_with_details,
    get_user_subordinates_hierarchy,
)

router = APIRouter(prefix="/api/admin/users", tags=["Admin - Users"])
logger = logging.getLogger(__name__)


# =================== REQUEST/RESPONSE MODELS ===================

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str  # Legacy highest role
    roles: List[str]  # All assigned roles
    tenant_id: int
    is_active: bool
    created_at: str
    department_id: Optional[int] = None
    departments: List[int] = []


class UserDetailResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    roles: List[Dict[str, Any]]  # Roles with full details
    tenant_id: int
    is_active: bool
    created_at: str
    departments: List[Dict[str, Any]]  # Departments with full details
    subordinates: List[Dict[str, Any]]  # Direct reports


class AssignRoleRequest(BaseModel):
    role_name: str
    expires_at: Optional[str] = None


class AssignDepartmentRequest(BaseModel):
    department_id: int
    is_primary: bool = False


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None  # For backward compatibility


# =================== ENDPOINTS ===================

@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_role(['admin']))
) -> List[UserResponse]:
    """
    List all users in the current tenant.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                u.id,
                u.email,
                u.full_name,
                u.role,
                u.tenant_id,
                u.is_active,
                u.created_at
            FROM users u
            WHERE u.tenant_id = ?
            ORDER BY u.full_name ASC
        """, (current_user.tenant_id,))

        users = []
        for row in cursor.fetchall():
            user_id = row[0]

            # Get all roles for this user
            roles_data = get_user_roles_with_details(user_id)
            role_names = [r['name'] for r in roles_data]

            # Get all departments for this user
            depts_data = get_user_departments_with_details(user_id)
            dept_ids = [d['id'] for d in depts_data]
            primary_dept = next((d['id'] for d in depts_data if d.get('is_primary')), None)

            users.append(UserResponse(
                id=row[0],
                email=row[1],
                full_name=row[2],
                role=row[3],
                roles=role_names,
                tenant_id=row[4],
                is_active=bool(row[5]),
                created_at=str(row[6]),
                department_id=primary_dept,
                departments=dept_ids
            ))

        conn.close()
        return users

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: int,
    current_user: User = Depends(require_role(['admin']))
) -> UserDetailResponse:
    """
    Get detailed information about a specific user.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Get user basic info
        cursor.execute("""
            SELECT
                id, email, full_name, role, tenant_id, is_active, created_at
            FROM users
            WHERE id = ? AND tenant_id = ?
        """, (user_id, current_user.tenant_id))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        # Get detailed roles
        roles = get_user_roles_with_details(user_id)

        # Get detailed departments
        departments = get_user_departments_with_details(user_id)

        # Get subordinates
        subordinates = get_user_subordinates_hierarchy(user_id, include_indirect=False)

        conn.close()

        return UserDetailResponse(
            id=row[0],
            email=row[1],
            full_name=row[2],
            role=row[3],
            roles=roles,
            tenant_id=row[4],
            is_active=bool(row[5]),
            created_at=str(row[6]),
            departments=departments,
            subordinates=subordinates
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role_to_user(
    user_id: int,
    request: AssignRoleRequest,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, Any]:
    """
    Assign a role to a user.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Verify user exists and belongs to tenant
        cursor.execute("""
            SELECT id FROM users
            WHERE id = ? AND tenant_id = ?
        """, (user_id, current_user.tenant_id))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        # Get role_id
        cursor.execute("""
            SELECT id, name FROM roles
            WHERE name = ?
              AND (tenant_id IS NULL OR tenant_id = ?)
              AND is_active = TRUE
        """, (request.role_name, current_user.tenant_id))

        role_row = cursor.fetchone()
        if not role_row:
            raise HTTPException(status_code=404, detail=f"Role '{request.role_name}' not found")

        role_id = role_row[0]

        # Check if assignment already exists
        cursor.execute("""
            SELECT 1 FROM user_roles
            WHERE user_id = ? AND role_id = ?
        """, (user_id, role_id))

        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="User already has this role")

        # Insert assignment
        cursor.execute("""
            INSERT INTO user_roles (user_id, role_id, assigned_by, expires_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, role_id, current_user.id, request.expires_at))

        conn.commit()
        conn.close()

        return {
            "message": f"Role '{request.role_name}' assigned successfully",
            "user_id": user_id,
            "role_name": request.role_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/roles/{role_name}")
async def remove_role_from_user(
    user_id: int,
    role_name: str,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Remove a role from a user.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Get role_id
        cursor.execute("""
            SELECT id FROM roles
            WHERE name = ?
        """, (role_name,))

        role_row = cursor.fetchone()
        if not role_row:
            raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

        role_id = role_row[0]

        # Delete assignment
        cursor.execute("""
            DELETE FROM user_roles
            WHERE user_id = ? AND role_id = ?
        """, (user_id, role_id))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Role assignment not found")

        conn.commit()
        conn.close()

        return {"message": f"Role '{role_name}' removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{user_id}/departments", status_code=status.HTTP_201_CREATED)
async def assign_department_to_user(
    user_id: int,
    request: AssignDepartmentRequest,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, Any]:
    """
    Assign a department to a user.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Verify user and department exist
        cursor.execute("""
            SELECT id FROM users
            WHERE id = ? AND tenant_id = ?
        """, (user_id, current_user.tenant_id))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("""
            SELECT id FROM departments
            WHERE id = ? AND tenant_id = ?
        """, (request.department_id, current_user.tenant_id))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Department not found")

        # Check if assignment exists
        cursor.execute("""
            SELECT 1 FROM user_departments
            WHERE user_id = ? AND department_id = ?
        """, (user_id, request.department_id))

        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="User already assigned to this department")

        # If setting as primary, unset other primary departments
        if request.is_primary:
            cursor.execute("""
                UPDATE user_departments
                SET is_primary = FALSE
                WHERE user_id = ?
            """, (user_id,))

        # Insert assignment
        cursor.execute("""
            INSERT INTO user_departments (user_id, department_id, is_primary, assigned_by)
            VALUES (?, ?, ?, ?)
        """, (user_id, request.department_id, request.is_primary, current_user.id))

        conn.commit()
        conn.close()

        return {
            "message": "Department assigned successfully",
            "user_id": user_id,
            "department_id": request.department_id,
            "is_primary": request.is_primary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning department: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{user_id}/departments/{department_id}")
async def remove_department_from_user(
    user_id: int,
    department_id: int,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Remove a department assignment from a user.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM user_departments
            WHERE user_id = ? AND department_id = ?
        """, (user_id, department_id))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Department assignment not found")

        conn.commit()
        conn.close()

        return {"message": "Department removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing department: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, Any]:
    """
    Update user information.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Build update query dynamically
        updates = []
        params = []

        if request.full_name is not None:
            updates.append("full_name = ?")
            params.append(request.full_name)

        if request.is_active is not None:
            updates.append("is_active = ?")
            params.append(request.is_active)

        if request.role is not None:
            updates.append("role = ?")
            params.append(request.role)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([user_id, current_user.tenant_id])

        cursor.execute(f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = ? AND tenant_id = ?
        """, params)

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")

        conn.commit()
        conn.close()

        return {"message": "User updated successfully", "user_id": user_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))
