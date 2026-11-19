"""Integration tests for triage_store against a real PostgreSQL 16 (Part 6A-2).

Needs a migrated test database. Defaults to the throwaway container:
        "TEST_DATABASE_URL", "postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax_triage_test"
Override with TEST_DATABASE_URL (the database name must end in _test).
Every test runs inside a transaction that is rolled back, so nothing is left behind.
"""
import json
import os
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.evidence_assembler import select_correlated
from app.services.llm_adapter import InjectedExemplar, MockAdapter
from app.services.triage_pipeline import run_triage_pipeline
from app.services.triage_store import load_triage_inputs, persist_outcome

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax_triage_test"
)
REF = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
LOG = {"full_log": "Failed password for root from 203.0.113.9 port 4242 ssh2"}


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


# --- helpers ------------------------------------------------------------------
def wid(alert_id: uuid.UUID) -> str:
    return f"it-{alert_id.hex[:12]}"


def make_agent(session, tier="MEDIUM") -> str:
    agent_id = f"it-{uuid.uuid4().hex[:10]}"
    session.execute(
        text("INSERT INTO assets (agent_id, hostname, criticality_tier) VALUES (:a, :a, :t)"),
        {"a": agent_id, "t": tier},
    )
    return agent_id


def make_alert(session, agent_id, *, age=timedelta(0), level=5, src_ip=None,
               status="PENDING_REVIEW", raw_payload=None) -> uuid.UUID:
    alert_id = uuid.uuid4()
    session.execute(
        text("""
            INSERT INTO alerts (id, wazuh_alert_id, rule_id, rule_level, rule_description,
                                agent_id, agent_name, src_ip, raw_payload, status, alert_timestamp)
            VALUES (:id, :wid, '5710', :level, 'test rule', :agent, 'host-1', :ip,
                    CAST(:raw AS jsonb), :status, :ts)
        """),
        {
            "id": alert_id, "wid": wid(alert_id), "level": level, "agent": agent_id,
            "ip": src_ip, "status": status, "ts": REF - age,
            "raw": json.dumps(raw_payload) if raw_payload is not None else None,
        },
    )
    return alert_id


def count(session, table, alert_id) -> int:
    return session.execute(
        text(f"SELECT count(*) FROM {table} WHERE alert_id = :id"), {"id": alert_id}
    ).scalar_one()


def alert_row(session, alert_id):
    return session.execute(
        text("SELECT status, retry_count FROM alerts WHERE id = :id"), {"id": alert_id}
    ).one()


def triage(session, alert_id, adapter=None, **lookups):
    inputs = load_triage_inputs(session, alert_id, **lookups)
    return run_triage_pipeline(inputs, adapter or MockAdapter(), sleep=lambda s: None)


def exemplar(i, tier="Tier 1", **over):
    d = {
        "id": i, "match_tier": tier, "rule_id": "5710", "process_signature": None,
        "asset_criticality": "MEDIUM", "calibrated_verdict": "FALSE_POSITIVE",
        "calibrated_severity": "LOW",
        "rationale": "Known backup job, confirmed benign by the analyst.",
    }
    d.update(over)
    return d


# --- load ---------------------------------------------------------------------
def test_load_reads_the_alert_tier_and_payload(session):
    agent = make_agent(session, tier="HIGH")
    payload = {**LOG, "data": {"srcuser": "admin"}}
    alert_id = make_alert(session, agent, level=12, src_ip="203.0.113.9", raw_payload=payload)
    inputs = load_triage_inputs(session, alert_id)
    a = inputs.alert
    assert (a.wazuh_alert_id, a.rule_id, a.rule_level, a.agent_id, a.agent_name, a.src_ip) == (
        wid(alert_id), "5710", 12, agent, "host-1", "203.0.113.9",
    )
    assert a.alert_timestamp == REF and a.alert_timestamp.tzinfo is not None
    assert a.raw_payload == payload
    assert inputs.criticality_tier == "HIGH"
    assert inputs.exemplars == ()


def test_a_null_payload_becomes_an_empty_dict(session):
    alert_id = make_alert(session, make_agent(session), raw_payload=None)
    assert load_triage_inputs(session, alert_id).alert.raw_payload == {}


def test_a_missing_alert_raises_lookup_error(session):
    with pytest.raises(LookupError):
        load_triage_inputs(session, uuid.uuid4())


def test_a_custom_tier_lookup_is_used(session):
    alert_id = make_alert(session, make_agent(session))
    inputs = load_triage_inputs(session, alert_id, tier_lookup=lambda s, agent_id: "CRITICAL")
    assert inputs.criticality_tier == "CRITICAL"


def test_correlation_merges_both_indexes_without_duplicates(session):
    agent, other = make_agent(session), make_agent(session)
    ip = "203.0.113.9"
    target = make_alert(session, agent, src_ip=ip)
    same_agent = [make_alert(session, agent, age=timedelta(minutes=m), src_ip=ip) for m in range(1, 8)]
    other_same_ip = make_alert(session, other, age=timedelta(seconds=90), src_ip=ip)
    too_old = make_alert(session, agent, age=timedelta(hours=25), src_ip=ip)
    future = make_alert(session, agent, age=timedelta(minutes=-5), src_ip=ip)

    inputs = load_triage_inputs(session, target)
    ids = [c.wazuh_alert_id for c in inputs.candidates]
    assert len(ids) == len(set(ids))
    assert not {wid(target), wid(too_old), wid(future)} & set(ids)

    chosen = select_correlated(inputs.alert, inputs.candidates)
    assert [c.wazuh_alert_id for c in chosen] == [
        wid(same_agent[0]), wid(other_same_ip), wid(same_agent[1]),
        wid(same_agent[2]), wid(same_agent[3]),
    ]


def test_loopback_source_ip_does_not_pull_in_other_agents(session):
    agent, other = make_agent(session), make_agent(session)
    target = make_alert(session, agent, src_ip="127.0.0.1")
    stranger = make_alert(session, other, age=timedelta(minutes=1), src_ip="127.0.0.1")
    mine = make_alert(session, agent, age=timedelta(minutes=2), src_ip="127.0.0.1")
    ids = [c.wazuh_alert_id for c in load_triage_inputs(session, target).candidates]
    assert wid(stranger) not in ids and wid(mine) in ids


def test_exemplar_dicts_become_injected_exemplars_capped_at_two(session):
    alert_id = make_alert(session, make_agent(session, tier="HIGH"))
    calls = []

    def lookup(s, **kwargs):
        calls.append(kwargs)
        return [exemplar(7, "Tier 2"), {"id": 8}, exemplar(9, "Tier 3"), exemplar(10), exemplar(11)]

    inputs = load_triage_inputs(session, alert_id, exemplar_lookup=lookup)
    assert [e.id for e in inputs.exemplars] == [7, 10]
    assert all(isinstance(e, InjectedExemplar) for e in inputs.exemplars)
    assert calls == [{
        "alert_id": alert_id, "rule_id": "5710",
        "process_signature": None, "asset_criticality": "HIGH",
    }]


def test_a_failing_exemplar_lookup_falls_back_to_zero_shot(session):
    alert_id = make_alert(session, make_agent(session))

    def broken(s, **kwargs):
        s.execute(text("SELECT * FROM table_that_does_not_exist"))

    inputs = load_triage_inputs(session, alert_id, exemplar_lookup=broken)
    assert inputs.exemplars == ()
    assert session.execute(text("SELECT 1")).scalar_one() == 1  # session still usable


# --- persist ------------------------------------------------------------------
def test_persist_success_saves_pack_assessment_and_status(session):
    alert_id = make_alert(session, make_agent(session), level=12, raw_payload=LOG)
    outcome = triage(session, alert_id)
    assert persist_outcome(session, alert_id, outcome) == "AWAITING_ANALYST"

    pack = session.execute(
        text("""SELECT pack_json->'alert_metadata'->'rule'->>'id',
                       jsonb_array_length(valid_dot_keys), injection_suspect
                FROM evidence_packs WHERE alert_id = :id"""),
        {"id": alert_id},
    ).one()
    assert pack[0] == "5710" and pack[1] > 0 and pack[2] is False

    a = session.execute(
        text("""SELECT effective_verdict, effective_severity, llm_provider, model_name,
                       latency_ms, inference_latency_ms, retry_count
                FROM ai_assessments WHERE alert_id = :id"""),
        {"id": alert_id},
    ).one()
    assert tuple(a[:4]) == ("TRUE_POSITIVE", "CRITICAL", "mock", "mock")
    assert a[4] is not None and a[4] == a[5] and a[6] == 0
    assert tuple(alert_row(session, alert_id)) == ("AWAITING_ANALYST", 0)


def test_persisting_twice_updates_in_place(session):
    alert_id = make_alert(session, make_agent(session), level=12, raw_payload=LOG)
    persist_outcome(session, alert_id, triage(session, alert_id))

    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for table in ("evidence_packs", "ai_assessments"):
        session.execute(
            text(f"UPDATE {table} SET created_at = :t, updated_at = :t WHERE alert_id = :id"),
            {"t": old, "id": alert_id},
        )
    session.execute(
        text("UPDATE alerts SET status = 'PENDING_REVIEW', rule_level = 5 WHERE id = :id"),
        {"id": alert_id},
    )

    assert persist_outcome(session, alert_id, triage(session, alert_id)) == "AWAITING_ANALYST"
    for table in ("evidence_packs", "ai_assessments"):
        assert count(session, table, alert_id) == 1
        created, updated = session.execute(
            text(f"SELECT created_at, updated_at FROM {table} WHERE alert_id = :id"),
            {"id": alert_id},
        ).one()
        assert created == old and updated > old
    severity = session.execute(
        text("SELECT effective_severity FROM ai_assessments WHERE alert_id = :id"), {"id": alert_id}
    ).scalar_one()
    assert severity == "MEDIUM"


def test_a_failed_run_keeps_the_pack_drops_the_assessment_and_needs_manual_triage(session):
    alert_id = make_alert(session, make_agent(session), level=12, raw_payload=LOG)
    persist_outcome(session, alert_id, triage(session, alert_id))
    session.execute(text("UPDATE alerts SET status = 'PENDING_REVIEW' WHERE id = :id"), {"id": alert_id})

    failed = triage(session, alert_id, MockAdapter(failure_mode="timeout"))
    assert failed.next_status == "NEEDS_MANUAL_TRIAGE" and failed.call.retry_count == 3
    assert persist_outcome(session, alert_id, failed) == "NEEDS_MANUAL_TRIAGE"
    assert count(session, "evidence_packs", alert_id) == 1
    assert count(session, "ai_assessments", alert_id) == 0
    assert tuple(alert_row(session, alert_id)) == ("NEEDS_MANUAL_TRIAGE", 3)


def test_a_decided_alert_is_never_touched(session):
    alert_id = make_alert(session, make_agent(session), status="CLOSED", level=12, raw_payload=LOG)
    outcome = triage(session, alert_id)
    assert persist_outcome(session, alert_id, outcome) is None
    assert count(session, "evidence_packs", alert_id) == 0
    assert count(session, "ai_assessments", alert_id) == 0
    assert tuple(alert_row(session, alert_id)) == ("CLOSED", 0)


def test_only_triage_statuses_can_be_written(session):
    alert_id = make_alert(session, make_agent(session), level=12, raw_payload=LOG)
    outcome = replace(triage(session, alert_id), next_status="CLOSED")
    with pytest.raises(ValueError):
        persist_outcome(session, alert_id, outcome)
    assert alert_row(session, alert_id)[0] == "PENDING_REVIEW"


def test_persisting_for_an_unknown_alert_raises_lookup_error(session):
    alert_id = make_alert(session, make_agent(session), level=12, raw_payload=LOG)
    outcome = triage(session, alert_id)
    with pytest.raises(LookupError):
        persist_outcome(session, uuid.uuid4(), outcome)


def test_nul_characters_in_model_text_are_stripped(session):
    alert_id = make_alert(session, make_agent(session), level=12, raw_payload=LOG)
    outcome = triage(session, alert_id)
    bad = outcome.call.output.model_copy(update={"explanation": "bad\x00text"})
    outcome = replace(outcome, call=replace(outcome.call, output=bad))
    persist_outcome(session, alert_id, outcome)
    explanation = session.execute(
        text("SELECT explanation FROM ai_assessments WHERE alert_id = :id"), {"id": alert_id}
    ).scalar_one()
    assert explanation == "badtext"