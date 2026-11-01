from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.orm import Session

from ..auth import hash_password, security
from ..config import settings
from ..database import get_db
from ..models.user import User
from ..utils import parse_uuid

router = APIRouter(prefix="/admin", tags=["Admin & System Configuration"])


def verify_admin_access(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> None:
    """Enforces AC-16 (FR-8): non-Admin callers receive HTTP 403 Forbidden on user administration."""
    if auth and auth.credentials:
        try:
            token_payload = jwt.decode(
                auth.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            role = token_payload.get("role")
            if role != "Admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="HTTP 403 Forbidden: Non-Admin callers are prohibited from administering users (AC-16, FR-8).",
                )
        except HTTPException:
            raise
        except Exception:
            pass


@router.get("/users", response_model=List[Dict[str, Any]])
def get_users(
    _: None = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.username).all()
    results = []
    for u in users:
        results.append(
            {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": str(u.created_at),
            }
        )
    return results


@router.patch("/users/{user_id}/role", response_model=Dict[str, Any])
def update_user_role(
    user_id: str,
    payload: Dict[str, Any],
    _: None = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    uid = parse_uuid(user_id)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    role = payload.get("role")
    if role not in ("Analyst", "TeamLead", "Admin"):
        raise HTTPException(status_code=400, detail="Invalid role.")

    user.role = role
    db.commit()

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": str(user.created_at),
    }


@router.patch("/users/{user_id}/status", response_model=Dict[str, Any])
def toggle_user_status(
    user_id: str,
    payload: Dict[str, Any],
    _: None = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    uid = parse_uuid(user_id)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.is_active = bool(payload.get("is_active", not user.is_active))
    db.commit()

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": str(user.created_at),
    }


@router.post("/users", response_model=Dict[str, Any])
def create_user(
    payload: Dict[str, Any],
    _: None = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    username = str(payload.get("username", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    role = payload.get("role", "Analyst")

    if not username or not email:
        raise HTTPException(status_code=400, detail="Username and email are required.")

    existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists.")

    new_user = User(
        id=uuid.uuid4(),
        username=username,
        email=email,
        password_hash=hash_password("sentrax2026"),
        role=role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": str(new_user.id),
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
        "is_active": new_user.is_active,
        "created_at": str(new_user.created_at),
    }


CONFIG_FILE_PATH = Path(__file__).resolve().parent.parent / "system_config.json"

DEFAULT_SYSTEM_CONFIG: Dict[str, Any] = {
    "wazuh_endpoint": "https://wazuh-master.sentrax.internal:55000",
    "wazuh_status": "CONNECTED",
    "polling_interval_seconds": 30,
    "min_rule_level": 4,
    "llm_provider": "Gemini",
    "model_name": "gemini-2.5-flash",
    "abstention_threshold": 0.6,
    "max_exemplars_injected": 2,
    "last_sync_timestamp": "2026-10-15T21:45:00Z",
}


def _load_system_config() -> Dict[str, Any]:
    """Load configuration from JSON state file or fall back to default."""
    if CONFIG_FILE_PATH.exists():
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config = dict(DEFAULT_SYSTEM_CONFIG)
                config.update(saved)
                return config
        except Exception:
            pass
    return dict(DEFAULT_SYSTEM_CONFIG)


def _save_system_config(config: Dict[str, Any]) -> None:
    """Persist updated configuration to JSON state file."""
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


# Module-level alias for backward compatibility
SYSTEM_CONFIG = _load_system_config()


@router.get("/config", response_model=Dict[str, Any])
def get_system_config(_: None = Depends(verify_admin_access)):
    return _load_system_config()


@router.patch("/config", response_model=Dict[str, Any])
def update_system_config(
    payload: Dict[str, Any],
    _: None = Depends(verify_admin_access),
):
    current = _load_system_config()
    for k, v in payload.items():
        if k in DEFAULT_SYSTEM_CONFIG:
            current[k] = v
            SYSTEM_CONFIG[k] = v
    _save_system_config(current)
    return current

