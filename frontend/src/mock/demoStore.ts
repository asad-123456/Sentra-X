import { DEMO_USERS } from './demoUsers';
import {
  BENCHMARK_30_PAYLOADS,
  INITIAL_ALERTS,
  INITIAL_ASSESSMENTS,
  INITIAL_ASSETS,
  INITIAL_AUDIT_TRAIL,
  INITIAL_EVIDENCE_PACKS,
  INITIAL_EXEMPLARS,
  INITIAL_ANALYTICS,
  INITIAL_SYSTEM_CONFIG,
  SAMPLE_CORRELATED_ALERTS,
} from './demoData';

export const demoStore = {
  alerts: structuredClone(INITIAL_ALERTS),
  assets: structuredClone(INITIAL_ASSETS),
  exemplars: structuredClone(INITIAL_EXEMPLARS),
  auditTrail: structuredClone(INITIAL_AUDIT_TRAIL),
  evidencePacks: structuredClone(INITIAL_EVIDENCE_PACKS),
  assessments: structuredClone(INITIAL_ASSESSMENTS),
  analytics: structuredClone(INITIAL_ANALYTICS),
  users: structuredClone(DEMO_USERS),
  systemConfig: structuredClone(INITIAL_SYSTEM_CONFIG),
  totalOverrides: 24,
  totalAgreements: Math.round(((INITIAL_ANALYTICS.agreement_rate ?? 0) / 100) * INITIAL_ANALYTICS.total_closed),
  correlatedAlerts: SAMPLE_CORRELATED_ALERTS,
  benchmarkCases: BENCHMARK_30_PAYLOADS,
};
