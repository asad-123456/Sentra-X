"""Asset criticality lookup for the triage worker (FR-9, AC-17).

The routes that edit tiers already exist in app/routers/governance.py (Asad). This module only adds the
hook the worker calls when it builds an Evidence Pack. It reads the tier fresh from the database on every
call, with no caching, so a tier change shows up in the NEXT evidence pack. Callers own the transaction."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset

DEFAULT_TIER = "MEDIUM"


def get_asset_tier(session: Session, agent_id: str) -> str:
    """Criticality tier for an agent. An unknown agent gives MEDIUM (the same default as auto-registration)."""
    tier = session.execute(
        select(Asset.criticality_tier).where(Asset.agent_id == agent_id)
    ).scalar_one_or_none()
    return tier or DEFAULT_TIER
