"""
API para User Preferences
Gestión de preferencias de usuario
"""

from contextlib import closing
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import json
import logging

from core.unified_auth import get_current_active_user, User as AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user/preferences", tags=["preferences"])


# ============================================================================
# MODELS
# ============================================================================

class UserPreferencesRequest(BaseModel):
    """Request para actualizar preferencias"""
    preferences: Dict[str, Any]
    onboarding_step: Optional[int] = None
    demo_preferences: Optional[Dict[str, Any]] = None
    completion_rules: Optional[Dict[str, Any]] = None
    field_priorities: Optional[Dict[str, Any]] = None


class UserPreferencesResponse(BaseModel):
    """Response con preferencias del usuario"""
    id: int
    user_id: int
    company_id: str
    preferences: Dict[str, Any]
    onboarding_step: Optional[int]
    demo_preferences: Optional[Dict[str, Any]]
    completion_rules: Optional[Dict[str, Any]]
    field_priorities: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str
    tenant_id: int


# ============================================================================
# HELPERS
# ============================================================================

def get_db_connection():
    """Obtener conexión a DB"""
    conn = sqlite3.connect("unified_mcp_system.db")
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=UserPreferencesResponse)
def get_user_preferences(
    current_user: AuthUser = Depends(get_current_active_user),
):
    """
    Obtener preferencias del usuario actual
    """
    tenant_id = current_user.tenant_id
    user_id = current_user.id

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM user_preferences
                WHERE user_id = ? AND tenant_id = ?
                """,
                (user_id, tenant_id),
            )

            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Preferencias no configuradas")

            return UserPreferencesResponse(
                id=row["id"],
                user_id=row["user_id"],
                company_id=row["company_id"] or str(current_user.company_id or "default"),
                preferences=json.loads(row["preferences"]) if row["preferences"] else {},
                onboarding_step=row["onboarding_step"],
                demo_preferences=json.loads(row["demo_preferences"]) if row["demo_preferences"] else None,
                completion_rules=json.loads(row["completion_rules"]) if row["completion_rules"] else None,
                field_priorities=json.loads(row["field_priorities"]) if row["field_priorities"] else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                tenant_id=row["tenant_id"],
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo preferencias: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("", response_model=UserPreferencesResponse)
def update_user_preferences(
    request: UserPreferencesRequest,
    current_user: AuthUser = Depends(get_current_active_user),
):
    """
    Actualizar preferencias del usuario
    """
    tenant_id = current_user.tenant_id
    user_id = current_user.id
    company_id = str(current_user.company_id) if current_user.company_id is not None else "default"

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM user_preferences
                WHERE user_id = ? AND tenant_id = ?
                """,
                (user_id, tenant_id),
            )
            row = cursor.fetchone()
            now = datetime.utcnow().isoformat()

            preferences_json = json.dumps(request.preferences)
            demo_json = json.dumps(request.demo_preferences) if request.demo_preferences else None
            completion_json = json.dumps(request.completion_rules) if request.completion_rules else None
            priorities_json = json.dumps(request.field_priorities) if request.field_priorities else None

            if row:
                cursor.execute(
                    """
                    UPDATE user_preferences
                    SET preferences = ?,
                        onboarding_step = ?,
                        demo_preferences = ?,
                        completion_rules = ?,
                        field_priorities = ?,
                        updated_at = ?
                    WHERE user_id = ? AND tenant_id = ?
                    """,
                    (
                        preferences_json,
                        request.onboarding_step,
                        demo_json,
                        completion_json,
                        priorities_json,
                        now,
                        user_id,
                        tenant_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_preferences
                    (user_id, company_id, preferences, onboarding_step, demo_preferences,
                     completion_rules, field_priorities, tenant_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        company_id,
                        preferences_json,
                        request.onboarding_step,
                        demo_json,
                        completion_json,
                        priorities_json,
                        tenant_id,
                        now,
                        now,
                    ),
                )

            conn.commit()

            cursor.execute(
                """
                SELECT * FROM user_preferences
                WHERE user_id = ? AND tenant_id = ?
                """,
                (user_id, tenant_id),
            )
            updated = cursor.fetchone()

        if not updated:
            raise HTTPException(status_code=500, detail="No se pudieron recuperar las preferencias actualizadas")

        logger.info(f"✅ Preferencias actualizadas para user_id={user_id}, tenant_id={tenant_id}")

        return UserPreferencesResponse(
            id=updated["id"],
            user_id=updated["user_id"],
            company_id=updated["company_id"] or company_id,
            preferences=json.loads(updated["preferences"]) if updated["preferences"] else {},
            onboarding_step=updated["onboarding_step"],
            demo_preferences=json.loads(updated["demo_preferences"]) if updated["demo_preferences"] else None,
            completion_rules=json.loads(updated["completion_rules"]) if updated["completion_rules"] else None,
            field_priorities=json.loads(updated["field_priorities"]) if updated["field_priorities"] else None,
            created_at=updated["created_at"],
            updated_at=updated["updated_at"],
            tenant_id=updated["tenant_id"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando preferencias: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
def delete_user_preferences(
    current_user: AuthUser = Depends(get_current_active_user),
):
    """
    Eliminar preferencias del usuario (reset to default)
    """
    tenant_id = current_user.tenant_id
    user_id = current_user.id

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM user_preferences
                WHERE user_id = ? AND tenant_id = ?
                """,
                (user_id, tenant_id),
            )

            deleted = cursor.rowcount
            conn.commit()

        if deleted == 0:
            raise HTTPException(status_code=404, detail="Preferencias no encontradas")

        logger.info(f"✅ Preferencias eliminadas para user_id={user_id}, tenant_id={tenant_id}")

        return {"success": True, "message": "Preferencias reseteadas"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando preferencias: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HELPERS
# ============================================================================

def create_default_preferences(user_id: int, tenant_id: int, company_id: Optional[str] = None) -> UserPreferencesResponse:
    """Crear preferencias default para usuario nuevo"""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            default_prefs = {
                "theme": "light",
                "language": "es",
                "notifications_enabled": True,
                "auto_categorization": True
            }

            cursor.execute(
                """
                INSERT INTO user_preferences
                (user_id, company_id, preferences, onboarding_step, tenant_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    company_id or "default",
                    json.dumps(default_prefs),
                    0,
                    tenant_id,
                    now,
                    now,
                ),
            )

            pref_id = cursor.lastrowid
            conn.commit()

            logger.info(f"✅ Preferencias default creadas para user_id={user_id}, tenant_id={tenant_id}")

            return UserPreferencesResponse(
                id=pref_id,
                user_id=user_id,
                company_id=company_id or "default",
                preferences=default_prefs,
                onboarding_step=0,
                demo_preferences=None,
                completion_rules=None,
                field_priorities=None,
                created_at=now,
                updated_at=now,
                tenant_id=tenant_id
            )

    except Exception as e:
        logger.error(f"Error creando preferencias default: {e}")
        raise HTTPException(status_code=500, detail=str(e))
