"""Opt-in AC-19/AC-22 load check using the worker already shipped in main."""
import math
import os
from pathlib import Path
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.ingestion import service
from app.ingestion.sources import ReplaySource
from app.worker.jobs import TriageQueue
from app.worker.triage_worker import MAX_WORKERS, TriageWorker, build_adapter
from app.worker.worker_settings import get_worker_settings

_REPLAY = Path(__file__).parent / "fixtures" / "replay" / "stream_3000.jsonl"
_PENDING = text("SELECT count(*) FROM alerts WHERE status = 'PENDING_REVIEW'")


@pytest.mark.skipif(os.getenv("SENTRAX_RUN_PERF_TESTS") != "1", reason="enable the sustained intake benchmark explicitly")
def test_sustained_mock_ingestion(contributor_test_engine, monkeypatch):
    factory = sessionmaker(bind=contributor_test_engine)
    with factory() as session:
        assert session.execute(text("SELECT count(*) FROM alerts")).scalar_one() == 0, "Load test requires an empty alerts table"

    scope = f"load-{uuid.uuid4().hex[:8]}-"
    settings = get_worker_settings().model_copy(update={"LLM_PROVIDER": "mock"})
    assert 0 <= settings.MOCK_DELAY_MIN_SECONDS <= settings.MOCK_DELAY_MAX_SECONDS
    worker_count = max(1, min(settings.TRIAGE_WORKERS, MAX_WORKERS))
    replay = ReplaySource(_REPLAY).fetch()
    assert len(replay) == 3000
    for raw in replay:
        raw["id"] = f'{scope}{raw["id"]}'
        raw["agent"]["id"] = f'{scope}{raw["agent"]["id"]}'

    queue = TriageQueue()
    monkeypatch.setattr(service, "enqueue_triage", queue.enqueue)
    worker = TriageWorker(
        build_adapter(settings), worker_count, settings.TRIAGE_SWEEP_SECONDS,
        session_factory=factory, work_queue=queue,
    )

    def pending_count():
        with factory() as session:
            return session.execute(_PENDING).scalar_one()

    max_pending = 0
    started = time.monotonic()
    worker.start()
    try:
        for index, raw in enumerate(replay, start=1):
            summary = service.ingest_raws(factory, [raw], min_level=4)
            assert summary.inserted == 1
            max_pending = max(max_pending, pending_count())
            time.sleep(max(0, started + index / 5 - time.monotonic()))
        ingest_seconds = time.monotonic() - started
        drain_deadline = time.monotonic() + 300
        while pending_count() and time.monotonic() < drain_deadline:
            time.sleep(0.25)
        with factory() as session:
            durations = session.execute(text("""
                SELECT extract(epoch FROM (ai.created_at - al.ingested_at))
                FROM alerts al JOIN ai_assessments ai ON ai.alert_id = al.id
                WHERE al.status = 'AWAITING_ANALYST'
                ORDER BY 1
            """)).scalars().all()
        assert len(durations) == len(replay), "Some alerts failed or did not finish before the drain deadline"
        p95 = durations[math.ceil(len(durations) * 0.95) - 1]
        print(
            f"workers={worker_count}, simulated delay="
            f"{settings.MOCK_DELAY_MIN_SECONDS}-{settings.MOCK_DELAY_MAX_SECONDS}s, "
            f"feed={len(replay) / ingest_seconds:.2f}/s, sampled backlog={max_pending}, "
            f"triage p95={p95:.2f}s, max={durations[-1]:.2f}s"
        )
        assert ingest_seconds <= len(replay) / 5 + 1, "Could not sustain the target replay rate"
        assert max_pending <= 500
        assert durations[-1] <= 8
    finally:
        worker.stop()
        with factory.begin() as session:
            session.execute(text("DELETE FROM alerts WHERE wazuh_alert_id LIKE :prefix"), {"prefix": scope + "%"})
            session.execute(text("DELETE FROM assets WHERE agent_id LIKE :prefix"), {"prefix": scope + "%"})
