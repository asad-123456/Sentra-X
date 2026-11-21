from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text

from app.auth import create_access_token
from app.config import settings
from app.database import SyncSessionLocal, get_db, sync_engine
from app.main import app
from app.models import AIAssessment, Alert, AnalystDecisionAudit, Asset, EvidencePack, FeedbackExemplar, User
from app.routers import alerts
from app.services.llm_adapter import MockAdapter
from app.worker import triage_worker


MANUAL_DISPOSITION = {
    "action": "MANUAL_TRIAGE_CLOSURE",
    "final_verdict": "FALSE_POSITIVE",
    "final_severity": "LOW",
    "rationale": "  Reviewed the synthetic telemetry and confirmed benign activity.  ",
}


@pytest.fixture
def scenario(application_test_database):
    tag = f"transition-{uuid4().hex[:10]}"
    with SyncSessionLocal.begin() as db:
        actor = User(username=tag, email=f"{tag}@example.test", password_hash="unused", role="Analyst")
        db.add_all([actor, Asset(agent_id=tag, hostname=tag)])
        db.flush()
        token = create_access_token({"sub": str(actor.id)})

    def seed(status="PENDING_REVIEW", verdict=None):
        with SyncSessionLocal.begin() as db:
            alert = Alert(
                wazuh_alert_id=uuid4().hex, agent_id=tag, rule_id="5710", rule_level=5,
                rule_description="Synthetic test", status=status,
                raw_payload={"full_log": "Synthetic authentication failure for test user"},
            )
            db.add(alert)
            db.flush()
            if verdict:
                db.add(AIAssessment(
                    alert_id=alert.id, raw_verdict="TRUE_POSITIVE", raw_severity="LOW",
                    effective_verdict=verdict, effective_severity="HIGH", confidence_score=0.5,
                    abstention_triggered=verdict == "NEEDS_ANALYST_REVIEW", explanation="Synthetic assessment",
                ))
            return alert.id

    def decide(alert_id, payload):
        return TestClient(app).post(
            f"/api/v1/alerts/{alert_id}/decision", headers={"Authorization": f"Bearer {token}"}, json=payload,
        )

    return seed, decide


def stored_state(alert_id):
    with SyncSessionLocal() as db:
        alert = db.get(Alert, alert_id)
        audits = db.scalars(select(AnalystDecisionAudit).where(AnalystDecisionAudit.alert_id == alert_id)).all()
        return alert.status, alert.triage_generation, [audit.action_taken for audit in audits]


def test_pending_queue_row_can_lack_ip_assessment_and_mitre(scenario, monkeypatch):
    seed, _ = scenario
    alert_id = seed()
    with SyncSessionLocal() as db:
        source_id = db.get(Alert, alert_id).wazuh_alert_id
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    response = TestClient(app).get("/api/v1/alerts", params={"search": source_id})
    assert response.status_code == 200, response.text
    [row] = response.json()["items"]
    assert row["status"] == "PENDING_REVIEW"
    assert row["ip_address"] is None and row["effective_verdict"] is None
    assert row["mitre_techniques"] == []
    assert set(row["available_actions"]) == {"ESCALATE", "MANUAL_TRIAGE_CLOSURE"}


@pytest.mark.parametrize("missing", ["final_verdict", "final_severity", "rationale"])
def test_pending_manual_disposition_requires_explicit_values(scenario, missing):
    seed, decide = scenario
    alert_id = seed()
    incomplete = dict(MANUAL_DISPOSITION)
    incomplete.pop(missing)
    assert decide(alert_id, incomplete).status_code == 422
    assert stored_state(alert_id) == ("PENDING_REVIEW", 0, [])


@pytest.mark.parametrize("state", ["PENDING_REVIEW", "AWAITING_ANALYST"])
def test_approval_requires_an_assessed_alert(scenario, state):
    seed, decide = scenario
    alert_id = seed(state)
    response = decide(alert_id, {**MANUAL_DISPOSITION, "action": "APPROVE"})
    assert response.status_code == 422
    assert stored_state(alert_id) == (state, 0, [])


@pytest.mark.parametrize("verdict", ["TRUE_POSITIVE", "NEEDS_ANALYST_REVIEW"])
def test_approval_uses_assessment_severity_and_confirms_abstention(scenario, verdict):
    seed, decide = scenario
    alert_id = seed("AWAITING_ANALYST", verdict)
    if verdict == "NEEDS_ANALYST_REVIEW":
        assert decide(alert_id, {"action": "APPROVE"}).status_code == 422
        final = "FALSE_POSITIVE"
    else:
        assert decide(alert_id, {"action": "APPROVE", "final_verdict": "FALSE_POSITIVE"}).status_code == 409
        final = verdict
    assert decide(alert_id, {"action": "APPROVE", "final_verdict": final, "final_severity": "LOW"}).status_code == 409
    approved = decide(alert_id, {"action": "APPROVE", "final_verdict": final})
    assert approved.status_code == 200, approved.text
    assert approved.json()["previous_verdict"] == verdict
    assert approved.json()["final_verdict"] == final
    assert approved.json()["final_severity"] == "HIGH"


def test_two_concurrent_manual_closures_commit_one_audit(scenario):
    seed, decide = scenario
    alert_id = seed()
    simultaneous = Barrier(2, timeout=5)

    def align_selects(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT alerts.") and "FROM alerts" in statement:
            assert "FOR UPDATE" in statement
            simultaneous.wait()

    event.listen(sync_engine, "before_cursor_execute", align_selects)
    try:
        with ThreadPoolExecutor(2) as pool:
            pending = [pool.submit(decide, alert_id, MANUAL_DISPOSITION) for _ in range(2)]
            replies = [future.result(timeout=10) for future in pending]
    finally:
        event.remove(sync_engine, "before_cursor_execute", align_selects)
    assert sorted(reply.status_code for reply in replies) == [200, 422]
    assert stored_state(alert_id) == ("CLOSED", 0, ["MANUAL_TRIAGE_CLOSURE"])


@contextmanager
def pause_worker(alert_id, monkeypatch, *, crash=False):
    running, release = Event(), Event()
    paused_adapter = MockAdapter()
    run_pipeline = triage_worker.run_triage_pipeline

    def held_pipeline(inputs, adapter):
        if adapter is paused_adapter:
            running.set()
            if not release.wait(timeout=10) or crash:
                raise RuntimeError("Synthetic interruption")
        return run_pipeline(inputs, adapter)

    monkeypatch.setattr(triage_worker, "run_triage_pipeline", held_pipeline)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(triage_worker.process_alert, alert_id, paused_adapter)
        try:
            assert running.wait(timeout=5)
            yield future
        finally:
            release.set()


def test_pending_closure_wins_over_running_inference(scenario, monkeypatch):
    seed, decide = scenario
    alert_id = seed()
    with pause_worker(alert_id, monkeypatch) as older:
        response = decide(alert_id, {**MANUAL_DISPOSITION, "action": "MANUAL_TRIAGE_CLOSE"})
        assert response.status_code == 200, response.text
        assert response.json()["previous_verdict"] is None
        assert response.json()["rationale"] == MANUAL_DISPOSITION["rationale"].strip()
    assert older.result() is None
    assert stored_state(alert_id) == ("CLOSED", 0, ["MANUAL_TRIAGE_CLOSURE"])
    with SyncSessionLocal() as db:
        assert db.scalar(select(AIAssessment).where(AIAssessment.alert_id == alert_id)) is None
        assert db.scalar(select(EvidencePack).where(EvidencePack.alert_id == alert_id)) is None


@pytest.mark.parametrize("crash", [False, True])
def test_retry_supersedes_an_older_worker_result_or_crash(scenario, monkeypatch, crash):
    seed, decide = scenario
    alert_id = seed()
    enqueued_states = []
    monkeypatch.setattr(alerts, "enqueue_triage", lambda alert_id: enqueued_states.append(stored_state(alert_id)))
    with pause_worker(alert_id, monkeypatch, crash=crash) as older:
        assert triage_worker.process_alert(alert_id, MockAdapter(failure_mode="http_400")) == "NEEDS_MANUAL_TRIAGE"
        retry = decide(alert_id, {"action": "RETRY_AI"})
        assert retry.status_code == 200, retry.text
        assert retry.json()["final_verdict"] is None and retry.json()["final_severity"] is None
        assert enqueued_states == [("PENDING_REVIEW", 1, ["RETRY_AI"])]
        assert decide(alert_id, {"action": "RETRY_AI"}).status_code == 422
    assert older.result() is None
    assert stored_state(alert_id) == ("PENDING_REVIEW", 1, ["RETRY_AI"])
    assert triage_worker.process_alert(alert_id, MockAdapter()) == "AWAITING_ANALYST"
    assert decide(alert_id, MANUAL_DISPOSITION).status_code == 422
    assert stored_state(alert_id) == ("AWAITING_ANALYST", 1, ["RETRY_AI"])


def test_failed_commit_rolls_back_status_audit_and_exemplar(scenario, monkeypatch):
    seed, decide = scenario
    alert_id = seed()

    def fail_after_flush(db):
        db.flush()
        db.execute(text("SELECT 1 / 0"))

    def failing_db():
        with SyncSessionLocal() as db:
            event.listen(db, "before_commit", fail_after_flush)
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, failing_db)
    response = decide(alert_id, {**MANUAL_DISPOSITION, "save_as_exemplar": True})
    assert response.status_code == 500, response.text
    assert stored_state(alert_id) == ("PENDING_REVIEW", 0, [])
    with SyncSessionLocal() as db:
        assert db.scalar(select(FeedbackExemplar).where(FeedbackExemplar.source_alert_id == alert_id)) is None
