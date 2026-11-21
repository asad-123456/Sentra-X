"""FR-4 few-shot exemplars on Asad's real schema (feedback_exemplars), run on the sentrax_test database.

  * find_exemplars(): AC-9 (2 most recent, Tier 1 first, revoked ones absent from the very next lookup) and AC-21
    (50 lookups over 10,000 exemplars, each under 50 ms).
  * governance exemplar routes: list = TeamLead/Admin, revoke = TeamLead only, revoker taken from the token.
DEMO_MODE is forced off so the role rules are the real ones."""
import logging
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.auth import hash_password
from app.config import settings
from app.database import get_db
from app.exemplars.service import find_exemplars
from app.exemplars.vocab import SEVERITIES, TIERS, VERDICTS
from app.ingestion.service import ingest_raws
from app.main import app
from app.models import User
from app.models.base import Base
from app.models.exemplar import FeedbackExemplar
from app.worker.jobs import triage_queue
from scripts.generate_replay import VALID, build_alert

TABLES = [Base.metadata.tables[n] for n in ("users", "assets", "alerts", "feedback_exemplars")]
PW = "Passw0rd!x"
URL = "/api/v1/governance/exemplars"


@pytest.fixture(scope="module")
def factory(legacy_test_engine):
    engine = legacy_test_engine
    Base.metadata.drop_all(engine, tables=TABLES)
    Base.metadata.create_all(engine, tables=TABLES)
    yield sessionmaker(engine, expire_on_commit=False)
    Base.metadata.drop_all(engine, tables=TABLES)


@pytest.fixture(autouse=True)
def clean(factory, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    with factory.begin() as s:
        s.execute(text("TRUNCATE feedback_exemplars, alerts, assets, users CASCADE"))
    while not triage_queue.empty():
        triage_queue.get_nowait()


@pytest.fixture
def client(factory):
    def override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------- helpers ----------
def add_alert(factory, seq=1):
    """Ingest one alert through the real ingestion path and return (alert uuid, rule_id, process_signature)."""
    raw = build_alert(seq, datetime(2026, 10, 22, 10, 0, seq % 60, tzinfo=timezone.utc), VALID[0], random.Random(seq))
    ingest_raws(factory, [raw])
    with factory() as s:
        r = s.execute(text("SELECT id, rule_id, process_signature FROM alerts WHERE wazuh_alert_id=:w"),
                      {"w": raw["id"]}).one()
    return r.id, r.rule_id, r.process_signature


def add_ex(factory, *, rule="5710", sig="sshd", tier="MEDIUM", age=1, active=True, source=None):
    ex = FeedbackExemplar(
        source_alert_id=source, rule_id=rule, process_signature=sig, asset_criticality=tier,
        calibrated_verdict="FALSE_POSITIVE", calibrated_severity="LOW", rationale="rationale long enough",
        is_active=active, created_at=datetime.now(timezone.utc) - timedelta(minutes=age),
    )
    with factory.begin() as s:
        s.add(ex)
        s.flush()
        return ex.id


def lookup(factory, alert_id, rule="5710", sig="sshd", tier="MEDIUM"):
    with factory.begin() as s:
        return find_exemplars(s, alert_id=alert_id, rule_id=rule, process_signature=sig, asset_criticality=tier)


def hits(factory, ex_id):
    with factory() as s:
        return s.execute(text("SELECT match_hit_count FROM feedback_exemplars WHERE id=:i"), {"i": ex_id}).scalar()


def make_user(factory, username, role):
    user = User(id=uuid.uuid4(), username=username, email=f"{username}@sentrax.dev",
                password_hash=hash_password(PW), role=role, is_active=True)
    with factory.begin() as s:
        s.add(user)
    return user


def headers(client, username):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def row(factory, ex_id):
    with factory() as s:
        return s.execute(text("SELECT is_active, revoked_by, revoked_at FROM feedback_exemplars WHERE id=:i"),
                         {"i": ex_id}).one()


# ---------- vocabulary ----------
def test_vocab_matches_the_database_check_constraints(factory):
    assert VERDICTS == ("TRUE_POSITIVE", "FALSE_POSITIVE")
    assert SEVERITIES == ("LOW", "MEDIUM", "HIGH", "CRITICAL") == TIERS


# ---------- retrieval ----------
def test_ac9_two_most_recent_tier1_first_then_revoked_is_absent(client, factory):
    a, rule, sig = add_alert(factory)
    old, mid, new = (add_ex(factory, rule=rule, sig=sig, age=n) for n in (30, 20, 10))
    got = lookup(factory, a, rule, sig)
    assert [g["id"] for g in got] == [new, mid]
    assert all(g["match_tier"] == "Tier 1" for g in got)

    make_user(factory, "lead", "TeamLead")
    r = client.patch(f"{URL}/{new}", json={"is_active": False}, headers=headers(client, "lead"))
    assert r.status_code == 200
    assert [g["id"] for g in lookup(factory, a, rule, sig)] == [mid, old]   # absent from the very next prompt


def test_tier1_comes_before_tier2_and_tier2_fills_up(factory):
    a, rule, sig = add_alert(factory)
    t1 = add_ex(factory, rule=rule, sig=sig, tier="LOW", age=50)       # signature match, other tier
    t2_new = add_ex(factory, rule=rule, sig="other", tier="MEDIUM", age=1)
    add_ex(factory, rule=rule, sig="other", tier="MEDIUM", age=5)      # older, cut by the limit of 2
    got = lookup(factory, a, rule, sig, "MEDIUM")
    assert [(g["id"], g["match_tier"]) for g in got] == [(t1, "Tier 1"), (t2_new, "Tier 2")]


def test_output_shape_and_integer_id(factory):
    a, rule, sig = add_alert(factory)
    ex = add_ex(factory, rule=rule, sig=sig)
    got = lookup(factory, a, rule, sig)[0]
    assert set(got) == {"id", "match_tier", "rule_id", "process_signature", "asset_criticality",
                        "calibrated_verdict", "calibrated_severity", "rationale"}
    assert got["id"] == ex and isinstance(got["id"], int)


def test_tier2_needs_same_rule_and_same_tier(factory):
    a, rule, sig = add_alert(factory)
    add_ex(factory, rule="9999", sig="other", tier="MEDIUM")
    add_ex(factory, rule=rule, sig="other", tier="HIGH")
    assert lookup(factory, a, rule, sig, "MEDIUM") == []                # zero-shot


def test_null_signature_never_matches_tier1(factory):
    a, rule, _ = add_alert(factory)
    ex = add_ex(factory, rule=rule, sig=None, tier="HIGH")
    assert lookup(factory, a, rule, None, "MEDIUM") == []               # NULL does not equal NULL, tier differs
    got = lookup(factory, a, rule, None, "HIGH")                        # only a Tier 2 (tier) match
    assert [(g["id"], g["match_tier"]) for g in got] == [(ex, "Tier 2")]


def test_own_exemplar_excluded_but_unlinked_ones_are_kept(factory):
    a, rule, sig = add_alert(factory)
    add_ex(factory, rule=rule, sig=sig, source=a)                       # made from this very alert: a retry must not cite it
    unlinked = add_ex(factory, rule=rule, sig=sig, source=None)         # source alert deleted (FK is SET NULL): still valid
    assert [g["id"] for g in lookup(factory, a, rule, sig)] == [unlinked]


def test_tier1_hit_not_repeated_in_tier2(factory):
    a, rule, sig = add_alert(factory)
    ex = add_ex(factory, rule=rule, sig=sig, tier="MEDIUM")             # qualifies for both tiers
    assert [(g["id"], g["match_tier"]) for g in lookup(factory, a, rule, sig, "MEDIUM")] == [(ex, "Tier 1")]


def test_inactive_never_returned(factory):
    a, rule, sig = add_alert(factory)
    add_ex(factory, rule=rule, sig=sig, active=False)
    assert lookup(factory, a, rule, sig) == []


def test_hit_count_incremented_only_for_returned(factory):
    a, rule, sig = add_alert(factory)
    cut, mid, new = (add_ex(factory, rule=rule, sig=sig, age=n) for n in (30, 20, 10))
    lookup(factory, a, rule, sig)
    lookup(factory, a, rule, sig)
    assert (hits(factory, new), hits(factory, mid), hits(factory, cut)) == (2, 2, 0)


def test_lookup_joins_callers_transaction(factory):
    a, rule, sig = add_alert(factory)
    ex = add_ex(factory, rule=rule, sig=sig)
    with factory() as s:                                                # caller rolls back: the hit count is not kept
        find_exemplars(s, alert_id=a, rule_id=rule, process_signature=sig, asset_criticality="MEDIUM")
        s.rollback()
    assert hits(factory, ex) == 0


# ---------- governance routes ----------
def test_list_access_and_null_signature_does_not_crash(client, factory):
    make_user(factory, "lead", "TeamLead")
    make_user(factory, "boss", "Admin")
    make_user(factory, "ann", "Analyst")
    add_ex(factory, sig=None)                                           # used to raise TypeError in the route
    for u in ("lead", "boss"):
        r = client.get(URL, headers=headers(client, u))
        assert r.status_code == 200 and len(r.json()) == 1
    assert client.get(URL, headers=headers(client, "ann")).status_code == 403
    assert client.get(URL).status_code == 401


def test_revoke_is_teamlead_only(client, factory):
    make_user(factory, "lead", "TeamLead")
    make_user(factory, "boss", "Admin")
    make_user(factory, "ann", "Analyst")
    ex = add_ex(factory)
    for who in ("ann", "boss"):
        assert client.patch(f"{URL}/{ex}", json={"is_active": False}, headers=headers(client, who)).status_code == 403
    assert client.patch(f"{URL}/{ex}", json={"is_active": False}).status_code == 401
    assert row(factory, ex).is_active is True                           # nothing changed


def test_revoke_records_the_caller_not_the_body(client, factory):
    lead = make_user(factory, "lead", "TeamLead")
    other = make_user(factory, "other", "Admin")
    ex = add_ex(factory)
    r = client.patch(f"{URL}/{ex}", json={"is_active": False, "revoked_by": str(other.id)},
                     headers=headers(client, "lead"))
    assert r.status_code == 200
    body = r.json()
    assert body["is_active"] is False and body["revoked_by"] == str(lead.id) and body["revoked_at"]
    assert row(factory, ex).revoked_by == lead.id


def test_second_revoke_keeps_the_original_who_and_when(client, factory):
    first = make_user(factory, "lead", "TeamLead")
    make_user(factory, "lead2", "TeamLead")
    ex = add_ex(factory)
    client.patch(f"{URL}/{ex}", json={"is_active": False}, headers=headers(client, "lead"))
    before = row(factory, ex)
    client.patch(f"{URL}/{ex}", json={"is_active": False}, headers=headers(client, "lead2"))
    after = row(factory, ex)
    assert after.revoked_by == first.id and after.revoked_at == before.revoked_at


def test_reactivate_clears_revocation_fields(client, factory):
    make_user(factory, "lead", "TeamLead")
    ex = add_ex(factory)
    h = headers(client, "lead")
    client.patch(f"{URL}/{ex}", json={"is_active": False}, headers=h)
    r = client.patch(f"{URL}/{ex}", json={"is_active": True}, headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is True
    assert row(factory, ex).revoked_by is None and row(factory, ex).revoked_at is None


def test_revoke_unknown_or_malformed_id_is_404(client, factory):
    make_user(factory, "lead", "TeamLead")
    h = headers(client, "lead")
    assert client.patch(f"{URL}/999999", json={"is_active": False}, headers=h).status_code == 404
    assert client.patch(f"{URL}/not-a-number", json={"is_active": False}, headers=h).status_code == 404


def test_revoke_is_logged(client, factory, caplog):
    make_user(factory, "lead", "TeamLead")
    ex = add_ex(factory)
    caplog.set_level(logging.INFO, logger="sentrax.security")
    client.patch(f"{URL}/{ex}", json={"is_active": False}, headers=headers(client, "lead"))
    assert "exemplar_revoked" in caplog.text and "by=lead" in caplog.text


# ---------- AC-21 ----------
def test_ac21_50_lookups_over_10000_exemplars_each_under_50ms(factory):
    rng = random.Random(7)
    rules, sigs = [f"R{i}" for i in range(20)], [f"proc{i}" for i in range(50)]
    now = datetime.now(timezone.utc)
    with factory.begin() as s:
        s.execute(FeedbackExemplar.__table__.insert(), [{
            "rule_id": rng.choice(rules),
            "process_signature": None if rng.random() < 0.1 else rng.choice(sigs),
            "asset_criticality": rng.choice(TIERS),
            "calibrated_verdict": "FALSE_POSITIVE", "calibrated_severity": "LOW",
            "rationale": "seeded exemplar for the lookup benchmark",
            "created_at": now - timedelta(minutes=i),
        } for i in range(10_000)])
        s.execute(text("ANALYZE feedback_exemplars"))

    def one():
        with factory.begin() as s:       # includes the hit-count UPDATE and the commit
            return find_exemplars(s, alert_id=uuid.uuid4(), rule_id=rng.choice(rules),
                                  process_signature=rng.choice(sigs), asset_criticality=rng.choice(TIERS))

    one()                                # warm-up: opens the connection, caches plans
    times = []
    for _ in range(50):
        start = time.perf_counter()
        got = one()
        times.append((time.perf_counter() - start) * 1000)
        assert len(got) <= 2
    assert max(times) < 50, f"slowest lookup {max(times):.1f} ms (limit 50 ms)"
