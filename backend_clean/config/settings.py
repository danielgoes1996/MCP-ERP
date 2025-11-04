"""
Enhanced configuration using Pydantic Settings
Centralizes all environment variables and configuration
"""

from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with validation and defaults"""

    # Application
    APP_NAME: str = "MCP Server"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql://mcp_user:mcp_pass@localhost:5432/mcp_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_ECHO: bool = False

    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # OpenAI (optional)
    OPENAI_API_KEY: Optional[str] = None

    # Odoo (optional)
    ODOO_URL: Optional[str] = None
    ODOO_DB: Optional[str] = None
    ODOO_USERNAME: Optional[str] = None
    ODOO_PASSWORD: Optional[str] = None

    # Invoicing Agent
    COMPANY_RFC: str = "XAXX010101000"
    COMPANY_NAME: str = "Mi Empresa SA de CV"
    COMPANY_EMAIL: str = "facturacion@miempresa.com"
    COMPANY_PHONE: str = "5555555555"
    COMPANY_ZIP: str = "01000"

    # OCR
    OCR_BACKEND: str = "tesseract"  # tesseract, google, amazon
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # File Upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [".pdf", ".xml", ".jpg", ".jpeg", ".png"]

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_ENABLED: bool = True
    METRICS_PORT: int = 9090

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

        # Allow extra fields for backwards compatibility
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create global settings instance
settings = get_settings()

# Backwards compatibility with old config
class LegacyConfig:
    """Compatibility layer for old config.config imports"""

    @property
    def LOG_LEVEL(self):
        return settings.LOG_LEVEL

    @property
    def HOST(self):
        return settings.HOST

    @property
    def PORT(self):
        return settings.PORT

    @property
    def ODOO_URL(self):
        return settings.ODOO_URL

    @property
    def ODOO_DB(self):
        return settings.ODOO_DB

    @property
    def ODOO_USERNAME(self):
        return settings.ODOO_USERNAME

    @property
    def ODOO_PASSWORD(self):
        return settings.ODOO_PASSWORD

    @property
    def OPENAI_API_KEY(self):
        return settings.OPENAI_API_KEY


# Export for backwards compatibility
config = LegacyConfig()

if __name__ == "__main__":
    # Test configuration loading
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📦 Environment: {settings.ENVIRONMENT}")
    print(f"🗄️  Database: {settings.DATABASE_URL}")
    print(f"🔐 Secret Key: {'SET' if settings.SECRET_KEY != 'your-secret-key-change-this-in-production' else 'NOT SET'}")
    print(f"🌍 CORS Origins: {settings.CORS_ORIGINS}")