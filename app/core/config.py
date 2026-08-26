from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Polyfollow - Polymarket Bandar Tracker"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./polyfollow.db"

    # Polymarket API Endpoints
    POLYMARKET_DATA_API_BASE: str = "https://data-api.polymarket.com"
    POLYMARKET_GAMMA_API_BASE: str = "https://gamma-api.polymarket.com"

    # Worker Settings
    POLLING_INTERVAL_SECONDS: int = 30
    ENABLE_BACKGROUND_POLLER: bool = True
    REQUEST_TIMEOUT_SECONDS: float = 15.0
    MAX_RETRIES: int = 3

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()
