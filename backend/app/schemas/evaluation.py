from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class BenchmarkPayload(BaseModel):
    id: str
    category: str
    target_field: str
    payload: str
    injection_detected: bool
    baseline_verdict: str
    baseline_bypassed: bool
    sentrax_verdict: str
    sentrax_bypassed: bool
    defense_mechanism: str


class BenchmarkComparativeScorecard(BaseModel):
    metric_name: str
    baseline_value: str
    sentrax_value: str
    research_delta: str
    is_target_met: bool


class EvaluationReport(BaseModel):
    timestamp: str
    dataset_name: str
    total_payloads: int
    baseline_bypass_rate: float
    sentrax_bypass_rate: float
    nfr3_target_achieved: bool
    comparative_metrics: List[BenchmarkComparativeScorecard]
    adversarial_suite: List[BenchmarkPayload]

