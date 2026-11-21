"""DB writes for ingestion. Race-safe: ON CONFLICT DO NOTHING, never select-then-insert.
Uses Asad's ORM models (app/models)."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingestion.parser import ParsedAlert
from app.models import Alert, Asset

log = logging.getLogger("sentrax.ingestion")


def to_row(a: ParsedAlert) -> dict:
    row = {
        "wazuh_alert_id": a.wazuh_alert_id,
        "rule_id": a.rule_id,
        "rule_level": a.rule_level,
        "rule_description": a.rule_description,
        "agent_id": a.agent_id,
        "agent_name": a.agent_name,
        "src_ip": a.src_ip,
        "process_signature": a.process_signature,
        "mitre_tactics": a.mitre_tactics,
        "mitre_techniques": a.mitre_techniques,
        "raw_payload": a.raw_payload,
        "alert_timestamp": a.alert_timestamp,
        # ingested_at, updated_at, status=PENDING_REVIEW and retry_count=0 come from column defaults
    }
    if a.needs_manual_triage:
        row["status"] = "NEEDS_MANUAL_TRIAGE"  # unusable rule.level: a human decides, no LLM call
    return row


def ensure_asset(session: Session, a: ParsedAlert) -> bool:
    """Auto-register an unseen agent as MEDIUM. Never overwrites an existing asset.
    alerts.agent_id is a foreign key to assets, so this must run before the alert insert."""
    stmt = (
        pg_insert(Asset)
        .values(
            agent_id=a.agent_id,
            hostname=a.agent_name,
            ip_address=a.agent_ip,
            criticality_tier="MEDIUM",
            description="Auto-registered by Wazuh Ingestion Daemon",
            updated_by=None,
        )
        .on_conflict_do_nothing(index_elements=["agent_id"])
        .returning(Asset.agent_id)
    )
    return session.execute(stmt).first() is not None


def insert_alert(session: Session, a: ParsedAlert) -> uuid.UUID | None:
    """Returns the new alert id, or None if wazuh_alert_id already existed."""
    stmt = (
        pg_insert(Alert)
        .values(**to_row(a))
        .on_conflict_do_nothing(index_elements=["wazuh_alert_id"])
        .returning(Alert.id)
    )
    return session.execute(stmt).scalar_one_or_none()


def persist_alerts(session: Session, parsed: list[ParsedAlert]) -> tuple[list[uuid.UUID], list[uuid.UUID], int]:
    """Returns (queued_ids, manual_ids, assets_new). queued_ids are new PENDING_REVIEW alerts for the
    triage worker; manual_ids are new NEEDS_MANUAL_TRIAGE alerts, which are stored but not enqueued."""
    queued: list[uuid.UUID] = []
    manual: list[uuid.UUID] = []
    assets_new = 0
    for a in parsed:
        if ensure_asset(session, a):  # asset first: alerts.agent_id has a FK to assets
            assets_new += 1
        alert_id = insert_alert(session, a)
        if alert_id is None:
            continue
        if a.needs_manual_triage:
            manual.append(alert_id)
            log.warning("ingest_manual_triage alert_id=%s reason=invalid_rule_level stored_level=%d",
                        alert_id, a.rule_level)
        else:
            queued.append(alert_id)
    return queued, manual, assets_new
