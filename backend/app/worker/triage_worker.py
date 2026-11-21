"""Triage worker (Part 6B): turns PENDING_REVIEW alerts into AWAITING_ANALYST or NEEDS_MANUAL_TRIAGE.

For each alert id taken from triage_queue:
  1. short transaction: load_triage_inputs (tier, correlated alerts, exemplars), then commit
  2. run_triage_pipeline: no database connection is held during the slow LLM call
  3. new transaction: persist_outcome saves the pack and assessment and sets the status, then commit
Failures send the current attempt to NEEDS_MANUAL_TRIAGE.
A sweeper thread re-queues PENDING_REVIEW alerts that never reached a worker (the queue is
in memory, so a restart loses it).

Run on its own with:  python -m app.worker.triage_worker
"""
import logging
import queue
import random
import threading
import time
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text

from app.assets.service import get_asset_tier
from app.database import SyncSessionLocal
from app.exemplars.service import find_exemplars
from app.services.llm_adapter import LLMAdapter, MockAdapter, get_adapter
from app.services.triage_pipeline import STATUS_NEEDS_MANUAL_TRIAGE, run_triage_pipeline
from app.services.triage_store import STATUS_PENDING_REVIEW, load_triage_inputs, persist_outcome
from app.worker.jobs import TriageQueue, triage_queue
from app.worker.worker_settings import WorkerSettings, get_worker_settings

logger = logging.getLogger(__name__)

# The default sync pool holds 15 connections; more threads than this would wait for one.
MAX_WORKERS = 12
SWEEP_BATCH = 500

_SQL_ATTEMPT = text("SELECT status, triage_generation FROM alerts WHERE id = CAST(:id AS uuid)")
_SQL_PENDING = text(
    "SELECT id FROM alerts WHERE status = 'PENDING_REVIEW' ORDER BY ingested_at LIMIT :n"
)
_SQL_MANUAL = text("""
    UPDATE alerts SET status = 'NEEDS_MANUAL_TRIAGE', updated_at = now()
    WHERE id = CAST(:id AS uuid) AND status = 'PENDING_REVIEW' AND triage_generation = :generation
""")


class _DelayedMock(MockAdapter):
    """Mock model with simulated latency, for load tests (AC-19, AC-22)."""

    def __init__(self, delay_min: float, delay_max: float, **switches: Any):
        super().__init__(**switches)
        self._delay_min, self._delay_max = delay_min, delay_max

    def generate(self, system_prompt: str, user_prompt: str, timeout_s: float) -> str:
        if self._delay_max > 0:
            time.sleep(random.uniform(self._delay_min, self._delay_max))
        return super().generate(system_prompt, user_prompt, timeout_s)


def build_adapter(settings: Optional[WorkerSettings] = None) -> LLMAdapter:
    """One adapter per process, shared by all threads. Mock unless LLM_PROVIDER says otherwise."""
    s = settings or get_worker_settings()
    provider = s.LLM_PROVIDER.strip().lower()
    if provider != "mock":
        return get_adapter(provider)
    base = get_adapter("mock")      # honours the MOCK_* switches in the environment
    return _DelayedMock(
        s.MOCK_DELAY_MIN_SECONDS, s.MOCK_DELAY_MAX_SECONDS,
        failure_mode=base.failure_mode, fail_times=base.fail_times,
        gullible=base.gullible, abstain_on_empty=base.abstain_on_empty,
    )


def _to_manual_triage(alert_id: UUID, generation: int, session_factory: Any) -> str | None:
    try:
        with session_factory() as s:
            moved = s.execute(_SQL_MANUAL, {"id": str(alert_id), "generation": generation}).rowcount
            s.commit()
        return STATUS_NEEDS_MANUAL_TRIAGE if moved else None
    except Exception:
        logger.exception("Could not move alert %s to manual triage", alert_id)
        return None


def process_alert(
    alert_id: UUID,
    adapter: LLMAdapter,
    *,
    session_factory: Any = SyncSessionLocal,
    tier_lookup: Any = get_asset_tier,
    exemplar_lookup: Any = find_exemplars,
) -> Optional[str]:
    """Triage one alert. Return the committed status, or None if no status changed."""
    generation = None
    try:
        with session_factory() as s:
            attempt = s.execute(_SQL_ATTEMPT, {"id": str(alert_id)}).first()
            if attempt is None or attempt.status != STATUS_PENDING_REVIEW:
                return None
            generation = attempt.triage_generation
            inputs = load_triage_inputs(
                s, alert_id, tier_lookup=tier_lookup, exemplar_lookup=exemplar_lookup
            )
            s.commit()              # keeps the exemplar hit counts
        outcome = run_triage_pipeline(inputs, adapter)
        with session_factory() as s:
            status = persist_outcome(s, alert_id, outcome, expected_generation=generation)
            s.commit()
        return status
    except Exception:
        logger.exception("Triage failed for alert %s", alert_id)
        if generation is not None:
            return _to_manual_triage(alert_id, generation, session_factory)
        return None


class TriageWorker:
    def __init__(
        self,
        adapter: LLMAdapter,
        workers: int,
        sweep_seconds: float,
        *,
        session_factory: Any = SyncSessionLocal,
        work_queue: Optional[TriageQueue] = None,
        **lookups: Any,
    ):
        self._adapter = adapter
        self._workers = workers
        self._sweep_seconds = sweep_seconds
        self._session_factory = session_factory
        self._queue = triage_queue if work_queue is None else work_queue
        self._lookups = lookups
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._inflight: set = set()
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return self._adapter.provider_name

    @property
    def model_name(self) -> str:
        return self._adapter.model_name

    @property
    def active_workers(self) -> int:
        return sum(thread.is_alive() for thread in self._threads if thread.name != "triage-sweeper")

    def start(self) -> None:
        for n in range(self._workers):
            self._spawn(self._loop, f"triage-{n}")
        self._spawn(self._sweep_loop, "triage-sweeper")

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        deadline = time.monotonic() + timeout
        for t in self._threads:
            t.join(max(0.0, deadline - time.monotonic()))
        self._threads.clear()

    def _spawn(self, target: Any, name: str) -> None:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        self._threads.append(t)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                alert_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                with self._lock:
                    if alert_id in self._inflight:
                        continue
                    self._inflight.add(alert_id)
                try:
                    process_alert(alert_id, self._adapter,
                                  session_factory=self._session_factory, **self._lookups)
                except Exception:
                    logger.exception("Unexpected error while triaging %s", alert_id)
                finally:
                    with self._lock:
                        self._inflight.discard(alert_id)
            finally:
                self._queue.task_done()

    def _sweep_loop(self) -> None:
        while not self._stop.is_set():
            self.sweep_once()
            self._stop.wait(self._sweep_seconds)

    def sweep_once(self) -> int:
        """Recover a batch of pending alerts even while new jobs are arriving."""
        try:
            with self._session_factory() as s:
                ids = [r[0] for r in s.execute(_SQL_PENDING, {"n": SWEEP_BATCH}).all()]
        except Exception:
            logger.exception("Sweep failed")
            return 0
        with self._lock:
            return sum(self._queue.enqueue(alert_id) for alert_id in ids if alert_id not in self._inflight)


_worker: Optional[TriageWorker] = None


def start_worker() -> Optional[TriageWorker]:
    """Start the worker if TRIAGE_ENABLED. Safe to call twice."""
    global _worker
    s = get_worker_settings()
    if not s.TRIAGE_ENABLED or _worker is not None:
        return _worker
    workers = max(1, min(s.TRIAGE_WORKERS, MAX_WORKERS))
    _worker = TriageWorker(build_adapter(s), workers, s.TRIAGE_SWEEP_SECONDS)
    _worker.start()
    logger.info("Triage worker started: %d threads, provider=%s", workers, s.LLM_PROVIDER)
    return _worker


def stop_worker() -> None:
    global _worker
    if _worker is not None:
        _worker.stop()
        _worker = None


if __name__ == "__main__":     # worker only, no API: it finds work through the sweeper
    logging.basicConfig(level=logging.INFO)
    if start_worker() is not None:
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            stop_worker()
