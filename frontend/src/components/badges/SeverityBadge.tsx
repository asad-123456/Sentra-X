import React from 'react';
import { ShieldAlert } from 'lucide-react';
import type { SeverityLevel } from '../../types/sentrax';

interface SeverityBadgeProps {
  severity: SeverityLevel;
  safetyFloorUpgraded?: boolean;
  className?: string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  safetyFloorUpgraded = false,
  className = '',
}) => {
  const styles: Record<SeverityLevel, { bg: string; border: string; text: string; dot: string }> = {
    CRITICAL: {
      bg: 'bg-red-950/25',
      border: 'border-red-500/40',
      text: 'text-red-300',
      dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]',
    },
    HIGH: {
      bg: 'bg-amber-950/25',
      border: 'border-amber-500/40',
      text: 'text-amber-300',
      dot: 'bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.4)]',
    },
    MEDIUM: {
      bg: 'bg-zinc-900',
      border: 'border-zinc-700/60',
      text: 'text-zinc-300',
      dot: 'bg-zinc-400',
    },
    LOW: {
      bg: 'bg-zinc-950',
      border: 'border-zinc-800',
      text: 'text-zinc-400',
      dot: 'bg-zinc-600',
    },
  };

  const style = styles[severity] || styles.MEDIUM;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-mono font-medium border whitespace-nowrap shrink-0 ${style.bg} ${style.border} ${style.text} ${className}`}
    >
      <span className={`size-1.5 rounded-full ${style.dot}`} />
      <span>{severity}</span>
      {safetyFloorUpgraded && (
        <span
          title="Upgraded by Safety Floor Policy"
          className="inline-flex items-center text-red-400 ml-0.5"
        >
          <ShieldAlert className="size-3" />
        </span>
      )}
    </span>
  );
};

