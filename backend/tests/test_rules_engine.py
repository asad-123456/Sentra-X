import pytest
from pydantic import ValidationError

from app.services.rules_engine import apply_guardrails, baseline_severity
from app.services.triage_schema import LLMTriageOutput

VALID_KEYS = {
    "alert_metadata.rule.id",
    "alert_metadata.rule.level",
    "telemetry_payload.full_log",
}


def make(verdict="TRUE_POSITIVE", severity="HIGH", conf=0.90, keys=None):
    return LLMTriageOutput(
        verdict=verdict,
        recommended_severity=severity,
        confidence_score=conf,
        cited_evidence_keys=["alert_metadata.rule.id"] if keys is None else keys,
        explanation="test",
    )


def run(level, llm, injection=False):
    return apply_guardrails(level, llm, VALID_KEYS, injection_suspect=injection)


# --- Baseline mapping -------------------------------------------------------
@pytest.mark.parametrize(
    "level,expected",
    [(3, "LOW"), (4, "MEDIUM"), (7, "MEDIUM"), (8, "HIGH"), (9, "HIGH"),
     (10, "HIGH"), (11, "HIGH"), (12, "CRITICAL"), (15, "CRITICAL")],
)
def test_baseline_mapping(level, expected):
    assert baseline_severity(level) == expected


@pytest.mark.parametrize("level", [-1, 16])
def test_baseline_rejects_out_of_range(level):
    with pytest.raises(ValueError):
        baseline_severity(level)


# --- SRS boundary checks (AC-7, AC-8) ---------------------------------------
def test_level_12_false_positive_becomes_critical():
    r = run(12, make("FALSE_POSITIVE", "LOW"))
    assert r.effective_severity == "CRITICAL"
    assert r.effective_verdict == "NEEDS_ANALYST_REVIEW"
    assert r.safety_floor_triggered is True
    assert "Critical Safety Floor" in r.guardrail_audit_note


def test_level_10_low_becomes_high():
    r = run(10, make("TRUE_POSITIVE", "LOW"))
    assert r.effective_severity == "HIGH"
    assert r.effective_verdict == "NEEDS_ANALYST_REVIEW"
    assert r.safety_floor_triggered is True
    assert "High-Severity Safety Floor" in r.guardrail_audit_note


def test_level_6_false_positive_low_accepted_unchanged():
    r = run(6, make("FALSE_POSITIVE", "LOW", conf=0.90))
    assert r.effective_verdict == "FALSE_POSITIVE"
    assert r.effective_severity == "LOW"
    assert r.abstention_triggered is False
    assert r.safety_floor_triggered is False
    assert r.guardrail_audit_note == ""


def test_confidence_059_abstains_and_060_does_not():
    low = run(6, make("TRUE_POSITIVE", "MEDIUM", conf=0.59))
    assert low.abstention_triggered is True
    assert low.effective_verdict == "NEEDS_ANALYST_REVIEW"

    ok = run(6, make("TRUE_POSITIVE", "MEDIUM", conf=0.60))
    assert ok.abstention_triggered is False
    assert ok.effective_verdict == "TRUE_POSITIVE"


# --- Abstention conditions --------------------------------------------------
def test_abstains_on_empty_citations():
    r = run(6, make(keys=[]))
    assert r.abstention_triggered is True
    assert "no evidence keys" in r.guardrail_audit_note


def test_abstains_on_unknown_citation_key():
    r = run(6, make(keys=["alert_metadata.rule.id", "made.up.key"]))
    assert r.abstention_triggered is True
    assert "made.up.key" in r.guardrail_audit_note


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL"])
def test_abstains_on_false_positive_with_high_severity(severity):
    r = run(6, make("FALSE_POSITIVE", severity))
    assert r.abstention_triggered is True
    assert r.effective_verdict == "NEEDS_ANALYST_REVIEW"


@pytest.mark.parametrize(
    "verdict,severity", [("FALSE_POSITIVE", "MEDIUM"), ("TRUE_POSITIVE", "LOW")]
)
def test_injection_suspect_blocks_dismissal(verdict, severity):
    r = run(6, make(verdict, severity), injection=True)
    assert r.abstention_triggered is True
    assert r.effective_verdict == "NEEDS_ANALYST_REVIEW"


def test_injection_suspect_with_true_positive_high_does_not_abstain():
    r = run(6, make("TRUE_POSITIVE", "HIGH"), injection=True)
    assert r.abstention_triggered is False
    assert r.effective_verdict == "TRUE_POSITIVE"


# --- Critical floor (level >= 12) -------------------------------------------
@pytest.mark.parametrize("level", [12, 15])
@pytest.mark.parametrize(
    "verdict,severity",
    [("FALSE_POSITIVE", "LOW"), ("TRUE_POSITIVE", "LOW"),
     ("TRUE_POSITIVE", "MEDIUM"), ("FALSE_POSITIVE", "HIGH")],
)
def test_critical_floor_rejects_downgrades(level, verdict, severity):
    r = run(level, make(verdict, severity))
    assert r.safety_floor_triggered is True
    assert r.effective_severity == "CRITICAL"
    assert r.effective_verdict == "NEEDS_ANALYST_REVIEW"


def test_critical_floor_not_triggered_by_true_positive_high():
    # Documents the SRS trigger condition: only FP, LOW or MEDIUM fire the floor.
    r = run(12, make("TRUE_POSITIVE", "HIGH"))
    assert r.safety_floor_triggered is False
    assert r.effective_severity == "HIGH"
    assert r.effective_verdict == "TRUE_POSITIVE"


# --- High floor (level 10-11) -----------------------------------------------
@pytest.mark.parametrize("level", [10, 11])
@pytest.mark.parametrize(
    "verdict,severity", [("FALSE_POSITIVE", "MEDIUM"), ("TRUE_POSITIVE", "LOW")]
)
def test_high_floor_rejects_dismissals(level, verdict, severity):
    r = run(level, make(verdict, severity))
    assert r.safety_floor_triggered is True
    assert r.effective_severity == "HIGH"
    assert r.effective_verdict == "NEEDS_ANALYST_REVIEW"


def test_level_9_has_no_floor():
    r = run(9, make("FALSE_POSITIVE", "LOW", conf=0.90))
    assert r.safety_floor_triggered is False
    assert r.effective_verdict == "FALSE_POSITIVE"
    assert r.effective_severity == "LOW"


# --- Combined behaviour and raw fields --------------------------------------
def test_floor_and_abstention_can_both_fire():
    r = run(12, make("FALSE_POSITIVE", "LOW", conf=0.30))
    assert r.abstention_triggered is True
    assert r.safety_floor_triggered is True
    assert "Abstention" in r.guardrail_audit_note
    assert "Critical Safety Floor" in r.guardrail_audit_note


def test_raw_fields_are_preserved():
    r = run(12, make("FALSE_POSITIVE", "LOW"))
    assert r.raw_verdict == "FALSE_POSITIVE"
    assert r.raw_severity == "LOW"
    assert r.baseline_severity == "CRITICAL"


# --- Schema validation (feeds AC-4 and the retry logic in Part 5) ------------
def test_schema_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        make(conf=1.5)


def test_schema_rejects_long_explanation():
    with pytest.raises(ValidationError):
        LLMTriageOutput(
            verdict="TRUE_POSITIVE", recommended_severity="HIGH",
            confidence_score=0.9, cited_evidence_keys=["a"], explanation="x" * 501,
        )


def test_schema_rejects_unknown_verdict():
    with pytest.raises(ValidationError):
        LLMTriageOutput(
            verdict="BENIGN", recommended_severity="HIGH",
            confidence_score=0.9, cited_evidence_keys=["a"], explanation="x",
        )