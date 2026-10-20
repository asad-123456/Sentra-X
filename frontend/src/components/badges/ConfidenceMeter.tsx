import React from 'react';

interface ConfidenceMeterProps {
  score?: number | null; // 0.0 to 1.0 or 0 to 100
  className?: string;
  showAbstentionWarning?: boolean;
}

export const ConfidenceMeter: React.FC<ConfidenceMeterProps> = ({
  score,
  className = '',
  showAbstentionWarning = true,
}) => {
  if (score === null || score === undefined) {
    return (
      <div className={`inline-flex items-center gap-1.5 whitespace-nowrap text-zinc-600 font-mono text-xs ${className}`}>
        <span>—</span>
      </div>
    );
  }

  const normalized = score > 1 ? score / 100 : score;
  const percentage = Math.round(normalized * 100);
  const isBelowThreshold = normalized < 0.60;

  return (
    <div className={`inline-flex items-center gap-2 whitespace-nowrap shrink-0 ${className}`}>
      {/* Segmented Monochrome Bar */}
      <div className="w-14 h-2 bg-zinc-900 border border-zinc-800 rounded-full overflow-hidden flex items-center p-0.5 shrink-0">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isBelowThreshold
              ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]'
              : 'bg-zinc-200'
          }`}
          style={{ width: `${Math.max(8, percentage)}%` }}
        />
      </div>

      {/* Percentage Text with Tabular Alignment */}
      <span
        className={`w-8 font-mono text-xs font-semibold tabular-nums text-right shrink-0 ${
          isBelowThreshold ? 'text-amber-400' : 'text-zinc-200'
        }`}
      >
        {percentage}%
      </span>

      {/* Abstention Marker Indicator (<60%) */}
      {isBelowThreshold && showAbstentionWarning && (
        <span
          title="Confidence below 60% abstention threshold"
          className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-500/30 text-amber-300 whitespace-nowrap shrink-0"
        >
          ABSTAIN
        </span>
      )}
    </div>
  );
};

