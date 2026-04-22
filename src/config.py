"""
Application configuration loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram
    telegram_bot_token: str
    telegram_allowed_user_id: int

    # Valorant
    valorant_region: str = "ap"
    valorant_shard: str = "ap"

    # Polling
    poll_interval: int = 2


settings = Settings()
