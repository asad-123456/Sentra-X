"""FR-7 metric regressions and opt-in checks on a migrated PostgreSQL database."""
import csv
from datetime import date, datetime, timedelta, timezone
import io
import os
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.routers.analytics import export_audit_csv, get_analytics
from app.services.analytics_service import _agreement_metrics, build_analytics
from fastapi import HTTPException


def test_agreement_uses_model_predictions_as_the_confusion_matrix_axis():
    metrics = _agreement_metrics(tp=1, fp=0, fn=1, tn=0)
    assert metrics == {
        "agreement_rate": 50.0,
        "accuracy": 50.0,
        "precision": 100.0,
        "recall": 50.0,
        "cohens_kappa": 0.0,
        "comparison_count": 2,
    }


def test_undefined_metrics_are_null():
    assert _agreement_metrics(0, 0, 0, 0)["precision"] is None
    assert _agreement_metrics(3, 0, 0, 0)["cohens_kappa"] is None


@pytest.mark.parametrize("value", ["0d", "91d", "all", "last90days"])
def test_summary_rejects_unsupported_ranges_before_querying(value):
    with pytest.raises(HTTPException, match="90 days") as error:
        get_analytics(range=value, date_range=None, rule_id=None, db=None)
    assert error.value.status_code == 422


def test_export_requires_both_dates_and_limits_their_span():
    day = date(2026, 1, 1)
    for end in (None, date(2025, 12, 31), date(2026, 4, 1)):
        with pytest.raises(HTTPException) as error:
            export_audit_csv(start_date=day, end_date=end, rule_id=None, db=None)
        assert error.value.status_code == 422


@pytest.fixture()
def session(contributor_test_engine):
    with contributor_test_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


def seed_closed(session, count, day, *, split_rule=False, rule=None, action="APPROVE"):
    marker = uuid.uuid4().hex[:10]
    target, other = rule or f"fr7-{marker}", f"other-{marker}"
    user = uuid.uuid4()
    params = {
        "prefix": marker, "agent": f"fr7-{marker}", "user": user, "email": f"fr7-{marker}@example.test",
        "target": target, "other": other, "count": count, "day": day, "split_rule": split_rule, "action": action,
    }
    session.execute(text("""
        INSERT INTO users (id, username, email, password_hash, role)
        VALUES (:user, :agent, :email, 'unused', 'Analyst')
    """), params)
    session.execute(text("INSERT INTO assets (agent_id, hostname, criticality_tier) VALUES (:agent, :agent, 'MEDIUM')"), params)
    session.execute(text("""
        WITH seeded AS (
            INSERT INTO alerts (wazuh_alert_id, rule_id, rule_level, rule_description, agent_id,
                                agent_name, status, alert_timestamp, ingested_at)
            SELECT :prefix || '-' || CAST(n AS text), CASE WHEN n = 3 AND :split_rule THEN :other ELSE :target END,
                   5, 'analytics test', :agent, :agent, 'CLOSED', :day, :day
            FROM generate_series(1, :count) AS n
            RETURNING id, wazuh_alert_id
        )
        INSERT INTO analyst_decisions_audit (alert_id, user_id, action_taken, previous_verdict,
                previous_severity, final_verdict, final_severity, rationale, created_at)
        SELECT id, :user,
               CASE WHEN wazuh_alert_id = :prefix || '-2' THEN 'OVERRIDE' ELSE :action END,
               CASE WHEN wazuh_alert_id = :prefix || '-2' THEN 'FALSE_POSITIVE' ELSE 'TRUE_POSITIVE' END,
               'LOW', 'TRUE_POSITIVE', 'CRITICAL', 'analytics test', :day
        FROM seeded
    """), params)
    return target


def test_summary_window_matches_csv_at_utc_boundaries(session):
    start = datetime(2026, 11, 20, tzinfo=timezone.utc)
    rule = seed_closed(session, 1, start, action="MANUAL_TRIAGE_CLOSURE")
    seed_closed(session, 1, start - timedelta(microseconds=1), rule=rule)
    seed_closed(session, 1, start + timedelta(days=1), rule=rule)
    seed_closed(session, 1, start)

    summary = build_analytics(session, start.date(), start.date(), rule)
    assert summary["report_window"] == {"start_date": "2026-11-20", "end_date": "2026-11-20", "rule_id": rule}
    assert summary["audit_event_count"] == summary["total_closed"] == 1
    assert summary["trendline"][0]["total_closed"] == 1
    assert summary["trendline"][0]["override_rate"] is None
    response = export_audit_csv(start_date=start.date(), end_date=start.date(), rule_id=rule, db=session)
    [row] = list(csv.DictReader(io.StringIO(response.body.decode())))
    assert row["Timestamp"] == start.isoformat()
    assert row["Rule ID"] == rule and row["Action Taken"] == "MANUAL_TRIAGE_CLOSURE"


def test_analytics_uses_historical_verdicts_and_filters_csv(session):
    day = datetime(2026, 11, 19, 23, 59, 59, tzinfo=timezone.utc)
    rule = seed_closed(session, 3, day, split_rule=True)
    # Deliberately no assessment rows. Historical decisions still have their original AI verdicts.
    summary = build_analytics(session, day.date(), day.date(), rule)
    assert summary["total_closed"] == 2 and summary["overridden_count"] == 1
    assert summary["precision"] == 100.0 and summary["recall"] == 50.0
    assert summary["mean_latency_seconds"] is None
    assert summary["trendline"][0]["date"] == "2026-11-19"
    assert summary["trendline"][0]["total_decisions"] == 2
    assert summary["severity_deltas"]["low_to_critical"] == 1

    next_day = date(2026, 11, 20)
    outside = build_analytics(session, next_day, next_day, rule)
    assert outside["total_closed"] == 0 and outside["agreement_rate"] is None
    assert outside["trendline"] == []
    response = export_audit_csv(start_date=day.date(), end_date=day.date(), rule_id=rule, db=session)
    assert len(response.body.splitlines()) == 3
    outside = export_audit_csv(start_date=next_day, end_date=next_day, rule_id=rule, db=session)
    assert len(outside.body.splitlines()) == 1


@pytest.mark.skipif(os.getenv("SENTRAX_RUN_PERF_TESTS") != "1", reason="enable the 50k reporting benchmark explicitly")
def test_50k_closed_alerts_and_single_day_export(session):
    day = datetime.now(timezone.utc)
    rule = seed_closed(session, 50_000, day)
    start = time.perf_counter()
    summary = build_analytics(session, day.date(), day.date(), rule)
    assert summary["total_closed"] == 50_000
    assert time.perf_counter() - start <= 5
    start = time.perf_counter()
    response = export_audit_csv(start_date=day.date(), end_date=day.date(), rule_id=rule, db=session)
    assert len(response.body.splitlines()) == 50_001
    assert time.perf_counter() - start <= 10
