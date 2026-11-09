from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..auth import security
from ..config import settings
from ..database import get_db
from ..models.asset import Asset
from ..models.exemplar import FeedbackExemplar
from ..models.user import User

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


def get_caller_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if auth and auth.credentials:
        try:
            token_payload = jwt.decode(
                auth.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            sub = token_payload.get("sub")
            if sub:
                return db.query(User).filter(User.id == uuid.UUID(sub)).first()
        except Exception:
            pass
    return None


@router.get("/exemplars", response_model=List[Dict[str, Any]])
def get_exemplars(db: Session = Depends(get_db)):
    exemplars = db.query(FeedbackExemplar).order_by(desc(FeedbackExemplar.created_at)).all()
    results = []
    for ex in exemplars:
        results.append(
            {
                "id": str(ex.id),
                "rule_id": ex.rule_id,
                "process_signature": ex.process_signature,
                "asset_criticality": ex.asset_criticality,
                "calibrated_verdict": ex.calibrated_verdict,
                "calibrated_severity": ex.calibrated_severity,
                "rationale": ex.rationale,
                "match_tier_support": "Tier 1" if "procdump" in ex.process_signature or "powershell" in ex.process_signature else "Tier 2",
                "match_hit_count": ex.match_hit_count,
                "is_active": ex.is_active,
                "created_by": _resolve_username(ex.created_by, db),
                "created_at": str(ex.created_at),
            }
        )
    return results


@router.patch("/exemplars/{exemplar_id}", response_model=Dict[str, Any])
def toggle_exemplar_active(
    exemplar_id: str,
    payload: Dict[str, Any],
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    caller = get_caller_user(auth, db)
    if not caller and not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HTTP 401 Unauthorized: Authentication credentials required.",
        )
    if caller and caller.role == "Analyst":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: Analyst role is prohibited from revoking exemplars (FR-4, UC-10).",
        )

    try:
        ex_id_int = int(exemplar_id.replace("EX-", "").replace("ex-", ""))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Invalid exemplar ID format: {exemplar_id}")

    exemplar = db.query(FeedbackExemplar).filter(FeedbackExemplar.id == ex_id_int).first()
    if not exemplar:
        raise HTTPException(status_code=404, detail=f"Exemplar {exemplar_id} not found.")

    if "is_active" in payload:
        new_active = bool(payload["is_active"])
    else:
        new_active = not exemplar.is_active

    exemplar.is_active = new_active
    if not new_active:
        exemplar.revoked_at = datetime.now(timezone.utc)
        revoked_by_raw = payload.get("revoked_by")
        if revoked_by_raw:
            try:
                rev_user = db.query(User).filter(User.id == uuid.UUID(str(revoked_by_raw))).first()
                if rev_user and rev_user.role == "Analyst":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="HTTP 403 Forbidden: Analyst role is prohibited from revoking exemplars (FR-4, UC-10).",
                    )
                exemplar.revoked_by = uuid.UUID(str(revoked_by_raw))
            except HTTPException:
                raise
            except Exception:
                pass
        elif caller:
            exemplar.revoked_by = caller.id
    else:
        exemplar.revoked_at = None

    db.commit()

    return {
        "id": str(exemplar.id),
        "rule_id": exemplar.rule_id,
        "process_signature": exemplar.process_signature,
        "asset_criticality": exemplar.asset_criticality,
        "calibrated_verdict": exemplar.calibrated_verdict,
        "calibrated_severity": exemplar.calibrated_severity,
        "rationale": exemplar.rationale,
        "match_tier_support": "Tier 1",
        "match_hit_count": exemplar.match_hit_count,
        "is_active": exemplar.is_active,
        "revoked_by": str(exemplar.revoked_by) if exemplar.revoked_by else None,
        "revoked_at": str(exemplar.revoked_at) if exemplar.revoked_at else None,
        "created_by": _resolve_username(exemplar.created_by, db),
        "created_at": str(exemplar.created_at),
    }


@router.get("/assets", response_model=List[Dict[str, Any]])
def get_assets(db: Session = Depends(get_db)):
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
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    caller = get_caller_user(auth, db)
    if not caller and not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HTTP 401 Unauthorized: Authentication credentials required.",
        )
    if caller and caller.role == "Analyst":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: Analyst role is prohibited from modifying asset criticality tiers (AC-17, FR-9).",
        )

    updated_by_raw = payload.get("updated_by")
    if updated_by_raw:
        try:
            user_obj = db.query(User).filter(User.id == uuid.UUID(str(updated_by_raw))).first()
            if user_obj and user_obj.role == "Analyst":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="HTTP 403 Forbidden: Analyst role is prohibited from modifying asset criticality tiers (AC-17, FR-9).",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    asset = db.query(Asset).filter(Asset.agent_id == agent_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {agent_id} not found.")

    tier = payload.get("criticality_tier")
    if not tier or tier not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"HTTP 422: Invalid criticality_tier '{tier}'. Must be one of: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.",
        )

    asset.criticality_tier = tier
    asset.updated_at = datetime.now(timezone.utc)
    if updated_by_raw:
        try:
            asset.updated_by = uuid.UUID(str(updated_by_raw))
        except Exception:
            pass
    elif caller:
        asset.updated_by = caller.id
    db.commit()

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
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    caller = get_caller_user(auth, db)
    if not caller and not settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HTTP 401 Unauthorized: Authentication credentials required.",
        )
    if caller and caller.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: Only Admin can register enterprise assets (UC-10, UC-11).",
        )
    agent_id = str(payload.get("agent_id", "")).strip()
    hostname = str(payload.get("hostname", "")).strip()
    ip_raw = payload.get("ip_address")
    ip_address = str(ip_raw).strip() if ip_raw else None
    tier = payload.get("criticality_tier", "MEDIUM")

    if not agent_id or not hostname:
        raise HTTPException(status_code=400, detail="agent_id and hostname are required.")

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

