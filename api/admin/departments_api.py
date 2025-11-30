"""
Admin API for Department Management

Endpoints for managing departments and organizational hierarchy.
Only accessible by admin users.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from core.auth.jwt import User, require_role
from core.shared.unified_db_adapter import (
    get_unified_adapter,
    get_all_departments,
    get_department_users,
)

router = APIRouter(prefix="/api/admin/departments", tags=["Admin - Departments"])
logger = logging.getLogger(__name__)


# =================== REQUEST/RESPONSE MODELS ===================

class DepartmentResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    code: Optional[str]
    parent_id: Optional[int]
    manager_user_id: Optional[int]
    description: Optional[str]
    cost_center: Optional[str]
    is_active: bool
    created_at: str
    user_count: int = 0


class CreateDepartmentRequest(BaseModel):
    name: str
    code: Optional[str] = None
    parent_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    description: Optional[str] = None
    cost_center: Optional[str] = None


class UpdateDepartmentRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    parent_id: Optional[int] = None
    manager_user_id: Optional[int] = None
    description: Optional[str] = None
    cost_center: Optional[str] = None
    is_active: Optional[bool] = None


# =================== ENDPOINTS ===================

@router.get("/", response_model=List[DepartmentResponse])
async def list_departments(
    include_inactive: bool = False,
    current_user: User = Depends(require_role(['admin']))
) -> List[DepartmentResponse]:
    """
    List all departments in the current tenant.

    🔐 Requires: admin role
    """
    try:
        departments = get_all_departments(
            current_user.tenant_id,
            include_inactive=include_inactive
        )

        # Get user count for each department
        result = []
        for dept in departments:
            users = get_department_users(dept['id'], include_subdepartments=False)
            result.append(DepartmentResponse(
                id=dept['id'],
                tenant_id=dept['tenant_id'],
                name=dept['name'],
                code=dept.get('code'),
                parent_id=dept.get('parent_id'),
                manager_user_id=dept.get('manager_user_id'),
                description=dept.get('description'),
                cost_center=dept.get('cost_center'),
                is_active=dept['is_active'],
                created_at=str(dept['created_at']),
                user_count=len(users)
            ))

        return result

    except Exception as e:
        logger.error(f"Error listing departments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: int,
    current_user: User = Depends(require_role(['admin']))
) -> DepartmentResponse:
    """
    Get detailed information about a specific department.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, tenant_id, name, code, parent_id,
                manager_user_id, description, cost_center,
                is_active, created_at
            FROM departments
            WHERE id = ? AND tenant_id = ?
        """, (department_id, current_user.tenant_id))

        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Department not found")

        users = get_department_users(department_id, include_subdepartments=False)

        return DepartmentResponse(
            id=row[0],
            tenant_id=row[1],
            name=row[2],
            code=row[3],
            parent_id=row[4],
            manager_user_id=row[5],
            description=row[6],
            cost_center=row[7],
            is_active=bool(row[8]),
            created_at=str(row[9]),
            user_count=len(users)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting department: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    request: CreateDepartmentRequest,
    current_user: User = Depends(require_role(['admin']))
) -> DepartmentResponse:
    """
    Create a new department.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Validate parent department if specified
        if request.parent_id:
            cursor.execute("""
                SELECT id FROM departments
                WHERE id = ? AND tenant_id = ?
            """, (request.parent_id, current_user.tenant_id))

            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Parent department not found")

        # Validate manager if specified
        if request.manager_user_id:
            cursor.execute("""
                SELECT id FROM users
                WHERE id = ? AND tenant_id = ?
            """, (request.manager_user_id, current_user.tenant_id))

            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Manager user not found")

        # Insert department
        cursor.execute("""
            INSERT INTO departments (
                tenant_id, name, code, parent_id, manager_user_id,
                description, cost_center, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            current_user.tenant_id,
            request.name,
            request.code,
            request.parent_id,
            request.manager_user_id,
            request.description,
            request.cost_center,
            current_user.id
        ))

        department_id = cursor.lastrowid
        conn.commit()

        # Fetch created department
        cursor.execute("""
            SELECT
                id, tenant_id, name, code, parent_id,
                manager_user_id, description, cost_center,
                is_active, created_at
            FROM departments
            WHERE id = ?
        """, (department_id,))

        row = cursor.fetchone()
        conn.close()

        return DepartmentResponse(
            id=row[0],
            tenant_id=row[1],
            name=row[2],
            code=row[3],
            parent_id=row[4],
            manager_user_id=row[5],
            description=row[6],
            cost_center=row[7],
            is_active=bool(row[8]),
            created_at=str(row[9]),
            user_count=0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating department: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: int,
    request: UpdateDepartmentRequest,
    current_user: User = Depends(require_role(['admin']))
) -> DepartmentResponse:
    """
    Update department information.

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Verify department exists
        cursor.execute("""
            SELECT id FROM departments
            WHERE id = ? AND tenant_id = ?
        """, (department_id, current_user.tenant_id))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Department not found")

        # Build update query
        updates = []
        params = []

        if request.name is not None:
            updates.append("name = ?")
            params.append(request.name)

        if request.code is not None:
            updates.append("code = ?")
            params.append(request.code)

        if request.parent_id is not None:
            # Validate parent
            if request.parent_id == department_id:
                raise HTTPException(status_code=400, detail="Department cannot be its own parent")
            updates.append("parent_id = ?")
            params.append(request.parent_id)

        if request.manager_user_id is not None:
            updates.append("manager_user_id = ?")
            params.append(request.manager_user_id)

        if request.description is not None:
            updates.append("description = ?")
            params.append(request.description)

        if request.cost_center is not None:
            updates.append("cost_center = ?")
            params.append(request.cost_center)

        if request.is_active is not None:
            updates.append("is_active = ?")
            params.append(request.is_active)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([department_id, current_user.tenant_id])

        cursor.execute(f"""
            UPDATE departments
            SET {', '.join(updates)}
            WHERE id = ? AND tenant_id = ?
        """, params)

        conn.commit()

        # Fetch updated department
        cursor.execute("""
            SELECT
                id, tenant_id, name, code, parent_id,
                manager_user_id, description, cost_center,
                is_active, created_at
            FROM departments
            WHERE id = ?
        """, (department_id,))

        row = cursor.fetchone()
        conn.close()

        users = get_department_users(department_id, include_subdepartments=False)

        return DepartmentResponse(
            id=row[0],
            tenant_id=row[1],
            name=row[2],
            code=row[3],
            parent_id=row[4],
            manager_user_id=row[5],
            description=row[6],
            cost_center=row[7],
            is_active=bool(row[8]),
            created_at=str(row[9]),
            user_count=len(users)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating department: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{department_id}")
async def delete_department(
    department_id: int,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Soft delete a department (mark as inactive).

    🔐 Requires: admin role
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE departments
            SET is_active = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND tenant_id = ?
        """, (department_id, current_user.tenant_id))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Department not found")

        conn.commit()
        conn.close()

        return {"message": "Department deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting department: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{department_id}/users")
async def get_department_users_endpoint(
    department_id: int,
    include_subdepartments: bool = False,
    current_user: User = Depends(require_role(['admin']))
) -> List[Dict[str, Any]]:
    """
    Get all users assigned to a department.

    🔐 Requires: admin role
    """
    try:
        # Verify department exists in tenant
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM departments
            WHERE id = ? AND tenant_id = ?
        """, (department_id, current_user.tenant_id))

        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Department not found")

        conn.close()

        users = get_department_users(department_id, include_subdepartments)
        return users

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting department users: {e}")
        raise HTTPException(status_code=500, detail=str(e))
