from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..exemplars.vocab import TIERS
from ..models.asset import Asset
from ..models.exemplar import FeedbackExemplar
from ..models.user import User
from ..security_log import security_log

router = APIRouter(prefix="/governance", tags=["Governance & Feedback Calibration"])


def _resolve_username(created_by_uuid, db: Session) -> str:
    """Resolve a creator UUID to a display name, falling back gracefully."""
    if created_by_uuid is None:
        return "Unknown"
    try:
        user = db.query(User).filter(User.id == created_by_uuid).first()
        if user:
            return f"{user.username} ({user.role})"
    except Exception:
        pass
    return str(created_by_uuid)


def _exemplar_payload(exemplar: FeedbackExemplar, db: Session) -> dict[str, Any]:
    return {
        "id": str(exemplar.id),
        "source_alert_id": str(exemplar.source_alert_id) if exemplar.source_alert_id else None,
        "rule_id": exemplar.rule_id,
        "process_signature": exemplar.process_signature,
        "asset_criticality": exemplar.asset_criticality,
        "calibrated_verdict": exemplar.calibrated_verdict,
        "calibrated_severity": exemplar.calibrated_severity,
        "rationale": exemplar.rationale,
        "match_tier_support": "Tier 1" if exemplar.process_signature else "Tier 2",
        "match_hit_count": exemplar.match_hit_count,
        "is_active": exemplar.is_active,
        "revoked_by": str(exemplar.revoked_by) if exemplar.revoked_by else None,
        "revoked_at": str(exemplar.revoked_at) if exemplar.revoked_at else None,
        "created_by": _resolve_username(exemplar.created_by, db),
        "created_at": str(exemplar.created_at),
    }


@router.get("/exemplars", response_model=List[Dict[str, Any]])
def get_exemplars(
    _: Optional[User] = Depends(require_roles("TeamLead", "Admin", demo_open=True)),
    db: Session = Depends(get_db),
):
    exemplars = db.query(FeedbackExemplar).order_by(desc(FeedbackExemplar.created_at)).all()
    return [_exemplar_payload(exemplar, db) for exemplar in exemplars]

@router.patch("/exemplars/{exemplar_id}", response_model=Dict[str, Any])
def toggle_exemplar_active(
    exemplar_id: str,
    payload: Dict[str, Any],
    caller: Optional[User] = Depends(
        require_roles(
            "TeamLead",
            demo_open=True,
            forbidden_detail="HTTP 403 Forbidden: Only a Team Lead may revoke exemplars (FR-4, UC-10).",
        )
    ),
    db: Session = Depends(get_db),
):
    # require_roles checks the role and is_active in the database on every request. A "revoked_by" in the body is
    # ignored on purpose: the revoker recorded is always the authenticated caller.
    try:
        ex_id_int = int(exemplar_id.replace("EX-", "").replace("ex-", ""))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Invalid exemplar ID format: {exemplar_id}")

    exemplar = db.query(FeedbackExemplar).filter(FeedbackExemplar.id == ex_id_int).with_for_update().first()
    if not exemplar:
        raise HTTPException(status_code=404, detail=f"Exemplar {exemplar_id} not found.")

    new_active = payload.get("is_active", not exemplar.is_active)
    if not isinstance(new_active, bool):
        raise HTTPException(status_code=422, detail="is_active must be a boolean.")

    was_active = exemplar.is_active
    exemplar.is_active = new_active
    if not new_active:
        if was_active:   # revoking an already revoked exemplar keeps the original who/when
            exemplar.revoked_at = datetime.now(timezone.utc)
            exemplar.revoked_by = caller.id if caller else None
    else:
        exemplar.revoked_at = None
        exemplar.revoked_by = None

    db.commit()
    security_log.info("exemplar_%s by=%s exemplar=%s", "reactivated" if new_active else "revoked",
                      caller.username if caller else "demo", exemplar.id)

    return _exemplar_payload(exemplar, db)


@router.get("/assets", response_model=List[Dict[str, Any]])
def get_assets(
    _: Optional[User] = Depends(require_roles("Analyst", "TeamLead", "Admin", demo_open=True)),
    db: Session = Depends(get_db),
):
    assets = db.query(Asset).order_by(Asset.agent_id).all()
    results = []
    for asset in assets:
        results.append(
            {
                "id": f"asset-{asset.agent_id}",
                "agent_id": asset.agent_id,
                "hostname": asset.hostname,
                "ip_address": asset.ip_address,
                "criticality_tier": asset.criticality_tier,
                "description": asset.description or "",
                "created_at": str(asset.created_at),
                "updated_at": str(asset.updated_at),
            }
        )
    return results


@router.patch("/assets/{agent_id}", response_model=Dict[str, Any])
def update_asset_criticality(
    agent_id: str,
    payload: Dict[str, Any],
    caller: Optional[User] = Depends(
        require_roles(
            "TeamLead",
            "Admin",
            demo_open=True,
            forbidden_detail="HTTP 403 Forbidden: Analyst role is prohibited from modifying asset criticality tiers (AC-17, FR-9).",
        )
    ),
    db: Session = Depends(get_db),
):
    # Role and is_active are checked against the database by require_roles. Any "updated_by" in the request body is
    # ignored on purpose: the editor recorded is always the authenticated caller (no identity spoofing).
    asset = db.query(Asset).filter(Asset.agent_id == agent_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {agent_id} not found.")

    tier = payload.get("criticality_tier")
    if tier not in TIERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"HTTP 422: Invalid criticality_tier '{tier}'. Must be one of: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.",
        )

    description = payload.get("description")
    if description is not None and not isinstance(description, str):
        raise HTTPException(status_code=422, detail="Description must be text.")

    old_tier = asset.criticality_tier
    asset.criticality_tier = tier
    if description is not None:
        asset.description = description.strip()
    asset.updated_at = datetime.now(timezone.utc)
    if caller is not None:
        asset.updated_by = caller.id
    db.commit()
    security_log.info(
        "asset_updated by=%s agent=%s tier=%s->%s", caller.username if caller else "demo", agent_id, old_tier, tier
    )

    return {
        "id": f"asset-{asset.agent_id}",
        "agent_id": asset.agent_id,
        "hostname": asset.hostname,
        "ip_address": asset.ip_address,
        "criticality_tier": asset.criticality_tier,
        "description": asset.description or "",
        "updated_by": str(asset.updated_by) if asset.updated_by else None,
        "created_at": str(asset.created_at),
        "updated_at": str(asset.updated_at),
    }


@router.post("/assets", response_model=Dict[str, Any])
def register_asset(
    payload: Dict[str, Any],
    caller: Optional[User] = Depends(
        require_roles(
            "Admin",
            demo_open=True,
            forbidden_detail="HTTP 403 Forbidden: Only Admin can register enterprise assets (UC-10, UC-11).",
        )
    ),
    db: Session = Depends(get_db),
):
    agent_id = str(payload.get("agent_id", "")).strip()
    hostname = str(payload.get("hostname", "")).strip()
    ip_raw = payload.get("ip_address")
    ip_address = str(ip_raw).strip() if ip_raw else None
    tier = payload.get("criticality_tier", "MEDIUM")

    if not agent_id or not hostname:
        raise HTTPException(status_code=400, detail="agent_id and hostname are required.")

    if tier not in TIERS:
        raise HTTPException(status_code=422, detail="Select a valid criticality tier.")

    existing = db.query(Asset).filter(Asset.agent_id == agent_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Asset {agent_id} is already registered.")

    new_asset = Asset(
        agent_id=agent_id,
        hostname=hostname,
        ip_address=ip_address,
        criticality_tier=tier,
        description=payload.get("description", ""),
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)

    return {
        "id": f"asset-{new_asset.agent_id}",
        "agent_id": new_asset.agent_id,
        "hostname": new_asset.hostname,
        "ip_address": new_asset.ip_address,
        "criticality_tier": new_asset.criticality_tier,
        "description": new_asset.description or "",
        "created_at": str(new_asset.created_at),
        "updated_at": str(new_asset.updated_at),
    }

