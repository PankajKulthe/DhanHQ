from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dhan Options Trading Platform"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@postgres:5432/trading")
    redis_url: str = Field(default="redis://redis:6379/0")
    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    app_access_password: str = ""
    app_session_cookie: str = "app_session"
    app_session_minutes: int = 720
    credential_key: str = Field(default="change-me-32-byte-fernet-key")
    dhan_client_id: str = ""
    dhan_access_token: str = ""
    dhan_totp_secret: str = ""
    live_trading_enabled: bool = False
    default_capital: float = 500000
    max_daily_loss: float = 12000
    max_trades_per_day: int = 6
    max_capital_exposure: float = 0.35
    order_rate_limit_per_second: int = 9
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
