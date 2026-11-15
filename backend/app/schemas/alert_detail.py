from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from .common import AlertStatus, AssetCriticality, DecisionAction, Severity, Verdict


class EvidencePackDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_id: UUID
    raw_wazuh_log: Dict[str, Any]
    mitre_tactics: List[str]
    mitre_techniques: List[str]
    asset_criticality: AssetCriticality
    temporal_context: List[Dict[str, Any]]
    valid_dot_keys: List[str]
    injection_suspect: bool
    injected_exemplar_ids: List[Union[int, str]]
    created_at: str
    updated_at: str


class AIAssessmentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_id: UUID
    raw_verdict: Verdict
    raw_severity: Severity
    effective_verdict: Verdict
    effective_severity: Severity
    confidence_score: float
    cited_evidence_keys: List[str]
    explanation: str
    safety_floor_triggered: bool
    abstention_triggered: bool
    guardrail_audit_note: Optional[str] = None
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    latency_ms: Optional[int] = None
    retry_count: int = 0
    created_at: str
    updated_at: str


class DecisionAuditDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_id: UUID
    user_id: UUID
    username: str
    user_role: str
    action_taken: DecisionAction
    previous_verdict: Optional[Verdict] = None
    previous_severity: Optional[Severity] = None
    final_verdict: Optional[Verdict] = None
    final_severity: Optional[Severity] = None
    rationale: str
    exemplar_created: bool
    created_at: str


class ExemplarItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Union[int, str]
    rule_id: str
    process_signature: str
    asset_criticality: AssetCriticality
    calibrated_verdict: Verdict
    calibrated_severity: Severity
    rationale: str
    is_active: bool
    match_hit_count: int
    created_by: Optional[str] = None
    created_at: str


class AssetRegistryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    hostname: str
    ip_address: str
    criticality_tier: AssetCriticality
    description: Optional[str] = None
    created_at: str
    updated_at: str


class AlertRecordDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wazuh_alert_id: str
    rule_id: str
    rule_level: int
    rule_description: str
    mitre_tactics: List[str]
    mitre_techniques: List[str]
    agent_id: str
    src_ip: Optional[str] = None
    process_signature: Optional[str] = None
    status: AlertStatus
    ingested_at: str
    updated_at: str


class AlertDetailDTO(BaseModel):
    alert: AlertRecordDTO
    asset: AssetRegistryItem
    evidence_pack: Optional[EvidencePackDTO] = None
    ai_assessment: Optional[AIAssessmentDTO] = None
    assessment: Optional[AIAssessmentDTO] = None
    audit_trail: List[DecisionAuditDTO] = Field(default_factory=list)
    decision_audit_trail: List[DecisionAuditDTO] = Field(default_factory=list)
    relevant_exemplars: List[ExemplarItem] = Field(default_factory=list)
    injected_exemplars: List[ExemplarItem] = Field(default_factory=list)
    correlated_alerts: List[Dict[str, Any]] = Field(default_factory=list)

