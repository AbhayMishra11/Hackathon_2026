import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Explicitly load backend/.env based on file location
_backend_dir = Path(__file__).resolve().parents[2]
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cold Storage Monitoring & Alert System"
    PROJECT_NAME: str = "Solar-Powered Smart Mini Cold Storage System (NER)"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings (PostgreSQL or SQLite fallback)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./cold_storage.db")
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL",
        "sqlite:///./cold_storage.db"
    )
    
    # Redis Settings (In-Memory Live Cache, Pub/Sub, Alert Debouncing)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ENABLE_REDIS: bool = os.getenv("ENABLE_REDIS", "false").lower() == "true"
    REDIS_METRICS_TTL_SECONDS: int = 15  # Cache TTL for live zone telemetry
    
    # CORS Origins for Frontend
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ]
    CORS_ORIGIN_REGEX: str = r"https://.*\.vercel\.app"
    DEVICE_API_KEYS: List[str] = [key for key in os.getenv("DEVICE_API_KEYS", "").split(",") if key]
    
    # Farmer Contact Settings (Configurable via .env)
    FARMER_1_NAME: str = os.getenv("FARMER_1_NAME", "Ramesh Patel")
    FARMER_1_PHONE: str = os.getenv("FARMER_1_PHONE", "+919876543210")
    FARMER_1_CHANNEL: str = os.getenv("FARMER_1_CHANNEL", "SMS")
    
    FARMER_2_NAME: str = os.getenv("FARMER_2_NAME", "Suresh Kumar")
    FARMER_2_PHONE: str = os.getenv("FARMER_2_PHONE", "+919812345678")
    FARMER_2_CHANNEL: str = os.getenv("FARMER_2_CHANNEL", "WHATSAPP")
    
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
        env_file = str(_env_path) if _env_path.exists() else ".env"

settings = Settings()

