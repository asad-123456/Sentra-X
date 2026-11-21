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

  const percent = (value: number | null) => value == null ? '—' : `${value.toFixed(1)}%`;

  const kpis = [
    {
      label: 'CLOSURE DECISIONS',
      value: summary.total_closed.toLocaleString(),
      subtext: 'Recorded in the audit trail',
      icon: FileCheck2,
      accent: 'text-zinc-100',
    },
    {
      label: 'AI AGREEMENT RATE',
      value: percent(summary.agreement_rate),
      subtext: `${summary.comparison_count} binary verdict comparisons`,
      icon: CheckCircle2,
      accent: 'text-emerald-400',
    },
    {
      label: 'ANALYST OVERRIDE RATE',
      value: percent(summary.override_rate),
      subtext: `${summary.overridden_count} override${summary.overridden_count === 1 ? '' : 's'} among approvals and overrides`,
      icon: Sliders,
      accent: 'text-cyan-400',
    },
    {
      label: 'CURRENT ESCALATION & FALLBACK',
      value: `${percent(summary.escalated_rate)} / ${percent(summary.manual_triage_rate)}`,
      subtext: 'Escalated / manual triage among alerts received',
      icon: Flame,
      accent: 'text-amber-400',
    },
    {
      label: 'GUARDRAIL INTERVENTIONS',
      value: summary.guardrail_interventions.toLocaleString(),
      subtext: 'Assessments with a safety floor or abstention',
      icon: ShieldAlert,
      accent: 'text-red-400',
    },
    {
      label: 'MEAN INFERENCE LATENCY',
      value: summary.mean_latency_seconds == null ? '—' : `${summary.mean_latency_seconds.toFixed(1)}s`,
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
            className="p-4 rounded-xl bg-zinc-950 border border-zinc-850 hover:border-zinc-750 transition-all space-y-2 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-mono text-zinc-400 tracking-wider">
                {kpi.label}
              </span>
              <Icon className="size-3.5 text-zinc-500 shrink-0" />
            </div>

            <div className="space-y-0.5">
              <div className={`text-xl font-bold font-mono tracking-tight ${kpi.accent}`}>
                {kpi.value}
              </div>
              <div className="text-[11px] text-zinc-400 font-sans">
                {kpi.subtext}
              </div>
            </div>

          </div>
        );
      })}
    </div>
  );
};

