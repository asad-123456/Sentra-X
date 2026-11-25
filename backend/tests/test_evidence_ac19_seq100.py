"""AC-19 evidence (mock only): seq_100.jsonl one alert at a time through the real ingestion path and the
shipped worker. Latency = from the commit of the PENDING_REVIEW row (ingest_raws returns after commit) until the
status becomes AWAITING_ANALYST. MOCK WITH SIMULATED DELAY, NOT A LIVE-PROVIDER MEASUREMENT.

PowerShell (same window as the other test databases, from backend/):
  $env:SENTRAX_RUN_PERF_TESTS='1'
  $env:MOCK_DELAY_MIN_SECONDS='0.5'; $env:MOCK_DELAY_MAX_SECONDS='2'
  $env:DATABASE_URL=$env:SENTRAX_INTEGRATION_DATABASE_URL
  python -m pytest -rs -s tests/test_evidence_ac19_seq100.py
"""
import math
import os
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.ingestion import service
from app.ingestion.sources import ReplaySource
from app.worker.jobs import TriageQueue
from app.worker.triage_worker import MAX_WORKERS, TriageWorker, build_adapter
from app.worker.worker_settings import get_worker_settings

_REPLAY = Path(__file__).parent / "fixtures" / "replay" / "seq_100.jsonl"
_STATUS = text("SELECT status FROM alerts WHERE wazuh_alert_id = :w")


@pytest.mark.skipif(os.getenv("SENTRAX_RUN_PERF_TESTS") != "1", reason="enable the benchmark explicitly")
def test_seq_100_one_at_a_time_latency(contributor_test_engine, monkeypatch):
    factory = sessionmaker(bind=contributor_test_engine)
    scope = f"seq-{uuid.uuid4().hex[:8]}-"
    settings = get_worker_settings().model_copy(update={"LLM_PROVIDER": "mock"})
    workers = max(1, min(settings.TRIAGE_WORKERS, MAX_WORKERS))
    replay = ReplaySource(_REPLAY).fetch()
    assert len(replay) == 100
    for raw in replay:
        raw["id"] = f'{scope}{raw["id"]}'
        raw["agent"]["id"] = f'{scope}{raw["agent"]["id"]}'

    queue = TriageQueue()
    monkeypatch.setattr(service, "enqueue_triage", queue.enqueue)
    worker = TriageWorker(build_adapter(settings), workers, settings.TRIAGE_SWEEP_SECONDS,
                          session_factory=factory, work_queue=queue)
    waits, manual, timeouts = [], 0, 0
    worker.start()
    try:
        for raw in replay:
            summary = service.ingest_raws(factory, [raw], min_level=4)
            assert summary.inserted == 1
            t0 = time.monotonic()                      # the PENDING_REVIEW row is committed here
            status = "PENDING_REVIEW"
            while time.monotonic() - t0 < 30:
                with factory() as s:
                    status = s.execute(_STATUS, {"w": raw["id"]}).scalar_one()
                if status != "PENDING_REVIEW":
                    break
                time.sleep(0.02)
            waits.append(time.monotonic() - t0)
            manual += status == "NEEDS_MANUAL_TRIAGE"
            timeouts += status == "PENDING_REVIEW"
        waits.sort()
        p95 = waits[math.ceil(len(waits) * 0.95) - 1]
        print(f"\nAC-19 (mock with simulated delay, NOT a live-provider measurement): "
              f"workers={workers}, delay={settings.MOCK_DELAY_MIN_SECONDS}-{settings.MOCK_DELAY_MAX_SECONDS}s, "
              f"alerts={len(waits)}, max={waits[-1]:.2f}s, p95={p95:.2f}s, mean={sum(waits)/len(waits):.2f}s, "
              f"needs_manual_triage={manual}, not_finished_in_30s={timeouts}")
        assert timeouts == 0 and manual == 0
        assert waits[-1] <= 8
    finally:
        worker.stop()
        with factory.begin() as s:
            s.execute(text("DELETE FROM alerts WHERE wazuh_alert_id LIKE :p"), {"p": scope + "%"})
            s.execute(text("DELETE FROM assets WHERE agent_id LIKE :p"), {"p": scope + "%"})
