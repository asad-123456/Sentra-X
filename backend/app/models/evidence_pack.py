from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EvidencePack(Base):
    """Structured evidence bundle assembled for a single alert.

    One-to-one with ``alerts`` (unique FK).  ``pack_json`` holds the full
    evidence payload sent to the LLM.  ``valid_dot_keys`` records the subset
    of dot-notation keys that passed the evidence validator.

    Decision 8.5: ``updated_at`` is REQUIRED on this table.
    """

    __tablename__ = "evidence_packs"

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
    pack_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    valid_dot_keys: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    injection_suspect: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
    injected_exemplar_ids: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    # Decision 8.5: REQUIRED
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    def __repr__(self) -> str:
        return f"<EvidencePack id={self.id} alert_id={self.alert_id}>"
