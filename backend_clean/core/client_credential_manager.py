"""
Sistema de Gestión de Credenciales por Cliente
Maneja credenciales, datos fiscales y configuración de portales por cliente.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .security_vault import get_security_vault

logger = logging.getLogger(__name__)


@dataclass
class ClientFiscalData:
    """Datos fiscales del cliente"""
    client_id: str
    rfc: str
    razon_social: str
    domicilio_fiscal: str
    regimen_fiscal: str
    email: str
    telefono: Optional[str] = None
    codigo_postal: str = ""
    # Datos adicionales por mercado
    extra_data: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}


@dataclass
class MerchantCredentials:
    """Credenciales para un portal específico"""
    merchant_name: str
    portal_url: str
    username: str
    password: str
    # Credenciales adicionales (API keys, tokens, etc.)
    additional_data: Dict[str, str] = None

    # Estado de la cuenta
    account_status: str = "active"  # active, inactive, requires_setup
    last_login: Optional[datetime] = None
    needs_registration: bool = False

    def __post_init__(self):
        if self.additional_data is None:
            self.additional_data = {}


class ClientCredentialManager:
    """
    Gestor de credenciales y datos fiscales por cliente.
    Permite al sistema saber qué credenciales usar para cada cliente en cada portal.
    """

    def __init__(self, vault_instance=None):
        self.vault = vault_instance or get_security_vault()
        self._client_cache = {}

    # ===============================================================
    # GESTIÓN DE DATOS FISCALES
    # ===============================================================

    async def store_client_fiscal_data(
        self,
        client_id: str,
        fiscal_data: ClientFiscalData
    ) -> bool:
        """Almacena los datos fiscales de un cliente"""

        try:
            # Validar RFC
            if not self._validate_rfc(fiscal_data.rfc):
                raise ValueError(f"RFC inválido: {fiscal_data.rfc}")

            # Almacenar en vault seguro
            vault_key = f"client_fiscal_{client_id}"
            fiscal_dict = {
                "rfc": fiscal_data.rfc,
                "razon_social": fiscal_data.razon_social,
                "domicilio_fiscal": fiscal_data.domicilio_fiscal,
                "regimen_fiscal": fiscal_data.regimen_fiscal,
                "email": fiscal_data.email,
                "telefono": fiscal_data.telefono,
                "codigo_postal": fiscal_data.codigo_postal,
                "extra_data": fiscal_data.extra_data,
                "updated_at": datetime.now().isoformat()
            }

            success = await self.vault.store_credentials(vault_key, fiscal_dict)

            if success:
                # Limpiar cache
                self._client_cache.pop(client_id, None)
                logger.info(f"Datos fiscales almacenados para cliente {client_id}")

            return success

        except Exception as e:
            logger.error(f"Error almacenando datos fiscales: {e}")
            return False

    async def get_client_fiscal_data(self, client_id: str) -> Optional[ClientFiscalData]:
        """Obtiene los datos fiscales de un cliente"""

        try:
            # Verificar cache
            if client_id in self._client_cache:
                return self._client_cache[client_id]["fiscal_data"]

            vault_key = f"client_fiscal_{client_id}"
            fiscal_dict = await self.vault.retrieve_credentials(vault_key)

            if not fiscal_dict:
                logger.warning(f"No se encontraron datos fiscales para cliente {client_id}")
                return None

            fiscal_data = ClientFiscalData(
                client_id=client_id,
                rfc=fiscal_dict["rfc"],
                razon_social=fiscal_dict["razon_social"],
                domicilio_fiscal=fiscal_dict["domicilio_fiscal"],
                regimen_fiscal=fiscal_dict["regimen_fiscal"],
                email=fiscal_dict["email"],
                telefono=fiscal_dict.get("telefono"),
                codigo_postal=fiscal_dict.get("codigo_postal", ""),
                extra_data=fiscal_dict.get("extra_data", {})
            )

            # Cache para siguiente uso
            if client_id not in self._client_cache:
                self._client_cache[client_id] = {}
            self._client_cache[client_id]["fiscal_data"] = fiscal_data

            return fiscal_data

        except Exception as e:
            logger.error(f"Error obteniendo datos fiscales: {e}")
            return None

    # ===============================================================
    # GESTIÓN DE CREDENCIALES DE PORTALES
    # ===============================================================

    async def store_merchant_credentials(
        self,
        client_id: str,
        merchant_name: str,
        credentials: MerchantCredentials
    ) -> bool:
        """Almacena credenciales de un cliente para un portal específico"""

        try:
            vault_key = f"client_merchant_{client_id}_{merchant_name.lower()}"

            creds_dict = {
                "merchant_name": credentials.merchant_name,
                "portal_url": credentials.portal_url,
                "username": credentials.username,
                "password": credentials.password,
                "additional_data": credentials.additional_data,
                "account_status": credentials.account_status,
                "last_login": credentials.last_login.isoformat() if credentials.last_login else None,
                "needs_registration": credentials.needs_registration,
                "updated_at": datetime.now().isoformat()
            }

            success = await self.vault.store_credentials(vault_key, creds_dict)

            if success:
                logger.info(f"Credenciales almacenadas para {client_id} en {merchant_name}")
                # Limpiar cache
                cache_key = f"{client_id}_{merchant_name}"
                self._client_cache.pop(cache_key, None)

            return success

        except Exception as e:
            logger.error(f"Error almacenando credenciales: {e}")
            return False

    async def get_merchant_credentials(
        self,
        client_id: str,
        merchant_name: str
    ) -> Optional[MerchantCredentials]:
        """Obtiene las credenciales de un cliente para un portal"""

        try:
            vault_key = f"client_merchant_{client_id}_{merchant_name.lower()}"
            creds_dict = await self.vault.retrieve_credentials(vault_key)

            if not creds_dict:
                logger.warning(f"No se encontraron credenciales para {client_id} en {merchant_name}")
                return None

            credentials = MerchantCredentials(
                merchant_name=creds_dict["merchant_name"],
                portal_url=creds_dict["portal_url"],
                username=creds_dict["username"],
                password=creds_dict["password"],
                additional_data=creds_dict.get("additional_data", {}),
                account_status=creds_dict.get("account_status", "active"),
                last_login=datetime.fromisoformat(creds_dict["last_login"]) if creds_dict.get("last_login") else None,
                needs_registration=creds_dict.get("needs_registration", False)
            )

            return credentials

        except Exception as e:
            logger.error(f"Error obteniendo credenciales: {e}")
            return None

    # ===============================================================
    # FLUJO INTELIGENTE DE AUTENTICACIÓN
    # ===============================================================

    async def prepare_portal_session(
        self,
        client_id: str,
        merchant_name: str,
        ticket_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepara toda la información necesaria para entrar a un portal:
        - Datos fiscales del cliente
        - Credenciales del portal
        - Configuración específica
        """

        try:
            # 1. Obtener datos fiscales del cliente
            fiscal_data = await self.get_client_fiscal_data(client_id)
            if not fiscal_data:
                raise ValueError(f"Cliente {client_id} no tiene datos fiscales configurados")

            # 2. Obtener credenciales para el portal
            credentials = await self.get_merchant_credentials(client_id, merchant_name)

            # 3. Si no hay credenciales, verificar si necesita registro
            if not credentials:
                logger.warning(f"Cliente {client_id} no tiene credenciales para {merchant_name}")

                # Verificar si el merchant requiere registro automático
                portal_config = await self._get_merchant_config(merchant_name)

                if portal_config.get("auto_registration", False):
                    logger.info(f"Iniciando registro automático para {client_id} en {merchant_name}")
                    credentials = await self._auto_register_client(
                        client_id, merchant_name, fiscal_data, portal_config
                    )
                else:
                    raise ValueError(f"Cliente requiere configuración manual para {merchant_name}")

            # 4. Preparar contexto completo
            session_context = {
                "client_id": client_id,
                "merchant_name": merchant_name,
                "fiscal_data": {
                    "rfc": fiscal_data.rfc,
                    "razon_social": fiscal_data.razon_social,
                    "email": fiscal_data.email,
                    "domicilio_fiscal": fiscal_data.domicilio_fiscal,
                    "regimen_fiscal": fiscal_data.regimen_fiscal,
                    "codigo_postal": fiscal_data.codigo_postal
                },
                "portal_credentials": {
                    "url": credentials.portal_url,
                    "username": credentials.username,
                    "password": credentials.password,
                    "additional_data": credentials.additional_data
                },
                "ticket_data": ticket_data,
                "session_config": {
                    "needs_registration": credentials.needs_registration,
                    "account_status": credentials.account_status,
                    "last_login": credentials.last_login.isoformat() if credentials.last_login else None
                }
            }

            logger.info(f"Contexto de portal preparado para {client_id} en {merchant_name}")
            return session_context

        except Exception as e:
            logger.error(f"Error preparando sesión de portal: {e}")
            raise

    # ===============================================================
    # REGISTRO AUTOMÁTICO
    # ===============================================================

    async def _auto_register_client(
        self,
        client_id: str,
        merchant_name: str,
        fiscal_data: ClientFiscalData,
        portal_config: Dict[str, Any]
    ) -> MerchantCredentials:
        """Registra automáticamente a un cliente en un portal"""

        try:
            logger.info(f"Iniciando registro automático para {client_id} en {merchant_name}")

            # Generar credenciales automáticas
            auto_username = fiscal_data.rfc.lower()
            auto_password = self._generate_secure_password()

            # Crear credenciales temporales
            temp_credentials = MerchantCredentials(
                merchant_name=merchant_name,
                portal_url=portal_config["portal_url"],
                username=auto_username,
                password=auto_password,
                needs_registration=True,
                account_status="pending_registration"
            )

            # Almacenar credenciales temporales
            await self.store_merchant_credentials(client_id, merchant_name, temp_credentials)

            logger.info(f"Credenciales temporales creadas para registro automático")
            return temp_credentials

        except Exception as e:
            logger.error(f"Error en registro automático: {e}")
            raise

    # ===============================================================
    # UTILIDADES
    # ===============================================================

    def _validate_rfc(self, rfc: str) -> bool:
        """Valida formato de RFC mexicano"""
        import re

        # RFC Persona Física: AAAA######AAA
        # RFC Persona Moral: AAA######AAA
        rfc_pattern = r'^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$'
        return bool(re.match(rfc_pattern, rfc.upper()))

    def _generate_secure_password(self) -> str:
        """Genera una contraseña segura"""
        import secrets
        import string

        chars = string.ascii_letters + string.digits + "!@#$%"
        return ''.join(secrets.choice(chars) for _ in range(12))

    async def _get_merchant_config(self, merchant_name: str) -> Dict[str, Any]:
        """Obtiene configuración de un merchant"""

        # Configuraciones predefinidas
        merchant_configs = {
            "oxxo": {
                "portal_url": "https://factura.oxxo.com",
                "auto_registration": True,
                "registration_fields": ["rfc", "email", "razon_social"]
            },
            "walmart": {
                "portal_url": "https://factura.walmart.com.mx",
                "auto_registration": True,
                "registration_fields": ["rfc", "email", "telefono"]
            },
            "costco": {
                "portal_url": "https://facturaelectronica.costco.com.mx",
                "auto_registration": False,
                "registration_fields": ["rfc", "email", "membership_number"]
            }
        }

        return merchant_configs.get(merchant_name.lower(), {
            "portal_url": "",
            "auto_registration": False,
            "registration_fields": ["rfc", "email"]
        })

    # ===============================================================
    # GESTIÓN DE MÚLTIPLES CLIENTES
    # ===============================================================

    async def list_client_portals(self, client_id: str) -> List[Dict[str, Any]]:
        """Lista todos los portales configurados para un cliente"""

        # En una implementación real, esto vendría de la base de datos
        # Por ahora simulamos con vault keys

        portals = []
        merchants = ["oxxo", "walmart", "costco", "7eleven", "soriana"]

        for merchant in merchants:
            credentials = await self.get_merchant_credentials(client_id, merchant)
            if credentials:
                portals.append({
                    "merchant_name": merchant,
                    "portal_url": credentials.portal_url,
                    "account_status": credentials.account_status,
                    "last_login": credentials.last_login.isoformat() if credentials.last_login else None,
                    "needs_setup": credentials.needs_registration
                })

        return portals

    async def get_client_summary(self, client_id: str) -> Dict[str, Any]:
        """Obtiene resumen completo de un cliente"""

        fiscal_data = await self.get_client_fiscal_data(client_id)
        portals = await self.list_client_portals(client_id)

        return {
            "client_id": client_id,
            "fiscal_data": fiscal_data.__dict__ if fiscal_data else None,
            "configured_portals": len(portals),
            "portals": portals,
            "ready_for_automation": fiscal_data is not None and len(portals) > 0
        }


# ===============================================================
# INSTANCIA GLOBAL
# ===============================================================

_credential_manager = None

def get_credential_manager() -> ClientCredentialManager:
    """Obtiene la instancia global del gestor de credenciales"""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = ClientCredentialManager()
    return _credential_manager


# ===============================================================
# FUNCIONES DE UTILIDAD
# ===============================================================

async def setup_new_client(
    client_id: str,
    rfc: str,
    razon_social: str,
    email: str,
    **kwargs
) -> Dict[str, Any]:
    """Configura un nuevo cliente con datos mínimos"""

    manager = get_credential_manager()

    fiscal_data = ClientFiscalData(
        client_id=client_id,
        rfc=rfc,
        razon_social=razon_social,
        email=email,
        domicilio_fiscal=kwargs.get("domicilio_fiscal", ""),
        regimen_fiscal=kwargs.get("regimen_fiscal", "601"),
        telefono=kwargs.get("telefono"),
        codigo_postal=kwargs.get("codigo_postal", "")
    )

    success = await manager.store_client_fiscal_data(client_id, fiscal_data)

    return {
        "success": success,
        "client_id": client_id,
        "message": "Cliente configurado exitosamente" if success else "Error configurando cliente"
    }


if __name__ == "__main__":
    # Ejemplo de uso
    async def test_credential_manager():
        manager = ClientCredentialManager()

        # Configurar cliente
        client_id = "empresa_abc_123"
        fiscal_data = ClientFiscalData(
            client_id=client_id,
            rfc="EMP850315ABC",
            razon_social="Empresa ABC SA de CV",
            email="facturacion@empresa-abc.com",
            domicilio_fiscal="Calle Principal 123, Col. Centro",
            regimen_fiscal="601"
        )

        await manager.store_client_fiscal_data(client_id, fiscal_data)

        # Configurar credenciales para OXXO
        oxxo_creds = MerchantCredentials(
            merchant_name="OXXO",
            portal_url="https://factura.oxxo.com",
            username="emp850315abc",
            password="mi_password_seguro"
        )

        await manager.store_merchant_credentials(client_id, "OXXO", oxxo_creds)

        # Preparar sesión para automatización
        ticket_data = {"folio": "123456", "total": 150.75}
        session_context = await manager.prepare_portal_session(client_id, "OXXO", ticket_data)

        print("Contexto de sesión preparado:")
        print(json.dumps(session_context, indent=2))

    # asyncio.run(test_credential_manager())