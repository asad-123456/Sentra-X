from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.orm import Session

from ..auth import security
from ..config import settings
from ..database import get_db
from ..services.analytics_service import build_analytics, build_audit_csv

router = APIRouter(prefix="/analytics", tags=["Team Lead Analytics & Reporting"])

MAX_RANGE_DAYS = 90


def verify_analytics_access(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> None:
    """Enforces AC-14 / FR-7: Analyst role receives HTTP 403 Forbidden on analytics."""
    if not auth or not auth.credentials:
        if settings.DEMO_MODE:
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HTTP 401 Unauthorized: Authentication credentials required.",
        )
    try:
        token_payload = jwt.decode(
            auth.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        role = token_payload.get("role")
        if role == "Analyst":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HTTP 403 Forbidden: Analyst role is prohibited from accessing Team Lead analytics (AC-14, FR-7).",
            )
    except HTTPException:
        raise
    except Exception as exc:
        if not settings.DEMO_MODE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="HTTP 401 Unauthorized: Invalid or expired authentication token.",
            ) from exc


@router.get("", response_model=Dict[str, Any])
def get_analytics(
    range: Optional[str] = Query(None),
    date_range: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    _: None = Depends(verify_analytics_access),
    db: Session = Depends(get_db),
):
    selected_range = date_range or range or "30d"
    days = 30
    digits = re.findall(r"\d+", selected_range)
    if digits:
        days = int(digits[0])
        if days > MAX_RANGE_DAYS:
            raise HTTPException(
                status_code=422,
                detail=f"HTTP 422: Date range of {days} days exceeds maximum allowed {MAX_RANGE_DAYS} days (AC-14, FR-7).",
            )
    return build_analytics(db, days, rule_id)


@router.get("/export-csv")
def export_audit_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _: None = Depends(verify_analytics_access),
    db: Session = Depends(get_db),
):
    if start_date and end_date:
        span = (end_date - start_date).days + 1
        if span < 1 or span > MAX_RANGE_DAYS:
            raise HTTPException(
                status_code=422,
                detail=f"HTTP 422: the date range must be between 1 and {MAX_RANGE_DAYS} days (AC-14, FR-7).",
            )
    csv_content = build_audit_csv(db, start_date, end_date)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sentrax_audit_trail_{today_str}.csv"},
    )