"""The triage worker on Asad's real schema (alerts, evidence_packs, ai_assessments, feedback_exemplars) and
Abdur's real pipeline (evidence assembler, MockAdapter, guardrails), run on the sentrax_test database."""
import json
import random
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import partial

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.config import settings
from app.ingestion.service import ingest_raws
from app.models import Alert
from app.models.base import Base
from app.models.exemplar import FeedbackExemplar
from app.services.llm_adapter import LLMAdapter, MockAdapter
from app.worker import processor
from app.worker.bridge import run_pipeline
from app.worker.dispatcher import Dispatcher
from app.worker.jobs import triage_queue
from app.worker.processor import fetch_correlated, process_alert
from scripts.generate_replay import VALID, build_alert

TABLES = [Base.metadata.tables[n] for n in
          ("users", "assets", "alerts", "evidence_packs", "ai_assessments", "feedback_exemplars")]
T0 = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)


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
        s.execute(text("TRUNCATE feedback_exemplars, evidence_packs, ai_assessments, alerts, assets, users CASCADE"))
    while not triage_queue.empty():
        triage_queue.get_nowait()


# ---------- helpers ----------
def ingest(factory, seq, *, agent="001", src="203.0.113.9", ts=T0, level=5):
    raw = build_alert(seq, ts, VALID[0], random.Random(seq))
    raw["agent"] = {"id": agent, "name": f"host-{agent}", "ip": "10.0.0.1"}
    raw["rule"]["level"] = level
    raw["data"] = {"srcip": src} if src else {}
    ingest_raws(factory, [raw])
    with factory() as s:
        return s.execute(text("SELECT id FROM alerts WHERE wazuh_alert_id=:w"), {"w": raw["id"]}).scalar()


def scalar(factory, sql, **params):
    with factory() as s:
        return s.execute(text(sql), params).scalar()


def status(factory, aid):
    return scalar(factory, "SELECT status FROM alerts WHERE id=:i", i=aid)


def retry_count(factory, aid):
    return scalar(factory, "SELECT retry_count FROM alerts WHERE id=:i", i=aid)


def n_rows(factory, table, aid):
    return scalar(factory, f"SELECT count(*) FROM {table} WHERE alert_id=:a", a=aid)


def set_status(factory, aid, st, retries=0):
    with factory.begin() as s:
        s.execute(text("UPDATE alerts SET status=:s, retry_count=:r WHERE id=:i"), {"s": st, "r": retries, "i": aid})


def wait_until(fn, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.1)
    return False


def mock_process(f, i):
    return process_alert(f, i, MockAdapter())


class FixedAdapter(LLMAdapter):
    """Always answers the same JSON (to test the guardrails on a model output we control)."""
    model_name = "fixed"

    def __init__(self, payload):
        self.payload = payload

    def generate(self, system_prompt, user_prompt, timeout_s):
        return json.dumps(self.payload)


# ---------- success path ----------
def test_success_path_writes_pack_and_assessment(factory):
    aid = ingest(factory, 1)
    assert process_alert(factory, aid, MockAdapter()) == "done"
    assert status(factory, aid) == "AWAITING_ANALYST" and retry_count(factory, aid) == 0
    assert n_rows(factory, "evidence_packs", aid) == 1 and n_rows(factory, "ai_assessments", aid) == 1
    assert scalar(factory, "SELECT jsonb_array_length(valid_dot_keys) FROM evidence_packs") > 0
    with factory() as s:
        a = s.execute(text("SELECT * FROM ai_assessments")).mappings().one()
    assert a["llm_provider"] == "mock" and a["model_name"] == "mock"
    assert a["raw_verdict"] in ("TRUE_POSITIVE", "FALSE_POSITIVE", "NEEDS_ANALYST_REVIEW")
    assert a["effective_verdict"] and a["effective_severity"] and 0.0 <= a["confidence_score"] <= 1.0
    assert a["inference_latency_ms"] is not None and a["retry_count"] == 0


def test_guardrails_run_on_the_models_original_output(factory):
    aid = ingest(factory, 1, level=12)
    lowball = FixedAdapter({"verdict": "FALSE_POSITIVE", "recommended_severity": "LOW", "confidence_score": 0.95,
                            "cited_evidence_keys": ["alert_metadata.rule.id"], "explanation": "looks benign"})
    assert process_alert(factory, aid, lowball) == "done"
    with factory() as s:
        a = s.execute(text("SELECT * FROM ai_assessments")).mappings().one()
    assert (a["raw_verdict"], a["raw_severity"]) == ("FALSE_POSITIVE", "LOW")          # model output kept as is
    assert (a["effective_verdict"], a["effective_severity"]) == ("NEEDS_ANALYST_REVIEW", "CRITICAL")
    assert a["safety_floor_triggered"] is True and a["guardrail_audit_note"]


def test_model_retries_are_recorded(factory):
    aid = ingest(factory, 1)
    flaky = MockAdapter(failure_mode="http_500", fail_times=1)      # first call fails, the retry works (1 s backoff)
    assert process_alert(factory, aid, flaky) == "done"
    assert retry_count(factory, aid) == 1
    assert scalar(factory, "SELECT retry_count FROM ai_assessments") == 1


# ---------- exemplars ----------
def test_exemplars_reach_the_pipeline_the_pack_and_the_hit_count(factory):
    aid = ingest(factory, 1)
    with factory() as s:
        row = s.execute(text("SELECT rule_id, process_signature FROM alerts WHERE id=:i"), {"i": aid}).one()
    with factory.begin() as s:
        ex = FeedbackExemplar(rule_id=row.rule_id, process_signature=row.process_signature,
                              asset_criticality="MEDIUM", calibrated_verdict="FALSE_POSITIVE",
                              calibrated_severity="LOW", rationale="known nightly backup job")
        s.add(ex)
        s.flush()
        ex_id = ex.id
    seen = {}

    def spy(ctx, adapter):
        seen.update(tier=ctx.tier, ids=[e.id for e in ctx.exemplars], tiers=[e.match_tier for e in ctx.exemplars])
        return run_pipeline(ctx, adapter)

    assert process_alert(factory, aid, MockAdapter(), run=spy) == "done"
    assert seen == {"tier": "MEDIUM", "ids": [ex_id], "tiers": ["Tier 1"]}
    assert scalar(factory, "SELECT injected_exemplar_ids FROM evidence_packs") == [ex_id]
    assert scalar(factory, "SELECT match_hit_count FROM feedback_exemplars WHERE id=:i", i=ex_id) == 1


# ---------- correlated alerts ----------
def test_correlated_rules(factory):
    target = ingest(factory, 1, agent="001", src="203.0.113.9", ts=T0)
    a1 = ingest(factory, 2, agent="001", src="198.51.100.1", ts=T0 - timedelta(hours=1))     # same agent
    a2 = ingest(factory, 3, agent="002", src="203.0.113.9", ts=T0 - timedelta(hours=2))      # same src_ip
    ingest(factory, 4, agent="002", src="198.51.100.1", ts=T0 - timedelta(minutes=90))       # neither
    ingest(factory, 5, agent="001", src="203.0.113.9", ts=T0 - timedelta(hours=24, minutes=1))  # too old
    ingest(factory, 6, agent="001", src="203.0.113.9", ts=T0 + timedelta(minutes=30))        # AFTER the alert
    with factory() as s:
        got = fetch_correlated(s, s.get(Alert, target))
    assert [r.id for r in got] == [a1, a2]                # newest first, never itself


def test_correlated_limited_to_5_newest(factory):
    target = ingest(factory, 1, ts=T0)
    older = [ingest(factory, 10 + i, ts=T0 - timedelta(minutes=i)) for i in range(1, 8)]
    with factory() as s:
        assert [r.id for r in fetch_correlated(s, s.get(Alert, target))] == older[:5]


def test_null_src_ip_never_matches(factory):
    target = ingest(factory, 1, agent="001", src=None, ts=T0)
    ingest(factory, 2, agent="002", src=None, ts=T0 - timedelta(hours=1))        # NULL must not match NULL
    same_agent = ingest(factory, 3, agent="001", src=None, ts=T0 - timedelta(hours=2))
    with factory() as s:
        assert [r.id for r in fetch_correlated(s, s.get(Alert, target))] == [same_agent]


def test_correlated_alerts_appear_in_the_pack(factory):
    target = ingest(factory, 1, ts=T0)
    ingest(factory, 2, ts=T0 - timedelta(hours=1))
    process_alert(factory, target, MockAdapter())
    assert scalar(factory, "SELECT jsonb_array_length(pack_json->'temporal_context') FROM evidence_packs") == 1


# ---------- failures ----------
def test_model_failure_goes_to_manual_triage_and_keeps_the_pack(factory):
    aid = ingest(factory, 1)
    assert process_alert(factory, aid, MockAdapter(failure_mode="http_400")) == "failed"   # 400 is not retryable
    assert status(factory, aid) == "NEEDS_MANUAL_TRIAGE" and retry_count(factory, aid) == 3
    assert n_rows(factory, "evidence_packs", aid) == 1 and n_rows(factory, "ai_assessments", aid) == 0


def test_pipeline_crash_goes_to_manual_triage(factory):
    aid = ingest(factory, 1)

    def boom(ctx, adapter):
        raise RuntimeError("pipeline exploded")

    assert process_alert(factory, aid, MockAdapter(), run=boom) == "failed"
    assert status(factory, aid) == "NEEDS_MANUAL_TRIAGE" and retry_count(factory, aid) == 3
    assert n_rows(factory, "evidence_packs", aid) == 0 and n_rows(factory, "ai_assessments", aid) == 0


def test_save_error_falls_back_to_manual_triage(factory, monkeypatch):
    aid = ingest(factory, 1)

    def broken(*a, **k):
        raise RuntimeError("db write failed")

    monkeypatch.setattr(processor, "upsert_assessment", broken)
    assert process_alert(factory, aid, MockAdapter()) == "failed"
    assert status(factory, aid) == "NEEDS_MANUAL_TRIAGE"
    assert n_rows(factory, "ai_assessments", aid) == 0 and n_rows(factory, "evidence_packs", aid) == 0


# ---------- Retry AI, human statuses, races ----------
def test_second_run_upserts_instead_of_duplicating(factory):
    aid = ingest(factory, 1)
    process_alert(factory, aid, MockAdapter())
    set_status(factory, aid, "PENDING_REVIEW", 0)                 # what a re-triage request does
    assert process_alert(factory, aid, MockAdapter()) == "done"
    assert status(factory, aid) == "AWAITING_ANALYST"
    assert n_rows(factory, "evidence_packs", aid) == 1 and n_rows(factory, "ai_assessments", aid) == 1


@pytest.mark.parametrize("st", ["CLOSED", "ESCALATED", "AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"])
def test_only_pending_alerts_are_processed(factory, st):
    aid = ingest(factory, 1)
    set_status(factory, aid, st)
    assert process_alert(factory, aid, MockAdapter()) == "skipped"
    assert status(factory, aid) == st and n_rows(factory, "evidence_packs", aid) == 0


def test_human_change_during_triage_wins(factory):
    aid = ingest(factory, 1)

    def human_closes(ctx, adapter):
        set_status(factory, aid, "CLOSED")
        return run_pipeline(ctx, adapter)

    assert process_alert(factory, aid, MockAdapter(), run=human_closes) == "superseded"
    assert status(factory, aid) == "CLOSED"
    assert n_rows(factory, "ai_assessments", aid) == 0 and n_rows(factory, "evidence_packs", aid) == 0


# ---------- dispatcher ----------
def test_dispatcher_processes_new_alerts(factory):
    ids = [ingest(factory, i, ts=T0 + timedelta(seconds=i)) for i in range(1, 13)]
    d = Dispatcher(factory, 4, 0.2, process=mock_process)
    d.start()
    try:
        assert wait_until(lambda: all(status(factory, i) == "AWAITING_ANALYST" for i in ids))
    finally:
        d.stop()


def test_sweeper_recovers_after_restart(factory):
    ids = [ingest(factory, i, ts=T0 + timedelta(seconds=i)) for i in range(1, 6)]
    while not triage_queue.empty():                    # simulate losing the in-memory queue
        triage_queue.get_nowait()
    d = Dispatcher(factory, 4, 0.2, process=mock_process)
    d.start()
    try:
        assert wait_until(lambda: all(status(factory, i) == "AWAITING_ANALYST" for i in ids))
    finally:
        d.stop()


def test_sweeper_picks_up_a_reset_alert(factory):
    aid = ingest(factory, 1)
    calls = []

    def counting(f, i):
        calls.append(i)
        return mock_process(f, i)

    d = Dispatcher(factory, 2, 0.2, process=counting)
    d.start()
    try:
        assert wait_until(lambda: len(calls) >= 1 and status(factory, aid) == "AWAITING_ANALYST")
        set_status(factory, aid, "PENDING_REVIEW", 0)
        assert wait_until(lambda: len(calls) >= 2)
        assert wait_until(lambda: status(factory, aid) == "AWAITING_ANALYST")
    finally:
        d.stop()


def test_no_double_dispatch_while_in_flight(factory):
    calls, gate = [], threading.Event()

    def slow(f, i):
        calls.append(i)
        gate.wait(5)

    d = Dispatcher(factory, 2, 60, process=slow)         # not started: submit() directly
    x = uuid.uuid4()
    assert d.submit(x) is True and d.submit(x) is False
    gate.set()
    assert wait_until(lambda: d.inflight_count() == 0)
    d.stop()
    assert calls == [x]


def test_one_bad_alert_does_not_stop_the_others(factory):
    ids = [ingest(factory, i, ts=T0 + timedelta(seconds=i)) for i in range(1, 5)]
    bad = ids[0]

    def proc(f, i):
        if i == bad:
            raise RuntimeError("boom")
        return mock_process(f, i)

    d = Dispatcher(factory, 2, 60, process=proc)
    d.start()
    try:
        assert wait_until(lambda: all(status(factory, i) == "AWAITING_ANALYST" for i in ids[1:]))
        assert d.alive
    finally:
        d.stop()
    assert status(factory, bad) == "PENDING_REVIEW"       # left for the sweeper to retry


def test_dispatcher_with_the_real_partial_helper(factory):
    aid = ingest(factory, 1)
    d = Dispatcher(factory, 2, 0.2, process=partial(process_alert, adapter=MockAdapter()))
    d.start()
    try:
        assert wait_until(lambda: status(factory, aid) == "AWAITING_ANALYST")
    finally:
        d.stop()
