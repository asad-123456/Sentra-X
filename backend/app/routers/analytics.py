from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..database import get_db
from ..models.alert import Alert
from ..models.audit import AnalystDecisionAudit
from ..models.user import User
from ..services.analytics_service import build_analytics, utc_bounds

router = APIRouter(prefix="/analytics", tags=["Team Lead Analytics & Reporting"])
MAX_RANGE_DAYS = 90


@router.get("", response_model=dict[str, Any])
def get_analytics(
    range: str | None = Query(None),
    date_range: str | None = Query(None),
    rule_id: str | None = Query(None),
    _: User = Depends(require_roles("TeamLead", "Admin", demo_open=True)),
    db: Session = Depends(get_db),
):
    match = re.fullmatch(r"([1-9][0-9]?)d?", date_range or range or "30d")
    if not match or int(match[1]) > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Analytics range must be between 1 and 90 days.")
    last_day = datetime.now(timezone.utc).date()
    first_day = last_day - timedelta(days=int(match[1]) - 1)
    rule = (rule_id or "").strip()
    return build_analytics(db, first_day, last_day, rule if rule and rule != "ALL" else None)


@router.get("/export-csv")
def export_audit_csv(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    rule_id: str | None = Query(None),
    _: User = Depends(require_roles("TeamLead", "Admin", demo_open=True)),
    db: Session = Depends(get_db),
):
    if start_date is None or end_date is None:
        if start_date is not None or end_date is not None:
            raise HTTPException(status_code=422, detail="Provide both start_date and end_date.")
    elif not 0 <= (end_date - start_date).days < MAX_RANGE_DAYS or end_date == date.max:
        raise HTTPException(status_code=422, detail="Export dates must span 1 to 90 days.")

    audits = (
        db.query(AnalystDecisionAudit, Alert, User)
        .join(Alert, AnalystDecisionAudit.alert_id == Alert.id)
        .outerjoin(User, AnalystDecisionAudit.user_id == User.id)
        .order_by(desc(AnalystDecisionAudit.created_at), desc(AnalystDecisionAudit.id))
    )
    if start_date is not None and end_date is not None:
        start, end = utc_bounds(start_date, end_date)
        audits = audits.filter(AnalystDecisionAudit.created_at >= start, AnalystDecisionAudit.created_at < end)
    rule = (rule_id or "").strip()
    if rule and rule != "ALL":
        audits = audits.filter(Alert.rule_id == rule)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Decision ID",
        "Timestamp",
        "Wazuh Alert ID",
        "Rule ID",
        "Rule Level",
        "Rule Description",
        "Analyst Username",
        "Analyst Role",
        "Action Taken",
        "Previous Verdict",
        "Previous Severity",
        "Final Verdict",
        "Final Severity",
        "Exemplar Created",
        "Rationale",
    ])

    for audit, alert, user in audits.yield_per(1000):
        writer.writerow([
            str(audit.id),
            audit.created_at.astimezone(timezone.utc).isoformat(),
            alert.wazuh_alert_id,
            alert.rule_id,
            alert.rule_level,
            alert.rule_description,
            user.username if user else "SOC Analyst",
            user.role if user else "Analyst",
            audit.action_taken,
            audit.previous_verdict or "—",
            audit.previous_severity or "—",
            audit.final_verdict or "—",
            audit.final_severity or "—",
            "TRUE" if audit.exemplar_created else "FALSE",
            audit.rationale,
        ])

    csv_content = output.getvalue()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sentrax_audit_trail_{today_str}.csv"},
    )

