"""AC-19 (latency) and AC-22 (throughput) with the real worker and the mock model plus a simulated delay.

PowerShell, from the repo root (the database MUST be named *_perf, the script truncates its tables):
  $env:DATABASE_URL="postgresql+psycopg://sentrax:sentrax@localhost:5432/sentrax_perf"
  $env:LLM_PROVIDER="mock"; $env:MOCK_DELAY_MIN_SECONDS="2"; $env:MOCK_DELAY_MAX_SECONDS="6"
  python backend\\scripts\\load_test.py --file backend\\tests\\fixtures\\replay\\seq_100.jsonl --rate 1
  python backend\\scripts\\load_test.py --file backend\\tests\\fixtures\\replay\\stream_3000.jsonl --rate 5
Afterwards: Remove-Item Env:DATABASE_URL, Env:LLM_PROVIDER, Env:MOCK_DELAY_MIN_SECONDS, Env:MOCK_DELAY_MAX_SECONDS
"""
from __future__ import annotations

import argparse
import functools
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import settings  # noqa: E402


def ensure_database(url) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.execute(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": url.database}).scalar():
            c.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--rate", type=float, default=5.0, help="alerts per second")
    ap.add_argument("--drain-timeout", type=float, default=300.0)
    args = ap.parse_args()

    url = make_url(settings.DATABASE_URL)
    if not (url.database or "").endswith("_perf"):
        sys.exit("Refusing to run: DATABASE_URL must point at a database whose name ends in _perf")
    if settings.LLM_PROVIDER.lower() != "mock":
        sys.exit("Set LLM_PROVIDER=mock for this test")
    ensure_database(url)

    import app.models  # noqa: F401
    from app.database import sync_engine
    from app.ingestion.db_access import get_session_factory
    from app.ingestion.service import ingest_raws
    from app.ingestion.sources import ReplaySource
    from app.ingestion.wazuh_settings import get_wazuh_settings
    from app.models.base import Base
    from app.worker.bridge import build_adapter
    from app.worker.dispatcher import Dispatcher
    from app.worker.processor import process_alert
    from app.worker.worker_settings import get_worker_settings

    Base.metadata.create_all(sync_engine)
    factory = get_session_factory()
    with factory.begin() as ses:
        ses.execute(text("TRUNCATE feedback_exemplars, evidence_packs, ai_assessments, alerts, assets, users CASCADE"))

    def pending() -> int:
        with factory() as ses:
            return ses.execute(text("SELECT count(*) FROM alerts WHERE status='PENDING_REVIEW'")).scalar()

    state = {"max": 0}
    stop = threading.Event()

    def sampler() -> None:
        while not stop.is_set():
            state["max"] = max(state["max"], pending())
            stop.wait(2)

    w, tw = get_wazuh_settings(), get_worker_settings()
    raws = ReplaySource(args.file).fetch()
    d = Dispatcher(factory, w.TRIAGE_WORKERS, tw.TRIAGE_SWEEP_SECONDS,
                   process=functools.partial(process_alert, adapter=build_adapter()))
    d.start()
    threading.Thread(target=sampler, daemon=True).start()
    print(f"feeding {len(raws)} alerts at {args.rate}/s, mock delay "
          f"{tw.MOCK_DELAY_MIN_SECONDS}-{tw.MOCK_DELAY_MAX_SECONDS}s, {w.TRIAGE_WORKERS} workers")

    chunk = max(1, round(args.rate))
    interval = chunk / args.rate
    nxt = time.monotonic()
    for i in range(0, len(raws), chunk):
        ingest_raws(factory, raws[i:i + chunk])
        nxt += interval
        time.sleep(max(0.0, nxt - time.monotonic()))

    deadline = time.time() + args.drain_timeout
    while pending() > 0 and time.time() < deadline:
        time.sleep(2)
    stop.set()
    d.stop()

    with factory() as ses:
        lat = sorted(float(x) for x in ses.execute(text(
            "SELECT extract(epoch FROM (x.created_at - a.ingested_at)) "
            "FROM ai_assessments x JOIN alerts a ON a.id = x.alert_id")).scalars())
        by_status = dict(ses.execute(text("SELECT status, count(*) FROM alerts GROUP BY status")).all())

    print("\nstatus counts:", by_status)
    if lat:
        p95 = lat[int(0.95 * (len(lat) - 1))]
        print(f"latency PENDING_REVIEW -> AWAITING_ANALYST: n={len(lat)} avg={sum(lat)/len(lat):.2f}s "
              f"p95={p95:.2f}s max={lat[-1]:.2f}s")
        print("AC-19 (max <= 8.0 s):", "PASS" if lat[-1] <= 8.0 else "FAIL")
    print(f"max backlog seen: {state['max']}")
    drained = by_status.get("PENDING_REVIEW", 0) == 0 and by_status.get("NEEDS_MANUAL_TRIAGE", 0) == 0
    print("AC-22 (backlog never above 500, all processed):",
          "PASS" if state["max"] <= 500 and drained else "FAIL")


if __name__ == "__main__":
    main()
