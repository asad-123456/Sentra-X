"""Triage pipeline: assemble -> LLM -> guardrails, with no database access (FR-2, FR-3).

Three phases keep database connections out of the slow LLM call:
    1. load     (reads, Part 6A-2)   -> TriageInputs
    2. run      (this module, no DB) -> TriageOutcome
    3. persist  (writes, Part 6A-2)  -> uses outcome_to_pack_fields / outcome_to_assessment_fields

run_triage_pipeline never raises. Every failure becomes
next_status = NEEDS_MANUAL_TRIAGE. This module never produces CLOSED or ESCALATED.
"""
import logging
from dataclasses import dataclass
from typing import Any, Sequence

from app.services.evidence_assembler import (
    AlertRecord,
    CorrelatedAlert,
    EvidencePack,
    assemble_evidence_pack,
)
from app.services.llm_adapter import (
    InjectedExemplar,
    LLMAdapter,
    TriageCallResult,
    triage_alert,
)
from app.services.rules_engine import (
    MIN_CONFIDENCE,
    GuardrailResult,
    apply_guardrails,
    baseline_severity,
)

logger = logging.getLogger(__name__)

STATUS_AWAITING_ANALYST = "AWAITING_ANALYST"
STATUS_NEEDS_MANUAL_TRIAGE = "NEEDS_MANUAL_TRIAGE"


@dataclass(frozen=True)
class TriageInputs:
    """Everything the run phase needs, already loaded from the database."""

    alert: AlertRecord
    criticality_tier: str | None = None
    candidates: Sequence[CorrelatedAlert] = ()
    exemplars: Sequence[InjectedExemplar] = ()


@dataclass(frozen=True)
class TriageOutcome:
    next_status: str
    provider_name: str | None
    evidence_pack: EvidencePack | None   # None only if pack assembly itself crashed
    call: TriageCallResult
    guardrails: GuardrailResult | None   # None if there is no assessment to store
    error: str | None = None

    @property
    def has_assessment(self) -> bool:
        return self.call.output is not None and self.guardrails is not None


def _failed_call(adapter: LLMAdapter, error: str) -> TriageCallResult:
    return TriageCallResult(
        output=None,
        model_name=getattr(adapter, "model_name", "unknown"),
        inference_latency_ms=0,
        retry_count=0,
        succeeded=False,
        last_error=error,
    )


def run_triage_pipeline(
    inputs: TriageInputs,
    adapter: LLMAdapter,
    *,
    min_confidence: float = MIN_CONFIDENCE,
    **call_options: Any,
) -> TriageOutcome:
    """Assemble the pack, call the LLM, apply FR-3. Extra keyword arguments
    (timeout_s, sleep, clock, ...) are passed to triage_alert."""
    provider = getattr(adapter, "provider_name", None)

    try:
        ep = assemble_evidence_pack(
            inputs.alert,
            inputs.criticality_tier,
            inputs.candidates,
            [e.id for e in inputs.exemplars],  # same order the prompt uses
        )
    except Exception as exc:
        logger.exception("Evidence pack assembly failed")
        error = f"evidence pack assembly failed: {type(exc).__name__}"
        return TriageOutcome(
            STATUS_NEEDS_MANUAL_TRIAGE, provider, None, _failed_call(adapter, error), None, error
        )

    # Fail fast on an invalid rule level, before spending an LLM call.
    try:
        baseline_severity(inputs.alert.rule_level)
    except ValueError as exc:
        error = str(exc)
        return TriageOutcome(
            STATUS_NEEDS_MANUAL_TRIAGE, provider, ep, _failed_call(adapter, error), None, error
        )

    call = triage_alert(ep, adapter, inputs.exemplars, **call_options)
    if not call.succeeded or call.output is None:
        return TriageOutcome(
            STATUS_NEEDS_MANUAL_TRIAGE, provider, ep, call, None, call.last_error
        )

    try:
        guardrails = apply_guardrails(
            inputs.alert.rule_level,
            call.output,
            ep.valid_dot_keys,
            ep.injection_suspect,
            min_confidence,
        )
    except Exception as exc:
        logger.exception("Guardrails failed")
        error = f"guardrails failed: {type(exc).__name__}: {exc}"
        return TriageOutcome(STATUS_NEEDS_MANUAL_TRIAGE, provider, ep, call, None, error)

    return TriageOutcome(STATUS_AWAITING_ANALYST, provider, ep, call, guardrails)


def outcome_to_pack_fields(outcome: TriageOutcome) -> dict | None:
    """Column values for evidence_packs (persist adds id, alert_id, timestamps)."""
    ep = outcome.evidence_pack
    if ep is None:
        return None
    return {
        "pack_json": ep.pack,
        "valid_dot_keys": ep.valid_dot_keys,
        "injection_suspect": ep.injection_suspect,
        "injected_exemplar_ids": ep.injected_exemplar_ids,
    }


def outcome_to_assessment_fields(outcome: TriageOutcome) -> dict | None:
    """Column values for ai_assessments, or None when there is nothing to store
    (adapter failed or guardrails could not run). An empty audit note is stored as NULL."""
    if not outcome.has_assessment:
        return None
    llm = outcome.call.output
    g = outcome.guardrails
    return {
        "raw_verdict": g.raw_verdict,
        "raw_severity": g.raw_severity,
        "effective_verdict": g.effective_verdict,
        "effective_severity": g.effective_severity,
        "confidence_score": llm.confidence_score,
        "cited_evidence_keys": list(llm.cited_evidence_keys),
        "explanation": llm.explanation,
        "safety_floor_triggered": g.safety_floor_triggered,
        "abstention_triggered": g.abstention_triggered,
        "guardrail_audit_note": g.guardrail_audit_note or None,
        "llm_provider": outcome.provider_name,
        "model_name": outcome.call.model_name,
        "inference_latency_ms": outcome.call.inference_latency_ms,
        "retry_count": outcome.call.retry_count,
    }