"""Settings for the triage worker only (kept out of app/config.py)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ENV, extra="ignore", case_sensitive=False)

    LLM_PROVIDER: str = "mock"            # mock | gemini | claude | ollama
    TRIAGE_ENABLED: bool = True
    TRIAGE_WORKERS: int = 32
    TRIAGE_SWEEP_SECONDS: float = Field(default=5.0, gt=0)
    MOCK_DELAY_MIN_SECONDS: float = 0.0   # simulated LLM latency for AC-19/AC-22
    MOCK_DELAY_MAX_SECONDS: float = 0.0


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
