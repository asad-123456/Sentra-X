"""One entry point used by the replay CLI, the poller and the webhook."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from app.ingestion.batch import process_batch
from app.ingestion.persistence import persist_alerts
from app.ingestion.wazuh_settings import get_wazuh_settings
from app.worker.jobs import enqueue_triage

log = logging.getLogger("sentrax.ingestion")


@dataclass
class IngestSummary:
    received: int = 0
    noise: int = 0
    invalid: int = 0
    duplicate_in_batch: int = 0
    accepted: int = 0
    inserted: int = 0
    db_duplicates: int = 0
    assets_registered: int = 0
    manual_triage: int = 0  # stored with an unusable rule.level, NEEDS_MANUAL_TRIAGE, not queued


def ingest_raws(session_factory, raws: Iterable[dict], min_level: Optional[int] = None) -> IngestSummary:
    level = get_wazuh_settings().WAZUH_MIN_LEVEL if min_level is None else min_level
    batch = process_batch(raws, level)
    queued, manual, assets_new = [], [], 0
    if batch.alerts:
        with session_factory.begin() as session:  # one transaction, commits on exit
            queued, manual, assets_new = persist_alerts(session, batch.alerts)
    for alert_id in queued:  # enqueue only AFTER the commit succeeded
        enqueue_triage(alert_id)
    s = batch.stats
    summary = IngestSummary(
        received=s.received, noise=s.noise, invalid=s.invalid,
        duplicate_in_batch=s.duplicate_in_batch, accepted=s.accepted,
        inserted=len(queued) + len(manual), db_duplicates=s.accepted - len(queued) - len(manual),
        assets_registered=assets_new, manual_triage=len(manual),
    )
    log.info("ingest batch: %s", summary)
    return summary
