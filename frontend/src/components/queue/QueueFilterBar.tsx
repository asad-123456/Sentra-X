import React from 'react';
import type { QueueTab, GuardrailFilter, QueueCounts } from '../../types/sentrax';
import { Search, X, RotateCcw, AlertTriangle, ShieldCheck, Flame } from 'lucide-react';

interface QueueFilterBarProps {
  currentTab: QueueTab;
  onTabChange: (tab: QueueTab) => void;
  subStatus: string;
  onSubStatusChange: (subStatus: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
  severity: string;
  onSeverityChange: (severity: string) => void;
  guardrail: GuardrailFilter;
  onGuardrailChange: (guardrail: GuardrailFilter) => void;
  assetTier: string;
  onAssetTierChange: (assetTier: string) => void;
  counts: QueueCounts;
  onResetFilters: () => void;
  hasActiveFilters: boolean;
}

export const QueueFilterBar: React.FC<QueueFilterBarProps> = ({
  currentTab,
  onTabChange,
  subStatus,
  onSubStatusChange,
  search,
  onSearchChange,
  severity,
  onSeverityChange,
  guardrail,
  onGuardrailChange,
  assetTier,
  onAssetTierChange,
  counts,
  onResetFilters,
  hasActiveFilters,
}) => {
  return (
    <div className="space-y-3 bg-zinc-950 border border-zinc-800/80 rounded-xl p-3.5 shadow-sm">
      {/* Primary Queue Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-900 pb-3">
        <div className="flex items-center gap-1.5 p-1 bg-zinc-900/60 rounded-lg border border-zinc-800/60">
          <button
            type="button"
            onClick={() => onTabChange('awaiting')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-colors ${
              currentTab === 'awaiting'
                ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/60'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <span>Awaiting Review</span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                currentTab === 'awaiting'
                  ? 'bg-zinc-700 text-zinc-100'
                  : 'bg-zinc-800/80 text-zinc-400'
              }`}
            >
              {counts.awaiting}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange('escalated')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-colors ${
              currentTab === 'escalated'
                ? 'bg-amber-950/60 text-amber-200 border border-amber-800/60'
                : 'text-zinc-400 hover:text-amber-300 hover:bg-zinc-800/40'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <Flame className="size-3 text-amber-400" />
              <span>Escalated</span>
            </span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                counts.escalated > 0
                  ? 'bg-amber-900/60 text-amber-300 border border-amber-700/50'
                  : 'bg-zinc-800/80 text-zinc-400'
              }`}
            >
              {counts.escalated}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange('closed')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-colors ${
              currentTab === 'closed'
                ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/60'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="size-3 text-zinc-400" />
              <span>Closed Audit Log</span>
            </span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                currentTab === 'closed'
                  ? 'bg-zinc-700 text-zinc-100'
                  : 'bg-zinc-800/80 text-zinc-400'
              }`}
            >
              {counts.closed}
            </span>
          </button>
        </div>

        {/* Sub-status filter for Awaiting Review */}
        {currentTab === 'awaiting' && (
          <div className="flex items-center gap-1 text-xs font-mono">
            <span className="text-zinc-500 mr-1 text-[11px]">SCOPE:</span>
            <button
              type="button"
              onClick={() => onSubStatusChange('ALL')}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${
                subStatus === 'ALL'
                  ? 'bg-zinc-800 text-zinc-100 font-semibold border border-zinc-700'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              All Actionable ({counts.awaiting})
            </button>
            <button
              type="button"
              onClick={() => onSubStatusChange('AWAITING_ANALYST')}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${
                subStatus === 'AWAITING_ANALYST'
                  ? 'bg-zinc-800 text-zinc-100 font-semibold border border-zinc-700'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Awaiting Review ({counts.awaitingAnalystCount})
            </button>
            <button
              type="button"
              onClick={() => onSubStatusChange('NEEDS_MANUAL_TRIAGE')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors ${
                subStatus === 'NEEDS_MANUAL_TRIAGE'
                  ? 'bg-purple-950/70 text-purple-200 font-semibold border border-purple-800/60'
                  : 'text-purple-400 hover:text-purple-200'
              }`}
            >
              <AlertTriangle className="size-3 text-purple-400" />
              <span>Manual Triage Required ({counts.needsManualTriageCount})</span>
            </button>
          </div>
        )}
      </div>

      {/* Filter and Search Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by rule, hostname, IP, or alert ID..."
            className="w-full bg-zinc-900/80 border border-zinc-800 rounded-lg pl-9 pr-8 py-1.5 text-xs font-mono text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600 transition-colors"
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 p-0.5"
              title="Clear search"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>

        {/* Severity Selector */}
        <div className="flex items-center gap-1.5 text-xs font-mono">
          <span className="text-zinc-500 text-[11px] hidden sm:inline">SEVERITY:</span>
          <select
            value={severity}
            onChange={(e) => onSeverityChange(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 font-mono focus:outline-none focus:border-zinc-700 cursor-pointer"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical (12–15)</option>
            <option value="HIGH">High (8–11)</option>
            <option value="MEDIUM">Medium (4–7)</option>
            <option value="LOW">Low (0–3)</option>
          </select>
        </div>

        {/* Guardrail Selector */}
        <div className="flex items-center gap-1.5 text-xs font-mono">
          <span className="text-zinc-500 text-[11px] hidden sm:inline">GUARDRAILS:</span>
          <select
            value={guardrail}
            onChange={(e) => onGuardrailChange(e.target.value as GuardrailFilter)}
            className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 font-mono focus:outline-none focus:border-zinc-700 cursor-pointer"
          >
            <option value="ALL">All Guardrail States</option>
            <option value="SAFETY_FLOOR">Safety Floor Enforced</option>
            <option value="ABSTENTION">Abstention Flagged</option>
            <option value="INJECTION_SUSPECT">Injection Intercept</option>
            <option value="MANUAL_TRIAGE">Manual Triage Required</option>
          </select>
        </div>

        {/* Asset Tier Selector */}
        <div className="flex items-center gap-1.5 text-xs font-mono">
          <span className="text-zinc-500 text-[11px] hidden sm:inline">ASSET TIER:</span>
          <select
            value={assetTier}
            onChange={(e) => onAssetTierChange(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 font-mono focus:outline-none focus:border-zinc-700 cursor-pointer"
          >
            <option value="ALL">All Asset Tiers</option>
            <option value="CRITICAL">Tier 1 — Critical</option>
            <option value="HIGH">Tier 2 — High</option>
            <option value="MEDIUM">Tier 3 — Medium</option>
            <option value="LOW">Tier 4 — Low</option>
          </select>
        </div>

        {/* Reset Filters Action */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={onResetFilters}
            className="flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
            title="Reset all active filters"
          >
            <RotateCcw className="size-3 text-zinc-400" />
            <span>Reset Filters</span>
          </button>
        )}
      </div>
    </div>
  );
};
