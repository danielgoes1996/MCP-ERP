"""
Configuration module for MCP Server
Handles environment variables and application settings using python-dotenv
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """
    Configuration class that centralizes all environment variables and settings.
    Uses dotenv to load credentials and configuration from .env file.
    """

    # Server configuration
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    # Internal persistence configuration
    DATA_DIR = Path(os.getenv("INTERNAL_DATA_DIR", BASE_DIR / "data"))
    INTERNAL_DB_PATH = Path(os.getenv("INTERNAL_DB_PATH", DATA_DIR / "mcp_internal.db"))
    UNIFIED_DB_PATH = Path(os.getenv("UNIFIED_DB_PATH", BASE_DIR / "unified_mcp_system.db"))
    DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "unified_mcp_system.db"))  # Alias for UNIFIED_DB_PATH
    USE_UNIFIED_DB = os.getenv("USE_UNIFIED_DB", "true").lower() == "true"
    USE_POSTGRESQL = os.getenv("USE_POSTGRESQL", "false").lower() == "true"
    POSTGRES_DSN = os.getenv("POSTGRES_DSN", "")

    # External system credentials (placeholders for now)
    # Odoo Configuration
    ODOO_URL = os.getenv("ODOO_URL", "https://your-odoo-instance.com")
    ODOO_DB = os.getenv("ODOO_DB", "your_database")
    ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "your_password")

    # ERP Configuration (generic)
    ERP_API_URL = os.getenv("ERP_API_URL", "https://your-erp-api.com")
    ERP_API_KEY = os.getenv("ERP_API_KEY", "your_api_key")
    ERP_API_SECRET = os.getenv("ERP_API_SECRET", "your_api_secret")

    # Banking API Configuration
    BANK_API_URL = os.getenv("BANK_API_URL", "https://bank-api.com")
    BANK_API_KEY = os.getenv("BANK_API_KEY", "your_bank_api_key")
    BANK_CERT_PATH = os.getenv("BANK_CERT_PATH", "/path/to/certificate.pem")

    # OpenAI Configuration for Voice Processing
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Logging configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "mcp_server.log")

    # Request timeout settings
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

    @classmethod
    def get_connector_config(cls, connector_type: str) -> dict:
        """
        Get configuration for specific connector type.

        Args:
            connector_type (str): Type of connector ('odoo', 'erp', 'bank', etc.)

        Returns:
            dict: Configuration dictionary for the specified connector
        """
        configs = {
            "odoo": {
                "url": cls.ODOO_URL,
                "database": cls.ODOO_DB,
                "username": cls.ODOO_USERNAME,
                "password": cls.ODOO_PASSWORD,
            },
            "erp": {
                "api_url": cls.ERP_API_URL,
                "api_key": cls.ERP_API_KEY,
                "api_secret": cls.ERP_API_SECRET,
            },
            "bank": {
                "api_url": cls.BANK_API_URL,
                "api_key": cls.BANK_API_KEY,
                "cert_path": cls.BANK_CERT_PATH,
            },
            "openai": {
                "api_key": cls.OPENAI_API_KEY,
            }
        }

        return configs.get(connector_type, {})


# Create global config instance
config = Config()
