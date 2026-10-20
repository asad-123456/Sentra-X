"""Shared schema for the LLM's triage output (FR-2 required output schema)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["TRUE_POSITIVE", "FALSE_POSITIVE", "NEEDS_ANALYST_REVIEW"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class LLMTriageOutput(BaseModel):
    """What the LLM must return. Anything that fails validation counts as a
    schema failure and triggers a retry (Part 5)."""

    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    recommended_severity: Severity
    confidence_score: float = Field(ge=0.0, le=1.0)
    cited_evidence_keys: list[str]
    explanation: str = Field(max_length=500)