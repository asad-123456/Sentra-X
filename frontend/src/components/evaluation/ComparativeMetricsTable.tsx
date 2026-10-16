import React from 'react';
import { CheckCircle2, XCircle, ArrowUpRight } from 'lucide-react';
import type { BenchmarkComparativeScorecard } from '../../types/sentrax';

interface ComparativeMetricsTableProps {
  metrics: BenchmarkComparativeScorecard[];
}

export const ComparativeMetricsTable: React.FC<ComparativeMetricsTableProps> = ({ metrics }) => {
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="p-4 border-b border-zinc-800/80 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold font-mono text-zinc-100">
            Comparative Evaluation Scorecard
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Side-by-side performance verification of raw zero-shot LLM versus the fully guarded pipeline
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-zinc-400">Target Standard:</span>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-700/60 text-emerald-300">
            0.0% Bypass
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="bg-zinc-900/60 text-zinc-400 font-mono text-[11px] uppercase tracking-wider border-b border-zinc-800">
              <th className="py-3 px-4">Evaluation Dimension</th>
              <th className="py-3 px-4">Baseline Raw LLM (Zero-Shot)</th>
              <th className="py-3 px-4">Sentra-X Pipeline</th>
              <th className="py-3 px-4">Research Delta</th>
              <th className="py-3 px-4 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 font-sans">
            {metrics.map((item, idx) => (
              <tr key={idx} className="hover:bg-zinc-900/30 transition-colors">
                <td className="py-3.5 px-4 font-mono font-medium text-zinc-200">
                  {item.metric_name}
                </td>
                <td className="py-3.5 px-4 font-mono text-zinc-400">
                  <span className="text-red-400/90">{item.baseline_value}</span>
                </td>
                <td className="py-3.5 px-4 font-mono text-zinc-200">
                  <span className="text-emerald-400 font-semibold">{item.sentrax_value}</span>
                </td>
                <td className="py-3.5 px-4 font-mono text-zinc-300">
                  <div className="flex items-center gap-1.5">
                    <ArrowUpRight className="size-3 text-emerald-400 shrink-0" />
                    <span className="text-zinc-300">{item.research_delta}</span>
                  </div>
                </td>
                <td className="py-3.5 px-4 text-right">
                  {item.is_target_met ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/50 border border-emerald-800/60 text-emerald-300">
                      <CheckCircle2 className="size-3" />
                      Target Met
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-red-950/50 border border-red-800/60 text-red-300">
                      <XCircle className="size-3" />
                      Unmet
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

