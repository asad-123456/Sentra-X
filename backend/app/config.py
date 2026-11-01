from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+psycopg://sentrax:sentrax2026@localhost:5432/sentrax_db"
    )
    DATABASE_URL_ASYNC: str = (
        "postgresql+psycopg_async://sentrax:sentrax2026@localhost:5432/sentrax_db"
    )
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    LLM_PROVIDER: str = "gemini"
    DEMO_MODE: bool = True


# Singleton used throughout the application
settings = Settings()
