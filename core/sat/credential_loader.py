"""
SAT Credential Loader
======================
Carga credenciales e.firma desde múltiples fuentes:
- file:// - Archivos locales
- inline: - Valores inline (para passwords)
- vault: - HashiCorp Vault (futuro)
"""

from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse


class CredentialLoader:
    """
    Carga credenciales SAT desde diferentes fuentes

    Soporta esquemas:
    - file:///path/to/file.cer  -> Lee archivo local
    - inline:password123        -> Retorna valor directo
    - vault:secret/path         -> Lee de Vault (futuro)
    """

    @staticmethod
    def load_credential(uri: str) -> bytes:
        """
        Carga una credencial desde un URI

        Args:
            uri: URI de la credencial (file://, inline:, vault:)

        Returns:
            Contenido de la credencial como bytes

        Raises:
            ValueError: Si el esquema no es soportado
            FileNotFoundError: Si el archivo no existe
        """
        if not uri:
            raise ValueError("URI vacío")

        parsed = urlparse(uri)
        scheme = parsed.scheme.lower() if parsed.scheme else 'inline'

        if scheme == 'file':
            # file:///path/to/file
            file_path = parsed.path
            if not file_path:
                raise ValueError(f"Path vacío en URI: {uri}")

            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

            return path.read_bytes()

        elif scheme == 'inline':
            # inline:valor o simplemente valor sin esquema
            value = uri.replace('inline:', '', 1)
            return value.encode('utf-8')

        elif scheme == 'vault':
            # vault:secret/path/key
            raise NotImplementedError(
                f"Vault integration not implemented yet. "
                f"For testing, use file:// or inline: schemes. "
                f"URI: {uri}"
            )

        else:
            raise ValueError(f"Esquema no soportado: {scheme}. Use file://, inline: o vault:")

    @staticmethod
    def load_efirma_credentials(
        cer_uri: str,
        key_uri: str,
        password_uri: str
    ) -> Tuple[bytes, bytes, str]:
        """
        Carga credenciales e.firma completas

        Args:
            cer_uri: URI del certificado (.cer)
            key_uri: URI de la llave privada (.key)
            password_uri: URI de la contraseña

        Returns:
            Tupla (cer_bytes, key_bytes, password_str)

        Example:
            cer, key, pwd = load_efirma_credentials(
                'file:///path/to/cert.cer',
                'file:///path/to/key.key',
                'inline:mypassword123'
            )
        """
        try:
            cer_bytes = CredentialLoader.load_credential(cer_uri)
            key_bytes = CredentialLoader.load_credential(key_uri)
            password_bytes = CredentialLoader.load_credential(password_uri)

            # Password siempre debe ser string
            password_str = password_bytes.decode('utf-8')

            return cer_bytes, key_bytes, password_str

        except Exception as e:
            raise ValueError(
                f"Error cargando credenciales e.firma: {e}\n"
                f"  CER: {cer_uri}\n"
                f"  KEY: {key_uri}\n"
                f"  PWD: {password_uri}"
            )
