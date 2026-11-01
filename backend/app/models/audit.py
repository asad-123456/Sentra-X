from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AnalystDecisionAudit(Base):
    """Immutable append-only log of every analyst decision.

    IMPORTANT: This table has NO ``updated_at`` column. A PostgreSQL trigger
    (``trg_audit_immutability``) prevents any UPDATE or DELETE at the DB level,
    making the audit log tamper-evident (FR-6, SOC 2 / ISO 27001 compliance).

    SRS v1.4 (§7.2.1):
      action_taken CHECK allows:
        APPROVE | OVERRIDE | ESCALATE | RETRY_AI | MANUAL_TRIAGE_CLOSURE |
        MANUAL_TRIAGE_CLOSE | RESOLVE_ESCALATION
    """

    __tablename__ = "analyst_decisions_audit"
    __table_args__ = (
        CheckConstraint(
            "action_taken IN ('APPROVE','OVERRIDE','ESCALATE','RETRY_AI','MANUAL_TRIAGE_CLOSE','MANUAL_TRIAGE_CLOSURE','RESOLVE_ESCALATION')",
            name="ck_audit_action_taken",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action_taken: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_verdict: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    previous_severity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    final_verdict: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    final_severity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    exemplar_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    # NO updated_at – this table is APPEND-ONLY. The DB trigger enforces this.

    def __repr__(self) -> str:
        return (
            f"<AnalystDecisionAudit id={self.id} alert_id={self.alert_id}"
            f" action={self.action_taken!r}>"
        )
