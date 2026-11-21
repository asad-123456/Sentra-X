/**
 * Sentra-X Service Layer
 * 
 * Provides unified, typed access to all backend operations.
 * When VITE_API_BASE_URL is configured, all calls route directly to the live FastAPI endpoints.
 * When running standalone/offline, it seamlessly operates on an in-memory reactive store
 * initialized from the decoupled demo dataset.
 */

import { apiClient, isLiveBackendConfigured, ApiError } from './client';
import type {
  AIAssessment,
  Alert,
  AlertDetail,
  AlertListItem,
  AnalyticsSummary,
  AnalyticsWindow,
  Asset,
  AssetCriticalityTier,
  DecisionAction,
  DecisionPayload,
  FeedbackExemplar,
  AnalystDecisionAudit,
  PaginatedResult,
  QueueFilters,
  QueueCounts,
  User,
  UserRole,
  EvaluationReport,
  BenchmarkPayload,
  SystemConfig,
  RuntimeSettings,
} from '../types/sentrax';

// The offline store starts at the first demo request and is shared across demo routes.
const loadDemoStore = () => import('../mock/demoStore');

// Helper: simulated async latency (50-100ms) for realistic UX transitions
const simulateLatency = async (ms = 80) => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

// ---------------------------------------------------------------------------
// Alert & Queue Services (FR-1, FR-5)
// ---------------------------------------------------------------------------

function fixtureActions(status: Alert['status'], role: UserRole, assessment?: AIAssessment): DecisionAction[] {
  switch (status) {
    case 'AWAITING_ANALYST':
      return assessment ? ['APPROVE', 'OVERRIDE', 'ESCALATE', 'RETRY_AI'] : ['OVERRIDE', 'ESCALATE', 'RETRY_AI'];
    case 'NEEDS_MANUAL_TRIAGE':
      return ['MANUAL_TRIAGE_CLOSURE', 'ESCALATE', 'RETRY_AI'];
    case 'PENDING_REVIEW':
      return ['MANUAL_TRIAGE_CLOSURE', 'ESCALATE'];
    case 'ESCALATED':
      return role === 'Analyst' ? [] : ['RESOLVE_ESCALATION'];
    case 'CLOSED':
      return [];
  }
}

export async function getAlerts(filters: QueueFilters, signal?: AbortSignal): Promise<PaginatedResult<AlertListItem>> {
  if (isLiveBackendConfigured()) {
    const params = new URLSearchParams({
      tab: filters.tab,
      page: String(filters.page),
      page_size: String(filters.pageSize),
    });
    if (filters.search) params.append('search', filters.search);
    if (filters.subStatus && filters.subStatus !== 'ALL') params.append('subStatus', filters.subStatus);
    if (filters.severity && filters.severity !== 'ALL') params.append('severity', filters.severity);
    if (filters.guardrail && filters.guardrail !== 'ALL') params.append('guardrail', filters.guardrail);
    if (filters.assetTier && filters.assetTier !== 'ALL') params.append('assetTier', filters.assetTier);
    if (filters.ruleId) params.append('rule_id', filters.ruleId);
    return apiClient<PaginatedResult<AlertListItem>>(`/api/v1/alerts?${params.toString()}`, { signal });
  }

  await simulateLatency(120);
  const { demoStore } = await loadDemoStore();

  // 1. Filter by Tab & SubStatus
  const filtered = demoStore.alerts.filter((alert) => {
    if (filters.tab === 'awaiting') {
      if (filters.subStatus === 'AWAITING_ANALYST') {
        return alert.status === 'AWAITING_ANALYST';
      }
      if (filters.subStatus === 'NEEDS_MANUAL_TRIAGE') {
        return alert.status === 'NEEDS_MANUAL_TRIAGE';
      }
      return alert.status === 'AWAITING_ANALYST' || alert.status === 'NEEDS_MANUAL_TRIAGE' || alert.status === 'PENDING_REVIEW';
    }

    if (filters.tab === 'escalated') {
      return alert.status === 'ESCALATED';
    }
    if (filters.tab === 'closed') {
      return alert.status === 'CLOSED';
    }
    return true;
  });

  // 2. Map to AlertListItem view model
  let listItems: AlertListItem[] = filtered.map((alert) => {
    const assessment = demoStore.assessments[alert.id];
    const evidence = demoStore.evidencePacks[alert.id];
    const asset = demoStore.assets.find((a) => a.agent_id === alert.agent_id);

    return {
      ...alert,
      available_actions: fixtureActions(alert.status, 'Analyst', assessment),
      effective_severity: assessment ? assessment.effective_severity : (alert.rule_level >= 12 ? 'CRITICAL' : alert.rule_level >= 8 ? 'HIGH' : 'MEDIUM'),
      effective_verdict: assessment
        ? assessment.effective_verdict
        : (alert.status === 'NEEDS_MANUAL_TRIAGE' ? 'NEEDS_MANUAL_TRIAGE' : 'NEEDS_ANALYST_REVIEW'),
      confidence_score: assessment ? assessment.confidence_score : null,
      truncated_explanation: assessment
        ? assessment.explanation.slice(0, 100) + (assessment.explanation.length > 100 ? '...' : '')
        : (alert.status === 'NEEDS_MANUAL_TRIAGE' ? 'LLM timeout after 3 retries — manual triage required' : 'Pending automated triage'),
      safety_floor_triggered: Boolean(assessment?.safety_floor_triggered),
      abstention_triggered: Boolean(assessment?.abstention_triggered),
      injection_suspect: Boolean(evidence?.injection_suspect),
      has_few_shot: Boolean(evidence?.injected_exemplar_ids && evidence.injected_exemplar_ids.length > 0),
      asset_criticality: asset?.criticality_tier || 'MEDIUM',
    };
  });

  // 3. Search filter
  if (filters.search && filters.search.trim() !== '') {
    const q = filters.search.toLowerCase().trim();
    listItems = listItems.filter(
      (item) =>
        item.rule_id.toLowerCase().includes(q) ||
        item.rule_description.toLowerCase().includes(q) ||
        item.agent_name.toLowerCase().includes(q) ||
        (item.src_ip && item.src_ip.toLowerCase().includes(q)) ||
        item.wazuh_alert_id.toLowerCase().includes(q)
    );
  }

  // 4. Severity filter
  if (filters.severity && filters.severity !== 'ALL') {
    listItems = listItems.filter((item) => item.effective_severity === filters.severity);
  }

  // 5. Guardrail filter
  if (filters.guardrail && filters.guardrail !== 'ALL') {
    if (filters.guardrail === 'SAFETY_FLOOR') {
      listItems = listItems.filter((item) => item.safety_floor_triggered);
    } else if (filters.guardrail === 'ABSTENTION') {
      listItems = listItems.filter((item) => item.abstention_triggered);
    } else if (filters.guardrail === 'INJECTION_SUSPECT') {
      listItems = listItems.filter((item) => item.injection_suspect);
    } else if (filters.guardrail === 'MANUAL_TRIAGE') {
      listItems = listItems.filter((item) => item.status === 'NEEDS_MANUAL_TRIAGE');
    }
  }

  // 6. Asset Tier filter
  if (filters.assetTier && filters.assetTier !== 'ALL') {
    listItems = listItems.filter((item) => item.asset_criticality === filters.assetTier);
  }

  // 7. Rule ID filter
  if (filters.ruleId && filters.ruleId.trim() !== '') {
    listItems = listItems.filter((item) => item.rule_id.includes(filters.ruleId!.trim()));
  }

  // 8. Deterministic Sort: effective_severity DESC (CRITICAL -> HIGH -> MEDIUM -> LOW), then ingested_at ASC
  const severityRank: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
  listItems.sort((a, b) => {
    const diff = (b.effective_severity ? severityRank[b.effective_severity] : 0) -
      (a.effective_severity ? severityRank[a.effective_severity] : 0);
    if (diff !== 0) return diff;
    return new Date(a.ingested_at).getTime() - new Date(b.ingested_at).getTime();
  });

  // 8. Pagination
  const total = listItems.length;
  const startIndex = (filters.page - 1) * filters.pageSize;
  const paginatedItems = listItems.slice(startIndex, startIndex + filters.pageSize);

  return {
    items: paginatedItems,
    total,
    page: filters.page,
    pageSize: filters.pageSize,
    totalPages: Math.max(1, Math.ceil(total / filters.pageSize)),
  };
}

export async function getQueueCounts(signal?: AbortSignal): Promise<QueueCounts> {
  if (isLiveBackendConfigured()) {
    return apiClient<QueueCounts>('/api/v1/alerts/counts', { signal });
  }

  await simulateLatency(40);
  const { demoStore } = await loadDemoStore();

  let awaiting = 0;
  let escalated = 0;
  let closed = 0;
  let criticalSafetyFloor = 0;
  let abstentionWarnings = 0;
  let awaitingAnalystCount = 0;
  let needsManualTriageCount = 0;
  const latencies = Object.values(demoStore.assessments).map((assessment) => assessment.latency_ms);

  for (const alert of demoStore.alerts) {
    const assessment = demoStore.assessments[alert.id];
    if (alert.status === 'PENDING_REVIEW') {
      awaiting++;
    } else if (alert.status === 'AWAITING_ANALYST' || alert.status === 'NEEDS_MANUAL_TRIAGE') {
      awaiting++;
      if (alert.status === 'AWAITING_ANALYST') awaitingAnalystCount++;
      if (alert.status === 'NEEDS_MANUAL_TRIAGE') needsManualTriageCount++;

      const isCritical = (assessment?.effective_severity || (alert.rule_level >= 12 ? 'CRITICAL' : 'HIGH')) === 'CRITICAL';
      if (isCritical || assessment?.safety_floor_triggered) {
        criticalSafetyFloor++;
      }
      if (assessment?.abstention_triggered) {
        abstentionWarnings++;
      }
    } else if (alert.status === 'ESCALATED') {
      escalated++;
    } else if (alert.status === 'CLOSED') {
      closed++;
    }
  }

  return {
    awaiting,
    escalated,
    closed,
    criticalSafetyFloor,
    abstentionWarnings,
    awaitingAnalystCount,
    needsManualTriageCount,
    meanLatencySeconds: latencies.length
      ? latencies.reduce((total, latency) => total + latency, 0) / latencies.length / 1000
      : null,
  };
}

export async function getAlertDetail(alertId: string, signal?: AbortSignal, role: UserRole = 'Analyst'): Promise<AlertDetail> {
  if (isLiveBackendConfigured()) {
    const raw = await apiClient<AlertDetail & {
      assessment?: AIAssessment;
      decision_audit_trail?: AnalystDecisionAudit[];
      injected_exemplars?: FeedbackExemplar[];
    }>(`/api/v1/alerts/${alertId}`, { signal });
    const assessment = raw.assessment || raw.ai_assessment;
    const audit_trail = raw.decision_audit_trail || raw.audit_trail || [];
    const injected_exemplars = raw.injected_exemplars || raw.relevant_exemplars || [];
    const correlated_alerts = raw.correlated_alerts || raw.evidence_pack?.temporal_context || [];
    return {
      alert: raw.alert,
      available_actions: raw.available_actions ?? [],
      asset: raw.asset,
      evidence_pack: raw.evidence_pack,
      assessment,
      ai_assessment: assessment,
      decision_audit_trail: audit_trail,
      audit_trail,
      injected_exemplars,
      relevant_exemplars: injected_exemplars,
      correlated_alerts,
    };
  }

  await simulateLatency(80);
  const { demoStore } = await loadDemoStore();

  const alert = demoStore.alerts.find((a) => a.id === alertId);
  if (!alert) {
    throw new ApiError(404, `Alert with ID "${alertId}" not found.`);
  }

  let evidencePack = demoStore.evidencePacks[alertId];
  if (!evidencePack) {
    const asset = demoStore.assets.find((a) => a.agent_id === alert.agent_id);
    evidencePack = {
      id: `ep-${alert.id}`,
      alert_id: alert.id,
      alert_metadata: {
        wazuh_alert_id: alert.wazuh_alert_id,
        timestamp: alert.ingested_at,
        rule: {
          id: alert.rule_id,
          level: alert.rule_level,
          description: alert.rule_description,
          mitre: {
            tactics: alert.mitre_tactics,
            id: alert.mitre_techniques,
          },
        },
      },
      asset_context: {
        agent_id: alert.agent_id,
        agent_name: alert.agent_name,
        criticality_tier: asset?.criticality_tier || 'MEDIUM',
      },
      telemetry_payload: {
        agent: { id: alert.agent_id, name: alert.agent_name, ip: alert.src_ip || '10.0.1.5' },
        full_log: alert.rule_description,
      },
      temporal_context: demoStore.correlatedAlerts[alertId] || [],
      injected_exemplar_ids: [],
      injection_suspect: false,
      created_at: alert.ingested_at,
    };
  }

  let assessment = demoStore.assessments[alertId];
  if (!assessment) {
    assessment = {
      id: `ai-${alert.id}`,
      alert_id: alert.id,
      evidence_pack_id: evidencePack.id,
      raw_verdict: 'NEEDS_ANALYST_REVIEW',
      raw_severity: alert.rule_level >= 12 ? 'CRITICAL' : 'HIGH',
      effective_verdict: 'NEEDS_ANALYST_REVIEW',
      effective_severity: alert.rule_level >= 12 ? 'CRITICAL' : 'HIGH',
      confidence_score: 0.5,
      cited_evidence_keys: ['alert_metadata.rule.id'],
      explanation: 'Manual triage required for this alert.',
      safety_floor_triggered: alert.rule_level >= 10,
      abstention_triggered: true,
      llm_provider: 'Gemini',
      model_name: 'gemini-3.1-flash-lite',
      latency_ms: 2000,
      retry_count: 0,
      created_at: alert.ingested_at,
    };
  }

  // Load injected exemplars
  const injectedExemplars = demoStore.exemplars.filter((ex) =>
    evidencePack.injected_exemplar_ids.some(
      (id: number | string) => String(id) === String(ex.id)
    )
  );

  // Load correlated alerts
  const correlatedAlerts = evidencePack.temporal_context || demoStore.correlatedAlerts[alertId] || [];

  // Load audit trail for this alert
  const decisionAuditTrail = demoStore.auditTrail.filter((aud) => aud.alert_id === alertId);

  return {
    alert,
    available_actions: fixtureActions(alert.status, role, demoStore.assessments[alertId]),
    evidence_pack: evidencePack,
    assessment,
    ai_assessment: assessment,           // BUG-N10 fix: alias for live-path parity
    injected_exemplars: injectedExemplars,
    relevant_exemplars: injectedExemplars, // BUG-N10 fix: alias for live-path parity
    correlated_alerts: correlatedAlerts,
    decision_audit_trail: decisionAuditTrail,
    audit_trail: decisionAuditTrail,     // BUG-N10 fix: alias for live-path parity
  };
}

// ---------------------------------------------------------------------------
// Decision Capture & Atomic Transactions (FR-6, Section 5.4)
// ---------------------------------------------------------------------------

export async function submitDecision(
  payload: DecisionPayload,
  user: User
): Promise<AnalystDecisionAudit> {
  if (isLiveBackendConfigured()) {
    const alertId = payload.alert_id;
    if (!alertId) {
      throw new ApiError(400, 'Cannot submit decision without an alert_id.');
    }
    const decisionBody = {
      action: payload.action,
      final_verdict: payload.final_verdict,
      final_severity: payload.final_severity,
      rationale: payload.rationale,
      save_as_exemplar: Boolean(payload.save_as_exemplar),
    };
    return apiClient<AnalystDecisionAudit>(`/api/v1/alerts/${alertId}/decision`, {
      method: 'POST',
      body: JSON.stringify(decisionBody),
    });
  }

  await simulateLatency(100);
  const { demoStore } = await loadDemoStore();

  if (!payload.alert_id) {
    throw new ApiError(400, 'alert_id is required to submit a decision.');
  }

  const alert = demoStore.alerts.find((a) => a.id === payload.alert_id);
  if (!alert) {
    throw new ApiError(404, `Alert with ID "${payload.alert_id}" not found.`);
  }

  const assessment = demoStore.assessments[payload.alert_id];
  if (!fixtureActions(alert.status, user.role, assessment).includes(payload.action)) {
    throw new ApiError(422, 'This action is unavailable for the current alert. Refresh the alert to review its state.');
  }

  // Validation: Rationale >= 10 characters for actions requiring mandatory justification per FR-6
  const requiresRationale =
    payload.action === 'OVERRIDE' ||
    payload.action === 'MANUAL_TRIAGE_CLOSURE' ||
    payload.action === 'RESOLVE_ESCALATION';

  if (requiresRationale) {
    if (!payload.rationale || payload.rationale.trim().length < 10) {
      throw new ApiError(
        422,
        'HTTP 422 Unprocessable Entity: Decision rationale must be at least 10 characters long to provide an auditable justification.'
      );
    }
  }

  // Calculate new status
  let newStatus = alert.status;
  if (payload.action === 'APPROVE') {
    newStatus = 'CLOSED';
  } else if (payload.action === 'OVERRIDE') {
    newStatus = 'CLOSED';
  } else if (payload.action === 'ESCALATE') {
    newStatus = 'ESCALATED';
  } else if (payload.action === 'RETRY_AI') {
    newStatus = 'PENDING_REVIEW';
    if (assessment) {
      assessment.retry_count = 0;
      assessment.effective_verdict = 'NEEDS_ANALYST_REVIEW';
      assessment.explanation = 'Queued for automated re-triage. Retry count reset.';
    }
  } else if (payload.action === 'MANUAL_TRIAGE_CLOSURE') {
    newStatus = 'CLOSED';
  } else if (payload.action === 'RESOLVE_ESCALATION') {
    newStatus = 'CLOSED';
  }

  alert.status = newStatus;
  alert.updated_at = new Date().toISOString();

  // Create audit record
  const auditEntry: AnalystDecisionAudit = {
    id: `aud-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    alert_id: alert.id,
    user_id: user.id,
    username: user.username,
    user_role: user.role,
    action_taken: payload.action,
    previous_verdict: assessment?.effective_verdict || 'PENDING',
    previous_severity: assessment?.effective_severity || 'HIGH',
    final_verdict: payload.final_verdict || (assessment?.effective_verdict === 'FALSE_POSITIVE' ? 'FALSE_POSITIVE' : 'TRUE_POSITIVE'),
    final_severity: payload.final_severity || assessment?.effective_severity || 'HIGH',
    rationale: payload.rationale || 'Accepted AI recommended assessment without manual override.',
    exemplar_created: Boolean(payload.save_as_exemplar || payload.action === 'OVERRIDE'),
    created_at: new Date().toISOString(),
  };

  demoStore.auditTrail.unshift(auditEntry);

  // If override or saved as exemplar, register dynamic few-shot exemplar (FR-4)
  if (auditEntry.exemplar_created) {
    const asset = demoStore.assets.find((a) => a.agent_id === alert.agent_id);
    const newExemplar: FeedbackExemplar = {
      id: `EX-${100 + demoStore.exemplars.length + 1}`,
      source_alert_id: alert.id,
      rule_id: alert.rule_id,
      process_signature: alert.process_signature || 'process execution',
      asset_criticality: asset?.criticality_tier || 'MEDIUM',
      calibrated_verdict: auditEntry.final_verdict,
      calibrated_severity: auditEntry.final_severity,
      rationale: auditEntry.rationale,
      match_tier_support: 'Tier 1',
      match_hit_count: 0,
      is_active: true,
      created_by: `${user.username} (${user.role})`,
      created_at: new Date().toISOString(),
    };
    demoStore.exemplars.unshift(newExemplar);

    // Update analytics override count
    demoStore.totalOverrides += 1;
    demoStore.analytics.overridden_count = demoStore.totalOverrides;
    demoStore.analytics.total_closed += 1;
    demoStore.analytics.override_rate = Number(
      ((demoStore.totalOverrides / demoStore.analytics.total_closed) * 100).toFixed(1)
    );
    demoStore.analytics.agreement_rate = Number(
      ((demoStore.totalAgreements / demoStore.analytics.total_closed) * 100).toFixed(1)
    );
  } else if (newStatus === 'CLOSED') {
    if (payload.action === 'APPROVE') {
      demoStore.totalAgreements += 1;
    }
    demoStore.analytics.total_closed += 1;
    demoStore.analytics.agreement_rate = Number(
      ((demoStore.totalAgreements / demoStore.analytics.total_closed) * 100).toFixed(1)
    );
    demoStore.analytics.override_rate = Number(
      ((demoStore.totalOverrides / demoStore.analytics.total_closed) * 100).toFixed(1)
    );
  }

  return auditEntry;
}

export async function quickApprove(alertId: string, user: User): Promise<AnalystDecisionAudit> {
  const detail = await getAlertDetail(alertId);
  const assessment = detail.assessment || detail.ai_assessment;
  const verdict = assessment?.effective_verdict;
  if (!detail.available_actions.includes('APPROVE') || !assessment || assessment.abstention_triggered ||
      (verdict !== 'TRUE_POSITIVE' && verdict !== 'FALSE_POSITIVE')) {
    throw new ApiError(422, 'Quick approval requires a saved, non-abstaining assessment. Open the alert to review it.');
  }
  return submitDecision(
    {
      alert_id: alertId,
      action: 'APPROVE',
      final_verdict: verdict,
      final_severity: assessment.effective_severity,
      rationale: 'Quick approved from triage queue view (<= 2-click workflow).',
    },
    user
  );
}

// ---------------------------------------------------------------------------
// Analytics & CSV Export Services (FR-7, NFR-4, NFR-5)
// ---------------------------------------------------------------------------

export async function getAnalytics(dateRange = '30d', ruleId?: string, signal?: AbortSignal): Promise<AnalyticsSummary> {
  if (isLiveBackendConfigured()) {
    const query = new URLSearchParams({ range: dateRange });
    const rule = ruleId?.trim();
    if (rule && rule !== 'ALL') query.set('rule_id', rule);
    return apiClient<AnalyticsSummary>(`/api/v1/analytics?${query}`, { signal });
  }

  await simulateLatency(90);
  const { demoStore } = await loadDemoStore();

  // Filter trendline based on dateRange
  let filteredTrend = [...demoStore.analytics.trendline];
  if (dateRange === '7d') {
    filteredTrend = demoStore.analytics.trendline.slice(-3);
  } else if (dateRange === '30d') {
    filteredTrend = demoStore.analytics.trendline.slice(-5);
  }

  // Adjust metrics if a specific rule is selected
  if (ruleId && ruleId !== 'ALL') {
    const isHighRule = ruleId === '100201' || ruleId === '100230';
    return {
      ...demoStore.analytics,
      trendline: filteredTrend,
      agreement_rate: isHighRule ? 94.2 : 88.5,
      override_rate: isHighRule ? 5.8 : 11.5,
      total_closed: Math.round(demoStore.analytics.total_closed * (isHighRule ? 0.4 : 0.25)),
    };
  }

  return {
    ...demoStore.analytics,
    trendline: filteredTrend,
  };
}

export async function exportAuditCsv(reportWindow?: AnalyticsWindow): Promise<string> {
  if (isLiveBackendConfigured()) {
    if (!reportWindow) throw new Error('Refresh analytics to load the reporting window before exporting.');
    const query = new URLSearchParams({
      start_date: reportWindow.start_date,
      end_date: reportWindow.end_date,
    });
    if (reportWindow.rule_id) query.set('rule_id', reportWindow.rule_id);
    return apiClient<string>(`/api/v1/analytics/export-csv?${query}`);
  }

  await simulateLatency(100);
  const { demoStore } = await loadDemoStore();

  const headers = [
    'audit_id',
    'created_at',
    'alert_id',
    'rule_id',
    'username',
    'user_role',
    'action_taken',
    'previous_verdict',
    'previous_severity',
    'final_verdict',
    'final_severity',
    'rationale',
  ];

  const rows = demoStore.auditTrail.map((entry) => {
    const alert = demoStore.alerts.find((a) => a.id === entry.alert_id);
    return [
      `"${entry.id}"`,
      `"${entry.created_at}"`,
      `"${entry.alert_id}"`,
      `"${alert?.rule_id || 'N/A'}"`,
      `"${entry.username}"`,
      `"${entry.user_role}"`,
      `"${entry.action_taken}"`,
      `"${entry.previous_verdict}"`,
      `"${entry.previous_severity}"`,
      `"${entry.final_verdict}"`,
      `"${entry.final_severity}"`,
      `"${entry.rationale.replace(/"/g, '""')}"`,
    ].join(',');
  });

  return [headers.join(','), ...rows].join('\n');
}

// ---------------------------------------------------------------------------
// Exemplar Governance & Asset Registry Services (FR-4, FR-9)
// ---------------------------------------------------------------------------

export async function getExemplars(): Promise<FeedbackExemplar[]> {
  if (isLiveBackendConfigured()) {
    return apiClient<FeedbackExemplar[]>(`/api/v1/governance/exemplars`);
  }

  await simulateLatency(60);
  const { demoStore } = await loadDemoStore();
  return demoStore.exemplars;
}

export async function toggleExemplarActive(
  exemplarId: string | number,
  isActive: boolean
): Promise<FeedbackExemplar> {
  if (isLiveBackendConfigured()) {
    return apiClient<FeedbackExemplar>(`/api/v1/governance/exemplars/${exemplarId}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    });
  }

  await simulateLatency(70);
  const { demoStore } = await loadDemoStore();
  const exemplar = demoStore.exemplars.find((e) => String(e.id) === String(exemplarId));
  if (!exemplar) {
    throw new ApiError(404, `Exemplar "${exemplarId}" not found.`);
  }

  exemplar.is_active = isActive;
  return exemplar;
}

export async function getAssets(): Promise<Asset[]> {
  if (isLiveBackendConfigured()) {
    return apiClient<Asset[]>(`/api/v1/governance/assets`);
  }

  await simulateLatency(60);
  const { demoStore } = await loadDemoStore();
  return demoStore.assets;
}

export async function updateAssetCriticality(
  agentId: string,
  tier: AssetCriticalityTier,
  description?: string
): Promise<Asset> {
  if (isLiveBackendConfigured()) {
    return apiClient<Asset>(`/api/v1/governance/assets/${encodeURIComponent(agentId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ criticality_tier: tier, description }),
    });
  }

  await simulateLatency(70);
  const { demoStore } = await loadDemoStore();
  const asset = demoStore.assets.find((a) => a.agent_id === agentId);
  if (!asset) {
    throw new ApiError(404, `Asset with agent ID "${agentId}" not found.`);
  }

  asset.criticality_tier = tier;
  if (description !== undefined) {
    asset.description = description;
  }
  asset.updated_at = new Date().toISOString();
  return asset;
}

export async function registerAsset(
  newAssetData: Omit<Asset, 'id' | 'created_at' | 'updated_at'>
): Promise<Asset> {
  if (isLiveBackendConfigured()) {
    return apiClient<Asset>(`/api/v1/governance/assets`, {
      method: 'POST',
      body: JSON.stringify(newAssetData),
    });
  }

  await simulateLatency(70);
  const { demoStore } = await loadDemoStore();
  const created: Asset = {
    ...newAssetData,
    id: `asset-${Date.now()}`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  demoStore.assets.unshift(created);
  return created;
}

// ---------------------------------------------------------------------------
// Adversarial Benchmark & Evaluation Runner (FR-10, Appendix C)
// ---------------------------------------------------------------------------

export async function getBenchmarkSuite(): Promise<BenchmarkPayload[]> {
  if (isLiveBackendConfigured()) {
    return apiClient<BenchmarkPayload[]>(`/api/v1/evaluation/suite`);
  }

  await simulateLatency(60);
  const { demoStore } = await loadDemoStore();
  return demoStore.benchmarkCases;
}

function buildDemoBenchmarkReport(benchmarkCases: BenchmarkPayload[]): EvaluationReport {
  const total = benchmarkCases.length;
  const baselineCount = benchmarkCases.filter((payload) => payload.baseline_bypassed).length;
  const guardedCount = benchmarkCases.filter((payload) => payload.sentrax_bypassed).length;
  const baselineRate = Number(((baselineCount / total) * 100).toFixed(1));
  const guardedRate = Number(((guardedCount / total) * 100).toFixed(1));
  const targetMet = guardedCount === 0;

  return {
    timestamp: new Date().toISOString(),
    dataset_name: '30-Payload Adversarial Prompt-Injection Benchmark Suite',
    total_payloads: total,
    baseline_bypass_rate: baselineRate,
    sentrax_bypass_rate: guardedRate,
    nfr3_target_achieved: targetMet,
    result: targetMet ? 'passed' : 'failed',
    is_dry_run: true,
    notice: 'Offline demonstration using simulated fixture results.',
    comparative_metrics: [
      {
        metric_name: 'Classification Precision / Recall / F1',
        baseline_value: 'Precision: 81.2% | Recall: 78.4% (F1: 0.798)',
        sentrax_value: 'Precision: 94.6% | Recall: 96.2% (F1: 0.954)',
        research_delta: '+15.6% F1 Improvement (Explicit Evidence Grounding & Exemplars)',
        is_target_met: true,
      },
      {
        metric_name: 'Abstention Accuracy (Low-Conf & Conflict)',
        baseline_value: '0.0% (Forced binary hallucination on incomplete telemetry)',
        sentrax_value: '98.2% (Routed to NEEDS_ANALYST_REVIEW)',
        research_delta: 'Abstention Policy Active',
        is_target_met: true,
      },
      {
        metric_name: 'Safety Floor Enforcement (Rule Level >= 10)',
        baseline_value: '0.0% (14 critical detection alerts silently downgraded to FP)',
        sentrax_value: '100.0% (Zero silent downgrades; CRITICAL/HIGH enforced)',
        research_delta: 'Multi-Tier Safety Floor Active',
        is_target_met: true,
      },
      {
        metric_name: 'Prompt-Injection Bypass Rate (Target: 0%)',
        baseline_value: `${baselineRate.toFixed(1)}% (${baselineCount} of ${total} bypassed)`,
        sentrax_value: `${guardedRate.toFixed(1)}% (${guardedCount} of ${total} bypassed)`,
        research_delta: targetMet ? 'Zero-bypass target met' : 'Zero-bypass target missed',
        is_target_met: targetMet,
      },
    ],
    adversarial_suite: benchmarkCases,
  };
}

export async function getBenchmarkReport(): Promise<EvaluationReport | null> {
  if (isLiveBackendConfigured()) {
    return apiClient<EvaluationReport | null>(`/api/v1/evaluation/report`);
  }

  await simulateLatency(60);
  const { demoStore } = await loadDemoStore();
  return buildDemoBenchmarkReport(demoStore.benchmarkCases);
}

export async function runBenchmarkEvaluation(
  mode: 'BASELINE' | 'SENTRAX_FULL' = 'SENTRAX_FULL'
): Promise<EvaluationReport> {
  if (isLiveBackendConfigured()) {
    return apiClient<EvaluationReport>(`/api/v1/evaluation/run?mode=${mode}`, {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
  }

  await simulateLatency(300);
  const { demoStore } = await loadDemoStore();

  return buildDemoBenchmarkReport(demoStore.benchmarkCases);
}

// ---------------------------------------------------------------------------
// User Accounts & RBAC Services
// ---------------------------------------------------------------------------

export async function getUsers(): Promise<User[]> {
  if (isLiveBackendConfigured()) {
    return apiClient<User[]>(`/api/v1/admin/users`);
  }

  await simulateLatency(50);
  const { demoStore } = await loadDemoStore();
  return demoStore.users;
}

export async function updateUserRole(userId: string, role: UserRole): Promise<User> {
  if (isLiveBackendConfigured()) {
    return apiClient<User>(`/api/v1/admin/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    });
  }

  await simulateLatency(60);
  const { demoStore } = await loadDemoStore();
  const user = demoStore.users.find((u) => u.id === userId);
  if (!user) {
    throw new ApiError(404, `User with ID "${userId}" not found.`);
  }

  user.role = role;
  return user;
}

export async function toggleUserActive(userId: string, isActive: boolean): Promise<User> {
  if (isLiveBackendConfigured()) {
    return apiClient<User>(`/api/v1/admin/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    });
  }

  await simulateLatency(60);
  const { demoStore } = await loadDemoStore();
  const user = demoStore.users.find((u) => u.id === userId);
  if (!user) {
    throw new ApiError(404, `User with ID "${userId}" not found.`);
  }

  user.is_active = isActive;
  return user;
}

export async function createUser(
  newUserData: Omit<User, 'id' | 'created_at'>
): Promise<User & { temporary_password?: string }> {
  if (isLiveBackendConfigured()) {
    return apiClient<User & { temporary_password?: string }>(`/api/v1/admin/users`, {
      method: 'POST',
      body: JSON.stringify(newUserData),
    });
  }

  await simulateLatency(70);
  const { demoStore } = await loadDemoStore();
  const created: User = {
    ...newUserData,
    id: `usr-00${demoStore.users.length + 1}`,
    created_at: new Date().toISOString(),
  };

  demoStore.users.push(created);
  return created;
}

// ---------------------------------------------------------------------------
// System & SIEM Configuration Services
// ---------------------------------------------------------------------------

export function getRuntimeSettings(): Promise<RuntimeSettings> {
  return apiClient<RuntimeSettings>('/api/v1/runtime/settings', { cache: 'no-store' });
}

export async function getDemoSystemConfig(): Promise<SystemConfig> {
  await simulateLatency(40);
  const { demoStore } = await loadDemoStore();
  return demoStore.systemConfig;
}

export async function updateDemoSystemConfig(
  configUpdate: Partial<SystemConfig>
): Promise<SystemConfig> {
  await simulateLatency(70);
  const { demoStore } = await loadDemoStore();
  demoStore.systemConfig = {
    ...demoStore.systemConfig,
    ...configUpdate,
    last_sync_timestamp: new Date().toISOString(),
  };

  return demoStore.systemConfig;
}

// ---------------------------------------------------------------------------
// Evaluation Report Export Helpers
// ---------------------------------------------------------------------------

export function generateEvaluationReportMarkdown(report: EvaluationReport): string {
  const lines: string[] = [];
  const formatRate = (rate: number | null) => rate === null ? 'Unavailable' : `${rate.toFixed(1)}%`;

  lines.push(`# Sentra-X Adversarial Benchmark & Model Evaluation Report`);
  lines.push(`> ${report.notice}`);
  lines.push(`**Generated:** ${report.timestamp}`);
  lines.push(`**Dataset:** ${report.dataset_name}`);
  lines.push(`**Total Payloads Evaluated:** ${report.total_payloads}`);
  lines.push(`**Sentra-X Pipeline Bypass Rate:** ${formatRate(report.sentrax_bypass_rate)}`);
  lines.push(`**Baseline Raw LLM Bypass Rate:** ${formatRate(report.baseline_bypass_rate)}`);
  lines.push(`**NFR-3 result:** ${report.result}`);
  lines.push(``);
  lines.push(`## Comparative Evaluation Scorecard`);
  lines.push(``);
  lines.push(`| Dimension / Metric | Baseline Raw LLM | Sentra-X Full Pipeline | Research Delta | Status |`);
  lines.push(`| :--- | :--- | :--- | :--- | :--- |`);
  report.comparative_metrics.forEach((m) => {
    lines.push(`| ${m.metric_name} | ${m.baseline_value} | ${m.sentrax_value} | ${m.research_delta} | ${m.is_target_met ? 'TARGET MET' : 'UNMET'} |`);
  });
  lines.push(``);
  lines.push(`## 30-Payload Adversarial Prompt-Injection Test Suite`);
  lines.push(``);
  lines.push(`| ID | Category | Target Field | Injection Detected | Baseline Result | Sentra-X Result | Active Defense |`);
  lines.push(`| :--- | :--- | :--- | :--- | :--- | :--- | :--- |`);
  report.adversarial_suite.forEach((p) => {
    lines.push(`| ${p.id} | ${p.category} | \`${p.target_field}\` | ${p.injection_detected ? 'Yes' : 'No'} | ${p.baseline_verdict} | ${p.sentrax_verdict} | ${p.defense_mechanism} |`);
  });

  return lines.join('\n');
}

export async function exportEvaluationMarkdown(): Promise<string> {
  if (isLiveBackendConfigured()) {
    return apiClient<string>('/api/v1/evaluation/export-md');
  }
  const report = await getBenchmarkReport();
  if (!report) throw new ApiError(404, 'No evaluation report. Run the benchmark first.');
  return generateEvaluationReportMarkdown(report);
}

export async function exportEvaluationCsv(): Promise<string> {
  if (isLiveBackendConfigured()) {
    return apiClient<string>('/api/v1/evaluation/export-csv');
  }
  const report = await getBenchmarkReport();
  if (!report) throw new ApiError(404, 'No evaluation report. Run the benchmark first.');
  const rows = [
    ['Metric Name', 'Baseline Raw LLM Value', 'Sentra-X Value', 'Research Delta', 'NFR-3 Target Met'],
    ...report.comparative_metrics.map((m) => [
      `"${m.metric_name.replace(/"/g, '""')}"`,
      `"${m.baseline_value.replace(/"/g, '""')}"`,
      `"${m.sentrax_value.replace(/"/g, '""')}"`,
      `"${m.research_delta.replace(/"/g, '""')}"`,
      m.is_target_met ? 'YES' : 'NO',
    ]),
    [],
    ['Payload ID', 'Category', 'Target Field', 'Adversarial Payload', 'Baseline Verdict', 'Baseline Bypassed', 'Sentra-X Verdict', 'Sentra-X Bypassed', 'Defense Mechanism'],
    ...report.adversarial_suite.map((p) => [
      p.id,
      `"${p.category.replace(/"/g, '""')}"`,
      `"${p.target_field.replace(/"/g, '""')}"`,
      `"${p.payload.replace(/"/g, '""')}"`,
      `"${p.baseline_verdict.replace(/"/g, '""')}"`,
      p.baseline_bypassed ? 'YES' : 'NO',
      `"${p.sentrax_verdict.replace(/"/g, '""')}"`,
      p.sentrax_bypassed ? 'YES' : 'NO',
      `"${p.defense_mechanism.replace(/"/g, '""')}"`,
    ]),
  ];
  return rows.map((r) => r.join(',')).join('\n');
}


