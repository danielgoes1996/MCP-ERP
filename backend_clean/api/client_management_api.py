"""
API para Gestión de Clientes y Credenciales
Endpoints para configurar clientes, sus datos fiscales y credenciales de portales.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, validator
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime

from core.client_credential_manager import (
    get_credential_manager,
    ClientFiscalData,
    MerchantCredentials,
    setup_new_client
)

router = APIRouter(prefix="/api/v1/clients", tags=["client-management"])


# ===============================================================
# MODELOS PYDANTIC
# ===============================================================

class ClientFiscalDataRequest(BaseModel):
    """Datos fiscales de un cliente"""
    rfc: str
    razon_social: str
    domicilio_fiscal: str
    regimen_fiscal: str = "601"
    email: EmailStr
    telefono: Optional[str] = None
    codigo_postal: str = ""
    extra_data: Optional[Dict[str, Any]] = {}

    @validator('rfc')
    def validate_rfc(cls, v):
        import re
        rfc_pattern = r'^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$'
        if not re.match(rfc_pattern, v.upper()):
            raise ValueError('RFC con formato inválido')
        return v.upper()


class MerchantCredentialsRequest(BaseModel):
    """Credenciales para un portal"""
    merchant_name: str
    portal_url: str
    username: str
    password: str
    additional_data: Optional[Dict[str, str]] = {}


class InvoiceRequest(BaseModel):
    """Solicitud de facturación"""
    client_id: str
    merchant_name: str
    ticket_data: Dict[str, Any]
    fiscal_data_override: Optional[Dict[str, str]] = None


# ===============================================================
# ENDPOINTS DE GESTIÓN DE CLIENTES
# ===============================================================

@router.post("/setup")
async def setup_client(
    client_data: ClientFiscalDataRequest,
    client_id: Optional[str] = None
):
    """Configura un nuevo cliente con sus datos fiscales"""

    if not client_id:
        client_id = str(uuid.uuid4())

    try:
        result = await setup_new_client(
            client_id=client_id,
            rfc=client_data.rfc,
            razon_social=client_data.razon_social,
            email=client_data.email,
            domicilio_fiscal=client_data.domicilio_fiscal,
            regimen_fiscal=client_data.regimen_fiscal,
            telefono=client_data.telefono,
            codigo_postal=client_data.codigo_postal
        )

        if result["success"]:
            return {
                "success": True,
                "client_id": client_id,
                "message": "Cliente configurado exitosamente",
                "next_steps": [
                    "Configurar credenciales de portales",
                    "Realizar primera facturación de prueba"
                ]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error configurando cliente"
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error: {str(e)}"
        )


@router.get("/{client_id}")
async def get_client_info(client_id: str):
    """Obtiene información completa de un cliente"""

    try:
        manager = get_credential_manager()
        client_summary = await manager.get_client_summary(client_id)

        if not client_summary["fiscal_data"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cliente {client_id} no encontrado"
            )

        return {
            "success": True,
            "client": client_summary
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo información del cliente: {str(e)}"
        )


@router.put("/{client_id}/fiscal-data")
async def update_client_fiscal_data(
    client_id: str,
    fiscal_data: ClientFiscalDataRequest
):
    """Actualiza los datos fiscales de un cliente"""

    try:
        manager = get_credential_manager()

        client_fiscal_data = ClientFiscalData(
            client_id=client_id,
            rfc=fiscal_data.rfc,
            razon_social=fiscal_data.razon_social,
            domicilio_fiscal=fiscal_data.domicilio_fiscal,
            regimen_fiscal=fiscal_data.regimen_fiscal,
            email=fiscal_data.email,
            telefono=fiscal_data.telefono,
            codigo_postal=fiscal_data.codigo_postal,
            extra_data=fiscal_data.extra_data or {}
        )

        success = await manager.store_client_fiscal_data(client_id, client_fiscal_data)

        if success:
            return {
                "success": True,
                "message": "Datos fiscales actualizados exitosamente"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error actualizando datos fiscales"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error: {str(e)}"
        )


# ===============================================================
# ENDPOINTS DE CREDENCIALES DE PORTALES
# ===============================================================

@router.post("/{client_id}/portals/{merchant_name}/credentials")
async def setup_portal_credentials(
    client_id: str,
    merchant_name: str,
    credentials: MerchantCredentialsRequest
):
    """Configura credenciales de un cliente para un portal específico"""

    try:
        manager = get_credential_manager()

        # Verificar que el cliente exista
        fiscal_data = await manager.get_client_fiscal_data(client_id)
        if not fiscal_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cliente {client_id} no encontrado"
            )

        merchant_creds = MerchantCredentials(
            merchant_name=credentials.merchant_name,
            portal_url=credentials.portal_url,
            username=credentials.username,
            password=credentials.password,
            additional_data=credentials.additional_data or {}
        )

        success = await manager.store_merchant_credentials(
            client_id, merchant_name, merchant_creds
        )

        if success:
            return {
                "success": True,
                "message": f"Credenciales configuradas para {merchant_name}",
                "portal_status": "ready_for_automation"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error almacenando credenciales"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error: {str(e)}"
        )


@router.get("/{client_id}/portals")
async def list_client_portals(client_id: str):
    """Lista todos los portales configurados para un cliente"""

    try:
        manager = get_credential_manager()
        portals = await manager.list_client_portals(client_id)

        return {
            "success": True,
            "client_id": client_id,
            "total_portals": len(portals),
            "portals": portals
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@router.get("/{client_id}/portals/{merchant_name}/status")
async def check_portal_status(client_id: str, merchant_name: str):
    """Verifica el estado de configuración de un portal"""

    try:
        manager = get_credential_manager()

        credentials = await manager.get_merchant_credentials(client_id, merchant_name)

        if not credentials:
            return {
                "success": True,
                "portal_configured": False,
                "status": "not_configured",
                "message": f"Cliente no tiene credenciales para {merchant_name}",
                "next_action": "setup_credentials"
            }

        return {
            "success": True,
            "portal_configured": True,
            "status": credentials.account_status,
            "needs_registration": credentials.needs_registration,
            "last_login": credentials.last_login.isoformat() if credentials.last_login else None,
            "portal_url": credentials.portal_url
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


# ===============================================================
# ENDPOINT DE FACTURACIÓN INTELIGENTE
# ===============================================================

@router.post("/{client_id}/invoice")
async def create_invoice_with_context(
    client_id: str,
    invoice_request: InvoiceRequest
):
    """
    Crea una factura automáticamente usando el contexto completo del cliente.
    Este endpoint prepara TODA la información necesaria para la automatización.
    """

    try:
        manager = get_credential_manager()

        # Preparar contexto completo para automatización
        session_context = await manager.prepare_portal_session(
            client_id=client_id,
            merchant_name=invoice_request.merchant_name,
            ticket_data=invoice_request.ticket_data
        )

        # Si hay override de datos fiscales, aplicarlos
        if invoice_request.fiscal_data_override:
            session_context["fiscal_data"].update(invoice_request.fiscal_data_override)

        # Aquí normalmente llamarías al sistema de automatización
        # Por ahora retornamos el contexto preparado

        return {
            "success": True,
            "message": "Contexto de facturación preparado",
            "client_id": client_id,
            "merchant": invoice_request.merchant_name,
            "ready_for_automation": True,
            "session_context": {
                "has_fiscal_data": bool(session_context["fiscal_data"]),
                "has_credentials": bool(session_context["portal_credentials"]),
                "portal_url": session_context["portal_credentials"]["url"],
                "account_status": session_context["session_config"]["account_status"]
            },
            "next_step": "start_automation_job"
        }

    except ValueError as e:
        # Error de configuración (cliente sin datos, etc.)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error preparando facturación: {str(e)}"
        )


# ===============================================================
# ENDPOINTS DE CONFIGURACIÓN MASIVA
# ===============================================================

@router.post("/batch-setup")
async def batch_setup_clients(clients_data: List[ClientFiscalDataRequest]):
    """Configura múltiples clientes de forma masiva"""

    results = []

    for client_data in clients_data:
        try:
            client_id = str(uuid.uuid4())
            result = await setup_new_client(
                client_id=client_id,
                rfc=client_data.rfc,
                razon_social=client_data.razon_social,
                email=client_data.email,
                domicilio_fiscal=client_data.domicilio_fiscal,
                regimen_fiscal=client_data.regimen_fiscal,
                telefono=client_data.telefono,
                codigo_postal=client_data.codigo_postal
            )

            results.append({
                "rfc": client_data.rfc,
                "client_id": client_id,
                "success": result["success"],
                "message": result["message"]
            })

        except Exception as e:
            results.append({
                "rfc": client_data.rfc,
                "client_id": None,
                "success": False,
                "message": f"Error: {str(e)}"
            })

    successful = sum(1 for r in results if r["success"])
    total = len(results)

    return {
        "success": True,
        "total_processed": total,
        "successful": successful,
        "failed": total - successful,
        "results": results
    }


@router.get("/")
async def list_all_clients():
    """Lista todos los clientes configurados (para desarrollo)"""

    # En una implementación real, esto vendría de la base de datos
    # Por ahora retornamos un placeholder

    return {
        "success": True,
        "message": "Funcionalidad en desarrollo",
        "note": "En producción, esto listará todos los clientes desde la base de datos"
    }


# ===============================================================
# HEALTH CHECK
# ===============================================================

@router.get("/health")
async def health_check():
    """Verifica el estado del sistema de gestión de clientes"""

    try:
        manager = get_credential_manager()

        # Verificar conexión con vault
        vault_status = await manager.vault.health_check()

        return {
            "status": "healthy",
            "vault_connection": vault_status,
            "timestamp": datetime.now().isoformat(),
            "services": {
                "credential_manager": "operational",
                "fiscal_data_storage": "operational",
                "portal_credentials": "operational"
            }
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }