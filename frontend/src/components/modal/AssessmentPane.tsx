import React from 'react';
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
}

export const AssessmentPane: React.FC<AssessmentPaneProps> = ({
  alertDetail,
  selectedCitationKey,
  onSelectCitationKey,
}) => {
  const { alert, assessment, evidence_pack, injected_exemplars, correlated_alerts, decision_audit_trail } = alertDetail;

  return (
    <div className="h-full overflow-y-auto p-5 space-y-6 text-zinc-100 font-mono text-xs pr-4 custom-scrollbar">
      {/* 1. Guardrail Intervention Banners */}
      <div className="space-y-3">
        {/* Safety Floor Banner */}
        {assessment.safety_floor_triggered && (
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
        {assessment.abstention_triggered && (
          <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/80 shadow-[0_0_12px_rgba(245,158,11,0.06)] space-y-2">
            <div className="flex items-center justify-between text-amber-300 font-bold">
              <div className="flex items-center gap-2">
                <Clock className="size-4 text-amber-400 shrink-0" />
                <span>Abstention Triggered</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-amber-900/60 border border-amber-700/60 text-amber-200">
                Threshold &lt; 60%
              </span>
            </div>

            <div className="text-zinc-300 font-sans text-xs leading-relaxed">
              Confidence score{' '}
              <strong className="text-amber-200 font-mono">
                {assessment.confidence_score !== null && assessment.confidence_score !== undefined
                  ? `${Math.round(assessment.confidence_score * 100)}%`
                  : 'N/A'}
              </strong>{' '}
              falls below autonomous triage threshold or cited evidence requires human contextual validation. Automated binary decision withheld.
            </div>
          </div>
        )}

        {/* Prompt-Injection Intercept Warning */}
        {evidence_pack.injection_suspect && (
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
      <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3.5">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2.5">
          <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
            <Sparkles className="size-4 text-cyan-400" />
            <span>Model Assessment</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-zinc-400">
            <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-cyan-300 font-mono">
              {assessment.model_name}
            </span>
            <span>{assessment.latency_ms}ms</span>
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
          <div className="flex items-center justify-between text-[10px] text-zinc-500">
            <span>MODEL CONFIDENCE</span>
            <span className="text-zinc-400">
              {assessment.confidence_score !== null && assessment.confidence_score !== undefined
                ? `${Math.round(assessment.confidence_score * 100)}%`
                : 'Undetermined'}
            </span>
          </div>
          <ConfidenceMeter score={assessment.confidence_score} />
        </div>

        {/* Full Explanation */}
        <div className="space-y-1.5 pt-1">
          <span className="text-[10px] text-zinc-500 font-mono">ANALYST EXPLANATION</span>
          <div className="p-3 rounded-lg bg-zinc-900/70 border border-zinc-800 text-zinc-200 font-sans text-xs leading-relaxed">
            {assessment.explanation}
          </div>
        </div>
      </div>

      {/* 3. Interactive Cited Evidence Key Pills */}
      <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
            <Link2 className="size-4 text-cyan-400" />
            <span>Evidence Citations</span>
          </div>
          <span className="text-[10px] text-zinc-500">
            {assessment.cited_evidence_keys.length} verified fields
          </span>
        </div>

        <p className="text-[11px] text-zinc-400 font-sans">
          Click any citation key below to immediately scroll and highlight its verified telemetry path in the evidence tree:
        </p>

        <div className="flex flex-wrap gap-2 pt-1">
          {assessment.cited_evidence_keys.map((key) => {
            const isSelected = selectedCitationKey === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => onSelectCitationKey(key)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-cyan-950 text-cyan-200 border border-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.3)] ring-1 ring-cyan-400'
                    : 'bg-zinc-900 hover:bg-zinc-850 text-zinc-300 hover:text-white border border-zinc-800 hover:border-zinc-700'
                }`}
                title={`Highlight field "${key}" in evidence tree`}
              >
                <FileCode className={`size-3 ${isSelected ? 'text-cyan-400' : 'text-zinc-500'}`} />
                <span className="truncate max-w-[280px]">{key}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 4. Matched Few-Shot Feedback Exemplars */}
      {injected_exemplars && injected_exemplars.length > 0 && (
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
              <BookmarkCheck className="size-4 text-emerald-400" />
              <span>Matched Few-Shot Calibration Exemplars</span>
            </div>
            <span className="text-[10px] text-zinc-500">
              {injected_exemplars.length} active injected
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
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
                        ex.match_tier_support === 'Tier 1'
                          ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60'
                          : 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
                      }`}
                    >
                      {ex.match_tier_support}:{' '}
                      {ex.match_tier_support === 'Tier 1' ? 'Exact Signature Match' : 'Asset Fallback'}
                    </span>
                  </div>
                  <span className="text-[10px] text-zinc-500 font-mono">
                    {ex.match_hit_count} historical hits
                  </span>
                </div>

                <div className="text-[11px] text-zinc-400 font-mono">
                  Rule {ex.rule_id} • <span className="text-zinc-300 font-semibold">{ex.process_signature}</span>
                </div>

                <div className="text-xs text-zinc-300 font-sans italic bg-zinc-950/60 p-2 rounded border border-zinc-850">
                  "{ex.rationale}"
                </div>

                <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono pt-1">
                  <span>Author: {ex.created_by}</span>
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
                key={corr.id}
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
                  <VerdictBadge verdict={corr.verdict} />
                  <SeverityBadge severity={corr.severity} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 6. Immutable Decision Audit Trail */}
      {decision_audit_trail && decision_audit_trail.length > 0 && (
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-zinc-200 font-semibold text-xs">
              <History className="size-4 text-zinc-400" />
              <span>Immutable Decision Audit Trail</span>
            </div>
            <ShieldCheck className="size-4 text-emerald-400" />
          </div>

          <div className="space-y-2.5">
            {decision_audit_trail.map((aud) => (
              <div
                key={aud.id}
                className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800 space-y-1.5 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-zinc-300 font-bold">{aud.username}</span>
                  <span className="text-[10px] text-zinc-500 font-mono">
                    {new Date(aud.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-200 font-semibold">
                    {aud.action_taken}
                  </span>
                  <span className="text-zinc-500 font-sans">→ Final: {aud.final_verdict} ({aud.final_severity})</span>
                </div>
                <p className="text-zinc-300 font-sans text-xs italic bg-zinc-950/70 p-2 rounded border border-zinc-850">
                  "{aud.rationale}"
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

