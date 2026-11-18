from __future__ import annotations

import json
import logging
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.orm import Session

from ..auth import hash_password, require_roles, security
from ..config import settings
from ..database import get_db
from ..models.system_configuration import SystemConfiguration
from ..models.user import User
from ..security_log import security_log
from ..utils import parse_uuid

logger = logging.getLogger("sentrax.admin")

router = APIRouter(prefix="/admin", tags=["Admin & System Configuration"])


# AC-16 (FR-8): only Admin may administer users. The role is read from the database on every request.
verify_admin_access = require_roles(
    "Admin",
    demo_open=True,
    forbidden_detail="HTTP 403 Forbidden: Non-Admin callers are prohibited from administering users (AC-16, FR-8).",
)


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
    admin: Optional[User] = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    uid = parse_uuid(user_id)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    role = payload.get("role")
    if role not in ("Analyst", "TeamLead", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"HTTP 422: Invalid role '{role}'. Must be one of: 'Analyst', 'TeamLead', 'Admin'.",
        )

    if admin is not None and uid == admin.id and role != "Admin":
        raise HTTPException(status_code=400, detail="HTTP 400: Admins cannot demote themselves.")

    old_role = user.role
    user.role = role
    db.commit()
    security_log.info(
        "user_role_changed by=%s target=%s %s->%s", admin.username if admin else "demo", user.username, old_role, role
    )

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
    admin: Optional[User] = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    uid = parse_uuid(user_id)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    new_active = bool(payload.get("is_active", not user.is_active))
    if admin is not None and uid == admin.id and not new_active:
        raise HTTPException(status_code=400, detail="HTTP 400: Admins cannot deactivate themselves.")

    user.is_active = new_active
    db.commit()
    security_log.info(
        "user_status_changed by=%s target=%s active=%s", admin.username if admin else "demo", user.username, new_active
    )

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
    admin: Optional[User] = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    username = str(payload.get("username", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    role = payload.get("role", "Analyst")

    if not username or not email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HTTP 422: Username and email are required.",
        )

    if role not in ("Analyst", "TeamLead", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"HTTP 422: Invalid role '{role}'. Must be one of: 'Analyst', 'TeamLead', 'Admin'.",
        )

    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HTTP 422: Username must be 3-64 characters (letters, digits, '.', '_' or '-').",
        )
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 255:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="HTTP 422: Invalid email address.")

    # The admin UI has no password field: use DEFAULT_NEW_USER_PASSWORD if configured, otherwise generate a random
    # temporary password and return it once in the response. A password supplied by the caller must be 8-72 bytes.
    raw_password = payload.get("password")
    generated_password = None
    if raw_password in (None, ""):
        if settings.DEFAULT_NEW_USER_PASSWORD:
            raw_password = settings.DEFAULT_NEW_USER_PASSWORD
        else:
            raw_password = generated_password = secrets.token_urlsafe(12)
    else:
        raw_password = str(raw_password)
        if not 8 <= len(raw_password.encode("utf-8")) <= 72:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="HTTP 422: Password must be 8 to 72 bytes long.",
            )

    existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists.")

    new_user = User(
        id=uuid.uuid4(),
        username=username,
        email=email,
        password_hash=hash_password(raw_password),
        role=role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    security_log.info(
        "user_created by=%s new_user=%s role=%s", admin.username if admin else "demo", new_user.username, new_user.role
    )

    result = {
        "id": str(new_user.id),
        "username": new_user.username,
        "email": new_user.email,
        "role": new_user.role,
        "is_active": new_user.is_active,
        "created_at": str(new_user.created_at),
    }
    if generated_password:  # shown once, never stored in clear text
        result["temporary_password"] = generated_password
    return result


CONFIG_FILE_PATH = Path(__file__).resolve().parent.parent / "system_config.json"

DEFAULT_SYSTEM_CONFIG: Dict[str, Any] = {
    "wazuh_endpoint": "https://wazuh-master.sentrax.internal:55000",
    "wazuh_status": "CONNECTED",
    "polling_interval_seconds": 30,
    "min_rule_level": 4,
    "llm_provider": "Gemini",
    "model_name": "gemini-3.1-flash-lite",
    "abstention_threshold": 0.6,
    "max_exemplars_injected": 2,
    "last_sync_timestamp": "2026-10-15T21:45:00Z",
}


def _load_system_config(db: Optional[Session] = None) -> Dict[str, Any]:
    """Load configuration from PostgreSQL table, with resilient disk/default fallback."""
    if db:
        try:
            config_row = db.query(SystemConfiguration).first()
            if config_row:
                return config_row.to_dict()
            # If table is empty, auto-seed default row
            new_row = SystemConfiguration()
            db.add(new_row)
            db.commit()
            db.refresh(new_row)
            return new_row.to_dict()
        except Exception as exc:
            logger.warning("Database config query failed, falling back to disk cache: %s", exc)

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


def _save_system_config(payload: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    """Persist updated configuration to PostgreSQL and mirror to JSON state file."""
    current = _load_system_config(db)
    for k, v in payload.items():
        if k in DEFAULT_SYSTEM_CONFIG:
            current[k] = v
            SYSTEM_CONFIG[k] = v

    if db:
        try:
            config_row = db.query(SystemConfiguration).first()
            if not config_row:
                config_row = SystemConfiguration()
                db.add(config_row)

            for k, v in current.items():
                if hasattr(config_row, k) and k != "id":
                    setattr(config_row, k, v)
            config_row.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(config_row)
            current = config_row.to_dict()
        except Exception as exc:
            logger.error("Failed to persist configuration to PostgreSQL: %s", exc)

    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
    except Exception:
        pass

    return current


# Module-level alias for backward compatibility
SYSTEM_CONFIG = _load_system_config()


@router.get("/config", response_model=Dict[str, Any])
def get_system_config(
    _: None = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    return _load_system_config(db)


@router.patch("/config", response_model=Dict[str, Any])
def update_system_config(
    payload: Dict[str, Any],
    _: None = Depends(verify_admin_access),
    db: Session = Depends(get_db),
):
    if "min_rule_level" in payload:
        try:
            mrl = int(payload["min_rule_level"])
            if not 0 <= mrl <= 9:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="HTTP 422: min_rule_level must be between 0 and 9 (rule levels 10+ represent critical alerts and cannot be suppressed).",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="HTTP 422: min_rule_level must be an integer.",
            )
    return _save_system_config(payload, db)

