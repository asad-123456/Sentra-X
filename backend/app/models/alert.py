from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, SmallInteger, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Alert(Base):
    """Security alert ingested from Wazuh.

    Each alert maps 1-to-1 with a Wazuh event (``wazuh_alert_id`` unique).
    FK to ``assets`` uses ON DELETE RESTRICT so historical alerts are never
    silently orphaned when an asset is removed.

    Status lifecycle (SRS v1.4 §6.4):
      PENDING_REVIEW → AWAITING_ANALYST → NEEDS_MANUAL_TRIAGE
                                        → ESCALATED → CLOSED
    """

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("rule_level BETWEEN 0 AND 15", name="ck_alerts_rule_level"),
        CheckConstraint("retry_count >= 0", name="ck_alerts_retry_count"),
        CheckConstraint(
            "status IN ('PENDING_REVIEW','AWAITING_ANALYST','NEEDS_MANUAL_TRIAGE','ESCALATED','CLOSED')",
            name="ck_alerts_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    wazuh_alert_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
    )
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_level: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_description: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''"),
    )
    mitre_tactics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    mitre_techniques: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # FK → assets(agent_id). ON DELETE RESTRICT protects audit integrity.
    agent_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("assets.agent_id", ondelete="RESTRICT"),
        nullable=False,
    )
    src_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    process_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'PENDING_REVIEW'"),
        # CHECK: PENDING_REVIEW | AWAITING_ANALYST | NEEDS_MANUAL_TRIAGE | ESCALATED | CLOSED
    )
    retry_count: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("0"),
    )
    alert_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    ingested_at: Mapped[datetime] = mapped_column(
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
            f"<Alert id={self.id} wazuh_id={self.wazuh_alert_id!r}"
            f" status={self.status!r}>"
        )
