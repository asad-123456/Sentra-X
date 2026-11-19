import React from 'react';
import { ShieldCheck, AlertTriangle, TrendingUp, Lock } from 'lucide-react';
import type { EvaluationReport } from '../../types/sentrax';

interface ScorecardRibbonProps {
  report: EvaluationReport;
  isRunning: boolean;
}

export const ScorecardRibbon: React.FC<ScorecardRibbonProps> = ({ report, isRunning }) => {
  const formatRate = (rate: number | null) => rate === null ? 'Unavailable' : `${rate.toFixed(1)}%`;
  const baselineBypassed = report.adversarial_suite.filter((payload) => payload.baseline_bypassed).length;
  const sentraxBypassed = report.adversarial_suite.filter((payload) => payload.sentrax_bypassed).length;
  const f1 = report.comparative_metrics.find((metric) => metric.metric_name.includes('F1'));
  const safetyFloor = report.comparative_metrics.find((metric) => metric.metric_name.startsWith('Safety Floor'));

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Baseline Raw LLM Bypass Rate */}
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between hover:border-zinc-700/60 transition-all">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400 mb-2">
          <span>BASELINE RAW LLM BYPASS</span>
          <div className="size-6 rounded-md bg-red-950/40 border border-red-800/50 flex items-center justify-center text-red-400">
            <AlertTriangle className="size-3.5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className={`text-2xl font-bold font-mono tracking-tight text-red-400 ${isRunning ? 'animate-pulse' : ''}`}>
            {formatRate(report.baseline_bypass_rate)}
          </span>
          {report.baseline_bypass_rate !== null && (
            <span className="text-xs text-zinc-500 font-mono">{baselineBypassed} of {report.total_payloads} bypassed</span>
          )}
        </div>
        <div className="mt-3 pt-2.5 border-t border-zinc-900 text-[11px] text-zinc-500 leading-tight">
          Unreviewed dismissals in the raw model run.
        </div>
      </div>

      {/* 2. Sentra-X Pipeline Bypass Rate */}
      <div className="bg-zinc-950 border border-emerald-900/40 rounded-xl p-4 flex flex-col justify-between hover:border-emerald-800/60 transition-all relative overflow-hidden">
        <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-xl pointer-events-none" />
        <div className="flex items-center justify-between text-xs font-mono text-emerald-400 mb-2">
          <span>SENTRA-X PIPELINE BYPASS</span>
          <div className="size-6 rounded-md bg-emerald-950/60 border border-emerald-700/60 flex items-center justify-center text-emerald-400">
            <ShieldCheck className="size-3.5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className={`text-2xl font-bold font-mono tracking-tight text-emerald-400 ${isRunning ? 'animate-pulse' : ''}`}>
            {formatRate(report.sentrax_bypass_rate)}
          </span>
          <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-200">
            {report.result}
          </span>
        </div>
        <div className="mt-3 pt-2.5 border-t border-zinc-900 text-[11px] text-zinc-400 leading-tight">
          {report.sentrax_bypass_rate === null
            ? 'The guarded run did not complete every case.'
            : `${sentraxBypassed} of ${report.total_payloads} bypassed.`}
        </div>
      </div>

      {/* 3. Research Delta / F1 Improvement */}
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between hover:border-zinc-700/60 transition-all">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400 mb-2">
          <span>RESEARCH DELTA (F1)</span>
          <div className="size-6 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
            <TrendingUp className="size-3.5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono tracking-tight text-zinc-100">
            {report.result === 'inconclusive' ? 'Unavailable' : f1?.research_delta ?? 'Unavailable'}
          </span>
        </div>
        <div className="mt-3 pt-2.5 border-t border-zinc-900 text-[11px] text-zinc-500 leading-tight">
          Change in F1 from baseline to guarded triage.
        </div>
      </div>

      {/* 4. Safety Floor Enforcement Rate */}
      <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4 flex flex-col justify-between hover:border-zinc-700/60 transition-all">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400 mb-2">
          <span>SAFETY FLOOR</span>
          <div className="size-6 rounded-md bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
            <Lock className="size-3.5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold font-mono tracking-tight text-zinc-100">
            {report.result === 'inconclusive' ? 'Unavailable' : safetyFloor?.sentrax_value ?? 'Unavailable'}
          </span>
        </div>
        <div className="mt-3 pt-2.5 border-t border-zinc-900 text-[11px] text-zinc-500 leading-tight">
          Observed guardrail metric across evaluated cases.
        </div>
      </div>
    </div>
  );
};

