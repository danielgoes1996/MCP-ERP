"""
SAT Credentials API
Manage SAT FIEL credentials (e-signature) for automatic downloads
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from typing import Optional
import logging
import os
import shutil
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from core.auth.jwt import get_current_user, User, get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sat/credentials", tags=["SAT Credentials"])


# =====================================================
# MODELS
# =====================================================

class SATCredentialsResponse(BaseModel):
    """SAT Credentials response (without sensitive data)"""
    id: int
    company_id: int
    rfc: str
    certificate_serial_number: Optional[str] = None
    certificate_valid_from: Optional[str] = None
    certificate_valid_until: Optional[str] = None
    is_active: bool
    created_at: str


# =====================================================
# VAULT DIRECTORY SETUP
# =====================================================

# Credentials vault directory (secure location)
CREDENTIALS_VAULT_DIR = os.getenv("CREDENTIALS_VAULT_DIR", "/app/credentials/sat_vault")

def ensure_vault_directory(company_id: int) -> str:
    """
    Ensure company vault directory exists
    Returns the company's vault path
    """
    company_vault = os.path.join(CREDENTIALS_VAULT_DIR, str(company_id))
    os.makedirs(company_vault, mode=0o700, exist_ok=True)
    return company_vault


def parse_certificate(cer_path: str) -> dict:
    """
    Parse .cer file to extract certificate information
    Returns: serial_number, valid_from, valid_until
    """
    try:
        with open(cer_path, 'rb') as f:
            cert_data = f.read()

        cert = x509.load_der_x509_certificate(cert_data, default_backend())

        return {
            "serial_number": format(cert.serial_number, 'x'),
            "valid_from": cert.not_valid_before_utc,
            "valid_until": cert.not_valid_after_utc
        }
    except Exception as e:
        logger.warning(f"Could not parse certificate: {e}")
        return {
            "serial_number": None,
            "valid_from": None,
            "valid_until": None
        }


# =====================================================
# ENDPOINTS
# =====================================================

@router.post("/upload", response_model=SATCredentialsResponse)
async def upload_sat_credentials(
    rfc: str = Form(...),
    sat_password: str = Form(...),
    fiel_password: str = Form(...),
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload SAT FIEL credentials

    **Required:**
    - rfc: Company RFC (12-13 characters)
    - sat_password: SAT portal password
    - fiel_password: FIEL (e.firma) password
    - cer_file: Certificate file (.cer)
    - key_file: Private key file (.key)

    **Returns:**
    - Credentials information (without sensitive data)
    """

    try:
        # Get company_id from user's tenant
        # NOTE: users.company_id doesn't exist (denormalized)
        # We need to get it via: users.tenant_id -> companies.tenant_id
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.id
            FROM companies c
            WHERE c.tenant_id = %s
            LIMIT 1
        """, (current_user.tenant_id,))

        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=400, detail="No company found for your tenant")

        company_id = result[0]

        # Validate RFC length
        if len(rfc) not in [12, 13]:
            raise HTTPException(status_code=400, detail="RFC must be 12 or 13 characters")

        # Validate file extensions
        if not cer_file.filename.endswith('.cer'):
            raise HTTPException(status_code=400, detail="Certificate file must have .cer extension")

        if not key_file.filename.endswith('.key'):
            raise HTTPException(status_code=400, detail="Key file must have .key extension")

        # Create company vault directory
        vault_dir = ensure_vault_directory(company_id)

        # Save files to vault
        cer_path = os.path.join(vault_dir, f"{rfc}.cer")
        key_path = os.path.join(vault_dir, f"{rfc}.key")
        password_path = os.path.join(vault_dir, f"{rfc}_passwords.txt")

        # Save .cer file
        with open(cer_path, "wb") as f:
            shutil.copyfileobj(cer_file.file, f)

        # Save .key file
        with open(key_path, "wb") as f:
            shutil.copyfileobj(key_file.file, f)

        # Save passwords (in production, use proper encryption)
        with open(password_path, "w") as f:
            f.write(f"SAT_PASSWORD={sat_password}\n")
            f.write(f"FIEL_PASSWORD={fiel_password}\n")

        # Set secure permissions
        os.chmod(cer_path, 0o600)
        os.chmod(key_path, 0o600)
        os.chmod(password_path, 0o600)

        # Parse certificate information
        cert_info = parse_certificate(cer_path)

        # Check if credentials already exist for this company
        cursor.execute("""
            SELECT id FROM sat_efirma_credentials
            WHERE company_id = %s AND rfc = %s
        """, (company_id, rfc))

        existing = cursor.fetchone()

        if existing:
            # Update existing credentials
            cursor.execute("""
                UPDATE sat_efirma_credentials
                SET vault_cer_path = %s,
                    vault_key_path = %s,
                    vault_password_path = %s,
                    certificate_serial_number = %s,
                    certificate_valid_from = %s,
                    certificate_valid_until = %s,
                    is_active = true,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, company_id, rfc, certificate_serial_number,
                          certificate_valid_from, certificate_valid_until,
                          is_active, created_at
            """, (
                cer_path, key_path, password_path,
                cert_info["serial_number"],
                cert_info["valid_from"],
                cert_info["valid_until"],
                existing[0]
            ))
        else:
            # Insert new credentials
            cursor.execute("""
                INSERT INTO sat_efirma_credentials (
                    company_id, rfc, vault_cer_path, vault_key_path, vault_password_path,
                    certificate_serial_number, certificate_valid_from, certificate_valid_until,
                    is_active, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true, %s)
                RETURNING id, company_id, rfc, certificate_serial_number,
                          certificate_valid_from, certificate_valid_until,
                          is_active, created_at
            """, (
                company_id, rfc, cer_path, key_path, password_path,
                cert_info["serial_number"],
                cert_info["valid_from"],
                cert_info["valid_until"],
                current_user.id
            ))

        result = cursor.fetchone()
        conn.commit()
        conn.close()

        logger.info(f"✅ SAT credentials uploaded for company {company_id}, RFC {rfc}")

        return SATCredentialsResponse(
            id=result[0],
            company_id=result[1],
            rfc=result[2],
            certificate_serial_number=result[3],
            certificate_valid_from=result[4].isoformat() if result[4] else None,
            certificate_valid_until=result[5].isoformat() if result[5] else None,
            is_active=result[6],
            created_at=result[7].isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading SAT credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading credentials: {str(e)}"
        )


@router.get("/{company_identifier}", response_model=Optional[SATCredentialsResponse])
async def get_sat_credentials(
    company_identifier: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get SAT credentials for a company

    **Parameters:**
    - company_identifier: Can be either:
      - Integer company_id (e.g., "1")
      - String tenant company_id (e.g., "carreta_verde")

    **Returns:**
    - Credentials information (without sensitive passwords/keys)
    - null if no credentials found
    """

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Resolve company_identifier to companies.id AND tenant_id
        # Accepts either integer (companies.id) or string (companies.company_id slug)
        try:
            company_id = int(company_identifier)
        except ValueError:
            # It's a company_id slug - look up companies.id directly
            cursor.execute("""
                SELECT id, tenant_id
                FROM companies
                WHERE company_id = %s
                LIMIT 1
            """, (company_identifier,))

            result = cursor.fetchone()
            if not result:
                logger.warning(f"No company found for company_id slug: {company_identifier}")
                conn.close()
                return None

            company_id = result[0]
            company_tenant_id = result[1]
            logger.info(f"Resolved company_id slug '{company_identifier}' to companies.id {company_id}")
        else:
            # Integer was provided - still need to get tenant_id for authorization
            cursor.execute("""
                SELECT tenant_id
                FROM companies
                WHERE id = %s
                LIMIT 1
            """, (company_id,))

            result = cursor.fetchone()
            if not result:
                logger.warning(f"No company found for companies.id: {company_id}")
                conn.close()
                return None

            company_tenant_id = result[0]

        # 🔒 AUTHORIZATION: Verify user has access to this company
        if current_user.tenant_id != company_tenant_id:
            logger.warning(
                f"SECURITY: User {current_user.email} (tenant_id={current_user.tenant_id}) "
                f"attempted to access SAT credentials for company_id={company_id} "
                f"(tenant_id={company_tenant_id})"
            )
            conn.close()
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to access this company's credentials"
            )

        # Now fetch SAT credentials using the resolved company_id
        cursor.execute("""
            SELECT id, company_id, rfc, certificate_serial_number,
                   certificate_valid_from, certificate_valid_until,
                   is_active, created_at
            FROM sat_efirma_credentials
            WHERE company_id = %s AND is_active = true
            ORDER BY created_at DESC
            LIMIT 1
        """, (company_id,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return SATCredentialsResponse(
            id=result[0],
            company_id=result[1],
            rfc=result[2],
            certificate_serial_number=result[3],
            certificate_valid_from=result[4].isoformat() if result[4] else None,
            certificate_valid_until=result[5].isoformat() if result[5] else None,
            is_active=result[6],
            created_at=result[7].isoformat()
        )

    except Exception as e:
        logger.error(f"Error fetching SAT credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error fetching credentials"
        )


@router.delete("/{company_identifier}")
async def delete_sat_credentials(
    company_identifier: str,
    current_user: User = Depends(get_current_user)
):
    """
    Deactivate SAT credentials for a company
    (Soft delete - files remain for audit purposes)

    **Parameters:**
    - company_identifier: Can be either:
      - Integer company_id (e.g., "1")
      - String tenant company_id (e.g., "carreta_verde")

    **Returns:**
    - success: true/false
    - message: Confirmation message
    """

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Resolve company_identifier to companies.id AND tenant_id
        try:
            company_id = int(company_identifier)
        except ValueError:
            cursor.execute("""
                SELECT id, tenant_id
                FROM companies
                WHERE company_id = %s
                LIMIT 1
            """, (company_identifier,))

            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Company not found")

            company_id = result[0]
            company_tenant_id = result[1]
        else:
            # Integer was provided - still need to get tenant_id for authorization
            cursor.execute("""
                SELECT tenant_id
                FROM companies
                WHERE id = %s
                LIMIT 1
            """, (company_id,))

            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Company not found")

            company_tenant_id = result[0]

        # 🔒 AUTHORIZATION: Verify user has access to this company
        if current_user.tenant_id != company_tenant_id:
            logger.warning(
                f"SECURITY: User {current_user.email} (tenant_id={current_user.tenant_id}) "
                f"attempted to delete SAT credentials for company_id={company_id} "
                f"(tenant_id={company_tenant_id})"
            )
            conn.close()
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this company's credentials"
            )

        cursor.execute("""
            UPDATE sat_efirma_credentials
            SET is_active = false,
                updated_at = CURRENT_TIMESTAMP
            WHERE company_id = %s AND is_active = true
        """, (company_id,))

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected == 0:
            raise HTTPException(status_code=404, detail="No active credentials found")

        logger.info(f"✅ SAT credentials deactivated for company {company_id}")

        return {
            "success": True,
            "message": "Credentials deactivated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating SAT credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error deactivating credentials"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    vault_exists = os.path.exists(CREDENTIALS_VAULT_DIR)
    vault_writable = os.access(CREDENTIALS_VAULT_DIR, os.W_OK) if vault_exists else False

    return {
        "status": "healthy",
        "vault_directory": CREDENTIALS_VAULT_DIR,
        "vault_exists": vault_exists,
        "vault_writable": vault_writable
    }
