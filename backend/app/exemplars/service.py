"""FR-4 few-shot exemplar retrieval for the triage worker (Part 9).

Exemplars are created by Asad's decision endpoint (app/routers/alerts.py) and revoked through
PATCH /api/v1/governance/exemplars/{id}. This module adds the retrieval rules. The caller owns the transaction:
nothing here commits.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models.exemplar import FeedbackExemplar as Ex

MAX_EXEMPLARS = 2


def _shape(row: Ex, match_tier: str) -> dict:
    """The shape Abdur's evidence-pack code expects. rationale and process_signature are passed RAW (he sanitizes
    them). id is an int because Asad's table uses a serial integer key."""
    return {
        "id": row.id,
        "match_tier": match_tier,
        "rule_id": row.rule_id,
        "process_signature": row.process_signature,
        "asset_criticality": row.asset_criticality,
        "calibrated_verdict": row.calibrated_verdict,
        "calibrated_severity": row.calibrated_severity,
        "rationale": row.rationale,
    }


def find_exemplars(session: Session, *, alert_id: uuid.UUID, rule_id: str,
                   process_signature: Optional[str], asset_criticality: str) -> list[dict]:
    """At most 2 ACTIVE exemplars, most recent first.

    Tier 1: same rule_id AND same process_signature.
    Tier 2: fills the remaining slots with same rule_id AND same asset_criticality.
    A NULL signature never matches in Tier 1. Exemplars created from this very alert are excluded (a retry must not
    cite itself). A Tier 1 hit is never repeated in Tier 2. match_hit_count is incremented for every exemplar
    returned. An empty list means zero-shot."""
    # IS DISTINCT FROM keeps rows whose source_alert_id is NULL (the FK is ON DELETE SET NULL).
    not_own = Ex.source_alert_id.is_distinct_from(alert_id)
    newest_first = (Ex.created_at.desc(), Ex.id.desc())
    picked: list[tuple[Ex, str]] = []

    if process_signature is not None:   # in SQL "== None" would turn into IS NULL, so skip Tier 1 instead
        rows = session.execute(
            select(Ex)
            .where(Ex.is_active.is_(True), Ex.rule_id == rule_id,
                   Ex.process_signature == process_signature, not_own)
            .order_by(*newest_first).limit(MAX_EXEMPLARS)
        ).scalars().all()
        picked += [(r, "Tier 1") for r in rows]

    remaining = MAX_EXEMPLARS - len(picked)
    if remaining > 0:
        stmt = (
            select(Ex)
            .where(Ex.is_active.is_(True), Ex.rule_id == rule_id,
                   Ex.asset_criticality == asset_criticality, not_own)
            .order_by(*newest_first).limit(remaining)
        )
        already = [r.id for r, _ in picked]
        if already:
            stmt = stmt.where(Ex.id.not_in(already))
        picked += [(r, "Tier 2") for r in session.execute(stmt).scalars().all()]

    if picked:
        session.execute(
            update(Ex).where(Ex.id.in_([r.id for r, _ in picked]))
            .values(match_hit_count=Ex.match_hit_count + 1)
            .execution_options(synchronize_session=False)
        )
    return [_shape(r, tier) for r, tier in picked]
