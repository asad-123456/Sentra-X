"""Opt-in FastAPI webhook-to-worker smoke test with a disposable PostgreSQL database."""
from datetime import datetime, timezone
from functools import partial
import hashlib
import hmac
import json
import random
import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import main
from app.auth import hash_password
from app.config import settings
from app.database import get_db
from app.ingestion import service as ingest_service
from app.ingestion.db_access import get_session_factory
from app.ingestion.wazuh_settings import get_wazuh_settings
from app.services.llm_adapter import MockAdapter
from app.worker import triage_worker
from app.worker.jobs import TriageQueue
from scripts.generate_replay import VALID, build_alert


def test_webhook_worker_permissions_and_evidence(contributor_test_engine, monkeypatch):
    factory = sessionmaker(bind=contributor_test_engine)
    work_queue = TriageQueue()
    tag = uuid.uuid4().hex[:10]
    agent = f"e2e-{tag}"
    lead, analyst = f"lead-{tag}", f"analyst-{tag}"
    password = uuid.uuid4().hex
    signing_key = uuid.uuid4().hex
    secret = uuid.uuid4().hex

    def db_dependency():
        with factory() as session:
            yield session

    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "SECRET_KEY", signing_key)
    monkeypatch.setattr(get_wazuh_settings(), "WAZUH_INGEST_MODE", "replay")
    monkeypatch.setattr(get_wazuh_settings(), "WAZUH_MIN_LEVEL", 4)
    monkeypatch.setattr(get_wazuh_settings(), "WAZUH_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(triage_worker.get_worker_settings(), "TRIAGE_ENABLED", True)
    monkeypatch.setattr(triage_worker.get_worker_settings(), "TRIAGE_WORKERS", 1)
    monkeypatch.setattr(triage_worker, "build_adapter", lambda _: MockAdapter())
    monkeypatch.setattr(triage_worker, "TriageWorker", partial(triage_worker.TriageWorker,
                        session_factory=factory, work_queue=work_queue))
    monkeypatch.setattr(ingest_service, "enqueue_triage", work_queue.enqueue)
    monkeypatch.setitem(main.app.dependency_overrides, get_db, db_dependency)
    monkeypatch.setitem(main.app.dependency_overrides, get_session_factory, lambda: factory)

    with factory.begin() as session:
        for name, role in ((lead, "TeamLead"), (analyst, "Analyst")):
            session.execute(text("""
                INSERT INTO users (username, email, password_hash, role, is_active)
                VALUES (:name, :email, :password, :role, true)
            """), {"name": name, "email": f"{name}@example.test", "password": hash_password(password), "role": role})

    def post_alert(client, suffix):
        raw = build_alert(suffix, datetime.now(timezone.utc), VALID[0], random.Random(suffix))
        raw["id"] = f"{agent}.{suffix}"
        raw["agent"] = {"id": agent, "name": agent, "ip": "192.0.2.10"}
        raw["rule"].update(id=tag, level=9)
        body = json.dumps(raw).encode()
        signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return client.post("/api/webhooks/wazuh", content=body, headers={"X-Sentrax-Signature": signature})

    def wait_for_assessment(suffix):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with factory() as session:
                row = session.execute(text("""
                    SELECT al.id, ep.pack_json, al.process_signature
                    FROM alerts al JOIN evidence_packs ep ON ep.alert_id = al.id
                    JOIN ai_assessments ai ON ai.alert_id = al.id
                    WHERE al.wazuh_alert_id = :wid AND al.status = 'AWAITING_ANALYST'
                """), {"wid": f"{agent}.{suffix}"}).first()
            if row is not None:
                return row
            time.sleep(0.1)
        raise AssertionError(f"Alert {suffix} never reached AWAITING_ANALYST with persisted evidence and assessment")

    try:
        with TestClient(main.app) as client:
            def login(name):
                response = client.post("/api/v1/auth/login", json={"username": name, "password": password})
                assert response.status_code == 200
                return {"Authorization": f"Bearer {response.json()['access_token']}"}

            lead_headers, analyst_headers = login(lead), login(analyst)
            runtime_url = "/api/v1/runtime/settings"
            assert client.get(runtime_url).status_code == 401
            runtime = client.get(runtime_url, headers=analyst_headers)
            assert runtime.status_code == 200
            assert runtime.json() == {
                "ingestion_mode": "replay",
                "min_rule_level": 4,
                "polling_interval_seconds": None,
                "worker_status": "running",
                "active_workers": 1,
                "llm_provider": "mock",
                "model_name": "mock",
                "abstention_threshold": 0.6,
                "max_exemplars_injected": 2,
            }
            assert client.patch("/api/v1/admin/config", headers=analyst_headers).status_code == 403
            assert client.get("/api/v1/analytics", headers=analyst_headers).status_code == 403
            assert client.get("/api/v1/analytics/export-csv", headers=analyst_headers).status_code == 403
            assert client.get("/api/v1/analytics?range=90d", headers=lead_headers).status_code == 200
            assert client.get("/api/v1/analytics?range=91d", headers=lead_headers).status_code == 422
            assert post_alert(client, 1).json()["inserted"] == 1
            assert post_alert(client, 1).json()["db_duplicates"] == 1
            _, first_pack, signature = wait_for_assessment(1)
            assert first_pack["asset_context"]["criticality_tier"] == "MEDIUM"
            asset_url = f"/api/v1/governance/assets/{agent}"
            assert client.patch(asset_url, headers=analyst_headers, json={"criticality_tier": "CRITICAL"}).status_code == 403
            updated_asset = client.patch(asset_url, headers=lead_headers, json={
                "criticality_tier": "CRITICAL", "description": "Synthetic governed asset",
            })
            assert updated_asset.status_code == 200
            assert updated_asset.json()["description"] == "Synthetic governed asset"

            with factory.begin() as session:
                exemplar_id = session.execute(text("""
                    INSERT INTO feedback_exemplars (rule_id, process_signature, asset_criticality,
                                                    calibrated_verdict, calibrated_severity, rationale)
                    VALUES (:rule, :signature, 'CRITICAL', 'TRUE_POSITIVE', 'HIGH', 'Historical example for smoke test')
                    RETURNING id
                """), {"rule": tag, "signature": signature}).scalar_one()
            assert post_alert(client, 2).json()["inserted"] == 1
            second_id, second_pack, _ = wait_for_assessment(2)
            assert second_pack["asset_context"]["criticality_tier"] == "CRITICAL"
            exemplar_url = f"/api/v1/governance/exemplars/{exemplar_id}"
            assert client.patch(exemplar_url, headers=analyst_headers, json={"is_active": False}).status_code == 403
            revoked = client.patch(exemplar_url, headers=lead_headers, json={"is_active": False})
            assert revoked.status_code == 200 and revoked.json()["is_active"] is False
            assert revoked.json()["revoked_at"] and revoked.json()["revoked_by"]

            response = client.get(f"/api/v1/alerts/{second_id}", headers=analyst_headers)
            assert response.status_code == 200
            detail = response.json()
            assert "APPROVE" in detail["available_actions"]
            assert detail["evidence_pack"]["asset_context"] == second_pack["asset_context"]
            assert detail["evidence_pack"]["pack_json"] == second_pack
            items = detail["injected_exemplars"]
            assert [(item["id"], item["is_active"], item["match_hit_count"]) for item in items] == [(exemplar_id, False, 1)]
            assert post_alert(client, 3).json()["inserted"] == 1
            third_id, third_pack, _ = wait_for_assessment(3)
            assert third_pack["asset_context"]["criticality_tier"] == "CRITICAL"
            assert client.get(f"/api/v1/alerts/{third_id}", headers=analyst_headers).json()["injected_exemplars"] == []
            with factory.begin() as session:
                session.execute(text("UPDATE users SET is_active = false WHERE username = :name"), {"name": lead})
            assert client.get("/api/v1/analytics", headers=lead_headers).status_code == 403
    finally:
        with factory.begin() as session:
            session.execute(text("DELETE FROM feedback_exemplars WHERE rule_id = :rule"), {"rule": tag})
            session.execute(text("DELETE FROM alerts WHERE agent_id = :agent"), {"agent": agent})
            session.execute(text("DELETE FROM assets WHERE agent_id = :agent"), {"agent": agent})
            session.execute(text("DELETE FROM users WHERE username IN (:lead, :analyst)"), {"lead": lead, "analyst": analyst})
