from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel, Field


class AgreementMatrix(BaseModel):
    agreed_true_positive: int = 0
    agreed_false_positive: int = 0
    analyst_overrode_to_tp: int = 0  # Threat Rescue (AI said FP -> Human said TP)
    analyst_overrode_to_fp: int = 0  # Benign Filter (AI said TP -> Human said FP)


class OverrideTrendPoint(BaseModel):
    date: str
    override_rate: float
    total_decisions: int
    active_exemplars: int


class GuardrailBreakdown(BaseModel):
    safety_floor_interventions: int = 0
    abstention_fallbacks: int = 0
    prompt_injection_flags: int = 0


class AnalyticsSummaryDTO(BaseModel):
    total_closed_decisions: int
    ai_agreement_rate: float
    cohens_kappa: float
    human_override_rate: float
    escalation_count: int
    manual_fallback_count: int
    guardrail_interventions: int
    mean_triage_latency_seconds: float
    agreement_matrix: AgreementMatrix
    override_trend: List[OverrideTrendPoint] = Field(default_factory=list)
    override_root_causes: Dict[str, int] = Field(default_factory=dict)
    guardrail_breakdown: GuardrailBreakdown

