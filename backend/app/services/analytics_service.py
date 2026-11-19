"""FR-7 analytics: every figure is computed from the audit log, alerts and AI assessments.
With no data the metrics are 0. Nothing in this module is invented or hard-coded."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

_VERDICTS = ("TRUE_POSITIVE", "FALSE_POSITIVE", "NEEDS_ANALYST_REVIEW")

# {rule} is either empty or " AND al.rule_id = :rule_id"
_SQL_ACTIONS = """
    SELECT a.action_taken, count(*)
    FROM analyst_decisions_audit a JOIN alerts al ON al.id = a.alert_id
    WHERE a.created_at >= :cutoff{rule}
    GROUP BY a.action_taken"""
_SQL_STATUSES = """
    SELECT al.status, count(*) FROM alerts al
    WHERE al.ingested_at >= :cutoff{rule}
    GROUP BY al.status"""
_SQL_GUARDRAILS = """
    SELECT count(*) FILTER (WHERE s.safety_floor_triggered),
           count(*) FILTER (WHERE s.abstention_triggered),
           count(*) FILTER (WHERE s.safety_floor_triggered OR s.abstention_triggered),
           count(*),
           avg(COALESCE(s.inference_latency_ms, s.latency_ms))
               FILTER (WHERE COALESCE(s.inference_latency_ms, s.latency_ms) > 0)
    FROM ai_assessments s JOIN alerts al ON al.id = s.alert_id
    WHERE al.ingested_at >= :cutoff{rule}"""
_SQL_INJECTION = """
    SELECT count(*) FROM evidence_packs p JOIN alerts al ON al.id = p.alert_id
    WHERE p.injection_suspect AND al.ingested_at >= :cutoff{rule}"""
_SQL_PAIRS = """
    SELECT a.final_verdict, s.effective_verdict, a.action_taken, count(*)
    FROM analyst_decisions_audit a
    JOIN alerts al ON al.id = a.alert_id
    JOIN ai_assessments s ON s.alert_id = a.alert_id
    WHERE a.created_at >= :cutoff{rule}
    GROUP BY a.final_verdict, s.effective_verdict, a.action_taken"""
_SQL_DELTAS = """
    SELECT count(*) FILTER (WHERE a.previous_severity = 'LOW' AND a.final_severity = 'CRITICAL'),
           count(*) FILTER (WHERE a.previous_severity = 'MEDIUM' AND a.final_severity = 'HIGH'),
           count(*) FILTER (WHERE a.previous_severity = 'HIGH' AND a.final_severity = 'CRITICAL')
    FROM analyst_decisions_audit a JOIN alerts al ON al.id = a.alert_id
    WHERE a.action_taken = 'OVERRIDE' AND a.created_at >= :cutoff{rule}"""
_SQL_TREND = """
    SELECT CAST(a.created_at AT TIME ZONE 'UTC' AS date) AS day,
           count(*) FILTER (WHERE a.action_taken IN ('APPROVE', 'OVERRIDE')),
           count(*) FILTER (WHERE a.action_taken = 'OVERRIDE'),
           count(*) FILTER (WHERE a.action_taken IN
               ('APPROVE', 'OVERRIDE', 'MANUAL_TRIAGE_CLOSURE', 'RESOLVE_ESCALATION'))
    FROM analyst_decisions_audit a JOIN alerts al ON al.id = a.alert_id
    WHERE a.created_at >= :cutoff{rule}
    GROUP BY 1 ORDER BY 1"""
_SQL_CSV = """
    SELECT a.id, a.created_at, al.wazuh_alert_id, al.rule_id, al.rule_level, al.rule_description,
           u.username, u.role, a.action_taken, a.previous_verdict, a.previous_severity,
           a.final_verdict, a.final_severity, a.exemplar_created, a.rationale
    FROM analyst_decisions_audit a
    JOIN alerts al ON al.id = a.alert_id
    LEFT JOIN users u ON u.id = a.user_id
    {where}
    ORDER BY a.created_at DESC"""

_CSV_HEADER = [
    "Decision ID", "Timestamp", "Wazuh Alert ID", "Rule ID", "Rule Level", "Rule Description",
    "Analyst Username", "Analyst Role", "Action Taken", "Previous Verdict", "Previous Severity",
    "Final Verdict", "Final Severity", "Exemplar Created", "Rationale",
]


def _pct(num: float, den: float) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def build_analytics(db: Session, days: int, rule_id: Optional[str] = None) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rule = rule_id if rule_id and rule_id != "ALL" else None
    where_rule = " AND al.rule_id = :rule_id" if rule else ""
    params: Dict[str, Any] = {"cutoff": cutoff}
    if rule:
        params["rule_id"] = rule

    def run(sql: str):
        return db.execute(text(sql.format(rule=where_rule)), params)

    actions = {a: c for a, c in run(_SQL_ACTIONS)}
    statuses = {s: c for s, c in run(_SQL_STATUSES)}
    floors, abstentions, interventions, assessed, avg_ms = run(_SQL_GUARDRAILS).one()
    injections = run(_SQL_INJECTION).scalar_one()
    pairs = [(a, b, act, c) for a, b, act, c in run(_SQL_PAIRS)]
    d_low, d_medium, d_high = run(_SQL_DELTAS).one()
    day_rows = run(_SQL_TREND).all()

    exemplar_sql = "SELECT created_at FROM feedback_exemplars WHERE is_active"
    if rule:
        exemplar_sql += " AND rule_id = :rule_id"
    exemplar_days = [
        r[0].astimezone(timezone.utc).date()
        for r in db.execute(text(exemplar_sql), {"rule_id": rule} if rule else {})
    ]

    # --- decisions and alert outcomes
    approved, overridden = actions.get("APPROVE", 0), actions.get("OVERRIDE", 0)
    decisions = approved + overridden
    override_rate = _pct(overridden, decisions)
    agreement_rate = round(100.0 - override_rate, 1) if decisions else 0.0
    closed = statuses.get("CLOSED", 0)
    escalated = statuses.get("ESCALATED", 0)
    manual = statuses.get("NEEDS_MANUAL_TRIAGE", 0)
    escalated_rate = _pct(escalated, closed + escalated)     # share of handled alerts
    manual_rate = _pct(manual, sum(statuses.values()))       # share of all alerts in the window

    # --- agreement between the analyst's final verdict and the AI's effective verdict
    agreed_tp = sum(c for a, b, _x, c in pairs if a == "TRUE_POSITIVE" and b == "TRUE_POSITIVE")
    agreed_fp = sum(c for a, b, _x, c in pairs if a == "FALSE_POSITIVE" and b == "FALSE_POSITIVE")
    threat_rescue = sum(c for a, _b, act, c in pairs if act == "OVERRIDE" and a == "TRUE_POSITIVE")
    benign_override = sum(c for a, _b, act, c in pairs if act == "OVERRIDE" and a == "FALSE_POSITIVE")

    valid = [(a, b, c) for a, b, _x, c in pairs if a and b]
    n = sum(c for _a, _b, c in valid)
    kappa = 0.0
    if n:
        po = sum(c for a, b, c in valid if a == b) / n
        pe = sum(
            (sum(c for a, _b, c in valid if a == cat) / n) * (sum(c for _a, b, c in valid if b == cat) / n)
            for cat in _VERDICTS
        )
        if pe < 1.0:
            kappa = round(max(-1.0, min(1.0, (po - pe) / (1.0 - pe))), 2)
        else:
            kappa = 1.0 if po == 1.0 else 0.0

    tp, fp, fn, tn = agreed_tp, threat_rescue, benign_override, agreed_fp
    accuracy = _pct(tp + tn, tp + fp + fn + tn)
    precision = _pct(tp, tp + fp)
    recall = _pct(tp, tp + fn)
    mean_latency = round(float(avg_ms) / 1000.0, 2) if avg_ms else 0.0

    # --- daily override trendline
    trend = []
    for day, day_decisions, day_overrides, day_closed in day_rows:
        exemplars = sum(1 for d in exemplar_days if d <= day)
        trend.append({
            "date": day.isoformat(),
            "override_rate": _pct(day_overrides, day_decisions),
            "total_decisions": day_decisions,
            "total_closed": day_closed,
            "override_count": day_overrides,
            "active_exemplars": exemplars,
            "exemplar_count": exemplars,
        })

    return {
        "has_data": bool(decisions or sum(statuses.values())),
        "total_closed_decisions": closed,
        "total_closed": closed,
        "approved_count": approved,
        "overridden_count": overridden,
        "ai_agreement_rate": agreement_rate,
        "agreement_rate": agreement_rate,
        "cohens_kappa": kappa,
        "human_override_rate": override_rate,
        "override_rate": override_rate,
        "escalation_count": escalated,
        "escalated_rate": escalated_rate,
        "manual_fallback_count": manual,
        "manual_triage_rate": manual_rate,
        "guardrail_interventions": floors + abstentions + injections,
        "guardrail_intervention_rate": _pct(interventions, assessed),
        "mean_triage_latency_seconds": mean_latency,
        "mean_latency_seconds": mean_latency,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "confusion_matrix": {
            "tp_tp": agreed_tp,
            "tp_fp_overridden": benign_override,
            "fp_tp_overridden": threat_rescue,
            "fp_fp": agreed_fp,
        },
        "agreement_matrix": {
            "agreed_true_positive": agreed_tp,
            "agreed_false_positive": agreed_fp,
            "analyst_overrode_to_tp": threat_rescue,
            "analyst_overrode_to_fp": benign_override,
            "agreed_tp": agreed_tp,
            "agreed_fp": agreed_fp,
            "threat_rescue": threat_rescue,
            "benign_filter": benign_override,
        },
        "trendline": trend,
        "override_trend": trend,
        "override_trendline": trend,
        # No table records why an analyst overrode, so root causes cannot be computed.
        "override_root_causes": [],
        "root_causes_dict": {},
        "severity_deltas": {
            "low_to_critical": d_low,
            "medium_to_high": d_medium,
            "high_to_critical": d_high,
            "tp_to_fp": benign_override,
            "fp_to_tp": threat_rescue,
            "safety_floor_count": floors,
            "abstention_count": abstentions,
            "injection_intercept_count": injections,
        },
        "guardrail_breakdown": {
            "safety_floor_interventions": floors,
            "abstention_fallbacks": abstentions,
            "prompt_injection_flags": injections,
            "safety_floor": floors,
            "abstention": abstentions,
            "injection_strip": injections,
        },
    }


def build_audit_csv(db: Session, start: Optional[date] = None, end: Optional[date] = None) -> str:
    """The audit trail as CSV, optionally limited to start..end (both days inclusive, UTC)."""
    clauses, params = [], {}
    if start:
        clauses.append("a.created_at >= :start")
        params["start"] = datetime.combine(start, time.min, tzinfo=timezone.utc)
    if end:
        clauses.append("a.created_at < :end")
        params["end"] = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(_CSV_HEADER)
    for r in db.execute(text(_SQL_CSV.format(where=where)), params):
        writer.writerow([
            str(r[0]), str(r[1]), r[2], r[3], r[4], r[5],
            r[6] or "SOC Analyst", r[7] or "Analyst", r[8],
            r[9] or "—", r[10] or "—", r[11] or "—", r[12] or "—",
            "TRUE" if r[13] else "FALSE", r[14],
        ])
    return out.getvalue()