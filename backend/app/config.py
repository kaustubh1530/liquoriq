"""
config.py — LiquorIQ application settings

Uses pydantic-settings to load from .env automatically.
Every setting has a sane default for local dev; production
values are injected via real environment variables.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "LiquorIQ"
    app_env: str = "development"
    debug: bool = True

    # ── CORS (production) ─────────────────────────────────────────────────────
    # Set to the deployed frontend origin, e.g. https://liquoriq.vercel.app
    frontend_url: str = ""

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/liquoriq"

    @field_validator("database_url")
    @classmethod
    def _force_asyncpg_driver(cls, v: str) -> str:
        """
        Railway (and most PaaS) inject DATABASE_URL as plain postgresql://
        SQLAlchemy would then use the sync psycopg2 driver and crash our
        async engine. Rewrite the scheme so asyncpg is always used.
        """
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):  # legacy Heroku-style scheme
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_image_model: str = "gpt-image-1"   # successor to DALL-E 3; always returns b64

    # ── Ad creatives ──────────────────────────────────────────────────────────
    creatives_dir: str = "generated_images"   # DALL-E PNGs saved here, served at /static/creatives

    # ── File Uploads ──────────────────────────────────────────────────────────
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20

    # ── Email (Gmail SMTP) ────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""           # your-gmail@gmail.com
    smtp_password: str = ""       # Gmail App Password (16 chars, no spaces)
    from_email: str = ""          # same as smtp_user usually

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
