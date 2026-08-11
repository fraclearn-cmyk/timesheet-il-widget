from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str
    
    # amoCRM
    AMOCRM_CLIENT_ID: str
    AMOCRM_CLIENT_SECRET: str
    AMOCRM_REDIRECT_URI: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application
    POLLING_INTERVAL: int = 15
    INACTIVITY_TIMEOUT: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
