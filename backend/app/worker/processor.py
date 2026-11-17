"""Processes ONE alert: PENDING_REVIEW -> AWAITING_ANALYST (or NEEDS_MANUAL_TRIAGE). Never raises.
Only humans set CLOSED or ESCALATED; this module never does.

Three steps, so no database connection is held during the slow model call:
  1. short transaction: load the alert, asset tier, correlated alerts, exemplars (hit counts bumped), commit
  2. no database:       Abdur's pipeline (evidence pack -> model call with retries -> guardrails)
  3. one transaction:   guarded status update + evidence_packs / ai_assessments upsert
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import timedelta
from typing import Any, Callable, Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.assets.service import get_asset_tier
from app.exemplars.service import find_exemplars
from app.models.ai_assessment import AIAssessment
from app.models.alert import Alert
from app.models.evidence_pack import EvidencePack as EvidencePackRow
from app.services.evidence_assembler import AlertRecord, CorrelatedAlert
from app.services.llm_adapter import InjectedExemplar, LLMAdapter
from app.worker.bridge import Context, TriageOutcome, run_pipeline

log = logging.getLogger("sentrax.worker")

PENDING = "PENDING_REVIEW"
AWAITING = "AWAITING_ANALYST"
MANUAL = "NEEDS_MANUAL_TRIAGE"
CORRELATION_WINDOW = timedelta(hours=24)
MAX_CORRELATED = 5
FAILURE_RETRY_COUNT = 3


def to_json(value: Any) -> Any:
    """Make anything JSON-storable (datetimes, UUIDs -> strings)."""
    return json.loads(json.dumps(value, default=str))


def fetch_correlated(session: Session, alert: Alert) -> list[Alert]:
    """Same agent OR same src_ip, within 24 h BEFORE this alert, excluding itself, newest first, max 5, any
    status. A NULL src_ip never matches."""
    cond = Alert.agent_id == alert.agent_id
    if alert.src_ip is not None:
        cond = or_(cond, Alert.src_ip == alert.src_ip)
    stmt = (
        select(Alert)
        .where(cond, Alert.id != alert.id,
               Alert.alert_timestamp <= alert.alert_timestamp,
               Alert.alert_timestamp >= alert.alert_timestamp - CORRELATION_WINDOW)
        .order_by(Alert.alert_timestamp.desc(), Alert.id)
        .limit(MAX_CORRELATED)
    )
    return list(session.execute(stmt).scalars())


def _load_context(factory, alert_id: uuid.UUID) -> Optional[Context]:
    with factory.begin() as s:
        alert = s.get(Alert, alert_id)
        if alert is None or alert.status != PENDING:
            return None
        tier = get_asset_tier(s, alert.agent_id)
        correlated = fetch_correlated(s, alert)
        found = find_exemplars(s, alert_id=alert.id, rule_id=alert.rule_id,
                               process_signature=alert.process_signature, asset_criticality=tier)
        record = AlertRecord(
            wazuh_alert_id=alert.wazuh_alert_id, alert_timestamp=alert.alert_timestamp,
            rule_id=alert.rule_id, rule_level=alert.rule_level, rule_description=alert.rule_description,
            agent_id=alert.agent_id, agent_name=alert.agent_name, src_ip=alert.src_ip,
            process_signature=alert.process_signature,
            raw_payload=alert.raw_payload if isinstance(alert.raw_payload, dict) else {})
        return Context(
            record=record, tier=tier,
            correlated=[CorrelatedAlert(
                wazuh_alert_id=c.wazuh_alert_id, alert_timestamp=c.alert_timestamp, rule_id=c.rule_id,
                rule_level=c.rule_level, rule_description=c.rule_description, agent_id=c.agent_id,
                src_ip=c.src_ip) for c in correlated],
            exemplars=[InjectedExemplar(**{k: f[k] for k in (
                "id", "match_tier", "rule_id", "process_signature", "asset_criticality",
                "calibrated_verdict", "calibrated_severity", "rationale")}) for f in found])


def _set_status(session: Session, alert_id: uuid.UUID, status: str, retry_count: int) -> bool:
    """Guarded: only touches an alert that is STILL PENDING_REVIEW."""
    res = session.execute(
        update(Alert).where(Alert.id == alert_id, Alert.status == PENDING)
        .values(status=status, retry_count=retry_count, updated_at=func.now())
        .execution_options(synchronize_session=False))
    return res.rowcount == 1


def upsert_pack(session: Session, alert_id: uuid.UUID, outcome: TriageOutcome) -> None:
    pack = outcome.pack
    stmt = pg_insert(EvidencePackRow.__table__).values(
        alert_id=alert_id, pack_json=to_json(pack.pack), valid_dot_keys=to_json(pack.valid_dot_keys),
        injection_suspect=bool(pack.injection_suspect),
        injected_exemplar_ids=to_json(pack.injected_exemplar_ids))
    session.execute(stmt.on_conflict_do_update(
        index_elements=["alert_id"],
        set_={"pack_json": stmt.excluded.pack_json, "valid_dot_keys": stmt.excluded.valid_dot_keys,
              "injection_suspect": stmt.excluded.injection_suspect,
              "injected_exemplar_ids": stmt.excluded.injected_exemplar_ids,
              "updated_at": func.now()}))


_ASSESSMENT_UPDATE = ("raw_verdict", "raw_severity", "effective_verdict", "effective_severity",
                      "confidence_score", "cited_evidence_keys", "explanation", "safety_floor_triggered",
                      "abstention_triggered", "guardrail_audit_note", "llm_provider", "model_name",
                      "latency_ms", "inference_latency_ms", "retry_count")


def upsert_assessment(session: Session, alert_id: uuid.UUID, outcome: TriageOutcome) -> None:
    out, gr, res = outcome.result.output, outcome.guardrail, outcome.result
    vals = dict(
        raw_verdict=out.verdict, raw_severity=out.recommended_severity,
        effective_verdict=gr.effective_verdict, effective_severity=gr.effective_severity,
        confidence_score=out.confidence_score, cited_evidence_keys=to_json(out.cited_evidence_keys),
        explanation=out.explanation, safety_floor_triggered=gr.safety_floor_triggered,
        abstention_triggered=gr.abstention_triggered, guardrail_audit_note=gr.guardrail_audit_note or None,
        llm_provider=outcome.provider, model_name=(res.model_name or "")[:64],
        latency_ms=res.inference_latency_ms, inference_latency_ms=res.inference_latency_ms,
        retry_count=res.retry_count)
    stmt = pg_insert(AIAssessment.__table__).values(alert_id=alert_id, **vals)
    session.execute(stmt.on_conflict_do_update(
        index_elements=["alert_id"],
        set_={**{k: stmt.excluded[k] for k in _ASSESSMENT_UPDATE}, "updated_at": func.now()}))


def _fallback_manual(factory, alert_id: uuid.UUID) -> str:
    try:
        with factory.begin() as s:
            _set_status(s, alert_id, MANUAL, FAILURE_RETRY_COUNT)
    except Exception:
        log.exception("could not even mark alert %s as manual triage", alert_id)   # stays PENDING: sweeper retries
        return "error"
    return "failed"


def process_alert(factory, alert_id: uuid.UUID, adapter: LLMAdapter,
                  run: Callable[[Context, LLMAdapter], TriageOutcome] = run_pipeline) -> str:
    """Returns 'done' | 'failed' | 'skipped' | 'superseded' | 'error'."""
    started = time.monotonic()
    try:
        ctx = _load_context(factory, alert_id)
    except Exception:
        log.exception("could not load alert %s", alert_id)
        return "error"
    if ctx is None:
        return "skipped"

    try:                                   # no retry loop here: triage_alert owns the model retries
        outcome = run(ctx, adapter)
    except Exception as exc:
        log.exception("pipeline crashed for alert %s", alert_id)
        outcome = TriageOutcome(None, None, None, "unknown", f"{type(exc).__name__}: {exc}")

    status = AWAITING if outcome.ok else MANUAL
    retries = outcome.result.retry_count if outcome.ok else FAILURE_RETRY_COUNT
    try:
        with factory() as s:               # ONE transaction
            if not _set_status(s, alert_id, status, retries):
                s.rollback()
                log.info("alert %s changed while triaging; result discarded", alert_id)
                return "superseded"
            if outcome.pack is not None:   # keep the evidence pack even when the model failed
                upsert_pack(s, alert_id, outcome)
            if outcome.ok:
                upsert_assessment(s, alert_id, outcome)
            s.commit()
    except Exception:
        log.exception("could not save triage result for alert %s", alert_id)
        return _fallback_manual(factory, alert_id)

    log.info("triaged alert=%s status=%s retries=%d in %.2fs%s", alert_id, status, retries,
             time.monotonic() - started, "" if outcome.ok else f" error={outcome.error}")
    return "done" if outcome.ok else "failed"
