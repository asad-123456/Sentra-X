"""Triage worker settings. Kept separate from Asad's app/config.py so we never edit his file.
Reads the same backend/.env file. TRIAGE_WORKERS (thread pool size) lives in app/ingestion/wazuh_settings.py."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # backend/.env


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    TRIAGE_ENABLED: bool = True
    TRIAGE_SWEEP_SECONDS: float = 5.0
    # Simulated model latency for the mock provider only (AC-19 / AC-22 load test uses 2 and 6).
    MOCK_DELAY_MIN_SECONDS: float = 0.0
    MOCK_DELAY_MAX_SECONDS: float = 0.0


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
