from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import secrets


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # App
    APP_NAME: str = "Timesheet IL API"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Database
    DATABASE_URL: str
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql://", "sqlite://", "mysql://")):
            raise ValueError("DATABASE_URL must start with postgresql://, sqlite://, or mysql://")
        return v
    
    # amoCRM
    AMOCRM_CLIENT_ID: str
    AMOCRM_CLIENT_SECRET: str
    AMOCRM_REDIRECT_URI: str
    
    @field_validator("AMOCRM_CLIENT_ID", "AMOCRM_CLIENT_SECRET")
    @classmethod
    def validate_amocrm_creds(cls, v: str) -> str:
        if not v or len(v) < 10:
            raise ValueError("AMOCRM credentials must be at least 10 characters")
        return v
    
    # Security
    SECRET_KEY: str
    
    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: List[str] = []
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v or []
    
    # Application
    POLLING_INTERVAL: int = 15
    INACTIVITY_TIMEOUT: int = 300
    
    # Rate limiting
    RATE_LIMIT_CALLS: int = 60
    RATE_LIMIT_PERIOD: int = 60
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()

# Dev auto-generate secret if needed
if settings.DEBUG and len(settings.SECRET_KEY) < 32:
    settings.SECRET_KEY = secrets.token_urlsafe(32)
    print(f"🔑 Generated dev secret key")

# Production checks
if not settings.DEBUG and settings.ENVIRONMENT == "production":
    if "change_this" in settings.SECRET_KEY.lower():
        raise ValueError("❌ SECRET_KEY must be changed in production!")
