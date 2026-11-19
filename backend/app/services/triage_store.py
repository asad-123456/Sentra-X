"""Database side of the triage pipeline (Part 6A-2).

    load_triage_inputs(session, alert_id)         phase 1, reads  -> TriageInputs
    run_triage_pipeline(inputs, adapter)          phase 2, no DB  (triage_pipeline.py)
    persist_outcome(session, alert_id, outcome)   phase 3, writes -> status it set

Neither function here commits; the caller owns the transaction. Plain SQL is used
instead of the ORM models so the column names are exactly the ones in the migrations.
"""
import json
import logging
from datetime import timezone
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.evidence_assembler import (
    CORRELATION_WINDOW,
    DEFAULT_CRITICALITY,
    MAX_CORRELATED,
    MAX_EXEMPLARS,
    AlertRecord,
    CorrelatedAlert,
    is_correlatable_ip,
)
from app.services.llm_adapter import InjectedExemplar
from app.services.triage_pipeline import (
    STATUS_AWAITING_ANALYST,
    STATUS_NEEDS_MANUAL_TRIAGE,
    TriageInputs,
    TriageOutcome,
    outcome_to_assessment_fields,
    outcome_to_pack_fields,
)

logger = logging.getLogger(__name__)

STATUS_PENDING_REVIEW = "PENDING_REVIEW"
_ALLOWED_NEXT_STATUS = {STATUS_AWAITING_ANALYST, STATUS_NEEDS_MANUAL_TRIAGE}
_MATCH_TIERS = ("Tier 1", "Tier 2")

TierLookup = Callable[[Session, str], Any]      # (session, agent_id) -> tier or None
ExemplarLookup = Callable[..., Any]             # Atta's find_exemplars(session, alert_id=..., ...)

# --- reads --------------------------------------------------------------------
_SQL_ALERT = text("""
    SELECT wazuh_alert_id, alert_timestamp, rule_id, rule_level, rule_description,
           agent_id, agent_name, src_ip, process_signature, raw_payload
    FROM alerts
    WHERE id = CAST(:alert_id AS uuid)
""")
_SQL_TIER = text("SELECT criticality_tier FROM assets WHERE agent_id = :agent_id")
_SQL_BY_AGENT = text("""
    SELECT wazuh_alert_id, alert_timestamp, rule_id, rule_level, rule_description,
           agent_id, src_ip
    FROM alerts
    WHERE agent_id = :agent_id
      AND id <> CAST(:alert_id AS uuid)
      AND alert_timestamp BETWEEN :lo AND :hi
    ORDER BY alert_timestamp DESC
    LIMIT :k
""")
_SQL_BY_IP = text("""
    SELECT wazuh_alert_id, alert_timestamp, rule_id, rule_level, rule_description,
           agent_id, src_ip
    FROM alerts
    WHERE src_ip = :src_ip AND src_ip IS NOT NULL
      AND id <> CAST(:alert_id AS uuid)
      AND alert_timestamp BETWEEN :lo AND :hi
    ORDER BY alert_timestamp DESC
    LIMIT :k
""")

# --- writes -------------------------------------------------------------------
_SQL_LOCK_ALERT = text(
    "SELECT status FROM alerts WHERE id = CAST(:alert_id AS uuid) FOR UPDATE"
)
_SQL_UPSERT_PACK = text("""
    INSERT INTO evidence_packs
        (alert_id, pack_json, valid_dot_keys, injection_suspect, injected_exemplar_ids)
    VALUES
        (CAST(:alert_id AS uuid), CAST(:pack_json AS jsonb), CAST(:valid_dot_keys AS jsonb),
         :injection_suspect, CAST(:injected_exemplar_ids AS jsonb))
    ON CONFLICT (alert_id) DO UPDATE SET
        pack_json = EXCLUDED.pack_json,
        valid_dot_keys = EXCLUDED.valid_dot_keys,
        injection_suspect = EXCLUDED.injection_suspect,
        injected_exemplar_ids = EXCLUDED.injected_exemplar_ids,
        updated_at = now()
""")
# latency_ms is kept equal to inference_latency_ms (the model calls it a synonym).
_SQL_UPSERT_ASSESSMENT = text("""
    INSERT INTO ai_assessments
        (alert_id, raw_verdict, raw_severity, effective_verdict, effective_severity,
         confidence_score, cited_evidence_keys, explanation,
         safety_floor_triggered, abstention_triggered, guardrail_audit_note,
         llm_provider, model_name, latency_ms, inference_latency_ms, retry_count)
    VALUES
        (CAST(:alert_id AS uuid), :raw_verdict, :raw_severity, :effective_verdict,
         :effective_severity, :confidence_score, CAST(:cited_evidence_keys AS jsonb),
         :explanation, :safety_floor_triggered, :abstention_triggered,
         :guardrail_audit_note, :llm_provider, :model_name,
         :inference_latency_ms, :inference_latency_ms, :retry_count)
    ON CONFLICT (alert_id) DO UPDATE SET
        raw_verdict = EXCLUDED.raw_verdict,
        raw_severity = EXCLUDED.raw_severity,
        effective_verdict = EXCLUDED.effective_verdict,
        effective_severity = EXCLUDED.effective_severity,
        confidence_score = EXCLUDED.confidence_score,
        cited_evidence_keys = EXCLUDED.cited_evidence_keys,
        explanation = EXCLUDED.explanation,
        safety_floor_triggered = EXCLUDED.safety_floor_triggered,
        abstention_triggered = EXCLUDED.abstention_triggered,
        guardrail_audit_note = EXCLUDED.guardrail_audit_note,
        llm_provider = EXCLUDED.llm_provider,
        model_name = EXCLUDED.model_name,
        latency_ms = EXCLUDED.latency_ms,
        inference_latency_ms = EXCLUDED.inference_latency_ms,
        retry_count = EXCLUDED.retry_count,
        updated_at = now()
""")
_SQL_DELETE_ASSESSMENT = text(
    "DELETE FROM ai_assessments WHERE alert_id = CAST(:alert_id AS uuid)"
)
_SQL_SET_STATUS = text("""
    UPDATE alerts
    SET status = :status, retry_count = :retry_count, updated_at = now()
    WHERE id = CAST(:alert_id AS uuid)
""")


# --- phase 1: load ------------------------------------------------------------
def _default_tier_lookup(session: Session, agent_id: str) -> str | None:
    row = session.execute(_SQL_TIER, {"agent_id": agent_id}).first()
    return row[0] if row else None


def _to_exemplar(item: Any) -> InjectedExemplar | None:
    """Turn one of Atta's dicts into an InjectedExemplar; skip anything malformed."""
    if isinstance(item, InjectedExemplar):
        return item
    try:
        tier = item["match_tier"]
        if tier not in _MATCH_TIERS:
            raise ValueError(tier)
        return InjectedExemplar(
            id=item["id"],
            match_tier=tier,
            rule_id=str(item["rule_id"]),
            process_signature=item.get("process_signature"),
            asset_criticality=item["asset_criticality"],
            calibrated_verdict=item["calibrated_verdict"],
            calibrated_severity=item["calibrated_severity"],
            rationale=item["rationale"],
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        logger.warning("Skipping a malformed exemplar")
        return None


def _load_candidates(session: Session, alert_id: UUID | str, alert: AlertRecord) -> list[CorrelatedAlert]:
    """One indexed query per match type. The union always contains the 5 most
    recent matches overall; duplicates (same alert matched by both) are dropped."""
    base = {
        "alert_id": str(alert_id),
        "lo": alert.alert_timestamp - CORRELATION_WINDOW,
        "hi": alert.alert_timestamp,
        "k": MAX_CORRELATED,
    }
    rows = list(session.execute(_SQL_BY_AGENT, {**base, "agent_id": alert.agent_id}).mappings())
    if is_correlatable_ip(alert.src_ip):
        rows += list(session.execute(_SQL_BY_IP, {**base, "src_ip": alert.src_ip}).mappings())
    seen: set[str] = set()
    out: list[CorrelatedAlert] = []
    for row in rows:
        if row["wazuh_alert_id"] in seen:
            continue
        seen.add(row["wazuh_alert_id"])
        out.append(CorrelatedAlert(**dict(row)))
    return out


def _load_exemplars(
    session: Session,
    lookup: ExemplarLookup | None,
    alert_id: UUID | str,
    alert: AlertRecord,
    tier: str | None,
) -> list[InjectedExemplar]:
    if lookup is None:
        return []
    try:
        # SAVEPOINT: a failing lookup must not poison the caller's transaction.
        with session.begin_nested():
            raw = lookup(
                session,
                alert_id=alert_id,
                rule_id=alert.rule_id,
                process_signature=alert.process_signature,
                asset_criticality=tier or DEFAULT_CRITICALITY,
            )
        items = [e for e in map(_to_exemplar, raw or ()) if e is not None]
    except Exception:
        logger.exception("Exemplar lookup failed; continuing without exemplars")
        return []
    return items[:MAX_EXEMPLARS]


def load_triage_inputs(
    session: Session,
    alert_id: UUID | str,
    *,
    tier_lookup: TierLookup | None = None,
    exemplar_lookup: ExemplarLookup | None = None,
) -> TriageInputs:
    """Read everything the run phase needs. Raises LookupError for an unknown alert.

    Read-only except that Atta's find_exemplars bumps match_hit_count, so the
    caller should commit (not roll back) after this if it wants those hits kept."""
    row = session.execute(_SQL_ALERT, {"alert_id": str(alert_id)}).mappings().first()
    if row is None:
        raise LookupError(f"alert {alert_id} not found")

    ts = row["alert_timestamp"]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    payload = row["raw_payload"]
    alert = AlertRecord(
        wazuh_alert_id=row["wazuh_alert_id"],
        alert_timestamp=ts,
        rule_id=row["rule_id"],
        rule_level=row["rule_level"],
        rule_description=row["rule_description"],
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        src_ip=row["src_ip"],
        process_signature=row["process_signature"],
        raw_payload=payload if isinstance(payload, dict) else {},
    )
    tier = (tier_lookup or _default_tier_lookup)(session, alert.agent_id)
    return TriageInputs(
        alert=alert,
        criticality_tier=tier,
        candidates=tuple(_load_candidates(session, alert_id, alert)),
        exemplars=tuple(_load_exemplars(session, exemplar_lookup, alert_id, alert, tier)),
    )


# --- phase 3: persist ---------------------------------------------------------
def _strip_nul(value: Any) -> Any:
    """PostgreSQL text and jsonb cannot hold NUL characters."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [_strip_nul(v) for v in value]
    if isinstance(value, dict):
        return {_strip_nul(k): _strip_nul(v) for k, v in value.items()}
    return value


def _j(value: Any) -> str:
    return json.dumps(_strip_nul(value))


def persist_outcome(session: Session, alert_id: UUID | str, outcome: TriageOutcome) -> str | None:
    """Save the pack and assessment and move the alert to outcome.next_status.

    Returns the status it set, or None (and writes nothing) if the alert is no
    longer PENDING_REVIEW, so a human decision is never overwritten. Does not commit.
    On a failed run the pack is kept, any old assessment is deleted, and the alert
    goes to NEEDS_MANUAL_TRIAGE. alerts.retry_count records the LLM retries used."""
    if outcome.next_status not in _ALLOWED_NEXT_STATUS:
        raise ValueError(
            f"triage may only set {sorted(_ALLOWED_NEXT_STATUS)}, got {outcome.next_status!r}"
        )
    key = {"alert_id": str(alert_id)}
    row = session.execute(_SQL_LOCK_ALERT, key).first()
    if row is None:
        raise LookupError(f"alert {alert_id} not found")
    if row[0] != STATUS_PENDING_REVIEW:
        logger.warning("Alert %s is %s, not PENDING_REVIEW; triage result not saved", alert_id, row[0])
        return None

    pack = outcome_to_pack_fields(outcome)
    if pack is not None:
        session.execute(
            _SQL_UPSERT_PACK,
            {
                **key,
                "pack_json": _j(pack["pack_json"]),
                "valid_dot_keys": _j(pack["valid_dot_keys"]),
                "injection_suspect": bool(pack["injection_suspect"]),
                "injected_exemplar_ids": _j(pack["injected_exemplar_ids"]),
            },
        )

    assessment = outcome_to_assessment_fields(outcome)
    if assessment is None:
        session.execute(_SQL_DELETE_ASSESSMENT, key)
    else:
        params = {k: _strip_nul(v) for k, v in assessment.items()}
        params["cited_evidence_keys"] = json.dumps(params["cited_evidence_keys"])
        session.execute(_SQL_UPSERT_ASSESSMENT, {**key, **params})

    session.execute(
        _SQL_SET_STATUS,
        {**key, "status": outcome.next_status, "retry_count": outcome.call.retry_count},
    )
    return outcome.next_status