"""Background polling loop. Must never die: any error is logged and retried next cycle."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.ingestion.batch import next_cursor
from app.ingestion.parser import parse_timestamp
from app.ingestion.service import ingest_raws
from app.ingestion.sources import AlertSource
from app.models import Alert

log = logging.getLogger("sentrax.poller")


def _latest_ts(raws: list) -> Optional[datetime]:
    latest = None
    for r in raws:
        if not isinstance(r, dict):
            continue
        try:
            ts = parse_timestamp(r.get("timestamp"))
        except ValueError:
            continue
        if latest is None or ts > latest:
            latest = ts
    return latest


class Poller:
    def __init__(self, source: AlertSource, session_factory, interval: float,
                 min_level: int = 4, overlap_seconds: int = 60):
        self.source = source
        self.session_factory = session_factory
        self.interval = interval
        self.min_level = min_level
        self.overlap = overlap_seconds
        self.cursor: Optional[datetime] = None
        self._cursor_loaded = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _load_cursor(self) -> None:
        with self.session_factory() as s:
            latest = s.execute(select(func.max(Alert.alert_timestamp))).scalar()
        self.cursor = next_cursor(latest, self.overlap)
        self._cursor_loaded = True

    def run_once(self):
        if not self._cursor_loaded:
            self._load_cursor()
        raws = self.source.fetch(self.cursor)
        summary = ingest_raws(self.session_factory, raws, self.min_level)
        latest = _latest_ts(raws)  # includes noise, so the cursor still advances
        if latest is not None:
            new = next_cursor(latest, self.overlap)
            if self.cursor is None or new > self.cursor:
                self.cursor = new
        return summary

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:  # never kill the loop
                log.warning("wazuh_poll_failed error_type=%s", type(exc).__name__)
            self._stop.wait(self.interval)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="wazuh-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        # Close the httpx client after the thread exits so no in-flight request is interrupted
        if hasattr(self.source, "close"):
            self.source.close()

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
