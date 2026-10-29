from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", case_sensitive=False
    )

    db_url: str = "postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax"

    wazuh_api_url: str = ""
    wazuh_api_user: str = ""
    wazuh_api_password: str = ""
    wazuh_poll_interval_seconds: int = 30
    wazuh_min_level: int = 4
    wazuh_verify_tls: bool = False
    wazuh_ingest_mode: str = "replay"  # poll | webhook | replay
    wazuh_webhook_secret: str = ""

    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 60
    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = "ChangeMe123!"

    triage_workers: int = 32


@lru_cache
def get_settings() -> Settings:
    return Settings()