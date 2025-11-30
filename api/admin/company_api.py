"""
Admin API for Company Management

Endpoints for managing company information, logo, fiscal documents, and AI context.
Only accessible by admin users.
"""

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json
import os
from datetime import datetime
import uuid

from core.auth.jwt import User, get_current_user, require_role
from core.shared.unified_db_adapter import get_unified_adapter

router = APIRouter(prefix="/api/admin/company", tags=["Admin - Company"])
logger = logging.getLogger(__name__)

# Upload directory for company files
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/company")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# =================== REQUEST/RESPONSE MODELS ===================

class CompanyInfoResponse(BaseModel):
    id: int
    name: str
    company_id: Optional[str] = None
    description: Optional[str] = None
    rfc: Optional[str] = None
    logo_url: Optional[str] = None
    fiscal_document_url: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: str


class UpdateCompanyNameRequest(BaseModel):
    name: str


class UpdateCompanySettingsRequest(BaseModel):
    industry: Optional[str] = None
    business_model: Optional[str] = None
    typical_expenses: Optional[List[str]] = None
    provider_treatments: Optional[Dict[str, str]] = None
    preferences: Optional[Dict[str, Any]] = None


# =================== ENDPOINTS ===================

@router.get("", response_model=CompanyInfoResponse)
async def get_company_info(
    current_user: User = Depends(get_current_user)
) -> CompanyInfoResponse:
    """
    Get company information for the current user's tenant.
    Combines data from tenants table and companies.settings.
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Get tenant information
        cursor.execute("""
            SELECT
                id, name, company_id, description,
                logo_url, fiscal_document_url, rfc,
                is_active, created_at
            FROM tenants
            WHERE id = %s
        """, (current_user.tenant_id,))

        tenant_row = cursor.fetchone()
        if not tenant_row:
            raise HTTPException(status_code=404, detail="Company not found")

        # Get company settings if they exist
        settings = None
        if tenant_row[2]:  # company_id exists
            cursor.execute("""
                SELECT settings
                FROM companies
                WHERE id = %s
            """, (tenant_row[2],))
            company_row = cursor.fetchone()
            if company_row and company_row[0]:
                try:
                    settings = json.loads(company_row[0]) if isinstance(company_row[0], str) else company_row[0]
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in company settings for company_id {tenant_row[2]}")

        conn.close()

        return CompanyInfoResponse(
            id=tenant_row[0],
            name=tenant_row[1],
            company_id=tenant_row[2],
            description=tenant_row[3],
            logo_url=tenant_row[4],
            fiscal_document_url=tenant_row[5],
            rfc=tenant_row[6],
            is_active=tenant_row[7],
            created_at=tenant_row[8].isoformat() if isinstance(tenant_row[8], datetime) else str(tenant_row[8]),
            settings=settings
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching company info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/name")
async def update_company_name(
    request: UpdateCompanyNameRequest,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Update company name. Admin only.
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE tenants
            SET name = %s
            WHERE id = %s
        """, (request.name, current_user.tenant_id))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Company not found")

        conn.commit()
        conn.close()

        logger.info(f"Company name updated by admin {current_user.id}")
        return {"message": "Company name updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company name: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def update_company_settings(
    request: UpdateCompanySettingsRequest,
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Update company AI context settings. Admin only.
    """
    try:
        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        # Get current tenant's company_id
        cursor.execute("SELECT company_id FROM tenants WHERE id = %s", (current_user.tenant_id,))
        tenant_row = cursor.fetchone()

        if not tenant_row or not tenant_row[0]:
            raise HTTPException(status_code=404, detail="Company not linked to tenant")

        company_id = tenant_row[0]

        # Get current settings
        cursor.execute("SELECT settings FROM companies WHERE id = %s", (company_id,))
        company_row = cursor.fetchone()

        if company_row and company_row[0]:
            try:
                current_settings = json.loads(company_row[0]) if isinstance(company_row[0], str) else company_row[0]
            except json.JSONDecodeError:
                current_settings = {}
        else:
            current_settings = {}

        # Update only provided fields
        if request.industry is not None:
            current_settings['industry'] = request.industry
        if request.business_model is not None:
            current_settings['business_model'] = request.business_model
        if request.typical_expenses is not None:
            current_settings['typical_expenses'] = request.typical_expenses
        if request.provider_treatments is not None:
            current_settings['provider_treatments'] = request.provider_treatments
        if request.preferences is not None:
            current_settings['preferences'] = request.preferences

        # Save updated settings
        settings_json = json.dumps(current_settings)
        cursor.execute("""
            UPDATE companies
            SET settings = %s
            WHERE id = %s
        """, (settings_json, company_id))

        conn.commit()
        conn.close()

        logger.info(f"Company settings updated by admin {current_user.id}")
        return {"message": "Company settings updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Upload company logo. Admin only.
    Allowed formats: PNG, JPG, JPEG, SVG
    """
    try:
        # Validate file type
        allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: PNG, JPG, JPEG, SVG"
            )

        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"logo_{current_user.tenant_id}_{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Update tenant record
        file_url = f"/uploads/company/{unique_filename}"

        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE tenants
            SET logo_url = %s
            WHERE id = %s
        """, (file_url, current_user.tenant_id))

        conn.commit()
        conn.close()

        logger.info(f"Company logo uploaded by admin {current_user.id}")
        return {"message": "Logo uploaded successfully", "url": file_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading logo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fiscal-document")
async def upload_fiscal_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(['admin']))
) -> Dict[str, str]:
    """
    Upload Constancia de Situación Fiscal (CSF). Admin only.
    Allowed formats: PDF
    """
    try:
        # Validate file type
        if file.content_type != 'application/pdf':
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF allowed"
            )

        # Generate unique filename
        unique_filename = f"csf_{current_user.tenant_id}_{uuid.uuid4()}.pdf"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Update tenant record
        file_url = f"/uploads/company/{unique_filename}"

        adapter = get_unified_adapter()
        conn = adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE tenants
            SET fiscal_document_url = %s
            WHERE id = %s
        """, (file_url, current_user.tenant_id))

        conn.commit()
        conn.close()

        logger.info(f"Fiscal document uploaded by admin {current_user.id}")
        return {"message": "Fiscal document uploaded successfully", "url": file_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading fiscal document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
