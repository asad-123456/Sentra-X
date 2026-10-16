/**
 * Sentra-X Official TypeScript Data Contracts
 * Authoritative types strictly traced to sentraX_srs.md (v1.3) Section 7.2
 * and frontend_design.md
 */

// ---------------------------------------------------------------------------
// 1. Primitive Enums & System Types
// ---------------------------------------------------------------------------

export type UserRole = 'Analyst' | 'TeamLead' | 'Admin';

export type AlertStatus =
  | 'PENDING_REVIEW'
  | 'AWAITING_ANALYST'
  | 'NEEDS_MANUAL_TRIAGE'
  | 'ESCALATED'
  | 'CLOSED';

export type SeverityLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type BinaryVerdict = 'TRUE_POSITIVE' | 'FALSE_POSITIVE';

export type AIVerdict = BinaryVerdict | 'NEEDS_ANALYST_REVIEW';

export type AssetCriticalityTier = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type LLMProvider = 'Gemini' | 'Claude';

export type DecisionAction =
  | 'APPROVE'
  | 'OVERRIDE'
  | 'ESCALATE'
  | 'RETRY_AI'
  | 'MANUAL_TRIAGE_CLOSE'
  | 'RESOLVE_ESCALATION';

export type ExemplarMatchTier = 'Tier 1' | 'Tier 2';

// ---------------------------------------------------------------------------
// 2. Database Entities (SRS Section 7.2 Relational Model)
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Asset {
  id?: string;
  agent_id: string;
  hostname: string;
  ip_address: string;
  criticality_tier: AssetCriticalityTier;
  description?: string;
  created_at?: string;
  updated_at: string;
}

export interface CorrelatedAlert {
  id: string;
  wazuh_alert_id: string;
  rule_id: string;
  rule_description: string;
  severity: SeverityLevel;
  verdict: AIVerdict;
  timestamp: string;
  agent_id: string;
  src_ip?: string;
}

export interface EvidencePack {
  id: string;
  alert_id: string;
  alert_metadata: {
    wazuh_alert_id: string;
    timestamp: string;
    rule: {
      id: string;
      level: number;
      description: string;
      mitre?: {
        tactics?: string[];
        id?: string[];
      };
    };
  };
  asset_context: {
    agent_id: string;
    agent_name: string;
    criticality_tier: AssetCriticalityTier;
  };
  telemetry_payload: Record<string, unknown>;
  temporal_context: CorrelatedAlert[];
  injected_exemplar_ids: string[];
  injection_suspect: boolean;
  valid_dot_keys?: string[];
  pack_json?: Record<string, unknown>;
  created_at: string;
}

export interface AIAssessment {
  id: string;
  alert_id: string;
  evidence_pack_id?: string;
  raw_verdict: AIVerdict;
  raw_severity: SeverityLevel;
  effective_verdict: AIVerdict;
  effective_severity: SeverityLevel;
  confidence_score: number;
  cited_evidence_keys: string[];
  explanation: string;
  safety_floor_triggered: boolean;
  abstention_triggered: boolean;
  guardrail_audit_note?: string;
  llm_provider: LLMProvider;
  model_name: string;
  latency_ms: number;
  retry_count: number;
  created_at: string;
}

export interface AnalystDecisionAudit {
  id: string;
  alert_id: string;
  user_id: string;
  username?: string;
  user_role?: UserRole;
  action_taken: DecisionAction;
  previous_verdict: string;
  previous_severity: string;
  final_verdict: BinaryVerdict;
  final_severity: SeverityLevel;
  rationale: string;
  exemplar_created?: boolean;
  created_at: string;
}

export interface FeedbackExemplar {
  id: string;
  source_alert_id: string;
  rule_id: string;
  process_signature: string;
  asset_criticality: AssetCriticalityTier;
  calibrated_verdict: BinaryVerdict;
  calibrated_severity: SeverityLevel;
  rationale: string;
  match_tier_support?: ExemplarMatchTier;
  match_hit_count: number;
  is_active: boolean;
  created_by?: string;
  created_at: string;
}

export interface Alert {
  id: string;
  wazuh_alert_id: string;
  rule_id: string;
  rule_level: number;
  rule_description: string;
  mitre_tactics: string[];
  mitre_techniques: string[];
  agent_id: string;
  agent_name: string;
  src_ip?: string;
  process_signature?: string;
  raw_payload?: Record<string, unknown>;
  status: AlertStatus;
  ingested_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// 3. UI Joined & View Models
// ---------------------------------------------------------------------------

export interface AlertListItem extends Alert {
  effective_severity: SeverityLevel;
  effective_verdict: AIVerdict | 'NEEDS_MANUAL_TRIAGE';
  confidence_score?: number | null;
  truncated_explanation: string;
  safety_floor_triggered: boolean;
  abstention_triggered: boolean;
  injection_suspect: boolean;
  has_few_shot: boolean;
  asset_criticality: AssetCriticalityTier;
}

export interface AlertDetail {
  alert: Alert;
  evidence_pack: EvidencePack;
  assessment: AIAssessment;
  injected_exemplars: FeedbackExemplar[];
  correlated_alerts: CorrelatedAlert[];
  decision_audit_trail: AnalystDecisionAudit[];
}

export interface DecisionPayload {
  alert_id?: string;
  action: DecisionAction;
  final_verdict?: BinaryVerdict;
  final_severity?: SeverityLevel;
  rationale?: string;
  save_as_exemplar?: boolean;
}

// ---------------------------------------------------------------------------
// 4. Queue Filter State & Pagination
// ---------------------------------------------------------------------------

export type QueueTab = 'awaiting' | 'escalated' | 'closed';

export type GuardrailFilter =
  | 'ALL'
  | 'SAFETY_FLOOR'
  | 'ABSTENTION'
  | 'INJECTION_SUSPECT'
  | 'MANUAL_TRIAGE';

export interface QueueFilters {
  tab: QueueTab;
  subStatus?: string;
  severity?: string;
  guardrail?: GuardrailFilter;
  assetTier?: string;
  search?: string;
  ruleId?: string;
  page: number;
  pageSize: number;
}

export interface QueueCounts {
  awaiting: number;
  escalated: number;
  closed: number;
  criticalSafetyFloor: number;
  abstentionWarnings: number;
  awaitingAnalystCount: number;
  needsManualTriageCount: number;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// ---------------------------------------------------------------------------
// 5. Analytics & Audit Reporting (FR-7)
// ---------------------------------------------------------------------------

export interface OverrideTrendPoint {
  date: string;
  total_closed: number;
  override_count: number;
  override_rate: number;
  exemplar_count: number;
}

export interface SeverityDeltaSummary {
  low_to_critical: number;
  medium_to_high: number;
  high_to_critical: number;
  tp_to_fp: number;
  fp_to_tp: number;
  safety_floor_count: number;
  abstention_count: number;
  injection_intercept_count: number;
}

export interface AnalyticsSummary {
  total_closed: number;
  agreement_rate: number;
  override_rate: number;
  escalated_rate: number;
  manual_triage_rate: number;
  mean_latency_seconds: number;
  cohens_kappa: number;
  precision: number;
  recall: number;
  accuracy: number;
  confusion_matrix: {
    tp_tp: number;
    tp_fp_overridden: number;
    fp_tp_overridden: number;
    fp_fp: number;
  };
  override_root_causes: {
    cause: string;
    count: number;
    percentage: number;
  }[];
  trendline: OverrideTrendPoint[];
  severity_deltas: SeverityDeltaSummary;
}

// ---------------------------------------------------------------------------
// 6. Adversarial Benchmark & Evaluation (FR-10, Appendix C)
// ---------------------------------------------------------------------------

export type PromptInjectionCategory =
  | '1. Direct Instruction Override'
  | '2. Delimiter & Role Spoofing'
  | '3. Citation & Confidence Spoofing';

export interface BenchmarkPayload {
  id: string;
  category: PromptInjectionCategory;
  target_field: string;
  payload: string;
  injection_detected: boolean;
  baseline_verdict: string;
  baseline_bypassed: boolean;
  sentrax_verdict: string;
  sentrax_bypassed: boolean;
  defense_mechanism: string;
}

export interface BenchmarkComparativeScorecard {
  metric_name: string;
  baseline_value: string;
  sentrax_value: string;
  research_delta: string;
  is_target_met: boolean;
}

export interface EvaluationReport {
  timestamp: string;
  dataset_name: string;
  total_payloads: number;
  baseline_bypass_rate: number;
  sentrax_bypass_rate: number;
  nfr3_target_achieved: boolean;
  comparative_metrics: BenchmarkComparativeScorecard[];
  adversarial_suite: BenchmarkPayload[];
}

// ---------------------------------------------------------------------------
// 7. System Configuration & Engine Parameters
// ---------------------------------------------------------------------------

export interface SystemConfig {
  wazuh_endpoint: string;
  wazuh_status: 'CONNECTED' | 'DISCONNECTED' | 'DEGRADED';
  polling_interval_seconds: number;
  min_rule_level: number;
  llm_provider: LLMProvider;
  model_name: string;
  abstention_threshold: number;
  max_exemplars_injected: number;
  last_sync_timestamp: string;
}


