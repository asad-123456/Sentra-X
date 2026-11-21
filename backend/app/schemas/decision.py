from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, StrictBool, field_validator, model_validator

from .common import DecisionAction, Severity, Verdict


class DecisionRequestDTO(BaseModel):
    action: DecisionAction
    final_verdict: Optional[Verdict] = None
    final_severity: Optional[Severity] = None
    rationale: str = ""
    save_as_exemplar: StrictBool = False
    create_exemplar: StrictBool = False

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: Any) -> Any:
        if v == "MANUAL_TRIAGE_CLOSE":
            return DecisionAction.MANUAL_TRIAGE_CLOSURE
        return v

    @field_validator("rationale", mode="before")
    @classmethod
    def trim_rationale(cls, value: Any) -> Any:
        if value is None:
            return ""
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_disposition(self) -> DecisionRequestDTO:
        if self.final_verdict == Verdict.NEEDS_ANALYST_REVIEW:
            raise ValueError("Final verdict must be TRUE_POSITIVE or FALSE_POSITIVE.")
        if self.action in (
            DecisionAction.OVERRIDE,
            DecisionAction.MANUAL_TRIAGE_CLOSURE,
            DecisionAction.RESOLVE_ESCALATION,
        ):
            if len(self.rationale) < 10:
                raise ValueError("Enter a rationale of at least 10 characters.")
            if self.final_verdict is None or self.final_severity is None:
                raise ValueError("Select a final verdict and severity.")
        return self


class DecisionResponseDTO(BaseModel):
    success: bool
    message: str
    alert_id: UUID
    action_taken: DecisionAction
    audit_id: UUID
    exemplar_created: bool

