from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator

from .common import DecisionAction, Severity, Verdict


class DecisionRequestDTO(BaseModel):
    alert_id: UUID
    action: DecisionAction
    final_verdict: Optional[Verdict] = None
    final_severity: Optional[Severity] = None
    rationale: str = Field(default="")
    user_id: UUID

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: Any) -> Any:
        if v == "MANUAL_TRIAGE_CLOSE":
            return DecisionAction.MANUAL_TRIAGE_CLOSURE
        return v

    @model_validator(mode="after")
    def validate_override_rationale(self) -> DecisionRequestDTO:
        clean_rationale = (self.rationale or "").strip()
        if self.action in (
            DecisionAction.OVERRIDE,
            DecisionAction.MANUAL_TRIAGE_CLOSURE,
            DecisionAction.RESOLVE_ESCALATION,
        ):
            if len(clean_rationale) < 10:
                raise ValueError(
                    f"Action '{self.action.value}' requires a mandatory justification rationale of at least 10 characters."
                )
        if self.action == DecisionAction.OVERRIDE:
            if not self.final_verdict:
                raise ValueError("Override action requires a final_verdict.")
            if not self.final_severity:
                raise ValueError("Override action requires a final_severity.")
        return self


class DecisionResponseDTO(BaseModel):
    success: bool
    message: str
    alert_id: UUID
    action_taken: DecisionAction
    audit_id: UUID
    exemplar_created: bool

