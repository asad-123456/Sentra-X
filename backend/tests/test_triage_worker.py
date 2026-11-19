"""Integration tests for the triage worker (Part 6B) on the migrated test database."""
import json
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.services.llm_adapter import MockAdapter
from app.worker.jobs import TriageQueue
from app.worker.triage_worker import TriageWorker, process_alert

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax_triage_test"
)
REF = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
LOG = {"full_log": "Failed password for root from 203.0.113.9 port 4242 ssh2"}


@pytest.fixture(scope="module")
def factory():
    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
    if not (engine.url.database or "").endswith("_test"):
        engine.dispose()
        pytest.fail("refusing to run: the database name must end in _test")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM alerts LIMIT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"test database not reachable or not migrated ({type(exc).__name__})")
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


@pytest.fixture()
def new_alert(factory):
    agents, alerts = [], []

    def make(level=12, status="PENDING_REVIEW"):
        agent_id, alert_id = f"wk-{uuid.uuid4().hex[:10]}", uuid.uuid4()
        with factory() as s:
            s.execute(
                text("INSERT INTO assets (agent_id, hostname, criticality_tier) VALUES (:a, :a, 'MEDIUM')"),
                {"a": agent_id},
            )
            s.execute(
                text("""
                    INSERT INTO alerts (id, wazuh_alert_id, rule_id, rule_level, rule_description,
                                        agent_id, agent_name, raw_payload, status, alert_timestamp)
                    VALUES (:id, :wid, '5710', :level, 'test rule', :agent, 'host-1',
                            CAST(:raw AS jsonb), :status, :ts)
                """),
                {"id": alert_id, "wid": f"wk-{alert_id.hex[:12]}", "level": level,
                 "agent": agent_id, "raw": json.dumps(LOG), "status": status, "ts": REF},
            )
            s.commit()
        agents.append(agent_id)
        alerts.append(alert_id)
        return alert_id

    yield make
    with factory() as s:
        for a in alerts:
            s.execute(text("DELETE FROM alerts WHERE id = :id"), {"id": a})
        for g in agents:
            s.execute(text("DELETE FROM assets WHERE agent_id = :a"), {"a": g})
        s.commit()


def row(factory, alert_id):
    """(status, retry_count, evidence packs, assessments)"""
    with factory() as s:
        status, retries = s.execute(
            text("SELECT status, retry_count FROM alerts WHERE id = :id"), {"id": alert_id}
        ).one()
        packs = s.execute(
            text("SELECT count(*) FROM evidence_packs WHERE alert_id = :id"), {"id": alert_id}
        ).scalar_one()
        assessments = s.execute(
            text("SELECT count(*) FROM ai_assessments WHERE alert_id = :id"), {"id": alert_id}
        ).scalar_one()
    return status, retries, packs, assessments


def test_a_pending_alert_is_triaged(factory, new_alert):
    alert_id = new_alert(level=12)
    assert process_alert(alert_id, MockAdapter(), session_factory=factory) == "AWAITING_ANALYST"
    assert row(factory, alert_id) == ("AWAITING_ANALYST", 0, 1, 1)


def test_an_adapter_failure_goes_to_manual_triage_and_keeps_the_pack(factory, new_alert):
    alert_id = new_alert()
    adapter = MockAdapter(failure_mode="http_400")      # not retried, so the test is fast
    assert process_alert(alert_id, adapter, session_factory=factory) == "NEEDS_MANUAL_TRIAGE"
    assert row(factory, alert_id) == ("NEEDS_MANUAL_TRIAGE", 0, 1, 0)


def test_a_decided_alert_is_left_alone(factory, new_alert):
    alert_id = new_alert(status="CLOSED")
    assert process_alert(alert_id, MockAdapter(), session_factory=factory) is None
    assert row(factory, alert_id) == ("CLOSED", 0, 0, 0)


def test_a_crash_sends_the_alert_to_manual_triage(factory, new_alert):
    alert_id = new_alert()

    def broken(session, agent_id):
        raise RuntimeError("boom")

    result = process_alert(alert_id, MockAdapter(), session_factory=factory, tier_lookup=broken)
    assert result == "NEEDS_MANUAL_TRIAGE"
    assert row(factory, alert_id)[0] == "NEEDS_MANUAL_TRIAGE"


def test_sweep_recovers_pending_alerts_while_queue_is_busy_without_duplicates(factory, new_alert):
    pending, closed = new_alert(), new_alert(status="CLOSED")
    q = TriageQueue()
    fresh_job = uuid.uuid4()
    q.enqueue(fresh_job)
    worker = TriageWorker(MockAdapter(), workers=1, sweep_seconds=60,
                          session_factory=factory, work_queue=q)
    assert worker.sweep_once() >= 1
    assert worker.sweep_once() == 0
    queued = []
    while not q.empty():
        queued.append(q.get())
    assert queued[0] == fresh_job and queued.count(pending) == 1 and closed not in queued


def test_worker_threads_process_a_queued_alert_and_ignore_a_duplicate(factory, new_alert):
    alert_id = new_alert(level=12)
    q = TriageQueue()
    worker = TriageWorker(MockAdapter(), workers=2, sweep_seconds=60,
                          session_factory=factory, work_queue=q)
    worker.start()
    try:
        q.enqueue(alert_id)
        q.enqueue(alert_id)
        deadline = time.time() + 10
        while time.time() < deadline and row(factory, alert_id)[0] != "AWAITING_ANALYST":
            time.sleep(0.1)
    finally:
        worker.stop()
    assert row(factory, alert_id) == ("AWAITING_ANALYST", 0, 1, 1)
