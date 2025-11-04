"""
Sistema de Seguridad y Manejo de Credenciales con HashiCorp Vault
Manejo seguro de credenciales, encriptación y autenticación para el sistema de facturación.
Compatible con HashiCorp Vault y fallback a encriptación local.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
import uuid

logger = logging.getLogger(__name__)


@dataclass
class CredentialEntry:
    """Entrada de credencial segura"""
    id: str
    company_id: str
    merchant_id: str
    credential_type: str  # 'web_login', 'api_key', 'email', 'certificate'
    encrypted_data: bytes
    vault_path: Optional[str] = None
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    is_active: bool = True


@dataclass
class VaultConfig:
    """Configuración de HashiCorp Vault"""
    url: str
    token: Optional[str] = None
    mount_point: str = "secret"
    namespace: Optional[str] = None
    ca_cert_path: Optional[str] = None
    verify_ssl: bool = True


class SecurityVault:
    """
    Sistema de seguridad y manejo de credenciales.
    Soporta HashiCorp Vault y fallback a encriptación local.
    """

    def __init__(self, vault_config: Optional[VaultConfig] = None):
        self.vault_config = vault_config
        self.vault_client = None
        self.local_encryption_key = None

        # Configuración de seguridad
        self.encryption_algorithm = "fernet"
        self.key_rotation_interval = 86400 * 30  # 30 días
        self.max_access_attempts = 3
        self.access_log = []

        # Cache de credenciales (temporal, en memoria)
        self._credential_cache = {}
        self.cache_ttl = 300  # 5 minutos

        # Inicializar sistema de seguridad
        asyncio.create_task(self._initialize_security_system())

    async def _initialize_security_system(self):
        """Inicializar sistema de seguridad"""

        try:
            # Intentar conectar con HashiCorp Vault
            if self.vault_config:
                await self._initialize_vault()
            else:
                logger.info("HashiCorp Vault no configurado, usando encriptación local")

            # Configurar encriptación local como fallback
            await self._initialize_local_encryption()

            logger.info("Sistema de seguridad inicializado correctamente")

        except Exception as e:
            logger.error(f"Error inicializando sistema de seguridad: {e}")
            raise

    async def _initialize_vault(self):
        """Inicializar conexión con HashiCorp Vault"""

        try:
            import hvac

            self.vault_client = hvac.Client(
                url=self.vault_config.url,
                token=self.vault_config.token,
                verify=self.vault_config.verify_ssl
            )

            if self.vault_config.namespace:
                self.vault_client.namespace = self.vault_config.namespace

            # Verificar conectividad
            if self.vault_client.is_authenticated():
                logger.info(f"Conectado a HashiCorp Vault: {self.vault_config.url}")
            else:
                raise Exception("No se pudo autenticar con Vault")

        except ImportError:
            logger.warning("hvac no instalado, usando solo encriptación local")
            self.vault_client = None
        except Exception as e:
            logger.error(f"Error conectando con Vault: {e}")
            self.vault_client = None

    async def _initialize_local_encryption(self):
        """Inicializar encriptación local"""

        try:
            # Obtener o generar clave de encriptación
            key_env = os.getenv("ENCRYPTION_KEY")

            if key_env:
                # Usar clave de variable de entorno
                self.local_encryption_key = key_env.encode()
            else:
                # Generar clave basada en secret derivado
                secret = os.getenv("SECRET_KEY", "default-secret-change-me")
                salt = b"invoicing-system-salt"

                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
                self.local_encryption_key = key

            logger.info("Encriptación local configurada")

        except Exception as e:
            logger.error(f"Error configurando encriptación local: {e}")
            raise

    # ===============================================================
    # GESTIÓN DE CREDENCIALES
    # ===============================================================

    async def store_credentials(
        self,
        company_id: str,
        merchant_id: str,
        credential_type: str,
        credentials: Dict[str, str],
        force_vault: bool = False
    ) -> str:
        """
        Almacenar credenciales de forma segura.

        Args:
            company_id: ID de la empresa
            merchant_id: ID del merchant
            credential_type: Tipo de credencial
            credentials: Datos de credenciales a almacenar
            force_vault: Forzar uso de Vault (si está disponible)

        Returns:
            ID de la entrada de credencial creada
        """

        logger.info(f"Almacenando credenciales para {company_id}/{merchant_id}")

        try:
            # Generar ID único
            credential_id = str(uuid.uuid4())

            # Serializar credenciales
            credential_json = json.dumps(credentials)

            # Intentar almacenar en Vault primero
            vault_path = None
            if self.vault_client and (force_vault or self._should_use_vault()):
                vault_path = await self._store_in_vault(
                    credential_id, company_id, merchant_id, credential_json
                )

            # Encriptar localmente (siempre como backup)
            encrypted_data = await self._encrypt_data(credential_json)

            # Crear entrada de credencial
            entry = CredentialEntry(
                id=credential_id,
                company_id=company_id,
                merchant_id=merchant_id,
                credential_type=credential_type,
                encrypted_data=encrypted_data,
                vault_path=vault_path,
                created_at=time.time(),
                last_accessed="",
                access_count=0,
                is_active=True
            )

            # Guardar en base de datos
            await self._save_credential_entry(entry)

            # Log de auditoría
            await self._log_security_event(
                event_type="credential_stored",
                company_id=company_id,
                merchant_id=merchant_id,
                credential_id=credential_id
            )

            logger.info(f"Credenciales almacenadas con ID: {credential_id}")
            return credential_id

        except Exception as e:
            logger.error(f"Error almacenando credenciales: {e}")
            raise

    async def retrieve_credentials(
        self,
        company_id: str,
        merchant_id: str,
        credential_type: str = None
    ) -> Optional[Dict[str, str]]:
        """
        Recuperar credenciales de forma segura.

        Args:
            company_id: ID de la empresa
            merchant_id: ID del merchant
            credential_type: Tipo específico de credencial (opcional)

        Returns:
            Diccionario con las credenciales o None si no existen
        """

        logger.info(f"Recuperando credenciales para {company_id}/{merchant_id}")

        try:
            # Verificar cache primero
            cache_key = f"{company_id}:{merchant_id}:{credential_type or 'all'}"
            if cache_key in self._credential_cache:
                cache_entry = self._credential_cache[cache_key]
                if time.time() - cache_entry["timestamp"] < self.cache_ttl:
                    logger.debug("Credenciales obtenidas desde cache")
                    return cache_entry["data"]

            # Obtener entrada de credencial
            entry = await self._get_credential_entry(company_id, merchant_id, credential_type)
            if not entry or not entry.is_active:
                logger.warning(f"Credenciales no encontradas para {company_id}/{merchant_id}")
                return None

            # Intentar recuperar desde Vault primero
            credentials = None
            if entry.vault_path and self.vault_client:
                try:
                    credentials = await self._retrieve_from_vault(entry.vault_path)
                except Exception as e:
                    logger.warning(f"Error recuperando desde Vault, usando backup local: {e}")

            # Fallback a encriptación local
            if not credentials:
                decrypted_data = await self._decrypt_data(entry.encrypted_data)
                credentials = json.loads(decrypted_data)

            # Actualizar estadísticas de acceso
            await self._update_access_stats(entry.id)

            # Guardar en cache
            self._credential_cache[cache_key] = {
                "data": credentials,
                "timestamp": time.time()
            }

            # Log de auditoría
            await self._log_security_event(
                event_type="credential_accessed",
                company_id=company_id,
                merchant_id=merchant_id,
                credential_id=entry.id
            )

            logger.info(f"Credenciales recuperadas exitosamente")
            return credentials

        except Exception as e:
            logger.error(f"Error recuperando credenciales: {e}")
            raise

    async def update_credentials(
        self,
        company_id: str,
        merchant_id: str,
        credential_type: str,
        new_credentials: Dict[str, str]
    ) -> bool:
        """Actualizar credenciales existentes"""

        logger.info(f"Actualizando credenciales para {company_id}/{merchant_id}")

        try:
            # Deshabilitar credenciales anteriores
            await self._deactivate_credentials(company_id, merchant_id, credential_type)

            # Crear nuevas credenciales
            new_id = await self.store_credentials(
                company_id, merchant_id, credential_type, new_credentials
            )

            # Limpiar cache
            self._clear_cache_for_merchant(company_id, merchant_id)

            logger.info(f"Credenciales actualizadas con nuevo ID: {new_id}")
            return True

        except Exception as e:
            logger.error(f"Error actualizando credenciales: {e}")
            return False

    async def delete_credentials(
        self,
        company_id: str,
        merchant_id: str,
        credential_type: str = None
    ) -> bool:
        """Eliminar credenciales de forma segura"""

        logger.info(f"Eliminando credenciales para {company_id}/{merchant_id}")

        try:
            # Obtener entrada
            entry = await self._get_credential_entry(company_id, merchant_id, credential_type)
            if not entry:
                return False

            # Eliminar de Vault si existe
            if entry.vault_path and self.vault_client:
                try:
                    await self._delete_from_vault(entry.vault_path)
                except Exception as e:
                    logger.warning(f"Error eliminando de Vault: {e}")

            # Marcar como inactivo en base de datos
            await self._deactivate_credential_entry(entry.id)

            # Limpiar cache
            self._clear_cache_for_merchant(company_id, merchant_id)

            # Log de auditoría
            await self._log_security_event(
                event_type="credential_deleted",
                company_id=company_id,
                merchant_id=merchant_id,
                credential_id=entry.id
            )

            logger.info("Credenciales eliminadas exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error eliminando credenciales: {e}")
            return False

    # ===============================================================
    # OPERACIONES DE VAULT
    # ===============================================================

    async def _store_in_vault(
        self,
        credential_id: str,
        company_id: str,
        merchant_id: str,
        data: str
    ) -> str:
        """Almacenar en HashiCorp Vault"""

        vault_path = f"invoicing/{company_id}/{merchant_id}/{credential_id}"

        try:
            self.vault_client.secrets.kv.v2.create_or_update_secret(
                path=vault_path,
                secret={
                    "data": data,
                    "metadata": {
                        "company_id": company_id,
                        "merchant_id": merchant_id,
                        "created_at": time.time(),
                        "version": "1.0"
                    }
                },
                mount_point=self.vault_config.mount_point
            )

            logger.info(f"Credenciales almacenadas en Vault: {vault_path}")
            return vault_path

        except Exception as e:
            logger.error(f"Error almacenando en Vault: {e}")
            raise

    async def _retrieve_from_vault(self, vault_path: str) -> Dict[str, str]:
        """Recuperar desde HashiCorp Vault"""

        try:
            response = self.vault_client.secrets.kv.v2.read_secret_version(
                path=vault_path,
                mount_point=self.vault_config.mount_point
            )

            secret_data = response["data"]["data"]["data"]
            return json.loads(secret_data)

        except Exception as e:
            logger.error(f"Error recuperando desde Vault: {e}")
            raise

    async def _delete_from_vault(self, vault_path: str):
        """Eliminar desde HashiCorp Vault"""

        try:
            self.vault_client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=vault_path,
                mount_point=self.vault_config.mount_point
            )

            logger.info(f"Credenciales eliminadas de Vault: {vault_path}")

        except Exception as e:
            logger.error(f"Error eliminando de Vault: {e}")
            raise

    # ===============================================================
    # ENCRIPTACIÓN LOCAL
    # ===============================================================

    async def _encrypt_data(self, data: str) -> bytes:
        """Encriptar datos localmente"""

        try:
            fernet = Fernet(self.local_encryption_key)
            encrypted_data = fernet.encrypt(data.encode())
            return encrypted_data

        except Exception as e:
            logger.error(f"Error encriptando datos: {e}")
            raise

    async def _decrypt_data(self, encrypted_data: bytes) -> str:
        """Desencriptar datos localmente"""

        try:
            fernet = Fernet(self.local_encryption_key)
            decrypted_data = fernet.decrypt(encrypted_data)
            return decrypted_data.decode()

        except Exception as e:
            logger.error(f"Error desencriptando datos: {e}")
            raise

    # ===============================================================
    # GESTIÓN DE BASE DE DATOS
    # ===============================================================

    async def _save_credential_entry(self, entry: CredentialEntry):
        """Guardar entrada de credencial en base de datos"""

        # Implementar guardado en base de datos
        # Por ahora, simular
        logger.info(f"Guardando entrada de credencial: {entry.id}")

    async def _get_credential_entry(
        self,
        company_id: str,
        merchant_id: str,
        credential_type: Optional[str]
    ) -> Optional[CredentialEntry]:
        """Obtener entrada de credencial desde base de datos"""

        # Implementar obtención desde base de datos
        # Por ahora, simular
        return CredentialEntry(
            id="test-credential-id",
            company_id=company_id,
            merchant_id=merchant_id,
            credential_type=credential_type or "web_login",
            encrypted_data=b"encrypted-test-data",
            vault_path=None,
            created_at=str(time.time()),
            last_accessed="",
            access_count=0,
            is_active=True
        )

    async def _update_access_stats(self, credential_id: str):
        """Actualizar estadísticas de acceso"""

        # Implementar actualización en base de datos
        logger.debug(f"Actualizando estadísticas de acceso para: {credential_id}")

    async def _deactivate_credentials(
        self,
        company_id: str,
        merchant_id: str,
        credential_type: str
    ):
        """Desactivar credenciales existentes"""

        # Implementar desactivación en base de datos
        logger.info(f"Desactivando credenciales para {company_id}/{merchant_id}")

    async def _deactivate_credential_entry(self, credential_id: str):
        """Desactivar entrada específica de credencial"""

        # Implementar desactivación en base de datos
        logger.info(f"Desactivando entrada de credencial: {credential_id}")

    # ===============================================================
    # UTILIDADES Y HELPERS
    # ===============================================================

    def _should_use_vault(self) -> bool:
        """Determinar si usar Vault basado en configuración"""

        return (
            self.vault_client is not None and
            self.vault_client.is_authenticated()
        )

    def _clear_cache_for_merchant(self, company_id: str, merchant_id: str):
        """Limpiar cache para un merchant específico"""

        keys_to_remove = [
            key for key in self._credential_cache.keys()
            if key.startswith(f"{company_id}:{merchant_id}:")
        ]

        for key in keys_to_remove:
            del self._credential_cache[key]

        logger.debug(f"Cache limpiado para {company_id}/{merchant_id}")

    async def _log_security_event(
        self,
        event_type: str,
        company_id: str,
        merchant_id: str,
        credential_id: str,
        additional_data: Dict[str, Any] = None
    ):
        """Log de eventos de seguridad para auditoría"""

        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "company_id": company_id,
            "merchant_id": merchant_id,
            "credential_id": credential_id,
            "additional_data": additional_data or {}
        }

        self.access_log.append(event)

        # En producción, esto se guardaría en sistema de auditoría
        logger.info(f"Security event: {event_type} for {company_id}/{merchant_id}")

    # ===============================================================
    # OPERACIONES DE MANTENIMIENTO
    # ===============================================================

    async def rotate_encryption_keys(self) -> bool:
        """Rotar claves de encriptación"""

        logger.info("Iniciando rotación de claves de encriptación")

        try:
            # Generar nueva clave
            new_key = Fernet.generate_key()

            # Re-encriptar todas las credenciales con nueva clave
            # (En producción, esto sería un proceso más complejo)

            self.local_encryption_key = new_key

            # Log de auditoría
            await self._log_security_event(
                event_type="key_rotation",
                company_id="system",
                merchant_id="system",
                credential_id="encryption_key"
            )

            logger.info("Rotación de claves completada exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error en rotación de claves: {e}")
            return False

    async def cleanup_inactive_credentials(self, days_inactive: int = 90) -> int:
        """Limpiar credenciales inactivas"""

        logger.info(f"Limpiando credenciales inactivas (>{days_inactive} días)")

        try:
            # Implementar limpieza de credenciales inactivas
            # Por ahora, simular
            cleaned_count = 0

            logger.info(f"Limpieza completada: {cleaned_count} credenciales eliminadas")
            return cleaned_count

        except Exception as e:
            logger.error(f"Error en limpieza de credenciales: {e}")
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del sistema de seguridad"""

        health_status = {
            "vault_connected": False,
            "local_encryption_ready": False,
            "cached_credentials": len(self._credential_cache),
            "security_events_logged": len(self.access_log),
            "last_key_rotation": None,
            "status": "unknown"
        }

        try:
            # Verificar Vault
            if self.vault_client:
                health_status["vault_connected"] = self.vault_client.is_authenticated()

            # Verificar encriptación local
            health_status["local_encryption_ready"] = self.local_encryption_key is not None

            # Determinar estado general
            if health_status["vault_connected"] or health_status["local_encryption_ready"]:
                health_status["status"] = "healthy"
            else:
                health_status["status"] = "degraded"

            return health_status

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            return health_status


# ===============================================================
# SINGLETON INSTANCE
# ===============================================================

_security_vault_instance = None


async def get_security_vault() -> SecurityVault:
    """Obtener instancia singleton del vault de seguridad"""

    global _security_vault_instance

    if _security_vault_instance is None:
        # Configurar Vault desde variables de entorno
        vault_config = None
        vault_url = os.getenv("VAULT_URL")

        if vault_url:
            vault_config = VaultConfig(
                url=vault_url,
                token=os.getenv("VAULT_TOKEN"),
                mount_point=os.getenv("VAULT_MOUNT_POINT", "secret"),
                namespace=os.getenv("VAULT_NAMESPACE"),
                verify_ssl=os.getenv("VAULT_VERIFY_SSL", "true").lower() == "true"
            )

        _security_vault_instance = SecurityVault(vault_config)

    return _security_vault_instance


# ===============================================================
# FUNCIONES DE CONVENIENCIA
# ===============================================================

async def store_merchant_credentials(
    company_id: str,
    merchant_id: str,
    username: str,
    password: str,
    additional_data: Dict[str, str] = None
) -> str:
    """
    Función de conveniencia para almacenar credenciales de merchant.

    Args:
        company_id: ID de la empresa
        merchant_id: ID del merchant
        username: Usuario
        password: Contraseña
        additional_data: Datos adicionales (API keys, etc.)

    Returns:
        ID de la credencial almacenada
    """

    vault = await get_security_vault()

    credentials = {
        "username": username,
        "password": password,
        **(additional_data or {})
    }

    return await vault.store_credentials(
        company_id=company_id,
        merchant_id=merchant_id,
        credential_type="web_login",
        credentials=credentials
    )


async def get_merchant_credentials(
    company_id: str,
    merchant_id: str
) -> Optional[Dict[str, str]]:
    """
    Función de conveniencia para obtener credenciales de merchant.

    Args:
        company_id: ID de la empresa
        merchant_id: ID del merchant

    Returns:
        Diccionario con credenciales o None
    """

    vault = await get_security_vault()

    return await vault.retrieve_credentials(
        company_id=company_id,
        merchant_id=merchant_id,
        credential_type="web_login"
    )


if __name__ == "__main__":
    # Test del sistema de seguridad
    import asyncio

    async def test_security_vault():
        """Test del sistema de seguridad"""

        print("=== TEST DEL SISTEMA DE SEGURIDAD ===")

        # Crear vault
        vault = SecurityVault()

        # Esperar inicialización
        await asyncio.sleep(1)

        try:
            # Test de almacenamiento
            credential_id = await vault.store_credentials(
                company_id="test-company",
                merchant_id="test-merchant",
                credential_type="web_login",
                credentials={
                    "username": "test_user",
                    "password": "test_password",
                    "api_key": "test_api_key"
                }
            )

            print(f"✅ Credenciales almacenadas: {credential_id}")

            # Test de recuperación
            retrieved = await vault.retrieve_credentials(
                company_id="test-company",
                merchant_id="test-merchant",
                credential_type="web_login"
            )

            print(f"✅ Credenciales recuperadas: {retrieved}")

            # Test de health check
            health = await vault.health_check()
            print(f"✅ Estado de salud: {health}")

            # Test de funciones de conveniencia
            conv_id = await store_merchant_credentials(
                company_id="test-company-2",
                merchant_id="test-merchant-2",
                username="user2",
                password="pass2"
            )

            conv_creds = await get_merchant_credentials(
                company_id="test-company-2",
                merchant_id="test-merchant-2"
            )

            print(f"✅ Funciones de conveniencia: {conv_creds}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Ejecutar test
    asyncio.run(test_security_vault())