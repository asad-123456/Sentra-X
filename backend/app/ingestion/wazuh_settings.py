"""Wazuh / ingestion settings. Separate from Asad's app/config.py so we never edit his file.
Reads the same backend/.env file (names are case-insensitive)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # backend/.env


class WazuhSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    WAZUH_INGEST_MODE: str = "replay"  # poll | webhook | replay
    WAZUH_POLL_INTERVAL_SECONDS: int = 30
    WAZUH_MIN_LEVEL: int = 4
    WAZUH_VERIFY_TLS: bool = False
    WAZUH_WEBHOOK_SECRET: str = ""
    WAZUH_INDEXER_URL: str = "https://localhost:9200"
    WAZUH_INDEXER_USER: str = "admin"
    WAZUH_INDEXER_PASSWORD: str = ""
    TRIAGE_WORKERS: int = 32


@lru_cache
def get_wazuh_settings() -> WazuhSettings:
    return WazuhSettings()
