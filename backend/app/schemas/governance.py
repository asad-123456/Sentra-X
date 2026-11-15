from __future__ import annotations

from typing import Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field

from .common import AssetCriticality, Severity, Verdict


class ExemplarCreateRequest(BaseModel):
    rule_id: str
    process_signature: str
    asset_criticality: AssetCriticality
    calibrated_verdict: Verdict
    calibrated_severity: Severity
    rationale: str = Field(..., min_length=10)
    source_alert_id: Optional[UUID] = None


class AssetRegisterRequest(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=64)
    hostname: str = Field(..., min_length=1, max_length=255)
    ip_address: str = Field(..., min_length=1, max_length=45)
    criticality_tier: AssetCriticality = AssetCriticality.MEDIUM
    description: Optional[str] = None


class AssetUpdateCriticalityRequest(BaseModel):
    criticality_tier: AssetCriticality

