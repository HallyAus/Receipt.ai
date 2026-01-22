"""Application configuration from environment variables."""
import secrets
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # App settings
    app_name: str = "Receipt.ai"
    debug: bool = False
    secret_key: str = secrets.token_urlsafe(32)

    # Encryption key for refresh tokens (32 bytes = 256 bits)
    encryption_key: str = secrets.token_urlsafe(32)

    # Database
    database_url: str = "postgresql+asyncpg://receipt:receipt@localhost:5432/receipt"
    database_url_sync: str = "postgresql://receipt:receipt@localhost:5432/receipt"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Server
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # Microsoft OAuth
    microsoft_client_id: Optional[str] = None
    microsoft_client_secret: Optional[str] = None
    microsoft_tenant_id: str = "common"  # 'common' for multi-tenant
    microsoft_redirect_uri: str = "http://localhost:8000/api/auth/microsoft/callback"

    # LLM (optional)
    openai_api_key: Optional[str] = None
    llm_enabled: bool = False

    # Storage
    attachment_storage_path: str = "/app/data/attachments"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
