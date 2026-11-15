from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import Float, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SystemConfiguration(Base):
    """Platform system configuration entity.
    
    Persisted to PostgreSQL to ensure thread-safety and state consistency
    across multi-worker ASGI processes (uvicorn --workers N) and container replicas.
    """

    __tablename__ = "system_configurations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    wazuh_endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'https://wazuh-master.sentrax.internal:55000'"),
    )
    wazuh_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'CONNECTED'"),
    )
    polling_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("30"),
    )
    min_rule_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("4"),
    )
    llm_provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'Gemini'"),
    )
    model_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'gemini-3.1-flash-lite'"),
    )
    abstention_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.6"),
    )
    max_exemplars_injected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("2"),
    )
    last_sync_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration entity to API/Frontend matching contract dictionary."""
        sync_ts = self.last_sync_timestamp
        if isinstance(sync_ts, datetime):
            sync_ts_str = sync_ts.isoformat()
        else:
            sync_ts_str = str(sync_ts)

        return {
            "wazuh_endpoint": self.wazuh_endpoint,
            "wazuh_status": self.wazuh_status,
            "polling_interval_seconds": self.polling_interval_seconds,
            "min_rule_level": self.min_rule_level,
            "llm_provider": self.llm_provider,
            "model_name": self.model_name,
            "abstention_threshold": float(self.abstention_threshold),
            "max_exemplars_injected": int(self.max_exemplars_injected),
            "last_sync_timestamp": sync_ts_str,
        }

    def __repr__(self) -> str:
        return f"<SystemConfiguration id={self.id} provider={self.llm_provider!r} model={self.model_name!r}>"
