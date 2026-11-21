import React from 'react';
import type { AnalyticsSummary } from '../../types/sentrax';
import {
  CheckCircle2,
  Sliders,
  ShieldAlert,
  Clock,
  Flame,
  FileCheck2,
} from 'lucide-react';

interface KpiSummaryGridProps {
  summary: AnalyticsSummary;
  isLoading?: boolean;
}

export const KpiSummaryGrid: React.FC<KpiSummaryGridProps> = ({ summary, isLoading = false }) => {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6 gap-3.5">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="p-4 rounded-xl bg-zinc-950 border border-zinc-850 animate-pulse space-y-2.5"
          >
            <div className="h-3 w-20 bg-zinc-850 rounded" />
            <div className="h-6 w-16 bg-zinc-800 rounded" />
            <div className="h-2.5 w-24 bg-zinc-850 rounded" />
          </div>
        ))}
      </div>
    );
  }

  const percent = (value: number | null) => value == null ? 'Unavailable' : `${value.toFixed(1)}%`;
  const overrideTotal = summary.approved_count == null ? null : summary.approved_count + summary.overridden_count;
  const agreements = summary.confusion_matrix.tp_tp + summary.confusion_matrix.fp_fp;

  const kpis = [
    {
      label: 'Closure decisions',
      value: summary.total_closed.toLocaleString(),
      subtext: 'Recorded in the audit trail',
      icon: FileCheck2,
      accent: 'text-zinc-100',
    },
    {
      label: 'AI agreement rate',
      value: summary.agreement_rate == null ? 'No comparable decisions' : percent(summary.agreement_rate),
      subtext: `${agreements} agreements across ${summary.comparison_count} binary verdict comparisons`,
      icon: CheckCircle2,
      accent: 'text-emerald-400',
    },
    {
      label: 'Analyst override rate',
      value: summary.override_rate == null ? 'No approvals or overrides' : percent(summary.override_rate),
      subtext: `${summary.overridden_count} overrides${overrideTotal === null ? ' among approvals and overrides' : ` across ${overrideTotal} approvals and overrides`}`,
      icon: Sliders,
      accent: 'text-cyan-400',
    },
    {
      label: 'Current escalation and fallback',
      value: summary.escalated_rate == null && summary.manual_triage_rate == null
        ? 'No alerts received' : `${percent(summary.escalated_rate)} / ${percent(summary.manual_triage_rate)}`,
      subtext: summary.escalation_count == null || summary.manual_fallback_count == null
        ? 'Escalated / manual triage among alerts received'
        : `${summary.escalation_count} escalated / ${summary.manual_fallback_count} in manual triage among alerts received`,
      icon: Flame,
      accent: 'text-amber-400',
    },
    {
      label: 'Guardrail interventions',
      value: summary.guardrail_interventions.toLocaleString(),
      subtext: 'Assessments with a safety floor or abstention',
      icon: ShieldAlert,
      accent: 'text-red-400',
    },
    {
      label: 'Mean inference latency',
      value: summary.mean_latency_seconds == null ? 'No recorded latency' : `${summary.mean_latency_seconds.toFixed(1)}s`,
      subtext: 'Recorded model call latency',
      icon: Clock,
      accent: 'text-zinc-200',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6 gap-3.5">
      {kpis.map((kpi, idx) => {
        const Icon = kpi.icon;
        return (
          <div
            key={idx}
            className="surface p-4 space-y-2 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                {kpi.label}
              </span>
              <Icon className="size-3.5 text-zinc-500 shrink-0" />
            </div>

            <div className="space-y-0.5">
              <div className={`text-lg font-semibold tabular-nums tracking-tight ${/\d/.test(kpi.value) ? kpi.accent : 'text-foreground'}`}>
                {kpi.value}
              </div>
              <div className="text-xs text-muted-foreground">
                {kpi.subtext}
              </div>
            </div>

          </div>
        );
      })}
    </div>
  );
};

