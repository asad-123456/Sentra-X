"""End-to-end test against the RUNNING stack (docker compose up -d).

PowerShell, from the backend folder:
  $env:E2E_BASE_URL="http://localhost:8000"
  python -m pytest tests/test_e2e_stack.py -v
  Remove-Item Env:E2E_BASE_URL
Without E2E_BASE_URL the test is skipped (one expected skip in the normal run).
The webhook secret is read from backend/.env, so it must match the running container.
"""
import hashlib
import hmac
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine, text

BASE = os.getenv("E2E_BASE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE, reason="set E2E_BASE_URL to run the E2E test")
PW = "E2eTest123!"


def make_alert(agent_id: str) -> dict:
    from scripts.generate_replay import VALID, build_alert
    n = uuid.uuid4().int % 10_000_000
    raw = build_alert(n, datetime.now(timezone.utc), VALID[0], random.Random(n))
    raw["id"] = f"e2e.{uuid.uuid4().hex[:12]}"
    raw["rule"]["level"] = 5
    raw["agent"] = {"id": agent_id, "name": f"host-{agent_id}", "ip": "10.1.1.1"}
    return raw


def post_alert(client, raw, secret, signature=None):
    body = json.dumps(raw).encode()
    sig = signature or "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(f"{BASE}/api/webhooks/wazuh", content=body,
                       headers={"X-Sentrax-Signature": sig, "Content-Type": "application/json"})


def wait_status(engine, wazuh_id, want, timeout=60):
    end = time.time() + timeout
    row = None
    while time.time() < end:
        with engine.connect() as c:
            row = c.execute(text("SELECT id, status FROM alerts WHERE wazuh_alert_id=:w"),
                            {"w": wazuh_id}).first()
        if row and row.status == want:
            return row
        time.sleep(1)
    pytest.fail(f"alert {wazuh_id} did not reach {want} within {timeout}s (last: {row})")


def login(client, user, password):
    r = client.post(f"{BASE}/api/v1/auth/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_flow():
    from app.auth import hash_password
    from app.config import settings
    from app.ingestion.wazuh_settings import get_wazuh_settings

    secret = get_wazuh_settings().WAZUH_WEBHOOK_SECRET
    assert secret, "WAZUH_WEBHOOK_SECRET is empty in backend/.env"
    engine = create_engine(settings.DATABASE_URL)
    suffix = uuid.uuid4().hex[:8]
    agent = f"e2e{suffix}"
    users = {f"lead{suffix}": "TeamLead", f"ann{suffix}": "Analyst"}

    try:
        # users are created straight in the DB so the test does not depend on admin credentials
        with engine.begin() as c:
            for name, role in users.items():
                c.execute(text(
                    "INSERT INTO users (id, username, email, password_hash, role, is_active) "
                    "VALUES (:i, :u, :e, :p, :r, true)"),
                    {"i": uuid.uuid4(), "u": name, "e": f"{name}@sentrax.dev",
                     "p": hash_password(PW), "r": role})

        with httpx.Client(timeout=15, verify=False) as c:
            # 1. stack is up
            assert c.get(f"{BASE}/api/health").json()["status"] == "HEALTHY"

            # 2. auth (AC-15 / AC-16)
            lead, analyst = login(c, f"lead{suffix}", PW), login(c, f"ann{suffix}", PW)
            assert c.post(f"{BASE}/api/v1/auth/login",
                          json={"username": f"lead{suffix}", "password": "wrong"}).status_code == 401
            assert c.get(f"{BASE}/api/v1/admin/users", headers=lead).status_code == 403

            # 3. ingestion: bad signature rejected, good one accepted, duplicate ignored (FR-1)
            first = make_alert(agent)
            assert post_alert(c, first, secret, signature="sha256=bad").status_code == 401
            r = post_alert(c, first, secret)
            assert r.status_code == 200, r.text
            first_body = r.json()
            assert post_alert(c, first, secret).status_code == 200   # duplicate must not create a 2nd row

            # 4. worker: PENDING_REVIEW -> AWAITING_ANALYST with pack + assessment
            row = wait_status(engine, first["id"], "AWAITING_ANALYST")
            with engine.connect() as conn:
                assert conn.execute(text("SELECT count(*) FROM alerts WHERE wazuh_alert_id=:w"),
                                    {"w": first["id"]}).scalar() == 1
                assert conn.execute(text("SELECT count(*) FROM evidence_packs WHERE alert_id=:a"),
                                    {"a": row.id}).scalar() == 1
                assert conn.execute(text("SELECT count(*) FROM ai_assessments WHERE alert_id=:a"),
                                    {"a": row.id}).scalar() == 1

            # 5. assets (FR-9 / AC-17): auto-registered MEDIUM, analyst blocked, lead updates
            assets = {a["agent_id"]: a for a in c.get(f"{BASE}/api/v1/governance/assets").json()}
            assert assets[agent]["criticality_tier"] == "MEDIUM"
            assert c.patch(f"{BASE}/api/v1/governance/assets/{agent}", headers=analyst,
                           json={"criticality_tier": "HIGH"}).status_code == 403
            r = c.patch(f"{BASE}/api/v1/governance/assets/{agent}", headers=lead,
                        json={"criticality_tier": "CRITICAL"})
            assert r.status_code == 200, r.text

            # 6. the NEXT alert's evidence pack carries the new tier (AC-17)
            second = make_alert(agent)
            assert post_alert(c, second, secret).status_code == 200
            row2 = wait_status(engine, second["id"], "AWAITING_ANALYST")
            with engine.connect() as conn:
                pack = conn.execute(text("SELECT pack_json FROM evidence_packs WHERE alert_id=:a"),
                                    {"a": row2.id}).scalar()
            assert pack["asset_context"]["criticality_tier"] == "CRITICAL"
    finally:
        with engine.begin() as c:
            c.execute(text("DELETE FROM users WHERE username = ANY(:n)"), {"n": list(users)})
