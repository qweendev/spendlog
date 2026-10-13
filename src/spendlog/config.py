from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPENDLOG_", env_file=".env")

    bot_token: SecretStr
    database_url: str = "sqlite+aiosqlite:///data/spendlog.db"
    webapp_url: str | None = None
    host: str = "0.0.0.0"
    port: int = 8080
    default_timezone: str = "Europe/Moscow"
