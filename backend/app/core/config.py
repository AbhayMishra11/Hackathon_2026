import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cold Storage Monitoring & Alert System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings (PostgreSQL System of Record)
    # Production: e.g., postgresql+asyncpg://postgres:password@localhost:5432/coldstorage_db
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./cold_storage.db"
    )
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL",
        "sqlite:///./cold_storage.db"
    )
    
    # Redis Settings (In-Memory Live Cache, Pub/Sub, Alert Debouncing)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ENABLE_REDIS: bool = os.getenv("ENABLE_REDIS", "true").lower() == "true"
    REDIS_METRICS_TTL_SECONDS: int = 15  # Cache TTL for live zone telemetry
    
    # CORS Origins for Frontend
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*"
    ]
    
    # SMS Chef Gateway Configuration (Free SMS using Android phone & SIM card)
    SMSCHEF_API_URL: str = os.getenv("SMSCHEF_API_URL", "https://www.cloud.smschef.com/api/send/sms")
    SMSCHEF_API_KEY: str = os.getenv("SMSCHEF_API_KEY", "") # Found under Tools -> API Keys
    SMSCHEF_DEVICE_ID: str = os.getenv("SMSCHEF_DEVICE_ID", "") # Device ID from SMS Chef Dashboard
    SMSCHEF_SIM_SLOT: int = int(os.getenv("SMSCHEF_SIM_SLOT", "1")) # 1 or 2
    
    # General alert settings
    ENABLE_SMS_SIMULATION: bool = True  # Fallback to rich console logging if SMS Chef keys are not yet configured
    ALERT_DEBOUNCE_MINUTES: int = 5
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
