from __future__ import annotations

import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, verify_password
from ..config import settings
from ..database import get_db
from ..models.user import User
from ..schemas.auth import LoginRequest, TokenResponse, UserDTO

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory sliding window rate guard for failed authentication: IP -> list of unix timestamps
FAILED_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
MAX_FAILED_ATTEMPTS = 10
ATTEMPT_WINDOW_SECONDS = 60.0


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    attempts = [t for t in FAILED_LOGIN_ATTEMPTS[client_ip] if now - t < ATTEMPT_WINDOW_SECONDS]
    FAILED_LOGIN_ATTEMPTS[client_ip] = attempts
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="HTTP 429 Too Many Requests: Rate limit exceeded for login attempts. Please wait 60 seconds.",
        )


def _record_failed_attempt(client_ip: str) -> None:
    FAILED_LOGIN_ATTEMPTS[client_ip].append(time.time())


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, raw_req: Request, db: Session = Depends(get_db)):
    client_ip = raw_req.client.host if raw_req.client else "127.0.0.1"
    _check_rate_limit(client_ip)

    # Support login with either username or email
    user = (
        db.query(User)
        .filter(
            (User.username == request.username)
            | (User.email == request.username.lower())
        )
        .first()
    )

    if not user:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HTTP 401 Unauthorized: Invalid username, email or password.",
        )

    # Verify password hash; allow demo passwords only when DEMO_MODE is explicitly enabled
    is_valid = verify_password(request.password, user.password_hash) or (
        settings.DEMO_MODE
        and request.password
        in (
            "sentrax2026",
            "analyst123",
            "teamlead123",
            "admin123",
        )
    )

    if not is_valid:
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HTTP 401 Unauthorized: Invalid username, email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: User account is disabled.",
        )

    # Successful login: reset rate limit attempts for this client IP
    FAILED_LOGIN_ATTEMPTS.pop(client_ip, None)

    token = create_access_token({"sub": str(user.id), "role": user.role, "username": user.username})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=str(user.created_at),
        ),
    )


@router.get("/me", response_model=UserDTO)
def get_me(current_user: User = Depends(get_current_user)):
    return UserDTO(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=str(current_user.created_at),
    )

