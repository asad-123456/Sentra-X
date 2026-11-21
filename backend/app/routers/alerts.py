from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..database import get_db
from ..models.alert import Alert
from ..models.asset import Asset
from ..models.ai_assessment import AIAssessment
from ..models.evidence_pack import EvidencePack
from ..models.audit import AnalystDecisionAudit
from ..models.exemplar import FeedbackExemplar
from ..models.user import User
from ..schemas.common import Severity, Verdict
from ..schemas.decision import DecisionRequestDTO
from ..schemas.queue import PaginatedQueueResponse
from ..utils import parse_uuid
from ..worker.jobs import enqueue_triage

router = APIRouter(prefix="/alerts", tags=["Alerts & Triage Queue"])

DECISION_TRANSITIONS = {
    "APPROVE": ({"AWAITING_ANALYST"}, "CLOSED"),
    "OVERRIDE": ({"AWAITING_ANALYST"}, "CLOSED"),
    "ESCALATE": ({"PENDING_REVIEW", "AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"}, "ESCALATED"),
    "RETRY_AI": ({"AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"}, "PENDING_REVIEW"),
    "MANUAL_TRIAGE_CLOSURE": ({"PENDING_REVIEW", "NEEDS_MANUAL_TRIAGE"}, "CLOSED"),
    "RESOLVE_ESCALATION": ({"ESCALATED"}, "CLOSED"),
}
VALID_ASSESSMENT_VERDICTS = set(Verdict)
VALID_SEVERITIES = set(Severity)
ESCALATION_ROLES = {"TeamLead", "Admin"}


def _can_approve(assessment: AIAssessment | None) -> bool:
    return (
        assessment is not None
        and assessment.effective_verdict in VALID_ASSESSMENT_VERDICTS
        and assessment.effective_severity in VALID_SEVERITIES
    )


def _available_actions(alert: Alert, user: User | None, assessment: AIAssessment | None) -> list[str]:
    return [
        action for action, (states, _) in DECISION_TRANSITIONS.items()
        if alert.status in states
        and (action != "APPROVE" or _can_approve(assessment))
        and (action != "RESOLVE_ESCALATION" or (user is not None and user.role in ESCALATION_ROLES))
    ]


@router.get("", response_model=PaginatedQueueResponse)
def get_alerts(
    tab: str = Query("awaiting", pattern="^(awaiting|escalated|closed)$"),
    subStatus: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    guardrail: Optional[str] = Query(None),
    assetTier: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(require_roles("Analyst", "TeamLead", "Admin", demo_open=True)),
):
    query = (
        db.query(Alert, Asset, AIAssessment, EvidencePack)
        .join(Asset, Alert.agent_id == Asset.agent_id)
        .outerjoin(AIAssessment, Alert.id == AIAssessment.alert_id)
        .outerjoin(EvidencePack, Alert.id == EvidencePack.alert_id)
    )

    # 1. Filter by Tab & SubStatus
    effective_sub = subStatus or status
    if effective_sub:
        if effective_sub in ("AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE", "PENDING_REVIEW"):
            query = query.filter(Alert.status == effective_sub)
        elif effective_sub == "ESCALATED":
            query = query.filter(Alert.status == "ESCALATED")
        elif effective_sub == "CLOSED":
            query = query.filter(Alert.status == "CLOSED")
    elif tab == "awaiting":
        query = query.filter(Alert.status.in_(["AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE", "PENDING_REVIEW"]))
    elif tab == "escalated":
        query = query.filter(Alert.status == "ESCALATED")
    elif tab == "closed":
        query = query.filter(Alert.status == "CLOSED")

    # 2. Severity Filter
    if severity and severity != "ALL":
        query = query.filter(
            (AIAssessment.effective_severity == severity)
            | (AIAssessment.raw_severity == severity)
        )

    # 3. Guardrail Filter
    if guardrail and guardrail != "ALL":
        if guardrail == "SAFETY_FLOOR":
            query = query.filter(AIAssessment.safety_floor_triggered.is_(True))
        elif guardrail == "ABSTENTION":
            query = query.filter(AIAssessment.abstention_triggered.is_(True))
        elif guardrail == "PROMPT_INJECTION":
            query = query.filter(EvidencePack.injection_suspect.is_(True))

    # 4. Asset Tier Filter
    if assetTier and assetTier != "ALL":
        query = query.filter(Asset.criticality_tier == assetTier)

    # 5. Rule ID Filter
    if rule_id:
        query = query.filter(Alert.rule_id == rule_id)

    # 6. Search Filter
    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            (func.lower(Alert.rule_description).like(search_term))
            | (func.lower(Alert.rule_id).like(search_term))
            | (func.lower(Alert.wazuh_alert_id).like(search_term))
            | (func.lower(Asset.hostname).like(search_term))
            | (func.lower(Asset.ip_address).like(search_term))
            | (func.lower(Alert.process_signature).like(search_term))
        )

    # 7. Sorting: Queue Index Order — effective_severity DESC then ingested_at ASC (SDD §3.6)
    from sqlalchemy import case
    severity_order = case(
        (AIAssessment.effective_severity == "CRITICAL", 4),
        (AIAssessment.effective_severity == "HIGH", 3),
        (AIAssessment.effective_severity == "MEDIUM", 2),
        (AIAssessment.effective_severity == "LOW", 1),
        else_=0,
    )
    if tab == "closed":
        query = query.order_by(desc(Alert.updated_at))
    else:
        query = query.order_by(desc(severity_order), Alert.ingested_at)

    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)

    offset = (page - 1) * page_size
    records = query.offset(offset).limit(page_size).all()

    items = []
    for alert, asset, ai, ep in records:
        items.append(
            {
                "id": str(alert.id),
                "wazuh_alert_id": alert.wazuh_alert_id,
                "rule_id": alert.rule_id,
                "rule_level": alert.rule_level,
                "rule_description": alert.rule_description,
                "agent_id": alert.agent_id,
                "agent_name": asset.hostname,
                "hostname": asset.hostname,
                "ip_address": asset.ip_address,
                "mitre_tactics": alert.mitre_tactics,
                "mitre_techniques": alert.mitre_techniques,
                "asset_criticality": asset.criticality_tier,
                "status": alert.status,
                "available_actions": _available_actions(alert, user, ai),
                "ingested_at": str(alert.ingested_at),
                "effective_verdict": ai.effective_verdict if ai else None,
                "effective_severity": ai.effective_severity if ai else None,
                "confidence_score": ai.confidence_score if ai else None,
                "explanation_snippet": (ai.explanation[:100] + "...") if (ai and ai.explanation) else alert.rule_description,
                "safety_floor_triggered": ai.safety_floor_triggered if ai else False,
                "abstention_triggered": ai.abstention_triggered if ai else False,
                "injection_suspect": ep.injection_suspect if ep else False,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


@router.get("/counts", response_model=Dict[str, Any])
def get_alert_counts(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Analyst", "TeamLead", "Admin", demo_open=True)),
):
    awaiting = db.query(Alert).filter(Alert.status.in_(["PENDING_REVIEW", "AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"])).count()
    awaiting_analyst_count = db.query(Alert).filter(Alert.status == "AWAITING_ANALYST").count()
    needs_manual_triage_count = db.query(Alert).filter(Alert.status == "NEEDS_MANUAL_TRIAGE").count()
    escalated = db.query(Alert).filter(Alert.status == "ESCALATED").count()
    closed = db.query(Alert).filter(Alert.status == "CLOSED").count()

    critical_safety_floor = (
        db.query(AIAssessment)
        .join(Alert, AIAssessment.alert_id == Alert.id)
        .filter(
            Alert.status.in_(["AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"]),
            AIAssessment.safety_floor_triggered.is_(True),
            AIAssessment.effective_severity == "CRITICAL",
        )
        .count()
    )

    abstention_warnings = (
        db.query(AIAssessment)
        .join(Alert, AIAssessment.alert_id == Alert.id)
        .filter(
            Alert.status.in_(["AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"]),
            AIAssessment.abstention_triggered.is_(True),
        )
        .count()
    )

    avg_latency = (
        db.query(func.avg(func.coalesce(AIAssessment.inference_latency_ms, AIAssessment.latency_ms)))
        .scalar()
    )
    mean_latency_seconds = round(float(avg_latency) / 1000.0, 2) if avg_latency is not None else None

    return {
        "awaiting": awaiting,
        "awaitingAnalystCount": awaiting_analyst_count,
        "needsManualTriageCount": needs_manual_triage_count,
        "escalated": escalated,
        "closed": closed,
        "criticalSafetyFloor": critical_safety_floor,
        "abstentionWarnings": abstention_warnings,
        "meanLatencySeconds": mean_latency_seconds,
    }


@router.get("/{alert_id}", response_model=Dict[str, Any])
def get_alert_detail(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(require_roles("Analyst", "TeamLead", "Admin", demo_open=True)),
):
    target_uuid = parse_uuid(alert_id)
    alert = db.query(Alert).filter(Alert.id == target_uuid).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")

    asset = db.query(Asset).filter(Asset.agent_id == alert.agent_id).first()
    evidence_pack = db.query(EvidencePack).filter(EvidencePack.alert_id == alert.id).first()
    ai_assessment = db.query(AIAssessment).filter(AIAssessment.alert_id == alert.id).first()

    # Fetch audit trail
    audits = (
        db.query(AnalystDecisionAudit, User)
        .outerjoin(User, AnalystDecisionAudit.user_id == User.id)
        .filter(AnalystDecisionAudit.alert_id == alert.id)
        .order_by(desc(AnalystDecisionAudit.created_at))
        .all()
    )

    audit_trail = []
    for audit, user in audits:
        audit_trail.append(
            {
                "id": str(audit.id),
                "alert_id": str(audit.alert_id),
                "user_id": str(audit.user_id),
                "username": user.username if user else "SOC Analyst",
                "user_role": user.role if user else "Analyst",
                "action_taken": audit.action_taken,
                "previous_verdict": audit.previous_verdict,
                "previous_severity": audit.previous_severity,
                "final_verdict": audit.final_verdict,
                "final_severity": audit.final_severity,
                "rationale": audit.rationale,
                "exemplar_created": audit.exemplar_created,
                "created_at": str(audit.created_at),
            }
        )

    saved_ids = evidence_pack.injected_exemplar_ids if evidence_pack else []
    exemplar_ids = [
        int(value) for value in saved_ids
        if type(value) in (str, int)
        and str(value).isascii() and str(value).isdigit()
        and len(str(value)) <= 10 and 0 < int(value) <= 2_147_483_647
    ] if isinstance(saved_ids, list) else []
    exemplar_items = []
    if exemplar_ids:
        exemplars = db.query(FeedbackExemplar).filter(FeedbackExemplar.id.in_(exemplar_ids)).all()
        by_id = {ex.id: ex for ex in exemplars}
        for exemplar_id in dict.fromkeys(exemplar_ids):
            ex = by_id.get(exemplar_id)
            if ex is None:
                continue
            exemplar_items.append(
                {
                    "id": ex.id,
                    "source_alert_id": str(ex.source_alert_id) if ex.source_alert_id else None,
                    "rule_id": ex.rule_id,
                    "process_signature": ex.process_signature,
                    "asset_criticality": ex.asset_criticality,
                    "calibrated_verdict": ex.calibrated_verdict,
                    "calibrated_severity": ex.calibrated_severity,
                    "rationale": ex.rationale,
                    "is_active": ex.is_active,
                    "match_hit_count": ex.match_hit_count,
                    "created_at": str(ex.created_at),
                }
            )

    # Prepare EvidencePack payload
    ep_data = None
    if evidence_pack:
        pack_json = evidence_pack.pack_json or {}
        ep_data = {
            "id": str(evidence_pack.id),
            "alert_id": str(evidence_pack.alert_id),
            "raw_wazuh_log": pack_json.get("telemetry_payload", {}),
            "telemetry_payload": pack_json.get("telemetry_payload", {}),
            "alert_metadata": pack_json.get("alert_metadata", {}),
            "asset_context": pack_json.get("asset_context"),
            "pack_json": pack_json,
            "mitre_tactics": alert.mitre_tactics or [],
            "mitre_techniques": alert.mitre_techniques or [],
            "asset_criticality": asset.criticality_tier if asset else "MEDIUM",
            "temporal_context": pack_json.get("temporal_context", []),
            "valid_dot_keys": evidence_pack.valid_dot_keys or [],
            "injection_suspect": evidence_pack.injection_suspect,
            "injected_exemplar_ids": exemplar_ids,
            "created_at": str(evidence_pack.created_at),
            "updated_at": str(evidence_pack.updated_at),
        }

    # Prepare AIAssessment payload
    ai_data = None
    if ai_assessment:
        ai_data = {
            "id": str(ai_assessment.id),
            "alert_id": str(ai_assessment.alert_id),
            "raw_verdict": ai_assessment.raw_verdict,
            "raw_severity": ai_assessment.raw_severity,
            "effective_verdict": ai_assessment.effective_verdict,
            "effective_severity": ai_assessment.effective_severity,
            "confidence_score": ai_assessment.confidence_score,
            "cited_evidence_keys": ai_assessment.cited_evidence_keys or [],
            "explanation": ai_assessment.explanation,
            "safety_floor_triggered": ai_assessment.safety_floor_triggered,
            "abstention_triggered": ai_assessment.abstention_triggered,
            "guardrail_audit_note": ai_assessment.guardrail_audit_note,
            "llm_provider": ai_assessment.llm_provider,
            "model_name": ai_assessment.model_name,
            "latency_ms": ai_assessment.latency_ms,
            "inference_latency_ms": ai_assessment.inference_latency_ms or ai_assessment.latency_ms,
            "retry_count": ai_assessment.retry_count,
            "created_at": str(ai_assessment.created_at),
            "updated_at": str(ai_assessment.updated_at),
        }

    return {
        "alert": {
            "id": str(alert.id),
            "wazuh_alert_id": alert.wazuh_alert_id,
            "rule_id": alert.rule_id,
            "rule_level": alert.rule_level,
            "rule_description": alert.rule_description,
            "agent_name": alert.agent_name or (asset.hostname if asset else "Unknown"),
            "mitre_tactics": alert.mitre_tactics,
            "mitre_techniques": alert.mitre_techniques,
            "agent_id": alert.agent_id,
            "src_ip": alert.src_ip,
            "process_signature": alert.process_signature,
            "status": alert.status,
            "retry_count": alert.retry_count,
            "alert_timestamp": str(alert.alert_timestamp),
            "ingested_at": str(alert.ingested_at),
            "updated_at": str(alert.updated_at),
        },
        "asset": {
            "agent_id": asset.agent_id if asset else alert.agent_id,
            "hostname": asset.hostname if asset else "Unknown",
            "ip_address": asset.ip_address if asset else "Unknown",
            "criticality_tier": asset.criticality_tier if asset else "MEDIUM",
            "description": asset.description if asset else "",
            "created_at": str(asset.created_at) if asset else str(alert.ingested_at),
            "updated_at": str(asset.updated_at) if asset else str(alert.updated_at),
        },
        "available_actions": _available_actions(alert, current_user, ai_assessment),
        "evidence_pack": ep_data,
        "ai_assessment": ai_data,
        "audit_trail": audit_trail,
        "relevant_exemplars": exemplar_items,
        "injected_exemplars": exemplar_items,
        "correlated_alerts": ep_data.get("temporal_context", []) if ep_data else [],
    }


@router.post("/{alert_id}/decision", response_model=Dict[str, Any])
def submit_alert_decision(
    alert_id: str,
    payload: DecisionRequestDTO,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    action = payload.action.value
    if action == "RESOLVE_ESCALATION" and user.role not in ESCALATION_ROLES:
        raise HTTPException(status_code=403, detail="Only TeamLead or Admin can resolve escalated alerts.")

    target_uuid = parse_uuid(alert_id)
    alert = db.query(Alert).filter(Alert.id == target_uuid).populate_existing().with_for_update().first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")

    allowed_states, next_state = DECISION_TRANSITIONS[action]
    if alert.status not in allowed_states:
        raise HTTPException(
            status_code=422,
            detail=f"Action {action} is unavailable while the alert is {alert.status}. Refresh to review its current state.",
        )

    ai = db.query(AIAssessment).filter(AIAssessment.alert_id == alert.id).first()
    prev_verdict = ai.effective_verdict if ai else None
    prev_severity = ai.effective_severity if ai else None
    rationale = payload.rationale
    final_verdict = payload.final_verdict.value if payload.final_verdict else None
    final_severity = payload.final_severity.value if payload.final_severity else None

    if action == "APPROVE":
        if ai is None or not _can_approve(ai):
            raise HTTPException(status_code=422, detail="Approval requires a saved AI assessment with a valid verdict and severity.")
        if ai.abstention_triggered or prev_verdict == Verdict.NEEDS_ANALYST_REVIEW:
            if final_verdict is None:
                raise HTTPException(status_code=422, detail="Select a final verdict for the assessment that needs analyst review.")
        else:
            if final_verdict is not None and final_verdict != prev_verdict:
                raise HTTPException(status_code=409, detail="The verdict differs from the saved assessment. Refresh the alert or use Override.")
            final_verdict = prev_verdict
        if final_severity is not None and final_severity != prev_severity:
            raise HTTPException(status_code=409, detail="The severity differs from the saved assessment. Refresh the alert or use Override.")
        final_severity = prev_severity

    alert.status = next_state
    alert.updated_at = datetime.now(timezone.utc)
    if action == "RETRY_AI":
        alert.triage_generation += 1
        alert.retry_count = 0
        if ai:
            ai.retry_count = 0

    exemplar_created = (
        next_state == "CLOSED"
        and (action == "OVERRIDE" or payload.save_as_exemplar or payload.create_exemplar)
        and len(rationale) >= 10
    )
    if exemplar_created:
        asset = db.query(Asset).filter(Asset.agent_id == alert.agent_id).first()
        exemplar = FeedbackExemplar(
            source_alert_id=alert.id,
            rule_id=alert.rule_id,
            process_signature=alert.process_signature,
            asset_criticality=asset.criticality_tier if asset else "MEDIUM",
            calibrated_verdict=final_verdict,
            calibrated_severity=final_severity,
            rationale=rationale,
            is_active=True,
            match_hit_count=0,
            user_id=user.id,
            created_by=user.id,
        )
        db.add(exemplar)

    # Record immutable audit entry (SRS §7.2.1: NULL for ESCALATE and RETRY_AI)
    audit_id = uuid.uuid4()
    audit_record = AnalystDecisionAudit(
        id=audit_id,
        alert_id=alert.id,
        user_id=user.id,
        action_taken=action,
        previous_verdict=prev_verdict,
        previous_severity=prev_severity,
        final_verdict=final_verdict if next_state == "CLOSED" else None,
        final_severity=final_severity if next_state == "CLOSED" else None,
        rationale=rationale,
        exemplar_created=exemplar_created,
    )
    db.add(audit_record)

    db.commit()
    if action == "RETRY_AI":
        enqueue_triage(target_uuid)
    db.refresh(audit_record)  # BUG-N3 fix: populate server-generated created_at before serializing

    return {
        "id": str(audit_id),
        "alert_id": str(target_uuid),
        "user_id": str(user.id),
        "username": user.username,
        "user_role": user.role,
        "action_taken": action,
        "previous_verdict": prev_verdict,
        "previous_severity": prev_severity,
        "final_verdict": audit_record.final_verdict,
        "final_severity": audit_record.final_severity,
        "rationale": rationale,
        "exemplar_created": exemplar_created,
        "created_at": str(audit_record.created_at),
    }
