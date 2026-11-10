"""Batch helpers: noise/invalid counters, in-batch dedup, polling cursor."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Optional

from app.ingestion.parser import ParsedAlert, parse_alert

log = logging.getLogger("sentrax.ingestion")


@dataclass
class BatchStats:
    received: int = 0
    noise: int = 0
    invalid: int = 0
    duplicate_in_batch: int = 0
    accepted: int = 0


@dataclass
class BatchResult:
    alerts: list[ParsedAlert] = field(default_factory=list)
    stats: BatchStats = field(default_factory=BatchStats)


def process_batch(raws: Iterable[dict], min_level: int = 4) -> BatchResult:
    """Parse, filter and de-duplicate a batch. The DB's ON CONFLICT (Part 4)
    is the final dedup; this removes repeats inside one batch."""
    result = BatchResult()
    stats = result.stats
    seen: set[str] = set()
    for raw in raws:
        stats.received += 1
        outcome = parse_alert(raw, min_level)
        if outcome.status == "noise":
            stats.noise += 1
        elif outcome.status == "invalid":
            stats.invalid += 1
            log.warning("skipping invalid alert: %s", outcome.reason)
        else:
            alert = outcome.alert
            assert alert is not None
            if alert.wazuh_alert_id in seen:
                stats.duplicate_in_batch += 1
                continue
            seen.add(alert.wazuh_alert_id)
            result.alerts.append(alert)
            stats.accepted += 1
    return result


def next_cursor(latest: Optional[datetime], overlap_seconds: int = 60) -> Optional[datetime]:
    """Polling cursor = newest alert_timestamp minus overlap. The unique
    wazuh_alert_id makes re-reading the overlap harmless. None means start fresh."""
    if latest is None:
        return None
    return latest - timedelta(seconds=overlap_seconds)