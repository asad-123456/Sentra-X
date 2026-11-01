from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Asset(Base):
    """Wazuh-monitored asset (endpoint / server).

    The primary key is the Wazuh agent ID string (e.g. ``"agent_001"``),
    NOT a UUID. This mirrors the upstream Wazuh identifier so joins with
    the alerts table require no translation.

    Criticality tiers follow the organisation's risk classification:
      LOW | MEDIUM | HIGH | CRITICAL

    SRS v1.4 (§7.2.1, FR-9):
      ``updated_by`` tracks the user who modified the tier (NULL when auto-registered).
    """

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "criticality_tier IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_assets_criticality_tier",
        ),
    )

    # PK is a Wazuh agent ID string, not a UUID.
    agent_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    criticality_tier: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'MEDIUM'"),
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return (
            f"<Asset agent_id={self.agent_id!r} hostname={self.hostname!r}"
            f" tier={self.criticality_tier!r}>"
        )
