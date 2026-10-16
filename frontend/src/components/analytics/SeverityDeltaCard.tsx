import React from 'react';
import type { AnalyticsSummary } from '../../types/sentrax';
import {
  ShieldAlert,
  Clock,
  AlertTriangle,
  GitCompare,
  PieChart,
} from 'lucide-react';

interface SeverityDeltaCardProps {
  summary: AnalyticsSummary;
  isLoading?: boolean;
}

export const SeverityDeltaCard: React.FC<SeverityDeltaCardProps> = ({
  summary,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-5 rounded-xl bg-zinc-950 border border-zinc-850 h-[340px] animate-pulse" />
        <div className="p-5 rounded-xl bg-zinc-950 border border-zinc-850 h-[340px] animate-pulse" />
      </div>
    );
  }

  const { confusion_matrix, override_root_causes, severity_deltas } = summary;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* 1. Agreement Confusion Matrix & Statistical Quality */}
      <div className="p-5 rounded-xl bg-zinc-950 border border-zinc-850 space-y-4 flex flex-col justify-between">
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitCompare className="size-4 text-cyan-400" />
              <span className="text-xs font-mono font-bold text-zinc-100 uppercase tracking-wider">
                AI vs. Human Agreement Matrix
              </span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
              Cohen's κ = {summary.cohens_kappa.toFixed(2)}
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            Cross-tabulation of autonomous AI triage proposals against final human supervisor decisions
          </p>
        </div>

        {/* 2x2 Matrix */}
        <div className="space-y-2 font-mono text-xs">
          <div className="grid grid-cols-2 gap-2 text-center">
            {/* Top Left: Agreed TP */}
            <div className="p-3.5 rounded-lg bg-emerald-950/40 border border-emerald-800/60 space-y-1">
              <div className="flex items-center justify-between text-[10px] text-emerald-400 font-bold">
                <span>AGREED TRUE POSITIVE</span>
                <span>TP ➔ TP</span>
              </div>
              <div className="text-2xl font-bold text-emerald-300">
                {confusion_matrix.tp_tp}
              </div>
              <div className="text-[10px] text-zinc-400 font-sans">
                AI proposed threat, analyst approved
              </div>
            </div>

            {/* Top Right: AI TP, Human FP (Override) */}
            <div className="p-3.5 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-1">
              <div className="flex items-center justify-between text-[10px] text-cyan-400 font-bold">
                <span>BENIGN OVERRIDE</span>
                <span>TP ➔ FP</span>
              </div>
              <div className="text-2xl font-bold text-cyan-300">
                {confusion_matrix.tp_fp_overridden}
              </div>
              <div className="text-[10px] text-zinc-400 font-sans">
                AI proposed threat, analyst marked benign
              </div>
            </div>

            {/* Bottom Left: AI FP, Human TP (Override / FN Rescue) */}
            <div className="p-3.5 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-1">
              <div className="flex items-center justify-between text-[10px] text-amber-400 font-bold">
                <span>THREAT RESCUE</span>
                <span>FP ➔ TP</span>
              </div>
              <div className="text-2xl font-bold text-amber-300">
                {confusion_matrix.fp_tp_overridden}
              </div>
              <div className="text-[10px] text-zinc-400 font-sans">
                AI proposed benign, analyst flagged threat
              </div>
            </div>

            {/* Bottom Right: Agreed FP */}
            <div className="p-3.5 rounded-lg bg-zinc-900/40 border border-zinc-850 space-y-1">
              <div className="flex items-center justify-between text-[10px] text-zinc-400 font-bold">
                <span>AGREED FALSE POSITIVE</span>
                <span>FP ➔ FP</span>
              </div>
              <div className="text-2xl font-bold text-zinc-200">
                {confusion_matrix.fp_fp}
              </div>
              <div className="text-[10px] text-zinc-500 font-sans">
                AI proposed benign noise, analyst approved
              </div>
            </div>
          </div>
        </div>

        {/* Statistical Scorecards */}
        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-900 text-center font-mono">
          <div className="p-2 rounded bg-zinc-900/40 border border-zinc-850">
            <span className="text-[10px] text-zinc-500 uppercase">Precision</span>
            <div className="text-sm font-bold text-zinc-200">{summary.precision.toFixed(1)}%</div>
          </div>
          <div className="p-2 rounded bg-zinc-900/40 border border-zinc-850">
            <span className="text-[10px] text-zinc-500 uppercase">Recall</span>
            <div className="text-sm font-bold text-zinc-200">{summary.recall.toFixed(1)}%</div>
          </div>
          <div className="p-2 rounded bg-zinc-900/40 border border-zinc-850">
            <span className="text-[10px] text-zinc-500 uppercase">Accuracy</span>
            <div className="text-sm font-bold text-zinc-200">{summary.accuracy.toFixed(1)}%</div>
          </div>
        </div>
      </div>

      {/* 2. Guardrail Trigger Breakdown & Override Root Causes */}
      <div className="p-5 rounded-xl bg-zinc-950 border border-zinc-850 space-y-4 flex flex-col justify-between">
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PieChart className="size-4 text-cyan-400" />
              <span className="text-xs font-mono font-bold text-zinc-100 uppercase tracking-wider">
                Guardrail Interventions &amp; Override Drivers
              </span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
              Policy Filters
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            Safety rule triggers and primary justifications cited by analysts during override submissions
          </p>
        </div>

        {/* Guardrail Metrics Strip */}
        <div className="grid grid-cols-3 gap-2 font-mono">
          <div className="p-2.5 rounded-lg bg-red-950/30 border border-red-900/60 space-y-0.5">
            <div className="flex items-center gap-1.5 text-red-400 text-[10px] font-bold">
              <ShieldAlert className="size-3" />
              <span>Safety Floor</span>
            </div>
            <div className="text-lg font-bold text-red-200">{severity_deltas.safety_floor_count}</div>
            <div className="text-[9px] text-zinc-400 font-sans">Rule Level ≥ 10/12</div>
          </div>

          <div className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-900/60 space-y-0.5">
            <div className="flex items-center gap-1.5 text-amber-400 text-[10px] font-bold">
              <Clock className="size-3" />
              <span>Abstentions</span>
            </div>
            <div className="text-lg font-bold text-amber-200">{severity_deltas.abstention_count}</div>
            <div className="text-[9px] text-zinc-400 font-sans">Confidence &lt; 60%</div>
          </div>

          <div className="p-2.5 rounded-lg bg-fuchsia-950/30 border border-fuchsia-900/60 space-y-0.5">
            <div className="flex items-center gap-1.5 text-fuchsia-400 text-[10px] font-bold">
              <AlertTriangle className="size-3" />
              <span>Sanitizations</span>
            </div>
            <div className="text-lg font-bold text-fuchsia-200">
              {severity_deltas.injection_intercept_count}
            </div>
            <div className="text-[9px] text-zinc-400 font-sans">Delimiter blocks</div>
          </div>
        </div>

        {/* Override Root Causes Bars */}
        <div className="space-y-2 pt-1">
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block">
            Primary Analyst Override Justifications
          </span>
          <div className="space-y-2">
            {override_root_causes.map((rc, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-zinc-300 truncate max-w-[260px]">{rc.cause}</span>
                  <span className="text-zinc-500 shrink-0">
                    {rc.count} ({rc.percentage}%)
                  </span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-zinc-900 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-cyan-500 transition-all duration-300"
                    style={{ width: `${rc.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Severity Shifts Row */}
        <div className="pt-2 border-t border-zinc-900 flex items-center justify-between text-[11px] font-mono text-zinc-400">
          <span>Human Severity Upgrades:</span>
          <div className="flex items-center gap-3 text-zinc-300">
            <span>Low ➔ Critical: <strong className="text-red-400">{severity_deltas.low_to_critical}</strong></span>
            <span>•</span>
            <span>Medium ➔ High: <strong className="text-amber-400">{severity_deltas.medium_to_high}</strong></span>
            <span>•</span>
            <span>High ➔ Critical: <strong className="text-red-400">{severity_deltas.high_to_critical}</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
};

