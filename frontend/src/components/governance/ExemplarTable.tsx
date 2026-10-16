import React, { useState } from 'react';
import type { FeedbackExemplar } from '../../types/sentrax';
import { SeverityBadge } from '../badges/SeverityBadge';
import { VerdictBadge } from '../badges/VerdictBadge';
import { AssetTierBadge } from '../badges/AssetTierBadge';
import {
  Search,
  BookmarkCheck,
  Ban,
  RotateCcw,
  Sparkles,
  Loader2,
} from 'lucide-react';

interface ExemplarTableProps {
  exemplars: FeedbackExemplar[];
  isLoading: boolean;
  onToggleActive: (id: string, active: boolean) => Promise<void>;
}

export const ExemplarTable: React.FC<ExemplarTableProps> = ({
  exemplars,
  isLoading,
  onToggleActive,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'REVOKED'>('ALL');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const filteredExemplars = exemplars.filter((ex) => {
    // Status filter
    if (statusFilter === 'ACTIVE' && !ex.is_active) return false;
    if (statusFilter === 'REVOKED' && ex.is_active) return false;

    // Search query
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      ex.id.toLowerCase().includes(q) ||
      ex.rule_id.toLowerCase().includes(q) ||
      ex.process_signature.toLowerCase().includes(q) ||
      ex.rationale.toLowerCase().includes(q) ||
      (ex.created_by ? ex.created_by.toLowerCase().includes(q) : false)
    );
  });

  const activeCount = exemplars.filter((e) => e.is_active).length;
  const revokedCount = exemplars.filter((e) => !e.is_active).length;

  const handleActionClick = async (exemplar: FeedbackExemplar) => {
    setUpdatingId(exemplar.id);
    try {
      await onToggleActive(exemplar.id, !exemplar.is_active);
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Control Bar: Search & Status Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-zinc-950 border border-zinc-850">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by rule, process, rationale, or author..."
            className="w-full pl-9 pr-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-700 transition-colors"
          />
        </div>

        {/* Status Filter Pills */}
        <div className="flex items-center gap-1 p-0.5 bg-zinc-900 rounded-lg border border-zinc-800 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setStatusFilter('ALL')}
            className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors cursor-pointer ${
              statusFilter === 'ALL'
                ? 'bg-zinc-800 text-zinc-100 border border-zinc-700 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            All ({exemplars.length})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('ACTIVE')}
            className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors cursor-pointer ${
              statusFilter === 'ACTIVE'
                ? 'bg-zinc-800 text-zinc-100 border border-zinc-700 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Active ({activeCount})
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('REVOKED')}
            className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors cursor-pointer ${
              statusFilter === 'REVOKED'
                ? 'bg-zinc-800 text-zinc-100 border border-zinc-700 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Revoked ({revokedCount})
          </button>
        </div>
      </div>

      {/* Exemplar Governance Table */}
      <div className="rounded-xl border border-zinc-850 bg-zinc-950 overflow-hidden shadow-sm">
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-zinc-850 bg-zinc-900/60 font-mono text-[10px] text-zinc-400 uppercase tracking-wider">
                <th className="py-3 px-4 font-semibold">Exemplar ID &amp; Status</th>
                <th className="py-3 px-4 font-semibold">Target Rule &amp; Process</th>
                <th className="py-3 px-4 font-semibold">Asset Tier</th>
                <th className="py-3 px-4 font-semibold">Calibrated Verdict</th>
                <th className="py-3 px-4 font-semibold max-w-sm">Analyst Justification</th>
                <th className="py-3 px-4 font-semibold">Tier Support &amp; Hits</th>
                <th className="py-3 px-4 font-semibold text-right">Governance Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-850/60">
              {isLoading && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 font-mono">
                    <Loader2 className="size-5 text-cyan-400 animate-spin mx-auto mb-2" />
                    <span>Loading few-shot exemplar registry...</span>
                  </td>
                </tr>
              )}

              {!isLoading && filteredExemplars.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 font-mono space-y-1">
                    <BookmarkCheck className="size-6 text-zinc-600 mx-auto" />
                    <div className="text-zinc-300 font-bold">No feedback exemplars match filter</div>
                    <div className="text-[11px] text-zinc-500 font-sans">
                      Try adjusting search query or status filter.
                    </div>
                  </td>
                </tr>
              )}

              {!isLoading &&
                filteredExemplars.map((ex) => {
                  const isUpdating = updatingId === ex.id;
                  return (
                    <tr
                      key={ex.id}
                      className={`hover:bg-zinc-900/40 transition-colors ${
                        !ex.is_active ? 'opacity-60 bg-zinc-950/40' : ''
                      }`}
                    >
                      {/* ID & Status */}
                      <td className="py-3.5 px-4 font-mono">
                        <div className="font-bold text-zinc-200">{ex.id}</div>
                        <div className="pt-1">
                          {ex.is_active ? (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
                              <span className="size-1 rounded-full bg-emerald-400" />
                              <span>ACTIVE IN PROMPT</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-zinc-900 text-zinc-400 border border-zinc-800">
                              <Ban className="size-2.5 text-zinc-500" />
                              <span>REVOKED (EXCLUDED)</span>
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Target Rule & Process */}
                      <td className="py-3.5 px-4 font-mono">
                        <div className="text-cyan-400 font-semibold">Rule {ex.rule_id}</div>
                        <div className="text-[11px] text-zinc-300 font-mono truncate max-w-[180px]" title={ex.process_signature}>
                          {ex.process_signature}
                        </div>
                      </td>

                      {/* Asset Criticality */}
                      <td className="py-3.5 px-4">
                        <AssetTierBadge tier={ex.asset_criticality} />
                      </td>

                      {/* Calibrated Verdict & Severity */}
                      <td className="py-3.5 px-4">
                        <div className="space-y-1">
                          <VerdictBadge verdict={ex.calibrated_verdict} />
                          <div>
                            <SeverityBadge severity={ex.calibrated_severity} />
                          </div>
                        </div>
                      </td>

                      {/* Analyst Justification */}
                      <td className="py-3.5 px-4 max-w-sm">
                        <div className="text-xs text-zinc-300 font-sans italic line-clamp-2" title={ex.rationale}>
                          "{ex.rationale}"
                        </div>
                        <div className="text-[10px] text-zinc-500 font-mono pt-1">
                          Author: {ex.created_by} • {new Date(ex.created_at).toLocaleDateString()}
                        </div>
                      </td>

                      {/* Tier Support & Hits */}
                      <td className="py-3.5 px-4 font-mono">
                        <span
                          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium border ${
                            ex.match_tier_support === 'Tier 1'
                              ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60'
                              : 'bg-amber-950/60 text-amber-300 border-amber-800/60'
                          }`}
                        >
                          <Sparkles className="size-2.5" />
                          <span>{ex.match_tier_support === 'Tier 1' ? 'Tier 1 (Exact)' : 'Tier 2 (Fallback)'}</span>
                        </span>
                        <div className="text-[10px] text-zinc-400 pt-1">
                          {ex.match_hit_count} historical hits
                        </div>
                      </td>

                      {/* Governance Action: Revoke / Restore */}
                      <td className="py-3.5 px-4 text-right">
                        {ex.is_active ? (
                          <button
                            type="button"
                            onClick={() => handleActionClick(ex)}
                            disabled={isUpdating}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950/50 hover:bg-red-900/60 border border-red-800/80 text-red-300 text-xs font-mono font-medium transition-colors cursor-pointer disabled:opacity-50"
                            title="Revoke exemplar to exclude from future prompt retrieval"
                          >
                            {isUpdating ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <Ban className="size-3 text-red-400" />
                            )}
                            <span>Revoke</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleActionClick(ex)}
                            disabled={isUpdating}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-750 text-zinc-200 text-xs font-mono font-medium transition-colors cursor-pointer disabled:opacity-50"
                            title="Restore exemplar for prompt retrieval"
                          >
                            {isUpdating ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <RotateCcw className="size-3 text-emerald-400" />
                            )}
                            <span>Restore</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

