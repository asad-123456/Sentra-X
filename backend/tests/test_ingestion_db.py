import hashlib
import hmac
import json
import random
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (importing the package registers every table on Base.metadata)
from app.config import settings
from app.ingestion.db_access import get_session_factory
from app.ingestion.poller import Poller
from app.ingestion.service import ingest_raws
from app.ingestion.webhook import verify_signature
from app.main import app
from app.models.base import Base
from app.worker.jobs import triage_queue
from scripts.generate_replay import VALID, build_ac1, build_alert

# Only the tables ingestion touches. assets has a foreign key to users, so users is needed too.
TABLES = [Base.metadata.tables[n] for n in ("users", "assets", "alerts")]


@pytest.fixture(scope="module")
def factory():
    url = make_url(settings.DATABASE_URL).set(database="sentrax_test")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"sentrax_test database not reachable: {exc}")
    Base.metadata.drop_all(engine, tables=TABLES)
    Base.metadata.create_all(engine, tables=TABLES)
    yield sessionmaker(engine, expire_on_commit=False)
    Base.metadata.drop_all(engine, tables=TABLES)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean(factory):
    with factory.begin() as s:
        s.execute(text("TRUNCATE alerts, assets"))
    while not triage_queue.empty():
        triage_queue.get_nowait()


def count(factory, table="alerts"):
    with factory() as s:
        return s.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def one_alert(seq=1, agent=None):
    rng = random.Random(seq)
    a = build_alert(seq, datetime(2026, 10, 22, 10, 0, seq % 60, tzinfo=timezone.utc), VALID[0], rng)
    if agent:
        a["agent"] = agent
    return a


def test_ac1_100_alerts_insert_exactly_70(factory):
    summary = ingest_raws(factory, build_ac1(random.Random(1)))
    assert (summary.received, summary.noise, summary.duplicate_in_batch) == (100, 20, 10)
    assert summary.inserted == 70
    assert count(factory) == 70
    assert triage_queue.qsize() == 70  # one job per new alert, none for noise


def test_second_replay_is_idempotent(factory):
    raws = build_ac1(random.Random(1))
    ingest_raws(factory, raws)
    again = ingest_raws(factory, raws)
    assert again.inserted == 0 and again.db_duplicates == 70
    assert count(factory) == 70
    assert triage_queue.qsize() == 70  # nothing new enqueued


def test_columns_populated(factory):
    raw = one_alert()
    ingest_raws(factory, [raw])
    with factory() as s:
        row = s.execute(text("SELECT * FROM alerts")).mappings().one()
    assert row["wazuh_alert_id"] == raw["id"]
    assert row["rule_id"] == "5710" and isinstance(row["rule_id"], str)
    assert row["status"] == "PENDING_REVIEW" and row["retry_count"] == 0
    assert row["raw_payload"] == raw
    assert row["mitre_tactics"] == ["Credential Access"]
    assert row["mitre_techniques"] == ["T1110.001"]
    assert row["alert_timestamp"].astimezone(timezone.utc).utcoffset().total_seconds() == 0
    assert row["ingested_at"] is not None


def test_ac3_unseen_agent_registered_as_medium(factory):
    ingest_raws(factory, [one_alert(agent={"id": "042", "name": "new-host", "ip": "10.9.9.9"})])
    with factory() as s:
        a = s.execute(text("SELECT * FROM assets WHERE agent_id='042'")).mappings().one()
    assert a["criticality_tier"] == "MEDIUM" and a["updated_by"] is None
    assert a["hostname"] == "new-host" and a["ip_address"] == "10.9.9.9"


def test_existing_asset_tier_not_overwritten(factory):
    with factory.begin() as s:
        s.execute(text("INSERT INTO assets (agent_id, hostname, criticality_tier) VALUES ('001','ubuntu-1','HIGH')"))
    ingest_raws(factory, [one_alert(agent={"id": "001", "name": "ubuntu-1", "ip": "10.0.0.11"})])
    with factory() as s:
        tier = s.execute(text("SELECT criticality_tier FROM assets WHERE agent_id='001'")).scalar()
    assert tier == "HIGH"


class Flaky:
    """First fetch fails (Wazuh down), second returns alerts, later ones are empty."""
    def __init__(self, raws):
        self.raws, self.calls = raws, 0

    def fetch(self, cursor):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("wazuh down")
        return self.raws if self.calls == 2 else []


def test_ac2_poller_survives_failure_and_resumes(factory):
    src = Flaky([one_alert(i) for i in range(1, 6)])
    p = Poller(src, factory, interval=0.05)
    p.start()
    try:
        deadline = time.time() + 5
        while time.time() < deadline and count(factory) < 5:
            time.sleep(0.05)
        assert p.alive
        assert count(factory) == 5
        assert src.calls >= 2
    finally:
        p.stop()


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_unit():
    body = b'{"a":1}'
    assert verify_signature("s", body, sign("s", body))
    assert not verify_signature("s", body, sign("other", body))
    assert not verify_signature("", body, sign("", body))
    assert not verify_signature("s", body, None)
    assert not verify_signature("s", body, "md5=abc")


def test_webhook_accepts_good_and_rejects_bad(factory, monkeypatch):
    monkeypatch.setattr("app.ingestion.webhook.get_wazuh_settings",
                        lambda: SimpleNamespace(WAZUH_WEBHOOK_SECRET="s3cret"))
    app.dependency_overrides[get_session_factory] = lambda: factory
    try:
        client = TestClient(app)
        body = json.dumps(one_alert()).encode()
        ok = client.post("/api/webhooks/wazuh", content=body,
                         headers={"X-Sentrax-Signature": sign("s3cret", body)})
        assert ok.status_code == 200 and ok.json()["inserted"] == 1
        bad = client.post("/api/webhooks/wazuh", content=body,
                          headers={"X-Sentrax-Signature": sign("wrong", body)})
        assert bad.status_code == 401
        assert client.post("/api/webhooks/wazuh", content=body).status_code == 401
        assert count(factory) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("bad_level,stored", [(99, 15), (-3, 0)])
def test_unusable_level_stored_clamped_as_manual_triage_and_not_queued(factory, bad_level, stored):
    raw = one_alert()
    raw["rule"]["level"] = bad_level
    summary = ingest_raws(factory, [raw])
    assert summary.inserted == 1 and summary.manual_triage == 1 and summary.noise == 0
    with factory() as s:
        row = s.execute(text("SELECT rule_level, status, raw_payload FROM alerts")).mappings().one()
    assert row["rule_level"] == stored and row["status"] == "NEEDS_MANUAL_TRIAGE"
    assert row["raw_payload"]["rule"]["level"] == bad_level  # original kept in raw_payload
    assert triage_queue.qsize() == 0  # a human decides; the AI worker never sees it
