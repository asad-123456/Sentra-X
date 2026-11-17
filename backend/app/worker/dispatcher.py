"""Thread pool + queue reader + sweeper. Run exactly ONE backend process (never uvicorn --workers 2 or more)."""
from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from sqlalchemy import select

from app.models.alert import Alert
from app.worker.jobs import triage_queue

log = logging.getLogger("sentrax.worker")


class Dispatcher:
    def __init__(self, session_factory, workers: int, sweep_seconds: float, process: Callable):
        """process(factory, alert_id) does the work for one alert (see processor.process_alert)."""
        self.factory = session_factory
        self.sweep_seconds = sweep_seconds
        self._process = process
        self._pool = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="triage")
        self._inflight: set[uuid.UUID] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def inflight_count(self) -> int:
        with self._lock:
            return len(self._inflight)

    def submit(self, alert_id: uuid.UUID) -> bool:
        """False if it is already being processed (no double dispatch)."""
        with self._lock:
            if self._stop.is_set() or alert_id in self._inflight:
                return False
            self._inflight.add(alert_id)
        self._pool.submit(self._run, alert_id)
        return True

    def _run(self, alert_id: uuid.UUID) -> None:
        try:
            self._process(self.factory, alert_id)
        except Exception:                    # a bad alert must never kill the worker
            log.exception("worker error on alert %s", alert_id)
        finally:
            with self._lock:
                self._inflight.discard(alert_id)

    def sweep(self) -> int:
        """Picks up PENDING_REVIEW alerts: restart recovery, Retry AI, and alerts ingested by another process
        (for example the replay CLI, whose in-memory queue this process never sees)."""
        with self.factory() as s:
            ids = s.execute(
                select(Alert.id).where(Alert.status == "PENDING_REVIEW")
                .order_by(Alert.ingested_at).limit(2000)).scalars().all()
        return sum(1 for i in ids if self.submit(i))

    def _loop(self) -> None:
        last_sweep: Optional[float] = None
        while not self._stop.is_set():
            now = time.monotonic()
            if last_sweep is None or now - last_sweep >= self.sweep_seconds:
                try:
                    self.sweep()
                except Exception as exc:
                    log.warning("sweep failed, will retry: %s", exc)
                last_sweep = now
            try:
                alert_id = triage_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self.submit(alert_id)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="triage-dispatcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._pool.shutdown(wait=False, cancel_futures=True)

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
