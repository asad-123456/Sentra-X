from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax"
    )
    DATABASE_URL_ASYNC: str = (
        "postgresql+psycopg_async://sentrax:sentrax@localhost:5432/sentrax"
    )
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    LLM_PROVIDER: str = "gemini"
    DEMO_MODE: bool = True
    ALLOWED_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:4173"
    )
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""


# Singleton used throughout the application
settings = Settings()
