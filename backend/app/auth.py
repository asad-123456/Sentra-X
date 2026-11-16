from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models.user import User
from .security_log import security_log

ALL_ROLES = ("Analyst", "TeamLead", "Admin")

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    pwd_bytes = password[:72].encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password[:72].encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def _user_from_token(token: str, db: Session) -> User:
    """Verify the JWT and load the user FRESH from the database, so a role change or a deactivation takes effect
    on the very next request (the role and is_active in the token are never trusted)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise credentials_exception

    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        security_log.warning("inactive_user_blocked user=%s", user.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user account"
        )
    return user


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_token(auth.credentials, db)


def require_roles(*roles: str, demo_open: bool = False, forbidden_detail: Optional[str] = None):
    """Dependency factory: the caller must hold one of `roles`.

    401 = no, expired, forged or unknown token; 403 = deactivated account or wrong role. The role comes from the
    database on every request. With demo_open=True a request with NO token is let through (returns None), but only
    while DEMO_MODE is on, so production (DEMO_MODE=false) always requires a token."""
    allowed = set(roles)
    if not allowed or not allowed.issubset(ALL_ROLES):
        raise ValueError(f"unknown role in {roles}; valid roles are {ALL_ROLES}")

    def dependency(
        auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: Session = Depends(get_db),
    ) -> Optional[User]:
        if not auth or not auth.credentials:
            if demo_open and settings.DEMO_MODE:
                return None
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="HTTP 401 Unauthorized: Authentication credentials required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = _user_from_token(auth.credentials, db)
        if user.role not in allowed:
            security_log.warning("access_denied user=%s role=%s needs=%s", user.username, user.role, sorted(allowed))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=forbidden_detail or f"HTTP 403 Forbidden: role '{user.role}' may not perform this action.",
            )
        return user

    return dependency

