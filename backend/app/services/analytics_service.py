"""Database-backed operational analytics for a UTC reporting window."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

_BINARY = ("TRUE_POSITIVE", "FALSE_POSITIVE")
_CLOSURES = ("APPROVE", "OVERRIDE", "MANUAL_TRIAGE_CLOSURE", "RESOLVE_ESCALATION")
_RULE_FILTER = " AND al.rule_id = :rule_id"

_SQL_ACTIONS = """
    SELECT a.action_taken, count(*)
    FROM analyst_decisions_audit a JOIN alerts al ON al.id = a.alert_id
    WHERE a.created_at >= :start AND a.created_at < :end{rule}
    GROUP BY a.action_taken
"""
_SQL_STATUSES = """
    SELECT al.status, count(*) FROM alerts al
    WHERE al.ingested_at >= :start AND al.ingested_at < :end{rule}
    GROUP BY al.status
"""
_SQL_GUARDRAILS = """
    SELECT count(*) FILTER (WHERE s.safety_floor_triggered),
           count(*) FILTER (WHERE s.abstention_triggered),
           count(*) FILTER (WHERE s.safety_floor_triggered OR s.abstention_triggered),
           count(*) FILTER (WHERE p.injection_suspect),
           avg(COALESCE(s.inference_latency_ms, s.latency_ms))
    FROM alerts al
    LEFT JOIN ai_assessments s ON s.alert_id = al.id
    LEFT JOIN evidence_packs p ON p.alert_id = al.id
    WHERE al.ingested_at >= :start AND al.ingested_at < :end{rule}
"""
_SQL_PAIRS = """
    SELECT a.previous_verdict, a.final_verdict, count(*)
    FROM analyst_decisions_audit a JOIN alerts al ON al.id = a.alert_id
    WHERE a.created_at >= :start AND a.created_at < :end{rule}
      AND a.action_taken IN ('APPROVE', 'OVERRIDE', 'MANUAL_TRIAGE_CLOSURE', 'RESOLVE_ESCALATION')
      AND a.previous_verdict IN ('TRUE_POSITIVE', 'FALSE_POSITIVE')
      AND a.final_verdict IN ('TRUE_POSITIVE', 'FALSE_POSITIVE')
    GROUP BY a.previous_verdict, a.final_verdict
"""
_SQL_DELTAS = """
    SELECT count(*) FILTER (WHERE a.previous_severity = 'LOW' AND a.final_severity = 'CRITICAL'),
           count(*) FILTER (WHERE a.previous_severity = 'MEDIUM' AND a.final_severity = 'HIGH'),
           count(*) FILTER (WHERE a.previous_severity = 'HIGH' AND a.final_severity = 'CRITICAL')
    FROM analyst_decisions_audit a JOIN alerts al ON al.id = a.alert_id
    WHERE a.action_taken = 'OVERRIDE' AND a.created_at >= :start AND a.created_at < :end{rule}
"""
_SQL_TREND = """
    SELECT CAST(a.created_at AT TIME ZONE 'UTC' AS date) AS day,
           count(*) FILTER (WHERE a.action_taken IN ('APPROVE', 'OVERRIDE')) AS decisions,
           count(*) FILTER (WHERE a.action_taken = 'OVERRIDE'),
           count(*) FILTER (WHERE a.action_taken IN
               ('APPROVE', 'OVERRIDE', 'MANUAL_TRIAGE_CLOSURE', 'RESOLVE_ESCALATION'))
    FROM analyst_decisions_audit a JOIN alerts al ON al.id = a.alert_id
    WHERE a.created_at >= :start AND a.created_at < :end{rule}
    GROUP BY 1
HAVING count(*) FILTER (WHERE a.action_taken IN
    ('APPROVE', 'OVERRIDE', 'MANUAL_TRIAGE_CLOSURE', 'RESOLVE_ESCALATION')) > 0
    ORDER BY 1
"""
_SQL_EXEMPLARS = """
    SELECT CAST(created_at AT TIME ZONE 'UTC' AS date) AS day, count(*)
    FROM feedback_exemplars
    WHERE created_at < :end{rule}
    GROUP BY 1 ORDER BY 1
"""


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


def _agreement_metrics(tp: int, fp: int, fn: int, tn: int) -> dict:
    total = tp + fp + fn + tn
    expected = (tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)
    denominator = total**2 - expected
    return {
        "agreement_rate": _percent(tp + tn, total),
        "accuracy": _percent(tp + tn, total),
        "precision": _percent(tp, tp + fp),
        "recall": _percent(tp, tp + fn),
        "cohens_kappa": round(((tp + tn) * total - expected) / denominator, 2) if denominator else None,
        "comparison_count": total,
    }


def utc_bounds(first_day: date, last_day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(first_day, time.min, tzinfo=timezone.utc),
        datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=timezone.utc),
    )


def build_analytics(db: Session, first_day: date, last_day: date, rule_id: str | None = None) -> dict:
    start, end = utc_bounds(first_day, last_day)
    params = {"start": start, "end": end}
    if rule_id:
        params["rule_id"] = rule_id

    def run(sql: str):
        return db.execute(text(sql.format(rule=_RULE_FILTER if rule_id else "")), params)

    actions = {action: count for action, count in run(_SQL_ACTIONS)}
    statuses = {status: count for status, count in run(_SQL_STATUSES)}
    floors, abstentions, interventions, injections, avg_ms = run(_SQL_GUARDRAILS).one()
    pairs = {(ai, human): count for ai, human, count in run(_SQL_PAIRS)}
    positive, negative = _BINARY
    tp = pairs.get((positive, positive), 0)
    fp = pairs.get((positive, negative), 0)
    fn = pairs.get((negative, positive), 0)
    tn = pairs.get((negative, negative), 0)
    metrics = _agreement_metrics(tp, fp, fn, tn)
    low, medium, high = run(_SQL_DELTAS).one()
    observed = sum(statuses.values())
    escalated = statuses.get("ESCALATED", 0)
    manual = statuses.get("NEEDS_MANUAL_TRIAGE", 0)
    approved = actions.get("APPROVE", 0)
    overrides = actions.get("OVERRIDE", 0)
    closed = sum(actions.get(action, 0) for action in _CLOSURES)
    override_rate = _percent(overrides, approved + overrides)
    latency = round(float(avg_ms) / 1000, 2) if avg_ms is not None else None

    daily = run(_SQL_TREND).all()
    trend = []
    if daily:
        exemplar_sql = _SQL_EXEMPLARS.format(rule=" AND rule_id = :rule_id" if rule_id else "")
        exemplar_days = iter(db.execute(text(exemplar_sql), params))
        created = next(exemplar_days, None)
        cumulative = 0
        for day, decisions, day_overrides, day_closed in daily:
            while created is not None and created[0] <= day:
                cumulative += created[1]
                created = next(exemplar_days, None)
            trend.append({
                "date": day.isoformat(),
                "total_decisions": decisions,
                "total_closed": day_closed,
                "override_count": day_overrides,
                "override_rate": _percent(day_overrides, decisions),
                "exemplar_count": cumulative,
            })

    return {
        **metrics,
        "report_window": {"start_date": first_day.isoformat(), "end_date": last_day.isoformat(), "rule_id": rule_id},
        "audit_event_count": sum(actions.values()),
        "total_closed": closed,
        "total_closed_decisions": closed,
        "approved_count": approved,
        "overridden_count": overrides,
        "ai_agreement_rate": metrics["agreement_rate"],
        "override_rate": override_rate,
        "human_override_rate": override_rate,
        "escalation_count": escalated,
        "escalated_rate": _percent(escalated, observed),
        "manual_fallback_count": manual,
        "manual_triage_rate": _percent(manual, observed),
        "guardrail_interventions": interventions,
        "mean_latency_seconds": latency,
        "mean_triage_latency_seconds": latency,
        "confusion_matrix": {"tp_tp": tp, "tp_fp_overridden": fp, "fp_tp_overridden": fn, "fp_fp": tn},
        "agreement_matrix": {
            "agreed_true_positive": tp, "agreed_false_positive": tn,
            "analyst_overrode_to_tp": fn, "analyst_overrode_to_fp": fp,
            "agreed_tp": tp, "agreed_fp": tn, "threat_rescue": fn, "benign_filter": fp,
        },
        "trendline": trend,
        "override_trend": trend,
        "override_trendline": trend,
        "override_root_causes": [],
        "root_causes_dict": {},
        "severity_deltas": {
            "low_to_critical": low, "medium_to_high": medium, "high_to_critical": high,
            "tp_to_fp": fp, "fp_to_tp": fn, "safety_floor_count": floors,
            "abstention_count": abstentions, "injection_intercept_count": injections,
        },
        "guardrail_breakdown": {
            "safety_floor_interventions": floors, "abstention_fallbacks": abstentions,
            "prompt_injection_flags": injections, "safety_floor": floors, "abstention": abstentions,
            "injection_strip": injections,
        },
    }
