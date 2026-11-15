from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FeedbackExemplar(Base):
    """Human-verified few-shot calibration examples for the AI triage pipeline.

    Decision 8.4: ``id`` is an INTEGER SERIAL (autoincrement), NOT a UUID.
    The frontend stores exemplar IDs as ``number | string``, and integer IDs
    are more ergonomic for the retrieval hot-path.

    The partial composite index ``ix_exemplars_retrieval`` (WHERE is_active = TRUE)
    enables sub-50 ms exemplar lookup (NFR-4, FR-4).

    SRS v1.4 (§7.2.1, FR-4, §6.5 Sequence 2):
      ``user_id`` and ``created_by`` record the authoring user (FK users.id).
      ``revoked_by`` (FK users.id) and ``revoked_at`` record exemplar revocation by Team Leads.
    """

    __tablename__ = "feedback_exemplars"
    __table_args__ = (
        CheckConstraint(
            "asset_criticality IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_exemplars_asset_criticality",
        ),
        CheckConstraint(
            "calibrated_verdict IN ('TRUE_POSITIVE','FALSE_POSITIVE')",
            name="ck_exemplars_calibrated_verdict",
        ),
        CheckConstraint(
            "length(rationale) >= 10",
            name="ck_exemplars_rationale_length",
        ),
    )

    # Decision 8.4 – INTEGER autoincrement (SERIAL), not UUID.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    process_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # CHECK: LOW | MEDIUM | HIGH | CRITICAL
    asset_criticality: Mapped[str] = mapped_column(String(16), nullable=False)
    # CHECK: TRUE_POSITIVE | FALSE_POSITIVE
    calibrated_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    calibrated_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )
    match_hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    # Canonical author column per SRS v1.4 §7.2.1 Data Dictionary.
    # Note: DB trigger trg_sync_feedback_exemplar_user automatically synchronizes user_id and created_by.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return (
            f"<FeedbackExemplar id={self.id} rule_id={self.rule_id!r}"
            f" verdict={self.calibrated_verdict!r} is_active={self.is_active}>"
        )
