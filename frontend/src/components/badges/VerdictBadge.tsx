import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle, RefreshCw } from 'lucide-react';
import type { AIVerdict } from '../../types/sentrax';

interface VerdictBadgeProps {
  verdict: AIVerdict | 'NEEDS_MANUAL_TRIAGE';
  className?: string;
}

export const VerdictBadge: React.FC<VerdictBadgeProps> = ({ verdict, className = '' }) => {
  switch (verdict) {
    case 'TRUE_POSITIVE':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-950/25 border border-emerald-500/40 text-emerald-300 font-mono whitespace-nowrap shrink-0 ${className}`}
        >
          <CheckCircle2 className="size-3 text-emerald-400 shrink-0" />
          <span>TRUE POSITIVE</span>
        </span>
      );
    case 'FALSE_POSITIVE':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-zinc-900 border border-zinc-700/60 text-zinc-300 font-mono whitespace-nowrap shrink-0 ${className}`}
        >
          <XCircle className="size-3 text-zinc-400 shrink-0" />
          <span>FALSE POSITIVE</span>
        </span>
      );
    case 'NEEDS_ANALYST_REVIEW':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-amber-950/25 border border-amber-500/40 text-amber-300 font-mono whitespace-nowrap shrink-0 ${className}`}
        >
          <AlertTriangle className="size-3 text-amber-400 shrink-0" />
          <span>NEEDS REVIEW</span>
        </span>
      );
    case 'NEEDS_MANUAL_TRIAGE':
    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-purple-950/25 border border-purple-500/40 text-purple-300 font-mono whitespace-nowrap shrink-0 ${className}`}
        >
          <RefreshCw className="size-3 text-purple-400 shrink-0" />
          <span>MANUAL TRIAGE</span>
        </span>
      );
  }
};

