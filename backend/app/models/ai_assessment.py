from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, Text, TIMESTAMP, text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AIAssessment(Base):
    """LLM-generated triage assessment for a single alert.

    One-to-one with ``alerts`` (unique FK, CASCADE delete).

    ``raw_verdict`` / ``raw_severity`` reflect the LLM's unmodified output.
    ``effective_verdict`` / ``effective_severity`` reflect the final values
    after guardrails (safety floor, abstention) are applied.

    SRS v1.4 (§7.2.1):
      ``inference_latency_ms`` records the round-trip API inference time.
      ``latency_ms`` is maintained as a synonym for backward compatibility.
    """

    __tablename__ = "ai_assessments"
    __table_args__ = (
        CheckConstraint(
            "raw_verdict IN ('TRUE_POSITIVE','FALSE_POSITIVE','NEEDS_ANALYST_REVIEW')",
            name="ck_ai_assessments_raw_verdict",
        ),
        CheckConstraint(
            "raw_severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_ai_assessments_raw_severity",
        ),
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_ai_assessments_confidence_score",
        ),
        CheckConstraint(
            "retry_count BETWEEN 0 AND 3",
            name="ck_ai_assessments_retry_count",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # LLM raw output – CHECK: TRUE_POSITIVE | FALSE_POSITIVE | NEEDS_ANALYST_REVIEW
    raw_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    # CHECK: LOW | MEDIUM | HIGH | CRITICAL
    raw_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    # Post-guardrail effective values
    effective_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    cited_evidence_keys: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    safety_floor_triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
    abstention_triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
    guardrail_audit_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inference_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
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
            f"<AIAssessment id={self.id} alert_id={self.alert_id}"
            f" verdict={self.effective_verdict!r}>"
        )
