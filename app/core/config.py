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

    # Worker & Discovery Settings
    POLLING_INTERVAL_SECONDS: int = 30
    ENABLE_BACKGROUND_POLLER: bool = True
    ENABLE_AUTO_DISCOVERY: bool = True
    AUTO_DISCOVERY_INTERVAL_RUNS: int = 10
    REQUEST_TIMEOUT_SECONDS: float = 15.0
    MAX_RETRIES: int = 3

    # Security & Authentication
    API_KEY: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"

    # Outbound Webhook & Push Alerts (For Hermes AI Agent & Telegram)
    HERMES_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    MIN_ALERT_CONFIDENCE_SCORE: float = 75.0
    MIN_WHALE_TRADE_ALERT_USD: float = 5000.0


settings = Settings()
