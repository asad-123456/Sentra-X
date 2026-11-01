from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from ..auth import security
from ..config import settings
from ..database import get_db
from ..models.alert import Alert
from ..models.asset import Asset
from ..models.ai_assessment import AIAssessment
from ..models.evidence_pack import EvidencePack
from ..models.audit import AnalystDecisionAudit
from ..models.exemplar import FeedbackExemplar
from ..models.user import User
from ..schemas.queue import PaginatedQueueResponse
from ..utils import parse_uuid

router = APIRouter(prefix="/alerts", tags=["Alerts & Triage Queue"])


@router.get("", response_model=PaginatedQueueResponse)
def get_alerts(
    tab: str = Query("awaiting", pattern="^(awaiting|escalated|closed)$"),
    subStatus: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    guardrail: Optional[str] = Query(None),
    assetTier: Optional[str] = Query(None),
    rule_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Alert, Asset, AIAssessment, EvidencePack)
        .join(Asset, Alert.agent_id == Asset.agent_id)
        .outerjoin(AIAssessment, Alert.id == AIAssessment.alert_id)
        .outerjoin(EvidencePack, Alert.id == EvidencePack.alert_id)
    )

    # 1. Filter by Tab & SubStatus
    if tab == "awaiting":
        if subStatus == "AWAITING_ANALYST":
            query = query.filter(Alert.status == "AWAITING_ANALYST")
        elif subStatus == "NEEDS_MANUAL_TRIAGE":
            query = query.filter(Alert.status == "NEEDS_MANUAL_TRIAGE")
        else:
            query = query.filter(Alert.status.in_(["AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"]))
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
                "asset_criticality": asset.criticality_tier,
                "status": alert.status,
                "ingested_at": str(alert.ingested_at),
                "effective_verdict": ai.effective_verdict if ai else None,
                "effective_severity": ai.effective_severity if ai else None,
                "confidence_score": ai.confidence_score if ai else None,
                "explanation_snippet": (ai.explanation[:100] + "...") if (ai and ai.explanation) else alert.rule_description,
                "truncated_explanation": (ai.explanation[:100] + "...") if (ai and ai.explanation) else alert.rule_description,
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
def get_alert_counts(db: Session = Depends(get_db)):
    awaiting = db.query(Alert).filter(Alert.status.in_(["AWAITING_ANALYST", "NEEDS_MANUAL_TRIAGE"])).count()
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
        db.query(func.avg(AIAssessment.latency_ms))
        .filter(AIAssessment.latency_ms.isnot(None))
        .scalar()
    )
    mean_latency_seconds = round(float(avg_latency or 1200) / 1000.0, 1)

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
def get_alert_detail(alert_id: str, db: Session = Depends(get_db)):
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

    # Fetch relevant few-shot calibration exemplars matching rule_id
    exemplars = (
        db.query(FeedbackExemplar)
        .filter(FeedbackExemplar.rule_id == alert.rule_id, FeedbackExemplar.is_active.is_(True))
        .order_by(desc(FeedbackExemplar.created_at))
        .limit(2)
        .all()
    )

    exemplar_items = []
    exemplars_updated = False
    for ex in exemplars:
        ex.match_hit_count = (ex.match_hit_count or 0) + 1
        exemplars_updated = True
        exemplar_items.append(
            {
                "id": ex.id,
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
    if exemplars_updated:
        try:
            db.commit()
        except Exception:
            db.rollback()

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
            "mitre_tactics": alert.mitre_tactics or [],
            "mitre_techniques": alert.mitre_techniques or [],
            "asset_criticality": asset.criticality_tier if asset else "MEDIUM",
            "temporal_context": pack_json.get("temporal_context", []),
            "valid_dot_keys": evidence_pack.valid_dot_keys or [],
            "injection_suspect": evidence_pack.injection_suspect,
            "injected_exemplar_ids": evidence_pack.injected_exemplar_ids or [],
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
        "evidence_pack": ep_data,
        "ai_assessment": ai_data,
        "assessment": ai_data,
        "audit_trail": audit_trail,
        "decision_audit_trail": audit_trail,
        "relevant_exemplars": exemplar_items,
        "injected_exemplars": exemplar_items,
        "correlated_alerts": ep_data.get("temporal_context", []) if ep_data else [],
    }


@router.post("/{alert_id}/decision", response_model=Dict[str, Any])
def submit_alert_decision(
    alert_id: str,
    payload: Dict[str, Any],
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    target_uuid = parse_uuid(alert_id)
    alert = db.query(Alert).filter(Alert.id == target_uuid).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")

    action = payload.get("action")
    if not action:
        raise HTTPException(status_code=400, detail="Action is required.")

    VALID_ACTIONS = {"APPROVE", "OVERRIDE", "ESCALATE", "RETRY_AI", "MANUAL_TRIAGE_CLOSE", "MANUAL_TRIAGE_CLOSURE", "RESOLVE_ESCALATION"}
    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"HTTP 422: Invalid action '{action}'. Must be one of: {sorted(VALID_ACTIONS)}.",
        )

    rationale = (payload.get("rationale") or "").strip()
    final_verdict = payload.get("final_verdict")
    final_severity = payload.get("final_severity")

    # Enforce >= 10 char rationale on actions requiring mandatory justification (FR-6, AC-11)
    if action in ("OVERRIDE", "MANUAL_TRIAGE_CLOSE", "MANUAL_TRIAGE_CLOSURE", "RESOLVE_ESCALATION"):
        if len(rationale) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"HTTP 422: Mandatory rationale of >= 10 characters required for action '{action}'.",
            )
        if action == "OVERRIDE":
            if not final_verdict:
                raise HTTPException(status_code=400, detail="final_verdict is required on OVERRIDE.")
            if not final_severity:
                raise HTTPException(status_code=400, detail="final_severity is required on OVERRIDE.")

    # Resolve active user from JWT Bearer token or payload
    user = None
    if auth and auth.credentials:
        try:
            token_payload = jwt.decode(
                auth.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            sub = token_payload.get("sub")
            if sub:
                user = db.query(User).filter(User.id == uuid.UUID(sub)).first()
        except Exception:
            pass

    if not user:
        user_id_raw = payload.get("user_id")
        if user_id_raw:
            user_uuid = parse_uuid(str(user_id_raw))
            user = db.query(User).filter(User.id == user_uuid).first()
        else:
            user = db.query(User).first()
            user_uuid = user.id if user else uuid.uuid4()
    else:
        user_uuid = user.id

    # Enforce AC-12 (FR-6): Only TeamLead or Admin can resolve escalated alerts
    if action == "RESOLVE_ESCALATION":
        caller_role = user.role if user else "Analyst"
        if caller_role not in ("TeamLead", "Admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HTTP 403 Forbidden: Only TeamLead or Admin can resolve escalated alerts (AC-12, FR-6).",
            )

    # Get current AI assessment for previous state
    ai = db.query(AIAssessment).filter(AIAssessment.alert_id == alert.id).first()
    prev_verdict = ai.effective_verdict if ai else None
    prev_severity = ai.effective_severity if ai else None

    # Handle status transition (SRS v1.4 §6.4, FR-6, UC-7)
    exemplar_created = False
    if action in ("APPROVE", "OVERRIDE", "MANUAL_TRIAGE_CLOSE", "MANUAL_TRIAGE_CLOSURE", "RESOLVE_ESCALATION"):
        alert.status = "CLOSED"
    elif action == "ESCALATE":
        alert.status = "ESCALATED"
    elif action == "RETRY_AI":
        alert.status = "PENDING_REVIEW"
        alert.retry_count = 0
        if ai:
            ai.retry_count = 0
            # Clean execution hook for live pipeline / guardrails (WP-4 handshake)
            if not settings.DEMO_MODE:
                try:
                    from ..services.rules_engine import apply_guardrails
                    from ..services.triage_schema import LLMTriageOutput

                    ep = db.query(EvidencePack).filter(EvidencePack.alert_id == alert.id).first()
                    valid_keys = ep.valid_dot_keys if ep and ep.valid_dot_keys else []
                    injection = ep.injection_suspect if ep else False
                    llm_repr = LLMTriageOutput(
                        verdict=ai.raw_verdict if ai.raw_verdict in ("TRUE_POSITIVE", "FALSE_POSITIVE", "NEEDS_ANALYST_REVIEW") else "TRUE_POSITIVE",
                        recommended_severity=ai.raw_severity if ai.raw_severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "HIGH",
                        confidence_score=ai.confidence_score if ai.confidence_score is not None else 0.85,
                        cited_evidence_keys=ai.cited_evidence_keys if isinstance(ai.cited_evidence_keys, list) else [],
                        explanation=(ai.explanation or "Re-evaluated via RETRY_AI trigger.")[:500],
                    )
                    gr = apply_guardrails(
                        rule_level=alert.rule_level,
                        llm=llm_repr,
                        valid_dot_keys=valid_keys,
                        injection_suspect=injection,
                    )
                    ai.effective_verdict = gr.effective_verdict
                    ai.effective_severity = gr.effective_severity
                    ai.safety_floor_triggered = gr.safety_floor_triggered
                    ai.abstention_triggered = gr.abstention_triggered
                    ai.guardrail_audit_note = gr.guardrail_audit_note
                except Exception:
                    pass  # Non-blocking if executing in decoupled worker mode

    alert.updated_at = datetime.now(timezone.utc)

    # If OVERRIDE, dynamically create feedback exemplar (FR-4)
    if action == "OVERRIDE":
        asset = db.query(Asset).filter(Asset.agent_id == alert.agent_id).first()
        exemplar = FeedbackExemplar(
            source_alert_id=alert.id,
            rule_id=alert.rule_id,
            process_signature=alert.process_signature or "Unknown Process",
            asset_criticality=asset.criticality_tier if asset else "MEDIUM",
            calibrated_verdict=final_verdict,
            calibrated_severity=final_severity,
            rationale=rationale,
            is_active=True,
            match_hit_count=0,
            user_id=user_uuid,
            created_by=user_uuid,
        )
        db.add(exemplar)
        exemplar_created = True

    # Record immutable audit entry
    audit_id = uuid.uuid4()
    audit_record = AnalystDecisionAudit(
        id=audit_id,
        alert_id=alert.id,
        user_id=user_uuid,
        action_taken=action,
        previous_verdict=prev_verdict,
        previous_severity=prev_severity,
        final_verdict=final_verdict or (prev_verdict if action == "APPROVE" else None),
        final_severity=final_severity or (prev_severity if action == "APPROVE" else None),
        rationale=rationale,
        exemplar_created=exemplar_created,
    )
    db.add(audit_record)

    db.commit()
    db.refresh(audit_record)  # BUG-N3 fix: populate server-generated created_at before serializing

    return {
        "id": str(audit_id),
        "alert_id": str(alert.id),
        "user_id": str(user_uuid),
        "username": user.username if user else "analyst_01",
        "user_role": user.role if user else "Analyst",
        "action_taken": action,
        "previous_verdict": prev_verdict,
        "previous_severity": prev_severity,
        "final_verdict": audit_record.final_verdict,
        "final_severity": audit_record.final_severity,
        "rationale": rationale,
        "exemplar_created": exemplar_created,
        "created_at": str(audit_record.created_at),
    }
