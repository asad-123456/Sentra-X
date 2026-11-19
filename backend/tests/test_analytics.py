"""FR-7 analytics: AC-14 access rules, computed (never invented) figures, and the 50k benchmark."""
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.main import app
from app.services.analytics_service import build_analytics, build_audit_csv

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax_triage_test"
)
RULE = "TST-FR7"
client = TestClient(app)


# --- access rules (AC-14), against the seeded dev database ---------------------------
def _login(username: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "sentrax2026"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_an_analyst_gets_403_on_analytics_and_on_the_csv():
    headers = _login("analyst_01")
    assert client.get("/api/v1/analytics?range=30d", headers=headers).status_code == 403
    assert client.get("/api/v1/analytics/export-csv", headers=headers).status_code == 403


def test_a_team_lead_can_read_90_days_but_not_91():
    headers = _login("teamlead_mercer")
    assert client.get("/api/v1/analytics?range=90d", headers=headers).status_code == 200
    assert client.get("/api/v1/analytics?range=91d", headers=headers).status_code == 422
    too_long = "/api/v1/analytics/export-csv?start_date=2026-01-01&end_date=2026-06-01"
    assert client.get(too_long, headers=headers).status_code == 422


# --- calculations, against the migrated test database --------------------------------
@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL, pool_pre_ping=True)
    if not (eng.url.database or "").endswith("_test"):
        eng.dispose()
        pytest.fail("refusing to run: the database name must end in _test")
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1 FROM alerts LIMIT 1"))
    except Exception as exc:
        eng.dispose()
        pytest.skip(f"test database not reachable or not migrated ({type(exc).__name__})")
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    conn = engine.connect()
    outer = conn.begin()
    sess = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield sess
    finally:
        sess.close()
        outer.rollback()
        conn.close()


def make_user(session) -> uuid.UUID:
    uid = uuid.uuid4()
    session.execute(
        text("INSERT INTO users (id, username, email, password_hash, role) "
             "VALUES (:id, :u, :e, 'x', 'Analyst')"),
        {"id": uid, "u": f"u-{uid.hex[:10]}", "e": f"{uid.hex[:10]}@test.local"},
    )
    return uid


def make_agent(session) -> str:
    agent = f"fr7-{uuid.uuid4().hex[:8]}"
    session.execute(
        text("INSERT INTO assets (agent_id, hostname, criticality_tier) VALUES (:a, :a, 'MEDIUM')"),
        {"a": agent},
    )
    return agent


def add_alert(session, agent, status) -> uuid.UUID:
    alert_id = uuid.uuid4()
    session.execute(
        text("""INSERT INTO alerts (id, wazuh_alert_id, rule_id, rule_level, rule_description,
                                    agent_id, agent_name, status, alert_timestamp)
                VALUES (:id, :wid, :rule, 10, 'fr7 test', :agent, 'host', :status, now())"""),
        {"id": alert_id, "wid": f"fr7-{alert_id.hex[:12]}", "rule": RULE, "agent": agent, "status": status},
    )
    return alert_id


def add_assessment(session, alert_id, verdict, floor, latency_ms):
    session.execute(
        text("""INSERT INTO ai_assessments (alert_id, raw_verdict, raw_severity, effective_verdict,
                    effective_severity, confidence_score, explanation, safety_floor_triggered,
                    inference_latency_ms, latency_ms)
                VALUES (:id, :v, 'LOW', :v, 'HIGH', 0.9, 'x', :floor, :lat, :lat)"""),
        {"id": alert_id, "v": verdict, "floor": floor, "lat": latency_ms},
    )


def add_audit(session, alert_id, user_id, action, previous, final):
    session.execute(
        text("""INSERT INTO analyst_decisions_audit (alert_id, user_id, action_taken, previous_verdict,
                    previous_severity, final_verdict, final_severity, rationale)
                VALUES (:a, :u, :act, :pv, :ps, :fv, :fs, 'fr7 test rationale')"""),
        {"a": alert_id, "u": user_id, "act": action,
         "pv": previous[0], "ps": previous[1], "fv": final[0], "fs": final[1]},
    )


def test_every_figure_is_computed_from_the_data(session):
    user, agent = make_user(session), make_agent(session)
    a = add_alert(session, agent, "CLOSED")          # analyst approved the AI's true positive
    b = add_alert(session, agent, "CLOSED")          # analyst overrode a false positive to critical
    c = add_alert(session, agent, "ESCALATED")
    add_alert(session, agent, "NEEDS_MANUAL_TRIAGE")
    add_assessment(session, a, "TRUE_POSITIVE", True, 2000)
    add_assessment(session, b, "FALSE_POSITIVE", False, 4000)
    session.execute(
        text("INSERT INTO evidence_packs (alert_id, pack_json, injection_suspect) "
             "VALUES (:id, CAST('{}' AS jsonb), true)"), {"id": a})
    add_audit(session, a, user, "APPROVE", ("TRUE_POSITIVE", "HIGH"), ("TRUE_POSITIVE", "HIGH"))
    add_audit(session, b, user, "OVERRIDE", ("FALSE_POSITIVE", "LOW"), ("TRUE_POSITIVE", "CRITICAL"))
    add_audit(session, c, user, "ESCALATE", (None, None), (None, None))

    m = build_analytics(session, 30, rule_id=RULE)
    assert (m["total_closed"], m["escalation_count"], m["manual_fallback_count"]) == (2, 1, 1)
    assert m["escalated_rate"] == 33.3 and m["manual_triage_rate"] == 25.0
    assert m["override_rate"] == 50.0 and m["ai_agreement_rate"] == 50.0
    assert m["agreement_matrix"]["agreed_tp"] == 1 and m["agreement_matrix"]["threat_rescue"] == 1
    assert (m["accuracy"], m["precision"], m["recall"]) == (50.0, 50.0, 100.0)
    assert m["cohens_kappa"] == 0.0
    assert m["guardrail_interventions"] == 2 and m["guardrail_intervention_rate"] == 50.0
    assert m["mean_triage_latency_seconds"] == 3.0
    assert m["severity_deltas"]["low_to_critical"] == 1
    assert len(m["override_trend"]) == 1
    day = m["override_trend"][0]
    assert (day["total_decisions"], day["override_count"], day["override_rate"]) == (2, 1, 50.0)


def test_no_data_gives_zeros_and_empty_lists_not_invented_numbers(session):
    m = build_analytics(session, 30, rule_id="NO-SUCH-RULE")
    assert m["has_data"] is False
    for key in ("cohens_kappa", "accuracy", "precision", "recall", "mean_triage_latency_seconds",
                "escalated_rate", "manual_triage_rate", "ai_agreement_rate"):
        assert m[key] == 0.0
    assert m["override_trend"] == [] and m["override_root_causes"] == []


def test_ac14_50000_closed_alerts_analytics_under_5s_and_a_single_day_csv_under_10s(session):
    token = uuid.uuid4().hex[:8]
    agent, user = make_agent(session), make_user(session)
    n = 50_000
    session.execute(text("""
        INSERT INTO alerts (wazuh_alert_id, rule_id, rule_level, rule_description, agent_id,
                            agent_name, status, alert_timestamp)
        SELECT 'bench-__T__-' || CAST(g AS text), 'BENCH-' || CAST(g % 20 AS text), 4 + (g % 12),
               'benchmark alert', '__AGENT__', 'host', 'CLOSED', now()
        FROM generate_series(1, :n) AS g
    """.replace("__T__", token).replace("__AGENT__", agent)), {"n": n})
    session.execute(text("""
        INSERT INTO analyst_decisions_audit (alert_id, user_id, action_taken, previous_verdict,
                    previous_severity, final_verdict, final_severity, rationale)
        SELECT al.id, CAST(:uid AS uuid),
               CASE WHEN random() < 0.2 THEN 'OVERRIDE' ELSE 'APPROVE' END,
               'FALSE_POSITIVE', 'LOW', 'TRUE_POSITIVE', 'HIGH', 'benchmark decision'
        FROM alerts al WHERE al.agent_id = '__AGENT__'
    """.replace("__AGENT__", agent)), {"uid": user})
    session.execute(text("""
        INSERT INTO ai_assessments (alert_id, raw_verdict, raw_severity, effective_verdict,
                    effective_severity, confidence_score, explanation, safety_floor_triggered,
                    inference_latency_ms, latency_ms)
        SELECT al.id, 'FALSE_POSITIVE', 'LOW', 'TRUE_POSITIVE', 'HIGH', 0.9, 'benchmark',
               (al.rule_level >= 12), 1200, 1200
        FROM alerts al WHERE al.agent_id = '__AGENT__'
    """.replace("__AGENT__", agent)))
    for table in ("alerts", "analyst_decisions_audit", "ai_assessments"):
        session.execute(text(f"ANALYZE {table}"))

    start = time.perf_counter()
    metrics = build_analytics(session, 30)
    analytics_seconds = time.perf_counter() - start
    assert metrics["total_closed"] >= n
    assert analytics_seconds <= 5.0, f"analytics took {analytics_seconds:.1f}s"

    today = datetime.now(timezone.utc).date()
    start = time.perf_counter()
    csv_text = build_audit_csv(session, today, today)
    csv_seconds = time.perf_counter() - start
    assert len(csv_text.splitlines()) >= n + 1
    assert csv_seconds <= 10.0, f"CSV took {csv_seconds:.1f}s"