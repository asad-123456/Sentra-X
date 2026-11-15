from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from .common import AlertStatus, AssetCriticality, Severity, Verdict


class AlertQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Union[UUID, str]
    wazuh_alert_id: str
    rule_id: str
    rule_level: int
    rule_description: str
    agent_id: str
    agent_name: Optional[str] = None
    hostname: str
    ip_address: str
    asset_criticality: AssetCriticality
    status: AlertStatus
    ingested_at: str
    effective_verdict: Optional[Verdict] = None
    effective_severity: Optional[Severity] = None
    confidence_score: Optional[float] = None
    explanation_snippet: Optional[str] = None
    truncated_explanation: Optional[str] = None
    safety_floor_triggered: bool = False
    abstention_triggered: bool = False
    injection_suspect: bool = False


class QueueStatsDTO(BaseModel):
    total_awaiting: int
    total_escalated: int
    total_closed: int
    critical_safety_floor: int
    abstention_warnings: int
    mean_latency_seconds: float


class PaginatedQueueResponse(BaseModel):
    items: List[AlertQueueItem]
    total: int
    page: int
    pageSize: int
    totalPages: int
    page_size: Optional[int] = None
    stats: Optional[QueueStatsDTO] = None

