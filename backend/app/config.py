"""
config.py — LiquorIQ application settings

Uses pydantic-settings to load from .env automatically.
Every setting has a sane default for local dev; production
values are injected via real environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "LiquorIQ"
    app_env: str = "development"
    debug: bool = True

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/liquoriq"

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # ── File Uploads ──────────────────────────────────────────────────────────
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Cached singleton — call get_settings() anywhere in the app.
    The @lru_cache means .env is only read once on startup.
    """
    return Settings()