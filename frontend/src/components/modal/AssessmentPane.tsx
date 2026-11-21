import React, { useEffect, useRef } from 'react';
import type { AlertDetail } from '../../types/sentrax';
import { SeverityBadge } from '../badges/SeverityBadge';
import { VerdictBadge } from '../badges/VerdictBadge';
import { ConfidenceMeter } from '../badges/ConfidenceMeter';
import {
  ShieldAlert,
  Clock,
  AlertTriangle,
  Sparkles,
  Link2,
  BookmarkCheck,
  History,
  Activity,
  FileCode,
  ShieldCheck,
} from 'lucide-react';

interface AssessmentPaneProps {
  alertDetail: AlertDetail;
  selectedCitationKey: string | null;
  onSelectCitationKey: (key: string) => void;
  savedAuditId: string | null;
}

export const AssessmentPane: React.FC<AssessmentPaneProps> = ({
  alertDetail,
  selectedCitationKey,
  onSelectCitationKey,
  savedAuditId,
}) => {
  const alert = alertDetail.alert;
  const isPending = alert.status === 'PENDING_REVIEW';
  const assessment = isPending ? undefined : alertDetail.assessment || alertDetail.ai_assessment;
  const evidence_pack = alertDetail.evidence_pack;
  const injected_exemplars = alertDetail.injected_exemplars || alertDetail.relevant_exemplars || [];
  const correlated_alerts = alertDetail.correlated_alerts || alertDetail.evidence_pack?.temporal_context || [];
  const decision_audit_trail = alertDetail.decision_audit_trail || alertDetail.audit_trail || [];
  const citationKeys = assessment?.cited_evidence_keys ?? [];
  const validCitationKeys = evidence_pack?.valid_dot_keys
    ? citationKeys.filter((key) => evidence_pack.valid_dot_keys?.includes(key))
    : evidence_pack ? citationKeys : [];
  const savedAudit = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (savedAuditId) savedAudit.current?.scrollIntoView({ block: 'center' });
  }, [savedAuditId]);

  return (
    <div className="flex flex-col gap-4 p-3 text-foreground text-sm sm:p-5 lg:h-full lg:overflow-y-auto [&>*]:shrink-0">
      {/* 1. Guardrail Intervention Banners */}
      <div className="space-y-3">
        {/* Safety Floor Banner */}
        {assessment?.safety_floor_triggered && (
          <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-800/80 shadow-[0_0_12px_rgba(239,68,68,0.08)] space-y-2">
            <div className="flex items-center justify-between text-red-300 font-bold">
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-red-400 shrink-0" />
                <span>Safety Floor Triggered</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-red-900/60 border border-red-700/60 text-red-200">
                Rule Level {alert.rule_level}
              </span>
            </div>

            <div className="text-zinc-300 font-sans text-xs leading-relaxed">
              {assessment.guardrail_audit_note ||
                'High-severity rule on critical asset prohibits automated downgrade or benign classification without human analyst review.'}
            </div>

            <div className="flex items-center gap-2 text-[11px] pt-1 border-t border-red-900/60">
              <span className="text-zinc-400">Model Proposal:</span>
              <span className="line-through text-zinc-500 font-mono">{assessment.raw_verdict} ({assessment.raw_severity})</span>
              <span className="text-zinc-600">→</span>
              <span className="text-red-300 font-bold font-mono">
                {assessment.effective_verdict} ({assessment.effective_severity})
              </span>
            </div>
          </div>
        )}

        {/* Abstention Banner */}
        {assessment?.abstention_triggered && (
          <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/80 shadow-[0_0_12px_rgba(245,158,11,0.06)] space-y-2">
            <div className="flex items-center justify-between text-amber-300 font-bold">
              <div className="flex items-center gap-2">
                <Clock className="size-4 text-amber-400 shrink-0" />
                <span>Abstention Triggered</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-amber-900/60 border border-amber-700/60 text-amber-200">
                {assessment.confidence_score !== null && assessment.confidence_score !== undefined && assessment.confidence_score < 0.6
                  ? 'Confidence < 60%'
                  : 'Policy Constraint / Guardrail'}
              </span>
            </div>

            <div className="text-zinc-300 font-sans text-xs leading-relaxed">
              {assessment.guardrail_audit_note ? (
                <span>{assessment.guardrail_audit_note}</span>
              ) : (
                <>
                  Confidence score{' '}
                  <strong className="text-amber-200 font-mono">
                    {assessment.confidence_score !== null && assessment.confidence_score !== undefined
                      ? `${Math.round(assessment.confidence_score * 100)}%`
                      : 'N/A'}
                  </strong>{' '}
                  falls below autonomous triage threshold or cited evidence requires human contextual validation. Automated binary decision withheld.
                </>
              )}
            </div>
          </div>
        )}

        {/* Prompt-Injection Intercept Warning */}
        {evidence_pack?.injection_suspect && (
          <div className="p-3.5 rounded-xl bg-fuchsia-950/40 border border-fuchsia-800/80 shadow-[0_0_12px_rgba(217,70,239,0.08)] space-y-2">
            <div className="flex items-center justify-between text-fuchsia-300 font-bold">
              <div className="flex items-center gap-2">
                <AlertTriangle className="size-4 text-fuchsia-400 shrink-0" />
                <span>Adversarial Delimiter Tokens Neutralized</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-fuchsia-900/60 border border-fuchsia-700/60 text-fuchsia-200">
                Sanitizer Intercept
              </span>
            </div>

            <div className="text-zinc-300 font-sans text-xs leading-relaxed">
              Untrusted commandline telemetry contained system override delimiter sequences. The telemetry was isolated inside read-only envelope structures before model evaluation.
            </div>
          </div>
        )}
      </div>

      {/* 2. Automated AI Assessment Card */}
      {assessment ? (
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3.5">
          <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2.5">
            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
              <Sparkles className="size-4 text-cyan-400" />
              <span>Model Assessment</span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-zinc-400">
              <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-cyan-300 font-mono">
                {assessment.model_name || 'Model unavailable'}
              </span>
              <span>{assessment.latency_ms || 0}ms</span>
            </div>
          </div>

          {/* Verdict & Severity Badges Grid */}
          <div className="grid grid-cols-2 gap-3 py-1">
            <div className="space-y-1">
              <span className="text-[10px] text-zinc-500 font-mono">EFFECTIVE VERDICT</span>
              <div>
                <VerdictBadge verdict={assessment.effective_verdict} />
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] text-zinc-500 font-mono">EFFECTIVE SEVERITY</span>
              <div>
                <SeverityBadge
                  severity={assessment.effective_severity}
                  safetyFloorUpgraded={assessment.safety_floor_triggered}
                />
              </div>
            </div>
          </div>

          {/* Confidence Meter */}
          <div className="space-y-1 pt-1">
            <p className="text-xs text-muted-foreground">Model confidence</p>
            <ConfidenceMeter score={assessment.confidence_score} />
          </div>

          {/* Full Explanation */}
          <div className="space-y-1.5 pt-1">
            <span className="text-xs text-muted-foreground">Model explanation</span>
            <div className="p-3 rounded-lg bg-zinc-900/70 border border-zinc-800 text-zinc-200 font-sans text-xs leading-relaxed">
              {assessment.explanation}
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2">
          <div className="flex items-center gap-2 text-zinc-300 font-semibold text-xs">
            <Clock className="size-4 text-amber-400" />
            <span>{isPending ? 'AI Triage Pending' : alert.status === 'NEEDS_MANUAL_TRIAGE' ? 'Manual Triage Required' : 'No Saved AI Assessment'}</span>
          </div>
          <p className="text-zinc-400 text-xs font-sans">
            {isPending ? 'AI is processing this alert. You can enter a manual disposition.' :
              alert.status === 'NEEDS_MANUAL_TRIAGE' ? 'Enter a manual disposition or retry AI triage.' :
                'This alert has no saved model assessment.'}
          </p>
        </div>
      )}

      {/* 3. Interactive Cited Evidence Key Pills */}
      {citationKeys.length > 0 && (
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
              <Link2 className="size-4 text-cyan-400" />
              <span>Evidence Citations</span>
            </div>
            <span className="text-xs text-muted-foreground">
              {validCitationKeys.length} available
            </span>
          </div>

          <div className="grid gap-2">
            {citationKeys.map((key) => {
              const isSelected = selectedCitationKey === key;
              const available = validCitationKeys.includes(key);
              const field = (key.split('.').at(-1) ?? key).replace(/([a-z])([A-Z])/g, '$1 $2').replaceAll('_', ' ');
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={isSelected}
                  disabled={!available}
                  onClick={() => onSelectCitationKey(key)}
                  className={`flex min-h-11 items-start gap-2 px-2.5 py-2 rounded-md text-left text-sm transition-colors disabled:cursor-default ${
                    isSelected
                      ? 'bg-cyan-950 text-cyan-200 border border-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.3)] ring-1 ring-cyan-400'
                      : 'bg-zinc-900 hover:bg-zinc-850 text-zinc-300 hover:text-white border border-zinc-800 hover:border-zinc-700'
                  }`}
                  title={`Highlight field "${key}" in evidence tree`}
                >
                  <FileCode className={`size-3 ${isSelected ? 'text-cyan-400' : 'text-zinc-500'}`} />
                  <span className="min-w-0">
                    <span className="block font-medium capitalize">{field}{!available && ' · unavailable'}</span>
                    <span className="block font-mono text-xs text-muted-foreground [overflow-wrap:anywhere]">{key}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Matched Few-Shot Feedback Exemplars */}
      {injected_exemplars && injected_exemplars.length > 0 && (
        <div className="surface p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
              <BookmarkCheck className="size-4 text-emerald-400" />
              <span>Exemplars Selected for This Assessment</span>
            </div>
            <span className="text-[10px] text-zinc-500">
              {injected_exemplars.length} selected
            </span>
          </div>

          <div className="space-y-2.5">
            {injected_exemplars.map((ex) => (
              <div
                key={ex.id}
                className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-300 font-bold font-mono">{ex.id}</span>
                    {ex.match_tier_support && <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
                        ex.match_tier_support === 'Tier 1'
                          ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60'
                          : 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
                      }`}
                    >
                      {ex.match_tier_support}:{' '}
                      {ex.match_tier_support === 'Tier 1' ? 'Exact Signature Match' : 'Asset Fallback'}
                    </span>}
                  </div>
                  <span className="text-[10px] text-zinc-500 font-mono">
                    {ex.match_hit_count} historical hits
                  </span>
                </div>

                <div className="text-[11px] text-zinc-400 font-mono">
                  Rule {ex.rule_id} • <span className="text-zinc-300 font-semibold">{ex.process_signature}</span>
                </div>

                {ex.match_tier_support === 'Tier 2' && (
                  <div className="p-2 rounded bg-amber-950/40 border border-amber-800/60 text-amber-300 text-[11px] font-mono flex items-center gap-1.5">
                    <AlertTriangle className="size-3 text-amber-400 shrink-0" />
                    <span>Caution: Verify command-line arguments and source IP similarity before applying this asset-tier fallback exemplar.</span>
                  </div>
                )}

                <div className="text-xs text-zinc-300 font-sans italic bg-zinc-950/60 p-2 rounded border border-zinc-850">
                  "{ex.rationale}"
                </div>

                <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono pt-1">
                  <span>{ex.is_active ? 'Active' : 'Revoked'}</span>
                  <div className="flex items-center gap-1.5">
                    <VerdictBadge verdict={ex.calibrated_verdict} />
                    <SeverityBadge severity={ex.calibrated_severity} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 5. 24-Hour Temporal Context (Correlated Alerts) */}
      {correlated_alerts && correlated_alerts.length > 0 && (
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
              <Activity className="size-4 text-cyan-400" />
              <span>24-Hour Correlated Host Alerts</span>
            </div>
            <span className="text-[10px] text-zinc-500">
              {correlated_alerts.length} historical hits
            </span>
          </div>

          <div className="space-y-2">
            {correlated_alerts.map((corr) => (
              <div
                key={corr.id ?? corr.wazuh_alert_id}
                className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/80 flex items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-0.5 min-w-0">
                  <div className="text-zinc-200 font-medium truncate font-sans text-xs">
                    {corr.rule_description}
                  </div>
                  <div className="text-[10px] text-zinc-500 font-mono flex items-center gap-2">
                    <span>Rule {corr.rule_id}</span>
                    <span>•</span>
                    <span>{new Date(corr.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {corr.verdict && <VerdictBadge verdict={corr.verdict} />}
                  {corr.severity && <SeverityBadge severity={corr.severity} />}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 6. Immutable Decision Audit Trail */}
      {decision_audit_trail && decision_audit_trail.length > 0 && (
        <section id="alert-decision-history" aria-label="Decision history" tabIndex={-1}
          className={`surface p-4 space-y-3 ${alert.status === 'CLOSED' ? 'order-first' : ''}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
              <History className="size-4 text-zinc-400" />
              <h3 className="text-sm">Decision history</h3>
            </div>
            <ShieldCheck className="size-4 text-emerald-400" />
          </div>

          <div className="space-y-2.5">
            {decision_audit_trail.map((aud) => (
              <div
                key={aud.id}
                ref={aud.id === savedAuditId ? savedAudit : undefined}
                data-audit-id={aud.id}
                className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800 space-y-1.5 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-zinc-300 font-bold">{aud.username ?? aud.user_id}</span>
                  <span className="text-[10px] text-zinc-500 font-mono">
                    {new Date(aud.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-200 font-semibold">
                    {aud.action_taken}
                  </span>
                  {aud.final_verdict && aud.final_severity && (
                    <span className="text-zinc-400 font-sans">Final {aud.final_verdict} ({aud.final_severity})</span>
                  )}
                </div>
                <p className="text-zinc-300 font-sans text-xs italic bg-zinc-950/70 p-2 rounded border border-zinc-850">
                  "{aud.rationale}"
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

