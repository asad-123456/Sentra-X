"""Deterministic guardrails: baseline severity, abstention, safety floors (FR-3).

Order of evaluation: baseline mapping, then abstention, then safety floors.
No LLM, database or network access in this module.
"""
from dataclasses import dataclass
from typing import Iterable

from app.services.triage_schema import LLMTriageOutput, Severity, Verdict

# Config constants (the SRS says these are env/config values, not DB rows).
# In Part 6 these can be read from the settings object instead.
MIN_CONFIDENCE = 0.60
CRITICAL_FLOOR_LEVEL = 12
HIGH_FLOOR_LEVEL = 10


def baseline_severity(rule_level: int) -> Severity:
    """Map a Wazuh rule level (0-15) to a baseline severity."""
    if not 0 <= rule_level <= 15:
        raise ValueError(f"Wazuh rule level must be 0-15, got {rule_level}")
    if rule_level >= 12:
        return "CRITICAL"
    if rule_level >= 8:
        return "HIGH"
    if rule_level >= 4:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class GuardrailResult:
    baseline_severity: Severity
    raw_verdict: Verdict
    raw_severity: Severity
    effective_verdict: Verdict
    effective_severity: Severity
    abstention_triggered: bool
    safety_floor_triggered: bool
    guardrail_audit_note: str


def apply_guardrails(
    rule_level: int,
    llm: LLMTriageOutput,
    valid_dot_keys: Iterable[str],
    injection_suspect: bool = False,
    min_confidence: float = MIN_CONFIDENCE,
) -> GuardrailResult:
    """Apply FR-3 to one LLM output. The original rule_level is never changed."""
    baseline = baseline_severity(rule_level)
    valid = set(valid_dot_keys)

    effective_verdict: Verdict = llm.verdict
    effective_severity: Severity = llm.recommended_severity
    notes: list[str] = []
    abstained = False
    floored = False

    proposes_dismissal = (
        llm.verdict == "FALSE_POSITIVE" or llm.recommended_severity == "LOW"
    )

    # --- Abstention ---------------------------------------------------------
    reasons: list[str] = []
    if llm.confidence_score < min_confidence:
        reasons.append(
            f"confidence {llm.confidence_score:.2f} is below {min_confidence:.2f}"
        )
    if not llm.cited_evidence_keys:
        reasons.append("no evidence keys were cited")
    else:
        bad = [k for k in llm.cited_evidence_keys if k not in valid]
        if bad:
            reasons.append("cited keys not in the evidence pack: " + ", ".join(bad))
    if llm.verdict == "FALSE_POSITIVE" and llm.recommended_severity in ("HIGH", "CRITICAL"):
        reasons.append("contradiction: FALSE_POSITIVE with HIGH/CRITICAL severity")
    if injection_suspect and proposes_dismissal:
        reasons.append(
            "possible prompt injection and the model proposed FALSE_POSITIVE or LOW"
        )

    if reasons:
        abstained = True
        effective_verdict = "NEEDS_ANALYST_REVIEW"
        notes.append("Abstention: " + "; ".join(reasons))

    # --- Critical Safety Floor (level >= 12) --------------------------------
    if rule_level >= CRITICAL_FLOOR_LEVEL and (
        llm.verdict == "FALSE_POSITIVE" or llm.recommended_severity in ("LOW", "MEDIUM")
    ):
        floored = True
        effective_severity = "CRITICAL"
        effective_verdict = "NEEDS_ANALYST_REVIEW"
        notes.append(
            f"Critical Safety Floor: Wazuh level {rule_level} but the model proposed "
            f"{llm.verdict}/{llm.recommended_severity}. Downgrade rejected, "
            "severity forced to CRITICAL."
        )

    # --- High Safety Floor (level 10-11) ------------------------------------
    elif HIGH_FLOOR_LEVEL <= rule_level < CRITICAL_FLOOR_LEVEL and proposes_dismissal:
        floored = True
        effective_severity = "HIGH"
        effective_verdict = "NEEDS_ANALYST_REVIEW"
        notes.append(
            f"High-Severity Safety Floor: Wazuh level {rule_level} but the model "
            f"proposed {llm.verdict}/{llm.recommended_severity}. Downgrade rejected, "
            "severity forced to HIGH."
        )

    return GuardrailResult(
        baseline_severity=baseline,
        raw_verdict=llm.verdict,
        raw_severity=llm.recommended_severity,
        effective_verdict=effective_verdict,
        effective_severity=effective_severity,
        abstention_triggered=abstained,
        safety_floor_triggered=floored,
        guardrail_audit_note=" | ".join(notes),
    )