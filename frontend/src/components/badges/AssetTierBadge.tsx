import React from 'react';
import { Server, Database, Monitor, Globe } from 'lucide-react';
import type { AssetCriticalityTier } from '../../types/sentrax';

interface AssetTierBadgeProps {
  tier: AssetCriticalityTier;
  className?: string;
  showIcon?: boolean;
}

export const AssetTierBadge: React.FC<AssetTierBadgeProps> = ({
  tier,
  className = '',
  showIcon = true,
}) => {
  const config: Record<
    AssetCriticalityTier,
    { label: string; subLabel: string; bg: string; border: string; text: string; icon: React.ReactNode }
  > = {
    CRITICAL: {
      label: 'CRITICAL',
      subLabel: 'Crown Jewel',
      bg: 'bg-red-950/20',
      border: 'border-red-500/40',
      text: 'text-red-300',
      icon: <Database className="size-3 text-red-400" />,
    },
    HIGH: {
      label: 'HIGH',
      subLabel: 'Infrastructure',
      bg: 'bg-amber-950/20',
      border: 'border-amber-500/40',
      text: 'text-amber-300',
      icon: <Server className="size-3 text-amber-400" />,
    },
    MEDIUM: {
      label: 'MEDIUM',
      subLabel: 'Endpoint',
      bg: 'bg-zinc-900',
      border: 'border-zinc-700/60',
      text: 'text-zinc-300',
      icon: <Monitor className="size-3 text-zinc-400" />,
    },
    LOW: {
      label: 'LOW',
      subLabel: 'Isolated DMZ',
      bg: 'bg-zinc-950',
      border: 'border-zinc-800',
      text: 'text-zinc-400',
      icon: <Globe className="size-3 text-zinc-500" />,
    },
  };

  const current = config[tier] || config.MEDIUM;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono font-medium border whitespace-nowrap shrink-0 ${current.bg} ${current.border} ${current.text} ${className}`}
    >
      {showIcon && current.icon}
      <span>{current.label}</span>
      <span className="text-[10px] text-zinc-500 font-sans hidden sm:inline whitespace-nowrap">
        ({current.subLabel})
      </span>
    </span>
  );
};

