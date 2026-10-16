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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3.5">
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

  const totalOverrides = Math.round((summary.total_closed * summary.override_rate) / 100);
  const totalGuardrails =
    summary.severity_deltas.safety_floor_count + summary.severity_deltas.abstention_count;

  const kpis = [
    {
      label: 'TOTAL CLOSED DECISIONS',
      value: summary.total_closed.toLocaleString(),
      subtext: 'Immutable audit records',
      icon: FileCheck2,
      accent: 'text-zinc-100',
      badge: 'Archived',
      badgeColor: 'bg-zinc-900 text-zinc-400 border-zinc-800',
    },
    {
      label: 'AI AGREEMENT RATE',
      value: `${summary.agreement_rate.toFixed(1)}%`,
      subtext: `Cohen's κ = ${summary.cohens_kappa.toFixed(2)} (Substantial)`,
      icon: CheckCircle2,
      accent: 'text-emerald-400',
      badge: 'High Alignment',
      badgeColor: 'bg-emerald-950/80 text-emerald-300 border-emerald-800/60',
    },
    {
      label: 'ANALYST OVERRIDE RATE',
      value: `${summary.override_rate.toFixed(1)}%`,
      subtext: `${totalOverrides} total human overrides`,
      icon: Sliders,
      accent: 'text-cyan-400',
      badge: 'Calibrated',
      badgeColor: 'bg-cyan-950/80 text-cyan-300 border-cyan-800/60',
    },
    {
      label: 'ESCALATION & FALLBACK',
      value: `${(summary.escalated_rate + summary.manual_triage_rate).toFixed(1)}%`,
      subtext: `${summary.escalated_rate}% Escalated • ${summary.manual_triage_rate}% Manual`,
      icon: Flame,
      accent: 'text-amber-400',
      badge: 'Tier-2 Review',
      badgeColor: 'bg-amber-950/80 text-amber-300 border-amber-800/60',
    },
    {
      label: 'GUARDRAIL INTERVENTIONS',
      value: totalGuardrails.toLocaleString(),
      subtext: `${summary.severity_deltas.safety_floor_count} Safety Floor • ${summary.severity_deltas.abstention_count} Abstentions`,
      icon: ShieldAlert,
      accent: 'text-red-400',
      badge: 'Active',
      badgeColor: 'bg-red-950/80 text-red-300 border-red-800/60',
    },
    {
      label: 'MEAN TRIAGE LATENCY',
      value: `${summary.mean_latency_seconds.toFixed(1)}s`,
      subtext: 'Target ≤ 8.0s (SLA Compliant)',
      icon: Clock,
      accent: 'text-zinc-200',
      badge: 'Real-time',
      badgeColor: 'bg-zinc-900 text-zinc-300 border-zinc-800',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3.5">
      {kpis.map((kpi, idx) => {
        const Icon = kpi.icon;
        return (
          <div
            key={idx}
            className="p-4 rounded-xl bg-zinc-950 border border-zinc-850 hover:border-zinc-750 transition-all space-y-2 flex flex-col justify-between"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-mono text-zinc-500 tracking-wider truncate">
                {kpi.label}
              </span>
              <Icon className="size-3.5 text-zinc-500 shrink-0" />
            </div>

            <div className="space-y-0.5">
              <div className={`text-xl font-bold font-mono tracking-tight ${kpi.accent}`}>
                {kpi.value}
              </div>
              <div className="text-[11px] text-zinc-400 font-sans truncate" title={kpi.subtext}>
                {kpi.subtext}
              </div>
            </div>

            <div className="pt-1.5 border-t border-zinc-900/80 flex items-center justify-between">
              <span
                className={`text-[9px] font-mono font-medium px-1.5 py-0.5 rounded border ${kpi.badgeColor}`}
              >
                {kpi.badge}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

